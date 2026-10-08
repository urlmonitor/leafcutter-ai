---
title: "Red-baseline gate tests: the nested pytest run stays inside its fixture folder"
status: todo
components:
  - testing_quality
  - build_orchestration
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
  - flaky
  - red-baseline
last_updated: 2026-10-07
files_touched:
  - unit_tests/build_orchestration/_tq500f3i_fixtures.py
  - unit_tests/workflows/_tq500f3ii_fixtures.py
  - unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
  - unit_tests/workflows/test_tq500f3ii_heavy_lane_red_baseline_gate.py
  - unit_tests/build_orchestration/test_tq500f3ii_nested_rootdir.py  # new
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

# Red-baseline gate tests: the nested pytest run stays inside its fixture folder

## Actor / Goal
In order that the red-baseline gate tests give a real verdict on every run, we need the nested pytest
they start to treat the test's own fixture folder as its root. Then pytest never lists the shared temp
folder, where other processes create and delete directories.

## Context
- **Symptom.** The red-baseline gate tests run a nested pytest. Some runs come back ERROR with
  `pytest run unfinished: N file(s), returncode 2`. Affected: `unit_tests/build_orchestration/test_tq500f3ii_*`
  and `unit_tests/workflows/test_tq500f3ii_*`.
- **How the tests run it.** They build a worktree fixture under `tempfile.TemporaryDirectory()`, a
  direct child of `%TEMP%`. Examples: `test_tq500f3ii_heavy_lane_gate_subcommand.py:94`, :125, :160,
  :190, and `test_tq500f3ii_heavy_lane_red_baseline_gate.py:210`. They start the gate as a subprocess
  with no `cwd`, so it inherits the test process's cwd, the repository root (`_run_heavy_lane_gate`,
  `test_tq500f3ii_heavy_lane_gate_subcommand.py:60-72`).
- **How the reader runs pytest.** `_run_pytest_and_parse_with_kind`
  (`scripts/ac_store/done_proof_kind_support.py:304-337`) starts the nested pytest with no `cwd` and
  no `--rootdir`.
- **Root cause.** No ini file lies above the fixture's test file. pytest then takes the common
  ancestor of the invocation folder and the test file as its rootdir. With the repository under
  `C:\Users\Hendrik\Code` and the fixture under `%TEMP%`, that is `C:\Users\Hendrik`. Collection then
  lists every folder on the path from there to the test, `%TEMP%` included. Other processes create
  and delete folders in `%TEMP%` (for example `bo3000c-*`). An entry that vanishes between listing and
  stat raises FileNotFoundError, pytest exits 2, and the reader reports the run as unfinished
  (`done_proof_kind_support.py:346-350`).
- **Measured 2026-10-07.** `python -m pytest --co <%TEMP%\...\work\unit_tests\test_x.py>`:
  - from the repository root: `rootdir: C:\Users\Hendrik`, 8.9 s for one test;
  - from the fixture folder: `rootdir: <fixture folder>`, 0.01 s.
- **Workaround that worked locally.** Pointing TEMP/TMP at a private folder and passing `--rootdir`.
- **Production is not affected.** There the test files live in the repository, whose `pytest.ini`
  fixes the rootdir.
- **Analogous code.** `done_proof._run_pytest_and_parse` (`scripts/ac_store/done_proof.py:1382-1391`)
  already anchors `cwd` with `_resolve_pytest_run_cwd` (`scripts/ac_store/_done_proof_phase_helpers.py:246`);
  the kind-support runner does not. Anchoring `cwd` in production once made the `pytest.ini` addopts
  plugin unimportable (`done_proof.py` DECISION HISTORY, 2026-09-28, PR #925).
- **Decision: fix it in the tests' fixtures, not in the reader.** The reader is right for the repo
  layout it serves, and changing it risks that regression. The fixture can start the gate with
  `cwd` set to the fixture root, or put a minimal `pytest.ini` there; either makes the fixture root
  the rootdir.

## Acceptance Criteria
- [ ] AC-1: Every nested pytest run started by the affected tests has its rootdir inside that test's own fixture folder.
- [ ] AC-2: While a helper thread creates and deletes folders in the shared temp folder for the whole run, the affected gate tests give a real verdict, never `pytest run unfinished`, in 3 consecutive runs.
- [ ] AC-3: No production file changes: `done_proof_kind_support.py`, `done_proof.py` and `scripts/build_orchestration/` stay as they are.
- [ ] AC-4: The affected tests' assertions are unchanged, and they pass on Windows and on Linux.

## Test Requirements

```yaml
tests:
  - name: test_gate_nested_pytest_rootdir_is_the_fixture_folder
    location: unit_tests/build_orchestration/test_tq500f3ii_nested_rootdir.py
    type: integration
    covers: [AC-1]
    description: |
      Build the fixture the way the affected tests do, then run `python -m pytest --co` over its
      test file from the same cwd the fixture gives the gate. The header's rootdir line names a
      folder inside the fixture. Red today: rootdir is the common ancestor of the repository and
      the temp folder (the user's home folder on this machine).
  - name: test_gate_verdict_survives_temp_folder_churn
    location: unit_tests/build_orchestration/test_tq500f3ii_nested_rootdir.py
    type: integration
    covers: [AC-2]
    description: |
      Start a thread that creates and deletes folders in tempfile.gettempdir() until stopped, run
      the real heavy_lane_gate over a fixture 3 times, and assert no verdict carries "pytest run
      unfinished". A stress guard: it may pass at base by luck, so it is not part of the red
      baseline; the rootdir test above is.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_gate_nested_pytest_rootdir_is_the_fixture_folder | | |
| AC-2 | test_gate_verdict_survives_temp_folder_churn | | |
| AC-3 | (diff) | | |
| AC-4 | (existing tests) | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

### test-writer
- [ ] Write `unit_tests/build_orchestration/test_tq500f3ii_nested_rootdir.py`.

### python-coder
- [ ] In the shared fixture modules (`unit_tests/build_orchestration/_tq500f3i_fixtures.py`,
  `unit_tests/workflows/_tq500f3ii_fixtures.py`), give every gate subprocess `cwd` = the fixture root,
  or write a minimal `pytest.ini` into the fixture root. Route the tests' direct `subprocess.run`
  calls (e.g. `_run_heavy_lane_gate`) through it.
- [ ] Keep each touched file within its size limit. `test_tq500f3ii_heavy_lane_red_baseline_gate.py`
  measures 346 of 400 (411 raw), so it has little headroom.

### test-runner / pr-reviewer / commit
- [ ] Run every `test_tq500f3ii_*` file in both folders, on Windows.

## Risk & Safety
- Touches money? No.
- Touches data? No; test fixtures only.
- Reversibility: revert the commit.

## Out of Scope
- Changing the reader's `cwd` or `--rootdir` in production (see the decision in Context).
- Other tests that run a nested pytest over a temp folder. The same root cause applies to them; list
  any found.
