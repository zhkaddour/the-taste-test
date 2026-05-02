---
name: doctrines
description: Use when the user wants to evaluate an idea, project, or problem through the lens of a famous thinker (e.g. "what would Thiel say about this?", "judge this paper as Hamming would"). Loads a doctrine and applies its Rule/Test framework in the persona's voice.
---

# Doctrines — Famous Thinkers as Evaluation Lenses

This library contains distilled doctrines from notable thinkers, each
expressed as a three-layer filter:

- **Layer 1 — Problem-Selection Taste**: what is worth working on
- **Layer 2 — Approach Taste**: given the problem, which angle
- **Layer 3 — Stopping Taste**: when to abandon, when to push

Every entry has a **Rule** (the principle), a **Test** (a concrete
probe to apply), and a **Source** (the citation).

Two tiers per persona:

- `doctrine-light.md` — short, AI-generated baseline (always present)
- `doctrine-distilled.md` — longer, distilled from primary sources
  (present when available)

## How to apply a doctrine

1. Identify which persona's lens the user wants. If they don't name one,
   pick the persona whose stated priors best match the question's domain.
2. Read `doctrines/<persona-id>/doctrine-distilled.md` if it exists,
   otherwise `doctrines/<persona-id>/doctrine-light.md`.
3. Speak in the persona's voice. Use their priors and vocabulary.
4. Apply the layer that fits the question:
   - "Should I work on X?" → Layer 1
   - "How should I approach X?" → Layer 2
   - "Should I stop / pivot / sell?" → Layer 3
5. For forced-choice between two options, score each candidate against
   the relevant Tests; pick the one that survives more of them.

## Persona ids

Kebab-case directory names under `doctrines/`. To list:

```bash
ls doctrines/ | grep -v '\.md$'
```

Each directory contains the persona's doctrine files. The directory name
*is* the persona_id; nothing else encodes it.
