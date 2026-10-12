---
title: "Planned: the acceptance-criteria store is set aside from the folder-density check, visibly (GE-133)"
date: "2026-10-12"
time: "12:00"
type: manual
components: 
  - commit_guardian
  - ac_store
summary: "Acceptance criteria only, no code: they plan that check-folder-density stops refusing commits that grow an acceptance-criteria feature folder past 15 files, while still reporting such folders as set aside."
description: "Planned work only; no code changes. New AC records GE-133 (L0), GE-133a (L1), GE-133a-1 and GE-133a-2 (L2). Why: the AC store is flat by design (one folder per feature family, none nested) and most of its folders are already over the 15-file density limit, so the first time any family crosses 15 the check refuses it; PR #1127 needed SKIP=check-folder-density for exactly that. GE-133a-1: the set-aside location is a declared set_aside_locations list inside the folder_density configuration, shipped with one entry for docs/acceptance-criteria/ and its stated ground; matching is by whole path components, never by folder name or string prefix; an absent or malformed declaration means every folder is judged and the outcome says so, and an empty one sets nothing aside. GE-133a-2: set-aside folders are reported with their ground and counted apart from judged ones, a commit that touches only set-aside folders never prints 'all within limits', and docs/pre-commit-hooks.md gains a check-folder-density entry. A per-location size bound was considered and dropped by BrainCandy's decision. 8 planned tests."
commits: []
breaking: false
---

## Entry
