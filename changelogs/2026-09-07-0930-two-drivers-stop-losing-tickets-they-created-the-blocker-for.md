---
title: Two drivers stop losing tickets they created the blocker for
date: "2026-09-07"
time: "09:30"
type: manual
components: 
  - build_orchestration
summary: "build-feature.js and build-ticket.js each had two dispatch defects: a per-ticket phase list frozen before the first phase ran, so a phase promoted mid-drive was never dispatched, and a handoff contract split across an agent template and the driver that read it. Found by driving a real epic that completed 0 of 12 tickets."
description: "BO-3700 and BO-3701: driveTicketPhases computed its phase list once, before any phase ran, then iterated that captured array. architect-review promotes adr-author to needed whenever it concludes an ADR is required, so the driver routinely created a blocker and then declined to clear it, reporting the ticket incomplete because adr-author was never dispatched. The signal was never missing: the post-dispatch read-back already returned needed_phases and the driver already parsed it, but that reply fed the completion decision and never the dispatch decision. The pending set is now re-derived from it and re-sorted by canonical priority, because a promoted phase usually has an earlier priority than its promoter. BO-3000a and BO-3000: python-coder.md defined a handoff as a ticket section plus status handoff and never mentioned the handoff_target field the driver routed on, so an agent that followed its template exactly was refused. A first fix taught the driver to infer the target from the ticket body and was rejected on review: that section is the general per-agent task breakdown carried by 13 agents, ambiguous by construction, and inference would have re-dispatched an agent on a deliberate targetless halt. The contract is now explicit in the agent templates and declared in PHASE_RESULT_SCHEMA with a conditional requirement, and the refusal distinguishes an absent target from a named-but-unrecognised one. Both drivers received both fixes; the twin was a generation behind on handoff and entirely unfixed on the phase list, and a naive mirror would have introduced two new bugs because build-ticket.js sorts unknown agent names last rather than rejecting them and nulls its record on an unreadable read-back. A twin-parity test now asserts the promotion behaviour across both drivers, so the divergence the header comment asked readers to prevent manually is detected by a run."
breaking: false
---

## Entry
