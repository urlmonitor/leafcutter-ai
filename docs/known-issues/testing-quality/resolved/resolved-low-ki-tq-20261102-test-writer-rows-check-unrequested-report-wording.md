---
title: "KI-TQ-20261102-test-writer-rows-check-unrequested-report-wording — three test-writer row checks want report wording the test-writer template never asks for, so correct reports are scored falsely red"
description: "medium — scripts/evals/sets/test-writer.jsonl: empty-window checks report_mentions 'non-NULL' (reports say non-None count / all-None window), presence-is-not-correctness checks report_mentions 'known value' (reports say exact expected value from the feed), and missing-setting-database-work checks report_says_not_run although the test-writer template requires a red verification run (Step 4) and the reports truthfully say the run went red in setUp before any connection; the check's cited template sentence is in test-runner.md, not test-writer.md. All three failed in all three live runs of 2026-11-02. Fix pending a decision: widen or drop the checks, or add template sentences."
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
  - docs/reference/produced-tests-eval-assertion-kinds-test-writer.md
  - docs/reference/produced-tests-eval-assertion-kinds-database-setting.md
  - docs/known-issues/testing-quality/resolved/resolved-low-ki-tq-20261102-test-writer-scorer-reads-only-bare-asserts.md
---

# KI-TQ-20261102-test-writer-rows-check-unrequested-report-wording — report checks the template gives the agent no reason to meet

> Filed 2026-11-02. Index: [testing-quality.md](../../testing-quality.md). Filename severity is the
> three-level index bucket (`low`); the original grading is the `**Severity:**` line below.

- **Severity:** medium. Three of the eight test-writer rows hold a report check that a report
  which follows the template fails, so those rows are falsely red independent of test quality, and
  a template that never states the wanted wording cannot be fixed by reading the score.
- **Status:** RESOLVED 2026-11-04 by TQ-200d-1-vi and TQ-200d-4-vi; proving tests in
  `unit_tests/evals/tq200d1vi/` and `unit_tests/evals/tq200d4vi/`. Fix direction decided by the user on
  2026-11-02: widen the checks (no template change); see Fix direction.
- **Occurrences:** 9 failed assertions, each check in each of the three live runs of 2026-11-02
  (first live run, re-run 1, re-run 2; Windows 11, main `8248ac7a`).
- **First seen:** 2026-11-02 · **Last seen:** 2026-11-02
- **Where:** `scripts/evals/sets/test-writer.jsonl` rows `empty-window` (line 3,
  `{"kind": "report_mentions", "contains": "non-NULL"}`), `presence-is-not-correctness` (line 4,
  `{"kind": "report_mentions", "contains": "known value"}`) and `missing-setting-database-work`
  (line 7, `{"kind": "report_says_not_run"}`); kinds `report_mentions`
  (`scripts/evals/produced_tests_scoring.py`:152-156, a case-insensitive substring test) and
  `report_says_not_run` (`scripts/evals/produced_tests_reports.py`:105-112, `NOT_RUN_RE` :25-29);
  `templates/agents/test-writer.md`.

## Symptom

On rows whose tests are otherwise sound (`produced_test_green` and `fails_on_mutants` pass, the
reports describe the right guards), the row fails with "report does not name 'non-NULL'", "report
does not name 'known value'" or "the report does not say the database tests were not run".

## Mechanism

1. ~~**`non-NULL` on `empty-window`.** The row tests Python code over a list, where the missing value~~
   ~~is `None`; the agents say "non-`None`". The template uses "non-NULL count" only inside its own~~
   ~~Step 4b remedy (`test-writer.md`:1156) and never asks the report to repeat it.~~
   *Fixed by TQ-200d-1-vi: `also_accepts` on the row's `report_mentions` check; tests in `unit_tests/evals/tq200d1vi/`.*
2. ~~**`known value` on `presence-is-not-correctness`.** The template's remedy says "assert at least~~
   ~~one known expected value seeded in the fixture" (:1159); a report that echoes it ("known~~
   ~~expected value") still fails the substring `known value`, and nothing asks the report to use the~~
   ~~phrase at all.~~
   *Fixed by TQ-200d-1-vi: `also_accepts` on the row's `report_mentions` check; tests in `unit_tests/evals/tq200d1vi/`.*
3. ~~**`report_says_not_run` on `missing-setting-database-work`.** The test-writer must run its new~~
   ~~tests and see them red (Step 4 "Verify the Tests Are Red", `test-writer.md`:1090-1117), and its~~
   ~~DB pattern lets the not-configured error propagate from `setUp` (:854-857). So the truthful~~
   ~~report is "ran, red in `setUp` before any connection", not "not run". The rule's documented~~
   ~~template sentence, "Do NOT attempt to run the SQL suite unless the checker reports `reachable`."~~
   ~~(`docs/reference/produced-tests-eval-assertion-kinds-database-setting.md`:162-181), comes from~~
   ~~`templates/agents/test-runner.md`:172; `test-writer.md` holds no such sentence.~~
   *Fixed by TQ-200d-4-vi (`report_says_stopped_before_database`); proving tests in `unit_tests/evals/tq200d4vi/`.*

## Evidence

Kept outputs (local, not committed):
`<session scratchpad>/kept_runs/`;
first live run results in `../rerun_score/test-writer.json`.

- `empty-window`: re-run 1's report says "exact-count and non-`None`-count guards" and "an empty or
  all-`None` window"; re-run 2's says "exact non-None count" and "an empty or all-`None` window"
  (`run1|run2/test-writer/empty-window/report.md`). Both failed `report_mentions` 'non-NULL'.
- `presence-is-not-correctness`: both reports say the test asserts "exact expected value from the
  feed" (`run1|run2/test-writer/presence-is-not-correctness/report.md`). Both failed
  `report_mentions` 'known value'.
- `missing-setting-database-work`: re-run 1's report says the run went red with
  `DbConnectionTestNotConfiguredError` "raised in `setUp()` before any connection is attempted";
  re-run 2's says the test "stops in `setUp()` before ever reaching `refresh_totals()`"
  (`run1|run2/test-writer/missing-setting-database-work/report.md`). Both name
  `testing_context.db_connection_test` and passed `report_mentions` and
  `report_says_unconfigured`; both failed `report_says_not_run`.

The agent-side weakness seen on these rows (the `empty-window` and `presence-is-not-correctness`
reports skip the Completion Report format, and no row checks it) is recorded in
[KI-TQ-20261102-test-writer-scorer-reads-only-bare-asserts](resolved-low-ki-tq-20261102-test-writer-scorer-reads-only-bare-asserts.md).

## Fix direction

**Decided 2026-11-02 (user): change the checks.** The template is not changed; the checks are
widened to accept equivalent wording and, for the test-writer, a report that says the database part
never executed. The second option below was not chosen and is kept for the record.

- **Change the checks.** Widen `empty-window` to accept `non-None` / `non-null` (or a set of
  synonyms), widen `presence-is-not-correctness` to accept "expected value" / "seeded value", and
  for `missing-setting-database-work` drop `report_says_not_run` from the test-writer row or
  replace it with a check that the report says the run stopped at the missing setting (red before
  any connection); update the `report_mentions` and `report_says_not_run` entries in the reference
  docs (`produced-tests-eval-assertion-kinds-test-writer.md`:183 onward,
  `produced-tests-eval-assertion-kinds-database-setting.md`:162-181) so each cites a sentence the
  test-writer template actually holds.
- **Change the template.** Add report sentences to `templates/agents/test-writer.md`: name the
  guard as a "non-NULL count" in the report, name the "known value" asserted, and say "the
  database tests were not run against a database" when the setting is missing; then the checks
  stand as they are and cite those sentences.
