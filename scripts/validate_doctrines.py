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
