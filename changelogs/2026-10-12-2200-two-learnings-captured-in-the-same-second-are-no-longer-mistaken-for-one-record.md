---
title: "Two learnings captured in the same second are no longer mistaken for one record"
date: "2026-10-12"
time: "22:00"
type: manual
components: 
  - knowledge_system
summary: "A knowledge record's identity now includes the learning text, so routing one learning can no longer mark a different learning from the same second as already routed."
description: "The harvester and the completion-routing path identified a record by timestamp, agent, component, destination and kind only. Distinct learnings emitted in the same second by one agent to one destination therefore shared an identity: once one was routed and recorded, the others looked already processed and were never routed, a learning lost while marked routed. In the committed 2026-10-12 snapshot, 16 distinct records shared 3 identities. The identity now also covers the text. State written under the old identity is still honoured only when no other record in the sink shared that old identity; a record whose old identity was shared is routed once more, so the worst outcome is a duplicate and never a loss. Only new identities are written from now on, and the harvester and completion routing apply the same rule from one shared module (INF-400b-2-iii)."
---

## Entry

Fix commit 1ae8eea20 on branch fix/harvest-identity-includes-text. Decision: BrainCandy, 2026-10-12, option A. Note: every record in the committed snapshot is classified unclassified with the destination (unrouted), which the harvester leaves unrouted by design, so no learning in that snapshot had actually been lost yet; the defect would have bitten the first time same-second records carried a routable kind.
