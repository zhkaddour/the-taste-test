"""Step 2: cohort-aware filter with subdomain restriction and tier labeling.

Reads data/raw_pool_enriched.json, applies filters in order, writes
data/filtered_pool.json with year_cohort, subdomain, tier, citation_percentile.

Cohorts: '2020' (single year) and '2010-2015' (combined 6 years).
Subdomains kept: Machine Learning, Computer Vision, Natural Language Processing.
Per cohort:
  - Drop top 1% (above p99 citationCount)
  - tier='good' if percentile in [75, 99]
  - tier='bad'  if percentile in [0, 10]
  - Middle papers dropped
Other filters: abstract present + length>200, citationCount>=5, English heuristic.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IN_PATH = ROOT / "data" / "raw_pool_enriched.json"
OUT_PATH = ROOT / "data" / "filtered_pool.json"

KEEP_SUBDOMAINS = {"Machine Learning", "Computer Vision", "Natural Language Processing"}
COHORT_2020 = "2020"
COHORT_OLD = "2010-2015"

ENGLISH_STOPWORDS = {"the", "of", "and", "to", "in", "we", "is", "for", "that", "with", "on", "as", "this", "are", "by"}


def percentile_rank(value: float, sorted_values: list[float]) -> float:
    """Return percentile rank (0..100) of value within sorted_values (nearest-rank)."""
    n = len(sorted_values)
    if n == 0:
        return 0.0
    # count of values <= this one
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
        print(f"Missing {IN_PATH}. Run enrich_arxiv.py first.", file=sys.stderr)
        return 1
    if OUT_PATH.exists() and not args.force:
        print(f"{OUT_PATH} already exists. Use --force to re-filter.")
        return 0

    raw = json.loads(IN_PATH.read_text())
    pool = raw["papers"]
    print(f"Loaded {len(pool)} enriched papers from {IN_PATH.name}")

    # Phase A: hard filters (no cohort needed)
    s0 = pool
    s1 = [p for p in s0 if p.get("subdomain") in KEEP_SUBDOMAINS]
    print(f"  after subdomain whitelist:        {len(s1)}")
    s2 = [p for p in s1 if p.get("abstract") and len(p["abstract"]) > 200]
    print(f"  after abstract+length>200:        {len(s2)}")
    s3 = [p for p in s2 if (p.get("citationCount") or 0) >= 5]
    print(f"  after citationCount>=5:           {len(s3)}")
    s4 = [p for p in s3 if cohort_for(p.get("year")) is not None]
    print(f"  after year in {{2010-2015, 2020}}:  {len(s4)}")
    s5 = [p for p in s4 if looks_english(p["abstract"])]
    print(f"  after English heuristic:          {len(s5)}")

    # Phase B: cohort-aware tier assignment
    by_cohort: dict[str, list[dict]] = defaultdict(list)
    for p in s5:
        by_cohort[cohort_for(p["year"])].append(p)

    tagged: list[dict] = []
    cohort_stats: dict[str, dict] = {}
    for cohort, papers in by_cohort.items():
        cs = sorted(p["citationCount"] for p in papers)
        p99 = percentile_at(99, cs)
        p75 = percentile_at(75, cs)
        p10 = percentile_at(10, cs)
        cohort_stats[cohort] = {
            "n_total": len(papers),
            "p10": p10, "p75": p75, "p99": p99,
            "min": cs[0] if cs else None, "max": cs[-1] if cs else None,
            "median": cs[len(cs)//2] if cs else None,
        }
        kept_in_cohort = 0
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
                "year_cohort": cohort,
                "tier": tier,
                "citation_percentile": round(rank, 2),
            })
            kept_in_cohort += 1
        cohort_stats[cohort]["n_kept"] = kept_in_cohort

    print()
    print("Per-cohort stats:")
    for cohort, st in cohort_stats.items():
        print(f"  [{cohort}] n={st['n_total']}  cites min={st['min']} med={st['median']} max={st['max']}")
        print(f"             p10={st['p10']}  p75={st['p75']}  p99={st['p99']}  -> kept (good+bad)={st['n_kept']}")

    # Cell matrix: subdomain x cohort x tier
    cell: dict[tuple, int] = defaultdict(int)
    for p in tagged:
        cell[(p["subdomain"], p["year_cohort"], p["tier"])] += 1

    print()
    print("Cell counts (subdomain × cohort × tier):")
    print(f"  {'subdomain':<32} {'cohort':<12} {'good':>6}  {'bad':>6}")
    for sub in sorted(KEEP_SUBDOMAINS):
        for coh in [COHORT_OLD, COHORT_2020]:
            g = cell[(sub, coh, "good")]
            b = cell[(sub, coh, "bad")]
            print(f"  {sub:<32} {coh:<12} {g:>6}  {b:>6}")

    OUT_PATH.write_text(json.dumps({
        "source": IN_PATH.name,
        "cohort_stats": cohort_stats,
        "papers": tagged,
    }, indent=2))
    print(f"\nWrote {len(tagged)} papers to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
