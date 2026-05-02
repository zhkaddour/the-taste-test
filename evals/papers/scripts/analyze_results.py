"""Post-hoc analysis of eval_pairs_log.json.

Produces:
  - results/decisions_matrix.csv     persona × pair → 'A' / 'B' / 'flipped'
  - results/agreement_matrix.csv     persona × persona → fraction of agreed decisions
  - results/agreement_overall.png    clustermap of agreement (hierarchical clustering)
  - results/agreement_per_domain.png one heatmap per (cohort_key) domain group

Also prints, to stdout:
  - per-pair "do all personas agree?" summary
  - per-domain agreement summaries
  - top most-similar and most-different persona pairs
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG = ROOT / "results" / "eval_pairs_log.json"
DEFAULT_RESULTS = ROOT / "results" / "eval_results.json"
OUT_DIR = ROOT / "results"


def load_decisions(log_path: Path, results_path: Path):
    log = json.loads(log_path.read_text())
    results = json.loads(results_path.read_text())
    pair_index = {p["pair_id"]: p for p in results["pair_index"]}

    # group by (persona, pair) → {ordering: pref}
    grouped: dict[tuple, dict[str, str]] = defaultdict(dict)
    for j in log["judgments"]:
        if j.get("preference_normalized") is None:
            continue
        grouped[(j["persona_id"], j["pair_id"])][j["ordering"]] = j["preference_normalized"]

    # consistent decision per (persona, pair): AB == BA → that letter; else 'flipped'
    decisions: dict[tuple, str] = {}
    for (persona, pair_id), ords in grouped.items():
        ab = ords.get("AB")
        ba = ords.get("BA")
        if ab is None or ba is None:
            decisions[(persona, pair_id)] = "missing"
        elif ab == ba:
            decisions[(persona, pair_id)] = ab
        else:
            decisions[(persona, pair_id)] = "flipped"

    return decisions, pair_index


def build_decision_table(decisions, pair_index) -> pd.DataFrame:
    personas = sorted({p for (p, _) in decisions})
    pairs = sorted(pair_index.keys())
    df = pd.DataFrame(index=personas, columns=pairs, dtype=object)
    for (p, pid), v in decisions.items():
        df.loc[p, pid] = v
    return df


def agreement_matrix(decision_df: pd.DataFrame) -> pd.DataFrame:
    """For each (persona_i, persona_j), fraction of pairs where they made the
    same consistent decision (skip pairs where either flipped or missing).
    """
    personas = list(decision_df.index)
    n = len(personas)
    mat = np.full((n, n), np.nan)
    for i, pi in enumerate(personas):
        for j, pj in enumerate(personas):
            if i == j:
                mat[i, j] = 1.0
                continue
            di = decision_df.loc[pi]
            dj = decision_df.loc[pj]
            valid = ((di.isin(["A", "B"])) & (dj.isin(["A", "B"])))
            if valid.sum() == 0:
                continue
            agree = ((di == dj) & valid).sum() / valid.sum()
            mat[i, j] = agree
    return pd.DataFrame(mat, index=personas, columns=personas)


def per_pair_unanimity(decision_df: pd.DataFrame, pair_index) -> pd.DataFrame:
    """For each pair, count how many personas pick A vs B vs flipped."""
    rows = []
    for pid, info in pair_index.items():
        col = decision_df[pid]
        n_a = (col == "A").sum()
        n_b = (col == "B").sum()
        n_flipped = (col == "flipped").sum()
        n_missing = (col == "missing").sum()
        n_total = n_a + n_b + n_flipped + n_missing
        majority = "A" if n_a > n_b else ("B" if n_b > n_a else "tie")
        agreement = max(n_a, n_b) / max(1, n_a + n_b)
        rows.append({
            "pair_id": pid,
            "cohort_key": info["cohort_key"],
            "correct_side": info["correct_side"],
            "n_A": n_a, "n_B": n_b,
            "n_flipped": n_flipped, "n_missing": n_missing,
            "majority": majority,
            "majority_correct": majority == info["correct_side"],
            "agreement_pct": round(agreement * 100, 1),
            "n_total": n_total,
        })
    return pd.DataFrame(rows)


def plot_agreement_clustermap(agree_df: pd.DataFrame, out_path: Path,
                              title: str = "Persona × persona decision agreement"):
    """Clustermap (hierarchical clustering on rows/cols)."""
    # Need a matrix free of NaNs for clustering: replace with 0
    m = agree_df.fillna(0.0)
    g = sns.clustermap(
        m,
        annot=True, fmt=".2f",
        cmap="rocket_r",
        vmin=0.4, vmax=1.0,
        figsize=(12, 11),
        cbar_pos=(0.02, 0.85, 0.03, 0.12),
        dendrogram_ratio=0.12,
        annot_kws={"size": 7},
    )
    g.ax_heatmap.set_xlabel("")
    g.ax_heatmap.set_ylabel("")
    g.fig.suptitle(title, y=1.02, fontsize=14)
    plt.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close()


def plot_per_domain(decision_df: pd.DataFrame, pair_index, out_path: Path):
    """One agreement heatmap per cohort_key (domain)."""
    by_domain: dict[str, list[str]] = defaultdict(list)
    for pid, info in pair_index.items():
        by_domain[info["cohort_key"]].append(pid)

    domains = sorted(by_domain.keys())
    n = len(domains)
    fig, axes = plt.subplots(1, n, figsize=(7 * n, 7), squeeze=False)

    for ax, dom in zip(axes[0], domains):
        sub = decision_df[by_domain[dom]]
        agree = agreement_matrix(sub)
        sns.heatmap(
            agree, ax=ax, annot=True, fmt=".2f",
            cmap="rocket_r", vmin=0.0, vmax=1.0,
            cbar=True, square=True,
            annot_kws={"size": 6},
        )
        ax.set_title(f"{dom}\n({len(by_domain[dom])} pairs)")
        ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right", fontsize=7)
        ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=7)

    plt.tight_layout()
    plt.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", default=str(DEFAULT_LOG))
    ap.add_argument("--results", default=str(DEFAULT_RESULTS))
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    args = ap.parse_args()

    log_path = Path(args.log)
    results_path = Path(args.results)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not log_path.exists() or not results_path.exists():
        print(f"Missing {log_path} or {results_path}", file=sys.stderr)
        return 1

    decisions, pair_index = load_decisions(log_path, results_path)
    decision_df = build_decision_table(decisions, pair_index)

    # Save decisions matrix
    decision_df.to_csv(out_dir / "decisions_matrix.csv")
    print(f"Wrote {out_dir / 'decisions_matrix.csv'}  ({decision_df.shape[0]} personas × "
          f"{decision_df.shape[1]} pairs)")

    # Overall agreement matrix
    agree = agreement_matrix(decision_df)
    agree.to_csv(out_dir / "agreement_matrix.csv")
    print(f"Wrote {out_dir / 'agreement_matrix.csv'}")

    # Per-pair unanimity
    per_pair = per_pair_unanimity(decision_df, pair_index)
    per_pair.to_csv(out_dir / "per_pair_summary.csv", index=False)
    print(f"Wrote {out_dir / 'per_pair_summary.csv'}")

    # Plots
    plot_agreement_clustermap(agree, out_dir / "agreement_overall.png")
    print(f"Wrote {out_dir / 'agreement_overall.png'}")
    plot_per_domain(decision_df, pair_index, out_dir / "agreement_per_domain.png")
    print(f"Wrote {out_dir / 'agreement_per_domain.png'}")

    # ---------- console reporting ----------
    print()
    print("=" * 70)
    print("PER-PAIR UNANIMITY")
    print("=" * 70)
    n_total = len(per_pair)
    n_total_agree = (per_pair["agreement_pct"] == 100).sum()
    n_majority_correct = per_pair["majority_correct"].sum()
    print(f"Total pairs: {n_total}")
    print(f"Pairs where ALL personas agreed (100%): {n_total_agree}")
    print(f"Pairs where the majority pick was correct: {n_majority_correct}/{n_total}")
    print()
    print("Per-pair distribution:")
    print(f"  {'cohort':<32} {'n_A':>4} {'n_B':>4} {'flip':>4} {'agree%':>7} {'truth':>5} {'maj_right':>9}")
    for _, row in per_pair.iterrows():
        print(f"  {row['cohort_key']:<32} {row['n_A']:>4} {row['n_B']:>4} "
              f"{row['n_flipped']:>4} {row['agreement_pct']:>7} {row['correct_side']:>5} "
              f"{str(row['majority_correct']):>9}")

    print()
    print("=" * 70)
    print("PERSONA-PAIR SIMILARITY")
    print("=" * 70)
    pairs_list = []
    personas = list(agree.index)
    for i in range(len(personas)):
        for j in range(i + 1, len(personas)):
            v = agree.iloc[i, j]
            if not np.isnan(v):
                pairs_list.append((personas[i], personas[j], v))
    pairs_list.sort(key=lambda x: -x[2])
    print("\nTop 10 most-similar pairs:")
    for a, b, v in pairs_list[:10]:
        print(f"  {v*100:>5.1f}%  {a}  ↔  {b}")
    print("\nTop 10 most-different pairs:")
    for a, b, v in pairs_list[-10:]:
        print(f"  {v*100:>5.1f}%  {a}  ↔  {b}")

    print()
    print("=" * 70)
    print("PER-DOMAIN AGREEMENT (mean off-diagonal)")
    print("=" * 70)
    by_domain: dict[str, list[str]] = defaultdict(list)
    for pid, info in pair_index.items():
        by_domain[info["cohort_key"]].append(pid)
    for dom in sorted(by_domain.keys()):
        sub = decision_df[by_domain[dom]]
        agree_d = agreement_matrix(sub)
        m = agree_d.values.copy()
        np.fill_diagonal(m, np.nan)
        mean_agree = np.nanmean(m)
        print(f"  {dom:<40}  mean off-diag agreement: {mean_agree*100:.1f}%  "
              f"({len(by_domain[dom])} pairs)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
