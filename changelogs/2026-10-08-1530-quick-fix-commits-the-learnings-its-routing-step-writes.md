---
title: "/quick-fix now commits the learnings its routing step writes"
date: "2026-10-08"
time: "15:30"
type: manual
components: 
  - build_orchestration
  - knowledge_system
summary: "/quick-fix ran its Knowledge Routing step before the fix commit, then told the commit agent to stage exactly four files and nothing else, so every learning the step wrote was lost when the worktree was removed. The routing step now reports the files it wrote, and the fix commit stages them by name."
description: "One content commit (4810e2414). templates/workflows-js/quick-fix.js: the routing prompt asks its agent to take a git status --porcelain --untracked-files=all snapshot in the worktree before and after harvest_learnings.py and return the new paths as written_paths (added to KNOWLEDGE_ROUTING_SCHEMA), because the harvester prints only a prose summary and never names the files it wrote. A new routedStageEntries() appends those paths as numbered entries 5, 6, ... to the fix commit's stage list. It is fail-open: when the routing step did not run or wrote nothing, the commit prompt is byte-identical to before. It drops paths outside the worktree, paths containing '..', debugging/logs/ bookkeeping, duplicates, and the four files already listed. Never git add -A. New L3 AC INF-700a-1-iii under INF-700a-1, done, covered by unit_tests/workflows/test_inf_700a_1_iii.py, which drives the workflow under the E2 engine harness and asserts on the prompt the commit dispatch received. quick-fix.js went from 1066 to 1046 content lines, under the GE-127b-1 ratchet."
commits: 
  - 4810e2414
breaking: false
---

## Entry

`/quick-fix` runs its Knowledge Routing step before its fix commit, so that the routed
learnings can ride that commit. But the commit prompt said "Stage and commit exactly these
files" (four of them) and "Do not stage any other files". So every learning the step wrote
stayed uncommitted, and it was lost when the worktree was removed.

- **The routing step now reports what it wrote.** `harvest_learnings.py` prints only a prose
  summary, so the routing agent takes a `git status --porcelain --untracked-files=all`
  snapshot before and after the harvester and returns the new paths as `written_paths`.
- **The fix commit stages them by name**, as items 5, 6, ... after the AC, its parent, the test
  and the fix. Paths outside the worktree, harvester bookkeeping under `debugging/logs/`,
  and files already in the list are dropped. Nothing is staged by a sweep.
- **Nothing written, nothing changed.** If the routing step did not run or wrote nothing,
  the commit prompt is byte-identical to before.
- **New AC INF-700a-1-iii**, done, covered by a test that runs the whole workflow under the
  engine harness and checks the prompt the commit dispatch actually received.

Known limit: a destination that was already modified before the harvester ran is not
detected by the before/after snapshot. The complete answer is a write manifest from the
harvester itself, which INF-700a-5 already calls for.
