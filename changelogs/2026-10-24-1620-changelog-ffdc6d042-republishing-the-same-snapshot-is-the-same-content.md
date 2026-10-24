---
title: "Changelog ffdc6d042 — republishing the same snapshot is the same content"
date: "2026-10-24"
time: "16:20"
type: manual
components: 
  - knowledge_management
summary: "Publishing a snapshot a second time no longer fails with 'generation identity already belongs to different content' after the duplicate-relationship collapse changed it in place."
description: "One commit (ffdc6d042, fix). The generation content digest is now taken after collapse_identical_edges and without the collapse's own diagnostic lines (collapsed_content_digest in knowledge/projection/validation.py), so a fresh snapshot and one already collapsed by an earlier publication name the same content; a generation recorded earlier with the raw pre-collapse digest is still accepted, and really different content is still refused. Found by the real-database check test_live_idempotence_scope_metadata_and_rebuild, which had been failing on main since #1203 (2026-10-14). New AC KM-400b-2-iii."
adrs: []
commits: 
  - ffdc6d042
breaking: false
---

## Entry
