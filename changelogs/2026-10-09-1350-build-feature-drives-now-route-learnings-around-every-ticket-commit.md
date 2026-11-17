---
title: "/build-feature drives now route learnings around every ticket's commit"
date: "2026-10-09"
time: "13:50"
type: manual
components: 
  - build_orchestration
  - knowledge_system
summary: "Epic and single-ticket /build-feature drives now run the knowledge-routing step around each ticket's commit: stage, the commit staging the learnings by name, and one observe. Siblings in a batch take turns, and the drive's result reports each ticket's figures and the totals."
description: "One content commit (9a103366f). build-feature.js dispatches each ticket's commit phase itself, so building-epics section 5.9 never reached it. At that dispatch the drive now runs completion_routing_cli.py stage, appends the stage's manifest to the commit prompt to be staged by name (plain relative paths inside the worktree only, never debugging/logs/), then runs exactly one observe with --commit-status ok or failed. The three steps run in a drive-level lane, one ticket at a time, because the tickets of a chunk run concurrently in one worktree. Fail-open: an unrecognised or missing reply reads did_not_run and changes no outcome. completed_with_waiting (INF-700a-5-ii, PR #1100) is trusted as completed and kept as its own case with the ticket's waiting count. The epic and single-ticket results carry knowledge_routing (per-ticket figures, written, unwritten, already_on_branch, and waiting_tickets, the number of tickets in that case; waiting counts are not summed). config/guardrail_gates.yaml moves build-feature.js from excluded to wired. build-feature.js shrinks from 2641 to 2569 measured lines; duplicated and dead code paid for the addition. New L3 AC INF-700a-1-v; the driver harness gains routing replies and a combined timeline."
commits: 
  - 9a103366f
breaking: false
---

## Entry

`/build-feature` is the real entry point for epic and single-ticket drives, and until now it
routed **no** learnings. It dispatches each ticket's `commit` phase itself, so the
`ticket-supervisor` procedure (building-epics §5.9) never reached it.

- **Around each ticket's commit** the drive now runs the routing step's `stage`, then tells the
  commit to stage the learnings it wrote by name, then runs exactly one `observe`, on success
  and on failure alike.
- **One ticket at a time.** The tickets of a batch run concurrently in one worktree, so the
  stage, commit and observe of each ticket run in turn and never interleave.
- **Reported.** The drive's result now carries `knowledge_routing`: each ticket's figures and
  the totals written, unwritten and already on the branch. A ticket whose run completed
  with learnings still waiting (`completed_with_waiting`) is reported as such, and those
  tickets are counted separately.
- **Fail-open.** A routing reply that is missing or unrecognised reads `did_not_run` and
  changes neither the ticket's outcome nor the drive's.
- **`config/guardrail_gates.yaml`**: `build-feature.js` moves from `excluded` to `wired`.
- **Smaller file.** `build-feature.js` goes from 2641 to 2569 measured lines. Duplicated and
  dead code paid for the addition.
- **AC** `INF-700a-1-v`, with tests that run the drive through the driver harness.
