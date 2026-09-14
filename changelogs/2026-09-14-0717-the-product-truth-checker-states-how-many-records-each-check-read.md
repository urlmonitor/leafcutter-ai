---
title: "The product-truth checker states how many records each check read"
date: "2026-09-14"
time: "07:17"
type: manual
components: 
  - ux_prototyping
summary: "Every check the product-truth checker runs now reports how many records it read, so 'it examined something' is a figure you can verify rather than a claim."
description: "The checker already said whether a run examined anything at all, but not what each check actually looked at -- so a check that silently stopped reading journeys would report exactly as it did when it read every one. Its structured result line now carries examined_by_check: for each check it performed, how many records that check read (UXP-700b-2). The figures are the sizes of what that run loaded, so adding one journey raises every journey-reading check by exactly one, removing one lowers it by one, and nothing is carried over from an earlier run. On this repository's own record the figures match independent counts from disk: 14 journeys, 2 example datasets, 10 screens, 117 pointers. Internally, the checker's bookkeeping moved into the module that already owns its outcome rules, keeping the checker inside its file-size limit."
commits: 
breaking: false
---

## Entry
