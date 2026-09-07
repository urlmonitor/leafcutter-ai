---
title: "BP-1100b-4's test_spec is corrected to name real tests instead of arguing equivalence in prose"
date: "2026-08-26"
time: "10:05"
type: manual
components: 
  - build_pipeline
  - build_orchestration
summary: "Coordinator review found BP-1100b-4 declared 8 test_spec descriptors while only 3 existed as real tests; test_spec is renamed to match the implemented tests, a real dedicated test closes the one genuine gap, and covered_by on both ACs now lists only files that carry a matching covers tag."
description: "The prior commit flipped BP-1100b-4 to done while its amended_by argued that differently-named BO-1000c-1a tests satisfied its test_spec intent -- an argument in prose while the declared names still disagreed with the tree, which is the phantom-done shape this branch exists to remove. Four descriptors (test_one_journal_record_is_appended_per_completed_step and three siblings) named a per-step journal-file mechanism BO-1000c-1a's 2026-08-18 redefinition deleted outright; they are renamed to the literal names of the dispatch-based tests that replace them, each with an amended_by note stating the old name and why. The fifth, test_run_that_cannot_append_fails_instead_of_passing, is the anti-phantom-done property itself -- a run that cannot append must fail a test, not merely produce a smaller number -- and had no real mapping at all. It is now a dedicated test in test_bp_1100b_4.py: a synthetic script gates a step's dispatch behind a swallowed require('fs') and still returns a normal success payload, then asserts that applying the real positive tests' own non-vacuous coverage check to that outcome raises AssertionError rather than passing. Four functions in test_bo_1000c_1a.py now carry a second covers tag for BP-1100b-4 alongside their existing BO-1000c-1a tag, since they genuinely satisfy both AC's test contracts; covered_by on both AC records is corrected to list only files with a matching tag, dropping the harness module (which cannot carry a covers tag at all) from both. Full unit_tests/workflows/ suite under AC_ENFORCE_STRICT=1: 469 passed, zero regressions."
commits: []
breaking: false
---

## Entry
