---
title: "The Atlas frontend is findable, and ADR-066 records how the kernel resolves named terms"
date: "2026-10-10"
time: "09:30"
type: manual
components: 
  - atlas_frontend
  - decision_kernel
summary: "Atlas now has a component entry, a component doc and a glossary entry. ADR-066 records how the decision kernel researches a term it cannot resolve and finds its own repository root."
description: "A kernel run once could not tell what \"Atlas\" meant: the Next.js frontend in leafcutter-web had no component registration, no component doc and no glossary entry, so retrieval found nothing. This change registers atlas_frontend in components.json, adds docs/architecture/components/atlas-frontend.md and adds a glossary entry. ADR-066 records the decision: when a goal or a human answer names something the kernel cannot resolve, it researches the term before ranking, reports an option with no evidence as unresearched instead of scoring it, finds its own git repository root from the topmost folder, and records every request it cannot serve in one central store. The ADR is listed in the ADR index and linked from the decision-kernel component doc. Documentation only, no code."
commits: []
---

## Entry
