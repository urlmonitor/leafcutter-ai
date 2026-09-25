---
title: "ACs for tests that catch the plausible wrong version, and for removing the shipped test database address"
date: "2026-09-25"
time: "11:30"
type: manual
components:
  - testing_quality
  - infrastructure
summary: "Adds an analysis of why the test writers prove a test can fail once but not that it tells right from wrong, and the acceptance criteria that follow from it: TQ-500f (tests specified and written against named plausible-wrong implementations), TQ-500g (post-coder mutation runs, L1 only) and INF-1100d (no shipped test database address). No code changes."
description: "New analysis page docs/analysis/2026-09-25-test-writers-prove-failure-not-discrimination.md, with the adopter database address replaced by a placeholder. AC store: TQ-500f and 13 children, TQ-500g (L1 only), INF-1100d and 9 children, all approved at priority high; TQ-500 criteria gain one sentence on early failures that only prove absence. docs/INDEX.md was restored after the doc-index hook rewrote its paths with Windows backslashes."
commits:
breaking: false
---

## Entry

A green test can be useless because its fixture and assertions cannot tell a correct
implementation from a wrong one. The package's red baseline only shows a test fails
while the code is missing, which an `ImportError` satisfies. This change records the
analysis and the acceptance criteria for fixing it: a `discrimination` test angle, a
`must_catch` list of named wrong versions on each test requirement, one shared
red-baseline reader for the fast lane and `/build-feature`, and the three questions
both test writers must ask. It also specifies removing the adopter database address
that leafcutter currently ships as a default.
