---
title: "A local eval scores the tests test-writer produces: green on the fix, red on each wrong version"
date: "2026-10-24"
time: "13:00"
type: manual
components:
  - testing_quality
summary: "New produced-tests scoring mode for agent evals. Each row runs the agent (or, with --score-gold, a recorded gold output) in a sandbox git repo and scores the tests it wrote deterministically: they must pass on the fixed code and fail against named wrong versions. The refresh-gate row runs the real wrong-version runner. test-writer is registered local_only, so the CI eval job never selects it and its results say run_context local."
description: "TQ-200d-1, TQ-200d-1-i. scripts/evals/produced_tests_mode.py, produced_tests_scoring.py, produced_tests_runs.py, produced_tests_mutants.py; set scripts/evals/sets/test-writer.jsonl (5 rows: refresh gate, new function or existing code, empty window, presence is not correctness, input moved to a new column) with fixture projects, mutants and recorded gold outputs; eval_selector local_only exclusion in main(); run_agent_eval.py 3-line dispatch and dead helpers removed. Sandbox git and pytest calls scrub GIT_* redirection so an eval inside a git hook cannot touch the real index; a live run exports every file the agent wrote at its relative path. User decisions OQ-1..OQ-11 (2026-10-23); the live before-score is deferred. Wrong-version gate: 29 named versions and the fix undone caught after weak tests were strengthened."
commits:
breaking: false
---

## Entry

The test writer can now be measured on what it actually produces, not on what it says. A
local eval gives it small projects with a known bug fix. The tests it writes have to pass on
the fixed code and fail on each named wrong version of it. A test that would pass whether the
fix is there or not scores as a fail.
