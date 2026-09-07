---
title: "Three build-feature dispatch defects, found by driving an epic and watching it"
date: "2026-09-01"
time: "11:30"
type: manual
components: 
  - build_orchestration
  - ticket_lifecycle
summary: "Register entries plus a Master_Plan correction. One /build-feature run on EPIC-TheNumberingGuaranteeHoldsAtEveryStage completed 0 of 12 tickets and produced three known-issues entries: the commit-phase lock that was never implemented, the phase list that is frozen before the first phase runs, and the handoff contract split across an agent template and the driver that reads it."
description: "No production code in this entry; the two driver fixes it documents ship separately in PR #687. The drive halted at batch 1 with epic_complete false and completed_batches empty, so it reported honestly rather than claiming success. KI-BO-20260901-1000 (blocker): driveTicketPhases computes its phase list once, before any phase runs, so a phase promoted to needed mid-drive is never dispatched; architect-review promotes adr-author exactly that way, and phaseOrder compounds it by placing the decider after the phases it gates. Cost 2 of 4 tickets. KI-BO-20260901-1052 (high): python-coder.md defines a handoff as a section written into the ticket plus status handoff, and never mentions the handoff_target field the driver requires, so an agent that followed its template was refused; cost the only ticket that produced working code. KI-BO-20260901-0920 (medium, downgraded from high mid-investigation): the commit-phase serialization lock is specified in building-epics section 5, its prescribed helper scripts/epic_lock.py was never written, and the flattened driver that inherited the responsibility takes no lock; the predicted index contamination did NOT occur because the commit agent commits by explicit pathspec, and the non-occurrence is recorded as prominently as the defect. Also corrects two stale dependency claims in the epic's Master_Plan."
---

## Entry
