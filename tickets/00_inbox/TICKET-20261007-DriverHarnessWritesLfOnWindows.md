---
title: "Driver test harness writes ticket records with LF line endings on Windows"
status: todo
components:
  - testing_quality
created: 2026-10-07
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
roadmap_phase: phase_1
advances_current_outcome: false
tags:
  - testing
  - windows
  - line-endings
  - test-harness
last_updated: 2026-10-07
files_touched:
  - unit_tests/prompt_assembly/_driver_harness.py
  - unit_tests/prompt_assembly/test_driver_harness_writes_lf.py  # new
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  llm-expert: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
---

# Driver test harness writes ticket records with LF line endings on Windows

## Actor / Goal
In order that the build-driver tests give the same verdict on a Windows checkout as in CI, we need
the test harness to write its ticket records with LF line endings. Then the `.mjs` harness can read
the frontmatter back, and a local test run shows real failures only.

## Context
- **Cause.** `write_ticket_record` (`unit_tests/prompt_assembly/_driver_harness.py:94-196`) writes
  the record with `open(path, "w", encoding="utf-8")` (:194). In text mode on Windows, every `"\n"`
  becomes `"\r\n"`.
- **Where it breaks.** The `.mjs` harness reads the record back with LF-only regexes, in
  `unit_tests/prompt_assembly/harness_build_ticket_guard.mjs`:
  - `text.match(/^---\n([\s\S]*?)\n---/)` (:258) finds the frontmatter;
  - then `/^status:\s*(\S+)\s*$/m` (:261) and `/^agents:[ \t]*\n/m` (:276) read it.
  On a CRLF file the first match fails, so the driver sees no status and no agents map.
- **Effect.** Every completion-dependent driver test fails locally on Windows, even at base: about 100
  tests. CI on Linux is unaffected.
- **Confirmed.** A local-only pytest plugin that forces LF writes (scratchpad `lfopen.py`) makes them
  pass.
- The Python reader `read_record` (:199-206) opens in text mode, which folds CRLF back to LF, so the
  Python side never showed the problem.
- 64 test modules import `_driver_harness`.
- **Size.** `_driver_harness.py` has 702 raw lines; check-file-size measures 542 of them against the
  400-line limit (2026-10-07), so it is over and the ratchet applies. A changed line counts as an
  added line, so the file must end at least one measured line shorter for a one-line change.
- **Note for the coder.** Write `newline="\n"` as the two characters backslash and n, not as a real
  line break inside the string. Run `ast.parse` on the edited file before committing.

## Acceptance Criteria
- [ ] AC-1: A record written by `write_ticket_record` contains no `\r` byte, on Windows and on Linux.
- [ ] AC-2: The `.mjs` harness reads `status` and the `agents` map from a record that `write_ticket_record` wrote on Windows. This is a real round trip through `run_driver`.
- [ ] AC-3: On Windows, `unit_tests/prompt_assembly/` passes without an LF-forcing plugin, apart from failures that also occur on Linux CI.
- [ ] AC-4: Every other file `_driver_harness.py` writes for a `.mjs` reader is written with LF too. The scenario JSON at :280 does not depend on line endings.

## Test Requirements

```yaml
tests:
  - name: test_ticket_record_has_no_carriage_return
    location: unit_tests/prompt_assembly/test_driver_harness_writes_lf.py
    type: unit
    covers: [AC-1]
    description: |
      Write a record with write_ticket_record and read its bytes. No b"\r". Red on Windows today;
      honestly green on Linux, which writes LF already.
  - name: test_mjs_harness_reads_status_and_agents_from_written_record
    location: unit_tests/prompt_assembly/test_driver_harness_writes_lf.py
    type: integration
    covers: [AC-2]
    description: |
      Write a record with status todo and one needed phase, run the real driver through run_driver
      with a minimal scenario, and assert that the drive dispatches that phase. Today, on Windows,
      it reports that it sees no agents map.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_ticket_record_has_no_carriage_return | | |
| AC-2 | test_mjs_harness_reads_status_and_agents_from_written_record | | |
| AC-3 | (local run of unit_tests/prompt_assembly/ on Windows) | | |
| AC-4 | (review of the harness's write sites) | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

### test-writer
- [ ] Write `unit_tests/prompt_assembly/test_driver_harness_writes_lf.py`.

### python-coder
- [ ] `_driver_harness.py:194`: open with `newline="\n"`. Shorten the file by at least one line.
- [ ] Check every other write in the file (AC-4).

### test-runner / pr-reviewer / commit
- [ ] Run `unit_tests/prompt_assembly/` on Windows without the LF plugin and report what still fails.

## Risk & Safety
- Touches money? No.
- Touches data? No; a test helper only.
- Reversibility: revert the commit.

## Out of Scope
- Making the `.mjs` regexes accept CRLF. Records written by the real tools are LF.
- Other test helpers that write in text mode.
