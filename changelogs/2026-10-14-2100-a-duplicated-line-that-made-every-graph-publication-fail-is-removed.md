---
title: "A duplicated line that made every graph publication fail is removed"
date: "2026-10-14"
time: "21:00"
type: manual
components: 
  - testing_quality
  - knowledge_management
summary: "One requirement listed the same file twice as part of its implementation. That single repeat made every knowledge-graph publication since 12 October write all its data and then fail its own check, leaving the data behind."
description: "One acceptance criterion, TQ-600a-13-ix, named the file scripts/ci/_hold_exempt.py twice in its list of implementing files. The knowledge graph turns each such reference into a connection, and two identical references produce two identical connections. The graph store keeps only one of two identical connections, so every publication stored one connection fewer than it had counted, failed its own consistency check, marked itself failed, and left everything it had written in place. Every publication since 12 October failed this way, at roughly one per merge, and the leftovers filled two hosted databases to their connection limit, where they stopped accepting writes. The repeated line is removed. Building the graph offline from the current main branch gave 28,815 connections but only 28,814 distinct ones; after the fix the two figures match. The underlying weaknesses — that a duplicate in the source data can stop all publication, and that a failed publication leaves its data behind — are being specified separately so the next duplicate cannot cause the same outage."
---

## Entry
