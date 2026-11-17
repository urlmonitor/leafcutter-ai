---
title: "TQ-200d-4-v: test-runner's Database Not Configured block now says the tests were not run"
date: "2026-11-04"
time: "12:00"
type: manual
components: 
  - testing_quality
summary: "The test-runner template's not_configured block ends with the sentence \"The database tests were not run.\", so a report that relays it passes report_says_not_run."
description: "TQ-200d-4-v adds the sentence \"The database tests were not run.\" as the last line of the fenced Database Not Configured block in templates/agents/test-runner.md. The report_says_not_run reference entry and the produced-tests section of scripts/evals/README.md now describe it. This resolves KI-TQ-20261102-test-runner-not-configured-block-has-no-not-run-sentence, which moves to the resolved folder."
---

## Entry
