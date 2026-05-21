---
title: "Harden test-writer (and python-coder) with Source-of-Truth Discipline to prevent silent production contract shrinkage"
status: in_progress
components:
  - agents
  - documentation_system
created: 2026-05-20
depends_on: []
priority: high
tags:
  - agent-prompting
  - test-writer
  - guardrails
  - regression-prevention
last_updated: 2026-05-21
files_touched:
  - templates/agents/test-writer.md
  - templates/agents/python-coder.md
  - docs/architecture/adrs/ADR-002-test-source-of-truth-discipline.md
  - docs/architecture/adrs/README.md
agents:
  architect-review: needed
  python-coder: not_needed
  test-writer: not_needed
  test-runner: not_needed
  sql-coder: not_needed
  documentation-expert: not_needed
  adr-author: needed
  architecture-diagram-author: not_needed
  change-scope-reviewer: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
requires_diagram: false
requires_adr: true
---

# Harden test-writer (and python-coder) with Source-of-Truth Discipline to prevent silent production contract shrinkage

## Actor / Goal

In order to prevent test-repair work from silently narrowing production contracts,
we need to add Source-of-Truth Discipline rules to the `test-writer` agent template
(and a parallel guard in `python-coder`) so that future agents — across every
leafcutter consumer — are forced to classify test failures, enumerate consumers,
and split contract changes from assertion fixes before making any production change.

## Provenance

This ticket originated from an incident in the `bybit-trader` consumer of leafcutter
on 2026-05-20. The Pipeline Health dashboard displayed a single "Unknown" trace
across all 8 per-phase charts instead of one color-coded trace per symbol. Root cause
traced to commit `d1dd18f1` ("fix(tests): repair 5 pre-existing test suite failures
on main"), produced by the `test-writer` agent on 2026-05-19 as Ticket 02 of
EPIC-Main_Test_Suite_Repair.

The bybit-trader-side fix ticket (`TICKET-20260520-PipelineHealth_Symbol_Regression`)
restores the dashboard. This ticket addresses the **systemic prompting gap in the
leafcutter agent templates** that allowed the incident to occur, so the same class
of regression is prevented across every consumer of leafcutter, not just bybit-trader.

---

## Deep Root-Cause Analysis

### Incident (in bybit-trader, a leafcutter consumer)

- **Symptom**: All 8 per-phase linecharts on the Pipeline Health dashboard
  displayed a single trace labelled "Unknown" instead of one color-coded
  trace per symbol.
- **Discovered**: 2026-05-20.
- **Introduced**: 2026-05-19 by commit `d1dd18f1` — "fix(tests): repair 5 pre-existing
  test suite failures on main", Ticket 02 (EPIC-Main_Test_Suite_Repair,
  "fix_pipeline_health_queries_drift").

### What actually changed

The `fetch_phase_timeseries` function in `dashboards/pipeline_health_data.py` had its
SQL contract narrowed:

- **Before**: `SELECT bucket, symbol, COUNT(...) ... GROUP BY 1, 2`, result rows =
  `{"bucket", "symbol", "count"}`.
- **After**: `SELECT bucket, COUNT(...) ... GROUP BY 1`, result rows =
  `{"bucket", "count"}` (no `symbol` key).

The chart consumer in `dashboards/pipeline_health_charts.py:98` was untouched and
still groups rows by `row.get("symbol") or "Unknown"`. With no `symbol` key, every
row falls into the `"Unknown"` bucket, producing a single mislabelled trace per phase.

The test file `unit_tests/dashboards/test_pipeline_health_queries.py` was also
rewritten in the same commit to assert the new 2-tuple shape — making the regression
invisible to CI from that point forward.

### Why this passed code review and CI

1. **Tests were treated as the source of truth**: the failing assertion said "2-tuple
   expected", so the implementing agent changed production code to emit 2-tuples. This
   inverts the actual contract — the test is supposed to mirror the production behavior
   the *real consumers* depend on, not the other way around.

2. **No blast-radius check on the producer**: `fetch_phase_timeseries` has exactly one
   runtime consumer (`_build_timeseries_figure` in a sibling file). A 30-second
   `grep`/`jcodemunch find_references` would have surfaced the consumer's
   `row.get("symbol")` access and made the regression obvious.

3. **No cross-layer integration test**: no test feeds a realistic
   `fetch_phase_timeseries` row into `_build_timeseries_figure` and asserts the
   resulting trace name. Both layers had unit tests that mocked each other away;
   nothing covered the seam.

4. **The behavior change was buried inside a test-repair commit**: the commit message
   ("removed symbol column from SQL SELECT/GROUP BY") technically disclosed it, but
   the framing of the PR ("fix tests") gave reviewers no reason to suspect a runtime
   contract change. Test-repair PRs are assumed by reviewers to be no-op for production.

5. **The original task framing was "fix 5 failing tests"** — a deliverable that biases
   the agent toward "minimum diff to make pytest green" rather than "is this test still
   correct?".

### Why the test was originally failing (relevant for fix design)

The `fetch_phase_timeseries` parameter shape had churned (`bucket_interval: str` vs
`bucket_hours: int`), phase 8 was added, and the test's mocked `fetchall` shape had
drifted. The legitimate test-repair work was to update the parameter type and the
phase count. The illegitimate side-effect was rewriting the SQL to drop `symbol`.
Those two changes should never have lived in the same commit.

### Failure class

"Test-driven regression by contract shrinkage." The agent treated a failing test as a
specification document instead of a stale mirror, and silently narrowed the runtime
contract until the mirror was correct again. The consumers — which are the *real*
specification — were never consulted.

---

## Architecture Plan

### ADRs

- ADR-001 (new): "Source-of-truth discipline for test repair: tests mirror production
  contracts; shrinkage requires explicit authorization." This is the first ADR for
  the leafcutter-ai package — the `docs/architecture/adrs/` folder does not yet exist
  and will be scaffolded by this ticket (folder + ADR-001 + a one-page `README.md`
  index). The ADR codifies the cross-cutting policy that a failing test is evidence
  of drift, not a mandate to change production behavior, and that any contract
  narrowing requires explicit authorization.

### Why scaffold the ADR folder here

The policy needs a durable home that future leafcutter consumers can cite. A new
ADR-001 in the leafcutter-ai canonical docs tree gives every consumer a stable URL
to reference. Scaffolding the folder + index in this same ticket keeps the ADR's
provenance attached to the incident that motivated it, which is the convention used
in consumer repos (e.g. bybit-trader's ADR-028 sits beside the procedure it
documents).

---

## Acceptance Criteria

```gherkin
Given the test-writer agent template is updated with Source-of-Truth Discipline rules
When an agent is invoked on a "fix failing tests" task that would remove a field from a return value
Then the agent must classify the failure before touching production code
  And enumerate every consumer of the changed function via blast-radius query
  And either restore the test to match production or surface a (status: handoff) to split the commit

Given the python-coder agent template has a parallel contract-shrinkage guard
When python-coder would narrow a function return shape to satisfy a downstream consumer or test
Then it must state its classification and enumerate consumers before proceeding
  And block the change if any consumer reads a field the proposed fix would remove

Given a dry-run scenario is documented in this ticket
When a future reader reviews how the May-19 incident would have been handled under the new rules
Then the scenario shows the agent classifying the failure as "test drift (test stale, production correct)"
  And running a blast-radius query that returns _build_timeseries_figure as a consumer
  And emitting (status: handoff) with a note that removing symbol is a contract change requiring a separate ticket
  And NOT modifying fetch_phase_timeseries in the test-repair commit

Given the adr-author agent authors ADR-001
When the ADR is approved
Then it documents the policy that tests are mirrors of production contracts
  And that contract shrinkage requires allow_contract_shrinkage: true in the ticket body
  And docs/architecture/adrs/README.md exists as a one-page ADR index
```

## Sign-offs

- [ ] architect-review
- [ ] adr-author
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### architect-review

- [ ] Review the six Source-of-Truth Discipline rules for consistency with existing
      agent protocol patterns (signoff skill, blast-radius convention from
      jcodemunch / research-agent).
- [ ] Confirm whether the consumer-enumeration step should be gated by a `signoff`
      check or whether inline `## Comments` logging is sufficient.
- [ ] Classify whether this ticket warrants ADR-001 or whether the policy is
      already implied by existing leafcutter conventions. (Assessment: yes, warrants
      ADR-001 — this is a binding cross-agent invariant that future implementers
      across consumers will ask "why?" about, and leafcutter has no ADR-class
      governance doc yet.)
- [ ] Confirm scope: does `python-coder` also need the same guard? (Assessment: yes —
      `python-coder` implements production changes that are sometimes triggered by
      failing tests, and is the more dangerous agent for contract shrinkage.)
- [ ] Confirm the path for `docs/architecture/adrs/` (vs. e.g.
      `docs/conventions/adrs/`). Both are precedented in consumer repos; the
      `architecture/adrs/` location matches bybit-trader and most public ADR
      conventions and is the recommended target.

### adr-author

- [ ] Scaffold `docs/architecture/adrs/` folder and create
      `docs/architecture/adrs/README.md` as a one-page ADR index (heading + table:
      number, status, title, date).
- [ ] Author `docs/architecture/adrs/ADR-001-test-source-of-truth-discipline.md`.
- [ ] Title: "Tests are mirrors of production contracts; contract shrinkage during
      test repair requires explicit authorization."
- [ ] Context: the May-19 Pipeline Health regression in bybit-trader (a leafcutter
      consumer); test-repair commits that silently narrow runtime contracts; the
      "minimum diff to make pytest green" bias.
- [ ] Decision: (a) a failing test is a question about which side has drifted;
      (b) the agent must classify the failure before touching production code;
      (c) any narrowing of a return shape, function signature, SQL result, or
      dictionary structure that has consumers requires a separate commit/ticket;
      (d) `allow_contract_shrinkage: true` in the ticket body is the explicit
      authorization gate; (e) cross-layer seam tests are mandatory when the
      function under repair sits at a layer boundary.
- [ ] Consequences: test-repair work may produce (status: handoff) exits more
      frequently across all leafcutter consumers; this is the correct behavior,
      not a defect.

### Prompting changes — templates/agents/test-writer.md

Add a new `## Source-of-Truth Discipline` section to the `test-writer` agent
template at `templates/agents/test-writer.md`, inserting it **before**
`## Step 1 — Pre-flight Reads`. The section must contain the following six rules:

**Rule 1 — A failing test is a question, not an answer.**
Before mutating production code to make a test pass, classify the failure as exactly
one of:
- **(a) test drift**: production is correct; the test is stale (parameter rename,
  new phase added, mock shape drifted). Fix: update the test only.
- **(b) production drift**: production introduced a bug; the test correctly catches
  it. Fix: fix production; test stays.
- **(c) consumer drift**: both the test and production are stale relative to the
  real downstream consumer. Fix: restore production to match the consumer; update
  the test to match restored production.

State the classification explicitly in `## Comments` before making any change.
The comment must use the exact label: `(classification: test_drift | production_drift | consumer_drift)`.

**Rule 2 — Consumer enumeration is mandatory before contract changes.**
If the proposed fix would narrow or widen the shape of any return value, function
signature, SQL result, or dictionary structure associated with the function under
repair, spawn `research-agent` with a `jcodemunch get_blast_radius` or
`find_references` query on the producing function. List every consumer in
`## Comments`. If any consumer reads a field the proposed fix would remove, the
change is **blocked** — emit `(status: handoff)` and stop. Do not proceed without
human review of the consumer.

**Rule 3 — Cross-layer seam test required.**
If the function under repair sits at a layer boundary (data layer → chart/UI layer,
SQL → ORM, API handler → frontend, agent producer → agent consumer), add or update
at least one integration-style test that pipes a representative producer output
directly into the consumer and asserts the consumer's observable behavior (e.g.
trace names, field presence, rendered labels). Unit tests that mock both sides of
the seam are insufficient as the sole coverage.

**Rule 4 — Test-repair commits must not change production behavior.**
If the classification concludes that production code must change, split the work:
- Commit 1 (or a separate ticket): the production change with its own justification,
  blast-radius analysis, and sign-off chain.
- Commit 2: the test-only assertion fix.

Emit `(status: handoff)` in `## Comments` listing the required split, and stop.
Do not bundle a production behavior change into a test-repair commit.

**Rule 5 — Prefer expanding the test over shrinking production.**
When the classification is ambiguous, the test is the cheaper thing to change.
Shrinking a production contract requires explicit user authorization recorded in
the ticket body as `allow_contract_shrinkage: true`. Absent that flag, assume the
test is stale and restore it to match the production contract.

**Rule 6 — The `tests` array must reference the consumer contract.**
Before writing any test for a function that has downstream consumers, confirm that
the test assertions cover what the *consumer* reads from the producer's output — not
just internal fields the producer happens to emit. If the `## Test Requirements`
section was authored without consumer context, propose an expansion before writing
the test.

Also update the frontmatter `description` field to add the phrase
"consumer-aware test repair" and "source-of-truth discipline" so that
ticket-supervisor selects this agent correctly for test-repair tasks.

### Prompting changes — templates/agents/python-coder.md

Add a condensed version of Rules 1, 2, and 4 to `templates/agents/python-coder.md`
under a new section titled `## Contract-Shrinkage Guard`, placed immediately before
the `## Sign-off` block. The section must state:

- Before narrowing any return shape, function signature, SQL result, or dictionary
  structure, run `research-agent get_blast_radius` on the function and enumerate
  consumers in `## Comments`.
- If a consumer reads a field the change would remove, block and emit
  `(status: handoff)`. Do not proceed without explicit user authorization
  (`allow_contract_shrinkage: true` in the ticket body).
- If the narrowing was requested to satisfy a failing test, classify the failure
  per the test-writer Source-of-Truth Discipline (Rule 1) and confirm the
  classification before proceeding.

---

## Dry-Run Scenario: How the May-19 Incident Would Have Been Handled Under the New Rules

**Task given to test-writer**: "Repair 5 failing tests in
`unit_tests/dashboards/test_pipeline_health_queries.py`."

**Failure observed**: `test_fetch_phase_timeseries` fails because the mock
`fetchall` returns 3-tuples `(bucket, symbol, count)` but the assertion expects
2-tuples.

**Step under Rule 1 — Classification**:
The agent examines `fetch_phase_timeseries` in `dashboards/pipeline_health_data.py`
and the test. The production function executes `SELECT bucket, symbol, COUNT(...)
GROUP BY 1, 2` and returns 3-tuples. The test was authored expecting 2-tuples — the
test is stale. Classification: **(a) test drift**. The agent records in `## Comments`:
`(classification: test_drift)` — "production SELECT still emits bucket+symbol+count;
test mock was authored with wrong shape."

**Step under Rule 2 — Consumer enumeration** (triggered because the agent considers
whether to change production to match the test instead):
The agent is tempted to take the "minimum diff" path of removing `symbol` from the
SQL. Rule 2 fires: before doing so, spawn `research-agent` with
`jcodemunch find_references("fetch_phase_timeseries")`. Result:
`_build_timeseries_figure` in `dashboards/pipeline_health_charts.py:98` calls
`row.get("symbol") or "Unknown"`. Consumer reads `symbol`. Change is **blocked**.

**Outcome under Rule 5 — Prefer expanding the test**:
Since the classification is `test_drift` and the consumer confirms the 3-tuple contract
is live, the agent updates the test mock to return 3-tuples and the assertion to match.
It does NOT touch `fetch_phase_timeseries`. No contract shrinkage. No regression.

**Contrast with actual May-19 behavior**: The agent removed `symbol` from the SELECT
to satisfy the 2-tuple assertion. No consumer check. No classification. The fix made
pytest green but silently broke the dashboard.

---

## Risk & Safety

- Touches money? No.
- Touches data? No — agent prompt files and one new ADR doc only.
- Reversibility? Fully reversible: revert the template + ADR edits in the leafcutter-ai
  repo. The change has no runtime side effects in consumers until the next leafcutter
  release is tagged and consumers bump their submodule pin (and re-run `build.py`).
- Over-restriction risk: the consumer-enumeration step (Rule 2) fires only when a
  contract change is proposed. Pure assertion-value fixes (wrong expected number, wrong
  mock return count without changing production shape) are exempt. This limits
  false-positive thrash.
- Release path: after merge in leafcutter-ai, cut a new `vX.Y.Z` tag per the standard
  versioning flow; consumers pick up the new behavior on their next submodule bump.
