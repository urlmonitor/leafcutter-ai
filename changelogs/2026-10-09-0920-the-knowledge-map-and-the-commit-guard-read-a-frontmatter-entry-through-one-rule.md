---
title: "The knowledge map and the commit guard read a frontmatter entry through one rule, and the map reports what it declines (GE-118f, KM-KGS-100d-3, KM-KGS-100d-3-i)"
date: "2026-10-09"
time: "09:20"
type: manual
components:
  - knowledge_management
  - commit_guardian
summary: "The knowledge-graph builder now resolves list entries through the same shared resolver the commit guard uses, so a labelled entry becomes an edge instead of vanishing, and a refused entry is reported per field instead of being dropped in silence."
description: "The commit guard learned (GE-118d) to accept a frontmatter path entry as a bare string or a single-key mapping and to refuse anything else by name. The knowledge-graph builder kept its own rule: it took only plain strings, so a labelled entry such as `- reference: docs/x.md` was flattened to a target that matched no node and was then removed as dangling. KI-CG-008 counted roughly 33 of 50 documents in one adopter repo written that way, all silently missing from the map. extract_edges in scripts/knowledge_query.py now classifies every list entry through scripts/frontmatter_path_resolver.py, the module the guard uses. Accepted entries become edges. Refused entries are named on stderr as ENTRY-DECLINED lines carrying surface, document, field and entry. They are counted per field: the JSON output gains field_counts ({field: {edges, declined}}, every examined field listed, zeros included) beside the existing entries_declined total, and the text output gains one 'Field <name>: edges=<n> declined=<m>' line per field. So a field that contributed nothing is distinguishable from one that had nothing to contribute. An empty-string entry is no longer skipped before the resolver; the resolver refuses it, matching the guard. The frontmatter reader marks a flattened mapping item with its source key count, so a multi-key mapping is refused by arity rather than read as its first key. On this repository the change is neutral by measurement: the main and branch builders over the same tree produce identical graphs (14,240 nodes; 37,623 edges, 30,191 unique; 0 added, 0 lost; 0 ENTRY-DECLINED), because no frontmatter here uses the labelled form. The defect lives in adopter repositories, and the deployed-layout test is what proves the fix. Reporting is scoped to the knowledge_query CLI named by the criteria; its two other callers (knowledge/projection/canonical_loader.py and visualise_knowledge_graph.py) gain the new edges but not the decline report."
breaking: false
---

## Entry

### Changed

- `scripts/knowledge_query.py` — `extract_edges` classifies every list entry
  through the shared resolver; the declines and per-field counts are carried out
  through optional accumulator arguments (None by default, so existing callers
  are unchanged). The empty-string early skip is removed.
- `scripts/knowledge_frontmatter_reader.py` — a flattened mapping list item
  keeps its source key count (`MappingItemText`), and `entry_for_resolver`
  rebuilds the mapping the resolver judges.
- `scripts/knowledge_rendering.py` — JSON `field_counts` and per-field text
  lines; `entries_declined` total kept.
- `scripts/knowledge_file_nodes.py` — `ENTRY-DECLINED` line formatter.

### Added

- `unit_tests/test_km_kgs_100d_3.py`, `unit_tests/test_km_kgs_100d_3_i.py`,
  `unit_tests/commit_guardian/test_ge_118f.py`, `unit_tests/km_kgs_100d_3_shared.py`.
  The GE-118f deployed-layout test runs the deployed guard and the deployed
  builder from a real build outside this repository.

### Known, filed separately

- The shipped `knowledge-query` skill documents `python scripts/knowledge_query.py`,
  which does not exist in an adopter install (`KI-KM-20261009`).
- The shared-layout integrity plugin can print "clean" while failing the session
  (`KI-TQ-20261009`).
