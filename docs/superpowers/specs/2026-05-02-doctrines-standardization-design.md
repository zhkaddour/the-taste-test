# Doctrines Library Standardization — Design

**Status:** Draft for review
**Owner:** Zaid
**Date:** 2026-05-02
**Scope:** PLAN.md Step 1 — standardize the doctrines library before running evals

---

## Problem

The `doctrines/` library serves two consumers — the eval pipeline today, and (soon) the web-app "taste test agent" + an open-source skill anyone can drop into their LLM. It can't serve either cleanly in its current state:

- **Three+ incompatible markdown formats** coexist (rich `the-*-doctrine.md`, compact `*_LAYERS.md`, medium `vol-NN-*.md`, plus a one-off `MUNGER_LATTICE_PLAYBOOK.md` that doesn't fit the 3-layer mold).
- **Duplicates**: Thiel × 3 files, Graham × 2 files.
- **Filename casing is mixed** (kebab, UPPER_SNAKE, numbered) and none encode persona_id; the runner relies on a hardcoded `DOCTRINE_MAP` ([evals/papers/scripts/run_eval.py:39-44](../../../evals/papers/scripts/run_eval.py#L39-L44)) that knows only 4 of the ~21 distilled files.
- **Two artifact types are conflated**: the AI-generated stub (currently `profile.json`) and the human-distilled doctrine (markdown). They serve different purposes and the eval needs to compare them, but they're stored in different shapes (JSON vs MD) and the runner treats them as fallback tiers rather than independent personas.
- **No frontmatter anywhere** — none of the files are loadable as Claude Code skills.
- **3 personas have a distilled doctrine but no light stub**: `cathie-wood`, `andrej-karpathy`, `ayn-rand`.
- **9 personas only have the compact `_LAYERS.md`** form, which omits the `Test:` field — the runnable probe that makes a doctrine usable as an evaluation framework rather than a quotation.

## Goals

1. **Eval consumer**: every persona is loadable through one consistent file-layout convention; light-vs-distilled is a fair head-to-head comparison.
2. **Open-source consumer**: the entire `doctrines/` directory can be dropped into `~/.claude/skills/` (or pasted into a system prompt, or read by a web-app agent) and Just Work.
3. **One canonical format** for distilled doctrines, with all required fields (Rule / Test / Source) populated for every persona.
4. **No duplicates, no orphan files, no special cases.** A new persona is "drop a directory in, done."

## Non-goals

- Re-distilling doctrines from primary sources (out of scope; trust existing distilled content).
- Generating new doctrines from scratch.
- Rewriting the light AI-generated baselines to be sharper — they're the experimental control.
- Changing the eval methodology (forced-choice / tri-state / order-flip remains unchanged).
- Web-app integration work (separate teammate's track).

---

## Design

### File layout

```
doctrines/
  README.md                           # what the library is, how to use it
  SKILL.md                            # frontmatter + wrapper template
                                      #   shared by eval, web app, and any LLM agent
  <persona-id>/
    doctrine-light.md                 # AI-generated baseline (always present)
    doctrine-distilled.md             # human-distilled (when available)
```

- **persona-id** is **kebab-case**, e.g. `peter-thiel`, `richard-hamming`, `cathie-wood`. The directory name *is* the persona_id; nothing else encodes it.
- **No `profile.json` anywhere.** The light tier is markdown like the distilled tier — same loader, same renderer, fair comparison.
- **No frontmatter on the doctrine files themselves.** Frontmatter only lives on `SKILL.md` at the top of the library. The doctrine files are pure content.
- **`_playbooks/` directory is removed.** All distilled content moves into per-persona dirs.

### `doctrine-light.md` format

Plain markdown converted from the current `profile.json` fields. ~10 lines.

```markdown
# Richard Hamming — Light Doctrine

**Bio:** Mathematician, 'You and Your Research' lecturer. Asks why
you aren't working on the most important problem in your field.

**Priors:**
- Work on important problems, not just interesting ones
- Courage to attack hard problems openly
- Compounding: small daily effort on the right problem
```

The H1 carries the display name; "— Light Doctrine" makes the tier explicit when the file is read in isolation.

### `doctrine-distilled.md` format (canonical)

Based on the existing `vol-NN-*.md` shape. Three layers, every entry carries Rule + Test + Source.

```markdown
# The Hamming Doctrine

> "What are the important problems of your field? Why aren't you
> working on them?"

**About:** Three-layer filter for choosing and executing research
work. Distilled from 'You and Your Research' (1986), 'The Art of
Doing Science and Engineering' (1995-1998), and the Bell Labs
operating record (1945-1986). Every doctrine carries a rule, a
concrete test, and its source.

---

## Layer 1 — Problem-Selection Taste
*What is worth working on at all*

[Layer rationale paragraph — 2-4 sentences setting the lens.]

### The Monday Morning Question
**Rule:** Every Monday morning ask: 'What are the important
problems of my field?' Then ask: 'Why am I not working on them?'
**Test:** Can the researcher name the top three problems and
articulate, for each, a concrete reason why they're not currently
attacking it? Vague answers ("not my area," "too hard") fail.
**Source:** You and Your Research, Bell Labs 1986.

### [Next entry...]
**Rule:** ...
**Test:** ...
**Source:** ...

---

## Layer 2 — Approach Taste
*Given the problem, which angle to attack from*

[Layer rationale paragraph]

### [entries with Rule / Test / Source...]

---

## Layer 3 — Stopping Taste
*When to abandon, when to push, when "done enough"*

[Layer rationale paragraph]

### [entries with Rule / Test / Source...]

---

## 2026 Overlay

### Where the alpha is
- [bullet list of current high-conviction areas in the persona's voice]

### Auto-reject
- [bullet list of structural disqualifiers in the persona's voice]
```

Notes:
- **No `01.01·` numeric prefixes** on entry titles (kept the original vol-NN choice — it's cleaner).
- **No `**Chapter:**` field** — fold the chapter info into `Source:` when it exists (e.g. *"Zero to One, Ch.1 (pp.7-8)"*). One field, not two.
- **Layer rationale paragraph** is preserved (rich format had it; vol-NN format had it; LAYERS format had it). It frames the lens.
- **2026 Overlay is required.** It's the most load-bearing section for taste-test framing on modern artifacts — strip it and the persona can't speak about today.
- **"About:" paragraph** is required. It's Hannah's "playbook-summary wrapper" from PLAN.md Step 3, already present in rich/medium formats — just standardize the heading.

### `SKILL.md` (the wrapper)

One file at `doctrines/SKILL.md`. Two roles:

1. **Claude Code skill** — drop the `doctrines/` directory into `~/.claude/skills/` (or `<project>/.claude/skills/`) and the agent can invoke it. Frontmatter `description` is what triggers it.
2. **Wrapper template** — its body contains the prompt scaffolding the eval pipeline and the web-app agent both read at runtime, so there's exactly one source of truth for "how to channel a doctrine."

Shape:

```markdown
---
name: doctrines
description: Use when the user wants to evaluate an idea, project, or
  problem through the lens of a famous thinker (e.g. "what would Thiel
  say about this?", "judge this paper as Hamming would"). Loads a
  doctrine and applies its Rule/Test framework in the persona's voice.
---

# Doctrines — Famous Thinkers as Evaluation Lenses

This library contains distilled doctrines from notable thinkers, each
expressed as a three-layer filter:

- **Layer 1 — Problem-Selection Taste**: what is worth working on
- **Layer 2 — Approach Taste**: given the problem, which angle
- **Layer 3 — Stopping Taste**: when to abandon, when to push

Every entry has a **Rule** (the principle), a **Test** (a concrete
probe to apply), and a **Source** (the citation).

## How to apply a doctrine

1. Read the relevant `doctrines/<persona-id>/doctrine-distilled.md`
   (or `doctrine-light.md` if no distilled version exists).
2. Speak in the persona's voice. Use their priors.
3. Apply the layer that fits the question:
   - "Should I work on X?" → Layer 1
   - "How should I approach X?" → Layer 2
   - "Should I stop / pivot / sell?" → Layer 3
4. For forced-choice between two options, score each against the
   relevant Tests; pick the one that survives more of them.

## Available doctrines

[Auto-generated table: persona-id, display name, has-distilled?,
one-line tagline drawn from the doctrine's epigraph quote.]
```

The eval runner consumes the same `SKILL.md` body as a string, prepends the loaded doctrine, appends the forced-choice prompt. The web app does the same with its own user-facing wrapping. **The skill body is the contract; the doctrine files are the content.**

### Eval runner changes

- Drop `DOCTRINE_MAP` entirely.
- Replace `load_personas()` with a function that walks `doctrines/<persona-id>/` and emits **two persona records per directory** when both files exist:
  - `{persona_id}-light` from `doctrine-light.md`
  - `{persona_id}-distilled` from `doctrine-distilled.md`
- Persona display names use the H1 from each file.
- Both tiers go on the leaderboard side-by-side. Light-vs-distilled becomes a built-in head-to-head: does the AI-generated stub do as well as the carefully distilled doctrine?
- The runner's prompt-cache block already handles long doctrines correctly ([run_eval.py:213-217](../../../evals/papers/scripts/run_eval.py#L213-L217)) — no change needed there.

### Migration steps (in order)

1. **Rename directories** to kebab-case: `richard_hamming/` → `richard-hamming/`, etc.
2. **Convert `profile.json` → `doctrine-light.md`** for all 15 existing stubs.
3. **Generate 3 missing `doctrine-light.md`** files for `cathie-wood`, `andrej-karpathy`, `ayn-rand` from their distilled content.
4. **De-duplicate**:
   - Keep `vol-18-thiel.md` → move to `peter-thiel/doctrine-distilled.md`. Drop `the-thiel-doctrine.md` and `THIEL_LAYERS.md`.
   - Keep `vol-07-graham.md` → move to `paul-graham/doctrine-distilled.md`. Drop `the-graham-doctrine.md`.
5. **Move all remaining distilled files** into per-persona dirs as `doctrine-distilled.md`. For files in vol-NN format, fold the separate `**Chapter:**` field into `**Source:**` (canonical format has Source only).
6. **Convert rich `the-*-doctrine.md`** (Andreessen, Buffett) to canonical format: drop `01.01·` numeric prefixes, fold Chapter info into Source.
7. **Promote compact `_LAYERS.md` files** to canonical: write `Test:` fields for each entry. **Generated by Claude using the existing Rule and Source as context** — applies to Altman, Hamming, Jensen, Marks, Musk, Naval, Cathie, Karpathy, Rand. The user has confirmed that Claude has enough context to do this without re-reading sources.
8. **Attempt Munger 3-layer conversion** from Poor Charlie's Almanack content: Layer 1 (durable competitive advantages, simple businesses, capable management), Layer 2 (lattice of mental models, inversion, multidisciplinary checklists), Layer 3 ("too hard" pile, sit on cash, hold winners). If the conversion materially distorts Munger's thinking, drop him from the doctrines list and note in README.
9. **Write `SKILL.md`** with frontmatter and the wrapper template above.
10. **Update `doctrines/README.md`** to document the canonical format, the light/distilled tiers, the kebab-case convention, and the SKILL.md role.
11. **Refactor `evals/papers/scripts/run_eval.py`**: drop `DOCTRINE_MAP`, replace `load_personas()` with directory walk, emit both tiers as separate persona records.
12. **Run smoke test** (3 personas × 5 pairs × 1 order, papers domain) to confirm everything loads and produces parseable output.

### Test plan

- **Loading test**: every persona-id directory yields at least one valid persona record (light); persona-ids with `doctrine-distilled.md` yield two records.
- **Format consistency**: a script verifies every `doctrine-distilled.md` has exactly 3 layers, each layer has ≥1 entry, every entry has Rule + Test + Source.
- **Eval smoke test**: run the existing smoke command (`scripts/run_eval.py --smoke`) with the new layout. Verify pair logs are parseable, no missing personas, no DOCTRINE_MAP errors.
- **Light-vs-distilled sanity**: on the smoke run, confirm that `peter-thiel-light` and `peter-thiel-distilled` both produce judgments, both appear on the leaderboard, and the prompts visibly differ.

---

## Open questions

None at this point. The user has confirmed every fork (file naming, format choice, Test-field generation, SKILL.md scope, Munger attempt-then-fall-back).

## What "done" looks like

- `doctrines/` contains exactly: `README.md`, `SKILL.md`, and one kebab-case subdirectory per persona, each with `doctrine-light.md` and (when available) `doctrine-distilled.md`. No `profile.json`, no `_playbooks/`, no duplicates.
- `evals/papers/scripts/run_eval.py` runs cleanly without `DOCTRINE_MAP`, loads ~36 persona records (~18 light + ~18 distilled, minus Munger if he was scrapped), and the smoke test passes.
- A future contributor can add a new persona by creating one directory with one or two markdown files. No code changes required.
