---
title: "Two /build-feature drive defects filed as known issues: a refused handoff and a lost red-baseline verdict"
date: "2026-10-09"
time: "18:45"
type: manual
components: 
  - build_orchestration
summary: "Driving EPIC-OneDurableLogRootForEveryWorkspace hit two /build-feature defects, both present on origin/main. A handoff to adr-author, which architect-review had just added, was refused as 'not on this ticket'. A red-baseline gate that passed was reported as unverifiable, because the relaying agent timed out and returned an empty output with exit code 0. Both are filed for the build-orchestration owner."
description: "One content commit (f1535a2d4), documentation only. Adds KI-BO-20261009-1832 (medium, low bucket): build-feature.js checks a handoff target against orderedPhases, the ticket-planner snapshot taken before any phase runs (:1936, check at :2392-2393), not the live read-back that absorbPromotedPhases has already used to queue the new phase (:2269-2275). architect-review set requires_adr and added adr-author: needed, then handed off to it; runs wf_6eeb35a5-324 and wf_20325042-622 halted, and the third run advanced only because the ticket already carried the key. Adds KI-BO-20261009-1833 (high): the heavy_lane_gate command is dispatched to status-checker (:2164-2168) with no timeout; on run wf_0648a71b-2ac it took about six minutes, the Bash call was backgrounded at 120s, and the agent returned {output: '', exit_code: 0}, taking the exit code from the completion notice and the output from an earlier empty read. The real stdout was gate_passed: true with nine red tests, and the gate recorded that pass in the ticket. The driver's fail-closed parse (:2169-2177) was correct. Index rows added; open 58 -> 60 (high 33 -> 34, low 21 -> 22). Line numbers are origin/main 282117ab5; the deployed copy built 2026-10-08 has the same logic."
commits: 
  - f1535a2d4
breaking: false
---

## Entry

Two `/build-feature` defects showed up while driving `EPIC-OneDurableLogRootForEveryWorkspace`.
Both are on `origin/main`, not only in the older deployed copy.

- **KI-BO-20261009-1832 filed** (medium). `architect-review` added `adr-author: needed` to the
  ticket and handed off to it. The driver refused the handoff as "not on this ticket", because
  it checks the target against the planner's opening snapshot of the agents map. Its own
  read-back from the same step already listed `adr-author`. Two runs halted this way. The third
  advanced only because the ticket already carried the key.
- **KI-BO-20261009-1833 filed** (high). The red-baseline gate took about six minutes. The agent
  relaying it hit its 120s timeout and returned an empty output with exit code 0. The real
  output said the gate **passed**, with nine red tests. The driver correctly refused to trust
  the empty reply, so the drive halted on a gate that had passed.

Both entries record the evidence from the run journals, the line numbers on `origin/main` and in
the deployed copy, a workaround (re-run) and a fix direction. No code changes.
