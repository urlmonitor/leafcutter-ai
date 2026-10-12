---
title: "Close TQ-600a-5 and document the marker declaration"
date: "2026-09-30"
time: "11:10"
type: manual
components: 
  - testing_quality
  - ticket_lifecycle
summary: "Closes TQ-600a-5 and writes the two documentation surfaces its ticket contracted for but never had dispatched."
description: "TICKET-20260929-TQ-600a-5 moves to 99_done with status done, via set_ticket_status.py with the transition allow-list and agents parity enforced rather than bypassed. The documentation was a real gap: the ticket carried documentation_required true and documentation-expert was never run, leaving CLAUDE.md's standing rule telling authors to request the shared_reference_layout fixture while saying nothing about markers. From the moment PR #957 merged, an author following that rule exactly would write an unmarked test, be routed to a private copy, and silently pay the full deploy cost while believing they were sharing. CLAUDE.md now states the declaration requirement with both registered marker spellings quoted verbatim, the undeclared case described as fail-safe but expensive, and the note that strict_markers must remain a direct ini key because the addopts spelling enforces nothing on pytest 9.0.3. docs/testing/test-angles.md records the boundary as three cases rather than two, since a two-branch implementation's natural default routes the undeclared case to the shared layout, which is the corrupting direction. Four phase rows were reconciled to reflect work done outside a phase dispatch, with the ticket's own comments recording which rows represent real agent runs and which represent coordinator work. Finalized by hand rather than via /finalize-feature, whose Step 3.5 flips every inbox ticket and AC to done store-wide while TQ-600a-2, a-3, a-4, a-6, a-7 and a-8 are all legitimately todo; a sibling baseline captured before and after confirms all six unchanged and the closure commit touching exactly three files."
---

## Entry
