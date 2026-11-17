---
title: "A retention evaluation the store refused says so instead of reporting nothing to reclaim"
date: "2026-10-15"
time: "08:00"
type: manual
components: 
  - knowledge_management
summary: "When the store refuses the reads a knowledge retention evaluation needs, the report now says it could not assess the store, names each refusal, and gives undetermined figures, instead of failing or reading as zero generations with nothing to reclaim."
description: "A refused read used to either escape as an error or, worse, look like an empty store: zero generations assessed and nothing reclaimable. The evaluation now carries an assessment with a status of assessed, partial or could_not_assess, the refusals received with the backend's own text, and which parts succeeded and which could not be completed. When the generation records cannot be read, every figure is undetermined and no verdict is made. When only the node counts are refused, the verdicts stand and the node figures are undetermined. A refusal that names a read-only store adds a read_only entry stating that reclaiming space is blocked while it holds. The helpers live in the new neo4j_retention_assessment module, and the retention reference was split so the evaluation details have their own page."
---

## Entry
