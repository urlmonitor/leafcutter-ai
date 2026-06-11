---
title: "Fix 14 consolidation-residue test failures (path and schema mismatches)"
status: todo
components:
  - commit_guardian
  - build_pipeline
  - skills_system
created: 2026-06-11
depends_on: []
priority: high
source_ac: ACD-1100
requires_diagram: false
requires_adr: false
roadmap_phase: phase_1
advances_current_outcome: true
files_touched:
  - unit_tests/test_check_description_field.py
  - unit_tests/commit_guardian/test_check_ac_limits.py
  - unit_tests/test_build_workflow_output_paths.py
  - config/skill_registry.schema.json
  - config/skill_registry.json
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

# 02: Fix 14 consolidation-residue test failures (path and schema mismatches)

## Actor / Goal

In order to restore a green test suite after the EPIC-AcPipelineConsolidation merge, we need to correct 14 test failures caused by path and schema mismatches left as residue from the consolidation restructuring.

## Context

The EPIC-AcPipelineConsolidation moved script files from `scripts/` to `templates/scripts/`, updated build output directories, and added new fields to skill registry schemas. Five groups of tests did not get updated correspondingly:

1. **`unit_tests/test_check_description_field.py` lines 23-28** — 4 tests reference `scripts/` paths that should be `templates/scripts/` after the consolidation move.
2. **`unit_tests/commit_guardian/test_check_ac_limits.py` lines 31, 696** — 7 tests reference `scripts/` paths that should be `templates/scripts/`.
3. **`unit_tests/test_build_workflow_output_paths.py`** — 1 test expects an output directory that moved during `build_phases.py` refactor at line 353.
4. **`config/skill_registry.schema.json`** — missing `invocation_surface` and `workflow_script` property definitions causes 1 schema validation failure.
5. **`config/skill_registry.json`** — 3 orphaned skill directories (`ac-scanner`, `build-ac`, `quick-fix`) exist on disk but have no corresponding registry entries, causing 1 orphan-detection failure.

Total: 14 failures. All 14 must go green without changing the behavior under test.

## Acceptance Criteria

- [ ] AC-1: Running `pytest unit_tests/test_check_description_field.py` exits 0 with all 4 previously-failing tests passing; no new tests are added or removed.
- [ ] AC-2: Running `pytest unit_tests/commit_guardian/test_check_ac_limits.py` exits 0 with all 7 previously-failing tests passing; path references updated to `templates/scripts/`.
- [ ] AC-3: Running `pytest unit_tests/test_build_workflow_output_paths.py` exits 0 with the 1 previously-failing output-dir test passing; expected dir matches `build_phases.py` line 353 actual output.
- [ ] AC-4: `config/skill_registry.schema.json` is updated to include `invocation_surface` and `workflow_script` as optional property definitions; schema validation test passes.
- [ ] AC-5: `config/skill_registry.json` contains valid entries for `ac-scanner`, `build-ac`, and `quick-fix` skill directories; orphan-detection test passes.
- [ ] AC-6: Full test suite (`pytest`) exits 0 — no previously-passing tests regress.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | pytest test_check_description_field.py | fix path refs in test file | |
| AC-2 | pytest test_check_ac_limits.py | fix path refs in test file | |
| AC-3 | pytest test_build_workflow_output_paths.py | fix expected dir in test | |
| AC-4 | schema validation test | add fields to schema.json | |
| AC-5 | orphan-detection test | add entries to skill_registry.json | |
| AC-6 | full pytest run | no behavior changes | |

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Read `unit_tests/test_check_description_field.py` lines 23-28; update `scripts/` path assertions to `templates/scripts/`.
- [ ] Read `unit_tests/commit_guardian/test_check_ac_limits.py` lines 31, 696; update `scripts/` path assertions to `templates/scripts/`.
- [ ] Read `unit_tests/test_build_workflow_output_paths.py`; compare expected output dir with `build_phases.py` line 353 actual output; align the test expectation.
- [ ] Read `config/skill_registry.schema.json`; add `invocation_surface` (string, optional) and `workflow_script` (string, optional) to the schema properties.
- [ ] Read `config/skill_registry.json`; check the three skill directories (`templates/skills/ac-scanner/`, `templates/skills/build-ac/`, `templates/skills/quick-fix/`) for their SKILL.md metadata; add corresponding registry entries.
- [ ] Run `pytest` to verify all 14 failures are resolved and no regressions introduced.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? All changes are test file and config file edits; fully reversible.
- Risk: Adding skill registry entries for orphaned directories — verify the skill directories actually exist and have valid SKILL.md before adding entries. If a skill directory is itself stale and should be deleted instead, surface that to the user rather than adding a registry entry for a ghost.
