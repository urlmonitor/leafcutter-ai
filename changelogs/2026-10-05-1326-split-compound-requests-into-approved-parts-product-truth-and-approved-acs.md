---
title: "Split compound requests into approved parts: product truth and approved ACs"
date: "2026-10-05"
time: "13:26"
type: manual
components:
  - decision_kernel
  - ux_prototyping
summary: "Specified how the decision kernel splits a request that bundles several questions into two to five person-approved parts, and approved the 57 DK-400 ACs."
description: "Product truth for goal splitting: a Decomposition entity in the decisions mock data (triggers, eight states including rejected_clarify, verbatim covers quotes, dropped and not-covered parts, per-part outcomes), the split steps and twelve branches in the decision-forming flow, and the split approval and progress mockups. Rules decided at the gates: split also requests the kernel would accept as one, never split a single question or a caller-supplied decision_request, only a person answers the split gate, and a rejected split ends blocked (no capability), falls back to today's clarification question (ambiguous), or goes ahead as one (accepted or mid-run). Planning only: no runtime code."
---

The split interfaces (the goal_decomposition request and proposal, the split record and the split-answer schema) are not built. They are recorded as explicit missing bindings under main's JSON-contract rule, and ADR-067 is to pin them before the first build ticket. Mid-run splits are specified to ship dormant, exercised only through an injected test producer.

This tree supersedes TICKET-20261002-KernelDecomposeMultiPartGoal and TICKET-20261001-KernelCompoundGoalSplit once it merges.
