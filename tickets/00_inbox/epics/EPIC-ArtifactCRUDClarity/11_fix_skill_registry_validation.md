---
title: "Fix: Bidirectional skill registry validation"
status: todo
components:
  - build_pipeline
  - config_loader
created: 2026-05-28
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/scripts/registry_validator.py
  - leafcutter-ai/config/skill_registry.json
  - leafcutter-ai/tests/test_skill_registry.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 11: Fix: Bidirectional skill registry validation

## Actor / Goal

In order to prevent future registry drift, we need a validator that catches mismatches between `templates/skills/` directories and `skill_registry.json` entries in both directions, and we need to fix the 4 currently missing entries so that the registry is immediately accurate.

## Context

The audit found:
- 4 skills are present as directories under `leafcutter-ai/templates/skills/` but have no entry in `leafcutter-ai/config/skill_registry.json`.
- `add-skill-to-package` does not update the registry (fixed in ticket 09) — this is the root cause of drift.
- No automated check currently catches this class of problem.

The fix has two parts:
1. **Backfill**: identify the 4 missing skills and add their entries to `skill_registry.json`.
2. **Validator**: write `registry_validator.py` that checks bidirectionally — every directory in `templates/skills/` must have a registry entry, and every registry entry must have a corresponding directory.

The validator should be runnable standalone (`python registry_validator.py`) and also importable as a module so it can be called from tests and potentially from `build.py`.

## Acceptance Criteria

```gherkin
Given registry_validator.py exists
When it is run against the current state of templates/skills/ and skill_registry.json
Then it exits 0 if there are no mismatches, or exits 1 and prints a diff listing orphaned directories and orphaned registry entries

Given the 4 missing skill entries are added to skill_registry.json
When registry_validator.py is run
Then it exits 0 with no mismatches reported

Given test_skill_registry.py exists
When pytest runs it
Then it passes for the corrected state and fails if a mismatch is introduced

Given registry_validator.py is run before build.py in CI
When a developer adds a skill directory without updating the registry
Then CI fails with a clear message identifying the missing registry entry
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### test-writer

- [ ] Write `leafcutter-ai/tests/test_skill_registry.py` with tests:
  - `test_no_orphaned_directories`: every directory under `templates/skills/` has a registry entry.
  - `test_no_orphaned_entries`: every registry entry has a corresponding directory.
  - `test_registry_entry_schema`: every entry has `id`, `description`, `path`, `internal` with correct types.
  - Tests should import and call `registry_validator.validate()` rather than re-implementing the logic.

### python-coder

- [ ] Identify the 4 skills on disk with no registry entry by running:
  ```bash
  python -c "
  import json, os
  reg = {e['id'] for e in json.load(open('leafcutter-ai/config/skill_registry.json'))['skills']}
  dirs = {d for d in os.listdir('leafcutter-ai/templates/skills') if os.path.isdir(f'leafcutter-ai/templates/skills/{d}')}
  print('Missing from registry:', dirs - reg)
  "
  ```
- [ ] Add the 4 missing entries to `leafcutter-ai/config/skill_registry.json` with correct `id`, `description` (from SKILL.md frontmatter), `path`, and `internal` fields.
- [ ] Write `leafcutter-ai/scripts/registry_validator.py`:
  - `validate(skills_dir, registry_path) -> (orphaned_dirs: list, orphaned_entries: list)` function.
  - `main()` entry point that prints a human-readable diff and exits 0/1.
  - Handle edge cases: `templates/skills/` directory does not exist, registry file missing, malformed JSON.
- [ ] Verify `python leafcutter-ai/scripts/registry_validator.py` exits 0 after the backfill.

### test-runner

- [ ] Run `pytest leafcutter-ai/tests/test_skill_registry.py -v` and confirm all tests pass.

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies a JSON config file and adds Python scripts.
- Reversibility? Fully reversible. Adding entries to `skill_registry.json` is backward-compatible; the validator is a new file.
- Shared contract? `skill_registry.json` is read by `build.py`. Adding entries does not change the format; no build-side changes required for this ticket.
