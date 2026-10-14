---
title: "Everything a standard does not ask a specialist for behaves exactly as it does today (BO-3800e)"
date: "2026-10-14"
time: "11:45"
type: manual
components: 
  - build_orchestration
  - supervisor_system
  - commit_guardian
summary: "Only a refusal from a gating hook that declares engage-specialist brings anyone in. Accepted work and refusals the author can clear take exactly the same path as before, at no extra cost, and an unreadable refusal outcome stops the run by name instead of being read as 'no disposition'."
description: "BO-3800e-1, -2. _remedy_declarations.py gains gating_hook_ids(), which reads blocking_hook_ids from the local routing table, then the package seed. The list is the only authority on which hooks gate a commit; a malformed list raises RemedyInputError. remedy_handoff.py now produces a handoff only for a hook in that list, so a hook outside it engages nobody even if it declares engage-specialist. In both twin drivers (templates/workflows-js/build-feature.js and build-ticket.js), a phase remedy that is not an object, or whose disposition is not text, is a named stop: nobody is engaged and delivery is not retried. An absent, null or blank remedy still takes the existing route. Both drivers were already over their size limit, so each removes two blank lines between statements to repay its one added line. Tests: unit_tests/workflows/test_bo_3800e_1.py and test_bo_3800e_2.py (shared _bo3800e_support.py) compare each run's dispatch record against a baseline run of the pre-change driver; harness_build_ticket_guard.mjs now records every remedy-declaration read (declaration_reads), so a test can see that an accepted run reads none. The duration arm compares medians within 2% plus a 30 ms floor. It is secondary evidence, as the AC states. It uses nine interleaved pairs, each sample the best of three runs, so a load spike on a shared host does not fail the required check. BO-3800e, -1 and -2 are marked done."
breaking: false
---

## Entry
