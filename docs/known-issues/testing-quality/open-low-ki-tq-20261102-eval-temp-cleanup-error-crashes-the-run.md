---
title: "KI-TQ-20261102-eval-temp-cleanup-error-crashes-the-run — a Windows 'file in use' error while deleting the produced-tests temp folder ends the whole eval run with a traceback, so no row of the run is scored or written"
description: "medium — scripts/evals/produced_tests_mode.py score_one runs each row inside tempfile.TemporaryDirectory(prefix=\"produced-tests-\"); when the sandbox under it is still in use, cleanup raises PermissionError [WinError 32] on ...\\produced-tests-*\\score\\sandbox outside the row's try/except, run_produced_tests_mode catches only AgentLaunchError, and the run dies: no results file, the remaining rows never run (sql-test-writer re-run 2, 2026-11-02). The same WinError 32 makes the score-gold unit tests flake on Windows."
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
  - docs/how-to/run-a-live-agent-eval.md
  - docs/known-issues/testing-quality/open-low-ki-tq-20260914-tempdir-cleanup-race-fails-a-green-test-run.md
  - docs/known-issues/testing-quality/open-high-ki-tq-20260927-windows-local-runs-disagree-with-linux-ci.md
---

# KI-TQ-20261102-eval-temp-cleanup-error-crashes-the-run — temp cleanup decides whether an eval run produces any result

> Filed 2026-11-02. Index: [testing-quality.md](../testing-quality.md). Filename severity is the
> three-level index bucket (`low`); the original grading is the `**Severity:**` line below.

- **Severity:** medium. Not a false score: the run produces no score at all. One locked folder
  discards every row already scored in that run and skips the rest, and on Windows the lock is
  routine after an agent run whose child processes outlive the CLI.
- **Status:** open, no AC.
- **Occurrences:** 1 live run (sql-test-writer re-run 2, 2026-11-02, Windows 11, main `8248ac7a`
  plus the keep-outputs change of PR #1386). The same `WinError 32` on the temp folder also makes
  the score-gold unit tests flake on Windows (`unit_tests/evals/test_tq200d1_runner_cli.py`, the
  tq200d4 gold tests under `unit_tests/evals/tq200d4/`); seen during local runs, not counted here.
- **First seen:** 2026-11-02 · **Last seen:** 2026-11-02
- **Where:** `scripts/evals/produced_tests_mode.py` (line numbers on `171aafa5d`, unchanged since
  `8248ac7a`; the traceback's :135 / :195 are the same lines on the PR #1386 branch): `live_output`
  :88-112 (the `finally: runs.remove_tree(agent_box)` at :110-111), `score_one` :115-132 (the
  `with tempfile.TemporaryDirectory(prefix="produced-tests-")` at :119, the row's `except` at
  :128-132), `run_produced_tests_mode` :168-200 (only `AgentLaunchError` caught, :177-180);
  `scripts/evals/produced_tests_runs.py` `remove_tree` :133-141.

## Symptom

`python scripts/evals/run_agent_eval.py --agent sql-test-writer` ends with a traceback whose last
line is `PermissionError: [WinError 32] … 'C:\Users\…\AppData\Local\Temp\produced-tests-5k0_msc_\score\sandbox'`.
No results file is written, no aggregate is printed, and rows after the failing one are never run.

## Mechanism

1. The agent's sandbox is `<tmp>/score/sandbox` inside the row's `TemporaryDirectory` (:95, :119).
2. In re-run 2 the agent CLI exited 1 ("API Error: Connection closed mid-response"). `live_output`'s
   `finally` then called `remove_tree(agent_box)`, which raised a `PermissionError` because the
   sandbox directory was still in use (presumably by a process the agent started that outlived the
   CLI; not confirmed). That error replaced the `ModelInvocationError`, and `score_one`'s `except`
   (:128) turned it into a failed row: "row empty-window-database-shape could not be scored:
   PermissionError(13, …)". The row's recorded error names the lock, not the API failure.
3. `return` from inside the `with` block runs `TemporaryDirectory.cleanup`, which tries the same
   directory again and raises `PermissionError [WinError 32]`. This is outside the `try`, so it
   propagates out of `score_one`, out of the list comprehension at :178, past the
   `except AgentLaunchError` (:179), and ends the process.

## Evidence

`<session scratchpad>/kept_runs/run2-sql-test-writer.log`
(local, not committed; 93 lines). Line 1: `ERROR run_agent_eval: agent CLI exited 1: API Error:
Connection closed mid-response.`; line 2: `WARNING run_agent_eval: row empty-window-database-shape
could not be scored: PermissionError(13, 'Der Prozess kann nicht auf die Datei zugreifen, da sie
von einem anderen Prozess verwendet wird')`; then a chained traceback through
`produced_tests_mode.py", line 195, in run_produced_tests_mode` → `line 135, in score_one` (`with
tempfile.TemporaryDirectory(prefix="produced-tests-") as tmp:`) → `tempfile.py", line 971, in
__exit__` → `shutil.rmtree`, ending in `PermissionError: [WinError 32] … '%TEMP%\produced-tests-…\score\sandbox'`.
No `run2-sql-test-writer.json` exists beside the log, and the second row (`no-test-database`) was
never run; `done.txt` records `run2 sql-test-writer 1`.

## Fix direction

Cleanup must never decide a run:

- Create the row folder with `tempfile.TemporaryDirectory(prefix="produced-tests-",
  ignore_cleanup_errors=True)` (Python 3.10+), or clean it up explicitly after the row with a few
  short retries, and log a warning naming the folder left behind.
- Make `remove_tree` in `live_output`'s `finally` best-effort too (retry, then warn), so a lock does
  not replace the row's real error (here the API failure).
- Optionally catch `OSError` per row in `run_produced_tests_mode` so one row's environment error is
  a failed row, not a lost run; apply the same tolerant cleanup to the score-gold path the unit
  tests use.
