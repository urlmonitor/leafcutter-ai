---
title: "Add TDD success gate to python-coder and sql-coder: make red-baseline green, no contract shrinking"
status: todo
components:
  - build_pipeline
created: 2026-05-26
depends_on:
  - 02_test_writer_rewrite.md
priority: high
requires_diagram: false
requires_adr: false
agents:
  architect-review: needed
  python-coder: needed
  test-writer: not_needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 03: Add TDD success gate to python-coder and sql-coder: make red-baseline green, no contract shrinking

## Goal

In order to close the TDD loop, we need `python-coder` and `sql-coder` to treat the `red_baseline` block from `test-writer`'s sign-off comment as their explicit success target, and to include an explicit contract-shrinking prohibition (honor-system layer) in both agent definitions.

## Context

After ticket 02, `test-writer` captures a `red_baseline` block listing the exact failing tests and their errors. The coders must:

1. **Read the red_baseline** from `test-writer`'s last `## Comments` entry before writing any production code.
2. **Success gate**: "All tests named in `red_baseline` must be green; no test that was passing before test-writer ran may now be red."
3. **Contract-shrinking prohibition** (honor-system layer): explicit clause in the agent definitions stating:
   > "You MUST NOT delete, comment out, add `pytest.skip`, `pytest.mark.xfail`, `@unittest.skip`, or any equivalent skip/xfail marker to any test in order to make the suite pass. Weakening the test suite to achieve a green run is a critical violation. If a test in red_baseline cannot be made to pass with correct implementation, append a `(status: blocker)` comment explaining the conflict and halt."

SQL TDD scope note: this epic covers Python only. The `sql-coder` definition gets the contract-shrinking prohibition and the red_baseline reading instruction, but the sql-coder's red_baseline comes from `sql-test-writer` (separate agent, separate flow). The test-FIRST ordering for SQL is deferred to the follow-on SQL TDD epic (ticket 08). For this ticket, only update the `python-coder` and `sql-coder` text; do not change sql-coder's priority or ordering.

A how-to doc explaining the rationale ("Writing a TDD ticket") is authored in ticket 07. This ticket adds the agent-level honor-system clause; the doc provides the fuller explanation.

Files to update:
- `leafcutter-ai/templates/agents/python-coder.md` (source)
- `.claude/agents/python-coder.md` (deployed)
- `leafcutter-ai/templates/agents/sql-coder.md` (source)
- `.claude/agents/sql-coder.md` (deployed)

## Acceptance Criteria

```gherkin
Given python-coder is spawned after test-writer has run
When python-coder reads the ticket
Then it locates the red_baseline block in test-writer's sign-off comment
And it uses those test names as its completion criterion

Given python-coder has written production code
When it runs the test suite
Then all tests in red_baseline are green
And no previously-passing test is now red
And python-coder's sign-off comment documents which red_baseline tests it turned green

Given a situation where making red_baseline tests pass would require deleting or skipping a test
When python-coder encounters this
Then it appends "(status: blocker)" with a description of the conflict
And it does NOT delete, skip, or xfail any test

Given sql-coder is read
When the agent definition is inspected
Then it contains the same contract-shrinking prohibition clause as python-coder
```

## Sign-offs

- [ ] architect-review
- [ ] python-coder
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### architect-review
- [ ] Review the exact wording of the contract-shrinking prohibition clause — confirm it covers all known skip/xfail mechanisms (pytest.skip, pytest.mark.xfail, unittest.skip, marking with `if False:`, deleting the test function, renaming to not match `test_*`)
- [ ] Confirm the red_baseline reading instruction is compatible with how ticket-supervisor passes context to phase agents (the comment history is passed via the ticket file, which the agent re-reads)

### python-coder
- [ ] Update `leafcutter-ai/templates/agents/python-coder.md`:
  - [ ] Add "Pre-flight: read red_baseline from test-writer's sign-off comment" as step 0 of the implementation sequence
  - [ ] Add the success gate clause: "Your done criterion is: every test in red_baseline is green AND no previously-passing test is red"
  - [ ] Add the contract-shrinking prohibition clause (verbatim from Context above)
  - [ ] Add the blocker path: "If you cannot make a red_baseline test pass with correct code, append (status: blocker) — do NOT weaken the test"
- [ ] Apply identical changes to `.claude/agents/python-coder.md` (deployed copy)
- [ ] Update `leafcutter-ai/templates/agents/sql-coder.md`:
  - [ ] Add the contract-shrinking prohibition clause
  - [ ] Add a note: "SQL TDD ordering (test-first for SQL) is deferred to EPIC-SQLTDDEnforcement; for now, ensure you never weaken existing SQL tests"
- [ ] Apply identical changes to `.claude/agents/sql-coder.md` (deployed copy)

### documentation-expert
- [ ] Verify that the new clauses added to python-coder and sql-coder agent definitions are consistent with any existing documentation in `docs/` that describes agent behavior (especially `docs/agents/` if it exists)
- [ ] Flag any doc that contradicts the new success gate language for update in ticket 07

## Risk & Safety

- Touches money? No.
- Touches data? No — agent definition markdown files only.
- Reversibility? Fully reversible: revert the agent templates and deployed copies.
- Risk: The honor-system layer has no enforcement at the agent level beyond the text instruction. The pre-commit hook (ticket 04) and supervisor check (ticket 05) provide the mechanical enforcement layers.
