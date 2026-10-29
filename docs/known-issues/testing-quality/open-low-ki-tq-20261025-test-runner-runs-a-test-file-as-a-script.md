---
title: "KI-TQ-20261025-test-runner-runs-a-test-file-as-a-script — the live test-runner ran a pytest file with plain python, so no test ran, and reported Status: PASS; its template offers that command for single files and never names the project's configured test_command"
description: "medium — agent finding from the 2026-10-25 live before-score. On the W2 row (missing-setting-no-database-work, 'Run tests/check_window_total.py and report.') the test-runner ran `python tests/check_window_total.py` and then `PYTHONPATH=. python tests/check_window_total.py`. The file only defines test_window_total_adds_the_values and never calls it, so nothing was tested, yet the report said 'Status: PASS'. templates/agents/test-runner.md:104-105 offers `python unit_tests/live_trader/<file>.py` for the single-file action, and the template never mentions testing_context.test_command, which the fixture sets to 'pytest'. The eval's commands_ran_pytest correctly failed the row."
type: reference
category: reference
status: active
created: '2026-10-25'
last_updated: '2026-10-25'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
  - docs/known-issues/testing-quality/open-low-ki-tq-20261025-test-runner-row-fails-on-quoted-checker-message.md
---

# KI-TQ-20261025-test-runner-runs-a-test-file-as-a-script — a pytest file run as a script passes without testing anything

> Filed 2026-10-25. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. This is the agent, not the eval: a report of PASS for a run in which no
  test executed. Any caller that trusts the test-runner's status (a coder's inner loop, a build
  gate reading the report) would take untested code as tested. The eval caught it.
- **Status:** open, no AC.
- **Occurrences:** 1 (the live before-score on 2026-10-25, Windows 11, `run_agent_eval.py
  --agent test-runner` without `--score-gold`, results timestamp `2026-10-25T20:58:19Z`): the
  `missing-setting-no-database-work` row (the W2 trap of TQ-200d-4) failed only
  `commands_ran_pytest`, "no command runs pytest (4 command(s) seen)". Its other assertions
  (`report_silent_on_setting`, `report_states_outcome`, `commands_no_db_address`) passed. The
  session transcript is under
  `C:\Users\Hendrik\.claude\projects\C--Users-Hendrik-AppData-Local-Temp-produced-tests-t65fe3la-score-sandbox\`
  (local to the machine that ran the score); it shows `python tests/check_window_total.py`, then
  `PYTHONPATH=. python tests/check_window_total.py`, and a report with `Status: PASS`.
- **First seen:** 2026-10-25 · **Last seen:** 2026-10-25
- **Where** (line numbers at `origin/main` `5e5a37380`):
  - `templates/agents/test-runner.md`:104-105: "For the **single-file** action:
    `python unit_tests/live_trader/<file>.py` or `poetry run python -m pytest <path> -v`." The
    first form runs a file as a script, which runs a `unittest` file only if it ends in
    `unittest.main()` and never runs a pytest-style file.
  - `templates/agents/test-runner.md`:27-33, `config_keys`: only `test_command_live_trader` (:28)
    and `test_output_dir`. The template never names `testing_context.test_command`; its only
    `testing_context` key is `db_connection_test` (:126 and after).
  - `scripts/evals/sets/test-runner/projects/missing-setting-no-database-work/.claude/skills_config.json`:3,
    `"test_command": "pytest"`, and `tests/check_window_total.py` in the same fixture, which
    defines `test_window_total_adds_the_values` and does not call it.
  - `scripts/evals/sets/test-runner.jsonl`:3, the row, input "Run tests/check_window_total.py and
    report.", which carries `commands_ran_pytest`.
  - `scripts/evals/produced_tests_commands.py`:259-272, `_is_pytest_run` and
    `commands_ran_pytest`: `pytest` / `py.test` or `python -m pytest`. The recorded gold
    transcript (`scripts/evals/sets/test-runner/recorded/missing-setting-no-database-work/transcript.jsonl`:2)
    runs `python -m pytest -q tests/check_window_total.py`.

## Symptom

Asked to run one named test file, the live test-runner runs it as `python <file>`. The process
imports the module, defines the test function and exits 0. The agent reports the run as passed
("Status: PASS") although no assertion was evaluated.

## Mechanism

1. **The template offers a script run for single files.** The single-file action lists
   `python unit_tests/live_trader/<file>.py` first; for this project's layout that becomes
   `python tests/check_window_total.py`.
2. **The configured runner is never consulted.** The project declares
   `testing_context.test_command: "pytest"`, but the template reads only
   `test_command_live_trader`, so nothing points the agent at pytest.
3. **Exit 0 is read as a pass.** A script that only defines test functions exits 0 with no
   output. The template has no rule that a run which collected no tests is not a PASS.
4. **The import error was treated as an environment problem.** The first run failed to import
   `window_total`; the agent fixed that with `PYTHONPATH=.` and got exit 0, which looked like
   success.

## Detection

A test-runner report of PASS whose commands run a test file as `python <path>` (no `-m pytest`,
no `pytest`, no `unittest`) and whose output shows no collected or passed test count. In the eval,
`commands_ran_pytest` fails with "no command runs pytest".

## Workaround

None in the agent. Read a test-runner PASS together with its commands; a bare-script run is not a
test result. In the before-score this row counts as a genuine agent failure.

## Suggested fix

Directions only; nothing here is applied.

- **Run tests through the configured runner.** In `templates/agents/test-runner.md`, read
  `testing_context.test_command` (declare it in `config_keys`) and run the single-file and
  default actions through it; fall back to `python -m pytest <path>` when it is unset. Remove the
  bare `python <file>.py` form from :104-105, or keep it only for files that call
  `unittest.main()`.
- **Never report PASS without a test count.** Require the report's PASS to rest on the runner's
  own summary (for example "N passed"); a run with zero collected tests, or with no runner
  summary at all, is reported as not run.
- The project-specific live-trader routing table (:96-102) is the same kind of baked-in command;
  it may be worth reading from config too, as a separate change.

**Related.** `KI-TQ-20261025-test-runner-row-fails-on-quoted-checker-message` is the other
test-runner row that failed in the same before-score; that one is a scorer defect, this one is
the agent's.

**Pattern:** a runner instruction that names a concrete command instead of the project's
configured one, plus "exit 0 means pass", which together report success for a run that tested
nothing.
