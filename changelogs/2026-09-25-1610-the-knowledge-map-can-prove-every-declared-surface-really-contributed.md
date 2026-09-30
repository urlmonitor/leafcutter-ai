---
title: The knowledge map can prove every declared surface really contributed
date: "2026-09-25"
time: "16:10"
type: manual
components: 
  - knowledge_management
summary: "A new check_surface_set() reports any declared knowledge-map surface whose path exists but contributed nothing, and any node carrying a surface label that is neither declared nor synthetic. A surface now counts as contributing only when something was actually read from its own path, so component hub nodes can no longer make an empty components surface look populated."
description: "Builds KM-KGS-100c-1, -i and -ii. The check lives in the new sibling module scripts/knowledge_surface_check.py (SYNTHETIC_SURFACE_LABELS = components, files) and is re-exported by knowledge_query. _collect_all_ex() now also returns primary_surfaces, captured before synthetic hub and file nodes are added, and build_knowledge_map() derives contributing_surfaces from it. A --surface-restricted map is judged against its own narrowed declared set. The module is deployed by both deploy lists. knowledge_query.py stays at 921 content lines. On the real repository all nine declared surfaces contribute and the check reports nothing."
commits: []
breaking: false
---

## Entry

The knowledge map can now prove that each surface declared in
`config/paths.json` actually contributed items, instead of assuming it. The
new surface-set check names any declared surface whose folder exists but
produced nothing, and any node whose surface label nobody declared.

It closes a masking bug. The component hub nodes are labelled `components`,
so an empty components folder used to look populated. A surface now counts
only when something was read from its own path. On this repository every one
of the nine surfaces contributes and the check reports nothing.
