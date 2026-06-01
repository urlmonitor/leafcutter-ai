---
title: "EPIC-LeafcutterVersioning — automated SemVer, release CI, and breaking-change guards"
date: "2026-05-27"
time: "14:30"
type: feature
components: 
  - build_pipeline
  - infrastructure
summary: "Added automated version tagging, breaking-change detection, and consumer upgrade guards to the leafcutter package."
description: "Delivers 5 sub-tickets: emit_entry.py breaking+migration_steps fields, compute_next_version.py for SemVer from changelog entries, GitHub Actions release workflow, build.py halt-guard for consumers, and schema-diff CI gate closing the silent-omission gap."
pr: 10
commits: 
  - acd0fac
  - d1bcdc4
  - 07b43e1
  - c4dc86e
  - bee9cbc
  - fad01c3
breaking: false
---

## Entry
