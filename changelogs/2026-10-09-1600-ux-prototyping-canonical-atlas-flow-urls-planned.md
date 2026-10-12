---
title: "UX prototyping: canonical, shareable Atlas flow URLs are planned and approved"
date: "2026-10-09"
time: "16:00"
type: manual
components: 
  - ux_prototyping
summary: "Product truth and 20 approved acceptance criteria for giving every Atlas flow its own shareable link, such as /flows/leafcutter/flow-render-pipeline."
description: "Planned through the product-truth pipeline with the owner deciding at each gate. A new canonical dataset records how flow and step links resolve: bare /flows, a 404 for unknown flows, a step notice for unknown steps, the legacy 308 redirect, and which actions add browser history entries and which replace them. A new mockup shows every state. The explore-flows-in-atlas flow gains twelve steps and branches with checked input and output contracts. Twenty acceptance criteria under UXP-591 are approved at medium priority, with technical decisions for middleware redirects, history state, trailing slashes and a Playwright suite for real-browser proof. No application code yet: building the criteria is the next step."
commits: []
---

## Entry
