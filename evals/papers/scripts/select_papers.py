"""Step 3: stratified random sample from each (domain × cohort × tier) cell.

Reads data/filtered_pool.json, takes a fixed quota of 'good' and 'bad' papers
per (domain × cohort), writes data/selected_papers.json.

The quota is uniform across domains by default. If a cell has fewer than the
target, takes all of it and reports the shortfall.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IN_PATH = ROOT / "data" / "filtered_pool.json"
OUT_PATH = ROOT / "data" / "selected_papers.json"

# Default per-(domain × cohort × tier) target. Across 7 domains × 2 cohorts × 2
# tiers = 28 cells, target=30 yields ~840 papers, enough to build ~1k pairs.
DEFAULT_PER_CELL = 30
COHORTS = ["2010-2015", "2020"]
TIERS = ["good", "bad"]
SAMPLE_SEED = 42


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--seed", type=int, default=SAMPLE_SEED)
    parser.add_argument(
        "--per-cell", type=int, default=DEFAULT_PER_CELL,
        help=f"Target sample size per (domain × cohort × tier) cell "
             f"(default: {DEFAULT_PER_CELL})",
    )
    args = parser.parse_args()

    if not IN_PATH.exists():
        print(f"Missing {IN_PATH}. Run filter_papers.py first.", file=sys.stderr)
        return 1
    if OUT_PATH.exists() and not args.force:
        print(f"{OUT_PATH} exists. Use --force to re-select.")
        return 0

    raw = json.loads(IN_PATH.read_text())
    pool = raw["papers"]
    rng = random.Random(args.seed)

    # bucket by (domain, cohort, tier)
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    domains: set[str] = set()
    for p in pool:
        buckets[(p["domain"], p["year_cohort"], p["tier"])].append(p)
        domains.add(p["domain"])

    selected: list[dict] = []
    shortfalls: list[tuple] = []
    target = args.per_cell

    print(f"Sampling per cell (seed={args.seed}, target={target}/cell):")
    print(f"  {'domain':<40} {'cohort':<12} {'tier':<5} "
          f"{'avail':>6} {'taken':>6}")
    for dom in sorted(domains):
        for coh in COHORTS:
            for tier in TIERS:
                avail = buckets.get((dom, coh, tier), [])
                take = min(target, len(avail))
                chosen = rng.sample(avail, take) if take else []
                selected.extend(chosen)
                marker = " (short)" if len(avail) < target else ""
                print(f"  {dom:<40} {coh:<12} {tier:<5} "
                      f"{len(avail):>6} {take:>6}{marker}")
                if len(avail) < target:
                    shortfalls.append((dom, coh, tier, len(avail), target))

    print(f"\nTotal selected: {len(selected)}")
    if shortfalls:
        print(f"\n{len(shortfalls)} cell(s) below target ({target}):")
        for dom, coh, tier, n, t in shortfalls:
            print(f"  {dom} | {coh} | {tier}: {n} < {t}")

    # quick distribution view
    cs = sorted([p["citationCount"] for p in selected])
    if cs:
        print(f"\nCitation counts (selected): "
              f"min={cs[0]} median={cs[len(cs)//2]} max={cs[-1]}")

    # spot-check: top 3 of each cell
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for p in selected:
        grouped[(p["domain"], p["year_cohort"], p["tier"])].append(p)
    print("\nTop 3 by citation per (domain × cohort × tier):")
    for key in sorted(grouped.keys()):
        items = sorted(grouped[key], key=lambda p: -p["citationCount"])
        dom, coh, tier = key
        print(f"\n  [{dom} | {coh} | {tier}] ({len(items)})")
        for p in items[:3]:
            title = (p.get("title") or "")[:70]
            cite = p["citationCount"]
            pct = p["citation_percentile"]
            print(f"    cites={cite:>6}  pct={pct:>5.1f}  {title}")

    OUT_PATH.write_text(json.dumps({
        "source": IN_PATH.name,
        "seed": args.seed,
        "per_cell_target": target,
        "shortfalls": [{"domain": d, "cohort": c, "tier": t, "available": n,
                        "target": t_} for d, c, t, n, t_ in shortfalls],
        "papers": selected,
    }, indent=2))
    print(f"\nWrote {len(selected)} papers to {OUT_PATH}")
    print("\nReview the distribution above before proceeding to anonymization.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
