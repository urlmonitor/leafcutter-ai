---
title: "KI-TQ-20261102-wrong-version-run-requires-every-tagged-test-to-catch — the eval's wrong_version_run gives every `# covers:`-tagged test a must_catch, so a criterion or boundary test that rightly passes under the wrong version is a blocking survivor"
description: "medium — scripts/evals/produced_tests_runs.py write_ac_records writes must_catch [wrong_version] on every tagged test of the row, and the shared runner's verdict fails on any blocking survivor. On refresh-gate the test-writer wrote four tagged tests; the one that targets the retry_due condition caught 'drop the retry_due condition', the other three cannot and survived, so the row failed in all three live runs of 2026-11-02 (falsely red)."
type: reference
category: reference
status: active
created: '2026-11-02'
last_updated: '2026-11-02'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
  - docs/reference/produced-tests-eval-assertion-kinds-test-writer.md
  - docs/reference/wrong-version-runs.md
---

# KI-TQ-20261102-wrong-version-run-requires-every-tagged-test-to-catch — one catching test is not enough for the eval

> Filed 2026-11-02. Index: [testing-quality.md](../testing-quality.md). Filename severity is the
> three-level index bucket (`low`); the original grading is the `**Severity:**` line below.

- **Severity:** medium. The `refresh-gate` row cannot pass unless the agent writes only tests that
  each catch the wrong version, which punishes the criterion and boundary tests that round out a
  test set. The row is falsely red whenever the agent writes more than the one catching test.
- **Status:** open, no AC.
- **Occurrences:** 3 (first live run, re-run 1 and re-run 2, all 2026-11-02, Windows 11, main
  `8248ac7a`).
- **First seen:** 2026-11-02 · **Last seen:** 2026-11-02
- **Where:** `scripts/evals/produced_tests_runs.py` (line numbers on `171aafa5d`, unchanged since
  `8248ac7a`): `write_ac_records` :242-250 (the entry at :246), `judge_verdict` :265-275,
  `wrong_version_run` :278-291; the runner's verdict
  `scripts/build_orchestration/_wvr_verdict.py`:128-132; row `refresh-gate` in
  `scripts/evals/sets/test-writer.jsonl` (line 1).

## Symptom

`wrong_version_run` fails with "not caught by the runner (survivor); survived: passed under 'drop
the retry_due condition': the test did not notice it" (three times), while the same verdict holds a
`caught` row for the test that targets the change, and the report correctly names that test as the
one that catches it.

## Mechanism

- `wrong_version_run` finds every test function tagged `# covers: <AC-ID>` (`tagged_tests`
  :228-239) and `write_ac_records` writes one `test_spec` entry per tagged test, each with
  `"angle": "discrimination"` and `"must_catch": [wrong_version]` (:246).
- The shared wrong-version runner therefore runs every tagged test under the wrong version, marks
  each `survived` row `blocking: true`, and its verdict reports `reason: survivor` and
  `gate_passed: false` as soon as one blocking row survives (`_wvr_verdict.py`:128-132).
- `judge_verdict` passes only on `gate_passed` and a caught row (:271), so one caught row cannot
  outweigh the survivors.
- A test that checks the both-due path, or that `refresh_due` false blocks the refresh, passes
  under "drop the retry_due condition" by construction; only a test with `refresh_due` true and
  `retry_due` false can catch it. The test-writer template teaches a set of test angles
  (criterion, boundary, discrimination and others; `templates/agents/test-writer.md`:109-122), so a
  test set that covers the change from several angles is expected, and the agent tags them all with
  the row's AC id because the row input says "Tag the test `# covers: TQ-9201`".

## Evidence

Kept outputs (local, not committed):
`<session scratchpad>/kept_runs/`;
first live run results in `../rerun_score/test-writer.json`.

| Run | Tagged tests (angle) | Under "drop the retry_due condition" |
|---|---|---|
| re-run 1, `run1/test-writer/refresh-gate/files/tests/test_refresh_gate.py` | `test_refresh_fires_when_both_due` (criterion, :9), `test_refresh_blocked_when_retry_not_due` (discrimination, :15), `test_refresh_blocked_when_refresh_not_due` (boundary, :23), `test_refresh_blocked_when_neither_due` (boundary, :29) | `..._retry_not_due` caught; the other three survived (blocking) |
| re-run 2, `run2/test-writer/refresh-gate/files/tests/test_refresh_gate.py` | `test_refresh_runs_when_both_due` (criterion, :7), `test_no_refresh_when_retry_not_due` (discrimination, :12), `test_no_refresh_when_refresh_not_due` (discrimination, :19), `test_no_refresh_when_neither_due` (boundary, :26) | `test_no_refresh_when_retry_not_due` caught; the other three survived (blocking) |

Verdicts in `run1-test-writer.json` / `run2-test-writer.json`: `outcome` "wrong-version runs
stopped the work: survivor", `reason` "survivor". `report_lists_wrong_version` passed in both
re-runs; re-run 1's report says the wrong version is "caught by
`test_refresh_blocked_when_retry_not_due`", re-run 2's "caught by
`test_no_refresh_when_retry_not_due`" — both correct.

## Fix direction

- Pass the row when at least one tagged test catches the named wrong version and the runner
  reports no other failure: either judge the verdict on "caught by any tagged test", or write
  `must_catch` only on the entry of the test meant to catch it (the one whose report line names it,
  or the `angle: discrimination` test) and mark the other entries non-blocking (no `must_catch`, or
  a to-run-later extra).
- Update the `wrong_version_run` entry in
  `docs/reference/produced-tests-eval-assertion-kinds-test-writer.md` (:219-236), whose "Reads"
  line says the kind writes an AC record "naming the row's `wrong_version` under `must_catch`" for
  every tagged test, and whose passing example has a single test.
