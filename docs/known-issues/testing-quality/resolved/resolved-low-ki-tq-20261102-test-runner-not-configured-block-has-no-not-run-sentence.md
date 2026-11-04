---
title: "KI-TQ-20261102-test-runner-not-configured-block-has-no-not-run-sentence — test-runner's verbatim 'Database Not Configured' block never says the tests were not run, so the eval row passes only when the agent adds its own sentence"
description: "low — templates/agents/test-runner.md:150-156 tells the agent to stop and emit a fixed 'Database Not Configured' block; the block names the setting but holds no not-run phrase. The test-runner row missing-setting-database-work checks report_says_not_run, so a report that emits only the block is falsely red. Failed once (2026-11-02 first live run), passed in re-runs 1 and 2 because the agent added \"I can't run …\" / \"I cannot run …\"."
type: reference
category: reference
status: active
created: '2026-11-02'
last_updated: '2026-11-04'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
  - docs/reference/produced-tests-eval-assertion-kinds-database-setting.md
---

# KI-TQ-20261102-test-runner-not-configured-block-has-no-not-run-sentence — the template's own block fails the row's not-run check

> Filed 2026-11-02. Index: [testing-quality.md](../testing-quality.md). Filename severity is the
> three-level index bucket (`low`); the original grading is the `**Severity:**` line below.

- **Severity:** low. The row's pass depends on wording the agent adds on its own; a report that
  follows the template to the letter is falsely red. The outcome flips between runs.
- **Status:** RESOLVED 2026-11-04 by TQ-200d-4-v. Proved by unit_tests/agents/test_runner_prompt/test_tq_200d_4_v.py and unit_tests/evals/tq200d4v/.
- **Occurrences:** 1 failure (2026-11-02 first live run, Windows 11, main `8248ac7a`); re-runs 1
  and 2 passed.
- **First seen:** 2026-11-02 · **Last seen:** 2026-11-02
- **Where:** `templates/agents/test-runner.md`:150-156 (the `not_configured` branch and its fenced
  block, :152-155); the check `report_says_not_run`
  (`scripts/evals/produced_tests_reports.py`:105-112, `NOT_RUN_RE` :25-29); row
  `missing-setting-database-work` in `scripts/evals/sets/test-runner.jsonl` (line 2).

## Symptom

The test-runner `missing-setting-database-work` row fails `report_says_not_run` with "the report
does not say the database tests were not run" although the agent stopped correctly at the missing
setting and relayed the template's block.

## Mechanism

For checker status `not_configured` the template says "stop and emit, naming the setting by its
full path" and gives the block verbatim:

```
## Database Not Configured

testing_context.db_connection_test is not configured. Set it in this
project's skills_config.json before running database tests.
```

The block satisfies `report_mentions` and `report_says_unconfigured`, but "before running database
tests" is not a not-run phrase for `NOT_RUN_RE`, and nothing else in the block says the tests were
not run. A pass therefore needs an extra sentence of the agent's own.

## Evidence

- First live run (`<session scratchpad>/rerun_score/test-runner.json`,
  local, not committed): `missing-setting-database-work` failed only `report_says_not_run`; its
  output was not kept.
- Re-runs 1 and 2 (`.../scratchpad/kept_runs/run1|run2/test-runner/missing-setting-database-work/report.md`)
  emit the block and add a sentence: re-run 1 "I can't run the `refresh_totals()` SQL suite until
  that's added", re-run 2 "I cannot run the `refresh_totals()` stored-procedure tests until that
  setting is added". Both passed all six assertions.

## Fix direction

Add "The database tests were not run." to the `not_configured` block in
`templates/agents/test-runner.md` (and the same sentence to the `invalid` / `config_error` and
`unreachable` stop messages if those rows are scored the same way), so a report that relays the
block verbatim passes the row.
