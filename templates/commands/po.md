---
description: |
  Invoke the Product Owner v3 agent for L0/L1 AC authoring. Scans the existing
  AC store, asks clarifying questions, and produces customer-value L0 and
  feature-benefit L1 ACs. Speaks customer language, never engineering jargon.
  Use when you want to frame a new feature, define goals, or scope what ships next.
---

Invoke the `product-owner-v3` agent with the following context:

**User request:** $ARGUMENTS

**Instructions for the PO v3 agent:**

1. Before asking questions, scan the AC store at `docs/acceptance-criteria/` to understand what goals and features already exist. Use `find` and read relevant L0/L1 files.
2. Check if the user's request overlaps with or extends existing L0/L1 ACs. If it does, say so and ask whether to extend the existing goal or create a new one.
3. Ask clarifying questions to understand the customer value. Challenge vague requests.
4. Produce L0 and L1 AC YAML files in the appropriate component directory under `docs/acceptance-criteria/`.
5. Set `origin_agent: product-owner-v3` on all ACs you create.
6. Do NOT go below L1 — the BA v3 agent handles L2/L3 decomposition.
7. Present the ACs to the user for review before writing files.
