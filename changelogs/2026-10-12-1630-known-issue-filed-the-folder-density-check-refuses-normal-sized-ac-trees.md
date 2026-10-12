---
title: "Known issue filed: the folder-density check refuses normal-sized acceptance-criteria trees"
date: "2026-10-12"
time: "16:30"
type: manual
components: 
  - commit_guardian
summary: "The commit-guardian known-issues register now records that check-folder-density's 15-file cap conflicts with how the acceptance-criteria store keeps each tree in one folder, and marks the earlier folder-density issue about merge commits as resolved."
description: "check-folder-density refuses any commit that pushes a folder past 15 non-markdown files, and it has no exemption for docs/acceptance-criteria/. The store keeps every L0 tree flat in one folder (BO-4300 holds 68 ACs, BO-4400 holds 49), so a business-analyst stage commit of a normal-sized tree is refused; the BO-4400 commit needed a user-authorized skip. The new entry KI-CG-20261012-folder-density-conflicts-with-flat-ac-store records the facts and two possible fixes without implementing either. KI-CG-20261010-folder-density-refuses-merges-of-main moves to resolved, since its fix landed in PR #1143, and three entries that linked to its old path now point to the new one. A duplicate resolved row for KI-CG-20260908-ratchet-reads-pre-merge-head is removed."
commits: [bed9f006f, 18f862d6c]
breaking: false
---

## Entry
