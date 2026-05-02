# Papers Eval

arXiv abstracts as the problem corpus. Outcome label = citation count.

## Status

MVP from the papers team. Currently runs on ~20 paper pairs. Plan: scale to 1000 pairs and align fields/methodology with [`evals/hn/`](../hn/).

The pipeline lives in `scripts/`. See `data/PROCESS.md` for the original methodology notes.

## Pipeline

```bash
# (run from taste-test/ root, with .venv active)

python evals/papers/scripts/fetch_papers.py
python evals/papers/scripts/enrich_arxiv.py
python evals/papers/scripts/filter_papers.py
python evals/papers/scripts/select_papers.py
python evals/papers/scripts/anonymize_papers.py     # → data/eval_papers.json
python evals/papers/scripts/run_eval.py             # → results/eval_results.json
python evals/papers/scripts/inspect_eval.py
```

## Outputs

- `data/eval_papers.json` — anonymized abstract pairs ready for evaluation
- `results/eval_results.json` — leaderboard
- `results/eval_pairs_log.json` — per-pair persona judgments
- `results/anonymization_log.json` — anonymization audit log

## Path conventions

- Scripts use `ROOT = Path(__file__).resolve().parent.parent` → `evals/papers/`
- Doctrines live at the **project root**: `taste-test/doctrines/` (shared with HN eval)
- The runner uses `PROJECT_ROOT = Path(__file__).resolve().parents[3]` to reach top-level

## Known scaling work (TBD)

- Expand from 20 → 1000 pairs
- Add more fields per pair to match HN methodology
- Consider tweaking the eval prompt template
