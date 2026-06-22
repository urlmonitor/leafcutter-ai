---
title: "fix traverse_ac_tree to filter composite parent ACs from leaf results"
status: todo
priority: medium
source_epic: EPIC-CodeQualityHooks (post-merge triage, 2026-06-22)
affected_tests:
  - unit_tests/ac_store/test_tree_traversal.py::TestTraverseAcTreeLeafCollection::test_ac1_leaf_only_returned_from_mixed_tree
  - unit_tests/ac_store/test_tree_traversal.py::TestTraverseAcTreeLeafCollection::test_ac1_depth_first_alphabetical_order
  - unit_tests/ac_store/test_tree_traversal.py::TestTraverseAcTreeLeafCollection::test_ac1_performance_200_nodes
  - unit_tests/ac_store/test_tree_traversal.py::TestTraverseAcTreeLeafCollection::test_ac1_absent_covered_by_treated_as_leaf
  - unit_tests/ac_store/test_tree_traversal.py::TestTraverseAcTreeL1Scope::test_ac1i_leaf_l1_returns_itself
---

# fix traverse_ac_tree to filter composite parent ACs from leaf results

## Problem

`traverse_ac_tree` currently includes composite parent ACs in the result set when it should return only leaf ACs. 5 tests in `unit_tests/ac_store/test_tree_traversal.py` are failing.

Root causes:
- `test_ac1_leaf_only_returned_from_mixed_tree`: parent ACD-050a-1 appears alongside leaves (should be filtered)
- `test_ac1_depth_first_alphabetical_order`: traversal does not reach all siblings
- `test_ac1_performance_200_nodes`: returns 200 nodes instead of 190 (10 parents not filtered)
- `test_ac1_absent_covered_by_treated_as_leaf`: ACs with absent covered_by not treated as leaves
- `test_ac1i_leaf_l1_returns_itself`: leaf L1 used as scope root returns empty instead of itself

## Acceptance Criteria

- [ ] `traverse_ac_tree` returns only ACs where `covered_by` is absent or empty (leaf nodes)
- [ ] A composite AC (one with child ACs) is not returned in the leaf set
- [ ] Depth-first alphabetical traversal visits all siblings
- [ ] An L1 leaf used as scope root returns itself
- [ ] All 5 failing tests pass

## Classification

Pre-existing failure; not caused by EPIC-CodeQualityHooks. First surfaced during finalization triage 2026-06-22.
