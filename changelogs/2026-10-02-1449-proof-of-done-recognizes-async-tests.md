---
title: "Proof-of-done recognizes asynchronous tests"
date: "2026-10-02"
time: "14:49"
type: fix
components:
  - ac_store
summary: "The coverage scanner recognizes async test definitions, so CI can execute their linked proof instead of reporting it missing."
description: "Fixes the async coverage discovery defect exposed by the context-enrichment PR, with real passing and failing coroutine regression fixtures."
---

The CI proof-of-done scanner matched only synchronous `def test_` declarations. It therefore
reported no linked test for DK-100 and several DK-200 criteria even though their asynchronous
integration tests existed and passed. The shared definition matcher now also recognizes
`async def test_`, preserving both coverage and angle tags and the existing pass/fail gate.

The touched module also uses a distinct variable for its optional invocation collector,
removing an existing mypy name collision while retaining the same fail-closed fallback.

Three new regression tests failed before the matcher fix and pass afterward. They discover
both tag axes, prove a real passing `IsolatedAsyncioTestCase`, and reject a real failing one.
The scanner/eligibility regression selection passes 26 tests and four subtests; the adjacent
automation/reachability checks pass 12 tests. The public oracle also proves the actual DK-100
record with all seven linked asynchronous kernel integration tests passing. Ruff and CI-style
mypy pass for the touched scanner and regression module.
