---
title: "TICKET-20260716-BP-300e-5 — Prose-tolerant reply reading applied uniformly across delivery workflow scripts"
date: "2026-07-20"
time: "07:39"
type: ticket_completion
components: 
  - build_pipeline
summary: "Every agent-reply parse point in the delivery workflow scripts now routes through a single balanced-brace tolerant reader (parseAgentJson), so a reply that wraps valid JSON in surrounding prose no longer crashes a /plan-feature or /finalize-feature run."
description: "Squash-merged as 9133dcab via PR #339. Added parseAgentJson(raw,{stage,agent}) with byte-identical bodies to plan-feature.js, finalize-feature.js, build-epic.js, and build-ticket.js; migrated all 20 safeParseJSON sites in finalize-feature.js and 25 brittle typeof-ternary parses in plan-feature.js; build-feature.js unchanged (schema-only). Complements BP-300e-6/#340 writer-side JSON-only contract as the reader-side defense-in-depth. Ticket signed off and merged to main."
pr: 339
commits: 
  - 9133dcab
ticket: "TICKET-20260716-BP-300e-5"
---

## Entry
