# HN Eval

Show HN posts as the problem corpus. Outcome label = GitHub stars + 12-month liveness.

## Pipeline

All scripts live in `scripts/` and read/write to `data/` (data/) and `results/` (downstream eval outputs).

```bash
# (run from taste-test/ root, with .venv active)

# 1. Pull Show HN posts that link to GitHub (Algolia, ~2 min)
python evals/hn/scripts/01_pull_hn.py --start 2020-01-01 --end 2024-01-01

# 2. Fetch GitHub metadata via batched GraphQL (~2 min)
python evals/hn/scripts/02_fetch_gh_metadata.py

# 3. Construct cohort + pairs (within quarter × language)
python evals/hn/scripts/03_build_pairs.py

# 4. Fetch READMEs for each repo in pairs (~1 min)
python evals/hn/scripts/04_fetch_readmes.py

# 5. LLM-anonymize (HN pitch + README → 200-word neutral abstract, ~25 min, ~$20)
python evals/hn/scripts/05_anonymize.py
```

All steps are resumable: re-running picks up where the previous run stopped.

## Filters and parameters

- **Cohort**: `[year-quarter, primary_language]` with min 8 active repos
- **Memorization defense**: drop everything with > 10,000 stars
- **Drop**: forks, archived, repos missing from GitHub
- **Winners**: top 20% by stars *and* `pushed_at` within last 12 months
- **Losers**: bottom 20% by stars (no liveness filter)
- **Pairing**: 1:1 random within cohort, capped at min(winners, losers)

## Outputs

- `data/show_hn.jsonl` — ~13k Show HN posts with GH URL
- `data/gh_metadata.jsonl` — ~11k GitHub repo metadata records
- `data/pairs.jsonl` — ~830 forced-choice pairs
- `data/readmes.jsonl` — ~1.7k READMEs
- `data/abstracts.jsonl` — ~1.7k anonymized 200-word abstracts
- `results/` — populated when the persona eval runs

## What's NOT here yet

The forced-choice persona runner. Currently the colleague's `evals/papers/scripts/run_eval.py` is paper-specific; we'll need to either generalize it or write a parallel HN runner that consumes `data/pairs.jsonl` + `data/abstracts.jsonl`.
