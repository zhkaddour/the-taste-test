"""Step 3: stratified random sample from each (subdomain × cohort × tier) cell.

Reads data/filtered_pool.json, samples per quotas below, writes
data/selected_papers.json.
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

# Per-cell sampling quotas: (subdomain, cohort, tier) -> target count
QUOTA = {
    "Machine Learning":            {"good": 10, "bad": 10},
    "Computer Vision":             {"good": 5,  "bad": 5},
    "Natural Language Processing": {"good": 3,  "bad": 3},
}
COHORTS = ["2010-2015", "2020"]
SAMPLE_SEED = 42


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--seed", type=int, default=SAMPLE_SEED)
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

    # bucket by cell
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for p in pool:
        buckets[(p["subdomain"], p["year_cohort"], p["tier"])].append(p)

    selected: list[dict] = []
    print(f"Sampling per cell (seed={args.seed}):")
    print(f"  {'subdomain':<32} {'cohort':<12} {'tier':<5} {'target':>6} {'avail':>6} {'taken':>6}")
    for sub, tiers in QUOTA.items():
        for coh in COHORTS:
            for tier, target in tiers.items():
                avail = buckets.get((sub, coh, tier), [])
                take = min(target, len(avail))
                chosen = rng.sample(avail, take) if take else []
                for p in chosen:
                    selected.append(p)
                print(f"  {sub:<32} {coh:<12} {tier:<5} {target:>6} {len(avail):>6} {take:>6}")

    print(f"\nTotal selected: {len(selected)}")

    # quick distribution view
    print("\nCitation counts of selected papers (sorted):")
    cs = sorted([p["citationCount"] for p in selected])
    print(f"  min={cs[0]} median={cs[len(cs)//2]} max={cs[-1]}")

    # show a snapshot
    print("\nFirst 3 of each (subdomain × cohort × tier) cell, by citation:")
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for p in selected:
        grouped[(p["subdomain"], p["year_cohort"], p["tier"])].append(p)
    for key, items in sorted(grouped.items()):
        items.sort(key=lambda p: -p["citationCount"])
        sub, coh, tier = key
        print(f"\n  [{sub} | {coh} | {tier}] ({len(items)} papers)")
        for p in items[:3]:
            title = (p.get("title") or "")[:70]
            print(f"    {p['citationCount']:>6}  pct={p['citation_percentile']:>5.1f}  {title}")

    OUT_PATH.write_text(json.dumps({
        "source": IN_PATH.name,
        "seed": args.seed,
        "quota": QUOTA,
        "papers": selected,
    }, indent=2))
    print(f"\nWrote {len(selected)} papers to {OUT_PATH}")
    print("\nPaused. Review the distribution above before approving Step 4 (anonymization).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
