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
  test-writer: signed_off
  python-coder: signed_off
  llm-expert: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
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
- [x] Create `unit_tests/workflows/test_tq500f3ii_gate_driver_contract.py` with the three driver-side tests. Ticket 03 adds to this file, so name it for the gate's driver contract rather than the interpreter alone.
- [x] Add the two reader tests to `test_tq500f3ii_heavy_lane_gate_subcommand.py`, using the real git fixture `unit_tests/build_orchestration/_tq500f3i_fixtures.py`.
- [x] In `test_tq500f3ii_heavy_lane_red_baseline_gate.py`, make `_run` (line 285) replace a leading `python3?` token with `sys.executable`, not only `python3`. Keep the file at or below its current measured length (346 / 400). `_GATE_INVOCATION_RE` in `unit_tests/workflows/_tq500f3ii_fixtures.py:74` already accepts `python3?`.
- [x] Grep `unit_tests/` for literal `python3 ${gateScript}` pins that would now fail. Docstring mentions are fine.

### python-coder
- [x] `_fl_red_baseline_support.py`: add the `find_spec("pytest")` precheck and the `interpreter` key, used by `verify_red_baseline` in `fast_lane.py`.
- [x] `build-feature.js:2115` and `build-ticket.js:1751`: `python3` → `python`. In the halt message (2136-2140 / 1772-1776), echo `gateVerdict.interpreter`. Pay back every changed line under the ratchet rule.
- [x] `fast-lane-ship.js`: `python3 ${gateScript}` → `python ${gateScript}` at 865, 958, 1073, 1202, 1304, 1308, 1626 and 1759. Pay back the changed lines.
- [x] Run `python scripts/build.py` and stage the tracked outputs it changes.

### test-runner / pr-reviewer / commit
- [x] Run the TQ-500f-3-ii suites (`unit_tests/workflows/test_tq500f3ii_*`, `unit_tests/build_orchestration/test_tq500f3ii_*`) and the fast-lane workflow tests.
- [x] pr-reviewer: confirm the twin parity, that no non-gate `python3` changed, and that check-file-size passes.

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

### 2026-10-06 15:40 — test-writer (status: ok)
feedback-id: (submit-failed)

Wrote the 5 tests from `## Test Requirements`: 3 in the new
`unit_tests/workflows/test_tq500f3ii_gate_driver_contract.py` (driven through the real twin drivers via
`_driver_harness.TWIN_DRIVERS` and the real `fast-lane-ship.js`, asserting on recorded dispatches) and 2 appended to
`unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py` (227 lines, under the limit; the reader test
patches `importlib.util.find_spec` and the pytest runners on the real git fixture, the other runs the real
`fast_lane.py heavy_lane_gate` CLI). Also changed `_run` in `test_tq500f3ii_heavy_lane_red_baseline_gate.py` to swap a leading
`python`/`python3` token for `sys.executable` (same line count, 346 measured). No literal `python3 ${gateScript}` pins exist in
`unit_tests/` (only docstring mentions). Note: AC TQ-500f-3-ii is not `done`, so plain pytest masks these as xfail; verified
red with `AC_ENFORCE_STRICT=1` (5 failed, 4 existing passed).
Rule 3 seam: covered (producing: JS drivers' dispatched gate command; consuming: real `fast_lane.py` verdict / halt message).

reachability_entry_point_answer: resolved, entry point = build-feature.js / build-ticket.js / fast-lane-ship.js run under run_workflow_under_e2, and `fast_lane.py heavy_lane_gate` via subprocess.

red_baseline:
  - test_name: test_heavy_and_fast_lane_gate_commands_share_the_python_token
    file: unit_tests/workflows/test_tq500f3ii_gate_driver_contract.py
    error: "AssertionError: got {'build-feature.js': 'python3', 'build-ticket.js': 'python3', 'fast-lane-ship.js': 'python3'}"
  - test_name: test_fast_lane_ship_never_launches_fast_lane_py_with_python3
    file: unit_tests/workflows/test_tq500f3ii_gate_driver_contract.py
    error: "AssertionError: offending (token, subcommand) pairs: [('python3', 'select_connected'), ... ('python3', 'release')]"
  - test_name: test_gate_halt_message_names_interpreter_and_reason
    file: unit_tests/workflows/test_tq500f3ii_gate_driver_contract.py
    error: "AssertionError: build-feature.js: halt message must name the interpreter from the verdict ('/x/venv/python')"
  - test_name: test_verify_red_baseline_refuses_when_pytest_not_importable
    file: unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
    error: "AssertionError: reason 'no_red_outcome_among_new_tests' != 'test_interpreter_unusable'"
  - test_name: test_real_gate_verdict_carries_launching_interpreter
    file: unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
    error: "AssertionError: verdict has no 'interpreter' key (None != sys.executable)"

### 2026-10-06 16:30 — python-coder (status: ok)
feedback-id: (submit-failed)

Change: `_fl_red_baseline_support.py` gains `_interpreter_unusable_verdict()` (importlib.util.find_spec("pytest") precheck, refusal reason `test_interpreter_unusable`) and `_red_baseline_verdict` now carries `interpreter` (sys.executable); `fast_lane.verify_red_baseline` calls the precheck first (4 lines). build-feature.js, build-ticket.js: gate command `python3` -> `python`, halt message adds `(interpreter: ${gateVerdict.interpreter || "unknown"})`. fast-lane-ship.js: 8 `python3 ${gateScript}` -> `python ${gateScript}`; non-fast_lane.py python3 uses untouched. Changelog entry docs/changelog/2026-10-06-1600-red-baseline-gate-runs-under-the-project-interpreter.md (Linux note).

red_baseline_results (AC_ENFORCE_STRICT=1): all 5 green (test_heavy_and_fast_lane_gate_commands_share_the_python_token, test_fast_lane_ship_never_launches_fast_lane_py_with_python3, test_gate_halt_message_names_interpreter_and_reason, test_verify_red_baseline_refuses_when_pytest_not_importable, test_real_gate_verdict_carries_launching_interpreter). Full tq500f3ii set: workflows 11 passed, build_orchestration 6 passed (no_second_reader and passes_and_is_verified flake on a transient pytest returncode 2 in the nested run on this machine; both pass on rerun). Wider unit_tests/workflows: failures identical to HEAD (e.g. 25 failed before and after on the dispatch/release subset).

Ratchet (check_file_size, staged): build-feature.js 2964 -> 2958 (req <=2958), build-ticket.js 1647 -> 1642 (req <=1642), fast-lane-ship.js 1673 -> 1665 (req <=1665), fast_lane.py 391/400, _fl_red_baseline_support.py 314/400. Payment was whole-line deletion of decorative `// ---` rule comments plus condensing the gate comment block.

### 2026-10-06 17:00 — pr-reviewer (status: ok)
feedback-id: (submit-failed)

Verified: all 12 fast_lane.py launches in build-feature.js, build-ticket.js, fast-lane-ship.js use `python`; remaining `python3` are set_ticket_status.py, setup_ticket_worktree, bundle script, emit_entry, harvest_learnings (none launch fast_lane.py). find_spec precheck is the first statement of verify_red_baseline; reason is exactly `test_interpreter_unusable`; verdict built via `_red_baseline_verdict` so shape matches; `interpreter` is on every verify_red_baseline path. Halt message in both twins names interpreter and reason, degrading to "unknown". Line removals are only decorative `// ---` rules and a condensed gate comment; the TQ-500f-3-ii and H-3 references are kept.

Findings (no high; non-blocking):
- [M-1] scripts/build_orchestration/_fl_heavy_lane_gate.py:60-66 - the not-applicable verdict (no source AC) has no `interpreter` key, so "interpreter on every verdict path" is not met for the heavy_lane_gate wrapper. It cannot halt, so the halt message is unaffected; add `sys.executable` or record the exemption.
- [M-2] docs/how-to/fast-lane-build.md:211, 281, 342 still show `python3 <worktree_path>/.../fast_lane.py`, and the reason list at :304 omits `test_interpreter_unusable`. Docs-only; decide whether to fix now or in a follow-up. templates/skills/build-feature-ops-notes/SKILL.md has no python3 reference, so it needs no change.
- [M-3] templates/agents/build-ac.md:333 (and its .claude copy) launches `python3 ... fast_lane.py select_connected`, outside the three drivers, so it is out of this ticket's scope but has the same interpreter trap.
Changelog frontmatter is valid (type manual, components, breaking false). The Linux note is accurate, though its claim that the hooks already require `python` was not checked here.

### 2026-10-06 18:00 — test-runner (status: ok)
feedback-id: (submit-failed)

Ran with `AC_ENFORCE_STRICT=1` from the worktree root. This ticket broke nothing: every remaining failure also fails in the base worktree (build-tooling-done-proof, 119fca8e2).

completion_manifest:
  test_suite_executed: true
  all_tests_passing: false
  failure_report_structured: true
  all_tests_passing_detail:
    result: false
    reason: 173 nodes fail in the touched dirs, all pre-existing in the base worktree; 0 attributable to this ticket, 0 flakes. Includes the step-1 node test_heavy_lane_gate_refuses_declared_absence_only_red, which fails serially in both worktrees (nested pytest ERROR outcomes).
    remediation: Pre-existing failures belong to other tickets; none is caused by the gate-interpreter change.
  commands:
    step1_tq500f3ii_files: "16 passed, 1 failed (pre-existing)"
    step2_full_dirs_xdist_here: "172 failed, 1244 passed, 4 xfailed, 1 error, 244 subtests passed (second run; first run 169 failed, 1247 passed, 1 error)"
    step2_base_worktree: "173 failed, 1238 passed, 4 xfailed, 1 error"
    tests_referencing_fast_lane: "tests/knowledge/test_harvest_learnings.py included in step 2"
  classification: {attributable: 0, pre_existing: 174, flake: 0}

### 2026-10-06 16:38 — python-coder (status: ok)
feedback-id: (submit-failed)
M-1: heavy_lane_gate not-applicable verdict now carries `interpreter` (sys.executable); pinned in test_heavy_lane_gate_with_no_source_ac_reports_not_applicable.
M-2: docs/how-to/fast-lane-build.md uses `python` (3 places) and lists `test_interpreter_unusable` among the refusal reasons, with no net doc growth.

### 2026-10-06 16:41 — commit (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Subject: fix(build-orchestration): run the red-baseline gate under the project interpreter
