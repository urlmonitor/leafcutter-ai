---
title: "Known-issues register corrections — commit-guardian"
date: "2026-09-29"
time: "12:20"
type: manual
components: 
  - commit_guardian
summary: "Restored a missing index row and corrected two stale claims in the commit-guardian known-issues register."
description: "Three corrections, each verified against the current tree rather than restated from the entries. (1) KI-CG-20260928-first-commit-leaves-the-deployed-config-drifted had a file but no row in commit-guardian.md — the row was cut to clear a merge conflict on PR #941 and never restored, leaving a filed issue reachable only by listing the directory. (2) KI-CG-20260909-gate-root-files asserted in two places that the status filter still matches A, M and R, concluding that modifying any of the five root files would be refused today; PR #857 narrowed it to A or R (check_root_files.py:55), so the urgent half is closed and only the allowlist half remains open. (3) The drift KI gained the template-restore trap: the deployed artifact is not a byte copy of its template because inject_config resolves the output_root token at deploy time, so the two differ by 150 lines and restoring from templates/ reintroduces 150 unresolved tokens, failing again with an identical message. Also records that the worktree scripts/commit_guardian path is a symlink into .leafcutter/scripts/commit_guardian, so the path the gate prints and the path the workaround writes are one file."
---

## Entry
