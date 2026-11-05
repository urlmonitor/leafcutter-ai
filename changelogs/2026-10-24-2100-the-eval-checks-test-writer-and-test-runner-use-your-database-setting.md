---
title: "The eval checks that test-writer and test-runner use your project's database setting and say when it is missing"
date: "2026-10-24"
time: "21:00"
type: manual
components:
  - testing_quality
summary: "The local produced-tests eval gains three database-setting rows for test-writer and a new local_only test-runner set. A configured row fails any produced test or command that reaches a database by an address of its own instead of testing_context.db_connection_test; a missing-setting row with database work must name the setting and not report the database tests as run; the missing-setting trap row with no database work fails a hand-off that warns about the setting. test-runner is scored from the Bash commands in its stream-json transcript, never from its final report."
description: "TQ-200d-4. New scripts/evals/produced_tests_db.py (AST and resolver-taint check of produced test files), produced_tests_commands.py (quote-aware splitting, bash -c / cmd /c recursion, wrapper and python-option skipping; a checker run counts only when its output holds the checker's JSON report), produced_tests_reports.py (hand-off wording checks), produced_tests_transcript.py (stream-json Bash commands and results, live invoker with utf-8 decoding); RowContext carries the transcript commands. agent_eval_config.json registers test-runner (local_only, support_scripts scripts/db_check, capture_transcript). Sets: test-writer.jsonl 5 to 8 rows, new test-runner.jsonl with 3 rows, fixture projects and recorded gold outputs whose checker results are the real checker output. Existing tests: test_agent_eval_config_triggers.py pins six agents; two TQ-200d-1 row-set tests replaced by renamed tests pinning all eight rows (sweep: removed with replacement notes). Three test-first review rounds. AC in_scope_files amended to the modules that now hold the scoring. Wrong-version gate: 12 named versions, all caught. Residual review misreads filed as KI-TQ-20261024-produced-tests-db-scoring-residual-misreads (low)."
commits:
breaking: false
---

## Entry

The eval that scores the tests the test writer produces now also checks how it handles your
project's test database. Given a configured setting, the tests it writes must take the address
from that setting and never write one of their own. Without a setting, it must say the setting is
missing when the work needs a database, and stay quiet about it when the work does not.

The test runner is now measured the same way, from the commands it actually ran rather than from
what its report says. It has to run the database checker, must not connect with an address of its
own, and has to say plainly when the database tests could not run. Both evals run locally only.
