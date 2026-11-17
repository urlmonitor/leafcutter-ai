---
title: Agents now record a learning with one helper command
date: "2026-10-20"
time: "20:30"
type: manual
components: 
  - knowledge_system
  - infrastructure
summary: "Agents now record a learning by running one helper command instead of appending JSON by hand, so following the capture step word for word leaves one clean, durable record."
description: "2 commits (0f254cc13, f6def9233). The signoff capture step and the S9 blocks of product-owner, business-analyst and it-po now run emit_knowledge.py with the learning in single quotes, so the shell cannot expand it. A learning that cannot be classified is kept using the unclassified sentinel. A missing, unusable or stale log declaration creates nothing, warns and exits 0, so the agent is not blocked. emit_knowledge.py gains an optional --sink and a read-only --print-sink; the sink-parity check (scripts/ci/check_sink_parity.py) now verifies the new command. ADR-034 gains a dated Amendment 1. Also adds the EPIC-ALearningAnAgentHasTodayActuallyGets scaffold of 8 tickets. INF-700b-1 stays in progress until its two sub-requirements (INF-700b-1-i, INF-700b-1-ii) are built."
adrs: 
  - ADR-034
commits: 
  - 0f254cc13
  - f6def9233
breaking: false
---

## Entry
