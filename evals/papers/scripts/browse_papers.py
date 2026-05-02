"""Inspect papers in any of the pipeline JSON files.

Usage examples:
  scripts/browse_papers.py --top 10
  scripts/browse_papers.py --bottom 10 --file data/filtered_pool.json
  scripts/browse_papers.py --keyword transformer
  scripts/browse_papers.py --id 7c8f...
  scripts/browse_papers.py --random 5
  scripts/browse_papers.py --bucket-citations          # histogram
  scripts/browse_papers.py --field fieldsOfStudy       # value distribution
  scripts/browse_papers.py --range 50:150              # citation count window
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILES = [
    ROOT / "data" / "eval_papers.json",
    ROOT / "data" / "selected_papers.json",
    ROOT / "data" / "filtered_pool.json",
    ROOT / "data" / "raw_pool.json",
]


def load(path: Path) -> list[dict]:
    blob = json.loads(path.read_text())
    if isinstance(blob, list):
        return blob
    if isinstance(blob, dict) and "papers" in blob:
        return blob["papers"]
    raise ValueError(f"Unrecognized JSON shape in {path}")


def pick_source(explicit: Path | None) -> Path:
    if explicit:
        return explicit
    for p in DEFAULT_FILES:
        if p.exists():
            return p
    raise SystemExit("No pipeline files found in data/. Pass --file <path>.")


def fmt(p: dict, full: bool = False) -> str:
    title = p.get("title") or "(no title)"
    cites = p.get("citationCount", "—")
    pid = p.get("paperId", "—")
    venue = p.get("venue", "—")
    fos = p.get("fieldsOfStudy") or []
    head = f"{cites:>5} cites | {title}\n        id: {pid}  venue: {venue}  fos: {fos}"
    if not full:
        return head
    abs_ = (p.get("abstract") or "").replace("\n", " ")
    if "anonymized_problem" in p:
        return head + f"\n  ANON: {p['anonymized_problem']}\n  ORIG: {abs_}"
    return head + f"\n  ABSTRACT: {abs_}"


def histogram(values: list[float], bins: int = 20, width: int = 50) -> str:
    if not values:
        return "(empty)"
    lo, hi = min(values), max(values)
    if lo == hi:
        return f"all values = {lo}"
    step = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        idx = min(bins - 1, int((v - lo) / step))
        counts[idx] += 1
    peak = max(counts)
    out = []
    for i, c in enumerate(counts):
        edge_lo = lo + i * step
        edge_hi = edge_lo + step
        bar = "#" * int(width * c / peak) if peak else ""
        out.append(f"  [{edge_lo:>7.1f}, {edge_hi:>7.1f})  {c:>4}  {bar}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", type=Path, help="JSON file to read (defaults to most-progressed pipeline file)")
    ap.add_argument("--top", type=int, help="Show top-N by citation count")
    ap.add_argument("--bottom", type=int, help="Show bottom-N by citation count")
    ap.add_argument("--random", type=int, help="Show N random papers (seed=42)")
    ap.add_argument("--keyword", type=str, help="Substring match on title (case-insensitive)")
    ap.add_argument("--id", dest="paper_id", type=str, help="Show one paper by paperId (full abstract)")
    ap.add_argument("--range", type=str, help="Citation range LO:HI inclusive, e.g. 50:150")
    ap.add_argument("--field", type=str, help="Print value distribution for a top-level field")
    ap.add_argument("--bucket-citations", action="store_true", help="ASCII histogram of citation counts")
    ap.add_argument("--full", action="store_true", help="Show full abstracts (with --top/--bottom/--random)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    src = pick_source(args.file).resolve()
    papers = load(src)
    try:
        rel = src.relative_to(ROOT)
    except ValueError:
        rel = src
    print(f"# source: {rel}  ({len(papers)} papers)\n")

    if args.paper_id:
        for p in papers:
            if p.get("paperId") == args.paper_id:
                print(fmt(p, full=True))
                return 0
        print(f"No paper with id {args.paper_id}", file=sys.stderr)
        return 1

    if args.field:
        c: Counter = Counter()
        for p in papers:
            v = p.get(args.field)
            if isinstance(v, list):
                for item in v: c[str(item)] += 1
            else:
                c[str(v)] += 1
        for k, n in c.most_common(30):
            print(f"  {n:>5}  {k}")
        return 0

    if args.bucket_citations:
        cs = [p["citationCount"] for p in papers if p.get("citationCount") is not None]
        print(histogram(cs))
        print(f"\n  n={len(cs)}  min={min(cs)}  max={max(cs)}  median={sorted(cs)[len(cs)//2]}")
        return 0

    subset = papers
    if args.keyword:
        kw = args.keyword.lower()
        subset = [p for p in subset if kw in (p.get("title") or "").lower()]
        print(f"# keyword '{args.keyword}': {len(subset)} match\n")
    if args.range:
        lo, hi = (int(x) for x in args.range.split(":"))
        subset = [p for p in subset if lo <= (p.get("citationCount") or 0) <= hi]
        print(f"# citation range [{lo}, {hi}]: {len(subset)} match\n")

    if args.top:
        subset = sorted(subset, key=lambda p: -(p.get("citationCount") or 0))[:args.top]
    elif args.bottom:
        subset = sorted(subset, key=lambda p: (p.get("citationCount") or 0))[:args.bottom]
    elif args.random:
        rng = random.Random(args.seed)
        subset = rng.sample(subset, k=min(args.random, len(subset)))

    if not (args.top or args.bottom or args.random or args.keyword or args.range):
        # No filter? Show summary.
        cs = [p["citationCount"] for p in papers if p.get("citationCount") is not None]
        print(f"  total papers: {len(papers)}")
        if cs:
            print(f"  citations:    min={min(cs)} median={sorted(cs)[len(cs)//2]} max={max(cs)}")
        with_arxiv = sum(1 for p in papers if (p.get("externalIds") or {}).get("ArXiv"))
        print(f"  with ArXiv:   {with_arxiv}")
        print("\nUse --help to see filters (--top, --keyword, --random, --bucket-citations, …).")
        return 0

    for i, p in enumerate(subset, 1):
        print(f"[{i}] {fmt(p, full=args.full)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
