---
title: "Changelog f744fa6f5 — capture-health report says which kind of quiet a period was"
date: "2026-10-23"
time: "19:40"
type: manual
components: 
  - knowledge_system
  - agent_telemetry
summary: "Added a report that tells a reader whether a quiet period of learning capture meant nothing needed saving, capture was broken, or capture never ran."
description: "One commit (f744fa6f5, feat). New scripts/knowledge/health/capture_health_report.py counts capture attempts (recorded, nothing-to-record, failed) and gives one of four verdicts: no-run-reached-the-step, capture-path-broken, learnings-recorded, nothing-to-record. It names missing targets, refuses to give a verdict when it cannot find the log (non-zero exit), prints its two known limits (A2.6 and A2.4), and is added to both deploy lists in scripts/build_phases_knowledge.py so it reaches consumer installs. ADR-034 Amendment 3 records the decisions; 11 new tests; INF-700b-3, INF-700b-1-i and INF-700b-1 are done."
adrs: 
  - ADR-034
commits: 
  - f744fa6f5
breaking: false
---

## Entry
