---
title: "A routing run that leaves a learning waiting now says so in its case"
date: "2026-10-09"
time: "15:00"
type: manual
components: 
  - knowledge_system
  - build_orchestration
summary: "When a learning reaches the sink after a run's routing step has read it, the run's knowledge_routing case is now completed_with_waiting, not completed. completed now means nothing is left waiting. fast-lane-ship, quick-fix and build-epic trust the new case as a completed result and report it separately; build-epic counts waiting tickets as waiting_tickets. INF-700a-5-ii is done."
description: "One content commit: 09a05b2a0. completion_routing.observe_publication turns a completed run whose waiting difference is above 0 into case completed_with_waiting, and keeps the waiting field. fast-lane-ship.js and quick-fix.js add the value to KNOWLEDGE_ROUTING_SCHEMA's case enum, and classifyKnowledgeRouting trusts any value in that enum, so the new case passes through with its figures. build-epic.js trusts it, keeps a per-ticket waiting count, and adds waiting_tickets to the drive totals; per-ticket counts are not summed. fast-lane-ship.js and quick-fix.js shrink under the file-size ratchet. New tests in unit_tests/workflows/test_inf_700a_5_ii_case_with_waiting.py run the real CLI on a real sink and scratch git, and drive all three workflows under the engine harness. knowledge-routing-step.md now lists four cases; the how-to's Step 1 explains the new one. INF-700a-5-ii is flipped to done."
commits: 
  - 09a05b2a0
breaking: false
---

## Entry

The commit, pull-request and finalize agents can emit a learning after a run's routing step
has read the sink. The next run routes it. Until now the run still reported
`case: completed`, and the wait showed up only as a count in a separate `waiting` field.

- **New case: `completed_with_waiting`.** `observe` reports it when the run completed and at
  least one record reached the sink after the stage read it. `completed` now means nothing is
  left waiting. The `waiting` field is unchanged.
- **Trusted, never folded in.** fast-lane-ship and quick-fix pass the new case through with
  its figures. It is not merged into `completed` and is not counted as `did_not_run`. It does
  not change the run's own status.
- **Epic drives count it.** build-epic keeps each ticket's case and waiting count, and adds
  `waiting_tickets` to the drive totals.
- **INF-700a-5-ii done.** Its last uncovered descriptor (an unread record is not reported as
  routed, written or nothing-to-do) now has a test that runs the real CLI.

/build-feature drives are not wired to routing yet. When they are, they must trust
`completed_with_waiting` too.
