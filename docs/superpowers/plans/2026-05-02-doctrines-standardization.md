# Doctrines Standardization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardize the `doctrines/` library so every persona is one kebab-case directory containing `doctrine-light.md` (always) and optionally `doctrine-distilled.md` (canonical 3-layer Rule/Test/Source format), the eval runner loads both tiers as separate persona records, and a single `SKILL.md` makes the library legible to any LLM agent.

**Architecture:** Per-persona directories replace the split `_playbooks/` + per-persona-stub layout. The light tier (AI-generated baseline) and distilled tier (human-distilled from primary sources) are both markdown — same loader, fair head-to-head comparison. The runner walks `doctrines/<id>/` and emits two persona records per directory when both files exist.

**Tech Stack:** Python 3.13, anthropic SDK, plain markdown. No new dependencies. No pytest (no existing test infra; we use a runnable validator script + the existing `run_eval.py --smoke` as integration test).

---

## Reference: Canonical `doctrine-distilled.md` format

```markdown
# The <Person> Doctrine

> "<one-line epigraph quote>"

**About:** <2-4 sentence distillation summary — what was the source corpus,
what is the doctrine, what makes it distinctive>.

---

## Layer 1 — Problem-Selection Taste
*What is worth working on at all*

<2-4 sentence layer rationale paragraph>.

### <Entry Title>
**Rule:** <one or two sentence principle>.
**Test:** <a concrete probe an agent can run against an idea — what would
this person actually ask or check>.
**Source:** <citation, with chapter/page if known>.

### <Next Entry Title>
**Rule:** ...
**Test:** ...
**Source:** ...

---

## Layer 2 — Approach Taste
*Given the problem, which angle to attack from*

<rationale paragraph>

### <entries with Rule / Test / Source...>

---

## Layer 3 — Stopping Taste
*When to abandon, when to push, when "done enough"*

<rationale paragraph>

### <entries with Rule / Test / Source...>

---

## 2026 Overlay

### Where the alpha is
- <bullet items in the persona's voice — what they'd say is high-conviction today>

### Auto-reject
- <bullet items in the persona's voice — what they'd structurally reject today>
```

**Required transformations from existing formats:**
- **From rich `the-*-doctrine.md`**: drop `**01.01·` numeric prefixes, change `*Source: ...*` (italic) to `**Source:** ...` (bold), drop the trailing backtick chapter tag like `` `Ch.1` `` from headings (fold into Source), drop "Created/Layers/Doctrines" subtitle line.
- **From medium `vol-NN-*.md`**: drop `**Chapter:** ...` line entirely (fold info into Source if not already redundant), drop the `# VOL. NN / X` title prefix and `**Subject:** ...` line.
- **From compact `*_LAYERS.md`**: convert each `- **Title** *(Source)* — One-sentence rule.` bullet into a `### Title` heading with `**Rule:**`, generated `**Test:**`, and `**Source:**`. Preserve existing layer rationale paragraphs and 2026 Overlay. Drop the "## Verdict logic" section.

**Test-field generation rule** (for LAYERS files): the Test must be a *concrete probe* — what the persona would actually ask, check, or measure to evaluate an idea. Not a paraphrase of the Rule. Looks like: a yes/no question on a specific signal, a numerical threshold, or a behavioral observation. ~1-2 sentences.

---

## Reference: Canonical `doctrine-light.md` format

```markdown
# <Person> — Light Doctrine

**Bio:** <one-paragraph bio drawn from the existing profile.json `bio` field>.

**Priors:**
- <prior 1>
- <prior 2>
- <prior 3>
```

---

## Persona inventory (post-migration target)

| persona-id (kebab) | dir name change | light source | distilled source |
|---|---|---|---|
| `balaji-srinivasan` | from `balaji_srinivasan` | existing profile.json | `vol-03-balaji.md` |
| `charlie-munger` | from `charlie_munger` | existing profile.json | `MUNGER_LATTICE_PLAYBOOK.md` (attempt 3-layer; drop if fails) |
| `elon-musk` | from `elon_musk` | existing profile.json | `MUSK_LAYERS.md` (LAYERS promotion) |
| `george-soros` | from `george_soros` | existing profile.json | `vol-16-soros.md` |
| `howard-marks` | from `howard_marks` | existing profile.json | `MARKS_LAYERS.md` (LAYERS promotion) |
| `jensen-huang` | from `jensen_huang` | existing profile.json | `JENSEN_LAYERS.md` (LAYERS promotion) |
| `marc-andreessen` | from `marc_andreessen` | existing profile.json | `the-andreessen-doctrine.md` |
| `nassim-taleb` | from `nassim_taleb` | existing profile.json | `vol-17-taleb.md` |
| `naval-ravikant` | from `naval_ravikant` | existing profile.json | `NAVAL_LAYERS.md` (LAYERS promotion) |
| `paul-graham` | from `paul_graham` | existing profile.json | `vol-07-graham.md` (drop `the-graham-doctrine.md`) |
| `peter-thiel` | from `peter_thiel` | existing profile.json | `vol-18-thiel.md` (drop `THIEL_LAYERS.md`, `the-thiel-doctrine.md`) |
| `ray-dalio` | from `ray_dalio` | existing profile.json | `vol-06-dalio.md` |
| `richard-hamming` | from `richard_hamming` | existing profile.json | `HAMMING_LAYERS.md` (LAYERS promotion) |
| `sam-altman` | from `sam_altman` | existing profile.json | `ALTMAN_LAYERS.md` (LAYERS promotion) |
| `warren-buffett` | from `warren_buffett` | existing profile.json | `the-buffett-doctrine.md` |
| `cathie-wood` | new dir | generate from distilled | `CATHIE_LAYERS.md` (LAYERS promotion) |
| `andrej-karpathy` | new dir | generate from distilled | `KARPATHY_LAYERS.md` (LAYERS promotion) |
| `ayn-rand` | new dir | generate from distilled | `RAND_LAYERS.md` (LAYERS promotion) |

Total: 18 personas, each with a light file, each (probably) with a distilled file. Munger's distilled is conditional.

---

## Task 1: Format validator script

**Files:**
- Create: `scripts/validate_doctrines.py`

- [ ] **Step 1: Create the validator script**

```python
#!/usr/bin/env python3
"""Verify the doctrines/ library conforms to the canonical layout.

Usage: python scripts/validate_doctrines.py
Exits 0 on PASS, 1 on FAIL with a list of issues.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCTRINES = ROOT / "doctrines"

KEBAB_RE = re.compile(r"^[a-z]+(-[a-z]+)*$")
LAYER_HEADING_RE = re.compile(r"^## Layer [123] —", re.MULTILINE)
ENTRY_HEADING_RE = re.compile(r"^### \S", re.MULTILINE)
RULE_RE = re.compile(r"^\*\*Rule:\*\*\s+\S", re.MULTILINE)
TEST_RE = re.compile(r"^\*\*Test:\*\*\s+\S", re.MULTILINE)
SOURCE_RE = re.compile(r"^\*\*Source:\*\*\s+\S", re.MULTILINE)
OVERLAY_RE = re.compile(r"^## 2026 Overlay", re.MULTILINE)

def validate() -> list[str]:
    issues: list[str] = []
    if not DOCTRINES.exists():
        return [f"missing dir: {DOCTRINES}"]

    # Top-level: README.md, SKILL.md, persona dirs only
    allowed_top = {"README.md", "SKILL.md"}
    for entry in sorted(DOCTRINES.iterdir()):
        if entry.is_file():
            if entry.name not in allowed_top:
                issues.append(f"unexpected file at top level: {entry.name}")
            continue
        if entry.name.startswith("_") or entry.name.startswith("."):
            issues.append(f"unexpected non-persona dir: {entry.name}")
            continue
        if not KEBAB_RE.match(entry.name):
            issues.append(f"non-kebab persona dir: {entry.name}")

    # Per-persona: doctrine-light.md required, doctrine-distilled.md optional, no profile.json
    persona_dirs = [d for d in DOCTRINES.iterdir() if d.is_dir() and KEBAB_RE.match(d.name)]
    for pdir in sorted(persona_dirs):
        light = pdir / "doctrine-light.md"
        distilled = pdir / "doctrine-distilled.md"
        legacy_json = pdir / "profile.json"

        if legacy_json.exists():
            issues.append(f"{pdir.name}: legacy profile.json still present")

        if not light.exists():
            issues.append(f"{pdir.name}: missing doctrine-light.md")
        else:
            text = light.read_text()
            if not text.lstrip().startswith("# "):
                issues.append(f"{pdir.name}/doctrine-light.md: missing H1")
            if "**Bio:**" not in text:
                issues.append(f"{pdir.name}/doctrine-light.md: missing **Bio:**")
            if "**Priors:**" not in text:
                issues.append(f"{pdir.name}/doctrine-light.md: missing **Priors:**")

        if distilled.exists():
            text = distilled.read_text()
            layers = LAYER_HEADING_RE.findall(text)
            if len(layers) != 3:
                issues.append(f"{pdir.name}/doctrine-distilled.md: expected 3 layer headings, got {len(layers)}")
            entries = ENTRY_HEADING_RE.findall(text)
            if len(entries) < 3:
                issues.append(f"{pdir.name}/doctrine-distilled.md: only {len(entries)} entries (expected ≥3 per layer × 3 layers)")
            n_rule, n_test, n_source = len(RULE_RE.findall(text)), len(TEST_RE.findall(text)), len(SOURCE_RE.findall(text))
            if not (n_rule == n_test == n_source):
                issues.append(f"{pdir.name}/doctrine-distilled.md: Rule/Test/Source counts mismatch ({n_rule}/{n_test}/{n_source})")
            if n_rule < len(entries):
                issues.append(f"{pdir.name}/doctrine-distilled.md: {len(entries)} entries but only {n_rule} Rule fields")
            if not OVERLAY_RE.search(text):
                issues.append(f"{pdir.name}/doctrine-distilled.md: missing '## 2026 Overlay' section")

    # No _playbooks/ dir
    if (DOCTRINES / "_playbooks").exists():
        issues.append("_playbooks/ directory still exists — should be deleted")

    return issues

def main() -> int:
    issues = validate()
    if not issues:
        print("PASS — doctrines/ library is canonical")
        return 0
    print(f"FAIL — {len(issues)} issue(s):")
    for i in issues:
        print(f"  - {i}")
    return 1

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the validator to confirm it loads and reports the current (broken) state**

Run: `python scripts/validate_doctrines.py`
Expected: FAIL with many issues (legacy `profile.json` per persona, snake_case dirs, `_playbooks/` exists, missing `SKILL.md`, etc.). This is correct — the validator is working.

- [ ] **Step 3: Commit**

```bash
git add scripts/validate_doctrines.py
git commit -m "scripts: add doctrines library validator"
```

---

## Task 2: Rename existing persona directories to kebab-case

**Files:**
- Rename: `doctrines/<snake_case>/` → `doctrines/<kebab-case>/` for all 15 existing persona dirs.

- [ ] **Step 1: Rename all 15 dirs using `git mv` to preserve history**

```bash
cd doctrines
git mv balaji_srinivasan balaji-srinivasan
git mv charlie_munger charlie-munger
git mv elon_musk elon-musk
git mv george_soros george-soros
git mv howard_marks howard-marks
git mv jensen_huang jensen-huang
git mv marc_andreessen marc-andreessen
git mv nassim_taleb nassim-taleb
git mv naval_ravikant naval-ravikant
git mv paul_graham paul-graham
git mv peter_thiel peter-thiel
git mv ray_dalio ray-dalio
git mv richard_hamming richard-hamming
git mv sam_altman sam-altman
git mv warren_buffett warren-buffett
cd ..
```

- [ ] **Step 2: Verify all dirs renamed, no snake_case remaining**

Run: `ls doctrines/ | grep '_' && echo "FAIL" || echo "PASS"`
Expected: `PASS`

- [ ] **Step 3: Update `persona_id` field inside each profile.json to match new kebab dir name**

For each persona dir, edit the `profile.json` to change `"persona_id": "snake_case"` to `"persona_id": "kebab-case"`. (This file goes away in Task 3, but we keep it consistent for one commit.)

```bash
for d in doctrines/*/; do
  pid=$(basename "$d")
  python3 -c "
import json, sys
from pathlib import Path
p = Path('$d/profile.json')
data = json.loads(p.read_text())
data['persona_id'] = '$pid'
p.write_text(json.dumps(data, indent=2) + '\n')
"
done
```

- [ ] **Step 4: Run validator to confirm dir naming progress**

Run: `python scripts/validate_doctrines.py 2>&1 | grep -c "non-kebab"`
Expected: `0`

- [ ] **Step 5: Commit**

```bash
git add -A doctrines/
git commit -m "doctrines: rename persona dirs to kebab-case"
```

---

## Task 3: Convert `profile.json` → `doctrine-light.md` for all 15 existing personas

**Files:**
- Create: `doctrines/<persona-id>/doctrine-light.md` × 15
- Delete: `doctrines/<persona-id>/profile.json` × 15

- [ ] **Step 1: Write a one-shot conversion script and run it**

```bash
python3 <<'PY'
import json
from pathlib import Path

DOCTRINES = Path("doctrines")
for pdir in sorted(DOCTRINES.iterdir()):
    if not pdir.is_dir():
        continue
    pj = pdir / "profile.json"
    if not pj.exists():
        continue
    data = json.loads(pj.read_text())
    name = data["name"]
    bio = data["bio"]
    priors = data["priors"]

    out = f"# {name} — Light Doctrine\n\n"
    out += f"**Bio:** {bio}\n\n"
    out += "**Priors:**\n"
    for p in priors:
        out += f"- {p}\n"

    (pdir / "doctrine-light.md").write_text(out)
    pj.unlink()
    print(f"  converted: {pdir.name}")
PY
```

- [ ] **Step 2: Spot-check one converted file**

Run: `cat doctrines/peter-thiel/doctrine-light.md`
Expected: Markdown with `# Peter Thiel — Light Doctrine`, a `**Bio:**` paragraph, and a `**Priors:**` bullet list (3 items).

- [ ] **Step 3: Run validator — light files should now pass; profile.json should be gone**

Run: `python scripts/validate_doctrines.py 2>&1 | grep -E "profile.json|doctrine-light"`
Expected: empty (no errors mentioning profile.json or missing doctrine-light)

- [ ] **Step 4: Commit**

```bash
git add -A doctrines/
git commit -m "doctrines: convert profile.json stubs to doctrine-light.md"
```

---

## Task 4: Create 3 new persona directories with `doctrine-light.md`

**Files:**
- Create: `doctrines/cathie-wood/doctrine-light.md`
- Create: `doctrines/andrej-karpathy/doctrine-light.md`
- Create: `doctrines/ayn-rand/doctrine-light.md`

- [ ] **Step 1: Create `doctrines/cathie-wood/doctrine-light.md`**

Read `doctrines/_playbooks/CATHIE_LAYERS.md` to extract bio context, then write:

```markdown
# Cathie Wood — Light Doctrine

**Bio:** Founder of ARK Invest. Thematic-disruptive-innovation investor focused on five platforms (AI, robotics, energy storage, blockchain, multi-omic sequencing). High-conviction, concentrated, long-duration; willing to be early and to drawdown publicly.

**Priors:**
- Disruptive innovation compounds at exponential rates
- Convergence across S-curves matters more than any single curve
- Public conviction beats benchmark hugging
```

- [ ] **Step 2: Create `doctrines/andrej-karpathy/doctrine-light.md`**

Read `doctrines/_playbooks/KARPATHY_LAYERS.md` to extract bio context, then write:

```markdown
# Andrej Karpathy — Light Doctrine

**Bio:** Former director of AI at Tesla, founding member of OpenAI. Deep-learning practitioner-explainer; values working code over theory, simple training loops, and end-to-end neural systems that subsume hand-engineered pipelines.

**Priors:**
- Software 2.0: replace stacks with neural nets where possible
- Working baselines beat clever architectures
- Build the whole training loop yourself before reaching for frameworks
```

- [ ] **Step 3: Create `doctrines/ayn-rand/doctrine-light.md`**

Read `doctrines/_playbooks/RAND_LAYERS.md` to extract bio context, then write:

```markdown
# Ayn Rand — Light Doctrine

**Bio:** Novelist and philosopher (Objectivism). Author of *Atlas Shrugged* and *The Fountainhead*. Champions reason, individualism, productive achievement, and rational self-interest as the engines of human flourishing.

**Priors:**
- Rational self-interest is the moral baseline
- Productive achievement is the meaning of life
- Reject the unearned: in achievement, in praise, in rewards
```

- [ ] **Step 4: Run validator**

Run: `python scripts/validate_doctrines.py 2>&1 | grep -E "cathie-wood|andrej-karpathy|ayn-rand"`
Expected: empty (no missing-light errors for these three)

- [ ] **Step 5: Commit**

```bash
git add doctrines/cathie-wood doctrines/andrej-karpathy doctrines/ayn-rand
git commit -m "doctrines: add light tier for cathie-wood, andrej-karpathy, ayn-rand"
```

---

## Task 5: De-duplicate Thiel files

**Files:**
- Move: `doctrines/_playbooks/vol-18-thiel.md` → `doctrines/peter-thiel/doctrine-distilled.md` (with format fixes)
- Delete: `doctrines/_playbooks/THIEL_LAYERS.md`
- Delete: `doctrines/_playbooks/the-thiel-doctrine.md`

- [ ] **Step 1: Move and convert `vol-18-thiel.md` to canonical**

Read `doctrines/_playbooks/vol-18-thiel.md`. Apply transformations:
- Drop `# VOL. 18 / THIEL` and `## The Thiel Doctrine` opening, replace with single `# The Thiel Doctrine` H1.
- Drop `**Subject:** Peter Thiel` line.
- Keep epigraph `> "..."` line.
- Keep `**About:**` distillation paragraph (rename if currently unlabeled).
- For each entry: drop the `**Chapter:** Ch.X` field — fold into Source if not already present.
- Layer headings should be `## Layer 1 — Problem-Selection Taste` (the file may currently have just `## Problem-Selection Taste` — add the layer prefix).

Write the result to `doctrines/peter-thiel/doctrine-distilled.md`.

- [ ] **Step 2: Delete the duplicate Thiel files**

```bash
git rm doctrines/_playbooks/vol-18-thiel.md
git rm doctrines/_playbooks/THIEL_LAYERS.md
git rm doctrines/_playbooks/the-thiel-doctrine.md
```

- [ ] **Step 3: Run validator — Thiel distilled should now exist and validate**

Run: `python scripts/validate_doctrines.py 2>&1 | grep peter-thiel`
Expected: empty

- [ ] **Step 4: Commit**

```bash
git add -A doctrines/
git commit -m "doctrines: dedupe peter-thiel and convert to canonical distilled"
```

---

## Task 6: De-duplicate Graham files

**Files:**
- Move: `doctrines/_playbooks/vol-07-graham.md` → `doctrines/paul-graham/doctrine-distilled.md` (with format fixes)
- Delete: `doctrines/_playbooks/the-graham-doctrine.md`

- [ ] **Step 1: Move and convert `vol-07-graham.md` to canonical**

Same transformations as Task 5 Step 1, applied to the Graham file:
- Title becomes `# The Graham Doctrine`.
- Drop `**Subject:**` line, drop VOL header.
- Drop per-entry `**Chapter:**` fields, fold into Source.
- Layer headings: `## Layer 1 — Problem-Selection Taste`, etc.

Write to `doctrines/paul-graham/doctrine-distilled.md`.

- [ ] **Step 2: Delete duplicates**

```bash
git rm doctrines/_playbooks/vol-07-graham.md
git rm doctrines/_playbooks/the-graham-doctrine.md
```

- [ ] **Step 3: Run validator**

Run: `python scripts/validate_doctrines.py 2>&1 | grep paul-graham`
Expected: empty

- [ ] **Step 4: Commit**

```bash
git add -A doctrines/
git commit -m "doctrines: dedupe paul-graham and convert to canonical distilled"
```

---

## Task 7: Move remaining vol-NN files (4 personas) to per-persona dirs

**Files:**
- Move: `doctrines/_playbooks/vol-03-balaji.md` → `doctrines/balaji-srinivasan/doctrine-distilled.md`
- Move: `doctrines/_playbooks/vol-06-dalio.md` → `doctrines/ray-dalio/doctrine-distilled.md`
- Move: `doctrines/_playbooks/vol-16-soros.md` → `doctrines/george-soros/doctrine-distilled.md`
- Move: `doctrines/_playbooks/vol-17-taleb.md` → `doctrines/nassim-taleb/doctrine-distilled.md`

- [ ] **Step 1: Convert + move all four**

For each of the 4 files, apply the same transformations as Task 5 Step 1 (drop VOL header, drop Subject line, drop per-entry Chapter, fix layer headings) and write to the target persona's `doctrine-distilled.md`.

- [ ] **Step 2: Delete originals**

```bash
git rm doctrines/_playbooks/vol-03-balaji.md
git rm doctrines/_playbooks/vol-06-dalio.md
git rm doctrines/_playbooks/vol-16-soros.md
git rm doctrines/_playbooks/vol-17-taleb.md
```

- [ ] **Step 3: Run validator**

Run: `python scripts/validate_doctrines.py 2>&1 | grep -E "balaji|dalio|soros|taleb"`
Expected: empty

- [ ] **Step 4: Commit**

```bash
git add -A doctrines/
git commit -m "doctrines: move vol-NN files to per-persona dirs as canonical distilled"
```

---

## Task 8: Convert rich Andreessen doctrine to canonical

**Files:**
- Move: `doctrines/_playbooks/the-andreessen-doctrine.md` → `doctrines/marc-andreessen/doctrine-distilled.md`

- [ ] **Step 1: Convert and move**

Read `doctrines/_playbooks/the-andreessen-doctrine.md`. Apply transformations:
- Keep H1 `# The Andreessen Doctrine` (or add if missing — check `### A Doctrine of Marc Andreessen` line and consolidate).
- Keep epigraph quote.
- Keep `**About this playbook:**` paragraph but rename label to `**About:**` for consistency.
- Drop the `**Created:** ... **Layers:** 3 **Doctrines:** N` subtitle line.
- Drop `**Layer 01 — PROBLEM`, `Layer 02 — APPROACH`, `Layer 03 — STOPPING` numbered prefixes; use canonical `## Layer 1 — Problem-Selection Taste`, `## Layer 2 — Approach Taste`, `## Layer 3 — Stopping Taste`.
- For each entry, transform from `**01.01 · Title** \`Tag\`` to `### Title`.
- Change `*Source: ...*` (italic) to `**Source:** ...` (bold).
- Fold the trailing chapter tag (e.g. `` `Ch.1` ``) from the heading line into Source if not already there.
- Preserve all `**Rule:**` and `**Test:**` content unchanged.
- Preserve "## 2026 Overlay" section (with sub-sections).

Write to `doctrines/marc-andreessen/doctrine-distilled.md`.

- [ ] **Step 2: Delete original**

```bash
git rm doctrines/_playbooks/the-andreessen-doctrine.md
```

- [ ] **Step 3: Worked-example check** — pick one entry to verify the transformation visually

Run: `grep -A 4 "^### " doctrines/marc-andreessen/doctrine-distilled.md | head -20`
Expected: ### headings followed by **Rule:** / **Test:** / **Source:** triples, no numeric prefixes, no trailing backtick tags.

- [ ] **Step 4: Run validator**

Run: `python scripts/validate_doctrines.py 2>&1 | grep marc-andreessen`
Expected: empty

- [ ] **Step 5: Commit**

```bash
git add -A doctrines/
git commit -m "doctrines: convert rich Andreessen doctrine to canonical"
```

---

## Task 9: Convert rich Buffett doctrine to canonical

**Files:**
- Move: `doctrines/_playbooks/the-buffett-doctrine.md` → `doctrines/warren-buffett/doctrine-distilled.md`

- [ ] **Step 1: Convert and move**

Apply the same transformations as Task 8 Step 1 to `the-buffett-doctrine.md`:
- H1 `# The Buffett Doctrine`.
- `**About:**` paragraph (renamed from `**About this playbook:**`).
- Drop `**Created:** ... **Layers:** ...` subtitle line.
- Layer headings: `## Layer 1 — Problem-Selection Taste`, `## Layer 2 — Approach Taste`, `## Layer 3 — Stopping Taste`.
- Drop `01.01·` numeric prefixes from entry headings; drop trailing backtick chapter tags from heading lines (fold into Source).
- Italic Source → bold Source.
- Preserve Rule, Test, 2026 Overlay.

Write to `doctrines/warren-buffett/doctrine-distilled.md`.

- [ ] **Step 2: Delete original**

```bash
git rm doctrines/_playbooks/the-buffett-doctrine.md
```

- [ ] **Step 3: Run validator**

Run: `python scripts/validate_doctrines.py 2>&1 | grep warren-buffett`
Expected: empty

- [ ] **Step 4: Commit**

```bash
git add -A doctrines/
git commit -m "doctrines: convert rich Buffett doctrine to canonical"
```

---

## Tasks 10-18: Promote LAYERS files to canonical (one per persona)

**Shared transformation rules** (applied identically per task):
1. Replace H1 (e.g. `# The Hamming Doctrine — Three Evaluation Layers (Deep Dive)`) with canonical `# The <Person> Doctrine`.
2. Keep the epigraph `> "..."` quote.
3. Convert the existing distillation paragraph into `**About:** ...` (one paragraph).
4. Drop the `**N doctrines across 3 layers.**` subtitle line.
5. Layer headings: ensure they read `## Layer 1 — Problem-Selection Taste` / `## Layer 2 — Approach Taste` / `## Layer 3 — Stopping Taste`. Keep the existing italic sub-tagline (`*What is worth working on at all*`).
6. Keep the layer rationale paragraphs unchanged.
7. **For each `- **Title** *(Source)* — Rule sentence.` bullet, transform into:**
   ```
   ### Title
   **Rule:** Rule sentence.
   **Test:** [generated probe — concrete check the persona would run]
   **Source:** Source.
   ```
   The Test is generated by the executor (Claude). Each Test must be a *concrete probe* — a yes/no question on a specific signal, a numerical threshold, or a behavioral observation — not a paraphrase of the Rule. ~1-2 sentences.
8. Drop sub-section headings inside layers like `### From *You and Your Research* (Bell Labs, 1986)` — these grouped LAYERS bullets but aren't part of the canonical entry structure. Distribute the entries directly under the layer heading.
9. Preserve "## 2026 Overlay" with `### Where the alpha is` and `### Auto-reject` sub-sections.
10. **Drop** the `## Verdict logic` section (not in canonical).

**Worked example for Test-field generation** (from `HAMMING_LAYERS.md`):

Before:
```
- **The Monday Morning Question** *(You and Your Research, 1986)* —
  Every Monday morning ask: 'What are the important problems of my field?'
  Then ask: 'Why am I not working on them?' Most people have never seriously
  posed either.
```

After:
```
### The Monday Morning Question
**Rule:** Every Monday morning ask: 'What are the important problems of my
field?' Then ask: 'Why am I not working on them?'
**Test:** Can the researcher name the top three important problems of their
field unprompted, AND give a concrete reason (capability gap, time, courage)
for not currently working on each? Vague answers fail.
**Source:** You and Your Research, Bell Labs 1986.
```

Note how the Test isn't "ask the Monday morning question" — it's a *probe an evaluator can apply to a candidate*: can they enumerate, can they explain.

---

### Task 10: Promote ALTMAN_LAYERS.md → sam-altman

**Files:**
- Move: `doctrines/_playbooks/ALTMAN_LAYERS.md` → `doctrines/sam-altman/doctrine-distilled.md`

- [ ] **Step 1: Apply shared transformations 1-10** to `ALTMAN_LAYERS.md`. Generate Test fields for every entry (~30+ entries) per the rule above. Write result to `doctrines/sam-altman/doctrine-distilled.md`.
- [ ] **Step 2: Delete original**: `git rm doctrines/_playbooks/ALTMAN_LAYERS.md`
- [ ] **Step 3: Validator**: `python scripts/validate_doctrines.py 2>&1 | grep sam-altman` → empty
- [ ] **Step 4: Commit**: `git add -A doctrines/ && git commit -m "doctrines: promote sam-altman LAYERS to canonical distilled"`

### Task 11: Promote HAMMING_LAYERS.md → richard-hamming

**Files:**
- Move: `doctrines/_playbooks/HAMMING_LAYERS.md` → `doctrines/richard-hamming/doctrine-distilled.md`

- [ ] **Step 1: Apply shared transformations 1-10** with Test fields generated. The worked example above for "The Monday Morning Question" is from this file — apply the same pattern to all ~77 entries.
- [ ] **Step 2: `git rm doctrines/_playbooks/HAMMING_LAYERS.md`**
- [ ] **Step 3: Validator**: `python scripts/validate_doctrines.py 2>&1 | grep richard-hamming` → empty
- [ ] **Step 4: Commit**: `git add -A doctrines/ && git commit -m "doctrines: promote richard-hamming LAYERS to canonical distilled"`

### Task 12: Promote JENSEN_LAYERS.md → jensen-huang

**Files:**
- Move: `doctrines/_playbooks/JENSEN_LAYERS.md` → `doctrines/jensen-huang/doctrine-distilled.md`

- [ ] **Step 1: Apply shared transformations 1-10**. Test fields generated.
- [ ] **Step 2: `git rm doctrines/_playbooks/JENSEN_LAYERS.md`**
- [ ] **Step 3: Validator**: empty for jensen-huang
- [ ] **Step 4: Commit**: `git add -A doctrines/ && git commit -m "doctrines: promote jensen-huang LAYERS to canonical distilled"`

### Task 13: Promote MARKS_LAYERS.md → howard-marks

**Files:**
- Move: `doctrines/_playbooks/MARKS_LAYERS.md` → `doctrines/howard-marks/doctrine-distilled.md`

- [ ] **Step 1: Apply shared transformations 1-10**. Test fields generated.
- [ ] **Step 2: `git rm doctrines/_playbooks/MARKS_LAYERS.md`**
- [ ] **Step 3: Validator**: empty for howard-marks
- [ ] **Step 4: Commit**: `git add -A doctrines/ && git commit -m "doctrines: promote howard-marks LAYERS to canonical distilled"`

### Task 14: Promote MUSK_LAYERS.md → elon-musk

**Files:**
- Move: `doctrines/_playbooks/MUSK_LAYERS.md` → `doctrines/elon-musk/doctrine-distilled.md`

- [ ] **Step 1: Apply shared transformations 1-10**. Test fields generated.
- [ ] **Step 2: `git rm doctrines/_playbooks/MUSK_LAYERS.md`**
- [ ] **Step 3: Validator**: empty for elon-musk
- [ ] **Step 4: Commit**: `git add -A doctrines/ && git commit -m "doctrines: promote elon-musk LAYERS to canonical distilled"`

### Task 15: Promote NAVAL_LAYERS.md → naval-ravikant

**Files:**
- Move: `doctrines/_playbooks/NAVAL_LAYERS.md` → `doctrines/naval-ravikant/doctrine-distilled.md`

- [ ] **Step 1: Apply shared transformations 1-10**. Test fields generated.
- [ ] **Step 2: `git rm doctrines/_playbooks/NAVAL_LAYERS.md`**
- [ ] **Step 3: Validator**: empty for naval-ravikant
- [ ] **Step 4: Commit**: `git add -A doctrines/ && git commit -m "doctrines: promote naval-ravikant LAYERS to canonical distilled"`

### Task 16: Promote CATHIE_LAYERS.md → cathie-wood

**Files:**
- Move: `doctrines/_playbooks/CATHIE_LAYERS.md` → `doctrines/cathie-wood/doctrine-distilled.md`

- [ ] **Step 1: Apply shared transformations 1-10**. Test fields generated.
- [ ] **Step 2: `git rm doctrines/_playbooks/CATHIE_LAYERS.md`**
- [ ] **Step 3: Validator**: empty for cathie-wood
- [ ] **Step 4: Commit**: `git add -A doctrines/ && git commit -m "doctrines: promote cathie-wood LAYERS to canonical distilled"`

### Task 17: Promote KARPATHY_LAYERS.md → andrej-karpathy

**Files:**
- Move: `doctrines/_playbooks/KARPATHY_LAYERS.md` → `doctrines/andrej-karpathy/doctrine-distilled.md`

- [ ] **Step 1: Apply shared transformations 1-10**. Test fields generated.
- [ ] **Step 2: `git rm doctrines/_playbooks/KARPATHY_LAYERS.md`**
- [ ] **Step 3: Validator**: empty for andrej-karpathy
- [ ] **Step 4: Commit**: `git add -A doctrines/ && git commit -m "doctrines: promote andrej-karpathy LAYERS to canonical distilled"`

### Task 18: Promote RAND_LAYERS.md → ayn-rand

**Files:**
- Move: `doctrines/_playbooks/RAND_LAYERS.md` → `doctrines/ayn-rand/doctrine-distilled.md`

- [ ] **Step 1: Apply shared transformations 1-10**. Test fields generated.
- [ ] **Step 2: `git rm doctrines/_playbooks/RAND_LAYERS.md`**
- [ ] **Step 3: Validator**: empty for ayn-rand
- [ ] **Step 4: Commit**: `git add -A doctrines/ && git commit -m "doctrines: promote ayn-rand LAYERS to canonical distilled"`

---

## Task 19: Attempt Munger 3-layer conversion

**Files:**
- Source: `doctrines/_playbooks/MUNGER_LATTICE_PLAYBOOK.md`
- Create (if successful): `doctrines/charlie-munger/doctrine-distilled.md`

- [ ] **Step 1: Attempt the 3-layer extraction from Poor Charlie's Almanack content**

Read `doctrines/_playbooks/MUNGER_LATTICE_PLAYBOOK.md`. The lattice format is organized by *discipline* (Mathematics, Physics, Chemistry, Biology, Psychology, etc.), not by Problem/Approach/Stopping. The conversion attempt: extract Munger's investment-and-decision principles from the lattice and reorganize them into the canonical 3 layers.

Proposed mapping:
- **Layer 1 — Problem-Selection Taste**: Circle of competence, simple-and-understandable businesses, durable competitive advantages (moats), capable and trustworthy management, "wonderful business at fair price > fair business at wonderful price."
- **Layer 2 — Approach Taste**: The lattice itself (multidisciplinary mental models), inversion ("invert, always invert"), checklists, second-order thinking, Lollapalooza effects (multiple models converging).
- **Layer 3 — Stopping Taste**: "Too hard" pile, sit on cash when nothing qualifies, hold winners for decades, avoid envy/resentment-driven actions, Cialdini-trigger awareness as exit signal.

For each layer, extract 8-12 entries from the lattice content. Each entry: a Rule (the principle in Munger's voice), a Test (concrete probe), a Source (which mental-model section it came from, e.g. "Poor Charlie's Almanack — Psychology of Human Misjudgment"). Preserve a layer-rationale paragraph for each.

Add a `## 2026 Overlay` section: where Munger would say alpha is today (per his late writings — he was active until 2023; project his late views forward), and his auto-rejects (crypto, fads, complex derivatives, "things I don't understand").

Write to `doctrines/charlie-munger/doctrine-distilled.md`.

- [ ] **Step 2: Self-evaluate the conversion quality**

Read the result. Ask: does the 3-layer reorganization preserve what's distinctive about Munger (the lattice / multidisciplinary approach), or does it feel like a forced cookie-cutter that loses the essence? Write a one-paragraph note in the commit message describing the verdict.

If the conversion materially distorts Munger's thinking (e.g. the "lattice" is the *whole point* and decomposing it into 3 layers strips the cross-disciplinary cross-pollination), **abort**: don't write the file, instead delete the source and document in the README that Munger has light-tier only.

- [ ] **Step 3: Either commit the conversion OR commit a "Munger-distilled-skipped" decision**

If converted:
```bash
git rm doctrines/_playbooks/MUNGER_LATTICE_PLAYBOOK.md
git add -A doctrines/
git commit -m "doctrines: convert Munger lattice to 3-layer canonical (verdict: <1-line>)"
```

If aborted:
```bash
git rm doctrines/_playbooks/MUNGER_LATTICE_PLAYBOOK.md
git commit -m "doctrines: drop Munger distilled tier (lattice doesn't fit 3-layer mold)"
```

- [ ] **Step 4: Run validator**

Run: `python scripts/validate_doctrines.py 2>&1 | grep charlie-munger`
Expected: empty either way (light is sufficient for validator; distilled is optional).

---

## Task 20: Delete `_playbooks/` directory

**Files:**
- Delete: `doctrines/_playbooks/`

- [ ] **Step 1: Verify the dir is empty**

Run: `ls doctrines/_playbooks/ 2>&1 || echo "already gone"`
Expected: empty listing or "already gone".

- [ ] **Step 2: Remove the directory**

```bash
rmdir doctrines/_playbooks
```

(If `git rm` of all contained files in earlier tasks left it empty in git's eyes too, this just cleans the working tree.)

- [ ] **Step 3: Run validator — `_playbooks` should not be flagged**

Run: `python scripts/validate_doctrines.py 2>&1 | grep _playbooks`
Expected: empty

- [ ] **Step 4: Commit (if any change)**

```bash
git status -s
# if anything to commit:
git add -A doctrines/
git commit -m "doctrines: remove empty _playbooks/ directory"
```

---

## Task 21: Write `doctrines/SKILL.md`

**Files:**
- Create: `doctrines/SKILL.md`

- [ ] **Step 1: Write the SKILL.md**

```markdown
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

\`\`\`bash
ls doctrines/ | grep -v '\.md$'
\`\`\`

Each directory contains the persona's doctrine files. The directory name
*is* the persona_id; nothing else encodes it.
```

- [ ] **Step 2: Verify**

Run: `head -5 doctrines/SKILL.md`
Expected: the YAML frontmatter block with `name: doctrines` and the description.

- [ ] **Step 3: Commit**

```bash
git add doctrines/SKILL.md
git commit -m "doctrines: add SKILL.md wrapper for the library"
```

---

## Task 22: Update `doctrines/README.md`

**Files:**
- Modify: `doctrines/README.md` (full rewrite — current contents are outdated)

- [ ] **Step 1: Rewrite README.md**

```markdown
# Doctrines

Distilled doctrines of notable thinkers, each formatted as a three-layer
evaluation filter. Used by the eval pipeline (papers and HN domains) and
by the web-app taste-test agent.

## Layout

\`\`\`
doctrines/
├── README.md                       # this file
├── SKILL.md                        # frontmatter + how to use, for any LLM agent
└── <persona-id>/                   # kebab-case (e.g. peter-thiel, richard-hamming)
    ├── doctrine-light.md           # short AI-generated baseline (always present)
    └── doctrine-distilled.md       # canonical 3-layer doctrine (when available)
\`\`\`

## Two tiers per persona

| Tier | File | Origin | Use |
|---|---|---|---|
| **Light** | `doctrine-light.md` | AI-generated from the persona's public profile | Baseline; runs as `<id>-light` in the eval |
| **Distilled** | `doctrine-distilled.md` | Distilled from the persona's writings/talks | Stronger signal; runs as `<id>-distilled` in the eval |

Both tiers are valid personas. The eval compares them head-to-head — a key
question is: does the carefully distilled doctrine outperform the AI-generated
stub? Don't rewrite the light tier to be sharper; it's the experimental control.

## Canonical `doctrine-distilled.md` format

\`\`\`markdown
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

### Where the alpha is
- <persona's high-conviction current bets>

### Auto-reject
- <persona's structural disqualifiers today>
\`\`\`

## Adding a new persona

1. Create `doctrines/<kebab-case-id>/`.
2. Add `doctrine-light.md` (mandatory). Format:
   \`\`\`markdown
   # <Name> — Light Doctrine

   **Bio:** <one-paragraph bio>.

   **Priors:**
   - <prior 1>
   - <prior 2>
   - <prior 3>
   \`\`\`
3. Optionally add `doctrine-distilled.md` (canonical format above).
4. Run `python scripts/validate_doctrines.py` — must pass.
5. The eval runner picks it up automatically (no code changes needed).

## Validation

\`\`\`bash
python scripts/validate_doctrines.py
\`\`\`

Exits 0 on PASS. Run after any change to `doctrines/`.
```

- [ ] **Step 2: Verify**

Run: `head -20 doctrines/README.md`
Expected: the new content starting with "# Doctrines" header.

- [ ] **Step 3: Commit**

```bash
git add doctrines/README.md
git commit -m "doctrines: rewrite README for new layout and tier system"
```

---

## Task 23: Refactor `run_eval.py` — drop `DOCTRINE_MAP`, walk per-persona dirs

**Files:**
- Modify: `evals/papers/scripts/run_eval.py`

- [ ] **Step 1: Replace `load_personas()` and remove `DOCTRINE_MAP`**

Open `evals/papers/scripts/run_eval.py` and locate:
1. The `DOCTRINE_MAP = {...}` dict at lines 39-44.
2. The constant `DOCTRINES_DIR = PROJECT_ROOT / "doctrines" / "_playbooks"` at line 34.
3. The `load_personas()` function at lines 72-109.

Replace them with:

```python
# (line ~33) — keep PERSONAS_DIR, drop DOCTRINES_DIR
PERSONAS_DIR = PROJECT_ROOT / "doctrines"

# (delete DOCTRINE_MAP entirely — lines 39-44)


def load_personas() -> dict[str, dict]:
    """Load both light and distilled doctrines from per-persona dirs.

    For each `doctrines/<persona-id>/` directory:
      - if doctrine-light.md exists → emit `<persona-id>-light`
      - if doctrine-distilled.md exists → emit `<persona-id>-distilled`

    Each persona record:
      - persona_id: e.g. "peter-thiel-light"
      - name: H1 of the markdown file (display name)
      - tier: "light" | "distilled"
      - profile_text: full markdown file contents
    """
    out: dict[str, dict] = {}
    if not PERSONAS_DIR.exists():
        return out

    for pdir in sorted(PERSONAS_DIR.iterdir()):
        if not pdir.is_dir():
            continue
        if pdir.name.startswith("_") or pdir.name.startswith("."):
            continue

        for tier, filename in [("light", "doctrine-light.md"),
                               ("distilled", "doctrine-distilled.md")]:
            fpath = pdir / filename
            if not fpath.exists():
                continue
            text = fpath.read_text()
            # Display name: H1 of the file, stripping trailing " — Light Doctrine"
            # or "— Three Evaluation Layers" cruft to keep the leaderboard clean.
            first_line = text.splitlines()[0] if text else ""
            name = first_line.lstrip("# ").split("—")[0].strip() or pdir.name
            persona_key = f"{pdir.name}-{tier}"
            out[persona_key] = {
                "persona_id": persona_key,
                "name": f"{name} ({tier})",
                "tier": tier,
                "profile_text": text,
            }
    return out
```

- [ ] **Step 2: Update the prompt template to use the new `tier` field**

Locate the `PROMPT_INTRO` constant at lines 53-56 and the `make_judgment` function at lines 173-238.

Change `PROMPT_INTRO` from:

```python
PROMPT_INTRO = """You are channeling {name}'s taste to judge research papers. Use their priors and voice.

Their {profile_label}:
"""
```

to:

```python
PROMPT_INTRO = """You are channeling {name}'s taste to judge research papers. Use their priors and voice.

Their doctrine:
"""
```

In `make_judgment`, find the line:

```python
profile_label = "playbook" if profile["format"] == "markdown" else "stub profile"
cache_block_text = (
    PROMPT_INTRO.format(name=profile["name"], profile_label=profile_label)
    + profile["profile_text"]
)
```

Replace with:

```python
cache_block_text = (
    PROMPT_INTRO.format(name=profile["name"])
    + profile["profile_text"]
)
```

(The `profile_label` is no longer used because both tiers are markdown doctrines.)

- [ ] **Step 3: Verify the new `load_personas()` works**

Run from repo root:
```bash
python -c "
import sys
sys.path.insert(0, 'evals/papers/scripts')
from run_eval import load_personas
ps = load_personas()
print(f'Loaded {len(ps)} personas')
print('  light:', sum(1 for p in ps.values() if p['tier'] == 'light'))
print('  distilled:', sum(1 for p in ps.values() if p['tier'] == 'distilled'))
"
```
Expected: total ≥ 30 (~18 light + ~17 distilled). Light count = 18.

- [ ] **Step 4: Commit**

```bash
git add evals/papers/scripts/run_eval.py
git commit -m "evals: walk doctrines/<id>/ dirs; drop DOCTRINE_MAP; emit two tiers"
```

---

## Task 24: Final validation + smoke test

**Files:** none modified — verification only

- [ ] **Step 1: Run the validator**

Run: `python scripts/validate_doctrines.py`
Expected: `PASS — doctrines/ library is canonical` and exit code 0.

- [ ] **Step 2: Run the eval smoke test**

Run: `python evals/papers/scripts/run_eval.py --smoke`
Expected:
- Output begins with `Loaded N papers, M personas.` where M ≥ 30 (~36 if Munger has both tiers, ~35 if not).
- Smoke message: `smoke: personas=['<id>-light' or '<id>-distilled', ...] cross=3 same=1`.
- Tasks complete without errors (look for `errors=0` in progress output).
- Final lines: `Wrote evals/papers/results/eval_results.json` and `Wrote evals/papers/results/eval_pairs_log.json`.

- [ ] **Step 3: Spot-check the leaderboard**

Run: `python -c "import json; r = json.load(open('evals/papers/results/eval_results.json')); print(*[(x['persona_id'], x['score']) for x in r['leaderboard'][:5]], sep='\n')"`
Expected: 5 rows, each `(<id>-light or <id>-distilled, integer score)`.

- [ ] **Step 4: Spot-check that both tiers appear for at least one persona**

Run: `python -c "import json; r = json.load(open('evals/papers/results/eval_results.json')); ids = [x['persona_id'] for x in r['leaderboard']]; print('peter-thiel-light' in ids, 'peter-thiel-distilled' in ids)"`
Expected: `True True`

- [ ] **Step 5: Final commit summarizing the migration**

If results files were generated by the smoke test, do NOT commit them (they're transient). Confirm clean status:

```bash
git status -s
```

Expected: clean (or only the smoke-test result files in `evals/papers/results/` which we don't commit).

If anything is still dirty in `doctrines/` or `evals/`, stop and investigate. Otherwise the migration is complete.

---

## Self-review checklist

After implementation, run all four:

1. `python scripts/validate_doctrines.py` → PASS
2. `python evals/papers/scripts/run_eval.py --smoke` → completes with errors=0
3. `git log --oneline | head -25` → ~22-24 clean migration commits, each focused on one persona or one structural change
4. `find doctrines -name "*.json" -o -name "_playbooks" -type d` → empty (no leftovers)

If any fail, fix before claiming complete.
