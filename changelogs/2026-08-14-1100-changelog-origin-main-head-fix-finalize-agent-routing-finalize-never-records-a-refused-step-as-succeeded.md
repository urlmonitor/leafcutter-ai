---
title: "Changelog origin/main..HEAD (fix/finalize-agent-routing) — finalize never records a refused step as succeeded"
date: "2026-08-14"
time: "11:00"
type: manual
components: 
  - finalize
summary: "Fixed a bug in the release-finalization tool that could let an unmerged, unintegrated branch reach main while logging that the merge had succeeded."
description: "1 commit (91159eab3). Bug Fixes: Step 2 (merge origin/main into the worktree) treated any unrecognised agent status as success — a live run returned status=refused and finalize logged \"Merged origin/main cleanly\" and proceeded toward merging to main with the branch never integrated. Added isRefusalStatus() (refused/wrong_agent/declined/not_permitted/out_of_scope*) so a refusal halts naming the step instead of falling through to success; Step 2 now only succeeds on an explicitly-matched \"merged\" result. Step 0 (pre-merge test baseline) now halts on a refusal too, while run_failed/parse_failed keep their existing conservative null-baseline degrade (those did run). Also rerouted the Step 0 and Step 2 dispatches from agentType status-checker to general-purpose — status-checker is scoped to ticket-state verification and correctly refuses git-worktree provisioning, build.py, pytest, and git merge; the 20 dispatches that are genuine ticket-state work keep status-checker."
commits: 
  - 91159eab3
---

## Entry

- Category: Bug Fixes (Fixed)
- AC: FIN-100h
- Component: finalize

### Known issues / caveats

FIN-100 (the L0 this fix's AC, FIN-100h, belongs to) now carries
`child_limit_override: 8` — 8 L1 children against a default cap of 7. The
waiver comment on FIN-100.yaml records that the tree is a Pattern A split
candidate (ac-tree-split) and should be revisited before a 9th child lands.
