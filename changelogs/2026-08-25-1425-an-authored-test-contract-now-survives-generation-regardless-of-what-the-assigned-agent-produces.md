---
title: "An authored test contract now survives generation regardless of what the assigned agent produces"
date: "2026-08-25"
time: "14:25"
type: manual
components: 
  - ac_store
  - build_pipeline
  - testing_quality
summary: "generate_ticket_from_ac.py gated the whole ## Test Requirements section on whether the assigned agent declares produces: production_code, silently discarding 308 authored test descriptors across 85 AC records and reporting the discard as a PASS."
description: "The generator asked the agent registry a question that does not answer the one it needed. It gated the entire ## Test Requirements block on _computed_map_has_production_code_producer -- i.e. on whether some needed agent declares produces: production_code in config/agent_registry.json. Exactly nine agents do, all of them coders. Every other assigned agent -- llm-expert, documentation-expert, business-analyst, architecture-diagram-author, test-failure-triage, and most damningly test-writer itself -- caused the block to be omitted entirely, even when the it-po had authored a precise contract on the record. The two questions 'does this change production code?' and 'did somebody specify tests for it?' are orthogonal, and conflating them is the whole defect. Measured on the real store at 06ce1c43: 85 records carry an authored test_spec under a non-production_code agent, totalling 308 discarded descriptors; 65 are approved and 37 are approved-and-todo, i.e. buildable that day. By assigned agent: llm-expert 43, test-writer 13, documentation-expert 12, unassigned 9, business-analyst 4, test-failure-triage 2, architecture-diagram-author 2. Three consequences compounded. The descriptors vanished from the ticket. test-writer was never injected into the agents map, because that injection was keyed off the same classification, so even a ticket that had somehow carried the block would have dispatched nobody to satisfy it. And --verify reported the discard as '[PASS] non-code AC -- no test contract required', a success-shaped message over a silent loss, which is how 85 records reached approved with nobody noticing. The fix un-gates the AUTHORED route only: an authored test_spec now emits the block and injects test-writer and test-runner on any AC. The derive-from-criteria fallback stays gated on the production-code classification, so a doc-only or diagram-only ticket that never asked for tests does not start receiving invented stubs -- that boundary is pinned by two negative controls, without which this would trade a silent omission for a silent fabrication. test_required: false remains the explicit opt-out and still wins over a stale spec, now with a WARN when both are present. Worth recording honestly: 43 of the affected records are already marked done, but 42 of them ended up with a covering test tag anyway because tests were written by other routes. The real residual is one record, FIN-100c-7, which already sits inside KI-KM-002's pile. The exposure was far larger than the damage. This is a phantom-done vector in the tool that generates the work, and it selected for the worst possible population -- the ACs specifying the test and prompt infrastructure were precisely the ones whose test contracts were thrown away. Found while running /build-ac on BP-1100g-1 ('Every kind of proof the plan can ask for is a kind the test writer has been taught'), whose four descriptors covering the criterion, real_artifact, failure and reachability angles appeared zero times in its own generated ticket."
breaking: false
---

## Entry

Found by running `/build-ac` on `BP-1100g-1` and reading the output instead of the exit code.

**The defect.** `generate_ticket_from_ac.py:2473` gated `## Test Requirements` on `_computed_map_has_production_code_producer(agents)`. Only the nine coder agents declare `produces: production_code`, so an authored `test_spec` on any other AC was discarded — and `--verify` called it `[PASS] non-code AC — no test contract required`.

**Scale**, measured on the real store at `06ce1c43`:

| assigned agent | ACs | |
|---|---|---|
| `llm-expert` | 43 | |
| `test-writer` | 13 | ← the test author's own ACs |
| `documentation-expert` | 12 | |
| (unassigned) | 9 | |
| `business-analyst` | 4 | |
| `test-failure-triage` | 2 | |
| `architecture-diagram-author` | 2 | |
| **total** | **85** | **308 descriptors discarded** |

65 approved; 37 approved-and-todo.

**The fix**, in `scripts/ac_store/generate_ticket_from_ac.py`:

- new `_has_authored_test_spec(ac)` predicate
- the body gate becomes `has_code_producer or authored_spec`
- `_build_agents_map` gains `has_authored_test_spec` and injects `test-writer` + `test-runner` on it — a contract with nobody dispatched to write it is no better than no contract
- `--verify` acknowledges an authored contract on any AC, and warns when `test_required: false` and a `test_spec` are both present

**Bounded deliberately.** The derive-from-criteria fallback stays gated on the production-code classification. Two negative controls pin it: a doc/prompt AC with no authored spec must still emit nothing, and `test_required: false` must still suppress. Without them this would swap a silent omission for a silent fabrication.

**Tests** — `unit_tests/ac_store/test_authored_test_spec_survives_generation.py`, 7 tests. Anchor tests drive the real CLI as a subprocess against the real store; the store-wide gate discovers its records by scanning rather than naming them, so it cannot be satisfied by a fixture chosen to agree with the author. Red baseline captured before any production edit: 3 anchor tests and the store-wide sweep failed (the sweep naming all 37 offenders), both negative controls passed before and after.

**Residual, stated plainly.** 43 affected records are already `done`. 42 have a covering test tag anyway — tests were written by other routes despite the generator not asking. The one that does not, `FIN-100c-7`, already belongs to KI-KM-002's pile. No new known issue: this defect is fixed, not open.
