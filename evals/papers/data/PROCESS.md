# Data pipeline — process notes

How the eval dataset gets built. Run scripts in this order.

## Methodology (TL;DR)

We build a paper-quality eval dataset where the ground-truth signal is **citation tier within an era cohort**. The pipeline:

1. **Fetch** all NeurIPS Computer Science papers from two era cohorts via the Semantic Scholar bulk API: `2010-2015` (combined as one cohort, ~2,300 papers) and `2020` (single year, ~1,900 papers). Cohorts are kept separate so older papers don't dominate "good" purely by virtue of having more years to accumulate citations.
2. **Enrich** each paper with its arXiv primary category (e.g., `cs.LG`, `cs.CV`, `cs.CL`) by hitting the arXiv Atom API in batches of 100. Papers without an arXiv ID — or with a category outside our 3-subdomain whitelist — are dropped.
3. **Filter** to three subdomains (Machine Learning / Computer Vision / Natural Language Processing) — the only ones with viable counts at NeurIPS — and apply abstract/citation/English heuristics.
4. **Tier-label within each cohort**: drop the top 1% of citations (mega-hits like GPT-3, Adam optimizer), label `good` if percentile rank is in [75, 99], label `bad` if rank ≤ 10, drop the middle. This gives two clear quality signals with the noisy middle removed.
5. **Stratified-sample** 66 papers (seed=42) across the (subdomain × cohort × tier) grid, with quotas proportional to subdomain prevalence (10 ML, 5 CV, 3 NLP per cell). Two sparse cells got truncated samples; rest met quota.
6. **Anonymize** each abstract via `claude-sonnet-4-6` with a prompt that strips first-person framing, the paper's own method names, and author/institution refs — but **keeps** benchmark numbers and standard-benchmark dataset names since those are the signal a persona needs to judge quality.

The eval consumes only the `anonymized_problem` field per paper; original titles, abstracts, and the `authors` array are either dropped or kept as our own reference and never shown to personas.

## Files in this directory

| File | Produced by | Size | Records | Description |
|---|---|---:|---:|---|
| `raw_pool.json` | `scripts/fetch_papers.py` | 8.7 MB | 4,212 | Unfiltered NeurIPS CS papers from Semantic Scholar. Two cohorts merged (2010-2015 and 2020), deduped by `paperId`. |
| `raw_pool_enriched.json` | `scripts/enrich_arxiv.py` | 9.1 MB | 4,212 | `raw_pool.json` + per-paper `arxiv_id`, `arxiv_primary_category`, and mapped `subdomain` (one of: Machine Learning / Computer Vision / Natural Language Processing / null). |
| `filtered_pool.json` | `scripts/filter_papers.py` | 1.5 MB | 552 | Subdomain-restricted, tier-labeled. Each paper has `year_cohort`, `tier` (`good` or `bad`), `citation_percentile` (within its cohort). |
| `selected_papers.json` | `scripts/select_papers.py` | 184 KB | 66 | Stratified random sample (seed=42) — the actual eval set. |
| `eval_papers.json` | `scripts/anonymize_papers.py` | 104 KB | 66 | Final eval input. `anonymized_problem` is the only field shown to personas. |
| `anonymization_log.json` | `scripts/anonymize_papers.py` | — | 66 | Side-by-side originals + rewrites + model's own anonymization notes, for spot-checking. |

## Pipeline at a glance

```
fetch_papers.py      → raw_pool.json            (Semantic Scholar bulk search)
enrich_arxiv.py      → raw_pool_enriched.json   (arXiv categories → 3 subdomains)
filter_papers.py     → filtered_pool.json       (cohort-aware tier labels)
select_papers.py     → selected_papers.json     (stratified sample)
anonymize_papers.py  → eval_papers.json         (Claude-rewritten abstracts)
inspect_papers.py    → stdout                   (sanity-check report)
```

## Data sources

- **Semantic Scholar Graph API** (`/paper/search/bulk`) — unauthenticated. Used for the venue/year query and citation counts.
- **arXiv Atom API** (`export.arxiv.org/api/query`) — used to recover the primary subject category (`cs.LG`, `cs.CV`, `cs.CL`, …) since Semantic Scholar's `s2FieldsOfStudy` only returns top-level fields.

## Cohorts

Two separate citation-percentile cohorts:

- `2010-2015` — NeurIPS papers from 2010 through 2015 combined into one cohort (~437 papers after filters).
- `2020` — single year (~1,222 papers after filters).

Percentiles are computed **within each cohort independently** so older papers don't dominate "good" purely because they had more years to accumulate citations.

## Filter rules

Applied in `filter_papers.py`:

1. `subdomain` ∈ {Machine Learning, Computer Vision, Natural Language Processing} — drops papers without arXiv tags or in irrelevant categories. (cs.IR / cs.CR / cs.HC originally requested but turned out to be near-zero at NeurIPS, so dropped.)
2. `abstract` non-null and length > 200 chars.
3. `citationCount` ≥ 5.
4. `year` in 2010-2015 or 2020.
5. English-looking abstract (heuristic: ≥60% ASCII letters, ≥3 stopword hits).
6. **Within each cohort:**
   - Drop papers above the **99th percentile** of citation count (mega-hits like GPT-3, Adam optimizer).
   - Label `tier = "good"` if percentile rank in [75, 99].
   - Label `tier = "bad"`  if percentile rank ≤ 10.
   - Drop the middle (10–75 percentile range).

## Sampling quotas

`select_papers.py` does stratified random sampling (seed=42) across the (subdomain × cohort × tier) grid:

| Subdomain | Per-cell target | × 4 cells |
|---|---:|---:|
| Machine Learning | 10 | 40 |
| Computer Vision | 5 | 20 |
| Natural Language Processing | 3 | 12 |
| | | **72 nominal** |

Two cells were sparse and got smaller-than-quota samples:
- **CV bad 2010-2015** — only 2 papers available (took both).
- **NLP bad 2010-2015** — 0 papers available (skipped).

Final yield: **66 papers**.

## Anonymization contract (Step 4)

The eval personas judge papers by abstract content alone. The anonymizer rewrites each abstract to:

- Drop "we propose", "in this paper", first-person framing.
- Strip the paper's own method names that signal a famous paper (when presented as the paper's own contribution).
- Strip author or institution references.
- **Keep** benchmark numbers and standard-benchmark dataset names — they're signal the persona needs, not identifying metadata.
- Keep the actual research question, approach, and type of finding.

The output file `eval_papers.json`:
- **Does not** contain author names, affiliations, or original titles in any field shown to the eval.
- The only field a persona should ever see is `anonymized_problem`.
- `original_title` and `original_abstract` are kept in the same file for our reference / debugging only.
- The `authors` array from `selected_papers.json` is dropped entirely.

## Caveats worth knowing

- **Citation count is the only quality proxy.** All "good"/"bad" labels are derived from citation tier within a cohort. NeurIPS already gates for quality, so "bad" really means *didn't catch on*, not *low rigor*.
- **Subdomain coverage is uneven** by venue: cs.LG dominates, cs.CL is tiny pre-2018.
- **Anonymization is not yet applied.** Titles in `selected_papers.json` are still the originals — that's intentional, since we want to spot-check before paying LLM tokens to rewrite them.
- **Reproducibility:** all scripts respect a `--force` flag to re-run; without `--force` they're idempotent (cached output is reused). Random seed = 42 throughout.

## Reproducing from scratch

```bash
.venv/bin/python scripts/fetch_papers.py --force
.venv/bin/python scripts/enrich_arxiv.py --force   # ~75 sec (arXiv polite-delay)
.venv/bin/python scripts/filter_papers.py --force
.venv/bin/python scripts/select_papers.py --force
.venv/bin/python scripts/anonymize_papers.py       # next step
```

Browse any output: `.venv/bin/python scripts/browse_papers.py --file data/<file>.json --help`.
