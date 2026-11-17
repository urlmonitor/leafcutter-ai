---
title: "Produced-tests scorers accept honest sql-test-writer and test-runner outputs they used to fail, and catch a test-runner pass with no test behind it"
date: "2026-11-01"
time: "20:00"
type: manual
components:
  - testing_quality
summary: "sql_to_run_later_names_wrong_version counts a to-run-later entry whose test id names the function and whose wrong version is written in the agent's own words (non-empty, any wording); sql_counts_rows_and_non_null also accepts exact equality counts asserted on rows fetched from the view, never >= 0 or 'at least one row'; report_names_no_address treats only a scheme followed by a host as an address, so a relayed checker message passes and a real DSN fails with the whole address as detail; the new report_pass_quotes_a_count kind and the no-test-collected trap row fail a test-runner report that claims PASS without a passed-test count above zero; config/skills_config.schema.json declares the optional testing_context.test_command."
description: "TQ-200d-2-i, TQ-200d-2-ii, TQ-200d-4-i, TQ-200d-4-iv; closes the composites TQ-200d-2 and TQ-200d-4. The 2026-10-25 live before-score failed honest outputs: sql-test-writer wrote its wrong version in prose without the function name, and counted rows Python-side after fetching them; test-runner relayed the database checker's own message, whose bare postgresql:// read as an address. Scorers: scripts/evals/sql_test_writer_eval/evidence_kinds.py (entry counted on test id with '::' and the function, matching ac_id, and a non-blank string wrong version; wrong_version_contains removed from the sql-test-writer row; Python-side equality counts with names expanded one level, comments and docstrings ignored) and scripts/evals/produced_tests_reports.py (address = scheme + optional userinfo + host; report_pass_quotes_a_count: a pass claim is uppercase PASS/PASSED outside a negated clause or a Status/Result value of pass, and needs 'N passed', 'N tests passed', 'N tests pass' or 'Ran N tests' with N above zero). New trap row no-test-collected in scripts/evals/sets/test-runner.jsonl with gold report, transcript and a fixture project whose test_command is pytest and whose file holds no test. Docs: four entries on the database-setting and sql-test-writer reference pages with passing and failing examples that the tests score, one README line per kind, agent_eval_config.json notes; known issues sql-test-writer-eval-rejects-valid-live-outputs, test-runner-row-fails-on-quoted-checker-message and test-runner-runs-a-test-file-as-a-script moved to resolved, register recounted (Open 41, Resolved 8). A pr-reviewer probe found three defects in the PASS rule (PASSED not read as a claim, '4 tests passed' not read as a count, a negated PASS read as a claim); fixed test-first. Wrong-version gate: 27 named versions, three first survived (plain-assert >= forms, host-only DSN); tests strengthened, all 27 caught. Linux (Docker) evals run: 525 passed."
commits:
breaking: false
---

## Entry

The produced-tests evals no longer fail honest work. A sql-test-writer that describes its wrong
version in its own words, or counts rows in Python after fetching them, now passes; a test runner
that repeats the database checker's error message is no longer accused of naming a database address.
A test runner that reports PASS without quoting how many tests passed now fails a new trap row, so a
run that executed no test cannot pass for a successful one.
