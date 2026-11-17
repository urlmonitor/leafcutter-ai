---
title: "Atlas flows have canonical, shareable addresses"
date: "2026-10-12"
time: "18:00"
type: manual
components: 
  - ux_prototyping
  - frontend_coding
summary: "Every product-truth flow in the Atlas now opens at its own address, such as /flows/leafcutter/flow-render-pipeline, and a step address (?step=) opens that step's drawer. Old /flows?flow= links redirect, and Back/Forward walk the flows you visited."
description: "Builds the 20 approved UXP-591 acceptance criteria. A flow's canonical address /flows/<product>/<flow> opens the Atlas with that flow selected and drawn; bare /flows keeps its address and opens the default entry flow; an unknown flow, a percent-encoded slash or a trailing slash shows 'Flow not found' with a 404. Adding ?step=<id> opens that step's or branch's drawer, and an unknown step shows 'Step not found' without a 404. Old /flows?flow=...&step=... links get a permanent 308 to the new addresses. The 'Appears in flows' links in an acceptance criterion's detail now point at the exact step address. Opening, switching or closing a drawer replaces the address without a Back entry; selecting a flow, drilling into one or clicking a breadcrumb adds one; Back and Forward restore each entry as it was left; filter changes re-pick the flow only when the current one is filtered out. Built with vitest tests written before the code (267 passing). The Playwright end-to-end checks the plan named are deferred, and the build pipeline's own red-baseline and done-proof checks cannot read vitest tests yet, so the epic was built by dispatching its phases directly."
commits: []
---

## Entry
