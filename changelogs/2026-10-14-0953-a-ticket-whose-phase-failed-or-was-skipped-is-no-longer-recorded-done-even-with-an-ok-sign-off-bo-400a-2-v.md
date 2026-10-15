---
title: "A ticket whose phase failed or was skipped is no longer recorded done, even with an ok sign-off (BO-400a-2-v)"
date: "2026-10-14"
time: "09:53"
type: manual
components: 
  - build_orchestration
summary: "/build-feature and /build-ticket no longer mark a ticket done when a required phase is marked failed in the ticket or was skipped by the run, even if the record holds an ok sign-off for that phase."
description: "completionVerdictFromRecord took the last Comments entry in file order as a phase verdict, so an older, misplaced or premature ok overruled the frontmatter failed value and the run own cross_agent skip. New pure failureSignalFor() in build-feature.js and build-ticket.js is consulted per required phase before entries are read: a phase in record.failed_phases or ctx.skippedAgents is outstanding, and the not-completed report names the phase and the signal. The unreadable-record and empty-required-set guards still answer first. A frontmatter value of needed is intentionally not a failure signal here, because set_ticket_status.py already refuses done while a phase reads needed. Addresses KI-BO-20261009 (blocker: completion write closes a ticket whose gate failed; occurrences 2026-09-30 and 2026-10-12); the KI file is not moved to resolved by this commit. AC BO-400a-2-v, covered by 5 behavioural tests in unit_tests/prompt_assembly/test_bo_400a_2_v.py. Historical comment narration was condensed in both drivers to stay under the file-size ratchet (comment lines only)."
commits: 
  - 85adb7369
breaking: false
---

## Entry
