---
title: "finalize-feature now names a learning that never reached main before removing the worktree"
date: "2026-10-09"
time: "16:00"
type: manual
components: 
  - knowledge_system
  - worktree_manager
summary: "Before finalize-feature removes a worktree, it now lists every routed learning written there that the merged tree does not hold, with its destination, reason, text and whether it will be written again. The removal still runs; nothing about the run's outcome changes."
description: "One content commit (cb0cdcbda). finalize-feature.js Step 7, before the worktree-agent removal and only when the worktree exists, dispatches the existing read-only `completion_routing_cli.py observe --working-dir <worktree> --commit-status ok` (label step-7-unpublished-learnings). Each unwritten record is logged, prepended to the removal prompt and returned as unpublished_learnings. An unusable reply degrades to an empty list; the removal and the run's status are unaffected. To stay inside the file-size ratchet, a readAgentJson helper replaces 17 duplicated parse blocks (measured length 1802 to 1730). INF-700a-5-i is marked done with its covering tests listed. One new subsection in docs/reference/knowledge-routing-step.md."
commits: 
  - cb0cdcbda
breaking: false
---

## Entry

`finalize-feature` is the only completion path that removes a worktree. A learning
written in that worktree but never carried into main used to disappear with it, unremarked.

- **Step 7 now announces it first.** Before the removal, the workflow runs the existing
  read-only `completion_routing_cli.py observe` in the worktree. Each learning the merged
  tree does not hold is named with its destination, reason, text, and whether it is still
  eligible to be written by a later run. The list goes to the log, to the removal agent's
  prompt, and to `unpublished_learnings` on the result.
- **It never blocks.** If the check cannot run, the list is empty and the worktree is
  removed as before. The run's status and step record are the same either way.
- **Smaller file.** A `readAgentJson` helper replaces 17 copies of the same parse-and-fallback
  block in `finalize-feature.js`, which keeps the file under its size ratchet.
- **INF-700a-5-i** is marked done.
- **Docs:** new subsection "Announcement before worktree removal" in
  `docs/reference/knowledge-routing-step.md`.
