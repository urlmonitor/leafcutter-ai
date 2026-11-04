---
title: "TQ-200d-1-iv: the test-writer count and seeded-value checks read unittest assertion calls"
date: "2026-11-04"
time: "12:30"
type: manual
components: 
  - testing_quality
summary: "counts_rows_and_non_null and asserts_known_seeded_value now read unittest assertEqual/assertTrue/assertGreater calls as well as bare asserts, and an exact count may compare against a non-literal integer expression such as len(seed)."
description: "TQ-200d-1-iv widens the two static test-writer kinds in scripts/evals/produced_tests_scoring.py: unittest assertion calls are read (assertEqual/assertEquals, assertTrue of a comparison, assertGreater, assertGreaterEqual) with the same bounds as assert, and an exact count may compare against a non-literal integer expression, never against itself. The reference entries and the evals README say so. This resolves KI-TQ-20261102-test-writer-scorer-reads-only-bare-asserts, which moves to the resolved folder."
---

## Entry
