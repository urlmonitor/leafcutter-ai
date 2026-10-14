---
title: "Retention reports nodes that no generation record accounts for"
date: "2026-10-15"
time: "07:30"
type: manual
components: 
  - knowledge_management
summary: "The knowledge retention evaluation now counts the entity nodes each generation holds and reports how many nodes name a generation that has no record, stating 0 explicitly rather than assuming none."
description: "The evaluation only ever looked at generation records, so nodes left behind by a generation whose record was gone could not be seen. It now reads, without writing, how many entity nodes carry each generation key and reconciles them against every generation record, failed publications included. Each verdict gains entity_nodes, the report gains unaccounted_nodes and unaccounted_generation_keys, and a zero is stated rather than omitted. A backend that cannot count nodes is reported as undetermined, never as 0. Unaccounted nodes are only measured here; nothing reclaims them. The retention reference documents the new fields."
---

## Entry
