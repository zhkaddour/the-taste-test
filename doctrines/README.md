# Doctrines

Distilled doctrines of notable thinkers, each formatted as a three-layer
evaluation filter. Used by the eval pipeline (papers and HN domains) and
by the web-app taste-test agent.

## Layout

```
doctrines/
├── README.md                       # this file
├── SKILL.md                        # frontmatter + how to use, for any LLM agent
└── <persona-id>/                   # kebab-case (e.g. peter-thiel, richard-hamming)
    ├── doctrine-light.md           # short AI-generated baseline (always present)
    └── doctrine-distilled.md       # canonical 3-layer doctrine (when available)
```

## Two tiers per persona

| Tier | File | Origin | Use |
|---|---|---|---|
| **Light** | `doctrine-light.md` | AI-generated from the persona's public profile | Baseline; runs as `<id>-light` in the eval |
| **Distilled** | `doctrine-distilled.md` | Distilled from the persona's writings/talks | Stronger signal; runs as `<id>-distilled` in the eval |

Both tiers are valid personas. The eval compares them head-to-head — a key
question is: does the carefully distilled doctrine outperform the AI-generated
stub? Don't rewrite the light tier to be sharper; it's the experimental control.

## Canonical `doctrine-distilled.md` format

```markdown
# The <Person> Doctrine

> "<one-line epigraph>"

**About:** <distillation summary — sources, what makes it distinctive>.

## Layer 1 — Problem-Selection Taste
*What is worth working on at all*

<rationale paragraph>

### <Entry Title>
**Rule:** <principle>.

**Test:** <concrete probe an agent can run>.

**Source:** <citation>.

[more entries...]

## Layer 2 — Approach Taste
*Given the problem, which angle to attack from*

[same structure]

## Layer 3 — Stopping Taste
*When to abandon, when to push, when "done enough"*

[same structure]

## 2026 Overlay

#### Where the alpha is
- <persona's high-conviction current bets>

#### Auto-reject
- <persona's structural disqualifiers today>
```

## Adding a new persona

1. Create `doctrines/<kebab-case-id>/`.
2. Add `doctrine-light.md` (mandatory). Format:
   ```markdown
   # <Name> — Light Doctrine

   **Bio:** <one-paragraph bio>.

   **Priors:**
   - <prior 1>
   - <prior 2>
   - <prior 3>
   ```
3. Optionally add `doctrine-distilled.md` (canonical format above).
4. Run `python3 scripts/validate_doctrines.py` — must pass.
5. The eval runner picks it up automatically (no code changes needed).

## Validation

```bash
python3 scripts/validate_doctrines.py
```

Exits 0 on PASS. Run after any change to `doctrines/`.
