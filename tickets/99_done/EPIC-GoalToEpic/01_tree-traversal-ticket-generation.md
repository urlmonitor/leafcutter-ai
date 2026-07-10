---
title: "Tree traversal, ticket generation, and epic folder assembly"
status: done
components:
  - ac_driven_dev
created: 2026-06-05
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
target_epic: EPIC-GoalToEpic
files_touched:
  - scripts/ac_store/scan_ac_store.py
  - scripts/goal_to_epic.py
  - scripts/ac_store/generate_ticket_from_ac.py
  - unit_tests/ac_store/test_tree_traversal.py
  - unit_tests/ac_store/test_ticket_generation_batch.py
  - unit_tests/ac_store/test_epic_folder_assembly.py
agents:
  test-writer: signed_off
  python-coder: signed_off
  test-runner: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
ac_coverage: 0/5
source_ac: ACD-1200a
---

# 01: Tree traversal, ticket generation, and epic folder assembly

## Actor / Goal

In order to turn a goal-level AC into a buildable epic, the system must walk
the AC tree, collect all leaves, generate a ticket per leaf, and assemble
numbered ticket files into a named EPIC folder — so the supervisor can drive
the entire feature from a single folder without any manual assembly.

## Context

`generate_ticket_from_ac.py` already generates a single ticket from one AC.
`scan_ac_store.py` already scans the AC store for ACs by field filter.
This ticket adds tree traversal (depth-first, leaf collection) and the
batch orchestrator (`goal_to_epic.py`) that calls `generate_ticket_from_ac.py`
once per leaf and assembles the folder.

The `covered_by` field in each AC YAML is the child pointer. An AC is a leaf
when `covered_by` is empty or absent. The folder name is PascalCase from the
goal AC's `title`.

## AC References

- Implements ACD-1200a-1 (tree traversal collects only leaf-level ACs)
- Implements ACD-1200a-1-i (L1-scoped traversal stays within the L1 subtree)
- Implements ACD-1200a-2 (one ticket per leaf AC)
- Implements ACD-1200a-3 (EPIC folder assembly with numeric prefixes)
- Implements ACD-1200a-3-i (zero-leaf condition produces error, not empty epic)

## Agent Contracts

### python-coder

- [x] AC-1: Given a goal AC with a mixed tree (L0 -> L1s -> L2s -> L3s), tree traversal returns only the leaf ACs (those where `covered_by` is empty or absent), in depth-first alphabetical-sibling order, in under 200ms for trees up to 200 nodes. <!-- signed: python-coder -->
- [x] AC-2: Given traversal is scoped to an L1 AC (not the L0 root), only leaves beneath that L1 are collected — sibling L1 branches are excluded — and the generated epic contains exactly that subset. <!-- signed: python-coder -->
- [x] AC-3: Given a leaf set of N ACs, `generate_ticket_from_ac.py` is called exactly once per leaf, each resulting ticket file contains `source_ac` and `ac_coverage` frontmatter referencing its source AC ID, and the full batch completes in under 5 seconds for N <= 50. <!-- signed: python-coder -->
- [x] AC-4: Given N ticket files have been generated, the assembler creates a folder named `EPIC-<PascalCaseTitle>` under `tickets/00_inbox/epics/`, places all ticket files inside it with monotonically increasing numeric prefixes (`01_`, `02_`, ...) reflecting topological order, and returns the absolute folder path. <!-- signed: python-coder -->
- [x] AC-5: Given the tree traversal finds zero leaf ACs beneath the target goal (L1 is composite with no L2/L3 children), the system outputs the error "No leaf-level ACs found beneath <id>. Decompose the L1s into L2/L3 ACs first.", exits non-zero, creates no folder, and writes no ticket files. <!-- signed: python-coder -->

**Delivers to python-coder (readiness gate — ticket 02):**
```
list[str] — ordered list of leaf AC IDs (depth-first, alphabetical siblings)
           e.g. ['ACD-050a-1', 'ACD-050a-2-i', 'ACD-050b-1']
           Guarantee: covered_by is empty or absent for every ID in the list.
```

**Delivers to python-coder (dependency wiring — ticket 03):**
```
list[str] — same ordered leaf AC ID list with depends_on fields readable from disk
```

**Delivers to python-coder (target_epic stamping — ticket 04):**
```
str — epic folder name (e.g. 'EPIC-ValidateApiInputs') derived from goal AC title
list[str] — absolute paths of generated ticket .md files, one per leaf AC
```

**Depends on:** Nothing upstream. This ticket is the foundation.

## Acceptance Criteria

- [ ] AC-1: Tree traversal returns only leaf ACs (no composites), depth-first alphabetical, <200ms for <=200 nodes
- [ ] AC-2: L1-scoped traversal excludes sibling L1 branches; generated epic contains exactly the L1 subtree leaves
- [ ] AC-3: Exactly one ticket per leaf; each ticket has `source_ac` and `ac_coverage`; batch completes <5s for <=50 leaves
- [ ] AC-4: Epic folder named `EPIC-<PascalCaseTitle>`, numeric prefixes from topological order, ready for ticket-supervisor
- [ ] AC-5: Zero-leaf condition outputs clear error, exits non-zero, creates no folder, writes no files

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| ACD-1200a-1   | test_tree_traversal.py:TestTraverseAcTreeLeafCollection | Added traverse_ac_tree() to scan_ac_store.py — DFS, alphabetical siblings, leaf=empty covered_by | |
| ACD-1200a-1-i | test_tree_traversal.py:TestTraverseAcTreeL1Scope | traverse_ac_tree() accepts any root_id; scoped to subtree naturally via DFS from that node | |
| ACD-1200a-2   | test_ticket_generation_batch.py:TestGenerateTicketsForLeaves | generate_tickets_for_leaves() in goal_to_epic.py calls _call_generate_ticket_from_ac() once per leaf | |
| ACD-1200a-3   | test_epic_folder_assembly.py:TestAssembleEpicFolder | assemble_epic_folder() in goal_to_epic.py: PascalCase name, 01_/02_/... prefixes, returns absolute path | |
| ACD-1200a-3-i | test_epic_folder_assembly.py:TestZeroLeafErrorGuard | ZeroLeafError raised before any filesystem writes; CLI exits non-zero with clear error message | |

## Test Requirements

```yaml
tests:
  - path: unit_tests/ac_store/test_tree_traversal.py
    covers: [ACD-1200a-1, ACD-1200a-1-i]
    type: unit
    rationale: "Traversal is pure logic on a dict graph; fast unit tests cover all branching conditions"
  - path: unit_tests/ac_store/test_ticket_generation_batch.py
    covers: [ACD-1200a-2]
    type: unit
    rationale: "Mocks generate_ticket_from_ac.py to verify call-once-per-leaf and frontmatter contract"
  - path: unit_tests/ac_store/test_epic_folder_assembly.py
    covers: [ACD-1200a-3, ACD-1200a-3-i]
    type: unit
    rationale: "Folder creation, naming, prefix assignment, and zero-leaf error path"
```

## Implementation Tasks

- [x] Add `traverse_ac_tree(root_id, ac_store_root) -> list[str]` to `scan_ac_store.py`
      — depth-first, alphabetical siblings, leaf = empty/absent `covered_by`
- [x] Add L1-scoped mode: `traverse_ac_tree(root_id, ac_store_root, scope='subtree')`
- [x] Write `scripts/goal_to_epic.py` orchestrator:
      - accept `--ac <id>` and `--store-root <path>`
      - call `traverse_ac_tree` to get leaf list
      - zero-leaf guard (error + non-zero exit before any writes)
      - call `generate_ticket_from_ac.py --ac <id>` once per leaf
      - collect ticket file paths from stdout
      - call epic folder assembler with leaf paths and epic name
- [x] Write `assemble_epic_folder(ticket_paths, epic_name, inbox_dir) -> str`
      — PascalCase epic name derivation, numeric prefixes from topological order
      (trivial for this ticket; full topo-sort added in ticket 03)
- [x] Handle conflict: epic folder already exists → report conflict, do not overwrite
- [x] Write `implemented_by` back-reference to each AC YAML after ticket generation
      (per ADR-010 convention)
- [x] Write unit tests for all 5 ACs

## Risk & Safety

- Touches money? No.
- Touches data? Yes — writes `implemented_by` back-reference to AC YAML files.
  This is a targeted field append (not a full yaml.dump round-trip).
- Reversibility? High — folder and ticket files are new files; delete them to revert.
  `implemented_by` back-references are metadata only.
- The zero-leaf guard (AC-5) must fire before ANY file system writes to prevent
  partial state.

## Sign-offs

- [x] test-writer — 2026-06-05 12:00
- [x] python-coder — 2026-06-05 12:30
- [x] test-runner — 2026-06-05 12:45
- [x] pr-reviewer — 2026-06-05 13:00
- [x] commit — 2026-06-05 13:15
- [x] pull-request — 2026-06-05 13:20

## Comments

### 2026-06-05 13:20 — pull-request (status: ok)
feedback-id: fb_2026-06-05_b03deb94
completion_manifest:
  pushed_to_branch: true
  existing_pr_updated: true
Pushed commit 27843c9 to origin/EPIC-GoalToEpic. PR #69 updated with this ticket's implementation — no new PR created (per user instruction, existing PR is used for the entire epic).

### 2026-06-05 13:15 — commit (status: ok)
feedback-id: fb_2026-06-05_ec873114
completion_manifest:
  files_staged_correctly: true
  no_cross_branch_files: true
  commit_created: true
Staged 7 in-scope files: scripts/ac_store/scan_ac_store.py, scripts/goal_to_epic.py, ticket file, unit_tests/ac_store/__init__.py and 3 test files. Commit created on EPIC-GoalToEpic branch.

### 2026-06-05 13:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_f41741d2
completion_manifest:
  implementation_correct: true
  tests_green: true
  ruff_clean: true
  zero_leaf_guard_fires_before_writes: true
  no_contract_shrinkage: true
Implementation approved. traverse_ac_tree() DFS with alphabetical siblings is correct. assemble_epic_folder() zero-leaf guard fires before any filesystem write. goal_to_epic.py subprocess delegation to generate_ticket_from_ac.py is clean. Minor note: _load_ac_by_id() in scan_ac_store.py is defined but unused — harmless dead code. 22/22 tests green, ruff clean.

### 2026-06-05 12:45 — test-runner (status: ok)
feedback-id: fb_2026-06-05_002474a6
completion_manifest:
  all_tests_green: true
  no_regressions: true
  coverage_all_acs: true
22/22 tests green in unit_tests/ac_store/ — test_tree_traversal.py (8), test_ticket_generation_batch.py (5), test_epic_folder_assembly.py (9). All red_baseline tests from test-writer are now green. No pre-existing tests broken.

### 2026-06-05 12:30 — python-coder (status: ok)
feedback-id: fb_2026-06-05_fbf6549b
completion_manifest:
  traverse_ac_tree_implemented: true
  goal_to_epic_implemented: true
  assemble_epic_folder_implemented: true
  zero_leaf_guard_fires_before_writes: true
  all_red_baseline_tests_green: true
  ruff_clean: true
Added traverse_ac_tree() to scan_ac_store.py (DFS, alphabetical siblings, leaf=empty/absent covered_by) and created scripts/goal_to_epic.py with generate_tickets_for_leaves(), assemble_epic_folder(), ZeroLeafError, EpicFolderConflictError, and run() CLI entry point. 22/22 tests green; ruff clean (E722, BLE001, TRY).

red_baseline_results:
  - test_name: test_ac1_leaf_only_returned_from_mixed_tree
    result: green
  - test_name: test_ac2_called_once_per_leaf
    result: green
  - test_name: test_ac3_folder_named_epic_pascal_case
    result: green

### 2026-06-05 12:00 — test-writer (status: ok)
feedback-id: fb_2026-06-05_55e33f6b
completion_manifest:
  test_files_written: true
  tests_are_red: true
  ac_coverage_table_filled: true
  no_syntax_errors: true
  ruff_clean: true
Wrote 3 failing test files (test_tree_traversal.py, test_ticket_generation_batch.py, test_epic_folder_assembly.py) under unit_tests/ac_store/. All tests are RED with ImportError/ModuleNotFoundError — scan_ac_store.traverse_ac_tree and goal_to_epic module do not exist yet. AC Coverage table Test column filled for all 5 ACs. Ruff clean (E722, BLE001, TRY rules).

## Test Writer — Completion Report

### Tests Written
| File | Directory | Framework | Status |
|---|---|---|---|
| test_tree_traversal.py | unit_tests/ac_store/ | pytest | written |
| test_ticket_generation_batch.py | unit_tests/ac_store/ | pytest | written |
| test_epic_folder_assembly.py | unit_tests/ac_store/ | pytest | written |

### Verification Run
- Command: python3 -m pytest unit_tests/ac_store/ -v
- Result: red (3 ImportError/ModuleNotFoundError — expected; traverse_ac_tree and goal_to_epic not yet implemented)

red_baseline:
  - test_name: test_ac1_leaf_only_returned_from_mixed_tree
    file: unit_tests/ac_store/test_tree_traversal.py
    error: "ImportError: cannot import name 'traverse_ac_tree' from 'scan_ac_store'"
  - test_name: test_ac2_called_once_per_leaf
    file: unit_tests/ac_store/test_ticket_generation_batch.py
    error: "ModuleNotFoundError: No module named 'goal_to_epic'"
  - test_name: test_ac3_folder_named_epic_pascal_case
    file: unit_tests/ac_store/test_epic_folder_assembly.py
    error: "ModuleNotFoundError: No module named 'goal_to_epic'"
