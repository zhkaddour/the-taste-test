# Doctrines

Distilled "doctrines" of great problem-pickers. Each persona has a folder; the eval runner loads both the stub profile and (when present) the richer playbook.

## Structure

```
doctrines/
├── <persona_id>/
│   └── profile.json          # stub profile (always present)
└── _playbooks/               # richer "OurPlaybook" doctrines (4 so far)
    └── the-<name>-doctrine.md
```

## Current personas (15 stubs)

`balaji_srinivasan`, `charlie_munger`, `elon_musk`, `george_soros`, `howard_marks`, `jensen_huang`, `marc_andreessen`, `nassim_taleb`, `naval_ravikant`, `paul_graham`, `peter_thiel`, `ray_dalio`, `richard_hamming`, `sam_altman`, `warren_buffett`

## Richer playbooks (4)

- `the-andreessen-doctrine.md`
- `the-buffett-doctrine.md`
- `the-graham-doctrine.md`
- `the-thiel-doctrine.md`

The eval runner falls back to the stub profile when a richer doctrine isn't yet available, so adding a new playbook to `_playbooks/` automatically upgrades that persona.

## Adding a doctrine

1. Drop the markdown into `_playbooks/the-<name>-doctrine.md`.
2. Add an entry to `DOCTRINE_MAP` in `evals/papers/scripts/run_eval.py` mapping the filename to `(persona_id, display_name)`.
3. Run the eval and verify it loads both versions.
