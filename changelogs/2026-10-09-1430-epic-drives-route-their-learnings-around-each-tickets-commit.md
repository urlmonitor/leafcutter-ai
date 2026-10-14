---
title: "Epic drives route their learnings around each ticket's commit"
date: "2026-10-09"
time: "14:30"
type: manual
components: 
  - knowledge_system
  - build_orchestration
summary: "A ticket-supervisor drive (build-epic.js, or a direct ticket-supervisor dispatch) now routes learnings around every ticket's commit. Inside the commit lock it runs stage, commits the stage's manifest by name, then runs one observe, as building-epics SKILL.md section 5.9 orders it. build-epic.js reports each ticket's knowledge_routing and the drive totals. An epic's N commits on one branch no longer write each learning N times. /build-feature drives (build-feature.js) are NOT routed yet, and their exclusion reason now says so."
description: "One content commit: 92d35ffbb. New SKILL.md section 5.9, referenced from the section 2.1 spawn step and from a note under the 2.1.1 table; ticket-supervisor.md's lock step, staging SOP and Outputs point at it. build-epic.js classifies each ticket's knowledge_routing (only completed/could_not_complete trusted) and sums it onto its ok and blocked results. completion_routing.stage_completion skips a record whose text HEAD already carries (not rewritten, not claimed, counted as already_on_branch). It re-stages, without a second append, text a refused commit left in the worktree. completion_routing_cli.py adds already_on_branch to its public stage keys and run-record keys. guardrail_gates.yaml: build-epic.js stays excluded (the build-time guard sees workflow files only), with covered_by naming SKILL.md section 5.9; build-feature.js's false 'completes nothing itself' reason is replaced with the truth. New AC INF-700a-1-iv."
commits: 
  - 92d35ffbb
breaking: false
---

## Entry

PR #1071 removed build-epic's routing step because no commit followed it, so epic drives
routed nothing. ADR-040 §3 puts the step in the building-epics skill, around each ticket's
commit.

- **Routed per ticket, inside the commit lock.** ticket-supervisor runs
  `completion_routing_cli.py stage`, has the commit agent stage the manifest by name, then
  runs exactly one `observe`. That observation is the ticket's `knowledge_routing`. A routing
  problem never fails the ticket.
- **The epic reports it.** build-epic.js puts each ticket's figures and the drive totals on
  its result, on a halted drive too.
- **One copy per branch.** The stage used to skip only learnings already on `origin/main`, so
  ticket 2 re-appended everything ticket 1 had committed. Learnings the branch already
  carries are now skipped and counted as `already_on_branch`.
- **Not yet routed: /build-feature drives.** build-feature.js runs its own per-phase driver
  and dispatches commit itself, so the skill does not reach it. Its exclusion used to say it
  "completes nothing itself". It now says what it actually does.
