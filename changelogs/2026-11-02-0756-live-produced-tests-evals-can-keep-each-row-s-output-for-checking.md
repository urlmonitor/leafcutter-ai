---
title: "Live produced-tests evals can keep each row's output for checking"
date: "2026-11-02"
time: "07:56"
type: manual
components: 
  - testing_quality
summary: "Set LEAFCUTTER_EVAL_KEEP_OUTPUTS to a directory and a live produced-tests eval run keeps what the agent produced for each row, so a failed row can be checked against the real output."
description: "A live produced-tests row's output (the files the agent changed, its report, its to-run-later evidence and, when captured, its transcript) lived in a temporary folder deleted after scoring, so a failed row could not be checked. With LEAFCUTTER_EVAL_KEEP_OUTPUTS naming a directory, each live row's output is copied to <dir>/<set name>/<row id>/ before scoring, for passing and failing rows; a re-run replaces the row's folder. Unset, or with --score-gold, nothing changes. Documented in scripts/evals/README.md. AC TQ-200d-1-iii."
breaking: false
---

## Entry
