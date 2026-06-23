---
title: "Register create-ac skill in skill_registry.json (orphaned directory)"
status: todo
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
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
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

- [ ] AC-1: `config/skill_registry.json` contains a `create-ac` entry whose fields match the schema enforced by `tests/test_skill_registry_schema.py` (mirror a sibling entry such as `plan-feature` for required keys and value shapes).
- [ ] AC-2: `tests/test_skill_registry.py::TestSkillRegistryBidirectional::test_no_orphaned_directories` passes (no orphaned directories).
- [ ] AC-3: `tests/test_skill_registry_schema.py` continues to pass for the new entry.
- [ ] AC-4: The full `tests/` suite shows no net-new regressions versus the pre-change baseline.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_skill_registry_schema.py | config/skill_registry.json | |
| AC-2 | test_skill_registry.py::test_no_orphaned_directories | config/skill_registry.json | |
| AC-3 | test_skill_registry_schema.py | config/skill_registry.json | |
| AC-4 | full tests/ suite | — | |

## Sign-offs

- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-22 — BrainCandy (status: ok)
feedback-id: none
Created from the 2026-06-22 full-suite triage. Only untracked genuine-bug
failure; all other clusters already have inbox tickets. Likely a one-line
registry addition plus schema-conformant fields.

## Implementation Tasks

- [ ] Read an existing `config/skill_registry.json` entry (e.g. `plan-feature` or `build-ac`) to determine the required field set.
- [ ] Add a `create-ac` entry whose `description`/path/metadata mirror the skill's `SKILL.md` frontmatter.
- [ ] Run `python -m pytest tests/test_skill_registry.py tests/test_skill_registry_schema.py -v` and confirm green.
- [ ] Run the full `tests/` suite and confirm no net-new regressions.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Additive single-entry JSON change; trivially revertible.
