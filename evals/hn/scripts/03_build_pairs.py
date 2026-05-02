"""
Step 4: Build forced-choice pairs from cohorts.

Cohort = (year-quarter, primary_language).
Within each cohort, by star count:
    winners = top 20% AND pushed_at within 12mo
    losers  = bottom 20%
Global filters: drop forks, archived, repos with >10k stars (memorization).
Cohorts with fewer than --min-cohort active repos are skipped.

Pairs are formed within cohort, 1:1, capped by min(#winners, #losers).
Random seed is fixed for reproducibility.

Output: data/pairs.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def parse_iso(s: str) -> datetime:
    # GitHub returns "2023-04-15T12:34:56Z"
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def quarter_key(ts: int) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return f"{dt.year}Q{(dt.month - 1) // 3 + 1}"


def load_records(hn_path: Path, meta_path: Path, max_stars: int):
    hn_by_repo = {}
    for line in hn_path.open():
        h = json.loads(line)
        # If multiple Show HNs point at the same repo, keep the highest-points one
        # (most representative pitch).
        key = (h["gh_owner"], h["gh_repo"])
        prior = hn_by_repo.get(key)
        if prior is None or h["points"] > prior["points"]:
            hn_by_repo[key] = h

    now = datetime.now(timezone.utc)
    records = []
    for line in meta_path.open():
        r = json.loads(line)
        m = r["meta"]
        if m is None:
            continue
        if m["is_fork"] or m["is_archived"] or m.get("is_disabled"):
            continue
        if m["stars"] > max_stars:
            continue  # memorization risk

        h = hn_by_repo.get((r["gh_owner"], r["gh_repo"]))
        if h is None:
            continue

        try:
            pushed_at = parse_iso(m["pushed_at"])
        except (TypeError, ValueError):
            continue

        records.append({
            "gh_owner": r["gh_owner"],
            "gh_repo": r["gh_repo"],
            "stars": m["stars"],
            "forks": m["forks"],
            "language": m["language"] or "(none)",
            "pushed_at": m["pushed_at"],
            "created_at": m["created_at"],
            "alive_12mo": (now - pushed_at).days <= 365,

            "hn_id": h["hn_id"],
            "hn_title": h["title"],
            "hn_url": h["url"],
            "hn_story_text": h["story_text"],
            "hn_points": h["points"],
            "hn_num_comments": h["num_comments"],
            "hn_created_at_i": h["created_at_i"],
            "cohort_quarter": quarter_key(h["created_at_i"]),
        })
    return records


def build_pairs(records, top_pct: float, bot_pct: float, min_cohort: int, seed: int):
    by_cohort = defaultdict(list)
    for r in records:
        by_cohort[(r["cohort_quarter"], r["language"])].append(r)

    rng = random.Random(seed)
    pairs = []
    cohort_stats = []

    for (quarter, lang), rs in sorted(by_cohort.items()):
        if len(rs) < min_cohort:
            cohort_stats.append((quarter, lang, len(rs), 0, 0, 0, "below-min"))
            continue

        rs_sorted = sorted(rs, key=lambda r: r["stars"])
        n = len(rs_sorted)
        bot_cut = max(1, int(n * bot_pct))
        top_cut = max(1, int(n * top_pct))

        losers = rs_sorted[:bot_cut]
        top_slice = rs_sorted[-top_cut:]
        winners = [r for r in top_slice if r["alive_12mo"]]

        n_pairs = min(len(winners), len(losers))
        cohort_stats.append((quarter, lang, n, len(winners), len(losers), n_pairs, "ok"))

        if n_pairs == 0:
            continue

        # Random 1-to-1 matching
        rng.shuffle(winners)
        rng.shuffle(losers)
        for i in range(n_pairs):
            w, l = winners[i], losers[i]
            pair_id = f"{quarter}_{lang.replace(' ', '-')}_{i:03d}"
            pairs.append({
                "pair_id": pair_id,
                "cohort_quarter": quarter,
                "cohort_language": lang,
                "cohort_size": n,
                "winner": w,
                "loser": l,
            })

    return pairs, cohort_stats


def print_summary(records, pairs, cohort_stats):
    print(f"Active records (after global filters): {len(records):,}")
    print(f"Total pairs constructed:                {len(pairs):,}")
    print(f"Cohorts considered:                     {len(cohort_stats):,}")
    used = sum(1 for c in cohort_stats if c[5] > 0)
    print(f"Cohorts that produced ≥1 pair:          {used}")
    print()

    # Per-language summary
    by_lang = defaultdict(lambda: [0, 0])  # [pairs, cohorts]
    for p in pairs:
        by_lang[p["cohort_language"]][0] += 1
    for q, l, n, w, lo, np_, status in cohort_stats:
        if np_ > 0:
            by_lang[l][1] += 1
    print(f"{'Language':<20} {'Pairs':>8} {'Cohorts':>8}")
    print("-" * 40)
    for lang, (np_, nc) in sorted(by_lang.items(), key=lambda x: -x[1][0]):
        print(f"{lang:<20} {np_:>8} {nc:>8}")

    # Per-quarter summary
    by_q = defaultdict(int)
    for p in pairs:
        by_q[p["cohort_quarter"]] += 1
    print()
    print(f"{'Quarter':<10} {'Pairs':>8}")
    print("-" * 22)
    for q in sorted(by_q):
        print(f"{q:<10} {by_q[q]:>8}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hn", default=str(DATA_DIR / "show_hn.jsonl"))
    ap.add_argument("--meta", default=str(DATA_DIR / "gh_metadata.jsonl"))
    ap.add_argument("--out", default=str(DATA_DIR / "pairs.jsonl"))
    ap.add_argument("--max-stars", type=int, default=10_000,
                    help="Drop any repo with more stars (memorization defense).")
    ap.add_argument("--top-pct", type=float, default=0.20)
    ap.add_argument("--bot-pct", type=float, default=0.20)
    ap.add_argument("--min-cohort", type=int, default=8)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    records = load_records(Path(args.hn), Path(args.meta), args.max_stars)
    pairs, cohort_stats = build_pairs(
        records,
        top_pct=args.top_pct,
        bot_pct=args.bot_pct,
        min_cohort=args.min_cohort,
        seed=args.seed,
    )

    out_path = Path(args.out)
    with out_path.open("w") as f:
        for p in pairs:
            f.write(json.dumps(p) + "\n")

    print_summary(records, pairs, cohort_stats)
    print(f"\nWrote {len(pairs):,} pairs to {out_path}")


if __name__ == "__main__":
    main()
