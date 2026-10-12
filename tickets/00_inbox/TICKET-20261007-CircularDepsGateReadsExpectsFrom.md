---
title: "Commit-time cycle gate reads expects_from with the same edge rule as goal_to_epic"
status: todo
components:
  - commit_guardian
  - ac_driven_dev
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
  - pre-commit
  - dependencies
  - cycles
last_updated: 2026-10-07
files_touched:
  - templates/scripts/commit_guardian/check_ac_circular_deps.py
  - scripts/ac_store/epic_dependencies.py
  - unit_tests/commit_guardian/test_check_ac_circular_deps_expects_from.py  # new
  - docs/known-issues/ac-driven-dev/open-high-ki-acd-20260929-cross-field-dependency-cycle-is-invisible-to-both-tools.md
agents:
  architect-review: needed
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

# Commit-time cycle gate reads expects_from with the same edge rule as goal_to_epic

## Actor / Goal
In order that a dependency cycle between `depends_on` and `expects_from` cannot be committed, we need
the commit-time cycle gate to build its graph with the edge rule `goal_to_epic` uses since
EPIC-BuildToolingRunsThrough ticket 08. That rule is `depends_on` plus `expects_from`, with the
parent-link yield, read through the shared helpers. Then the gate and the generator agree on which
edges exist, and a cycle is refused when it is introduced, not when an epic is generated.

## Context
- **The gap (KI-ACD-20260929, remediation 1).** The gate's only edge source is `_extract_depends_on`
  (`templates/scripts/commit_guardian/check_ac_circular_deps.py:222-254`), which `_build_depends_graph`
  (:257-324) calls for every record. The file contains no `expects_from` at all. So a cycle whose
  halves sit in different fields (`docs/known-issues/ac-driven-dev/open-high-ki-acd-20260929-cross-field-dependency-cycle-is-invisible-to-both-tools.md`)
  can be committed today. The KI says to share the rule: "One shared helper imported by both, not a
  second copy of `_expects_from_ac_ids`".
- **The rule to share: ticket 08.** Commit 49d6139f1 on `feature/build-tooling-generators` implements
  Decision Kernel dec-46476988badbd5e6 (chosen by the user, 2026-10-07). Line numbers are at that
  commit:
  - `_gtfa_store._prerequisite_ac_ids` (`scripts/ac_store/_gtfa_store.py:273`) returns `depends_on`
    plus the `expects_from` ac ids;
  - `_gtfa_store._expects_from_ac_ids` (:236) normalises `expects_from`;
  - `_gtfa_store._load_derive_parent_id_fn` (:132) loads `ac_parent_id.derive_parent_id`;
  - `epic_dependencies._scan_edges` (`scripts/ac_store/epic_dependencies.py:79-109`) applies the
    parent-link yield and records each edge's field. A child's `depends_on` on its own structural
    parent is not an edge when the parent's `expects_from` names that child.
  - `epic_dependencies._cycle_message` (:362) prints one line per edge:
    `<owner> -> <prerequisite> (<depends_on|expects_from>, parent-link: <true|false>)`.
- **What has to move.** `_scan_edges` loads the store from disk itself (`_load_records`, :58). The
  gate needs the same rule over its own record set: the shared store index plus the staged versions
  of changed files (`_build_depends_graph`, :257-329). So split `_scan_edges` into a load step and a
  records-to-edges function. `_scan_edges` and the gate then both call that function. Do not copy
  the yield logic into the gate.
- **Reaching the helpers from the deployed hook.**
  - `_gtfa_store.py`, `ac_parent_id.py` and `epic_dependencies.py` are in `AC_STORE_DEPLOY_MAP`
    (`scripts/build_phases_ac_store.py:122`, :167 and :227), so they ship to
    `.leafcutter/scripts/ac_store/`.
  - The gate runs from `.leafcutter/scripts/commit_guardian/` (`.pre-commit-config.yaml:326-332`).
  - `check_done_proof.py` reaches `ac_store` through `_ac_store_locator.ensure_ac_store_on_syspath()`
    (`templates/scripts/commit_guardian/_ac_store_locator.py:66`; `check_done_proof.py:122` and :128).
    Use the same route, and verify it from the deployed layout, not only from the dev tree.
  - The gate tolerates a missing PyYAML today (`_load_yaml_safe`, :154-192). The shared modules import
    `yaml` at module load (`epic_dependencies.py:33`, `_gtfa_store.py:38`).
- **Sequencing.**
  - **Switch it on only after `TICKET-20261007-AcStoreExpectsFromCyclesResolved` (the data fix) has
    landed.** Before that, every commit that stages a member of one of the 6 live groups, or of
    TQ-600a-2 / TQ-600a-5, would be refused, even for an unrelated edit.
  - Ticket 08 must also have merged, because the helpers live there.
  - `TICKET-20261007-ExpectsFromStringShapesAreEdges` is not a prerequisite. The gate gets the
    string shapes through the shared normaliser when that ticket lands.
  - None of these is in `depends_on`: they live in other folders.
- **Decision: cycles whose members are all done warn, they do not block.** After the data fix, 3
  non-live cyclic groups stay in the store, and every one of them needs an `expects_from` edge. A
  done AC is never generated, so such a cycle cannot break a build. If the gate refused it, any later
  edit to one of those records would be blocked. A cycle of `depends_on` edges only keeps today's
  behaviour (ACS-500e-1-i), whatever the members' status. The alternative is to fix those 3 groups in
  the data too; it was not chosen, because the data-fix scope says "no action needed unless re-opened".
- **AC coverage.** ACS-500e-1-i (`docs/acceptance-criteria/ac-store/ACS-500-shared-pattern-specs/ACS-500e-1-i.yaml`,
  L3, approved, `todo`) covers `depends_on` cycles only. Its message, "Circular dependency detected:
  PTN-010 -> PTN-020 -> PTN-010", and "the error names all ACs in the cycle" must keep holding. No AC
  covers `expects_from` at the gate, so the ACs below are ticket-local.
- **Size.** The gate has 506 raw lines, and check-file-size measures 341 of them against the 400
  limit (it skips triple-quoted text). That leaves 59 measured lines before the crossing refusal, so
  keep the gate's own logic small. `_extract_depends_on` can go once the shared rule replaces it,
  which frees lines. The existing test file `unit_tests/commit_guardian/test_check_ac_circular_deps.py`
  measures 295 of 400, so the new tests go in a new file. `epic_dependencies.py` is the generators
  branch's version; measure it after ticket 08 lands.

## Acceptance Criteria
- [ ] AC-1: The gate builds its graph with ticket 08's edge rule: `depends_on` plus `expects_from`, in every shape the shared normaliser accepts, with the parent-link yield. It is computed by a function imported from `scripts/ac_store` (no copy), over the store with the staged versions applied.
- [ ] AC-2: A cross-field cycle through a staged AC is refused with exit 1 when at least one member is not done. The TQ-600a-2 / -5 shape is an example: A `depends_on` B, and B `expects_from` A. The message keeps the summary line `Circular dependency detected: A -> B -> A`, and adds one line per edge in ticket 08's format.
- [ ] AC-3: A child whose `depends_on` names its own parent, while the parent's `expects_from` names the child, is not refused.
- [ ] AC-4: A cycle that needs an `expects_from` edge and whose members are all done is printed as a warning, naming its edges, and the commit passes. A cycle of `depends_on` edges only is refused as today, whatever the members' status.
- [ ] AC-5: If the shared helpers cannot be imported, the gate still fails open (exit 0). Its stderr line names the cause, so the degradation is never silent. The same applies to any other unexpected error (:498-506).
- [ ] AC-6: Once the data fix has landed, the gate exits 0 when run from the deployed `.leafcutter/scripts/commit_guardian/` with every AC file in the real store given through `HOOK_TEST_FILES`. KI-ACD-20260929 records remediation 1 as done, citing this ticket.

## Test Requirements

```yaml
tests:
  - name: test_cross_field_cycle_through_a_staged_ac_is_refused_edge_by_edge
    location: unit_tests/commit_guardian/test_check_ac_circular_deps_expects_from.py
    type: integration
    covers: [AC-1, AC-2]
    description: |
      Temporary store: A (todo) has depends_on [B]; B (todo) has expects_from [{ac_id: A}]. Stage A
      through HOOK_TEST_FILES and run the real gate entry point (run_hook.py). Exit 1; stderr has
      "Circular dependency detected: A -> B -> A" (or B -> A -> B) and both edge lines, with field
      and parent-link flag. Red today: exit 0, because expects_from is not read.
  - name: test_parent_link_that_yields_is_not_refused
    location: unit_tests/commit_guardian/test_check_ac_circular_deps_expects_from.py
    type: integration
    covers: [AC-3]
    description: |
      Parent P has expects_from [{ac_id: P-1}]; child P-1 has depends_on [P]. Stage P-1. Exit 0.
      This guards against a gate that reads expects_from without the yield.
  - name: test_all_done_cross_field_cycle_warns_and_passes
    location: unit_tests/commit_guardian/test_check_ac_circular_deps_expects_from.py
    type: integration
    covers: [AC-4]
    description: |
      The cycle of the first test with both members done: exit 0, and stderr names the cycle as a
      warning. The same with depends_on edges only (both members done): exit 1, as today.
  - name: test_gate_runs_the_shared_rule_from_the_deployed_layout
    location: unit_tests/commit_guardian/test_check_ac_circular_deps_expects_from.py
    type: integration
    covers: [AC-1, AC-5]
    description: |
      Run the deployed .leafcutter/scripts/commit_guardian/check_ac_circular_deps.py over the
      cross-field fixture: refused, which proves the ac_store helpers resolved from the deployed
      layout. Then run a copy whose ac_store folder cannot be found: exit 0, and stderr names the
      missing helpers.
  - name: test_real_store_passes_the_gate
    location: unit_tests/commit_guardian/test_check_ac_circular_deps_expects_from.py
    type: integration
    covers: [AC-6]
    description: |
      Pass every docs/acceptance-criteria/**/*.yaml through HOOK_TEST_FILES to the deployed gate:
      exit 0. Red until the data fix lands; it then guards the switch-on.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_cross_field_cycle_through_a_staged_ac_is_refused_edge_by_edge; test_gate_runs_the_shared_rule_from_the_deployed_layout | | |
| AC-2 | test_cross_field_cycle_through_a_staged_ac_is_refused_edge_by_edge | | |
| AC-3 | test_parent_link_that_yields_is_not_refused | | |
| AC-4 | test_all_done_cross_field_cycle_warns_and_passes | | |
| AC-5 | test_gate_runs_the_shared_rule_from_the_deployed_layout | | |
| AC-6 | test_real_store_passes_the_gate | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

### architect-review
- [ ] Confirm the split of `_scan_edges` (load step, records-to-edges function) and the import route
  from the deployed commit_guardian folder into `ac_store`.

### test-writer
- [ ] Write `unit_tests/commit_guardian/test_check_ac_circular_deps_expects_from.py`. Keep the existing
  `unit_tests/commit_guardian/test_check_ac_circular_deps.py` green.

### python-coder
- [ ] `epic_dependencies.py`: split `_scan_edges` so the edge rule takes a records mapping. Ticket 08's
  callers keep their behaviour.
- [ ] `check_ac_circular_deps.py`: reach `ac_store` through `ensure_ac_store_on_syspath()`, build the
  graph with the shared function over the index plus staged versions, render the edge lines, and
  apply the all-done warning rule (AC-4). Drop `_extract_depends_on` if nothing else uses it. Stay
  within 400 measured lines, and add a DECISION HISTORY entry.
- [ ] Run `python scripts/build.py` so the deployed copies match, and stage every tracked output it
  changes.
- [ ] Update KI-ACD-20260929: remediation 1 done (AC-6).

### test-runner / pr-reviewer / commit
- [ ] Run the new file, `unit_tests/commit_guardian/test_check_ac_circular_deps.py` and ticket 08's tests
  (`unit_tests/ac_store/test_bo_2600a_5_expects_from_edges.py`, `unit_tests/ac_store/test_bo_2600a_5_cycle_policy.py`).

## Risk & Safety
- Touches money? No.
- Touches data? No, but it changes which commits are refused. Landing it before the data fix would
  block commits that stage any member of a live group.
- Reversibility: revert the commit.

## Out of Scope
- Fixing the cycles in the data (`TICKET-20261007-AcStoreExpectsFromCyclesResolved`).
- String-shaped `expects_from` (`TICKET-20261007-ExpectsFromStringShapesAreEdges`).
- KI-ACD-20260929 remediation 2 (the generator refusing when it drops a record's only edge).
