---
title: "python-coder template carries its durable implementation craft"
status: todo
components:
  - llm_authoring
  - python_coding
created: 2026-07-08
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: prompt
risk_surface: internal
test_constraints: unit_only
complexity: medium
ac_coverage: 0/7
files_touched:
  - templates/agents/python-coder.md
  - unit_tests/prompt_assembly/test_python_coder_template.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 02: python-coder template carries its durable implementation craft

## Actor / Goal

In order that the coder behaves correctly on every run regardless of what its
dispatch prompt says, the durable craft rules a defective invocation had to be
hand-told must live in the `python-coder.md` template itself (Channel 6).

## Context

**Implementation for this ticket is already complete** — `templates/agents/python-coder.md`
was edited in the prompt-assembly-hardening session to add: the fail-open pre-commit
hook error carve-out (log to stderr + return 0, never re-raise; `print(stderr)`, no
unused logger); path-context awareness (`templates/` is source, `scripts/` and
`.claude/` are gitignored build outputs); the rule that new hooks/agents/skills route
through `create-hook`/`add-agent-to-package`/`add-skill-to-package` rather than being
hand-rolled; read-before-Edit; the real-artifact behavioral spot-check and phantom-test
prohibition; and the single-simple-command shell discipline.

This ticket **adds the test coverage** pinning those rules. It is a slice of
[EPIC-PromptAssemblyHardening](./Master_Plan.md).

## AC References

Implements L1 **BO-2000b** ("python-coder carries its own implementation craft in its
template") and its leaves: BO-2000b-1, BO-2000b-1-i, BO-2000b-2, BO-2000b-3, BO-2000b-4,
BO-2000b-5, BO-2000b-6. Canonical source: the BO-2000 AC folder.

## Acceptance Criteria

- [ ] AC-1 (BO-2000b-1 / -1-i): the template states pre-commit hooks fail open on unexpected errors — log to stderr and return 0, never re-raise; and to use `print(stderr)` without an unused module logger.
- [ ] AC-2 (BO-2000b-2): the template states `templates/` is the source and `scripts/`/`.claude/` are generated build outputs never used as a reference.
- [ ] AC-3 (BO-2000b-3): the template requires routing new hooks/agents/skills through their dedicated skills instead of hand-rolling registration.
- [ ] AC-4 (BO-2000b-4): the template states the read-before-Edit rule.
- [ ] AC-5 (BO-2000b-5): the template requires a real-artifact behavioral spot-check and prohibits phantom tests.
- [ ] AC-6 (BO-2000b-6): the template restates the single-simple-command shell discipline.

## Test Requirements

```yaml
tests:
  - name: test_python_coder_hook_failopen_carveout
    file: unit_tests/prompt_assembly/test_python_coder_template.py
    covers: [BO-2000b-1, BO-2000b-1-i]
    asserts: "template contains the fail-open hook carve-out (return 0, never re-raise) and the print(stderr)/no-unused-logger guidance."
  - name: test_python_coder_path_awareness_and_delegation
    file: unit_tests/prompt_assembly/test_python_coder_template.py
    covers: [BO-2000b-2, BO-2000b-3]
    asserts: "template states templates/ vs generated scripts/.claude, and the create-hook/add-agent/add-skill delegation rule."
  - name: test_python_coder_read_before_edit_and_shell
    file: unit_tests/prompt_assembly/test_python_coder_template.py
    covers: [BO-2000b-4, BO-2000b-6]
    asserts: "template states read-before-Edit and single-simple-command shell discipline."
  - name: test_python_coder_realartifact_and_phantom
    file: unit_tests/prompt_assembly/test_python_coder_template.py
    covers: [BO-2000b-5]
    asserts: "template requires a real-artifact spot-check and prohibits phantom tests."
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | done | |
| AC-2 | | done | |
| AC-3 | | done | |
| AC-4 | | done | |
| AC-5 | | done | |
| AC-6 | | done | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

### test-writer
- [ ] Write the four tests above; they read `templates/agents/python-coder.md` and assert the required content. Expect GREEN on first run (implementation already landed); a red test means the template edit regressed.

## Risk & Safety

- Touches money? No.
- Touches data? No — reads a template file; adds a unit test.
- Reversibility? Fully reversible via git.
