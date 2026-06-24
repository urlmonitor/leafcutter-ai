---
title: "Register create-ac skill in skill_registry.json (orphaned directory)"
status: in_progress
components:
  - skill_registry
  - testing_quality
created: 2026-06-22
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
tags:
  - test-debt
  - registry-drift
files_touched:
  - config/skill_registry.json
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# Register create-ac skill in skill_registry.json (orphaned directory)

## Actor / Goal

In order to keep the skill registry an accurate source of truth and the test
suite green as a regression gate, we need `templates/skills/create-ac/` to have
a matching `config/skill_registry.json` entry, so that the bidirectional
registry invariant holds.

## Context

Discovered during a full-suite test run on 2026-06-22 (branch
`fix/GE-112-ac-schema-fallback`, which is `origin/main` + the GE-112 commit;
this failure is pre-existing on `origin/main` and unrelated to GE-112).

`tests/test_skill_registry.py::TestSkillRegistryBidirectional::test_no_orphaned_directories`
fails:

```
AssertionError: Lists differ: ['create-ac'] != []
Skill directories exist on disk with no matching skill_registry.json entry.
Add entries for: ['create-ac']
```

The `create-ac` skill directory exists at
[templates/skills/create-ac/SKILL.md](templates/skills/create-ac/SKILL.md) and
deploys correctly via `build.py` (confirmed in build output), but it was never
registered in [config/skill_registry.json](config/skill_registry.json)
(confirmed: `grep create-ac config/skill_registry.json` returns nothing). The
skill is functional and user-invocable via `/create-ac`; only the registry entry
is missing. This is registry drift — a skill added without the registration step.

This is the only one of the genuine-bug test failures from the 2026-06-22 triage
that was not already tracked by an existing ticket. The other clusters are
covered by `TICKET-20260617-TrackMissingTransformHookScripts.md`,
`TICKET-20260617-TrackKnowledgeGraphApiMismatch.md`,
`TICKET-20260617-TrackACTreeTraversalTDDStubs.md`,
`TICKET-20260622-StaleTestEpicFolderConflict.md`, and the umbrella
`TICKET-20260617-Fix_Pre_Existing_Test_Failures.md`.

## Acceptance Criteria

- [x] AC-1: `config/skill_registry.json` contains a `create-ac` entry whose fields match the schema enforced by `tests/test_skill_registry_schema.py` (mirror a sibling entry such as `plan-feature` for required keys and value shapes).
- [x] AC-2: `tests/test_skill_registry.py::TestSkillRegistryBidirectional::test_no_orphaned_directories` passes (no orphaned directories).
- [x] AC-3: `tests/test_skill_registry_schema.py` continues to pass for the new entry.
- [x] AC-4: The full `tests/` suite shows no net-new regressions versus the pre-change baseline.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_skill_registry_schema.py | create-ac entry already present in config/skill_registry.json with all required fields (id, name, portable, domain, template_path, dependencies, description) | |
| AC-2 | test_skill_registry.py::test_no_orphaned_directories | Verified: test passes, no orphaned directories | |
| AC-3 | test_skill_registry_schema.py | All 6 schema tests pass including the new create-ac entry | |
| AC-4 | full tests/ suite | 524 passed, 4 skipped; 9 pre-existing failures (diagram_type_validators / GE-103) unchanged from baseline | |

## Sign-offs

- [x] python-coder — 2026-06-24 00:00
- [x] test-runner — 2026-06-24 11:30
- [x] pr-reviewer — 2026-06-24 12:00
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-22 — BrainCandy (status: ok)
feedback-id: none
Created from the 2026-06-22 full-suite triage. Only untracked genuine-bug
failure; all other clusters already have inbox tickets. Likely a one-line
registry addition plus schema-conformant fields.

### 2026-06-24 00:00 — python-coder (status: ok)
feedback-id: fb_2026-06-24_796bcc2e
completion_manifest:
  AC-1_entry_present_with_schema_fields: true
  AC-2_test_no_orphaned_directories_passes: true
  AC-3_schema_tests_all_pass: true
  AC-4_no_net_new_regressions: true
The create-ac entry was already present in config/skill_registry.json on this branch with all required schema fields (id, name, portable, domain, template_path, dependencies, description). Ran targeted tests: 16/16 passed. Full suite: 524 passed, 4 skipped, 9 pre-existing failures (all in commit_guardian/diagram_type_validators, tracked as GE-103) — no net-new regressions introduced. No file edits were needed; only ticket sign-off and coverage-table updates were written.

### 2026-06-24 12:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-24_be79cd28
completion_manifest:
  AC-1_entry_schema_valid: true
  AC-2_test_no_orphaned_directories_passes: true
  AC-3_schema_tests_pass: true
  AC-4_no_net_new_regressions: true
  diff_clean_no_unintended_changes: true
Reviewed the working diff and config/skill_registry.json. The diff is limited to ticket file updates (status/agent sign-off state, AC checkboxes, AC coverage table, comments). The create-ac entry in config/skill_registry.json is present and schema-valid with all required fields (id, name, portable, domain, template_path, dependencies, description) matching the sibling pattern of build-ac and plan-feature. All 4 ACs are satisfied per python-coder and test-runner sign-offs (524 passed, 9 pre-existing failures unchanged, test_no_orphaned_directories green). No high-confidence issues found.

## Implementation Tasks

- [x] Read an existing `config/skill_registry.json` entry (e.g. `plan-feature` or `build-ac`) to determine the required field set.
- [x] Add a `create-ac` entry whose `description`/path/metadata mirror the skill's `SKILL.md` frontmatter.
- [x] Run `python -m pytest tests/test_skill_registry.py tests/test_skill_registry_schema.py -v` and confirm green.
- [x] Run the full `tests/` suite and confirm no net-new regressions.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Additive single-entry JSON change; trivially revertible.
