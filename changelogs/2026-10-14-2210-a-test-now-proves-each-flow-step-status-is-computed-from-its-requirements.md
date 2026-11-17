---
title: A test now proves each flow step status is computed from its requirements
date: "2026-10-14"
time: "22:10"
type: manual
components: 
  - ux_prototyping
summary: "The product-truth generator already worked out each flow step status from the status of its requirements, but no test proved it. Four tests now do, and the requirement is marked done."
description: "UXP-510 says the product-truth generator recomputes every flow step status from the work status of the requirements that step implements, and totals those statuses for the flow. The code had been in place since July, but on 7 September an audit found no test that proved it, so the requirement was moved back from done. Four tests now drive the real generator against a small temporary store and check that a step with only finished requirements is done, a step with none started is not started, a mixed step is in progress, and the flow total matches its steps. Breaking the step calculation makes three of them fail and breaking the total makes the fourth fail. The generate-product-truth flow now shows its first step as done."
---

## Entry
