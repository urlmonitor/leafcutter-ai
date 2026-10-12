---
title: "Build orchestration: a repository reference that names a file is answered from its folder"
date: "2026-10-02"
time: "17:00"
type: manual
components: 
  - build_orchestration
summary: "A single-ticket build now finds its repository when it is pointed at a ticket file, just as an epic build does when pointed at a folder."
description: "worktree_repo_facts.py ran git with the given path as cwd, so a file path raised NotADirectoryError and the subcommand answered null. base start, facts --reference and branch-standing --repo now resolve a file to its parent folder; directories, missing paths and the facts inspected path are unchanged. 1 commit (BO-4000g, amends BO-4000f); tests cover ticket .md anchors from a non-git cwd."
commits: 
  - 463a9523f8ec209ea0acc3ca85e43608f11f064f
---

## Entry
