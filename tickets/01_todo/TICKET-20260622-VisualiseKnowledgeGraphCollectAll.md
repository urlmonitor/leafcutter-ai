---
title: "fix kq._collect_all return contract for visualise_knowledge_graph"
status: todo
priority: medium
source_epic: EPIC-CodeQualityHooks (post-merge triage, 2026-06-22)
affected_tests:
  - unit_tests/test_visualise_knowledge_graph.py (8 tests: TestWritesHtmlFile, TestEmbeddedJsonValid, TestNodesHaveColorField, TestNodeStructure, TestEdgeStructure, TestD3CdnReference, TestSurfaceFilterExcludesOthers, TestProjectRootFlagPassedToKq)
---

# fix kq._collect_all return contract for visualise_knowledge_graph

## Problem

`scripts/visualise_knowledge_graph.py:265` calls `kq._collect_all(project_root, paths_json, surface_filter=sf)` and attempts to unpack the result as a 2-tuple `(node_records, edge_records)`. The current implementation returns 0 values (or an empty iterable), causing `ValueError: not enough values to unpack (expected 2, got 0)` for all 8 test cases.

These are TDD red stubs written before the implementation was completed.

## Acceptance Criteria

- [ ] `kq._collect_all()` returns a 2-tuple `(node_records, edge_records)` where both are lists
- [ ] `visualise_knowledge_graph._assemble_graph()` successfully unpacks the tuple
- [ ] All 8 tests in `unit_tests/test_visualise_knowledge_graph.py` pass

## Classification

Pre-existing failures; TDD red stubs awaiting implementation. Not caused by EPIC-CodeQualityHooks. First surfaced during finalization triage 2026-06-22.
