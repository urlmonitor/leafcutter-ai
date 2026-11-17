---
title: "A successful knowledge publication reclaims superseded generations"
date: "2026-10-16"
time: "10:00"
type: manual
components: 
  - knowledge_management
summary: "After a knowledge publication switches the active pointer, it now deletes the old generations the declared retention bound permits and reports how many were reclaimed and why each other one was kept, so the hosted store no longer fills up with superseded copies."
description: "Every publication wrote a new full generation and nothing ever removed old ones, which filled the hosted Neo4j instance to its 400,000-relationship cap twice. When a retention bound is declared, a successful publication now reclaims, in the same operation and after the pointer switch, every generation the retention evaluation permits. It acts only when the evaluation fully assessed the store, never touches the active generation, a generation still being published, or another repository, and deletes each generation by its own key with its record last. Continuations are signed tokens that expire at most an hour after first issue, so a generation with no recorded pin is reclaimed only once it is older than that lifetime; a recorded future pin is kept. The lifetime is one shared setting used by both the token code and reclamation. A failure during reclamation is logged and reported but never turns the successful publication into a failure. The result reports reclaimed and retained counts, 0 stated, with a reason for each retained generation; a failed or stale publication reclaims nothing. The sync command takes the bound as --retention-max-generations and --retention-min-age-seconds, and the GitHub sync workflow now declares 3 generations and 7200 seconds. The workflow itself stays disabled."
---

## Entry
