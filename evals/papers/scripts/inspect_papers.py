"""Step 5: sanity-check report on data/eval_papers.json."""
from __future__ import annotations

import json
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "data" / "eval_papers.json"


def histogram(values, bins=15, width=40):
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
        e0 = lo + i * step
        e1 = e0 + step
        bar = "#" * int(width * c / peak) if peak else ""
        out.append(f"  [{e0:>7.1f}, {e1:>7.1f})  {c:>4}  {bar}")
    return "\n".join(out)


def main() -> int:
    if not PATH.exists():
        print(f"Missing {PATH}.")
        return 1
    papers = json.loads(PATH.read_text())["papers"]

    print(f"=== Eval papers report ===")
    print(f"Source: {PATH}")
    print(f"Total:  {len(papers)}\n")

    cs = [p["citation_count"] for p in papers]
    print(f"Citation counts:")
    print(f"  min={min(cs)}  max={max(cs)}  mean={round(statistics.mean(cs),1)}  median={statistics.median(cs)}")
    print(f"\nHistogram:")
    print(histogram(cs))

    print(f"\nTier distribution:")
    for k, n in Counter(p["tier"] for p in papers).most_common():
        print(f"  {n:>3}  {k}")

    print(f"\nSubdomain distribution:")
    for k, n in Counter(p["subdomain"] for p in papers).most_common():
        print(f"  {n:>3}  {k}")

    print(f"\nYear cohort distribution:")
    for k, n in Counter(p["year_cohort"] for p in papers).most_common():
        print(f"  {n:>3}  {k}")

    print(f"\nCell matrix (subdomain × cohort × tier):")
    cell = Counter()
    for p in papers:
        cell[(p["subdomain"], p["year_cohort"], p["tier"])] += 1
    print(f"  {'subdomain':<32} {'cohort':<12} {'good':>5} {'bad':>5}")
    for sub in ["Machine Learning", "Computer Vision", "Natural Language Processing"]:
        for coh in ["2010-2015", "2020"]:
            g = cell[(sub, coh, "good")]
            b = cell[(sub, coh, "bad")]
            print(f"  {sub:<32} {coh:<12} {g:>5} {b:>5}")

    lens = [len(p["anonymized_problem"]) for p in papers]
    print(f"\nAnonymized problem length (chars):")
    print(f"  min={min(lens)}  max={max(lens)}  mean={round(statistics.mean(lens),1)}  median={statistics.median(lens)}")

    rng = random.Random(42)
    samples = rng.sample(papers, k=5)
    print(f"\n=== 5 random anonymized problems ===")
    for i, p in enumerate(samples, 1):
        print(f"\n[{i}] tier={p['tier']} | subdomain={p['subdomain']} | cohort={p['year_cohort']} | cites={p['citation_count']}")
        print(f"    {p['anonymized_problem']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
