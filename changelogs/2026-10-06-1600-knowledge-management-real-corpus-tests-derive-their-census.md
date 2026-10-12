---
title: "Knowledge management: the real-corpus tests derive their census from the stores, and a changelog without frontmatter fails"
date: "2026-10-06"
time: "16:00"
type: manual
components: 
  - knowledge_management
summary: "Six knowledge tests no longer break whenever the repository gains a changelog, decision, flow, dataset, mockup or ticket."
description: "The native-reader tests over the real repository pinned exact population totals (changelog entries, decisions, flows, mock datasets, mockups, tickets, field counts), although the acceptance criteria call those counts observations, not requirements, so every content addition turned main red. Each test now computes its expected set from the store files and the product-truth index, independent of the reader under test, and keeps set equality, per-record deep equality, the round trip and byte-for-byte no-rewrite checks, plus named reviewed anchors (the three recovered malformed changelogs are pinned by path). By owner decision a changelog with no frontmatter now fails extraction, naming the file and the reason. The empty changelog committed on 2026-10-05 now carries its real entry, and the changelog known issue records the occurrence. Ticket: KnowledgeRealCorpusTestsDeriveCensus (2026-10-06), superseding the counts ticket on PR 995."
commits: []
---

## Entry
