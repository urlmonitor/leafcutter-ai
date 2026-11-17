---
title: "A knowledge publication is refused before it would fill the store"
date: "2026-10-20"
time: "16:00"
type: manual
components: 
  - knowledge_management
summary: "Before writing anything, a knowledge publication now measures how full the database is and refuses a snapshot that would push it past the declared capacity threshold, so a sync can no longer be the write that latches the hosted store read-only."
description: "Nothing measured headroom before a publication wrote, so the hosted Neo4j instance could fill up and latch read-only mid-sync, after which even cleanup was impossible. Every publication now counts the database's nodes and relationships before its first write. With a declared ceiling (sync flags --capacity-max-nodes, --capacity-max-relationships, --capacity-refuse-percent and --capacity-warn-percent, all four or none), it refuses before writing when usage plus the snapshot would exceed the refuse percentage on either axis, naming usage, ceiling, snapshot size and shortfall per axis and stating that the figures were measured; above the warning percentage it proceeds and warns with the remaining headroom. A database already latched read-only is refused as a capacity condition, never reported as an empty result. Neo4j does not report its own capacity, so without a declaration the headroom is reported as unknown and never counted as fitting; publication still proceeds. The sync result carries the headroom report as capacity. The GitHub sync workflow declares the Aura Free ceiling of 200,000 nodes and 400,000 relationships with refuse 90 and warn 75; the workflow itself stays disabled."
---

## Entry
