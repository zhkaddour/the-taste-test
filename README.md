# The Taste Test

> Distilling the taste of great problem-pickers into something measurable.

**Thesis**: taste in problem selection is a *prediction function*. A senior thinker reading a pitch is silently forecasting "will this matter / does this rot / is this load-bearing." If we extract that function from their writing and run it against historical outcomes, we can score how well we captured it — and compare distilled thinkers against each other.

## What's here

```
taste-test/
├── doctrines/           # Distilled "doctrines" (15 personas + 4 richer playbooks)
├── evals/
│   ├── hn/              # Show HN → GitHub-stars eval (this team's pipeline)
│   └── papers/          # arXiv papers → citations eval (papers-team pipeline)
└── web/                 # Presentation site (Next.js, TBD)
```

Each eval follows the same methodology: build forced-choice pairs of problems where one had the better outcome (more stars / more citations), present each persona with both problems anonymized, and score consistency-weighted accuracy across 1000+ pairs.

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
- **Persona eval (both)**: TODO — shared runner not yet built; for now use `evals/papers/scripts/run_eval.py`

## Methodology in one paragraph

For each eval domain, build a corpus of problem pitches, anonymize them aggressively (strip identifiers, success metrics, hype voice), pair them within tight cohorts (`quarter × language` for HN, `subfield × year` for papers), and force each distilled persona to pick which one they'd work on. Run twice with order flipped. Score each pair tri-state (+1 if correct both times, 0 if flipped, -1 if wrong both times). Report accuracy, consistency rate, and inter-persona agreement matrix. Compare against random, vanilla-LLM, and crowd baselines.
