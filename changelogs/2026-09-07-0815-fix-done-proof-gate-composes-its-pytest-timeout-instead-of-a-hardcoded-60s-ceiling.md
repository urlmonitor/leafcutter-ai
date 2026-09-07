---
title: "Fix: done-proof gate composes its pytest timeout instead of a hardcoded 60s ceiling"
date: "2026-09-07"
time: "08:15"
type: manual
components: 
  - ac_store
summary: Fixed a bug where the automated check that verifies a requirement is really done could time out on legitimately slow tests and wrongly report their proof as missing rather than as timed out.
description: "Commit cbc0e1efb fixes scripts/ac_store/done_proof.py: _run_pytest_and_parse ran an AC's linked-test subprocess under a hardcoded timeout=60, but pytest collection alone costs ~30-33s in this repository, leaving under 30s for actual test execution regardless of the AC being verified. Subprocess-heavy tests (e.g. BP-900g-8-ii / PR #694, which drives real build.py subprocesses) could never fit and were reported as \"linked test not run\", indistinguishable from missing tests. The budget is now composed -- a 30s collection floor charged once, plus 300s per linked test file -- and a timeout is threaded through verify_done_eligible and _verify_composite_eligible via a non-nodeid sentinel so it reports distinguishably from an absent test. LEAFCUTTER_DONE_PROOF_PYTEST_TIMEOUT_SECONDS overrides the computed value when positive, warning and falling back otherwise. The gate was never fail-open and still is not: a timeout still yields not-eligible, only the reason now names the budget instead of implying the tests do not exist. KI-TQ-20260901-1310 stays open by design -- it closes when PR #694's gate actually runs green, not on this fix landing."
pr: 706
commits: 
  - cbc0e1efb
breaking: false
---

## Entry

### The done-proof gate charged pytest collection against the AC's own budget

The done-proof gate is what actually decides whether an acceptance criterion is allowed
to be marked `done`: it runs the AC's linked tests as a real pytest subprocess and only
accepts a passing outcome as proof. That subprocess ran under a hardcoded
`timeout=60`. In this repository, pytest **collection alone** — before any test body
starts running — costs roughly 30-33 seconds, so the real execution allowance was under
30 seconds, and it shrank further as the repository's own test tree grew, regardless of
the size or nature of the AC actually being verified.

The gate was never fail-open, and this change does not touch that guarantee: a timeout
still produces no passing outcomes, and the verdict stays not-eligible. The defect was
subtler than that. The gate did not wave weak tests through — it selected against
**expensive** ones, and the cheapest thing to delete under budget pressure is always the
subprocess, which is exactly the part that proves a guard runs against something real
rather than against a mock. This blocked `BP-900g-8-ii` (PR #694), whose acceptance
criteria specifically require driving real `build.py` subprocesses, at ~142 seconds of
genuine execution time; CI reported `pytest timed out after 60s` followed by "linked
test not run" for all five of its tests — wording that reads as "these tests don't
exist" rather than "the gate ran out of time".

### The budget is now composed, not just raised

Rather than pick a single larger constant (which reproduces the same defect one notch
up, still indifferent to the AC's size), the timeout is now built from two pieces: a
30-second collection floor, charged **once** per subprocess call, plus 300 seconds per
linked test file. One linked file resolves to 330 seconds; ten resolve to 3,030. The
300-second per-file figure is deliberately generous — roughly 2x the ~142-second
measurement that exposed the bug — because that measurement was taken on a developer
workstation, and a GitHub-hosted CI runner is materially slower for subprocess-heavy
work; a tighter number chosen to just clear the local measurement would have reproduced
the same failure on CI while looking fixed locally.

A genuine timeout is now also reported distinguishably from a missing or unlinked test:
`_run_pytest_and_parse` returns a sentinel value (deliberately not shaped like a pytest
node id, so it can never be mistaken for a real result) that `verify_done_eligible` and
`_verify_composite_eligible` check before classifying individual test outcomes, so the
eligibility reason now names the budget and the command instead of implying the tests
were never found. `LEAFCUTTER_DONE_PROOF_PYTEST_TIMEOUT_SECONDS` lets an operator
override the computed value directly when it parses as a positive number, and warns on
stderr and falls back to the computed default otherwise, rather than crashing or
silently using a zero budget.

### What stays open on purpose

`KI-TQ-20260901-1310` remains `Status: open`. This fix is verified in isolation, but the
claim the known issue makes is that PR #694's proof-of-done gate can actually pass under
real CI conditions — and that is only established once that gate runs green there, not
by a desk-check on this branch.
