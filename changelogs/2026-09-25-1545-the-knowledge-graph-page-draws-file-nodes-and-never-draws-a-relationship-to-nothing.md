---
title: The knowledge graph page draws file nodes and never draws a relationship to nothing
date: "2026-09-25"
time: "15:45"
type: manual
components: 
  - knowledge_management
summary: "The knowledge graph page now drops any relationship whose other end is not on the page in every view (whole graph, one surface, several surfaces) and says how many it left out. Files named by criteria and tickets get their own colour, and files missing on disk are drawn dashed and faded, with a legend row and tooltip."
description: "Builds KM-KGS-100b-2, -i and -ii in scripts/visualise_knowledge_graph.py. Edges are filtered against the deduplicated node set in all three _assemble_graph branches (previously only the several-surfaces branch), and stderr always prints 'Left out N of M relationships', where M is the raw edge count. The page script builds degree, links and adjacency from a safeEdges list that cannot reference an unknown id. Files-surface nodes carry an explicit missing flag (an unmarked node draws as present), SURFACE_COLORS gains a files entry, and missing files use a missing-file class that hover and pin do not overwrite. On the real repository: 0 of 31,228 relationships left out, 1,336 file nodes, 370 missing."
commits: []
breaking: false
---

## Entry

The knowledge graph page no longer hands the browser a relationship whose
other end is not on the page. Whatever you filter by, it drops those
relationships and tells you how many: `Left out N of M relationships`. On
the whole repository that is now 0 of 31,228.

Files that criteria and tickets point at are drawn in their own colour. A
file that no longer exists on disk is drawn dashed and faded, the legend has
a "missing file" row, and its tooltip says it is missing.
