---
title: "Five product-truth generator requirements can be built again"
date: "2026-10-14"
time: "21:30"
type: manual
components: 
  - ux_prototyping
  - build_orchestration
summary: "Five requirements for the product-truth generator were recorded as in progress, which the fast lane reads as claimed by a running build, so it refused to build them. They are now recorded as not started, which is what they are."
description: "UXP-510 to UXP-514 were moved from done back to in progress on 7 September, because their code had landed but no test proved them. The fast lane treats in progress as claimed by a build that is running now, so pointing it at any of them refused before doing any work, although nothing was building them. They are now recorded as to do, the state the fast lane itself writes when it lets go of a claim, and each record notes why. What is still missing for each, its tests, is unchanged and still described in the record. The product-truth flow that maps the generator now shows those steps as not started instead of in progress."
---

## Entry
