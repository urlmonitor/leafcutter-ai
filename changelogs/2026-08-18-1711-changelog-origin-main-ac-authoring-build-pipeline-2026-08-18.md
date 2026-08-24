---
title: "Changelog origin/main..ac-authoring/build-pipeline — 2026-08-18"
date: "2026-08-18"
time: "17:11"
type: manual
components: 
  - ac_store
  - build_pipeline
summary: "Specified, but did not yet build, a guardrail so every config and data file the packages own safety checks depend on gets installed for consumers, and any check whose own required file is missing says so instead of quietly answering the wrong question."
description: "8 new L2/L3 acceptance criteria (work_status: todo) under BP-900-deployment-completeness authored against 5 verified cases of declaring files (doc_types.json, diagram_types.json, ac_store_schema.json, agent_registry.json, _component_migration_map.py) missing from a deployed consumer install; 4 additive parent covered_by back-link repairs; 1 memory note capturing the new declaring-file deployment-gap axis. No implementation code changed."
pr: 491
commits: 
  - 04cea83db46979121ded022ede0b274a4968e62f
  - dfb26436a63c089b469e7d6256ccdec5e85b34a4
---

## Entry
