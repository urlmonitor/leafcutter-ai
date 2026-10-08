---
title: "Decision records: publish the kernel's 'what to build next' and product-truth modelling decisions (#KernelDecisionStore)"
date: "2026-10-02"
time: "08:10"
type: manual
components: 
  - decision_kernel
summary: "Two decisions the user approved through the Decision Kernel are published into docs/decisions for review: dec-d53e1c52cd47c832 (make the kernel the default entry for design, planning and lookup questions in Claude Code sessions) and dec-5e7445182eaec1f2 (model the decision lifecycle in product truth as one parent flow whose steps expand to four sub-flows)."
description: "Both were decided end to end by the kernel with Claude Code as host: grounding research, host-proposed options and criteria approved by the user, a Jev-ranked comparison, and the user's choice. They were staged in their runs' artifacts and published with python -m kernel decisions publish, which validated them and regenerated docs/decisions/index.json (3 records). The first run (run-f0f15b38791a428f) chose the option ranked first; the second (run-7c7d6474612b438b) chose the option ranked second."
---

## Entry
