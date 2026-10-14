---
title: "Finalize no longer reports a pull request held by the post-merge check as merged"
date: "2026-10-14"
time: "09:42"
type: manual
components: 
  - testing_quality
summary: "Before merging, /finalize-feature now reads the pull request's checks. When the only failure is Post-merge suite status, it stops, says the pull request is held from outside the branch, and keeps the worktree, where it used to record a merge that never happened."
description: "/finalize-feature used to ask for the merge and then record that the pull request was merged, whatever the result. A pull request kept open by the Post-merge suite status check, which goes red when main's own test suite is not green, was therefore reported as merged, its worktree was removed, and the run said it had succeeded. The workflow now reads the pull request's checks once before asking to merge. If that check is the only failure, the run stops with the outcome held externally: it quotes the check's message and link, says the pull request was not merged, keeps the worktree so a later run can finish, and points to the owner-only break-glass procedure without carrying it out. If other checks fail as well, the run stops as a failure of the branch and names only those other checks, listing the hold separately. When the check is passing or still running, or its reply cannot be read, the merge goes ahead as before. Only the exact check name counts. A separate problem remains: the merge step still records a merge without reading the merge result when nothing is holding the pull request."
---

## Entry
