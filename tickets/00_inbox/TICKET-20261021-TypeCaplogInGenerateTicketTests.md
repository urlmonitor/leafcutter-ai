---
title: "Type the caplog fixture in test_generate_ticket_from_ac.py so mypy stops flagging it"
status: done
components:
  - testing_quality
created: 2026-10-21
depends_on: []
priority: low
tags:
  - mypy
  - tests
files_touched:
  - unit_tests/test_generate_ticket_from_ac.py
change_target: code
risk_surface: internal
requires_diagram: false
requires_adr: false
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: not_needed
---

# Type the caplog fixture in test_generate_ticket_from_ac.py so mypy stops flagging it

## Actor / Goal
In order to keep the informational mypy CI check meaningful, we need the one older type
finding in the ticket-generator tests fixed, so that mypy only reports real problems.

## Context
CI's "Type-check changed files (mypy, informational)" job on PR #1245 (2026-10-15) reported:

- `unit_tests/test_generate_ticket_from_ac.py:1204: error: "object" has no attribute "at_level"  [attr-defined]`
- `unit_tests/test_generate_ticket_from_ac.py:1212: error: "object" has no attribute "records"  [attr-defined]`

The cause is the test's signature at about line 1176, which annotates `caplog: object`. The
lines predate EPIC-RightJobRightAgent (blame 8aeb37d42, 2026-07-07). The two findings that
epic did introduce were fixed under ACD-2500b-1-ii and ACD-2500c-2-ii in
EPIC-RightJobRightAgentFollowUps.

This is a plain ticket, not an AC, by user decision (2026-10-16): no single ticket-generator AC
honestly owns this test file. There is no behaviour change, so no new test is needed. The proof
is that mypy no longer reports the file.

## Acceptance Criteria
- [x] AC-1: `python -m mypy --ignore-missing-imports --explicit-package-bases --no-error-summary unit_tests/test_generate_ticket_from_ac.py` reports no `attr-defined` finding at the `caplog` uses.
- [x] AC-2: the test function's `caplog` parameter is annotated `pytest.LogCaptureFixture`, and the file's tests still pass with the same collected count.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | mypy run (CI informational job) | | |
| AC-2 | existing tests in the file | | |

## Sign-offs

- [x] python-coder — 2026-10-21 14:10
- [x] test-runner — 2026-10-21 14:10
- [x] pr-reviewer — 2026-10-21 14:10
- [x] commit — 2026-10-21 14:10

## Comments

### 2026-10-21 14:10 — python-coder (status: ok)
feedback-id: fb_2026-10-21_bc642697

`caplog` is annotated `pytest.LogCaptureFixture` (and `import pytest` is added). mypy with the CI flags reports nothing for the
file; the file's tests pass (87 passed, 1 xfailed). The file is far over its size limit (2,390 measured lines), so the two-line change
lands under the user-approved one-off check-file-size skip of the EPIC-RightJobRightAgentFollowUps commit. Review: trivial
annotation, checked by the main session.

## Implementation Tasks
- [x] Change `caplog: object` to `caplog: pytest.LogCaptureFixture` (import `pytest` if needed).
- [x] Run mypy on the file and the file's tests.

## Risk & Safety
- Touches money? No.
- Touches data? No. A test-only type annotation.
- Reversibility: trivial.
