---
title: "check-package-surface-declaration stops treating every merge as a fresh registration"
date: "2026-09-01"
time: "11:07"
type: manual
components: 
  - ac_store
  - precommit_hooks
summary: "Fixed a pre-commit hook that was refusing merges for package-surface entries their own parent branch had already registered, closed an octopus-merge gap and a phantom test the same review found, and corrected a known issue that had been filed twice under two different names."
description: "2 commits (c4ef9419d, 4f6c58b8c) on ac_store and precommit_hooks. check-package-surface-declaration computed a 'new' registry entry as present-in-index and absent-from-HEAD, which is correct for an ordinary commit but wrong for a merge, where HEAD names only the first parent — so every entry the second parent already carried read as newly registered, and any branch merging origin/main after check-ticket-signoff-parity landed on main (406375c88) was refused for an entry it never introduced. Hit while merging PR #661 and bypassed with an authorised SKIP, filed as KI-BP-20260901-0812. Fixed by authoring ACS-100i-8-ii: an entry now counts as added only when absent from every parent, verified against a real git merge --no-commit --no-ff fixture where MERGE_HEAD is genuinely present, with a negative control proving an entry present in neither parent is still refused and named.

A same-day review found two further problems. The merge probe used git rev-parse -q --verify MERGE_HEAD, which resolves only the first line of a multi-line MERGE_HEAD, so an octopus merge's third-and-later parents were never consulted and an entry genuinely carried by one of them was still wrongly refused — reproduced directly against a real three-way merge. Fixed by reading MERGE_HEAD off disk in full (one SHA per line, also correct for a linked worktree) rather than resolving it as a single revision, with two new octopus tests including the negative control so octopus support could not be 'achieved' by exempting 3+-parent merges entirely. Separately, test_editing_an_entry_during_a_merge_needs_no_declaration turned out to be byte-for-byte the pre-existing single-parent edit test — no merge anywhere — while its docstring and assertion both claimed to cover the merge path. All seven tests in the file were re-audited against the state they actually construct rather than assumed sound; the test now builds a real merge.

Also recorded: KI-BP-20260901-0812 is a partial duplicate of KI-CG-20260826-package-surface-refuses-merge-commits, filed six days earlier in commit-guardian.md with the same mechanism, the same fix direction, and two observed occurrences (PRs #601, #577) against this entry's one — and more complete, naming both the octopus caveat and the independent sibling defect where all six AC guardians filter on --diff-filter=AM and so are blind to renamed registry entries. Filed in the wrong register because the search went to build-pipeline.md, where the consequence showed, rather than commit-guardian.md, where the hook lives. The datetime-id convention adopted the same week does not prevent this: a unique id stops two entries colliding, not the same defect being written up twice in two files. The genuinely unique remainder — BP-1100g-5-i's undeclared registration — stays open and is corrected separately; the canonical commit-guardian.md entry now carries the AC, an occurrence count of 4, and a note of what this fix does not cover."
commits: 
  - c4ef9419d
  - 4f6c58b8c
breaking: false
---

## Entry
