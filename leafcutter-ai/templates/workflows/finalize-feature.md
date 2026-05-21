---
description: >
  Invoke the finalize-feature agent, which orchestrates the 6-step post-merge
  feature finalization sequence (open PR if missing, merge, sync main, run tests,
  close tickets, remove worktree) with confirmation gates on all destructive steps.
---

Invoke the `finalize-feature` agent with the user's full request: $ARGUMENTS
