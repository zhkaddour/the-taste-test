"""Step 4: anonymize abstracts via Claude.

Reads data/selected_papers.json, calls claude-sonnet-4-6 with cached system
prompt and async concurrency, writes data/eval_papers.json (final eval input)
plus data/anonymization_log.json (originals + rewrites side-by-side).

Output target: ~150-200 word neutral paragraph in third-person voice.
This mirrors the HN abstractor's output shape so the two evals are comparable.

Resumable: if eval_papers.json already exists, paper_ids in it are skipped
unless --force is passed.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
from pathlib import Path

from anthropic import AsyncAnthropic
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent             # evals/papers/
PROJECT_ROOT = Path(__file__).resolve().parents[3]        # taste-test/
load_dotenv(PROJECT_ROOT / ".env")

IN_PATH = ROOT / "data" / "selected_papers.json"
OUT_PATH = ROOT / "data" / "eval_papers.json"
LOG_PATH = ROOT / "results" / "anonymization_log.json"

MODEL = "claude-sonnet-4-6"
DEFAULT_CONCURRENCY = 10
MAX_TOKENS = 600

SYSTEM_PROMPT = """You are an anonymizing technical abstractor. Given a research paper's title and abstract, produce a single ~200-word neutral abstract that lets a reader understand WHAT was studied and HOW, but not WHICH paper this is or WHO produced it.

Cover three things:
  1. What problem or question does this address?
  2. What is the approach or method?
  3. What are the key results or findings?

You MUST strip ALL of the following completely:

IDENTIFIERS
- Author, lab, institution, university, company, or country references
- Names of methods, models, frameworks, datasets, or systems that are *this paper's own contribution* (e.g., if the paper introduces something called "BERT", strip the name "BERT" but keep the description of what it does — call it "the proposed model" or similar). However, KEEP names of standard external benchmarks/datasets/instruments cited as evaluation context (e.g., "evaluated on ImageNet", "on the Reynolds-number-5000 regime").
- DOI, URL, citation handles, paper or grant numbers

VOICE / HYPE
- First-person framing ("we propose", "in this paper", "our method") → third-person neutral
- Subjective hype ("novel", "groundbreaking", "first to", "state-of-the-art" as a self-claim, "unprecedented")
- Self-comparative claims that name specific prior authors or methods ("outperforms Smith et al.", "improves on the X-method")

PRESERVE
- The substantive technical/scientific content: what was studied, how, what was found
- Concrete approach (algorithm, experimental setup, theoretical framework, study design)
- Quantitative results and the names of standard benchmarks/datasets/measurements they're computed on (e.g., "achieves 92.3% on ImageNet", "reduces drag by 23% at Re=5000", "p<0.001 for the primary endpoint")
- The problem framing — what gap or open question is being addressed

Output a single paragraph, ~150-200 words, third-person, neutral technical tone, in the language of the field. Begin directly with the description — no preamble, no headings, no bullet points, no JSON, no markdown."""


def build_user_message(paper: dict) -> str:
    title = paper.get("title") or "(no title)"
    abstract = paper.get("abstract") or "(no abstract)"
    domain = paper.get("domain") or paper.get("_domain") or "(unspecified)"
    return (
        f"=== DOMAIN ===\n{domain}\n\n"
        f"=== TITLE ===\n{title}\n\n"
        f"=== ABSTRACT ===\n{abstract}\n"
    )


async def anonymize_one(client: AsyncAnthropic, paper: dict,
                        sem: asyncio.Semaphore) -> tuple[dict | None, str | None]:
    """Returns (record, error_or_None)."""
    async with sem:
        for attempt in range(3):
            try:
                resp = await client.messages.create(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    system=[{
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }],
                    messages=[{
                        "role": "user",
                        "content": build_user_message(paper),
                    }],
                )
                anon = "".join(b.text for b in resp.content if b.type == "text").strip()
                if not anon:
                    return None, "empty response"
                pid = paper["paperId"]
                record = {
                    "paper_id": pid,
                    "year": paper.get("year"),
                    "year_cohort": paper.get("year_cohort"),
                    "venue": paper.get("venue"),
                    "domain": paper.get("domain"),
                    "tier": paper.get("tier"),
                    "citation_count": paper.get("citationCount"),
                    "citation_percentile": paper.get("citation_percentile"),
                    "anonymized_problem": anon,
                    "original_title": paper.get("title") or "",
                    "original_abstract": paper.get("abstract") or "",
                }
                return record, None
            except Exception as e:
                if attempt == 2:
                    return None, f"{type(e).__name__}: {e}"
                await asyncio.sleep(2 ** attempt)
        return None, "exhausted retries"


def load_existing(out_path: Path) -> tuple[list[dict], set[str]]:
    if not out_path.exists():
        return [], set()
    try:
        existing = json.loads(out_path.read_text()).get("papers", [])
        done = {r["paper_id"] for r in existing if r.get("paper_id")}
        return existing, done
    except (json.JSONDecodeError, KeyError):
        return [], set()


async def main_async(args):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not set")
    if not IN_PATH.exists():
        sys.exit(f"Missing {IN_PATH}. Run select_papers.py first.")

    raw = json.loads(IN_PATH.read_text())
    papers = raw["papers"]
    if args.limit:
        papers = papers[:args.limit]

    if args.force:
        existing, done = [], set()
    else:
        existing, done = load_existing(OUT_PATH)
    todo = [p for p in papers if p["paperId"] not in done]
    print(f"Total selected: {len(papers)} | already anonymized: {len(done)} | "
          f"to do: {len(todo)}")
    if not todo:
        print("Nothing to do.")
        return

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    client = AsyncAnthropic()
    sem = asyncio.Semaphore(args.concurrency)
    print(f"Anonymizing {len(todo)} papers via {MODEL} "
          f"(concurrency={args.concurrency}, cached system prompt)")

    results = list(existing)
    failures: list[dict] = []
    completed = 0

    async def worker(p):
        nonlocal completed
        rec, err = await anonymize_one(client, p, sem)
        completed += 1
        if err:
            failures.append({"paper_id": p["paperId"], "title": p.get("title"),
                             "error": err})
            print(f"  [{completed}/{len(todo)}] FAILED  {p['paperId']}  {err[:80]}")
        else:
            results.append(rec)
            print(f"  [{completed}/{len(todo)}] ok      {rec['paper_id']}  "
                  f"({rec['tier']}, {rec['domain']})")

    await asyncio.gather(*[worker(p) for p in todo])

    OUT_PATH.write_text(json.dumps({"papers": results}, indent=2))
    log_entries = [{
        "paper_id": r["paper_id"],
        "domain": r["domain"],
        "tier": r["tier"],
        "year_cohort": r["year_cohort"],
        "original_title": r["original_title"],
        "original_abstract": r["original_abstract"],
        "anonymized_problem": r["anonymized_problem"],
    } for r in results]
    LOG_PATH.write_text(json.dumps({"entries": log_entries, "failures": failures},
                                   indent=2))

    print(f"\nWrote {len(results)} records to {OUT_PATH}")
    print(f"Wrote anonymization log to {LOG_PATH}")
    if failures:
        print(f"\n{len(failures)} failures:")
        for f in failures:
            print(f"  {f['paper_id']}  {f['error']}")
    else:
        print("\nNo failures.")

    # 5-sample preview
    if results:
        rng = random.Random(42)
        sample = rng.sample(results, k=min(5, len(results)))
        print("\n--- 5 random originals → anonymized ---")
        for p in sample:
            title = p["original_title"][:80]
            print(f"\n[{p['tier']} | {p['domain']} | {p['year_cohort']}] {title}")
            print(f"  ORIG: {p['original_abstract'][:240].replace(chr(10), ' ')}...")
            print(f"  ANON: {p['anonymized_problem']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true",
                    help="Re-anonymize all papers, ignoring existing eval_papers.json")
    ap.add_argument("--limit", type=int, default=0,
                    help="Only process first N papers (smoke test).")
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
