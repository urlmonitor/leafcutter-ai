---
title: "The test runner runs a named test file through the project's test command and never reports a pass for a run that executed no test"
date: "2026-11-01"
time: "14:00"
type: manual
components:
  - testing_quality
summary: "templates/agents/test-runner.md runs a named test file as <testing_context.test_command> <file>, falling back to python -m pytest <file> when the setting is unset, and offers no plain-script form. It reports PASS only with a passed-test count above zero quoted from the runner's own summary (for unittest, Ran N tests ... OK with N above zero); a run that executed no test gets a NO TEST RAN report with the command and the reason (nothing collected, no passed test, or no runner summary), and its machine-parsed reply has passed false, the reason in anomalies and outcome error."
description: "TQ-200d-4-ii, TQ-200d-4-iii. The live before-score (2026-10-25) caught the test runner running tests/check_window_total.py as a plain script and reporting PASS (KI-TQ-20261025-test-runner-runs-a-test-file-as-a-script; its Status line now names these two ACs, and TQ-200d-4-iv resolves it). Template: frontmatter config_keys gains testing_context.test_command; Routing Table and the single <path> action name the configured command and the python -m pytest fallback; Output: Success requires a quoted passed count above zero and states that exit 0 alone is not a pass; new Output: No Test Ran section; Combined Output, Machine-Parsed Dispatch Output Contract and Completion Manifest follow. docs/reference/skills-config-fields.md gains the testing_context.test_command row. User decisions 2026-11-01 at review: outcome error when no test ran (quick-fix reads outcome before passed), a third reason 'no passed test', and the unittest passed-count note; TQ-200d-4-iii's criteria amended accordingly. Caller check: build-feature, build-ticket, finalize-feature, ticket-supervisor and python-coder read no pass from a no-test run. Tests: unit_tests/agents/test_runner_prompt/ (7, structural). Wrong-version gate: all 6 named versions caught."
commits:
breaking: false
---

## Entry

The test runner now runs a test file the way the project says to run tests, and falls back to
pytest when the project names no command. It never runs a test file as a plain Python script, which
executes no test at all. It reports a pass only when the runner itself says at least one test passed;
a run that executed nothing is reported as "no test ran", with the command and the reason, and is
never read as a pass by the workflows that call it.
