---
title: "Knowledge management: consumer installs ship the knowledge query's rendering module again"
date: "2026-10-06"
time: "15:30"
type: manual
components: 
  - knowledge_management
summary: "The deployed knowledge query works again in consumer installs; it crashed on import since 2026-10-01."
description: "On 2026-10-01 the knowledge query's output rendering moved into its own sibling module, but that module was added to neither deploy list, so every consumer install's knowledge query failed on import with a missing-file error (this workspace's own install included). The two duplicated deploy lists are now one shared list that includes the module, and a new build guard runs the real deploy and fails when any sibling module a deployed workflow tool loads is not shipped byte-identical. After a rebuild the deployed knowledge query's help exits 0. Ticket: DeployKnowledgeRendering (2026-10-06)."
commits: []
---

## Entry
