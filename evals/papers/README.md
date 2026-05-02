# Papers Eval

Multi-domain research-paper corpus. Outcome label = citation-percentile tier
within `(domain × year_cohort)` cohort.

## Scope

**21 venues across 7 domains** (full list in
[`scripts/fetch_papers.py`](scripts/fetch_papers.py) `VENUE_TO_DOMAIN`):

| Domain | Venues |
|---|---|
| Machine Learning | NeurIPS, ICML, ICLR |
| Mechanical & Aerospace Engineering | Journal of Fluid Mechanics, AIAA Journal, Journal of Mechanical Design |
| Biology / Life Sciences | Cell, Nature, PNAS |
| Chemistry & Materials Science | JACS, Nature Chemistry, Advanced Materials |
| Physics | Physical Review Letters, Nature Physics |
| Medicine | NEJM, The Lancet, JAMA |
| Economics | American Economic Review, Quarterly Journal of Economics, Econometrica, Journal of Political Economy |

Two cohorts: `2010-2015` (combined) and `2020`. Per-cohort percentiles are
computed within `(domain × cohort)` so a citation-rich field (medicine) doesn't
mechanically dominate a citation-sparse one (economics).

## Pipeline

Run from `taste-test/` root with `.venv` active. Each step caches its output,
so re-runs are cheap (use `--force` to invalidate).

```bash
# Full chain (~45 min for fetch, < $10 total)
python evals/papers/scripts/fetch_papers.py            # → data/raw_pool.json
python evals/papers/scripts/filter_papers.py           # → data/filtered_pool.json
python evals/papers/scripts/select_papers.py           # → data/selected_papers.json
python evals/papers/scripts/anonymize_papers.py        # → data/eval_papers.json
python evals/papers/scripts/run_eval.py --domain papers   # → results/eval_*.json
```

`enrich_arxiv.py` is no longer part of the pipeline — domain comes from the
venue tag written by `fetch_papers.py` directly.

### Stage details

1. **`fetch_papers.py`** — Semantic Scholar bulk search for each `(venue, year_spec)`.
   Tags every paper with `_domain` and `_fetched_via_venue`. Polite 1s pacing,
   429 backoff. Flags: `--venues`, `--years`, `--list-venues`, `--force`.
2. **`filter_papers.py`** — hard filters (abstract length > 200, citationCount ≥ 5,
   English heuristic) → cohort-aware tier labels (`good` ∈ p75-99, `bad` ∈ p≤10,
   drop top 1% to defeat memorization, drop middle).
3. **`select_papers.py`** — stratified random sample over `(domain × cohort × tier)`.
   Default 30/cell; bump with `--per-cell N`. Reports any cell that fell short.
4. **`anonymize_papers.py`** — async Claude calls (Sonnet 4.6, concurrency 10),
   cached system prompt, ~150-200 word neutral output. Strips identifiers and
   self-promotional voice; preserves quantitative results and standard
   benchmark/dataset names. Resumable by paper_id.
5. **`run_eval.py --domain papers|hn`** — see [Runner](#runner).

## Runner

Single script, dual-domain. The `--domain hn` branch reads
`evals/hn/data/{pairs.jsonl, abstracts.jsonl}` directly; outputs go to
`evals/{domain}/results/`.

### Personas

Auto-discovered at startup from `doctrines/<person>/doctrine-{variant}.md`:

- **Default per person**: distilled if it exists, light fallback otherwise.
- **5 comparison personas** (set via `LIGHT_VS_DISTILLED_COMPARISON` in
  [run_eval.py](scripts/run_eval.py)): load *both* variants to measure the
  light-vs-distilled lift. Currently: Hamming, Taleb, Thiel, Graham, Buffett.
- **Vanilla baselines** (no doctrine): `vanilla_sonnet_4_6` and `vanilla_opus_4_7`.

Current count: **25 personas** = 5 comparison × 2 variants (10) + 11 default
distilled + 2 default light (Ayn Rand & Charlie Munger lack a distilled file
yet) + 2 vanilla.

Filter with `--personas <id>,<id>,...` to run a subset. IDs follow the
`peter-thiel__light` / `peter-thiel__distilled` convention.

### Prompt

The persona block (cached) prepends the playbook/profile to a per-pair block
that names the year (avoids future-knowledge bias) and asks which is "more
worth their time and effort." Vanilla baselines get a neutral-judge prompt
with no persona framing.

### Logging

Every judgment record in `results/eval_pairs_log.json`:

```
persona_id, model, pair_id, kind, cohort_key,
side_a_id, side_b_id, ordering,
preference_normalized,   # 'A' or 'B' in canonical (side_a, side_b) frame
reasoning,               # one-sentence reasoning, in persona voice
raw_response,            # exact model output (for audit on parse failures)
input_tokens, cached_tokens, output_tokens,
error                    # populated on parse/API failure, else null
```

Tri-state scoring: AB and BA orderings agreeing = consistent; matching the
ground-truth side gives +1, disagreeing gives -1, flipped orderings give 0.

## Outputs

| Path | Contents |
|---|---|
| `data/raw_pool.json` | Raw fetch from Semantic Scholar, deduped by paperId |
| `data/filtered_pool.json` | Tier-labeled, with `domain` + `year_cohort` |
| `data/selected_papers.json` | Stratified sample (output of `select_papers.py`) |
| `data/eval_papers.json` | Anonymized abstracts ready for evaluation |
| `results/anonymization_log.json` | Originals + rewrites side-by-side, audit trail |
| `results/eval_results.json` | Leaderboard + metadata + pair index |
| `results/eval_pairs_log.json` | Every (persona × pair × ordering) judgment |

## Path conventions

- Scripts use `ROOT = Path(__file__).resolve().parent.parent` → `evals/papers/`
- Doctrines live at the **project root**: `doctrines/`
- Anonymize + runner load `.env` from `PROJECT_ROOT / ".env"` (works from any CWD)

## Smoke test

Validate the chain end-to-end on a tiny subset (~10 min, < $1):

```bash
python evals/papers/scripts/fetch_papers.py --venues "NeurIPS,Cell,Physical Review Letters" --years 2020
python evals/papers/scripts/filter_papers.py --force
python evals/papers/scripts/select_papers.py --per-cell 5 --force
python evals/papers/scripts/anonymize_papers.py --limit 10
python evals/papers/scripts/run_eval.py --domain papers --smoke
```

## Cost estimate (full headline run)

| Stage | Time | Cost |
|---|---|---|
| Fetch (~30k papers across 21 venues × 2 cohorts) | ~30-45 min | $0 |
| Anonymize ~840 papers (Sonnet, cached system prompt) | ~10 min | ~$10 |
| Eval: ~32 personas × pairs × 2 orderings | ≥ several hours sync | depends |

Pair count: with 1:1 matching and `--per-cell 30` in select_papers.py, expect
~30 pairs per `(domain × cohort)` cell × 14 cells ≈ 420 pairs. Bump to
`--per-cell 70` to reach ~1000 pairs.

For the headline eval run, prefer the Anthropic Batches API: 50% off, async,
sidesteps standard-tier ITPM. The sync runner here is fine for smoke tests
and small slices but will hit rate limits at full scale.
