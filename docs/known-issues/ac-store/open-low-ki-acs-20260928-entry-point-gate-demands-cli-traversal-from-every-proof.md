---
title: "KI-ACS-20260928-entry-point-gate-demands-cli-traversal-from-every-proof — the done-proof entry-point gate refuses any covering test that calls the code under proof directly, which contradicts a documented testing decision in the very file it judges"
description: "medium, and it is a QUESTION for the gate's owner rather than a defect report. The gate may be working exactly as ADR-050 intends. What is certain is the migration cost: every AC whose proofs are direct-import must gain CLI traversal before any PR touching that AC can pass, and ten such tests were migrated by hand on PR #862 to unblock one epic."
type: reference
category: reference
status: active
created: '2026-09-28'
last_updated: '2026-09-28'
components:
  - ac_store
  - build_orchestration
related_docs:
  - docs/known-issues/ac-store.md
  - docs/architecture/adrs/ADR-050-runtime-reachability-guard-refuses-not-warns.md
---

# KI-ACS-20260928-entry-point-gate-demands-cli-traversal-from-every-proof

- **Severity:** medium, with an explicit caveat: **this may not be a defect.** The gate is
  new, it is deliberate, and refuse-not-warn is ADR-050's stated posture. Filed as a question
  for whoever owns `BO-2900a-1`, plus a measured statement of the migration cost.
- **Status:** open — no AC, deliberately. Authoring one would presume the answer.
- **Occurrences:** 1 epic affected (PR #862, 2026-09-28): 10 covering tests across 2 files
  migrated by hand to unblock a single AC.
- **First seen:** 2026-09-28 · **Last seen:** 2026-09-28
- **Where:** `scripts/ac_store/_done_proof_entry_point_gate.py`,
  `_apply_entry_point_reachability_gate`, landed on main 2026-09-25 in `11b92057`.

## Mechanism

For each Python linked test of an otherwise-eligible AC, the gate detects whether the test's
unit defines a runtime way in (a module-level `main`). If one exists and the test's own
execution never entered it, the verdict is refused with
`refusal_cause: "proof_not_through_entry_point"` and the reason *"reached the code by direct
import instead of through `<module>:main`"*.

A unit test that imports the function under proof and calls it — the ordinary shape — is
therefore refused whenever that function's module happens to also expose a CLI.

## Why this is a question and not plainly a bug

`unit_tests/ac_store/test_done_proof_composite.py` carries a dedicated module-docstring
section titled *"Why `verify_done_eligible` is exercised directly for AC-6 (tests 1 & 2)"*.
It reasons that the ticket's Implementation Notes require the composite/leaf distinction to
live in `verify_done_eligible` itself, that calling it directly is the most direct behavioural
exercise of that logic, and that it "needs no git fixture repo… zero mocking."

So the gate refuses a test whose author wrote down, in advance, why it is shaped that way.
Two parts of main disagree, and the disagreement is between two deliberate positions rather
than between a rule and an oversight. That is the owner's call to make, not a hook to patch:

- If the gate is right, the docstring's reasoning is obsolete and a migration is owed across
  the store.
- If the docstring is right, the gate over-reaches for ACs about library functions and should
  scope its demand — perhaps to ACs whose subject IS the command surface.

## The cost, measured

On PR #862 the gate blocked the required Proof-of-done check. `BO-2500a-6` alone has **ten**
covers-tagged tests; every one reached its code by direct import. Unblocking one epic required
adding entry-point traversal to all ten, in two files, with per-test expected exit codes —
`0` for the four cases that must be eligible, `1` for the five that must refuse. A blanket
expectation would have inverted the five negative tests' meaning while still satisfying the
gate.

That work is committed and those ten now pass. It is not generalisable: **the next PR touching
any AC whose proofs are direct-import hits the same wall**, and only that AC's tests get fixed
each time.

Note also that the gate only bites when an AC enters `ci-changed` scope, so the surface is
invisible until touched. The store has not been swept for how many ACs are in this state; that
count is the first thing the owner will want and is not yet measured.

## Related, and already fixed

The same gate could not execute a `unittest.TestCase` method at all — its runner resolved the
test by `getattr(module, name)` and called it, which raises `AttributeError` for a method and
was reported as *"isolated re-execution did not pass"*, indistinguishable from a genuine test
failure. Since this repository's tests are overwhelmingly unittest classes, that made the
required gate refuse sound proofs across the board. Fixed in PR #862; the runner now locates
the defining `TestCase` subclass and runs it through the case's own `run()` so setUp and
tearDown execute as under pytest. **That fix is not this entry** — it removed a false refusal;
this entry is about the true refusals the gate then started issuing.

## Pattern

A new required gate landing with a policy that pre-existing, deliberately-reasoned tests do
not satisfy. The gate is not wrong to have an opinion; the open question is whose opinion
governs, and who pays the migration.
