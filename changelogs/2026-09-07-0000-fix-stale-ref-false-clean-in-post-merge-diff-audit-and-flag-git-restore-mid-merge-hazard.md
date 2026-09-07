---
title: "Fix stale-ref false clean in post-merge diff audit and flag git restore mid-merge hazard"
date: "2026-09-07"
time: "00:00"
type: manual
components: 
  - docs
  - claude-md
summary: "CLAUDE.md's post-merge diff audit reported a false clean because the origin/main ref it compared against was stale, not because the command form was wrong; the section now makes git fetch a mandatory precondition and warns against three-dot, which hides the defect pre-merge."
description: "The 'Post-origin/main-merge diff audit' section in CLAUDE.md recommends `git diff origin/main -- <file>` to catch merge hunks silently dropped by a 3-way auto-merge. An empirical scratch-repo test (branch diverges, main adds 42 lines, merge main in, run git restore mid-merge) confirmed the two-dot form is correct in BOTH the uncommitted and committed merge states and was never the defect, so the recommended command is unchanged. What the section previously lacked was a fetch precondition and any warning about the three-dot form; both are added here. Three-dot is the trap: before the merge is committed it compares against the OLD divergence point and hides exactly the dropped-hunk defect it should catch, and after the merge is committed origin/main becomes an ancestor of HEAD so three-dot is mathematically identical to two-dot and buys nothing. The section now states git fetch origin main as a mandatory precondition of the recipe, because the real cause of a false clean is a stale local origin/main remote-tracking ref: an unfetched ref lacks the same hunks the working tree lacks, so the diff agrees with itself. The section also documents a related but distinct hazard: git restore --staged --worktree <path> run mid-merge reads from HEAD, and mid-merge HEAD is the pre-merge commit, so it silently reverts origin/main's side of that path (git checkout --theirs/--ours is the correct mid-merge tool). Both defects contributed to a real incident on 2026-09-07 (fixed in 2d9d43cf3): git restore deleted 42 lines of merged card content, and the post-commit audit missed it because it ran against a stale origin/main ref, not because two-dot is unsound post-merge. The section names this as the third instance of a documented defence being a no-op in this file, alongside the feedback_categories.yaml wrong-path defect and the AC-store validator's bare-directory glob -- in this case the command was always right and the ref it pointed at was wrong."
---

## Entry
