---
title: "finalize-feature now names a learning that never reached main before removing the worktree"
date: "2026-10-09"
time: "16:00"
type: manual
components: 
  - knowledge_system
  - worktree_manager
summary: "Before finalize-feature removes a worktree, it checks the PR really merged and then lists every routed learning written there, across every stage on the branch, that main does not hold: destination, reason, text, and whether it will be written again. If the PR has not merged, every staged learning is listed as unpublished. The removal still runs either way."
description: "Content commits cb0cdcbda, 60860f5db and 3551104d4. finalize-feature.js Step 7, before the worktree-agent removal, probes the PR state (step-7-pr-merged-probe), because Step 4's gh pr merge --auto can return unmerged. It then dispatches completion_routing_cli.py observe --all-stages (step-7-unpublished-learnings), with --commit-status ok when MERGED and not_run otherwise. not_run lists every staged write as branch_not_merged under a 'branch not merged' heading. The list is logged, prepended to the removal prompt and returned as unpublished_learnings. An unusable reply degrades to an empty list and the removal still runs. completion_routing.py gains the pure accumulate_branch_run / branch_run, so each stage keeps the previous stages' writes in the run record (branch_entries, branch_unwritten_records). observe without --all-stages still judges only the latest commit. To stay inside the file-size ratchet, finalize-feature.js gains readAgentJson (replacing 21 duplicated parse blocks) and haltRefs (replacing five repeated fields in 13 halt returns). INF-700a-5-i is marked done. One subsection added to docs/reference/knowledge-routing-step.md."
commits: 
  - cb0cdcbda
  - 60860f5db
  - 3551104d4
breaking: false
---

## Entry

`finalize-feature` is the only completion path that removes a worktree. A learning
written in that worktree but never carried into main used to disappear with it, unremarked.

- **Step 7 now announces it first.** It checks that the PR is really `MERGED`, since
  Step 4's `gh pr merge --auto` can return before the merge happens. It then runs the
  read-only `completion_routing_cli.py observe --all-stages` in the worktree.
  - Merged: each learning main does not hold is named.
  - Not merged: every staged learning is named, under "branch not merged — every routed
    learning here is unpublished".
  - Each entry carries its destination, reason, text, and whether it is still eligible.
    The list goes to the log, to the removal agent's prompt, and to `unpublished_learnings`.
- **Every stage counts.** An epic drive stages once per ticket on one branch. The run
  record now keeps every stage's writes, so the teardown covers them all. A ticket's own
  `observe` still reports only that ticket's commit.
- **It never blocks.** If a check cannot run, the list is shorter or empty and the
  worktree is removed as before. The run's status and step record are unchanged.
- **Smaller file.** In `finalize-feature.js`, `readAgentJson` replaces 21 copies of a
  parse-and-fallback block, and `haltRefs` replaces five repeated fields in 13 halt
  returns.
- **INF-700a-5-i** is marked done.
- **Docs:** new subsection "Announcement before worktree removal" in
  `docs/reference/knowledge-routing-step.md`.
