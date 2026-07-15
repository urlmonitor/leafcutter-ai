---
title: "Add produces: frontmatter to agent templates (test_generate_ticket_from_ac)"
status: todo
components:
  - build_pipeline
created: 2026-07-15
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: config
risk_surface: internal
files_touched:
  - templates/agents/sql-view-creator.md
  - unit_tests/test_generate_ticket_from_ac.py
agents:
  test-writer: not_needed
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 03: Add produces: frontmatter to agent templates

## Actor / Goal

As a maintainer, I want every agent template to declare `produces:` in its YAML
frontmatter, so `test_generate_ticket_from_ac` (AC BO-510-2/4) goes green.

## Context

`unit_tests/test_generate_ticket_from_ac.py` has **1 failure** (masked to xfail on CI):
`test_bo510_2_all_agent_templates_have_produces_in_frontmatter` —
`AssertionError: ... templates missing 'produces:' ... ['sql-view-creator.md']`. The
`produces:` key is present in the body of `templates/agents/sql-view-creator.md` but not
in its YAML frontmatter, where the test (and the AC contract) requires it. Data/config
fix. (The `tests/ac_store/` duplicate copy of this test already passes.) Not owned
elsewhere.

## Acceptance Criteria

```gherkin
Given all agent templates under templates/agents/
When test_generate_ticket_from_ac checks each frontmatter for a produces: key
Then every template (incl. sql-view-creator.md) declares produces: in YAML frontmatter
  and the test passes with addopts="" AND under AC_ENFORCE_STRICT=1

Given the fix
Then produces: reflects the agent's ACTUAL output artifacts (not a placeholder added
  only to satisfy the check) — verify the value matches what the agent really produces
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | unit_tests/test_generate_ticket_from_ac.py | templates/agents/sql-view-creator.md | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Add a correct `produces:` block to `sql-view-creator.md`'s YAML frontmatter
      (mirror the body's declared outputs).
- [ ] Audit ALL `templates/agents/*.md` for the same gap (the test iterates over all);
      fix any others it flags.
- [ ] Confirm the test passes with `-o addopts=""` and `AC_ENFORCE_STRICT=1`.

## Risk & Safety
- Touches money? No.
- Touches data? Agent template frontmatter only.
- Reversibility? Fully reversible.
