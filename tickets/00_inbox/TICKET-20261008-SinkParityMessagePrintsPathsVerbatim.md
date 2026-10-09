---
title: "Sink-parity check prints the paths it compares exactly as they are, so Windows paths are not escaped"
status: todo
components:
  - infrastructure
created: 2026-10-08
depends_on: []
priority: low
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
roadmap_phase: phase_1
advances_current_outcome: false
tags:
  - windows
  - portability
  - error-message
  - knowledge-sink
last_updated: 2026-10-08
files_touched:
  - scripts/ci/check_sink_parity.py
  - tests/knowledge/test_inf_400c_4.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Sink-parity check prints the paths it compares exactly as they are, so Windows paths are not escaped

## Actor / Goal
In order that a reader of a sink-parity failure can copy either path out of the message and use
it, we need `check_sink_parity.py` to print paths verbatim instead of as Python string literals.
Then on Windows the message shows `C:\Users\...` and not `C:\\Users\\...`, and the INF-400c-4
proof passes there as it does on Linux.

## Context
- **Failing test (Windows only):**
  `tests/knowledge/test_inf_400c_4.py::test_parity_check_blocks_when_the_two_sides_resolve_to_different_paths`.
- **Reproduced on main `6ccbd14ea`, 2026-10-08, Windows 11.** The check blocks correctly and names
  `it-po`, but the assertion `declared_sink in combined` (:111) fails. The output reads
  `... while the install's declared sink is 'C:\\Users\\Hendrik\\AppData\\Local\\Temp\\pytest-of-Hendrik\\...\\knowledge_emissions.jsonl'`.
  Every backslash is doubled.
- **Root cause (verified):** `scripts/ci/check_sink_parity.py` formats paths with `!r` (`repr`).
  The places are :268, :274-275, :284-287, :369-370 and :378. `repr` of a Windows path escapes
  each backslash, so the printed text is not the path. On Linux, paths contain no backslashes, so
  `repr` only adds quotes and the test passes. The test asserts what the AC wants: both
  resolved values, readable. The defect is in the message, not the test.
- AC: INF-400c-4 (done). Its failure message must name both resolved values and which side
  produced each.

## Acceptance Criteria
- [ ] AC-1: Every path `check_sink_parity.py` prints in a finding (the declared sink, the
  resolved destination, the self-carried literal, the operational stream) appears exactly as the
  path's own text, optionally inside plain quotes, with no escape sequences added.
- [ ] AC-2: A test feeds a declared sink whose path holds a backslash and a space. It asserts that
  the failure output contains that path verbatim, and it passes on Linux and Windows.
- [ ] AC-3: `test_parity_check_blocks_when_the_two_sides_resolve_to_different_paths` passes on
  Windows unchanged, and the other `test_inf_400c_4.py` tests still pass on both platforms.

## Test Requirements

```yaml
tests:
  - name: test_parity_failure_prints_paths_verbatim
    location: tests/knowledge/test_inf_400c_4.py
    type: integration
    covers: [AC-1, AC-2]
    description: |
      Declared sink path containing a backslash and a space; run check_sink_parity as a
      subprocess against a disagreeing surface and assert the exact path text appears in the
      output. Red today on every platform, because repr doubles the backslash.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_parity_failure_prints_paths_verbatim | | |
| AC-2 | test_parity_failure_prints_paths_verbatim | | |
| AC-3 | test_parity_check_blocks_when_the_two_sides_resolve_to_different_paths (Windows run) | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [ ] Replace the `!r` path renderings with one small helper that quotes without escaping, and
  use it at every site listed above.
- [ ] Add the test; run `tests/knowledge/test_inf_400c_4.py` on Windows and Linux.

## Risk & Safety
- Touches money? No.
- Touches data? No; message text only. Exit codes are unchanged.
- Reversibility: revert the commit.
