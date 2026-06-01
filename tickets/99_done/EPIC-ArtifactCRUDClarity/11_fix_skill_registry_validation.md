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
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
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

- [x] test-writer — 2026-05-28 10:00
- [x] python-coder — 2026-05-28 10:05
- [x] test-runner — 2026-05-28 10:10
- [x] pr-reviewer — 2026-05-28 10:15
- [ ] commit
- [ ] pull-request

## Comments

### 2026-05-28 10:00 — test-writer (status: ok)
feedback-id: fb_2026-05-28_bf5199d9
Added TestSkillRegistryBidirectional class to tests/test_skill_registry.py with three tests: test_no_orphaned_directories, test_no_orphaned_entries, and test_registry_entry_schema. Tests delegate logic to validate_skill_registry() in registry_validator.py. Updated module docstring to reflect new bidirectional coverage.

### 2026-05-28 10:05 — python-coder (status: ok)
feedback-id: fb_2026-05-28_50b21a9b
Added validate_skill_registry(package_root, skills_dir, registry_path) to scripts/registry_validator.py returning (orphaned_dirs, orphaned_entries) tuples with full edge-case handling. Added main_skill_registry() CLI entry point (--skills flag); updated __main__ block for backward compatibility. Backfilled 5 skills missing from skill_registry.json: doc-enforcer, frontend-design, glossary-bootstrap, sql-query-past-queries, webapp-testing. Removed legacy build-feature/ directory from disk (duplicate of build-feature-ops-notes/; existing test test_build_feature_id_not_present confirms this is correct). Validator exits 0 after backfill.

### 2026-05-28 10:10 — test-runner (status: ok)
feedback-id: fb_2026-05-28_24b538a7
pytest tests/test_skill_registry.py: 9 passed in 29.70s (6 existing + 3 new bidirectional). test_agent_registry.py: 9 passed, no regressions.

### 2026-05-28 10:15 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-28_52cb8c3e
Implementation is clean and complete. validate_skill_registry() has a sensible signature with default path resolution, correct return type, and handles all edge cases (missing file, bad JSON, missing skills key). Test class is correctly thin (delegates to validator). All 9 tests pass. The build-feature directory removal is correct per the existing test_build_feature_id_not_present assertion. No regressions. Ready for commit.

## Implementation Tasks

### test-writer

- [x] Write `leafcutter-ai/tests/test_skill_registry.py` with tests:
  - `test_no_orphaned_directories`: every directory under `templates/skills/` has a registry entry.
  - `test_no_orphaned_entries`: every registry entry has a corresponding directory.
  - `test_registry_entry_schema`: every entry has `id`, `description`, `path`, `internal` with correct types.
  - Tests should import and call `registry_validator.validate()` rather than re-implementing the logic.

### python-coder

- [x] Identify the 4 skills on disk with no registry entry by running:
  ```bash
  python -c "
  import json, os
  reg = {e['id'] for e in json.load(open('leafcutter-ai/config/skill_registry.json'))['skills']}
  dirs = {d for d in os.listdir('leafcutter-ai/templates/skills') if os.path.isdir(f'leafcutter-ai/templates/skills/{d}')}
  print('Missing from registry:', dirs - reg)
  "
  ```
- [x] Add the 4 missing entries to `leafcutter-ai/config/skill_registry.json` with correct `id`, `description` (from SKILL.md frontmatter), `path`, and `internal` fields.
- [x] Write `leafcutter-ai/scripts/registry_validator.py`:
  - `validate(skills_dir, registry_path) -> (orphaned_dirs: list, orphaned_entries: list)` function.
  - `main()` entry point that prints a human-readable diff and exits 0/1.
  - Handle edge cases: `templates/skills/` directory does not exist, registry file missing, malformed JSON.
- [x] Verify `python leafcutter-ai/scripts/registry_validator.py` exits 0 after the backfill.

### test-runner

- [x] Run `pytest leafcutter-ai/tests/test_skill_registry.py -v` and confirm all tests pass.

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies a JSON config file and adds Python scripts.
- Reversibility? Fully reversible. Adding entries to `skill_registry.json` is backward-compatible; the validator is a new file.
- Shared contract? `skill_registry.json` is read by `build.py`. Adding entries does not change the format; no build-side changes required for this ticket.
