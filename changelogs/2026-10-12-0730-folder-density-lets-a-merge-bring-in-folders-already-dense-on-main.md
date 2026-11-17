---
title: "Folder-density hook no longer refuses a merge for folders that are already dense on the merged-in branch"
date: "2026-10-12"
time: "07:30"
type: manual
components: 
  - commit_guardian
summary: "check-folder-density now counts a folder as pre-existing when it is already over the limit in HEAD or in any MERGE_HEAD parent, so taking in main no longer needs a hook skip; a folder the merge itself pushes over the limit is still refused."
description: "Merging origin/main into a long-lived branch was refused for every folder that had grown past the 15-file limit on main, because the hook read its before-snapshot from HEAD only. The hook now takes the per-folder maximum over HEAD and every merge parent, octopus merges included. Ordinary commits behave exactly as before."
commits: []
---

## Entry

Ticket: TICKET-20261010-FolderDensityMergeCommit

Known issue: KI-CG-20261010-folder-density-refuses-merges-of-main
