---
title: "Knowledge management: the kernel-run test fixtures answer the graph-read question"
date: "2026-10-06"
time: "15:40"
type: manual
components: 
  - knowledge_management
summary: "Five knowledge tests that failed on main since 2026-10-04 pass again, and they now check that the graph-read choice is actually asked."
description: "Since 2026-10-04 every natural-language retrieval asks Jev which bounded graph read to run (DK-300d-4). Two full-run test fixtures never scripted an answer, so every retrieval child failed and five tests ended blocked or partial in strict mode. Both fixtures now answer with the component-context read, the binding used before that change, and the full-run test asserts the question was asked and the chosen read recorded, so a future bypass of the choice fails. No production code changed. The integrations README now says to run the knowledge tests in strict mode after bridge changes. Ticket: KnowledgeFixturesAnswerOperationSelect (2026-10-06)."
commits: []
---

## Entry
