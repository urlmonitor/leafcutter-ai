---
title: "A temp folder that cannot be deleted after an eval row no longer ends the run (TQ-200d-5-iv)"
date: "2026-11-04"
time: "12:00"
type: manual
components: 
  - testing_quality
summary: "Produced-tests eval rows now delete their temp folders with a tolerant helper (retry, then a warning naming the folder left behind, never raises), so a Windows file-in-use error no longer ends the run, replaces a row error or changes a score. Resolves KI-TQ-20261102-eval-temp-cleanup-error-crashes-the-run."
description: "TQ-200d-5-iv. Files: scripts/evals/produced_tests_runs.py, produced_tests_mode.py, produced_tests_scoring.py, scripts/build_orchestration/_wvr_gate.py, scripts/evals/README.md, docs/how-to/run-a-live-agent-eval.md, known-issue register."
breaking: false
---

## Entry
