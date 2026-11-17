---
title: Knowledge capture path reference and sequence diagram (5b6b0b71a)
date: "2026-10-25"
time: "14:37"
type: manual
components: 
  - knowledge_system
  - documentation_system
summary: "The knowledge-system architecture reference now describes the capture step as it actually ships, with a new sequence diagram of the capture path."
description: "docs(knowledge) commit 5b6b0b71a (INF-700b-4, INF-700b-5). agent_knowledge_system.md now covers the capture step outcomes (emit a learning, nothing-to-record attempt, failed capture attempt), the knowledge record fields with text as the only content field, where capture attempts and failures are recorded (operational telemetry stream, separate from the knowledge-emission sink) and the capture-health report that counts them, and that routing is wired on the fast-lane-ship, quick-fix and build-feature routes and manual elsewhere. Retired skills are named only as retired. Adds diagrams/c3-038-knowledge-capture-path-sequence.md; the description-field and knowledge-graph sections move to docs/reference/description-field-convention.md and knowledge-graph-visualization.md."
adrs: 
  - ADR-011
diagrams: 
  - docs/architecture/diagrams/c3-038-knowledge-capture-path-sequence.md
commits: 
  - 5b6b0b71a
breaking: false
---

## Entry
