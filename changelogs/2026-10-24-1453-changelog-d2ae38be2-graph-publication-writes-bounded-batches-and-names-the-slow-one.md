---
title: "Changelog d2ae38be2 — graph publication writes bounded batches and names the slow one"
date: "2026-10-24"
time: "14:53"
type: manual
components: 
  - knowledge_management
summary: "Publishing the project graph no longer sends one oversized batch past the writer's time limit: batches are bounded by size as well as rows, a timed-out batch is retried, and a failure names the phase and the exact batch."
description: "One commit (d2ae38be2, feat). New knowledge/adapters/neo4j_writes.py: write batches close at 250 rows or 2,000,000 bytes of payload, and an oversized record is written alone and named (KM-400b-5-iii). Each batch is verified by content fingerprint (KM-400b-5-iv). A time-limit failure is retried up to 3 attempts, 1 s apart, and only time-limit failures are retried; a connect timeout counts as unavailable (KM-400b-5-v). A failed publication names the phase, the batch (kind, batch N of M planned, rows, bytes), the attempts and the completed progress, as fields on the sync CLI error JSON as well as in the message (KM-400b-5-vi). docs/how-to/run-knowledge-retrieval.md describes it. The four figures are built-in defaults that cannot yet be set from configuration."
adrs: []
commits: 
  - d2ae38be2
breaking: false
---

## Entry
