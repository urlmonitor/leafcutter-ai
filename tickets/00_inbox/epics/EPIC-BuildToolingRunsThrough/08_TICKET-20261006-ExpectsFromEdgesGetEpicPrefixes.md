---
title: "expects_from edges are wired into the epic with epic-prefixed ticket names"
status: todo
components:
  - ac_driven_dev
  - ac_store
created: 2026-10-06
depends_on: []
priority: high
complexity: medium
roadmap_phase: phase_1
advances_current_outcome: true
source_ac: BO-2600a-5
ac_traceability:
  id: BO-2600a-5
  path: docs/acceptance-criteria/build-orchestration/BO-2600-connected-build-set/BO-2600a-5.yaml
requires_diagram: false
requires_adr: false
change_target:
  - code
risk_surface: contract_boundary
files_touched:
  - scripts/ac_store/epic_dependencies.py
  - scripts/ac_store/epic_tickets.py
  - scripts/ac_store/_gtfa_store.py
  - unit_tests/ac_store/test_bo_2600a_5_expects_from_edges.py  # new
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  llm-expert: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: not_needed
  status-checker: not_needed
---

# 08: expects_from edges are wired into the epic with epic-prefixed ticket names

## Actor / Goal

As the epic generator, I want a prerequisite declared only through `expects_from` to
become a real edge in the epic's dependency graph, and to be written as the
producer's epic-prefixed ticket filename. Then build order is correct by design
rather than by alphabetical luck. The build driver can resolve every `depends_on`
entry, and no generated ticket needs a hand fix.

## Context

Part of EPIC-BuildToolingRunsThrough (design section 6b). Restores approved
BO-2600a-5: "each generated ticket's depends_on references co-located ticket files
(AC-id -> ticket-file translation) so ticket_frontmatter_guard passes".

**Root cause (checked against the store)**
- Exactly two records are affected: DK-400a-3 and DK-400a-4 have `depends_on: [DK-400a]` (their L1 parent, outside the set) and `expects_from: [DK-400a-1]`. They are tickets 04 and 07 of EPIC-ABundledRequestThatRoutingTurnsAwayIs, the two that scaffold commit 7d593952e fixed by hand.
- The generator's `_build_ticket_depends_on` (`scripts/ac_store/_gtfa_store.py:273-357`) reads `depends_on` plus `expects_from`, drops the parent, and writes the **loose** inbox ticket's unprefixed name (347-349).
- `scripts/ac_store/epic_dependencies.py::_build_depends_on_index` (41-70) reads only `depends_on`, so the epic dependency graph has no edge.
- `scripts/ac_store/epic_tickets.py::_translate_ticket_depends_on` then returns early on an empty list (261-262), leaving the generator's value in place.
- Master_Plan's table re-reads ticket frontmatter (`scripts/ac_store/epic_master_plan.py:81-83`), so it showed the same names. The comment at line 82 is stale; ticket 09 fixes it.

**Consequences**
- Build order for such pairs is right only by alphabetical luck. A producer that sorts after its consumer is dropped with only a warning.
- At build time `resolveDependsOnPath` (`templates/workflows-js/build-feature.js:1827-1833`) cannot resolve the name, so the ticket is withheld for the whole run.

**Fix**
- The index reads `depends_on` plus `expects_from[].ac_id`, using the same normaliser as `_gtfa_store._expects_from_ac_ids` (236). Use one shared function, imported, not copied.
- `_translate_ticket_depends_on` always writes the epic's own list, `[]` when it is empty.

**Relation to `tickets/00_inbox/TICKET-20261005-GoalToEpicKeepsOutOfEpicDependencies.md`.**
That ticket extends the function this ticket changes (both touch
`epic_dependencies.py`), and its out-of-epic report must include `expects_from`-only
edges. So this ticket lands first.

## Constraints

- **Test placement.** The design puts these tests in the same files as ticket 07. `unit_tests/build_orchestration/test_bo_2600a_5.py` measures 570 / 400, so the ratchet refuses growth. Also, sharing a file with ticket 07 would stop the two running in parallel. The tests therefore go in a new file, `unit_tests/ac_store/test_bo_2600a_5_expects_from_edges.py`.
- Python sizes (measured / limit):
  - `epic_dependencies.py` 173 / 400;
  - `epic_tickets.py` 178 / 400;
  - `_gtfa_store.py` 195 / 400.
- Do not edit `epic_master_plan.py` here; ticket 09 owns it.

## Acceptance Criteria

- [ ] AC-1: `_build_depends_on_index` includes an edge for every `expects_from` entry. It normalises entries with the same function the generator's `_expects_from_ac_ids` uses (one definition).
- [ ] AC-2: For a record shaped like DK-400a-3 (`depends_on: [its L1 parent, outside the set]`, `expects_from: [a sibling in the set]`), the generated epic ticket's `depends_on` is `["01_TICKET-…"]`, the producer's epic-prefixed filename. The real `ticket_frontmatter_guard` accepts it.
- [ ] AC-3: A producer whose id sorts after its consumer is still placed before it in build order, and no `expects_from` edge is dropped.
- [ ] AC-4: `_translate_ticket_depends_on` always writes the epic's own list, `[]` when the AC has no in-set prerequisites, replacing any stale generator value.
- [ ] AC-5: The generated Master_Plan's ticket table shows the prefixed names for these edges.
- [ ] AC-6: For the same records, the epic index and the generator agree on each AC's in-set prerequisite set.

## Test Requirements

```yaml
tests:
  - name: test_expects_from_edge_gets_epic_prefixed_depends_on
    file: unit_tests/ac_store/test_bo_2600a_5_expects_from_edges.py
    covers:
      - BO-2600a-5
    asserts: >-
      In a temporary store shaped like DK-400a-1 / DK-400a-3 (the consumer has
      depends_on [L1 parent] and expects_from [the producer]),
      build_epic_from_ids writes the consumer ticket with depends_on equal to
      the producer's "NN_TICKET-..." epic filename, and the real
      ticket_frontmatter_guard.validate returns no errors for it.
    framework: pytest
    type: integration
    angle: criterion
  - name: test_producer_sorting_after_consumer_is_built_first
    file: unit_tests/ac_store/test_bo_2600a_5_expects_from_edges.py
    covers:
      - BO-2600a-5
    asserts: >-
      With a producer id that sorts alphabetically after its consumer and an
      edge only through expects_from, the producer's ticket number is lower
      than the consumer's, and no "dependency entry ... from depends_on or
      expects_from" warning is logged.
    framework: pytest
    type: integration
    angle: boundary
  - name: test_stale_depends_on_replaced_with_epic_list_or_empty
    file: unit_tests/ac_store/test_bo_2600a_5_expects_from_edges.py
    covers:
      - BO-2600a-5
    asserts: >-
      A generated ticket whose depends_on holds a loose, unprefixed name ends
      with the epic's own list. An AC with no in-set prerequisite ends with
      depends_on [] rather than the generator's value.
    framework: pytest
    type: integration
    angle: failure
  - name: test_master_plan_table_shows_prefixed_name
    file: unit_tests/ac_store/test_bo_2600a_5_expects_from_edges.py
    covers:
      - BO-2600a-5
    asserts: >-
      The generated Master_Plan.md "Depends On" column for the consumer row
      shows the producer's epic-prefixed filename, not the loose inbox name.
    framework: pytest
    type: integration
    angle: real_artifact
  - name: test_epic_index_and_generator_agree_on_prerequisites
    file: unit_tests/ac_store/test_bo_2600a_5_expects_from_edges.py
    covers:
      - BO-2600a-5
    asserts: >-
      For each record in the fixture store, the in-set prerequisite ids from
      _build_depends_on_index equal those the generator's
      _build_ticket_depends_on resolves (depends_on plus expects_from, parent
      dropped).
    framework: pytest
    type: unit
    angle: seam
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_epic_index_and_generator_agree_on_prerequisites | | |
| AC-2 | test_expects_from_edge_gets_epic_prefixed_depends_on | | |
| AC-3 | test_producer_sorting_after_consumer_is_built_first | | |
| AC-4 | test_stale_depends_on_replaced_with_epic_list_or_empty | | |
| AC-5 | test_master_plan_table_shows_prefixed_name | | |
| AC-6 | test_epic_index_and_generator_agree_on_prerequisites | | |

## Implementation Tasks

### test-writer
- [ ] Write `unit_tests/ac_store/test_bo_2600a_5_expects_from_edges.py` with a temporary store shaped like DK-400a-1 / DK-400a-3 / DK-400a-4.

### python-coder
- [ ] `epic_dependencies._build_depends_on_index` (41-70): add the `expects_from[].ac_id` entries through the shared normaliser.
- [ ] `_gtfa_store.py`: expose the normaliser (`_expects_from_ac_ids`, 236) for import, if needed. Do not copy it.
- [ ] `epic_tickets._translate_ticket_depends_on` (261-262): remove the early return on an empty list, and always write the epic's own list.

### test-runner / pr-reviewer / commit
- [ ] Run the new file, `unit_tests/build_orchestration/test_bo_2600a_5.py`, `unit_tests/ac_store/test_tkt_017_epic_depends_on_resolves.py` and `unit_tests/ac_store/test_epic_folder_assembly.py`.

## Risk & Safety

- Touches money? No.
- Touches data? Only newly generated tickets. Existing epics are not rewritten.
- Reversibility: revert the commit.

## Out of Scope

- Reporting out-of-epic dependencies (TICKET-20261005).
- Master_Plan frontmatter, and the stale comment at `epic_master_plan.py:82` (ticket 09).
- Re-generating EPIC-ABundledRequestThatRoutingTurnsAwayIs (already fixed by hand).

## Comments

_(Append-only log — leave blank when authoring.)_
