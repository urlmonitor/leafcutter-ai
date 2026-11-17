---
title: "UX prototyping: the product-truth store tests copy every planning source a flow declares"
date: "2026-10-06"
time: "15:50"
type: manual
components: 
  - ux_prototyping
summary: "Nine product-truth store tests that failed on main since 2026-10-05 pass again."
description: "The checked I/O contracts let a flow name a planning document as the source of a binding that is not defined yet, and the validator requires that document to exist. The bounded store the UXP-300 tests build copied contract schemas and example receipts but not those planning sources, so once a flow pointed at a document under docs/analysis the fixture's own validator baseline failed and nine tests failed with it. The fixture now copies every declared source on every step and branch (only declared paths, not the whole folder), and a self-check names any declared repository file the fixture lacks. The validator and the flows are unchanged. Ticket: Uxp300FixtureCopiesMissingBindingSources (2026-10-06)."
commits: []
---

## Entry
