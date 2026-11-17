---
title: "The Atlas Flows page opens on a finder: search every flow and step, filter by who runs it, share the search"
date: "2026-10-14"
time: "22:00"
type: manual
components: 
  - ux_prototyping
  - atlas_frontend
summary: "Bare /flows is now a finder. Search flow names, step text, input and output fields, criteria, entities and screens; narrow with counted filters including who runs a step (Code, AI agent, Person or Jev) and steps whose I/O is not defined yet; open a result straight at its step; and share the search as a link."
description: "Builds the 15 approved UXP-617 criteria and reworks six UXP-591 ones. The finder groups results by flow, shows why each step matched, recounts every filter as you narrow, and offers to remove a filter when nothing matches. The search lives in the /flows address, written once after you stop typing, so a link reproduces it; opening a result goes to its flow or step address in place and Back returns the finder as you left it. On flow pages a filter change no longer swaps the flow you are viewing - an 'Outside the current filters' notice explains it instead - step cards show who runs them and open with Enter, the close button is named, every flow page has its own tab title, and criterion chips open that criterion in the Atlas. A how-to and an address reference document the finder. Tests are vitest, written before the code (366 passing); the build pipeline's own checks cannot read vitest tests yet, so the epic was built by dispatching its phases directly."
commits: []
---

## Entry
