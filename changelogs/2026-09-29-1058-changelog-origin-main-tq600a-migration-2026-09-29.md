---
title: "Changelog origin/main..tq600a-migration — 2026-09-29"
date: "2026-09-29"
time: "10:58"
type: manual
components: 
  - testing_quality
  - ac_store
  - ticket_lifecycle
  - glossary
summary: "Added test coverage and corrected the acceptance-criteria scope for the shared-test-layout migration work; this does not yet speed up the test suite."
description: "7 commits on feature/tq600a-migration (origin/main..HEAD): implemented TQ-600a-1-i, covered by unit_tests/suite_performance/test_tq_600a_1_i.py (3 tests) pinning the laziness boundary of the shared reference layout (zero deploys with no consumer selected, one deploy once a consumer is added). Gave both entry-point AC records (TQ-600a-1-i, TQ-600a-1-ii) real file scope after their generated tickets shipped with an empty files_touched, then adopted the new declared_files AC field from ACD-1600c-4 (#948) on both records as the mechanism that decides file scope, replacing doc_links for that purpose (doc_links kept for explanatory prose). Expanded TQ-600a-8 so an unconverted read-only test site becomes a named failure rather than a silent omission, and corrected scope/bounds across TQ-600a-3, TQ-600a-4, TQ-600a-5, and TQ-600a-6. This is spec and coverage work only — the 77 build-spawning test sites have not been migrated yet; that lands with TQ-600a-4."
pr: 953
commits: 
  - a15f62a8
  - ebefcec0
  - 9ac3c581
  - ebf620b7
  - 36b6f30b
  - 28a12b4b
  - ba21892b
---

## Entry
