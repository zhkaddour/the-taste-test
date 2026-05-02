"""Pairwise eval runner — papers + HN domains.

Loads personas from doctrines/ (auto-discovered playbooks + profile stubs) and
adds two model-only baselines (vanilla Sonnet 4.6, vanilla Opus 4.7). For each
(persona × pair × ordering) tuple, asks the model to pick the better artifact,
parses the JSON response, and scores tri-state per pair (+1 consistent-correct
/ 0 inconsistent / -1 consistent-wrong).

Two domains:
  --domain papers  : reads evals/papers/data/eval_papers.json, generates pairs
                     within (domain × year_cohort) cells (good vs bad).
  --domain hn      : reads evals/hn/data/pairs.jsonl + abstracts.jsonl,
                     uses pre-built winner/loser pairs.

Outputs go to evals/{domain}/results/eval_{results,pairs_log}.json.

Usage:
  scripts/run_eval.py --domain papers --smoke
  scripts/run_eval.py --domain hn --resume
  scripts/run_eval.py --domain papers --max-pairs-per-cell 50 --max-pairs 1000
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
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent          # evals/papers/
PROJECT_ROOT = Path(__file__).resolve().parents[3]     # taste-test/
load_dotenv(PROJECT_ROOT / ".env")

PERSONAS_DIR = PROJECT_ROOT / "doctrines"

PAPERS_DATA_PATH = PROJECT_ROOT / "evals" / "papers" / "data" / "eval_papers.json"
PAPERS_RESULTS_DIR = PROJECT_ROOT / "evals" / "papers" / "results"

HN_PAIRS_PATH = PROJECT_ROOT / "evals" / "hn" / "data" / "pairs.jsonl"
HN_ABSTRACTS_PATH = PROJECT_ROOT / "evals" / "hn" / "data" / "abstracts.jsonl"
HN_RESULTS_DIR = PROJECT_ROOT / "evals" / "hn" / "results"

DEFAULT_MODEL = "claude-sonnet-4-6"
OPUS_MODEL = "claude-opus-4-7"
MAX_TOKENS = 400
DEFAULT_CONCURRENCY = 15
DEFAULT_MAX_PAIRS_PER_CELL = 50
DEFAULT_MAX_PAIRS_TOTAL = 1000
DEFAULT_SAME_PAIRS = 1
SAMPLE_SEED = 42

DOMAIN_CONFIG = {
    "papers": {
        "noun_plural": "research papers",
        "noun_singular_cap": "Paper",
    },
    "hn": {
        "noun_plural": "open-source projects",
        "noun_singular_cap": "Project",
    },
}

PROMPT_VANILLA = (
    "You are an expert evaluator. Two anonymized {noun_plural} from {year} are below. "
    "Based on overall substance, importance, and likely impact, which one is more "
    "worth time and effort?\n\n"
    "{noun_singular_cap} A:\n{problem_a}\n\n"
    "{noun_singular_cap} B:\n{problem_b}\n\n"
    "Return JSON only, no preamble or fences:\n"
    '{{"preference": "A" or "B", "reasoning": "one sentence"}}'
)


# ----------------------------- persona loading -----------------------------

def _humanize(person_slug: str) -> str:
    return " ".join(p.capitalize() for p in person_slug.split("-") if p)


def load_personas() -> dict[str, dict]:
    """Load both light and distilled doctrines from per-persona dirs.

    For each `doctrines/<persona-id>/` directory:
      - if doctrine-light.md exists → emit `<persona-id>-light`
      - if doctrine-distilled.md exists → emit `<persona-id>-distilled`

    Each persona record:
      - persona_id: e.g. "peter-thiel-light"
      - name: H1 of the markdown file (display name) + tier suffix
      - tier: "light" | "distilled"
      - profile_text: full markdown file contents
    """
    out: dict[str, dict] = {}
    if not PERSONAS_DIR.exists():
        return out

    for pdir in sorted(PERSONAS_DIR.iterdir()):
        if not pdir.is_dir():
            continue
        if pdir.name.startswith("_") or pdir.name.startswith("."):
            continue

        for tier, filename in [("light", "doctrine-light.md"),
                               ("distilled", "doctrine-distilled.md")]:
            fpath = pdir / filename
            if not fpath.exists():
                continue
            text = fpath.read_text()
            # Display name: H1 of the file, stripping trailing " — Light Doctrine"
            # or "— Three Evaluation Layers" cruft to keep the leaderboard clean.
            first_line = text.splitlines()[0] if text else ""
            name = first_line.lstrip("# ").split("—")[0].strip() or pdir.name
            persona_key = f"{pdir.name}-{tier}"
            out[persona_key] = {
                "persona_id": persona_key,
                "name": f"{name} ({tier})",
                "tier": tier,
                "kind": "doctrine",
                "profile_text": text,
                "model": DEFAULT_MODEL,
            }

    # Vanilla baselines (no doctrine, just the model)
    out["vanilla_sonnet_4_6"] = {
        "persona_id": "vanilla_sonnet_4_6",
        "name": "Vanilla Sonnet 4.6 (no doctrine)",
        "tier": "baseline",
        "kind": "vanilla",
        "profile_text": "",
        "model": DEFAULT_MODEL,
    }
    out["vanilla_opus_4_7"] = {
        "persona_id": "vanilla_opus_4_7",
        "name": "Vanilla Opus 4.7 (no doctrine)",
        "tier": "baseline",
        "kind": "vanilla",
        "profile_text": "",
        "model": OPUS_MODEL,
    }

    return out


# ----------------------------- pair loading -----------------------------

def load_papers_pairs(max_per_cell: int, max_total: int, n_same: int,
                      seed: int) -> tuple[list[dict], dict]:
    """Generate within-(domain × cohort) good-vs-bad pairs from eval_papers.json.

    Returns (pairs, papers_by_id).
    """
    if not PAPERS_DATA_PATH.exists():
        sys.exit(f"Missing {PAPERS_DATA_PATH}")
    raw = json.loads(PAPERS_DATA_PATH.read_text())
    papers = raw["papers"]
    papers_by_id = {p["paper_id"]: p for p in papers}

    rng = random.Random(seed)
    by_cell: dict[tuple, list[dict]] = {}
    for p in papers:
        key = (p.get("domain"), p["year_cohort"])
        by_cell.setdefault(key, []).append(p)

    # 1:1 matching within each cell: each paper appears in at most one pair.
    # This keeps pair observations independent (matches HN methodology).
    pairs: list[dict] = []
    for (domain, cohort), papers_in_cell in sorted(by_cell.items()):
        good = [p for p in papers_in_cell if p["tier"] == "good"]
        bad = [p for p in papers_in_cell if p["tier"] == "bad"]
        if not good or not bad:
            continue
        rng.shuffle(good)
        rng.shuffle(bad)
        n_pairs = min(len(good), len(bad), max_per_cell)
        for i in range(n_pairs):
            g, b = good[i], bad[i]
            # Randomize side_a/side_b assignment (defeat positional priors)
            if rng.random() < 0.5:
                side_a, side_b = g, b
            else:
                side_a, side_b = b, g
            pairs.append({
                "pair_id": _make_pair_id(side_a["paper_id"], side_b["paper_id"]),
                "kind": "cross",
                "cohort_key": f"{domain}__{cohort}",
                "year": _papers_year(side_a, side_b, cohort),
                "side_a_id": side_a["paper_id"],
                "side_b_id": side_b["paper_id"],
                "side_a_abstract": side_a["anonymized_problem"],
                "side_b_abstract": side_b["anonymized_problem"],
                "correct_side": "A" if side_a["tier"] == "good" else "B",
            })

    rng.shuffle(pairs)
    if max_total and len(pairs) > max_total:
        pairs = pairs[:max_total]

    # Same-tier-good calibration pairs (per cell)
    if n_same > 0:
        for (domain, cohort), papers_in_cell in sorted(by_cell.items()):
            goods = [p for p in papers_in_cell if p["tier"] == "good"]
            if len(goods) < 2:
                continue
            all_same = list(combinations(goods, 2))
            rng.shuffle(all_same)
            for a, b in all_same[:n_same]:
                pairs.append({
                    "pair_id": _make_pair_id(a["paper_id"], b["paper_id"]),
                    "kind": "same",
                    "cohort_key": f"{domain}__{cohort}",
                    "year": _papers_year(a, b, cohort),
                    "side_a_id": a["paper_id"],
                    "side_b_id": b["paper_id"],
                    "side_a_abstract": a["anonymized_problem"],
                    "side_b_abstract": b["anonymized_problem"],
                    "correct_side": None,  # not scored
                })

    meta = {"by_cell": {f"{d}__{c}": len(v) for (d, c), v in by_cell.items()}}
    return pairs, meta, papers_by_id


def load_hn_pairs(max_total: int, seed: int) -> tuple[list[dict], dict]:
    """Read pairs.jsonl + abstracts.jsonl, return unified-pair format."""
    if not HN_PAIRS_PATH.exists():
        sys.exit(f"Missing {HN_PAIRS_PATH}")
    if not HN_ABSTRACTS_PATH.exists():
        sys.exit(f"Missing {HN_ABSTRACTS_PATH}")

    abstracts: dict[tuple[str, str], str] = {}
    with HN_ABSTRACTS_PATH.open() as f:
        for line in f:
            r = json.loads(line)
            if r.get("abstract"):
                abstracts[(r["gh_owner"], r["gh_repo"])] = r["abstract"]

    rng = random.Random(seed)
    pairs: list[dict] = []
    skipped_no_abstract = 0
    with HN_PAIRS_PATH.open() as f:
        for line in f:
            p = json.loads(line)
            w_key = (p["winner"]["gh_owner"], p["winner"]["gh_repo"])
            l_key = (p["loser"]["gh_owner"], p["loser"]["gh_repo"])
            wa = abstracts.get(w_key)
            la = abstracts.get(l_key)
            if not wa or not la:
                skipped_no_abstract += 1
                continue
            if rng.random() < 0.5:
                side_a_id, side_b_id, side_a_text, side_b_text, correct = (
                    f"{w_key[0]}/{w_key[1]}", f"{l_key[0]}/{l_key[1]}", wa, la, "A")
            else:
                side_a_id, side_b_id, side_a_text, side_b_text, correct = (
                    f"{l_key[0]}/{l_key[1]}", f"{w_key[0]}/{w_key[1]}", la, wa, "B")
            year = int(p["cohort_quarter"][:4]) if p.get("cohort_quarter") else None
            pairs.append({
                "pair_id": p["pair_id"],
                "kind": "cross",
                "cohort_key": f"{p['cohort_quarter']}__{p['cohort_language']}",
                "year": year,
                "side_a_id": side_a_id,
                "side_b_id": side_b_id,
                "side_a_abstract": side_a_text,
                "side_b_abstract": side_b_text,
                "correct_side": correct,
            })

    rng.shuffle(pairs)
    if max_total and len(pairs) > max_total:
        pairs = pairs[:max_total]

    meta = {"skipped_no_abstract": skipped_no_abstract}
    return pairs, meta, {}  # papers_by_id unused for HN


def _make_pair_id(id_a: str, id_b: str) -> str:
    a, b = sorted([id_a, id_b])
    return f"{a}__{b}"


def _papers_year(a: dict, b: dict, cohort: str) -> int:
    """Pick a representative year for the prompt (avoid future-knowledge bias)."""
    ya = a.get("year")
    yb = b.get("year")
    if ya and yb:
        return min(ya, yb)
    if ya:
        return ya
    if yb:
        return yb
    if cohort and "-" in cohort:
        return int(cohort.split("-")[0])
    if cohort and cohort.isdigit():
        return int(cohort)
    return 2020


# ----------------------------- judgment loop -----------------------------

def parse_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def make_judgment(client: Anthropic, persona: dict, pair: dict, ordering: str,
                  domain_cfg: dict) -> dict:
    if ordering == "AB":
        prob_a, prob_b = pair["side_a_abstract"], pair["side_b_abstract"]
    else:
        prob_a, prob_b = pair["side_b_abstract"], pair["side_a_abstract"]

    base = {
        "persona_id": persona["persona_id"],
        "model": persona["model"],
        "pair_id": pair["pair_id"],
        "kind": pair["kind"],
        "cohort_key": pair["cohort_key"],
        "side_a_id": pair["side_a_id"],
        "side_b_id": pair["side_b_id"],
        "ordering": ordering,
        "preference_normalized": None,
        "reasoning": None,
        "raw_response": None,
        "input_tokens": None,
        "cached_tokens": None,
        "output_tokens": None,
        "error": None,
    }

    try:
        if persona["kind"] == "vanilla":
            prompt = PROMPT_VANILLA.format(
                noun_plural=domain_cfg["noun_plural"],
                noun_singular_cap=domain_cfg["noun_singular_cap"],
                year=pair["year"],
                problem_a=prob_a,
                problem_b=prob_b,
            )
            content = [{"type": "text", "text": prompt}]
        else:
            persona_block = (
                "You are channeling " + persona["name"]
                + f"'s taste to evaluate {domain_cfg['noun_plural']}."
                  f" Use their priors and voice.\n\nTheir doctrine:\n"
                + persona["profile_text"]
            )
            pair_block = (
                f"\n\nTwo anonymized {domain_cfg['noun_plural']} from {pair['year']}. "
                f"Based on their taste, which one is more worth their time and effort?\n\n"
                f"{domain_cfg['noun_singular_cap']} A:\n{prob_a}\n\n"
                f"{domain_cfg['noun_singular_cap']} B:\n{prob_b}\n\n"
                "Return JSON only, no preamble or fences:\n"
                '{"preference": "A" or "B", "reasoning": "one sentence in their voice"}'
            )
            content = [
                {"type": "text", "text": persona_block,
                 "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": pair_block},
            ]

        msg = client.messages.create(
            model=persona["model"],
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": content}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        base["raw_response"] = text
        base["input_tokens"] = msg.usage.input_tokens
        base["cached_tokens"] = (
            getattr(msg.usage, "cache_read_input_tokens", 0) or 0)
        base["output_tokens"] = msg.usage.output_tokens

        parsed = parse_response(text)
        raw = (parsed.get("preference") or "").strip().upper()
        if raw not in ("A", "B"):
            base["error"] = f"unexpected preference '{raw}'"
            return base
        # Normalize back to canonical (side_a, side_b) frame:
        if ordering == "AB":
            base["preference_normalized"] = raw
        else:
            base["preference_normalized"] = "B" if raw == "A" else "A"
        base["reasoning"] = (parsed.get("reasoning") or "").strip()
    except Exception as e:
        base["error"] = f"{type(e).__name__}: {e}"
    return base


# ----------------------------- scoring -----------------------------

def compute_results(judgments: list[dict], persona_ids: list[str]) -> dict:
    """Tri-state scoring per (persona × pair). Same-kind pairs are excluded.

    Each judgment carries `_correct_side` (stashed at submit-time from the
    canonical pair). For a (persona × pair), we need both AB and BA orderings;
    consistent + matches correct_side = +1, consistent + wrong = -1, flipped = 0.
    """
    grouped: dict[tuple, dict[str, dict]] = {}
    for j in judgments:
        if j.get("preference_normalized") is None or j["kind"] != "cross":
            continue
        key = (j["persona_id"], j["pair_id"])
        grouped.setdefault(key, {})[j["ordering"]] = j

    rows = []
    for pid in persona_ids:
        plus = zero = minus = n = 0
        for (persona_key, _pair_id), ordering in grouped.items():
            if persona_key != pid:
                continue
            if "AB" not in ordering or "BA" not in ordering:
                continue
            ab = ordering["AB"]["preference_normalized"]
            ba = ordering["BA"]["preference_normalized"]
            n += 1
            if ab != ba:
                zero += 1
                continue
            cs = (ordering["AB"].get("_correct_side")
                  or ordering["BA"].get("_correct_side"))
            if cs is None:
                continue
            if ab == cs:
                plus += 1
            else:
                minus += 1
        rows.append({
            "persona_id": pid,
            "score": plus - minus,
            "plus_one": plus,
            "zero": zero,
            "minus_one": minus,
            "n_pairs": n,
        })
    rows.sort(key=lambda r: -r["score"])
    return {"leaderboard": rows}


# ----------------------------- main -----------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--domain", choices=["papers", "hn"], required=True)
    ap.add_argument("--smoke", action="store_true",
                    help="3 personas × 5 cross + 1 same (for sanity)")
    ap.add_argument("--max-pairs-per-cell", type=int,
                    default=DEFAULT_MAX_PAIRS_PER_CELL,
                    help="Papers only: cap pairs per (domain × cohort) cell")
    ap.add_argument("--max-pairs", type=int, default=DEFAULT_MAX_PAIRS_TOTAL,
                    help="Cap total pairs after generation/loading")
    ap.add_argument("--same-pairs", type=int, default=DEFAULT_SAME_PAIRS,
                    help="Papers only: same-tier-good calibration pairs per cell")
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    ap.add_argument("--resume", action="store_true",
                    help="Skip judgments already in pairs log")
    ap.add_argument("--seed", type=int, default=SAMPLE_SEED)
    ap.add_argument("--personas", default=None,
                    help="Comma-separated persona_id subset (default: all)")
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY before running.", file=sys.stderr)
        return 1

    domain_cfg = DOMAIN_CONFIG[args.domain]
    results_dir = (PAPERS_RESULTS_DIR if args.domain == "papers"
                   else HN_RESULTS_DIR)
    results_dir.mkdir(parents=True, exist_ok=True)
    results_path = results_dir / "eval_results.json"
    pairs_log_path = results_dir / "eval_pairs_log.json"

    # Load data
    if args.domain == "papers":
        pairs, pair_meta, _papers_by_id = load_papers_pairs(
            max_per_cell=args.max_pairs_per_cell,
            max_total=args.max_pairs,
            n_same=args.same_pairs,
            seed=args.seed,
        )
    else:
        pairs, pair_meta, _papers_by_id = load_hn_pairs(
            max_total=args.max_pairs,
            seed=args.seed,
        )

    # Load personas
    personas = load_personas()
    if args.personas:
        keep = set(args.personas.split(","))
        personas = {k: v for k, v in personas.items() if k in keep}
    if args.smoke:
        keep = list(personas.keys())[:3]
        personas = {k: personas[k] for k in keep}
        pairs = pairs[:5]
        # add 1 same-pair if any exist
        same = [p for p in pairs if p["kind"] == "same"]
        if not same and args.domain == "papers":
            print("  smoke: no same-pair found in first 5; that's ok")

    print(f"Domain: {args.domain}")
    print(f"Pairs:  {len(pairs)} ({sum(1 for p in pairs if p['kind']=='cross')} cross, "
          f"{sum(1 for p in pairs if p['kind']=='same')} same)")
    print(f"Personas: {len(personas)}")
    by_kind: dict = {}
    for p in personas.values():
        by_kind[p["kind"]] = by_kind.get(p["kind"], 0) + 1
    print(f"  by kind: {by_kind}")

    # Build task list
    tasks: list[tuple] = []
    pair_by_id = {p["pair_id"]: p for p in pairs}
    for pair in pairs:
        for ordering in ("AB", "BA"):
            for persona_id in personas:
                tasks.append((persona_id, pair["pair_id"], ordering))

    # Resume support
    existing: list[dict] = []
    if args.resume and pairs_log_path.exists():
        existing = json.loads(pairs_log_path.read_text()).get("judgments", [])
        done = {(j["persona_id"], j["pair_id"], j["ordering"])
                for j in existing if j.get("error") is None}
        before = len(tasks)
        tasks = [t for t in tasks if (t[0], t[1], t[2]) not in done]
        print(f"Resume: {len(existing)} existing, {before - len(tasks)} skipped.")

    print(f"\nRunning {len(tasks)} tasks at concurrency {args.concurrency}.")

    judgments = list(existing)
    if tasks:
        client = Anthropic()
        log_lock = Lock()
        start = time.time()
        completed = 0

        def submit(t):
            persona_id, pair_id, ordering = t
            j = make_judgment(client, personas[persona_id],
                              pair_by_id[pair_id], ordering, domain_cfg)
            # Stash correct_side on the judgment for scoring
            j["_correct_side"] = pair_by_id[pair_id].get("correct_side")
            return j

        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futures = [ex.submit(submit, t) for t in tasks]
            for fut in as_completed(futures):
                j = fut.result()
                with log_lock:
                    judgments.append(j)
                    completed += 1
                    if completed % 30 == 0 or completed == len(tasks):
                        pairs_log_path.write_text(json.dumps(
                            {"judgments": judgments}, indent=2))
                        elapsed = time.time() - start
                        rate = completed / elapsed if elapsed else 0
                        eta = (len(tasks) - completed) / rate if rate else 0
                        errs = sum(1 for x in judgments if x.get("error"))
                        print(f"  {completed}/{len(tasks)}  rate={rate:.1f}/s  "
                              f"eta={eta:.0f}s  errors={errs}")

        pairs_log_path.write_text(json.dumps({"judgments": judgments}, indent=2))

    # Score
    persona_ids = list(personas.keys())
    metrics = compute_results(judgments, persona_ids)
    for row in metrics["leaderboard"]:
        p = personas.get(row["persona_id"])
        row["persona_name"] = p["name"] if p else row["persona_id"]
        row["model"] = p["model"] if p else None
        row["kind"] = p["kind"] if p else None

    err_count = sum(1 for j in judgments if j.get("error"))
    results_path.write_text(json.dumps({
        "metadata": {
            "domain": args.domain,
            "n_pairs": len(pairs),
            "n_cross": sum(1 for p in pairs if p["kind"] == "cross"),
            "n_same": sum(1 for p in pairs if p["kind"] == "same"),
            "n_personas": len(personas),
            "n_judgments": len(judgments),
            "n_errors": err_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "seed": args.seed,
            "pair_meta": pair_meta,
        },
        "leaderboard": metrics["leaderboard"],
        "pair_index": [
            {
                "pair_id": p["pair_id"],
                "kind": p["kind"],
                "cohort_key": p["cohort_key"],
                "side_a_id": p["side_a_id"],
                "side_b_id": p["side_b_id"],
                "correct_side": p["correct_side"],
                "year": p["year"],
            }
            for p in pairs
        ],
    }, indent=2))

    print(f"\nWrote {results_path}")
    print(f"Wrote {pairs_log_path} ({len(judgments)} judgments, {err_count} errors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
