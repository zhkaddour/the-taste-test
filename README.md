# The Taste Test

> Distilling the taste of great problem-pickers into something measurable.

**Thesis**: taste in problem selection is a *prediction function*. A senior thinker reading a pitch is silently forecasting "will this matter / does this rot / is this load-bearing." If we extract that function from their writing and run it against historical outcomes, we can score how well we captured it — and compare distilled thinkers against each other.

## What's here

```
taste-test/
├── doctrines/                    # 18 personas, two tiers each
│   ├── README.md                 # library docs + canonical format
│   ├── SKILL.md                  # frontmatter + wrapper for any LLM agent
│   └── <persona-id>/             # kebab-case (peter-thiel, richard-hamming, …)
│       ├── doctrine-light.md     # AI-generated baseline (always present)
│       └── doctrine-distilled.md # 3-layer Rule/Test/Source (when available)
├── evals/
│   ├── hn/                       # Show HN → GitHub-stars eval (this team's pipeline)
│   └── papers/                   # arXiv papers → citations eval (papers-team pipeline)
├── scripts/
│   └── validate_doctrines.py     # canonical-layout check; run after any doctrines/ change
└── web/                          # Presentation site (Next.js, TBD)
```

Each eval follows the same methodology: build forced-choice pairs of problems where one had the better outcome (more stars / more citations), present each persona with both problems anonymized, and score consistency-weighted accuracy across 1000+ pairs.

Each persona ships with **two tiers**: a short AI-generated `doctrine-light.md` (the experimental baseline) and a longer `doctrine-distilled.md` derived from the persona's actual writings. The eval runs both as separate leaderboard entries (`<id>-light` vs `<id>-distilled`) so we can measure whether careful distillation actually outperforms the AI-generated stub.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add: ANTHROPIC_API_KEY, GH_TOKEN
```

## Run order

- **HN eval data prep**: see [`evals/hn/README.md`](evals/hn/README.md)
- **Papers eval data prep**: see [`evals/papers/README.md`](evals/papers/README.md)
- **Persona eval**: `python evals/papers/scripts/run_eval.py --smoke` (papers domain only — shared runner across HN+papers is TODO)
- **Validate the doctrines library**: `python scripts/validate_doctrines.py`

## Methodology in one paragraph

For each eval domain, build a corpus of problem pitches, anonymize them aggressively (strip identifiers, success metrics, hype voice), pair them within tight cohorts (`quarter × language` for HN, `subfield × year` for papers), and force each distilled persona to pick which one they'd work on. Run twice with order flipped. Score each pair tri-state (+1 if correct both times, 0 if flipped, -1 if wrong both times). Report accuracy, consistency rate, and inter-persona agreement matrix. Compare against random, vanilla-LLM, and crowd baselines.
