"""Pairwise eval runner.

Generates within-cohort pairs from data/eval_papers.json, asks each persona to
pick the better paper in both AB and BA orderings, scores tri-state per pair
(+1 consistent-correct / 0 inconsistent / -1 consistent-wrong), and writes
data/eval_results.json + data/eval_pairs_log.json.

Usage:
  scripts/run_eval.py --smoke                       # 2 personas x 3 cross + 1 same (smoke test)
  scripts/run_eval.py                                # full run with defaults (20 cross + 1 same)
  scripts/run_eval.py --resume                      # skip judgments already in pairs log
  scripts/run_eval.py --cross-pairs 30 --same-pairs 2
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from threading import Lock

from anthropic import Anthropic

ROOT = Path(__file__).resolve().parent.parent          # evals/papers/
PROJECT_ROOT = Path(__file__).resolve().parents[3]     # taste-test/
PAPERS_PATH = ROOT / "data" / "eval_papers.json"
PERSONAS_DIR = PROJECT_ROOT / "doctrines"
DOCTRINES_DIR = PROJECT_ROOT / "doctrines" / "_playbooks"
RESULTS_PATH = ROOT / "results" / "eval_results.json"
PAIRS_LOG_PATH = ROOT / "results" / "eval_pairs_log.json"

# Map doctrine markdown filenames to (persona_id, display_name)
DOCTRINE_MAP = {
    "the-thiel-doctrine.md":      ("peter_thiel_ourplaybook",     "Peter Thiel-OurPlaybook"),
    "the-andreessen-doctrine.md": ("marc_andreessen_ourplaybook", "Marc Andreessen-OurPlaybook"),
    "the-graham-doctrine.md":     ("paul_graham_ourplaybook",     "Paul Graham-OurPlaybook"),
    "the-buffett-doctrine.md":    ("warren_buffett_ourplaybook",  "Warren Buffett-OurPlaybook"),
}

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 400
DEFAULT_CROSS_PAIRS = 20  # 10 from each cohort
DEFAULT_SAME_PAIRS = 1
DEFAULT_CONCURRENCY = 15
SAMPLE_SEED = 42

PROMPT_INTRO = """You are channeling {name}'s taste to judge research papers. Use their priors and voice.

Their {profile_label}:
"""

PROMPT_TRAILER = """

Two anonymized research problems. Based on their taste, which is more worth working on?

Problem A:
{problem_a}

Problem B:
{problem_b}

Return JSON only, no preamble or fences:
{{"preference": "A" or "B", "reasoning": "one sentence in their voice"}}"""


def load_personas() -> dict[str, dict]:
    """Load both stub profiles and doctrine playbooks into one dict.

    Each persona record has:
      - persona_id, name, version, format ("json"|"markdown"), profile_text
    """
    out: dict[str, dict] = {}
    # Stubs from personas/<id>/profile.json
    if PERSONAS_DIR.exists():
        for pdir in sorted(PERSONAS_DIR.iterdir()):
            if not pdir.is_dir():
                continue
            prof = pdir / "profile.json"
            if not prof.exists():
                continue
            payload = json.loads(prof.read_text())
            out[pdir.name] = {
                "persona_id": pdir.name,
                "name": payload.get("name", pdir.name),
                "version": payload.get("version", "v0-stub"),
                "format": "json",
                "profile_text": json.dumps(payload, indent=2),
            }
    # Doctrines from data/personas/the-*-doctrine.md
    if DOCTRINES_DIR.exists():
        for fname, (pid, display_name) in DOCTRINE_MAP.items():
            fpath = DOCTRINES_DIR / fname
            if not fpath.exists():
                continue
            text = fpath.read_text()
            out[pid] = {
                "persona_id": pid,
                "name": display_name,
                "version": "v1-ourplaybook",
                "format": "markdown",
                "profile_text": text,
            }
    return out


def load_papers() -> list[dict]:
    return json.loads(PAPERS_PATH.read_text())["papers"]


def generate_pairs(papers: list[dict], n_cross: int, n_same: int, seed: int) -> tuple[list[dict], list[dict]]:
    """Generate within-cohort pairs.

    Returns (cross_pairs, same_pairs). Each entry: {paper_a, paper_b, kind, cohort}.
    Cross pairs split balanced across cohorts (n_cross/2 from each).
    """
    rng = random.Random(seed)
    by_cohort: dict[str, list[dict]] = {}
    for p in papers:
        by_cohort.setdefault(p["year_cohort"], []).append(p)

    # CROSS-tier pairs: split evenly across cohorts
    cross_pairs: list[dict] = []
    cohorts = sorted(by_cohort.keys())
    per_cohort = max(1, n_cross // len(cohorts))
    remainder = n_cross - per_cohort * len(cohorts)
    for i, cohort in enumerate(cohorts):
        target = per_cohort + (1 if i < remainder else 0)
        good = [p for p in by_cohort[cohort] if p["tier"] == "good"]
        bad = [p for p in by_cohort[cohort] if p["tier"] == "bad"]
        all_pairs = [(g, b) for g in good for b in bad]
        rng.shuffle(all_pairs)
        for g, b in all_pairs[:target]:
            # Randomize which is paper_a vs paper_b so we don't always have good=A
            if rng.random() < 0.5:
                a, b_ = g, b
            else:
                a, b_ = b, g
            cross_pairs.append({"paper_a": a, "paper_b": b_, "kind": "cross", "cohort": cohort})

    # SAME-tier-good pairs: pick from one cohort (alternate or stick to cohort with more papers)
    same_pairs: list[dict] = []
    same_target_cohort = max(cohorts, key=lambda c: sum(1 for p in by_cohort[c] if p["tier"] == "good"))
    goods = [p for p in by_cohort[same_target_cohort] if p["tier"] == "good"]
    all_same = list(combinations(goods, 2))
    rng.shuffle(all_same)
    for a, b in all_same[:n_same]:
        same_pairs.append({"paper_a": a, "paper_b": b, "kind": "same", "cohort": same_target_cohort})

    return cross_pairs, same_pairs


def make_pair_id(paper_a: dict, paper_b: dict) -> str:
    a, b = sorted([paper_a["paper_id"], paper_b["paper_id"]])
    return f"{a}__{b}"


def parse_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def make_judgment(client: Anthropic, persona_id: str, profile: dict,
                  pair_id: str, paper_a: dict, paper_b: dict,
                  ordering: str, kind: str, cohort: str) -> dict:
    if ordering == "AB":
        first, second = paper_a, paper_b
    else:
        first, second = paper_b, paper_a

    profile_label = "playbook" if profile["format"] == "markdown" else "stub profile"
    cache_block_text = (
        PROMPT_INTRO.format(name=profile["name"], profile_label=profile_label)
        + profile["profile_text"]
    )
    pair_block_text = PROMPT_TRAILER.format(
        problem_a=first["anonymized_problem"],
        problem_b=second["anonymized_problem"],
    )

    base = {
        "persona_id": persona_id,
        "pair_id": pair_id,
        "kind": kind,
        "cohort": cohort,
        "paper_a_id": paper_a["paper_id"],
        "paper_b_id": paper_b["paper_id"],
        "ordering": ordering,
        "preference_normalized": None,  # 'A' or 'B' in original (paper_a, paper_b) frame
        "reasoning": None,
        "error": None,
    }
    try:
        msg = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": cache_block_text,
                        # Cache the persona-profile portion. Only takes effect for blocks
                        # >= ~1024 tokens (i.e., doctrine playbooks). Stubs are below the
                        # threshold so cache_control is a no-op for them.
                        "cache_control": {"type": "ephemeral"},
                    },
                    {"type": "text", "text": pair_block_text},
                ],
            }],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        parsed = parse_response(text)
        raw = parsed.get("preference", "").strip().upper()
        if raw not in ("A", "B"):
            base["error"] = f"unexpected preference '{raw}'"
            return base
        # Normalize back to original (paper_a, paper_b) frame:
        # ordering='AB': model 'A' = paper_a, model 'B' = paper_b -> identity
        # ordering='BA': model 'A' = paper_b, model 'B' = paper_a -> flip
        if ordering == "AB":
            base["preference_normalized"] = raw
        else:
            base["preference_normalized"] = "B" if raw == "A" else "A"
        base["reasoning"] = parsed.get("reasoning", "").strip()
    except Exception as e:
        base["error"] = f"{type(e).__name__}: {e}"
    return base


def compute_results(judgments: list[dict], papers: list[dict], persona_ids: list[str]) -> dict:
    paper_by_id = {p["paper_id"]: p for p in papers}
    # Group by (persona, pair) -> {ordering: judgment}
    grouped: dict[tuple, dict] = {}
    for j in judgments:
        if j.get("preference_normalized") is None:
            continue
        key = (j["persona_id"], j["pair_id"])
        grouped.setdefault(key, {})[j["ordering"]] = j

    leaderboard_rows = []
    for pid in persona_ids:
        plus_one = zero = minus_one = 0
        n_with_both = 0
        for key, ords in grouped.items():
            p, pair_id = key
            if p != pid: continue
            if "AB" not in ords or "BA" not in ords: continue
            j = ords["AB"]
            if j["kind"] != "cross": continue  # only cross-tier counts
            n_with_both += 1
            ab = ords["AB"]["preference_normalized"]
            ba = ords["BA"]["preference_normalized"]
            if ab != ba:
                zero += 1
                continue
            # Consistent. Did they pick the higher-citation (=good-tier) paper?
            chosen_id = ords["AB"]["paper_a_id"] if ab == "A" else ords["AB"]["paper_b_id"]
            good_id = ords["AB"]["paper_a_id"] if paper_by_id[ords["AB"]["paper_a_id"]]["tier"] == "good" else ords["AB"]["paper_b_id"]
            if chosen_id == good_id:
                plus_one += 1
            else:
                minus_one += 1
        score = plus_one - minus_one
        leaderboard_rows.append({
            "persona_id": pid,
            "score": score,
            "plus_one": plus_one,
            "zero": zero,
            "minus_one": minus_one,
            "n_pairs": n_with_both,
        })
    leaderboard_rows.sort(key=lambda r: -r["score"])
    return {"leaderboard": leaderboard_rows}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--smoke", action="store_true", help="2 personas x 3 cross + 1 same")
    ap.add_argument("--cross-pairs", type=int, default=DEFAULT_CROSS_PAIRS)
    ap.add_argument("--same-pairs", type=int, default=DEFAULT_SAME_PAIRS)
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    ap.add_argument("--resume", action="store_true", help="Skip judgments already in pairs log")
    ap.add_argument("--seed", type=int, default=SAMPLE_SEED)
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY before running.", file=sys.stderr)
        return 1
    if not PAPERS_PATH.exists():
        print(f"Missing {PAPERS_PATH}", file=sys.stderr)
        return 1

    papers = load_papers()
    personas = load_personas()
    print(f"Loaded {len(papers)} papers, {len(personas)} personas.")

    if args.smoke:
        keep = list(personas.keys())[:2]
        personas = {k: personas[k] for k in keep}
        n_cross, n_same = 3, 1
        print(f"  smoke: personas={list(personas.keys())} cross={n_cross} same={n_same}")
    else:
        n_cross, n_same = args.cross_pairs, args.same_pairs

    cross_pairs, same_pairs = generate_pairs(papers, n_cross, n_same, args.seed)
    print(f"Pairs: {len(cross_pairs)} cross-tier (within cohort), {len(same_pairs)} same-tier-good")
    for p in cross_pairs + same_pairs:
        a, b = p["paper_a"], p["paper_b"]
        print(f"  [{p['kind']}|{p['cohort']}] {a['paper_id'][:8]}({a['tier']},{a['citation_count']}) vs {b['paper_id'][:8]}({b['tier']},{b['citation_count']})")

    # Build task list
    all_pairs = cross_pairs + same_pairs
    tasks: list[tuple] = []
    for pair in all_pairs:
        pid = make_pair_id(pair["paper_a"], pair["paper_b"])
        for ordering in ("AB", "BA"):
            for persona_id in personas:
                tasks.append((persona_id, pid, pair, ordering))

    existing: list[dict] = []
    if args.resume and PAIRS_LOG_PATH.exists():
        existing = json.loads(PAIRS_LOG_PATH.read_text()).get("judgments", [])
        done = {(j["persona_id"], j["pair_id"], j["ordering"]) for j in existing if j.get("error") is None}
        before = len(tasks)
        tasks = [t for t in tasks if (t[0], t[1], t[3]) not in done]
        print(f"Resume: {len(existing)} existing, {before - len(tasks)} skipped.")

    print(f"\nRunning {len(tasks)} tasks at concurrency {args.concurrency} via {MODEL}.")

    judgments = list(existing)
    if tasks:
        client = Anthropic()
        log_lock = Lock()
        start = time.time()
        completed = 0

        def submit(t):
            persona_id, pair_id, pair, ordering = t
            return make_judgment(client, persona_id, personas[persona_id], pair_id,
                                 pair["paper_a"], pair["paper_b"], ordering,
                                 pair["kind"], pair["cohort"])

        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futures = [ex.submit(submit, t) for t in tasks]
            for fut in as_completed(futures):
                j = fut.result()
                with log_lock:
                    judgments.append(j)
                    completed += 1
                    if completed % 30 == 0 or completed == len(tasks):
                        PAIRS_LOG_PATH.write_text(json.dumps({"judgments": judgments}, indent=2))
                        elapsed = time.time() - start
                        rate = completed / elapsed if elapsed else 0
                        eta = (len(tasks) - completed) / rate if rate else 0
                        errs = sum(1 for x in judgments if x.get("error"))
                        print(f"  {completed}/{len(tasks)}  rate={rate:.1f}/s  eta={eta:.0f}s  errors={errs}")

        PAIRS_LOG_PATH.write_text(json.dumps({"judgments": judgments}, indent=2))

    persona_ids = list(personas.keys())
    metrics = compute_results(judgments, papers, persona_ids)
    # Attach persona names for the leaderboard
    for row in metrics["leaderboard"]:
        row["persona_name"] = personas[row["persona_id"]]["name"]

    err_count = sum(1 for j in judgments if j.get("error"))
    RESULTS_PATH.write_text(json.dumps({
        "metadata": {
            "n_papers": len(papers),
            "n_cross_pairs": len(cross_pairs),
            "n_same_pairs": len(same_pairs),
            "n_personas": len(personas),
            "n_judgments": len(judgments),
            "n_errors": err_count,
            "model": MODEL,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "seed": args.seed,
        },
        "leaderboard": metrics["leaderboard"],
        "pair_index": [
            {
                "pair_id": make_pair_id(p["paper_a"], p["paper_b"]),
                "kind": p["kind"],
                "cohort": p["cohort"],
                "paper_a_id": p["paper_a"]["paper_id"],
                "paper_b_id": p["paper_b"]["paper_id"],
            }
            for p in all_pairs
        ],
    }, indent=2))
    print(f"\nWrote {RESULTS_PATH}")
    print(f"Wrote {PAIRS_LOG_PATH} ({len(judgments)} judgments, {err_count} errors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
