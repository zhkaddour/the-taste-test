"""Print eval leaderboard + flags from data/eval_results.json."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = ROOT / "results" / "eval_results.json"


def main() -> int:
    if not RESULTS_PATH.exists():
        print(f"Missing {RESULTS_PATH}. Run scripts/run_eval.py first.")
        return 1
    res = json.loads(RESULTS_PATH.read_text())
    md = res["metadata"]
    print(f"Eval: {md['n_personas']} personas × ({md['n_cross_pairs']} cross + {md['n_same_pairs']} same) pairs")
    print(f"Model: {md['model']}  judgments: {md['n_judgments']}  errors: {md['n_errors']}")
    print()

    rows = res["leaderboard"]
    print(f"  {'rank':>4}  {'persona':<24}  {'score':>5}  {'+1':>3}  {'0':>3}  {'-1':>3}  {'n':>3}")
    print(f"  {'-'*4}  {'-'*24}  {'-'*5}  {'-'*3}  {'-'*3}  {'-'*3}  {'-'*3}")
    for i, r in enumerate(rows, 1):
        print(f"  {i:>4}  {r['persona_name']:<24}  {r['score']:>+5}  {r['plus_one']:>3}  {r['zero']:>3}  {r['minus_one']:>3}  {r['n_pairs']:>3}")

    print()
    flags = []
    for r in rows:
        if r["n_pairs"] and r["zero"] / r["n_pairs"] > 0.4:
            flags.append((r["persona_name"], r["zero"], r["n_pairs"]))
    if flags:
        print("⚠  Personas with high inconsistency (>40% order-flips) — stub may be too thin:")
        for name, z, n in flags:
            print(f"   {name}  ({z}/{n} pairs flipped)")
    else:
        print("All personas under 40% inconsistency — eval signal looks stable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
