---
title: "The test writers prove a test can fail once, not that it can tell right from wrong"
description: "Audit of test-writer and sql-test-writer against eight green-but-useless test incidents from the bybit-trader adopter. The test-angle taxonomy covers wiring-shaped failures; nothing in the package covers discrimination-shaped ones, and the red baseline is a single mutation that an ImportError satisfies."
type: explanation
status: active
created: 2026-09-25
last_updated: 2026-09-25
components:
  - testing_quality
  - build_orchestration
---

# The test writers prove a test can fail once, not that it can tell right from wrong

A green test can be useless in two different ways.

1. **Wiring-shaped.** The test is correct about the unit, but the unit is not
   connected to anything real: no production entry point reaches it, the real
   producer never feeds the real consumer, the fixture is not the real format,
   or the deployed copy differs from the source tree.
2. **Discrimination-shaped.** The test reaches the real code, but its fixture
   and assertions cannot distinguish a correct implementation from a wrong one.
   It passes on the fix, and it would also pass on the bug.

[`docs/testing/test-angles.md`](../testing/test-angles.md) is a strong answer to
the first kind. Its angles (`reachability`, `seam`, `real_artifact`, `deployed`)
and the `must_block` modifier each close a wiring gap with repo evidence behind
it. **Nothing in the package addresses the second kind.** Every one of the eight
incidents below, all from the bybit-trader adopter, is discrimination-shaped.

The red baseline does not close the gap. It shows a test fails against **one**
wrong program, the one where the implementation does not exist yet. An
`ImportError` counts as red (`templates/agents/test-writer.md:689-690`, `:878`).
So for any new symbol the baseline is red by construction, and it says nothing
about whether the assertions would catch a plausible wrong implementation.

## The evidence: eight incidents in one adopter

All eight come from bybit-trader's own write-ups (its `CLAUDE.md` § Testing,
`unit_tests/README.md:399-530`, `unit_tests/sql_functions/README.md:58`, and
its maintainer memory). I have not re-verified them against bybit-trader's git
history. The mechanism column is what those write-ups record.

| # | Incident | Mechanism | Cost | Covered by an angle? |
|---|---|---|---|---|
| 1 | ConfigCache DB-outage retry storm (PR #612) | A gate went from `if refresh_due:` to `if refresh_due and retry_due:`. Two of three tests were updated to satisfy both conditions; the third reset only the old variable. The branch under test ran **0 times** (measured call count). | The branch the ticket existed to fix could have been deleted with the suite still green. | No. No angle asks whether every condition of a compound gate is satisfied by the fixture. |
| 2 | EPIC-CvdWindowDeltaNormalisation, **six occurrences** | The gate's input moved from `cvd` to `cvd_delta_30`. Fixtures still seeded only `cvd`, so the control row that should pass was excluded for the same reason as the negative row. TEMP shadow tables omitted the new column "by design". One consumer suite was missed in the sweep. The probe written to *fix* one assertion used `buy_volume >= 0`, which drops NULLs, so it passed most reliably when the pipeline was dead. A further check measured a window that predated the backfill. | Correct code turned suites red, and the natural response was to "fix" working code. | No. `real_artifact` is about serialized bytes, not about which inputs a gate reads. |
| 3 | MacroAvwaps anchor starvation (`b8f47a12f` → PR #605) | `ORDER BY` added to a loop with a per-call cap of 5 and no resume cursor. Every test used a fixed population. | The same 5 anchors won every call; the rest starved in prod for **8 weeks**. | Partly. `boundary` names "limit", but not repeated calls under continuous inflow. |
| 4 | EPIC-UnblockResurrection/03 | The coverage test for the starvation fix used a pool that emptied under any ordering, so the fixed and reverted code both passed. | Caught only because `pr-reviewer` re-derived the guarantee by hand. | No. |
| 5 | EPIC-SqlFunctionsSuiteGreen (PR #448) | An integration test of a live procedure was `@unittest.skip`-ped as "retired". | Production coverage silently deleted. | Partly. `done_proof.py` treats `SKIPPED` as non-passing, but only for tests being proven for an AC now, not for skips added to old tests later. |
| 6 | SQL suite rot (~395–468 stale failures) | Column drops and procedure deletions never reconciled with tests. | Suite untrustworthy until a nightly CI gate was added. | Out of scope: a process failure (see test-angles.md "What this taxonomy does NOT fix"). |
| 7 | DB tests hardcoded to a developer's `localhost:<port>` | Passed against the developer's local DB, failed only in CI. | Hard-to-trace CI-only failures. | No. The package template **propagates** this (see below). |
| 8 | Context parity check at "live = 100%" | Measured that values were present, not that they were correct. | False confidence in prod data. | No. |

bybit-trader's `CLAUDE.md` names the family "green-by-vacuity" and records the
defences it learned: assert the denominator (exact counts, not one-sided
checks); seed new inputs with values distinct from old ones; mutation-test at
file level; sweep every consumer test when a gate's inputs change; test capped
loops under continuous inflow. **None of these reached the package.**

## What the current templates do (leafcutter v9.0.69)

### test-writer

The template has improved a great deal since the v1.10.6 copy bybit-trader still
runs (tagged 2026-06-08). It now runs before the coders, must leave its tests
red, records a `red_baseline`, carries the seven-angle taught set, and has
Rules 1–6 for test repair. Measured against what a writer needs in order to
produce a discriminating test:

| Needed | Current template | Gap |
|---|---|---|
| **Intent: the failure the test must catch** | AC `test_spec[].description` is "what this test asserts" (`config/ac_store_schema.json`). The Bug-Fix Test Mandate (`test-writer.md:194-196`) says a regression test "must fail when the bug is reintroduced". | There is no field for the concrete wrong behaviour or the mutation the test must catch. The mandate is prose with nothing that checks it. |
| **Every input the gate reads** | Step 3 sends research-agent questions about signatures and imports only (`:852-856`). | For changes to existing code, nothing asks the writer to list the inputs and conditions the fixture must satisfy. That list is what incidents 1 and 2 lacked. |
| **Realistic data shape** | Product-truth Mock Data (`:711-746`) and the fixture-authenticity rule (`:748-772`). | Both are about *format* authenticity. Neither covers the population shape that matters here: volume against a cap, NULL rates, rows that keep arriving. |
| **Sibling and consumer tests** | Rule 2 enumerates consumers, but only when a contract changes shape (`:447-455`). | The constraint "Do NOT modify existing test files unless the ticket explicitly requires it" (`:949`) forbids the consumer-test sweep whose absence caused three of the six incident-2 occurrences. |
| **Discrimination evidence** | Red baseline (`:858-884`). | Discussed below. |
| **Where the lessons live** | Step 1.3 reads the adopter's test README "for naming conventions, directory layout, and performance rules" (`:575-576`). | In bybit-trader the green-by-vacuity lessons are in that README (lines 399–530 of 653), but the prompt frames the file as conventions. |
| **How the test is executed** | `_MANUAL` suffix and time budget (`:664-670`). | The DB template hardcodes `postgresql://<user>:<password>@localhost:<port>/<db>` (`:631-633`) — an adopter's real local connection string, with username, password and a database named for production, inside a portable template, and the direct cause of incident 7's shape. |

### Why the red baseline is not enough

The red baseline is a mutation test with exactly one mutant: "the implementation
is missing". That is valuable. It is what defeats phantom-done, and the doc's
key question — *"If I deleted the single line that wires this in, would this
test go red?"* (`test-angles.md:77-79`) — is also a single, well-chosen mutant.
But three things weaken it as evidence of discrimination:

1. **An `ImportError` is a valid red state** (`:689-690`, `:878`). A test for a
   new symbol is red regardless of what it asserts. The baseline says only that
   the symbol does not yet exist.
2. **For zero-exit tests the prescribed remedy is "add a stronger assertion or a
   `TODO` comment, and re-run until non-zero"** (`:879`). A `TODO` comment
   cannot change the exit code. The instruction pushes toward "make it red",
   which is not the same as "make it discriminating".
3. **Nothing runs after the coder.** Once the implementation exists, no step
   perturbs it and checks the tests notice. Every incident above involved
   either a *wrong* implementation (the pre-fix code) or a fixture that could
   not reach the branch. The red-against-absence check sees neither.

### sql-test-writer

`templates/agents/sql-test-writer.md` asks for a happy path and "empty input,
zero rows, boundary condition" (`:70-71`) and verifies with `py_compile` only
(`:155-160`). It is told not to run the suite (`:196`). There is no red
baseline, no pre-fix run, and no mention of the adopter's documented trap that
a DB-level mutation is silently reverted because suites re-deploy `.sql` in
`setUpClass`. SQL is where six of the eight incidents happened.

## The three questions no template asks

These are the questions that would have caught incidents 1–4 and 8. Each is
answerable by an agent before sign-off.

1. **What is the smallest change to the production code that keeps this test
   green but brings the bug back?** If the writer can name one, the test is
   weak, and that change is the first mutant to run.
2. **What result would show that this assertion can fail?** Does the fixture
   produce it? A one-sided assertion or a "no NULLs" check over a set that can
   be empty has no such result.
3. **Does the control row pass for the same reason the negative row fails?** If
   the fixture's "should pass" case would be excluded by the same condition that
   excludes the "should fail" case, the test pins nothing.

## What we must do

In rough order of value per effort.

1. **Add the missing test family to the taxonomy.** Extend
   `docs/testing/test-angles.md` with a discrimination-shaped failure catalogue
   (incidents 1–4 and 8 above) and a `discrimination` angle or modifier. Its
   rule: the test must go red under at least one named plausible-wrong
   implementation, not only under absence. Update the schema enum and the
   taught-set block together, as the lockstep test requires.
2. **Give the AC a place to say what must be caught.** Add an optional
   `must_catch` list to `test_spec[]` items: named mutants such as "revert the
   fix", "drop the second gate condition", "new column NULL". This makes the
   Bug-Fix Test Mandate checkable instead of prose.
3. **Add a mutation phase after the coder.** A phase agent (working name
   `test-breaker`) takes the `must_catch` list plus its own proposals, applies
   each mutant to the file on disk, runs the tagged tests, restores the file,
   and blocks sign-off if any mutant survives. Reuse `done_proof.py`'s
   fail-closed outcome classifier rather than building a second one.
   Discrimination is decided by these runs; the agent's own opinion is not the
   verdict.
4. **Fix the red-baseline wording.** Treat an import- or attribute-error red as
   evidence of absence only; do not let it satisfy a regression test for
   existing code. Replace "or a `TODO` comment" (`:879`) with "a stronger
   assertion".
5. **Put the three questions and a short vacuity checklist into test-writer and
   sql-test-writer themselves:** exact-count assertions, a control row, new
   inputs seeded distinct from old ones, a call-count on the collaborator the
   branch must reach. Keep them in the prompt, not as a pointer into an
   adopter's README.
6. **Replace the blanket ban on editing existing tests** (`:949`) with a
   required sweep: list every test that exercises the changed gate or helper,
   and update it or state why it is unaffected.
7. **Make sql-test-writer run what it writes,** including a pre-fix run for
   regression tests. Document the setUpClass re-deploy trap alongside it.
8. **Move the DB connection string out of the template** (`:631-633`) into
   `testing_context`, where the adopter already configures it.
9. **Adopter follow-up (bybit-trader, not this repo):** it is pinned to v1.10.6.
   Bumping it brings the red baseline and the angles; its `CLAUDE.md` testing
   lessons should be fed back here as the evidence base for item 1.

## What this analysis does not show

- **Nothing was run.** This is a reading of the templates at `e919a24f`
  (v9.0.69) and of the adopter's written incident record. Whether the current
  red baseline would have caught any single incident is inference. Incident 1's
  third test, for example, was a repair of an existing test, not a test-first
  stub.
- **One adopter.** All eight incidents come from bybit-trader, which is
  SQL-heavy and time-series shaped. Adopters with less stateful data logic may
  see the wiring family dominate, as leafcutter itself does.
- **Cost of item 3 is unmeasured.** Mutation runs on DB-backed suites are
  slow. The phase should probably fire only for tests that pin a bug or a
  gate, not for every test. That scoping needs a decision before any AC is
  written.
