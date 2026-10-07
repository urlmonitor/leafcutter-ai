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
  - unit_tests/ac_store/test_bo_2600a_5_cycle_policy.py  # new
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: needed
  llm-expert: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
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

## Design Decisions

Decision Kernel dec-46476988badbd5e6 (run run-e02f770927304a29), chosen by the user on
2026-10-07: "Parent link yields, other cycles fail naming the edges, plus a data-fix
ticket". It answers the pr-reviewer blocker: feeding `expects_from` into the epic graph
exposes 15 cyclic groups in the real store, 10 of them live.

1. **Ordering graph.** The epic ordering graph is `depends_on` plus `expects_from`, with one
   exception. A child's `depends_on` on its own structural parent
   (`ac_parent_id.derive_parent_id`) is not an ordering edge when the parent's `expects_from`
   names that child. The child is built first, because the parent link is hierarchy only
   and the parent's `expects_from` decides. This resolves 7 of the 15 groups without
   dropping any `expects_from` edge. Supporting facts: the AC schema requires a child's
   `depends_on` to list its parent (`docs/reference/ac-schema.md:623`), and the ticket
   generator already drops the structural parent from ticket `depends_on`
   (`_gtfa_store.py:323-325, 351-361`).
2. **Remaining cycles fail loudly.** Any other cycle fails generation with an error that names
   every AC on the cycle, including ACs outside the requested id set that the cycle passes
   through (`epic_dependencies.py:116-121` follows such ids). For each edge it names the
   field (`depends_on` or `expects_from`) and whether it is a structural-parent link, in the
   form `<owner> -> <prerequisite> (<field>, parent-link: <true|false>)`. The old message
   "Circular dependency detected: A -> B -> A" had no edge kinds and hid out-of-set ACs.
3. **Data fix is separate.** A separate data-fix ticket handles the remaining live cycles. It
   is not part of this ticket.

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
- [ ] AC-7: Parent link yields. In a cycle formed only by a child's `depends_on` on its own parent plus the parent's `expects_from` on that child, the child is ordered and numbered first, generation succeeds, and the parent's ticket `depends_on` lists the child's `NN_` ticket.
- [ ] AC-8: A remaining cycle fails with a full report. Generation exits non-zero (`--ids` raises `CyclicDependencyError`, goal mode exits 1). The message names every AC on the cycle, including out-of-set ACs, and for each edge its field and parent-link flag. No epic folder or ticket is written.

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
| AC-7 | test_bo_2600a_5_cycle_policy.py:test_ac7_parent_link_yields_child_built_first; test_ac7_yield_keeps_parent_link_when_parent_does_not_expect_child; test_ac7_index_drops_yielded_parent_edge_only | | |
| AC-8 | test_bo_2600a_5_cycle_policy.py:test_ac8_sibling_cycle_fails_naming_both_edges; test_ac8_cycle_through_out_of_set_ac_names_it; test_ac8_expects_from_only_cycle_names_both_edges | | |

## Implementation Tasks

### test-writer
- [ ] Write `unit_tests/ac_store/test_bo_2600a_5_expects_from_edges.py` with a temporary store shaped like DK-400a-1 / DK-400a-3 / DK-400a-4.

### python-coder
- [x] `epic_dependencies._build_depends_on_index` (41-70): add the `expects_from[].ac_id` entries through the shared normaliser.
- [x] `_gtfa_store.py`: expose the normaliser (`_expects_from_ac_ids`, 236) for import, if needed. Do not copy it.
- [x] `epic_tickets._translate_ticket_depends_on` (261-262): remove the early return on an empty list, and always write the epic's own list.
- [x] AC-7: in the epic ordering graph (`_build_depends_on_index` or the graph build), drop a child's `depends_on` edge on its own structural parent (`derive_parent_id`) when the parent's `expects_from` names that child. Keep every `expects_from` edge and every other parent link.
- [x] AC-8: make the cycle error name every AC on the cycle, including out-of-set ACs reached through `epic_dependencies.py:116-121`, and render each edge as `<owner> -> <prerequisite> (<depends_on|expects_from>, parent-link: <true|false>)`. The graph must keep edge kinds for this. Fail before any epic folder or ticket is written.

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

### 2026-10-06 12:00 — test-writer (status: ok)
feedback-id: (submit-failed)
Wrote unit_tests/ac_store/test_bo_2600a_5_expects_from_edges.py (5 tests, all drive the real goal_to_epic --ids generator or the real index/generator functions against a temp store; the real ticket_frontmatter_guard.validate is used). Strict run (AC_ENFORCE_STRICT=1): 5 failed, 0 errors, all by assertion. Fixtures use colon-free titles. Note: the child generator process prints a UnicodeDecodeError from its own reader thread (cp1252 byte 0x97); it does not affect the exit code and is noise in the failure messages.
red_baseline:
  - test_name: test_expects_from_edge_gets_epic_prefixed_depends_on
    file: unit_tests/ac_store/test_bo_2600a_5_expects_from_edges.py
    error: "AssertionError: ['01_TICKET-20261006-ZZEF-100a-1.md'] != ['TICKET-20261006-ZZEF-100a-1.md']"
  - test_name: test_producer_sorting_after_consumer_is_built_first
    file: unit_tests/ac_store/test_bo_2600a_5_expects_from_edges.py
    error: "AssertionError: '02' not less than '01'"
  - test_name: test_stale_depends_on_replaced_with_epic_list_or_empty
    file: unit_tests/ac_store/test_bo_2600a_5_expects_from_edges.py
    error: "AssertionError: Lists differ: [] != ['TICKET-LOOSE-300b-9.md']"
  - test_name: test_master_plan_table_shows_prefixed_name
    file: unit_tests/ac_store/test_bo_2600a_5_expects_from_edges.py
    error: "AssertionError: '01_TICKET-20261006-ZZEF-400a-1.md' not found in Master_Plan row for the consumer"
  - test_name: test_epic_index_and_generator_agree_on_prerequisites
    file: unit_tests/ac_store/test_bo_2600a_5_expects_from_edges.py
    error: "AssertionError: Items in the first set but not the second: 'ZZEF-500a-1' : ZZEF-500a-3"

### 2026-10-06 14:00 — python-coder (status: ok)
feedback-id: (submit-failed)
Summary: added `_gtfa_store._prerequisite_ac_ids(ac)` (depends_on + expects_from ac_ids, ordered, deduped), the one shared rule. `_build_ticket_depends_on` and `epic_dependencies._build_depends_on_index` both call it, so the epic graph now carries expects_from edges (ordering, cycle detection, Master_Plan names). `_translate_ticket_depends_on` no longer returns early on an empty list, so it writes the epic's own list, `[]` included. Out-of-epic edges are still filtered by the leaf set; cycle error text unchanged.
red_baseline_results: all 5 tests in test_bo_2600a_5_expects_from_edges.py green.
Strict (AC_ENFORCE_STRICT=1): 99 test files referencing the touched modules + test_goal_to_epic.py + test_master_plan_frontmatter_gates.py: 467 passed, 1 skipped, 1 xfailed, 4 failed. All 4 pre-existing (3 confirmed failing in build-tooling-done-proof at base: test_acd_1200a_14_i git_rev_parse fallback, test_acd_1200b_4 no_tty, test_tkt_500f_6_iii_a single predicate owner; the 4th is the known Windows backslash test_implemented_by_written_repo_relative).
Ratchet (check_file_size, before -> after): epic_dependencies 173 -> 173, epic_tickets 178 -> 175, _gtfa_store 195 -> 197; all under 400.
Unicode defect: not reproduced after the fix; candidate is the git rev-parse call at scripts/ac_store/_gtfa_paths.py:190-195 (text=True, no encoding), left for a follow-up ticket (file not changed here).

### 2026-10-06 15:00 — pr-reviewer (status: blocker)
feedback-id: (submit-failed)
HIGH: scripts/ac_store/epic_dependencies.py:73 (via _gtfa_store.py:_prerequisite_ac_ids) - feeding expects_from into the epic graph creates cycles in the real AC store. Replaying the merged rule over docs/acceptance-criteria: 0 cycles with depends_on only, 18 with the merge. 12 are mutual pairs where one AC's expects_from names an AC that depends_on it (e.g. BO-2900a-1 expects_from BO-2900a-2 while BO-2900a-2 depends_on BO-2900a-1; TQ-600a-2/-5; BP-1500d-1/-3; BO-4300a-1/-4300c-2; ACD-2500b-1/-1-i). Generating an epic over such a pair used to succeed and now raises CyclicDependencyError; the message ("Circular dependency detected: A -> B -> A", epic_dependencies.py:343) does not say which edge kind closed the cycle. Fix before commit: let depends_on win (drop an expects_from edge that would close a cycle, with a WARNING naming it) or name the edge kind in the error; add a test using a real mutual pair.
MEDIUM: scripts/ac_store/_gtfa_store.py:236-267 - _expects_from_ac_ids ignores a bare string and a list of strings; 63 real ACs use them (e.g. BP-100e-2 "expects_from: BP-100e-1", INF-500b-4, TKT-500a list form). Those edges stay unordered in both the index and the generator. Pre-existing, but this ticket now calls it "the one shared rule". Either accept str/list[str] in the extractor or record it as a known gap.
MEDIUM: scripts/ac_store/_gtfa_store.py:273 - the change has no DECISION HISTORY entry (epic_dependencies.py and epic_tickets.py do). 
LOW (suppressed in report except note): epic_tickets.py:~232 docstring still says "No-ops when ... raw_deps is empty".
OK: single merge site (_prerequisite_ac_ids called by both _build_ticket_depends_on and _build_depends_on_index; no copy left). Import seam: _gtfa_store.py and epic_dependencies.py are both in AC_STORE_DEPLOY_MAP (build_phases_ac_store.py:122, :227); no templates/ copy; _gtfa_store imports only stdlib, yaml, _gtfa_seams, _gtfa_constants, so no cycle. Translation: dep_graph is already restricted to the generated set, so the always-write [] never emits an out-of-epic name and keeps every in-epic prefixed name.
Follow-up note (UnicodeDecodeError): the _gtfa_paths.py:190-195 theory is probably wrong. git rev-parse --show-toplevel prints only the ASCII worktree path, and 0x97 is a valid cp1252 byte (em dash), so cp1252 cannot raise on it; a 0x97 failure fits a cp1252-encoded file or git output (log/diff text) being read as UTF-8 instead. Look for other text=True subprocess calls in the generator path.

### 2026-10-06 15:25 — test-runner (status: ok)

feedback-id: (submit-failed)

All AC_ENFORCE_STRICT=1. Only pre-existing failures; none introduced by this change.

- Command 1 (4 files): 29 passed, 1 failed (pre-existing: test_bo_2600a_5::test_implemented_by_written_repo_relative, Windows backslash path).
- Command 2 (116 test files referencing the symbols, -n auto): 667 passed, 2 skipped, 1 xfailed, 7 failed, all pre-existing: test_acd_1200a_14_i git_rev_parse fallback, test_acd_1200b_4 no_tty, test_tkt_500f_6_iii_a single_owner, test_bo_2600a_5 implemented_by repo_relative, and 3 perf-timing tests (test_readiness_gate, test_dependency_wiring, test_tree_traversal).
- Dry run a (DK-400 E1, 17 ids): exit 0, `Dry-run: would create`, no cycle. Order: DK-400a-1, a-1-i, a-2, a-3, a-3-i, a-3-ii, a-4, a-1-ii, c-1, c-1-i, c-1-ii, c-2, c-2-i, c-3, a-5, c-3-i, c-4.
- Dry run b (DK-400b + DK-400d minus d-5, plus c-5; 20 ids): exit 0, `Dry-run: would create`, no cycle. Order: b, b-1, b-2, b-2-i, b-2-ii, b-3, b-4, d, d-1, d-1-i, d-1-ii, d-2, d-2-i, d-2-ii, d-3, c-5, d-3-i, d-3-ii, d-3-iii, d-4.
- git status after dry runs: only the 5 staged changes; nothing written.

```yaml
completion_manifest:
  test_suite_executed: true
  all_tests_passing:
    result: false
    reason: "7 failures in command 2, all in the known pre-existing list (identical at base)"
    remediation: "none for this ticket"
  failure_report_structured: true
  dry_run_cycles: none
```

### 2026-10-07 07:12 — test-writer (status: ok)
feedback-id: (submit-failed)
Scope changed by dec-46476988badbd5e6 (see Design Decisions): added AC-7 and AC-8. New file `unit_tests/ac_store/test_bo_2600a_5_cycle_policy.py` (6 tests, sibling because the earlier file would pass 400 lines). Drives the real `goal_to_epic --ids` as a subprocess plus a direct `_build_depends_on_index` seam test, against a temp store, colon-free titles. Strict run: 5 failed by assertion, 1 passed at baseline (`test_ac7_yield_keeps_parent_link_when_parent_does_not_expect_child`, a narrowness guard against dropping parent links in general, KI-ACD-021; P waits on a later-sorting producer so a dropped link would reorder). The 5 earlier tests stay green. The edge-report format is pinned in the test module docstring.
red_baseline:
  - test_name: test_ac7_parent_link_yields_child_built_first
    file: unit_tests/ac_store/test_bo_2600a_5_cycle_policy.py
    error: "AssertionError: generation failed (cycle error from the parent depends_on plus parent expects_from)"
  - test_name: test_ac7_index_drops_yielded_parent_edge_only
    file: unit_tests/ac_store/test_bo_2600a_5_cycle_policy.py
    error: "AssertionError: 'ZZCP-630a' unexpectedly found in ['ZZCP-630a']"
  - test_name: test_ac8_sibling_cycle_fails_naming_both_edges
    file: unit_tests/ac_store/test_bo_2600a_5_cycle_policy.py
    error: "AssertionError: unexpectedly None : edge ZZCP-640a-1 -> ZZCP-640b-1 not reported"
  - test_name: test_ac8_cycle_through_out_of_set_ac_names_it
    file: unit_tests/ac_store/test_bo_2600a_5_cycle_policy.py
    error: "AssertionError: 'ZZCP-650b-1' not found in 'ERROR: Circular dependency detected: ZZCP-650a-1 -> ZZCP-650c-1 -> ZZCP-650a-1'"
  - test_name: test_ac8_expects_from_only_cycle_names_both_edges
    file: unit_tests/ac_store/test_bo_2600a_5_cycle_policy.py
    error: "AssertionError: unexpectedly None : edge ZZCP-660a-1 -> ZZCP-660b-1 not reported"

### 2026-10-07 08:00 — python-coder (status: ok)
feedback-id: (submit-failed)
Summary: AC-7 and AC-8 (dec-46476988badbd5e6). `epic_dependencies._scan_edges` builds `owner -> {prerequisite: field}` once per scan; a child's depends_on on its own structural parent (`derive_parent_id`, the generator's loader) is dropped when the parent's expects_from names that child, every other edge is kept. `_build_depends_on_index` is derived from it. `resolve_leaf_dependencies` returns a `DepGraph` (dict subclass) carrying the raw edges; `topological_sort` expands each collapsed cycle edge through out-of-set ACs and raises CyclicDependencyError with `<owner> -> <prereq> (<depends_on|expects_from>, parent-link: <true|false>)` per edge. Plain dicts keep the old message. Review mediums: DECISION HISTORY added in `_gtfa_store._prerequisite_ac_ids`; stale `_translate_ticket_depends_on` docstring corrected.
Strict results: cycle_policy + expects_from_edges + test_bo_2600a_5 + test_goal_to_epic + master_plan_frontmatter_gates: 35 passed, 1 failed (known Windows backslash test_implemented_by_written_repo_relative). 117 test files referencing the touched modules (-n auto): 673 passed, 2 skipped, 1 xfailed, 7 failed, all in the pre-existing list (git_rev_parse fallback, no_tty, single_owner, implemented_by backslash, and 3 perf-timing tests; test_dependency_wiring perf passes alone in 0.5s and is load-sensitive).
Real-store replay (docs/acceptance-criteria, SCC of size>1 over the new rule): 9 cyclic groups remain, 6 live (review predicted 8 and 6). Live: ACD-2500c-1/3; BO-2400a-1-i/2400f-3-ii/2400f-5-iii; BO-2900a-1/2; BO-2900b-1/b-3/c-1/c-4; BO-4300a-1/c-2; TQ-500g-1-vii/viii.
DK-400 E1 dry run (17 ids): exit 0, "Dry-run: would create", nothing written.
Ratchet (check_file_size, after): epic_dependencies 173 -> 232, epic_tickets 175, _gtfa_store 197, all under 400.

### 2026-10-07 09:00 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
Re-review after dec-46476988badbd5e6. Both earlier fixes landed (DECISION HISTORY in _gtfa_store._prerequisite_ac_ids; _translate_ticket_depends_on docstring). My first blocker is resolved. Both new test files pass (11 passed, strict).
HIGH: none.
MEDIUM: none.
LOW (not blocking):
- epic_dependencies.py:~100-108 (_scan_edges): the field label is "depends_on" when an edge is in both lists, and `dep not in (rec.get("depends_on") or [])` is a substring test if depends_on is a bare string. Cosmetic in the cycle report only.
- epic_dependencies.py:~383 (_cycle_message): when no raw path is found the fallback `[owner, prereq]` is silent; unreachable for a collapsed edge, but untested. No test covers a cycle with two or more out-of-set hops (BFS in _real_path handles it by reading) or a plain-dict caller (verified by hand: still "Circular dependency detected: a -> b -> a").
- AC-6 holds for out-of-set parents only (the fixture's parent is outside the leaves). For an in-set parent that does not expect the child, the index keeps the parent edge and the generator drops it. Harmless in an epic, because _translate_ticket_depends_on writes the index list, so ticket depends_on always equals the ordering graph (no ticket can depend on a later-numbered one or on nothing where order assumed something).
Checks: yield is exactly (child -> derive_parent_id(child) via depends_on, parent expects_from names child, child does not also expect the parent); same loader as the generator (_load_derive_parent_id_fn); grandparent, sibling and non-expecting parent edges are kept; result is independent of scan order (records dict is built first, each decision reads only records). The narrowness guard (case b) discriminates: dropping parent links in general would order the child before the parent, failing the assertion. Tests drive the real goal_to_epic --ids CLI and the real index.
Callers of topological_sort / resolve_leaf_dependencies (scripts/, templates/): epic_ac_phases.py:214-216 (catches CyclicDependencyError, prints, exit 1); epic_pipeline.py:220-226 (--ids, lets it raise); epic_master_plan.py and epic_phases.py (read dep_graph via .items()/.get(), fine for a dict subclass); goal_to_epic.py:143-147 (re-export, tests only); templates/agents/build-ac.md only mentions them in prose. No caller copies or serialises the graph; DepGraph breaks none.
Note: 6 live cyclic groups in the real store now fail loudly in generation; that is the accepted outcome, covered by the separate data-fix ticket.

### 2026-10-07 10:00 — test-runner (status: ok)

feedback-id: (submit-failed)

All AC_ENFORCE_STRICT=1, worktree build-tooling-generators. Only pre-existing failures; none introduced by AC-7/AC-8.

- Command 1 (5 files): 35 passed, 1 failed (pre-existing: test_bo_2600a_5::test_implemented_by_written_repo_relative).
- Command 2 (117 files, -n auto): 673 passed, 2 skipped, 1 xfailed, 7 failed, all pre-existing: test_acd_1200a_14_i git_rev_parse fallback, test_acd_1200b_4 no_tty, test_tkt_500f_6_iii_a single_owner, test_bo_2600a_5 implemented_by repo_relative, and perf-timing tests test_readiness_gate, test_dependency_wiring, test_tree_traversal.
- Dry run a (DK-400 E1, 17 ids): exit 0, would create, no cycle.
- Dry run b (DK-400b + DK-400d minus d-5 + c-5, 20 ids): exit 0, would create, no cycle.
- Dry run c (BO-2900a-1,BO-2900a-2): exit 1 with
  `ERROR: Circular dependency detected: BO-2900a-1 -> BO-2900a-2 -> BO-2900a-1`
  `BO-2900a-1 -> BO-2900a-2 (expects_from, parent-link: false)`
  `BO-2900a-2 -> BO-2900a-1 (depends_on, parent-link: false)`
- Dry run d (ACD-2500b-1,ACD-2500b-1-i; parent expects_from names child, child depends_on parent): exit 0, build order ACD-2500b-1-i then ACD-2500b-1. Extra check: INF-1100d-3,INF-1100d-3-ii exits 1 because of a genuine three-edge cycle (INF-1100d-3 -> INF-1100d-3-ii expects_from; INF-1100d-3-ii -> INF-1100d-3-i depends_on; INF-1100d-3-i -> INF-1100d-3 depends_on, parent-link: true), reported per edge as designed.
- git status after dry runs: only the staged changes; nothing written.

```yaml
completion_manifest:
  test_suite_executed: true
  all_tests_passing:
    result: false
    reason: "8 failures across commands 1 and 2 (1 overlaps), all in the known pre-existing list (identical at base)"
    remediation: "none for this ticket"
  failure_report_structured: true
  dry_runs:
    a_dk400_e1: "exit 0"
    b_dk400_b_d: "exit 0"
    c_bo2900a_cycle: "exit 1, per-edge message naming both edges"
    d_parent_link_yield: "exit 0, child ACD-2500b-1-i before parent ACD-2500b-1"
```

### 2026-10-07 07:33 — commit (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Subject: "fix(ac-driven-dev): order epics by expects_from edges and report cycles edge by edge"
