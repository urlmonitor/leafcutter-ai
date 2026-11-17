---
title: "A failed generation removal that is refused is reported, not hidden"
date: "2026-10-15"
time: "01:00"
type: manual
components: 
  - knowledge_management
summary: "When a failed knowledge publication cannot remove the generation it stored, the failure now says so: it names the repository and generation left behind, the store's refusal, and what remains, or that the remaining amount is undetermined, never 0."
description: "A publication that fails after storing removes its own generation in the same operation. If the store refused that removal, the result used to say only 'failed generation not removed: <reason>'. Both deletes, relationships and then nodes, are now attempted whatever happens to the first, and the outcome is one of three. Removed reports the figures counted beforehand. Partially removed names the kinds that remain. Not removed means both deletes were refused. The last two name the repository and generation, the refusal received, and the nodes and relationships still tagged to that generation, counted afresh, or 'remaining amount undetermined' when the store also refuses the count. The original failure cause stays first in the message. The retention reference lists every message form and outcome, and says a generation left behind is not removed automatically yet."
---

## Entry
