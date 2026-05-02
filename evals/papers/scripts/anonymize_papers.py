"""Step 4: anonymize abstracts via Claude.

Reads data/selected_papers.json, calls claude-sonnet-4-6 with concurrency cap 5,
writes data/eval_papers.json (final eval input) and data/anonymization_log.json
(originals + rewrites side-by-side for spot checking).

Personas judge papers by abstract alone. Output drops author names, original
title is kept only for our reference, anonymized_problem is the only field
the eval should read.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from anthropic import Anthropic

ROOT = Path(__file__).resolve().parent.parent
IN_PATH = ROOT / "data" / "selected_papers.json"
OUT_PATH = ROOT / "data" / "eval_papers.json"
LOG_PATH = ROOT / "results" / "anonymization_log.json"

MODEL = "claude-sonnet-4-6"
CONCURRENCY = 5
MAX_TOKENS = 600

PROMPT_TEMPLATE = """You are rewriting a research paper abstract into a neutral problem statement that strips identifying signals.

Goals:
- Remove any "we propose", "we present", "in this paper" framing
- Remove specific method names that signal a famous paper (e.g., "BERT", "Transformer", "ResNet" — but only if they're presented as the paper's own contribution; if they're cited as prior work, leave them)
- Remove author or institution references
- KEEP benchmark numbers and the names of standard benchmark datasets (e.g., "achieves 92.3% on ImageNet" should stay) — they are signal for judging the paper, not identifying metadata to strip
- Keep the actual research question, the approach, the type of finding
- Output 2-4 sentences in third-person neutral voice

The output should let a reader understand WHAT problem was studied and HOW, but not WHICH paper this is.

Original abstract:
{abstract}

Original title (for context, do not include in output):
{title}

Return ONLY a JSON object with no markdown fence, no commentary:
{{
  "anonymized_problem": "...",
  "anonymization_notes": "brief note on what you stripped"
}}"""


def anonymize_one(client: Anthropic, paper: dict) -> tuple[dict, str | None]:
    """Returns (record_for_eval_papers, error_message_or_None)."""
    pid = paper["paperId"]
    title = paper.get("title") or ""
    abstract = paper.get("abstract") or ""
    prompt = PROMPT_TEMPLATE.format(abstract=abstract, title=title)
    try:
        msg = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in msg.content if block.type == "text").strip()
        # Some defensive parsing in case the model wraps JSON in a fence.
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        parsed = json.loads(text)
        anon = parsed["anonymized_problem"].strip()
        notes = parsed.get("anonymization_notes", "").strip()
    except Exception as e:
        return ({"paperId": pid}, f"{type(e).__name__}: {e}")

    record = {
        "paper_id": pid,
        "year": paper.get("year"),
        "year_cohort": paper.get("year_cohort"),
        "venue": "NeurIPS",
        "subdomain": paper.get("subdomain"),
        "tier": paper.get("tier"),
        "citation_count": paper.get("citationCount"),
        "citation_percentile": paper.get("citation_percentile"),
        "arxiv_primary_category": paper.get("arxiv_primary_category"),
        "anonymized_problem": anon,
        "original_title": title,
        "original_abstract": abstract,
    }
    log_entry = {
        "paper_id": pid,
        "original_title": title,
        "original_abstract": abstract,
        "anonymized_problem": anon,
        "anonymization_notes": notes,
        "tier": paper.get("tier"),
        "subdomain": paper.get("subdomain"),
        "year_cohort": paper.get("year_cohort"),
    }
    return ({"record": record, "log": log_entry}, None)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int, help="Only process first N papers (for smoke test)")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY in your env before running.", file=sys.stderr)
        return 1
    if not IN_PATH.exists():
        print(f"Missing {IN_PATH}. Run select_papers.py first.", file=sys.stderr)
        return 1
    if OUT_PATH.exists() and not args.force:
        print(f"{OUT_PATH} exists. Use --force to re-anonymize.")
        return 0

    raw = json.loads(IN_PATH.read_text())
    papers = raw["papers"]
    if args.limit:
        papers = papers[:args.limit]

    client = Anthropic()
    print(f"Anonymizing {len(papers)} papers via {MODEL} (concurrency={CONCURRENCY})")

    results: list[dict] = []
    failures: list[dict] = []
    done = 0
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futures = {ex.submit(anonymize_one, client, p): p for p in papers}
        for fut in as_completed(futures):
            paper = futures[fut]
            res, err = fut.result()
            done += 1
            if err:
                failures.append({"paper_id": paper["paperId"], "error": err, "title": paper.get("title")})
                print(f"  [{done}/{len(papers)}] FAILED  {paper['paperId']}  {err[:80]}")
            else:
                results.append(res)
                print(f"  [{done}/{len(papers)}] ok      {paper['paperId']}  ({paper.get('tier')}, {paper.get('subdomain')})")

    eval_papers = [r["record"] for r in results]
    log_entries = [r["log"] for r in results]
    OUT_PATH.write_text(json.dumps({"papers": eval_papers}, indent=2))
    LOG_PATH.write_text(json.dumps({"entries": log_entries, "failures": failures}, indent=2))

    print(f"\nWrote {len(eval_papers)} records to {OUT_PATH}")
    print(f"Wrote anonymization log to {LOG_PATH}")
    if failures:
        print(f"\n{len(failures)} failures:")
        for f in failures:
            print(f"  {f['paper_id']}  {f['error']}")
    else:
        print("\nNo failures.")

    # 5-sample preview
    if eval_papers:
        import random
        rng = random.Random(42)
        sample = rng.sample(eval_papers, k=min(5, len(eval_papers)))
        print("\n--- 5 random originals → anonymized ---")
        for p in sample:
            print(f"\n[{p['tier']} | {p['subdomain']} | {p['year_cohort']}] {p['original_title'][:80]}")
            print(f"  ORIG: {p['original_abstract'][:300].replace(chr(10), ' ')}...")
            print(f"  ANON: {p['anonymized_problem']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
