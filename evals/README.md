# Evals

Two domains, one methodology.

## Two domains

| | [`hn/`](hn/) | [`papers/`](papers/) |
|---|---|---|
| Corpus | Show HN posts (2020-2023) | arXiv abstracts |
| Outcome label | GitHub stars + 12-month liveness | Citation count |
| Cohort definition | quarter × primary_language | subfield × year |
| Memorization defense | drop > 10k stars | drop top citation outliers |
| Status | data ready (832 pairs) | MVP (20 pairs) — scaling to 1000 |

## Shared methodology

For each domain:

1. Build a corpus of problem pitches with measurable outcomes
2. Anonymize aggressively (LLM rewriter strips identifiers + success metrics)
3. Pair within tight cohorts to control for ecosystem and timing effects
4. Force each persona to choose one of two pitches; run twice with order flipped
5. Score each pair tri-state: **+1** if correct both times, **0** if flipped, **-1** if wrong both times
6. Report accuracy, consistency, agreement matrix; compare to random / vanilla-LLM / crowd baselines

## Shared runner (TBD)

A unified runner that takes any pair set in a common schema and runs the persona forced-choice. For now the colleague's `papers/scripts/run_eval.py` works on paper pairs; needs generalizing.
