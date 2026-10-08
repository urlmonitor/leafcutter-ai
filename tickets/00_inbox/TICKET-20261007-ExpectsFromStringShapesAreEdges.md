---
title: "expects_from written as an AC id string, or a list of them, is a build-order edge"
status: todo
components:
  - ac_driven_dev
  - ac_store
created: 2026-10-07
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: contract_boundary
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - ac-store
  - epic-generation
  - dependencies
last_updated: 2026-10-07
files_touched:
  - scripts/ac_store/_gtfa_store.py
  - unit_tests/ac_store/test_expects_from_string_shapes.py  # new
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  llm-expert: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
---

# expects_from written as an AC id string, or a list of them, is a build-order edge

## Actor / Goal
In order that every producer an AC names in `expects_from` is built before that AC, we need the
shared `expects_from` reader to accept every shape the AC schema allows. Then a bare AC id string,
or a list of them, orders the epic and fills the ticket's `depends_on` exactly like the mapping form.

## Context
- **Root cause.** `_expects_from_ac_ids` (`scripts/ac_store/_gtfa_store.py:236-270`) handles two
  shapes only:
  - a mapping (:260-261);
  - a list, of which it keeps the mapping elements only (:262-263).
  Anything else gives no entries (:264-265). So `expects_from: BP-100e-1` and
  `expects_from: [TKT-500a-1]` give no edge.
- **The schema allows these shapes.** In `config/ac_store_schema.json`, `properties.expects_from` is
  `oneOf` null, string, object or array, and the string is described as "a free-form string AC ID".
  The reference says the same (`docs/reference/ac-schema.md:54`).
- **Real records (scan at ed2190fd3).** 63 records hold 66 string values: 49 bare strings and 14 lists
  that contain strings. Every value names an existing AC id. All are in the BP, INF and TKT trees.
  Examples:
  - BP-100e-2 `expects_from: BP-100e-1` (`build_pipeline/BP-100-reliable-builds/BP-100e-2.yaml:29`);
  - INF-500b-4 `expects_from: INF-500b-1` (`infrastructure/INF-500-operational-observability/INF-500b-4.yaml:26`);
  - TKT-500a-2 `expects_from: [TKT-500a-1]` (`ticket-creation/TKT-500-single-source/TKT-500a-2.yaml:25`);
  - TKT-500b-2 `expects_from: [TKT-500b-1, TKT-500c-2]`.
- **Effect.** These 66 edges are invisible to two readers:
  - the ticket generator's `depends_on` (`_build_ticket_depends_on`, `_gtfa_store.py:273-357`, which
    calls the normaliser at :324);
  - epic ordering, once EPIC-BuildToolingRunsThrough ticket 08 lands. Ticket 08 makes the epic index
    import this same normaliser (its AC-1: one definition).
- **Build after ticket 08 lands.** It is not listed in `depends_on` because ticket 08 lives in another
  folder.
- **Cycles.** A replay at ed2190fd3 that counts the string edges (with ticket 08's parent-link
  yield) finds the same 9 cyclic groups as without them. So this change adds no cycle to the scope
  of `TICKET-20261007-AcStoreExpectsFromCyclesResolved`. Re-run the replay if the store has changed.
- **Analogous code.** `_gtfa_contracts._as_contract_entries` (`scripts/ac_store/_gtfa_contracts.py:60-78`)
  normalises the same field the same way, for rendering contracts into the ticket body. The
  normaliser's docstring says it is "duplicated here in miniature rather than imported, to avoid the
  circular import" (`_gtfa_store.py:248-251`). It is not an ordering reader, so it is out of scope.
- **Decision: `check_ac_circular_deps` is not part of this ticket.** The cycle gate
  (`templates/scripts/commit_guardian/check_ac_circular_deps.py`) builds its graph from `depends_on`
  only (`_extract_depends_on`, :222). The file contains no `expects_from` at all (KI-ACD-20260929,
  remediation 1). It needs its own ticket, for four reasons:
  1. It is another component and file: a deployed commit_guardian hook with 506 raw lines, of which
     check-file-size measures 341 against the 400 limit. That leaves 59 measured lines before the
     crossing refusal.
  2. It must apply ticket 08's rule exactly, parent-link yield included. Otherwise it refuses the
     parent-link-only groups that ticket 08 resolves.
  3. It can only be switched on after `TICKET-20261007-AcStoreExpectsFromCyclesResolved` has removed
     the live groups. Before that, every commit that stages one of those ACs would be refused.
  4. It must import the shared ordering-edge function from the deployed
     `.leafcutter/scripts/commit_guardian/` layout. Ticket 06 had to solve the same deploy question
     for `_done_proof_composite`.
  That ticket is `TICKET-20261007-CircularDepsGateReadsExpectsFrom`. It can be switched on only after
  the data-fix ticket and ticket 08 have landed.

## Acceptance Criteria
- [ ] AC-1: `_expects_from_ac_ids("BP-100e-1")` returns `["BP-100e-1"]`. For a list, it returns every non-blank string element and every mapping's `ac_id`, in order: `["TKT-500b-1", {"ac_id": "TKT-500c-2"}]` gives both. Blank strings, `None` and other types are skipped. Results for a mapping and for a list of mappings are unchanged.
- [ ] AC-2: In a temporary store where consumer C has `expects_from: <P>` (a bare string) and no `depends_on` on P, `generate_ticket_from_ac.py` writes C's ticket with P's ticket in `depends_on`.
- [ ] AC-3: In the same store, `goal_to_epic --ids C,P` numbers P before C even when P's id sorts after C's. C's ticket `depends_on` is P's epic-prefixed `NN_TICKET-...` filename. The same holds for the list-of-strings form with two producers (the TKT-500b-2 shape).
- [ ] AC-4: For string-shaped records, the epic ordering index and the generator agree on each AC's in-set prerequisites, because both call the one normaliser.
- [ ] AC-5: The existing tests stay green: `unit_tests/ac_store/test_ki_acd_20260921_depends_on_expects_from.py`, `unit_tests/test_generate_ticket_from_ac.py`, `unit_tests/ac_store/test_bo_2600a_5_expects_from_edges.py` and `unit_tests/ac_store/test_bo_2600a_5_cycle_policy.py`.

## Test Requirements

```yaml
tests:
  - name: test_bare_string_and_string_list_shapes_yield_ac_ids
    location: unit_tests/ac_store/test_expects_from_string_shapes.py
    type: unit
    covers: [AC-1]
    description: |
      _expects_from_ac_ids over a bare string, a list of strings, a mixed list, a mapping, a list
      of mappings, blank strings and None. Strings yield their ids in order; the mapping results
      are unchanged. Red today: the string shapes return [].
  - name: test_bare_string_producer_lands_in_generated_ticket_depends_on
    location: unit_tests/ac_store/test_expects_from_string_shapes.py
    type: integration
    covers: [AC-2]
    description: |
      Temporary store shaped like BP-100e-1 / BP-100e-2. Run the real generate_ticket_from_ac.py.
      The consumer's ticket depends_on names the producer's ticket.
  - name: test_string_shaped_producer_is_built_first_in_the_epic
    location: unit_tests/ac_store/test_expects_from_string_shapes.py
    type: integration
    covers: [AC-3, AC-4]
    description: |
      goal_to_epic --ids over the same store, with the producer id sorting after the consumer's,
      and over a TKT-500b-2-shaped list with two producers. Producers get the lower NN_ numbers, the
      consumer's depends_on holds their epic-prefixed filenames, and the epic index's prerequisite
      sets equal the generator's.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_bare_string_and_string_list_shapes_yield_ac_ids | | |
| AC-2 | test_bare_string_producer_lands_in_generated_ticket_depends_on | | |
| AC-3 | test_string_shaped_producer_is_built_first_in_the_epic | | |
| AC-4 | test_string_shaped_producer_is_built_first_in_the_epic | | |
| AC-5 | (existing tests) | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

### test-writer
- [ ] Write `unit_tests/ac_store/test_expects_from_string_shapes.py` with a temporary store.

### python-coder
- [ ] `_gtfa_store._expects_from_ac_ids` (236-270): accept a bare string and string list elements. Keep
  one definition, which ticket 08's epic index imports. Do not add a copy.
- [ ] Update the normaliser's docstring and add a DECISION HISTORY entry.

### test-runner / pr-reviewer / commit
- [ ] Run the new file and the tests named in AC-5.

## Risk & Safety
- Touches money? No.
- Touches data? Newly generated tickets and epics only. A ticket generated from one of the 63 records
  now gets the dependency it always declared. Existing tickets are not rewritten.
- Reversibility: revert the commit.

## Out of Scope
- The cycle gate `check_ac_circular_deps.py` (`TICKET-20261007-CircularDepsGateReadsExpectsFrom`).
- Rendering string-form contracts in the ticket body (`_gtfa_contracts._as_contract_entries`).
- Rewriting the 63 records into the mapping form.
