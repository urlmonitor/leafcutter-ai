---
title: "Extend emit_entry.py with breaking + migration_steps fields"
status: todo
components:
  - documentation_system
  - infrastructure
created: 2026-05-19
last_updated: 2026-05-19
depends_on: []
priority: high
phase: "Phase 1"
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter/scripts/changelog/emit_entry.py
  - leafcutter/templates/agents/changelog-agent.md
agents:
  architect-review: not_needed
  python-coder: needed
  test-writer: needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
  sql-coder: not_needed
---

# 01: Extend emit_entry.py with breaking + migration_steps fields

## Goal

In order to enable automated SemVer bump decisions, we need per-file changelog entries to carry a `breaking` flag and a `migration_steps` list so that the release script can determine the correct bump level without human judgement.

## Context

`emit_entry.py` (`leafcutter/scripts/changelog/emit_entry.py`) is the single write path for all changelog entries. It currently enforces the required fields (`title`, `date`, `time`, `type`, `components`, `summary`, `description`) and two conditional requirements (`epic` when `type=epic_completion`, `ticket` when `type=ticket_completion`). See the DECISION HISTORY section in that file for the full evolution.

The `breaking` and `migration_steps` fields are **optional at the payload level** (authors who do not introduce a breaking change simply omit them), but carry a cross-validation constraint: if `breaking: true` is present, `migration_steps` must be a non-empty list.

Cross-links:
- `leafcutter/scripts/changelog/emit_entry.py` — the file being extended.
- `leafcutter/templates/agents/changelog-agent.md` — the agent that drives changelog generation (Call site 1); its Step 7 payload construction section must document the new fields.
- Sub-ticket 02 (`02_release_script.md`) — depends on this ticket: the release script reads `breaking` from entries produced by the updated `emit_entry.py`.

No changelog skill template directory exists at `leafcutter/templates/skills/changelog/` — the changelog-agent template is a flat file at `leafcutter/templates/agents/changelog-agent.md`.

## Acceptance Criteria

```gherkin
Given emit_entry.py receives a payload with breaking=true and migration_steps=["Run alembic upgrade head"]
When emit_entry is called
Then it writes the entry file with breaking: true and migration_steps containing the step

Given emit_entry.py receives a payload with breaking=true and migration_steps=[]
When emit_entry is called
Then it raises ValueError with a message referencing migration_steps

Given emit_entry.py receives a payload with breaking=true and no migration_steps key
When emit_entry is called
Then it raises ValueError with a message referencing migration_steps

Given emit_entry.py receives a payload with breaking=false and no migration_steps
When emit_entry is called
Then it writes the entry file normally (no error)

Given emit_entry.py receives a payload with no breaking field at all
When emit_entry is called
Then it writes the entry file normally (breaking defaults to false; no error)
```

## Sign-offs

- [ ] python-coder
- [ ] test-writer
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Add `breaking` (optional bool) and `migration_steps` (optional list[str]) to `validate_payload()` in `emit_entry.py`
  - When `breaking=True` and `migration_steps` is absent or empty → raise `ValueError("Field 'migration_steps' must be a non-empty list when breaking=True")`
  - When `breaking=False` or `breaking` absent → no `migration_steps` requirement
- [ ] Add `"breaking"` and `"migration_steps"` to `optional_order` in `build_frontmatter()` so they are serialised in a stable position (after the existing optional fields)
- [ ] Update `_yaml_value()` if needed — bool already handled; list of strings already handled
- [ ] Update `changelog-agent.md` Step 7 payload construction section to document the two new optional fields with their semantics and the cross-validation rule
- [ ] Add unit tests in `leafcutter/tests/test_emit_entry.py` (or equivalent) covering all 5 Gherkin scenarios above
- [ ] Add a DECISION HISTORY entry to `emit_entry.py` documenting this change

## Risk & Safety

- Touches money? No.
- Touches data? `emit_entry.py` writes changelog entry files. Adding new optional fields is backwards-compatible — existing call sites that do not supply `breaking` or `migration_steps` continue to work without modification.
- Reversibility? Fully reversible — the new fields are optional on the payload; no existing entries are mutated.
