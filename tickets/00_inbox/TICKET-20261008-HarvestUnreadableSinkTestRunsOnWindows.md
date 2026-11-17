---
title: "Harvest-learnings test makes its unreadable sink unreadable on Windows too"
status: todo
components:
  - infrastructure
created: 2026-10-08
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
  - portability
  - harvest-learnings
last_updated: 2026-10-08
files_touched:
  - tests/knowledge/test_harvest_learnings_inf400c4iv.py
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Harvest-learnings test makes its unreadable sink unreadable on Windows too

## Actor / Goal
In order that the INF-400c-4-iv proof gives the same verdict on a Windows checkout as on CI, we
need the test's "sink that exists but cannot be read" to be unreadable on every platform. Then a
local red means the harvester regressed, not that the fixture failed to set up.

## Context
- **Failing test (Windows only):**
  `tests/knowledge/test_harvest_learnings_inf400c4iv.py::TestASinkThatExistsButCannotBeReadKeepsItsDistinctNonzeroStatus::test_a_sink_that_exists_but_cannot_be_read_keeps_its_distinct_nonzero_status`.
- **Reproduced on main `6ccbd14ea`, 2026-10-08, Windows 11:**
  `AssertionError: 0 == 0 : a sink that EXISTS but cannot be read must keep a status distinct from the absent-sink no-work status; unreadable stdout='0 learnings routed: none; 0 outstanding; 1 record(s) missing a required digest field at line(s) [1]\n'`.
  The harvester READ the "unreadable" file and processed its one record.
- **Root cause (verified):** the fixture makes the sink unreadable with
  `unreadable_sink.chmod(0o000)` (:333). On Windows, `os.chmod` only toggles the read-only
  attribute. It cannot remove read access, so the file stays readable. A one-line probe on this
  host: after `chmod(0o000)`, `read_text()` returned the content. The test's premise holds only
  on POSIX, and even there not for a root user.
- **The production code is fine.** `scripts/knowledge/harvest_learnings.py:570-578` checks
  `sink_path.exists()`, then reads. Any `OSError` on read logs "Cannot read sink file" and exits 1,
  which is the behaviour the test protects. That code path runs on Windows too, so a platform
  skip is not justified. The rule recorded in TICKET-20261006-CiShardsInstallWebToolchain
  (Design Decisions) permits a skip only where the code under test cannot run at all.
- **A portable unreadable sink (verified on this host):** a directory at the sink path. It
  `exists()`, and `read_text()` raises `PermissionError` on Windows and `IsADirectoryError` on
  POSIX, both `OSError`. Another option is a file held under an exclusive lock, which is
  platform-specific. The coder chooses; the AC fixes the outcome.
- **Agents.** The change is to the test fixture itself, and the existing test is already red on
  Windows, so `python-coder` edits it and `test-writer` is not needed.

## Acceptance Criteria
- [ ] AC-1: The test makes the sink unreadable by a means under which reading it raises
  `OSError` on Windows and on Linux, for root and non-root users alike. It passes on both
  platforms without a skip.
- [ ] AC-2: The test still fails if `harvest_learnings.py` treats an unreadable sink like an
  absent one. Check by temporarily replacing the `sys.exit(1)` at :578 with the no-work path: the
  test goes red. Record that run in the sign-off.
- [ ] AC-3: The test's other assertions (exit 1 keeps its number; exits 2, 3 and 4 keep their
  meanings) are unchanged and pass.

## Test Requirements

```yaml
tests:
  - name: test_a_sink_that_exists_but_cannot_be_read_keeps_its_distinct_nonzero_status
    location: tests/knowledge/test_harvest_learnings_inf400c4iv.py
    type: integration
    covers: [AC-1, AC-2, AC-3]
    description: |
      Existing test; replace the chmod(0o000) fixture with a portable unreadable sink. Red on
      Windows today, for the fixture reason above.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_a_sink_that_exists_but_cannot_be_read_keeps_its_distinct_nonzero_status (Windows and Linux runs) | | |
| AC-2 | mutation run described in AC-2 | | |
| AC-3 | same test | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [ ] Replace the fixture at :330-340 and drop the `chmod` restore.
- [ ] Run the test on Windows and Linux, plus the AC-2 mutation run.

## Risk & Safety
- Touches money? No.
- Touches data? No; a test fixture only.
- Reversibility: revert the commit.
