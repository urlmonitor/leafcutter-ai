---
title: "goal_to_epic --ids honours --dry-run and writes nothing"
status: todo
components:
  - ac_driven_dev
created: 2026-10-06
depends_on: []
priority: medium
complexity: low
roadmap_phase: phase_1
advances_current_outcome: true
source_ac: ACD-1200a-3-iii
ac_traceability:
  id: ACD-1200a-3-iii
  path: docs/acceptance-criteria/ac-driven-dev/ACD-1200-goal-to-epic/ACD-1200a-3-iii.yaml
requires_diagram: false
requires_adr: false
change_target:
  - code
risk_surface: internal
files_touched:
  - scripts/goal_to_epic.py
  - scripts/ac_store/epic_cli.py
  - scripts/ac_store/epic_pipeline.py
  - unit_tests/test_goal_to_epic.py
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

# 07: goal_to_epic --ids honours --dry-run and writes nothing

## Actor / Goal

As someone planning an epic from an explicit id list, I want
`goal_to_epic.py --ids <ids> --dry-run` to show the build order and the epic it
would create, without writing anything. Then I can check the order, the name and any
cycles before committing to the real run.

## Context

Part of EPIC-BuildToolingRunsThrough (design section 6a). Keeps ACD-1200a-3-iii: the
dry-run and the real run report a byte-identical epic name. Also serves BO-2600a-5,
the `--ids` entrypoint.

**Root cause**
- `scripts/goal_to_epic.py:257-259` calls `_run_ids_mode(args.ids, ac_store_root, inbox_dir)` and drops `args.dry_run`.
- Neither `scripts/ac_store/epic_cli.py::_run_ids_mode` (136-167) nor `scripts/ac_store/epic_pipeline.py::build_epic_from_ids` (175-267) has a dry-run parameter.
- So a "dry run" with `--ids` writes:
  - the tickets, through the generator, which also writes `implemented_by` into the AC YAML (`epic_pipeline.py:229`);
  - the `implemented_by` repoint (232), the loose-copy removal (243), the folder (251) and the Master_Plan (260).
- The `--ac` mode's dry-run (`epic_pipeline.py:114-119`) already shows the expected shape.

**Fix**
- Thread a keyword-only `dry_run=False` through `_run_ids_mode` and `build_epic_from_ids`, so fast_lane's existing call is unchanged.
- In dry-run:
  - still build the dependency graph and sort it, so a cycle exits 1 before any write;
  - derive the epic name with the same call the real run uses (ACD-1200a-3-iii);
  - print the ids in build order, and finish with `Dry-run: would create <path>`;
  - write nothing.

**Relation to `tickets/00_inbox/TICKET-20261005-GoalToEpicKeepsOutOfEpicDependencies.md`.**
This ticket is a prerequisite for that ticket's "--dry-run shows order and cycles for
--ids" bullet, and already prints the `--ids` build order. That ticket keeps `--ac`
ordering and the out-of-epic reporting.

## Constraints

- **Test placement.** `unit_tests/build_orchestration/test_bo_2600a_5.py` measures 570 / 400, so the ratchet refuses growth. The tests go in `unit_tests/test_goal_to_epic.py` (138 / 400). They run `goal_to_epic.py` as a subprocess.
- `epic_pipeline.py` measures 168 / 400. Ticket 09 also touches it and runs after this ticket.

## Acceptance Criteria

- [ ] AC-1: `goal_to_epic.py --ids <ids> --dry-run` writes nothing. No file or folder appears under the tickets inbox, and every AC YAML (including `implemented_by`) is byte-identical before and after.
- [ ] AC-2: The dry-run builds the same dependency graph and topological order as the real run, prints the ids in build order, and finishes with `Dry-run: would create <path>`.
- [ ] AC-3: The epic folder name the dry-run prints is byte-identical to the name a real run with the same ids creates. Both use the same derivation call.
- [ ] AC-4: A dependency cycle among the ids exits 1 with an `ERROR:` line during the dry-run, before any write.
- [ ] AC-5: `dry_run` is keyword-only with default `False` on `_run_ids_mode` and `build_epic_from_ids`. A real `--ids` run, and fast_lane's call, behave exactly as today.

## Test Requirements

```yaml
tests:
  - name: test_ids_dry_run_writes_nothing_under_inbox
    file: unit_tests/test_goal_to_epic.py
    covers:
      - ACD-1200a-3-iii
      - BO-2600a-5
    asserts: >-
      Running goal_to_epic.py --ids A,B --dry-run as a subprocess against a
      temporary AC store and inbox exits 0, and the set of files under the
      inbox is identical before and after.
    framework: pytest
    type: integration
    angle: criterion
  - name: test_ids_dry_run_leaves_ac_yamls_byte_identical
    file: unit_tests/test_goal_to_epic.py
    covers:
      - ACD-1200a-3-iii
      - BO-2600a-5
    asserts: >-
      After the same dry-run subprocess, every AC YAML in the temporary store
      has the same bytes as before, including implemented_by.
    framework: pytest
    type: integration
    angle: real_artifact
  - name: test_ids_dry_run_name_equals_real_run_name
    file: unit_tests/test_goal_to_epic.py
    covers:
      - ACD-1200a-3-iii
    asserts: >-
      The EPIC-<name> path printed in the dry-run's "Dry-run: would create
      <path>" line is byte-identical to the folder a following real --ids run
      with the same ids creates.
    framework: pytest
    type: integration
    angle: criterion
  - name: test_ids_dry_run_prints_ids_in_build_order
    file: unit_tests/test_goal_to_epic.py
    covers:
      - ACD-1200a-3-iii
      - BO-2600a-5
    asserts: >-
      With ids given in the order B,A, where B depends on A, the dry-run's
      stdout lists A before B, and its last line starts with
      "Dry-run: would create".
    framework: pytest
    type: integration
    angle: boundary
  - name: test_ids_dry_run_cycle_exits_1_without_writes
    file: unit_tests/test_goal_to_epic.py
    covers:
      - ACD-1200a-3-iii
      - BO-2600a-5
    asserts: >-
      With A depending on B and B depending on A, the dry-run exits 1 with an
      "ERROR:" line on stderr, and the inbox and the AC YAMLs are unchanged.
    framework: pytest
    type: integration
    angle: failure
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_ids_dry_run_writes_nothing_under_inbox, test_ids_dry_run_leaves_ac_yamls_byte_identical | | |
| AC-2 | test_ids_dry_run_prints_ids_in_build_order | | |
| AC-3 | test_ids_dry_run_name_equals_real_run_name | | |
| AC-4 | test_ids_dry_run_cycle_exits_1_without_writes | | |
| AC-5 | existing test_bo_2600a_5.py and the fast_lane tests stay green | | |

## Implementation Tasks

### test-writer
- [ ] Add the five subprocess tests to `unit_tests/test_goal_to_epic.py`, using a temporary AC store and inbox.

### python-coder
- [ ] `goal_to_epic.py:257-259`: pass `dry_run=args.dry_run`.
- [ ] `epic_cli._run_ids_mode` and `epic_pipeline.build_epic_from_ids`: add keyword-only `dry_run=False`. In dry-run, stop after the sort and the name derivation, print the order and the would-create line, and return.

### test-runner / pr-reviewer / commit
- [ ] Run `unit_tests/test_goal_to_epic.py`, `unit_tests/build_orchestration/test_bo_2600a_5.py` and the fast_lane `--ids` tests.

## Risk & Safety

- Touches money? No.
- Touches data? No. This removes unwanted writes.
- Reversibility: revert the commit.

## Out of Scope

- `--ac` mode ordering and out-of-epic reporting (TICKET-20261005).
- `expects_from` edges (ticket 08) and Master_Plan frontmatter (ticket 09).

## Comments

_(Append-only log — leave blank when authoring.)_
