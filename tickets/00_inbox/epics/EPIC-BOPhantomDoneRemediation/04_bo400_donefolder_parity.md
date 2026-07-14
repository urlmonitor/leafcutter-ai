---
title: "Done-folder parity: detect staged path moves (not presence); catch 99_done; un-mask tests"
status: todo
components:
  - build_orchestration
created: 2026-07-14
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
source_ac: BO-400c-3
ac_coverage:
  - BO-400c-3
  - BO-400c-3-i
  - BO-400c-3-ii
files_touched:
  - templates/scripts/commit_guardian/_signoff_parity_checks.py
  - scripts/ac_store/pytest_ac_enforcement.py
  - unit_tests/commit_guardian/test_check_ticket_signoff_parity_done_folder.py
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

# 04: Done-folder parity detects moves, not presence

## Actor / Goal

As the commit guardian, I want the done-folder parity check to detect a *staged
path change* into a done/ location (and catch `tickets/99_done/`), so BO-400c-3
is enforced correctly and its tests actually run.

## Remediation Context (audit 2026-07-14)

**Phantom-done + masked tests.** `_check_done_folder_prohibition` is
**presence-based** (fires on any `/done/` path) rather than detecting a staged
path *change*, so it over-fires on in-place edits (c-3-i false positive) and
misses `tickets/99_done/` (`/done/` substring never matches `/99_done/`, c-3-ii).
Worse, its tests are silently converted to **XFAIL** by
`scripts/ac_store/pytest_ac_enforcement.py` and import from
`leafcutter-ai/scripts/commit_guardian/` where the module isn't deployed — so
**no assertion ever runs**. (These 3 tests are RED in a plain pytest run.)

**Do:** compare staged file *paths* (old→new) to detect a move into done/; add
the `99_done` case + the finalize env-flag carve-out; fix the wrong import path;
remove the XFAIL masking so the tests assert for real.

## Acceptance Criteria

Resolves BO-400c-3, BO-400c-3-i, BO-400c-3-ii (verbatim Gherkin under
`.../BO-400-ticket-status-source-of-truth/`).

## Test Requirements

```yaml
tests:
  - name: test_done_folder_move_blocked
    file: unit_tests/commit_guardian/test_check_ticket_signoff_parity_done_folder.py
    covers: [BO-400c-3]
    asserts: a staged move of a ticket into a done/ path is blocked (real assertion, not xfail).
  - name: test_in_place_done_edit_not_blocked
    file: unit_tests/commit_guardian/test_check_ticket_signoff_parity_done_folder.py
    covers: [BO-400c-3-i]
    asserts: editing a file already at a done/ path is NOT blocked (no false positive).
  - name: test_99_done_move_caught
    file: unit_tests/commit_guardian/test_check_ticket_signoff_parity_done_folder.py
    covers: [BO-400c-3-ii]
    asserts: a move into tickets/99_done/ is caught; the finalize carve-out is honoured.
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
