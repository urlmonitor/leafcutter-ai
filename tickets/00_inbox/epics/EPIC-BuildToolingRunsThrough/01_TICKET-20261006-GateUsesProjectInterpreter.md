---
title: "The red-baseline gate runs under the project's interpreter in both lanes"
status: todo
components:
  - build_orchestration
  - testing_quality
created: 2026-10-06
depends_on: []
priority: high
complexity: medium
roadmap_phase: phase_1
advances_current_outcome: true
source_ac: TQ-500f-3-ii
ac_traceability:
  id: TQ-500f-3-ii
  path: docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-3-ii.yaml
requires_diagram: false
requires_adr: false
change_target:
  - pipeline
  - code
risk_surface: contract_boundary
files_touched:
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - scripts/build_orchestration/fast_lane.py
  - scripts/build_orchestration/_fl_red_baseline_support.py
  - unit_tests/workflows/test_tq500f3ii_heavy_lane_red_baseline_gate.py
  - unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
  - unit_tests/workflows/test_tq500f3ii_gate_driver_contract.py  # new
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  llm-expert: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: not_needed
  status-checker: not_needed
---

# 01: The red-baseline gate runs under the project's interpreter in both lanes

## Actor / Goal

As the build driver, I want to launch the red-baseline gate with the project's
interpreter (`python`) in both lanes, and to say so when that interpreter cannot run
pytest. Then the gate judges the new tests in the environment they were written for. A
Windows venv run will no longer fail every test as `no_red_outcome_among_new_tests`
with the real cause hidden.

## Context

Part of EPIC-BuildToolingRunsThrough (design section 3). This is one of the defects
behind the roughly 10 runs that DK-400 E1 ticket 01 needed.

**Root cause**
- `templates/workflows-js/build-feature.js:2115` and `templates/workflows-js/build-ticket.js:1751` launch the gate as `python3 ${gateScript} heavy_lane_gate ...`.
- pytest then runs as `sys.executable -m pytest` (`scripts/ac_store/done_proof.py:1382`, `scripts/ac_store/done_proof_kind_support.py:304`), so the interpreter that launches the gate decides which environment the tests see.
- A Windows venv has `python.exe` but no `python3.exe`, so `python3` resolves to the Windows Store 3.11. Every test ERRORs, and `verify_red_baseline` reports `no_red_outcome_among_new_tests` (`scripts/build_orchestration/fast_lane.py:403-410`), which hides the cause.
- `python` is already the project's interpreter convention:
  - `build-feature.js` uses it for `worktree_repo_facts.py` (1624-1639);
  - every hook in `templates/settings.json:37-74` uses it;
  - if `python` were wrong, every hook would already be broken.
- The fast lane uses `python3 ${gateScript}` at `templates/workflows-js/fast-lane-ship.js` lines 865, 958, 1073, 1202, 1304, 1308, 1626 and 1759.
- TQ-500f-3-ii (amended on this branch) requires that both lanes start the reader with the same command form.

**Fix**
- Use `python` for every `fast_lane.py` gate invocation in both lanes, in the same commit.
- Every `verify_red_baseline` verdict carries `interpreter: sys.executable`.
- Before running tests, `verify_red_baseline` (the shared reader) checks `importlib.util.find_spec("pytest")`. If pytest cannot be imported, it returns `gate_passed: false, reason: "test_interpreter_unusable"`.
- The JS halt message prints the interpreter from the verdict.
- Leave `set_ticket_status.py` alone (`build-feature.js:1311`, `build-ticket.js:1157`); it uses only the standard library.

## Constraints

- **Twins.** `build-feature.js` and `build-ticket.js` change together, in the same commit. The tests run against both through `_driver_harness.TWIN_DRIVERS`.
- **File-size ratchet (GE-127b-1, GE-127f-2).** Measured length / limit at bc8e6c62:
  - `build-feature.js` 2964 / 1000;
  - `build-ticket.js` 1647 / 1000;
  - `fast-lane-ship.js` 1673 / 1000.

  For a file already over its limit, the staged file may measure at most `previous − gross measured lines added`. A changed line, such as `python3` → `python`, counts as added. So each JS file must end at least as many lines shorter as the lines this ticket changes in it: remove an equal number of further measured lines (`//` comments count; `/* */` content does not). Net-zero is refused.
- **Python size.** `fast_lane.py` measures 387 / 400; crossing 400 is refused. Put the `find_spec` check and the `interpreter` key in `_fl_red_baseline_support.py` (305 / 400), and keep `fast_lane.py` to a call.
- **Echo, don't compute, in JS.** The halt message should echo `gateVerdict.interpreter` within the existing message line. Add no new JS lines.
- **Build mirrors.** After the template edits, run `python scripts/build.py` and stage every tracked output it changes.
- **Lane parity (TQ-500f-3-ii).** The heavy lane and the fast lane must keep giving an identical reader verdict and use the same command form.

## Acceptance Criteria

- [ ] AC-1: The `heavy_lane_gate` command in `build-feature.js` and `build-ticket.js`, and every `${gateScript}` (`fast_lane.py`) command in `fast-lane-ship.js`, starts with the interpreter token `python`. No `fast_lane.py` invocation in the three workflows starts with `python3`.
- [ ] AC-2: The heavy lane's gate command (both twins) and the fast lane's `verify_red_baseline` command start with the same interpreter token.
- [ ] AC-3: `verify_red_baseline` checks `importlib.util.find_spec("pytest")` before it runs any test. When pytest cannot be imported, it returns `gate_passed: false` with `reason: "test_interpreter_unusable"` and starts no pytest process.
- [ ] AC-4: Every verdict `verify_red_baseline` returns, and therefore every `heavy_lane_gate` verdict, carries `interpreter` equal to the running `sys.executable`.
- [ ] AC-5: When the gate fails a ticket, both twins' halt message names the interpreter and the reason from the verdict, and the coder is not dispatched.
- [ ] AC-6: The `set_ticket_status.py` invocations and the `python3` uses in `fast-lane-ship.js` that do not run `fast_lane.py` are unchanged.

## Test Requirements

```yaml
tests:
  - name: test_heavy_and_fast_lane_gate_commands_share_the_python_token
    file: unit_tests/workflows/test_tq500f3ii_gate_driver_contract.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      For build-feature.js and build-ticket.js (via _driver_harness.TWIN_DRIVERS),
      the captured red-baseline-gate command, and the verify_red_baseline command
      captured from a fast-lane-ship.js run, each start with the token "python"
      (not "python3"), and all three tokens are identical.
    framework: pytest
    type: integration
    angle: seam
  - name: test_fast_lane_ship_never_launches_fast_lane_py_with_python3
    file: unit_tests/workflows/test_tq500f3ii_gate_driver_contract.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      In a fast-lane-ship.js harness run that reaches the red-baseline step,
      every recorded command line that invokes fast_lane.py (including
      verify_red_baseline and verify_green_and_coverage) starts with "python ",
      and none starts with "python3".
    framework: pytest
    type: integration
    angle: criterion
  - name: test_gate_halt_message_names_interpreter_and_reason
    file: unit_tests/workflows/test_tq500f3ii_gate_driver_contract.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      For both twins, when the stubbed gate verdict is gate_passed false with
      reason test_interpreter_unusable and interpreter "/x/venv/python", the
      ticket halts before python-coder is dispatched, and the halt message
      contains both "/x/venv/python" and "test_interpreter_unusable".
    framework: pytest
    type: integration
    angle: failure
  - name: test_verify_red_baseline_refuses_when_pytest_not_importable
    file: unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      With importlib.util.find_spec patched to return None for "pytest",
      verify_red_baseline returns gate_passed false, reason
      "test_interpreter_unusable" and interpreter equal to sys.executable, and
      the pytest-running helper is never called.
    framework: pytest
    type: unit
    angle: failure
  - name: test_real_gate_verdict_carries_launching_interpreter
    file: unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      Running "<sys.executable> fast_lane.py heavy_lane_gate" as a real
      subprocess against the _tq500f3i_fixtures git fixture returns a JSON
      verdict whose "interpreter" key equals that sys.executable.
    framework: pytest
    type: integration
    angle: real_artifact
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_heavy_and_fast_lane_gate_commands_share_the_python_token, test_fast_lane_ship_never_launches_fast_lane_py_with_python3 | | |
| AC-2 | test_heavy_and_fast_lane_gate_commands_share_the_python_token | | |
| AC-3 | test_verify_red_baseline_refuses_when_pytest_not_importable | | |
| AC-4 | test_real_gate_verdict_carries_launching_interpreter | | |
| AC-5 | test_gate_halt_message_names_interpreter_and_reason | | |
| AC-6 | test_fast_lane_ship_never_launches_fast_lane_py_with_python3 (only fast_lane.py lines change) | | |

## Implementation Tasks

### test-writer
- [ ] Create `unit_tests/workflows/test_tq500f3ii_gate_driver_contract.py` with the three driver-side tests. Ticket 03 adds to this file, so name it for the gate's driver contract rather than the interpreter alone.
- [ ] Add the two reader tests to `test_tq500f3ii_heavy_lane_gate_subcommand.py`, using the real git fixture `unit_tests/build_orchestration/_tq500f3i_fixtures.py`.
- [ ] In `test_tq500f3ii_heavy_lane_red_baseline_gate.py`, make `_run` (line 285) replace a leading `python3?` token with `sys.executable`, not only `python3`. Keep the file at or below its current measured length (346 / 400). `_GATE_INVOCATION_RE` in `unit_tests/workflows/_tq500f3ii_fixtures.py:74` already accepts `python3?`.
- [ ] Grep `unit_tests/` for literal `python3 ${gateScript}` pins that would now fail. Docstring mentions are fine.

### python-coder
- [ ] `_fl_red_baseline_support.py`: add the `find_spec("pytest")` precheck and the `interpreter` key, used by `verify_red_baseline` in `fast_lane.py`.
- [ ] `build-feature.js:2115` and `build-ticket.js:1751`: `python3` → `python`. In the halt message (2136-2140 / 1772-1776), echo `gateVerdict.interpreter`. Pay back every changed line under the ratchet rule.
- [ ] `fast-lane-ship.js`: `python3 ${gateScript}` → `python ${gateScript}` at 865, 958, 1073, 1202, 1304, 1308, 1626 and 1759. Pay back the changed lines.
- [ ] Run `python scripts/build.py` and stage the tracked outputs it changes.

### test-runner / pr-reviewer / commit
- [ ] Run the TQ-500f-3-ii suites (`unit_tests/workflows/test_tq500f3ii_*`, `unit_tests/build_orchestration/test_tq500f3ii_*`) and the fast-lane workflow tests.
- [ ] pr-reviewer: confirm the twin parity, that no non-gate `python3` changed, and that check-file-size passes.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- On Linux with no venv, `python` may not exist. The hooks already require it, so this adds no new requirement. Note it in the changelog entry.
- Reversibility: revert the commit.

## Out of Scope

- A configurable `{{config.python_command}}` key. It would also have to cover the hooks, so it needs a separate ticket.
- `python3` uses that do not launch `fast_lane.py`: `setup_ticket_worktree.py`, the bundle script, `emit_entry.py`, `harvest_learnings.py` and `set_ticket_status.py`.
- Recording and reusing the gate's pass (ticket 03).

## Comments

_(Append-only log — leave blank when authoring.)_
