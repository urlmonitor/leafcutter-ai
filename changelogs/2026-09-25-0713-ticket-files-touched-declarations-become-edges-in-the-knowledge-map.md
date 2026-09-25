---
title: Ticket files_touched declarations become edges in the knowledge map
date: "2026-09-25"
time: "07:13"
type: manual
components: 
  - knowledge_management
summary: "The knowledge map now carries ticket-to-file edges: 3160 files_touched edges, up from 0."
description: "Quick-fix for KM-KGS-100c-4 (commit aa7ccdfa). The tickets surface declared files_touched in edge_fields but not in file_path_fields, so build_knowledge_map() dropped every such edge as a phantom (1160 tickets, 3057 declared values, 0 edges). config/paths.json now lists files_touched in the tickets surface's file_path_fields, as the acs surface does for implemented_by and covered_by. test_knowledge_query.py's edge-count integration test now derives its exempt set from paths.json instead of hardcoding it."
breaking: false
---

## Entry
