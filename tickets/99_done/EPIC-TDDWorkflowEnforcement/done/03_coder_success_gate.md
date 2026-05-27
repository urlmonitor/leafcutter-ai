---
title: "Add TDD success gate to python-coder and sql-coder: make red-baseline green, no contract shrinking"
status: done
components:
  - build_pipeline
created: 2026-05-26
depends_on:
  - 02_test_writer_rewrite.md
priority: high
requires_diagram: false
requires_adr: false
agents:
  architect-review: signed_off
  python-coder: signed_off
  test-writer: not_needed
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
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

- [x] architect-review — 2026-05-27 01:40
- [x] python-coder — 2026-05-27 01:45
- [x] documentation-expert — 2026-05-27 01:46
- [x] pr-reviewer — 2026-05-27 01:47
- [x] commit — 2026-05-27 01:48
- [x] pull-request — 2026-05-27 01:49

## Comments

### 2026-05-27 01:40 — architect-review (status: ok)
feedback-id: fb_2026-05-27_03_arch
Contract-shrinking prohibition wording confirmed complete: covers pytest.skip, pytest.mark.xfail, @unittest.skip, @unittest.expectedFailure, if False: wrappers, deleting test functions, and any equivalent mechanism. Note: renaming to not match test_* is not explicitly listed in the wording (ticket 04 hook does not detect renames — a known gap, not in this epic's scope). red_baseline reading instruction is compatible with how ticket-supervisor passes context: agents re-read the full ticket file including ## Comments history, so the red_baseline block in the test-writer comment is visible. No ADR required.

### 2026-05-27 01:45 — python-coder (status: ok)
feedback-id: fb_2026-05-27_03_coder
Updated templates/agents/python-coder.md: added "TDD Red-Baseline Success Gate" section with Step 0 pre-flight (read red_baseline from test-writer comment), success criterion, contract-shrinking prohibition clause with exact forbidden mechanisms, blocker path if test cannot be made green, and sign-off documentation of red_baseline results. Updated Implementation Sequence from 7-step to 8-step with Step 1 = read red_baseline. Applied identical changes to .claude/worktrees/.claude/agents/python-coder.md. Updated templates/agents/sql-coder.md: added "TDD Red-Baseline Contract (SQL)" section with red_baseline reading instruction, success criterion, contract-shrinking prohibition, SQL TDD ordering deferral note (EPIC-SQLTDDEnforcement). Applied identical changes to .claude/worktrees/.claude/agents/sql-coder.md.

### 2026-05-27 01:46 — documentation-expert (status: ok)
feedback-id: fb_2026-05-27_03_docs
Reviewed docs/ for any existing documentation describing python-coder or sql-coder behavior. No contradictions found with the new success gate language — the existing docs/agents/ directory does not exist in this repo; no standalone python-coder or sql-coder documentation files found that would conflict. The new clauses are consistent with the existing Test Delegation section in python-coder.md (which explicitly states not to modify unit test files, consistent with the contract-shrinking prohibition). Flagged for ticket 07: the how-to doc "writing-a-tdd-ticket.md" should cross-reference the red_baseline schema and the contract-shrinking prohibition.

### 2026-05-27 01:47 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-27_03_pr
All four acceptance criteria verified: (1) python-coder locates red_baseline from test-writer comment — Step 0 pre-flight confirmed. (2) All red_baseline tests green + no regressions — success criterion confirmed, sign-off documents results. (3) Blocker path for test-cannot-pass scenario — (status: blocker) path confirmed, no delete/skip/xfail. (4) sql-coder contains same prohibition clause — confirmed in TDD Red-Baseline Contract section. Approve for commit.

### 2026-05-27 01:48 — commit (status: ok)
feedback-id: fb_2026-05-27_03_commit
Committed: feat(tdd): add TDD success gate to python-coder and sql-coder.

### 2026-05-27 01:49 — pull-request (status: ok)
feedback-id: fb_2026-05-27_03_pr_push
Branch pushed to origin. PR deferred until all epic tickets complete (one PR per epic convention).

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
