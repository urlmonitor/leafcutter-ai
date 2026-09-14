---
title: "Knowledge capture emits now require a learning text field (INF-700b-1)"
date: "2026-09-07"
time: "12:51"
type: manual
components: 
  - ticket_creation_pipeline
  - product_ownership
  - skills_system
summary: "Knowledge-capture records now carry the actual insight text alongside their existing metadata, so the system that will later route learnings has something to act on instead of an empty receipt."
description: "Capture previously emitted a knowledge_captured record naming the agent, component, destination and entry_kind but never the learning itself -- a receipt with no payload that left nothing for the (not-yet-built) harvester to route. This adds a required, non-empty `text` field to the record's normative definition in templates/skills/signoff/SKILL.md sec 7, and updates the three v3 authoring agents (product-owner, business-analyst, it-po) to emit it. `text` is required of producers but optional to consumers, since 28 pre-existing on-disk records lack it and must stay readable (see test_existing_six_field_records_remain_readable_without_text). The three agents also had their route-learning / capture-learning skill loads removed -- both names were retired by ADR-034 sec 2 item 3 and neither ever existed on disk, so the loads were referencing nonexistent files; entry_kind and destination now carry literal sentinels (\"unclassified\" / \"(unrouted)\") since no classification procedure survives to run. 177 tests pass (unit_tests/agents + tests/knowledge), 0 xfail. This is the emission half only -- the caller (INF-700a), the sink path (INF-400c-4) and the entry_kind vocabulary (INF-400c-5) remain open."
pr: 722
adrs: 
  - ADR-034
commits: 
  - f7ab0c0e5
breaking: false
---

## Entry
