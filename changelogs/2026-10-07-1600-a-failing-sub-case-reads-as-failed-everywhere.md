---
title: "A test that fails in any sub-case reads as failed, and a contradictory run is inconclusive"
date: "2026-10-07"
time: "16:00"
type: manual
components:
  - testing_quality
  - ac_store
summary: "done_proof, the kind-aware reader and the fast lane's red-baseline gate now share one pytest reader. A test whose only failures sit in subTest sub-cases (SUBFAILED lines) reads FAILED, with the sub-case named in the reason. A run that exits 1 with no identifiable failing test is inconclusive instead of passed."
description: "TQ-500g-4 and TQ-500g-4-i (fast lane, manually orchestrated; fixes KI-TQ-20260928 subtest-failures-read-as-passed). New scripts/ac_store/pytest_outcome_reader.py holds the one parse: SUBFAILED[msg] / SUBFAILED(params) lines force the node id to FAILED (the node id runs to ' - ' or end of line, so parametrize ids with spaces stay whole), SUBPASSED never counts, and returncode 1 with no FAILED/ERROR returns the incomplete-run sentinel ('no failing test could be identified'). done_proof.py imports it (net shorter), done_proof_kind_support passes the exit status, red-baseline verdict entries gain an additive 'subcases' key, and mark_ac_done refuses an AC covered only by a sub-case-failing test with the sub-case named. The module is registered in AC_STORE_DEPLOY_MAP so deployed gates load it."
commits:
breaking: false
---

## Entry

A test written with unittest sub-cases could fail in one of them and still be counted as
passed, because pytest prints the test itself as PASSED and reports the sub-case failure on
a separate line that the checks did not read. Every check that reads a test run now reads
that line, so such a test counts as failed and the failing sub-case is named. A run that
says it failed but shows no failing test is now treated as unclear rather than as a pass.
