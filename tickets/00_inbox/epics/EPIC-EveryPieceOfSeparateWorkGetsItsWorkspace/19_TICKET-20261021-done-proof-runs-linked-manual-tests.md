---
title: "The done-proof check runs an AC's linked _MANUAL tests instead of refusing them as not run"
status: todo
components:
  - ac_store
  - commit_guardian
created: '2026-10-21'
last_updated: '2026-10-21'
depends_on: []
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: internal
complexity: low
requires_adr: false
requires_diagram: false
tags:
  - BO-4300
  - found-on-pr-1274
  - KI-ACS-20261013
agents:
  test-writer: signed_off
  python-coder: signed_off
  pr-reviewer: signed_off
  commit: needed
---

# 19: The done-proof check runs an AC's linked _MANUAL tests

## Actor / Goal
In order for a done AC whose real proof is a slow `_MANUAL` test to pass the required "Proof-of-done coverage check", the check must run the `_MANUAL` tests an AC links to, rather than reporting them as "linked test not run". Default test runs stay fast.

## Context
- **Found:** 2026-10-21 on PR #1274. CI's `check_done_proof.py --mode ci-changed` refuses BO-4300a-1 (9 linked `_MANUAL` tests) and BO-4300f-4 (2), both with "linked test not run".
- **Why the tests are manual:** purely speed. Their shared setup builds the real deployed maker, which exceeds `testing_context.max_test_duration_seconds` (5 s).
- **Why they are not run:** `scripts/suite_performance/pytest_manual_deselect.py` marks every `*_MANUAL` test `manual`, and pytest.ini's addopts deselects `manual` by default (TQ-600a-13). The done-proof oracle (`scripts/ac_store/done_proof.py`) runs linked node ids with the default selection, so they are deselected. This is KI-ACS-20261013-done-proof-cannot-see-manual-tests.
- **User decision 2026-10-21:** "Proof check runs them". Re-marking them as manual-evidence was rejected, because no other CI test asserts these ACs' clauses.

## Scope
1. When done_proof runs an AC's linked Python tests, linked `_MANUAL` tests are opted in, for example by overriding the `-m` selection for that invocation so manual tests are included. Exactly the linked node ids run, nothing else.
2. A linked manual test that passes counts as passing. One that fails, or is skipped, is still refused with its real outcome.
3. The default suite and CI's test shards keep deselecting manual tests.

## Acceptance Criteria
- [ ] AC-1: A done AC whose only linked tests are `_MANUAL` and pass is eligible.
- [ ] AC-2: A linked `_MANUAL` test that fails makes the AC ineligible, naming the failure.
- [ ] AC-3: The default pytest run still deselects `_MANUAL` tests.
- [ ] AC-4: On Linux, with the epic's tree, `verify_done_eligible` returns eligible for BO-4300a-1 and BO-4300f-4, and CI's `--mode ci-changed` command exits 0.

## Test Requirements

```yaml
tests:
- name: test_linked_manual_test_is_run_and_counts_when_it_passes
  file: unit_tests/ac_store/test_done_proof_runs_linked_manual_tests.py
  asserts: A temp AC store and test tree where an AC links only a passing *_MANUAL test; verify_done_eligible returns eligible with that test passing.
  framework: unittest
  type: behavioral
- name: test_failing_linked_manual_test_is_refused_with_its_outcome
  file: unit_tests/ac_store/test_done_proof_runs_linked_manual_tests.py
  asserts: A failing linked *_MANUAL test makes the AC ineligible, naming it as failed, not "not run".
  framework: unittest
  type: behavioral
- name: test_default_run_still_deselects_manual_tests
  file: unit_tests/ac_store/test_done_proof_runs_linked_manual_tests.py
  asserts: A plain pytest run over the same tree deselects the *_MANUAL test.
  framework: unittest
  type: behavioral
```

## Sign-offs
- [x] test-writer
- [x] python-coder
- [x] pr-reviewer — 2026-10-21 15:26
- [ ] commit

## Comments

_(Append-only log -- leave blank when authoring.)_

### 2026-10-21 14:20 — test-writer (status: ok)
feedback-id: fb_2026-10-21_7d265f91

Wrote unit_tests/ac_store/test_done_proof_runs_linked_manual_tests.py (3 tests, unittest). Each builds a temp AC store plus a temp test tree whose pytest.ini carries the repo's manual-deselect setup (a copy of scripts/suite_performance/pytest_manual_deselect.py loaded via -p, and -m "not manual and not timing_ratio" in addopts), then drives the real done_proof.verify_done_eligible. The fixture file holds the linked test_slow_proof_MANUAL plus an unlinked test_unlinked_sibling_MANUAL that writes a sentinel file, so test 1 also proves only the linked node ids run. Tests carry covers tags BO-2500a-3, BO-2500a-2 and TQ-600a-13. (classification: missing_behavior) - production gap, no existing test touched at this phase.

red_baseline:
  - test_name: test_linked_manual_test_is_run_and_counts_when_it_passes
    file: unit_tests/ac_store/test_done_proof_runs_linked_manual_tests.py
    kind: assertion
    error: "AssertionError: eligible False: could not verify ZZ-MANUAL-PROOF: the run did not finish -- pytest run unfinished: 1 file(s), returncode 5"
  - test_name: test_failing_linked_manual_test_is_refused_with_its_outcome
    file: unit_tests/ac_store/test_done_proof_runs_linked_manual_tests.py
    kind: assertion
    error: "AssertionError: reason names the unfinished run (returncode 5, every test deselected), not 'linked test failed:'"
  - test_name: test_default_run_still_deselects_manual_tests
    file: unit_tests/ac_store/test_done_proof_runs_linked_manual_tests.py
    kind: guard
    error: "green before the fix (guard for AC-3)"

### 2026-10-21 15:40 — python-coder (status: ok)
feedback-id: fb_2026-10-21_3baec94a

New `_manual_opt_in_args(linked_functions)` in scripts/ac_store/_done_proof_phase_helpers.py: when any linked function name ends in `_MANUAL` it returns `["-m", "manual or not manual", "-k", "<linked names joined by or>"]` (the later -m wins over addopts; -k keeps the run to the AC's linked tests), else `[]`. `done_proof._run_pytest_and_parse(test_files, linked_functions=())` appends it ahead of the file args; `_run_python_test_phase` passes `tuple(t["function"] for t in py_linked)` (leaf and composite paths both go through it). Other callers (fast lane) keep the default selection. A failing or skipped linked manual test still reports its real outcome. DECISION HISTORY entry in _done_proof_phase_helpers.py (KI-ACS-20261013, ticket 19); done_proof.py change documented in the function docstring. No templates/ mirror: done_proof.py is deployed from scripts/ac_store via AC_STORE_DEPLOY_MAP, and templates/scripts/commit_guardian/check_done_proof.py only imports verify_done_eligible. Ratchet: done_proof.py 966 -> 956 (removed a comment block that restated the module docstring's sibling-module paragraph), phase helpers 368 -> 378 (under 400); check_file_size and check_complexity pass. (classification: consumer_drift) for unit_tests/ac_store/test_done_proof_composite_js.py: three fake `_run_pytest_and_parse` runners now accept `linked_functions=()`.

red_baseline_results:
  - test_name: test_linked_manual_test_is_run_and_counts_when_it_passes
    result: green
  - test_name: test_failing_linked_manual_test_is_refused_with_its_outcome
    result: green
  - test_name: test_default_run_still_deselects_manual_tests
    result: green

Linux (bo4300-ci docker, origin/main bundled): new tests 3 passed; done_proof/check_done_proof suite 433 passed, 5 failed, all 5 also fail on origin/main's done_proof in the same image (vitest node_modules absent: test_real_vitest_assertions_control_composite_verdict x3, TestRunVitestRealInvocation x2). verify_done_eligible: BO-4300a-1 eligible (10 passing), BO-4300f-4 eligible (5), BO-4300b-4 eligible (4), BO-4300b-5 eligible (4). `check_done_proof.py --mode ci-changed --base origin/main --test-root .` exit 0. Default `pytest unit_tests/build_orchestration/test_bo_4300a_1_deployed.py -q`: 9 deselected.

### 2026-10-21 15:26 — pr-reviewer (status: ok)
feedback-id: fb_2026-10-21_ed09f8af

No high-confidence findings. Selection safe: classification reads only the AC's linked node ids, so extra tests selected by -m/-k can never change a verdict; opt-in is confined to _run_pytest_and_parse called with linked_functions from _run_python_test_phase and only when a linked name ends in _MANUAL; default suite and CI shards untouched. Re-marks: b-4 and b-5 keep four CI-runnable covers tests each matching their test_spec. New tests are real (sentinel proves unlinked sibling stays out; failing-linked case asserts 'linked test failed:'; default-deselect guard).
[M-1] -k is a substring match: names containing a linked name (incl. timing_ratio or other _MANUAL tests, since the later -m also lifts not timing_ratio) are also run. Cannot alter results; may only lengthen the run toward the timeout (reported as run-did-not-finish). Suppressed: 2 low (removed BP-100n-4-ii comment block, long -k argv on Windows).
