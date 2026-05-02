"""Step 2: cohort-aware filter with tier labeling.

Reads data/raw_pool.json (already tagged with _domain by fetch_papers.py),
applies hard filters, then assigns tiers within each (domain × year_cohort)
cohort. Writes data/filtered_pool.json.

Cohorts: '2020' (single year) and '2010-2015' (combined 6 years). Per cohort
*within each domain*:
  - Drop top 1% (above p99 citationCount)
  - tier='good' if percentile in [75, 99]
  - tier='bad'  if percentile in [0, 10]
  - Middle papers dropped

Other filters: abstract present + length>200, citationCount>=5, English heuristic.

The arXiv-enrichment step is no longer used — domain comes from the venue tag
written by fetch_papers.py, so filter reads raw_pool.json directly.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IN_PATH = ROOT / "data" / "raw_pool.json"
OUT_PATH = ROOT / "data" / "filtered_pool.json"

COHORT_2020 = "2020"
COHORT_OLD = "2010-2015"

ENGLISH_STOPWORDS = {"the", "of", "and", "to", "in", "we", "is", "for", "that",
                     "with", "on", "as", "this", "are", "by"}


def percentile_rank(value: float, sorted_values: list[float]) -> float:
    """Return percentile rank (0..100) of value within sorted_values (nearest-rank)."""
    n = len(sorted_values)
    if n == 0:
        return 0.0
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi) // 2
        if sorted_values[mid] <= value:
            lo = mid + 1
        else:
            hi = mid
    return 100.0 * lo / n


def percentile_at(p: float, sorted_values: list[float]) -> float:
    n = len(sorted_values)
    if n == 0:
        return 0.0
    k = max(0, min(n - 1, int(round(p / 100 * (n - 1)))))
    return sorted_values[k]


def looks_english(abstract: str) -> bool:
    if not abstract:
        return False
    letters = sum(1 for c in abstract if c.isascii() and c.isalpha())
    if letters / max(1, len(abstract)) < 0.6:
        return False
    tokens = re.findall(r"[a-zA-Z]+", abstract.lower())
    return sum(1 for t in tokens if t in ENGLISH_STOPWORDS) >= 3


def cohort_for(year: int | None) -> str | None:
    if year == 2020:
        return COHORT_2020
    if year is not None and 2010 <= year <= 2015:
        return COHORT_OLD
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not IN_PATH.exists():
        print(f"Missing {IN_PATH}. Run fetch_papers.py first.", file=sys.stderr)
        return 1
    if OUT_PATH.exists() and not args.force:
        print(f"{OUT_PATH} already exists. Use --force to re-filter.")
        return 0

    raw = json.loads(IN_PATH.read_text())
    pool = raw["papers"]
    print(f"Loaded {len(pool):,} papers from {IN_PATH.name}")

    # Phase A: hard filters
    s0 = pool
    s1 = [p for p in s0 if p.get("_domain")]
    print(f"  after has _domain tag:            {len(s1):,}")
    s2 = [p for p in s1 if p.get("abstract") and len(p["abstract"]) > 200]
    print(f"  after abstract+length>200:        {len(s2):,}")
    s3 = [p for p in s2 if (p.get("citationCount") or 0) >= 5]
    print(f"  after citationCount>=5:           {len(s3):,}")
    s4 = [p for p in s3 if cohort_for(p.get("year")) is not None]
    print(f"  after year in {{2010-2015,2020}}:  {len(s4):,}")
    s5 = [p for p in s4 if looks_english(p["abstract"])]
    print(f"  after English heuristic:          {len(s5):,}")

    # Phase B: cohort-aware tier assignment, scoped to (domain × cohort)
    by_cell: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for p in s5:
        by_cell[(p["_domain"], cohort_for(p["year"]))].append(p)

    tagged: list[dict] = []
    cell_stats: dict[str, dict] = {}
    for (domain, cohort), papers in by_cell.items():
        cs = sorted(p["citationCount"] for p in papers)
        p99 = percentile_at(99, cs)
        p75 = percentile_at(75, cs)
        p10 = percentile_at(10, cs)
        cell_key = f"{domain} | {cohort}"
        cell_stats[cell_key] = {
            "n_total": len(papers),
            "p10": p10, "p75": p75, "p99": p99,
            "min": cs[0] if cs else None,
            "max": cs[-1] if cs else None,
            "median": cs[len(cs)//2] if cs else None,
        }
        kept = 0
        for p in papers:
            c = p["citationCount"]
            if c > p99:
                continue  # drop top 1%
            rank = percentile_rank(c, cs)
            if 75.0 <= rank <= 99.0:
                tier = "good"
            elif rank <= 10.0:
                tier = "bad"
            else:
                continue  # skip middle
            tagged.append({
                **p,
                "domain": domain,
                "year_cohort": cohort,
                "tier": tier,
                "citation_percentile": round(rank, 2),
            })
            kept += 1
        cell_stats[cell_key]["n_kept"] = kept

    print()
    print("Per-(domain × cohort) cell stats:")
    print(f"  {'cell':<60} {'n':>5} {'min':>5} {'med':>5} {'max':>6} {'kept':>5}")
    for cell, st in sorted(cell_stats.items()):
        print(f"  {cell:<60} {st['n_total']:>5} {st['min']:>5} "
              f"{st['median']:>5} {st['max']:>6} {st['n_kept']:>5}")

    # Cell counts: domain × cohort × tier
    counts: dict[tuple, int] = defaultdict(int)
    for p in tagged:
        counts[(p["domain"], p["year_cohort"], p["tier"])] += 1

    print()
    print("Cell counts (domain × cohort × tier):")
    print(f"  {'domain':<40} {'cohort':<12} {'good':>6} {'bad':>6}")
    domains = sorted({p["domain"] for p in tagged})
    for dom in domains:
        for coh in [COHORT_OLD, COHORT_2020]:
            g = counts[(dom, coh, "good")]
            b = counts[(dom, coh, "bad")]
            print(f"  {dom:<40} {coh:<12} {g:>6} {b:>6}")

    OUT_PATH.write_text(json.dumps({
        "source": IN_PATH.name,
        "cell_stats": cell_stats,
        "papers": tagged,
    }, indent=2))
    print(f"\nWrote {len(tagged):,} papers to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
