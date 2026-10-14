---
title: "Stop the output-drift check from blocking commits over git-ignored folders and nested worktrees"
date: "2026-10-12"
time: "16:22"
type: manual
components: 
  - build_pipeline
summary: "The output-drift check no longer blocks every commit in a project just because it contains git-ignored cache folders or nested worktrees."
description: "fix(build-pipeline), 1 commit (73ecc50a7), AC BP-100k-3-vii. check-output-drift no longer reports git-ignored paths (e.g. .claude/.cache/) or nested git worktrees (.claude/worktrees/*) as blocking coverage GAPs. In a consumer repo (DIAGraph) the gate had exited 2 with 79,365 GAPs and 0 drifted files, which blocked every commit, including build-feature commit phase. The coverage census now prunes directories that hold a .git entry and git-ignored paths, using one `git ls-files --others --ignored --exclude-standard --directory` call; an ignored directory that holds a recorded manifest key is still walked. If git is unavailable it falls back to the unfiltered walk with a WARNING. Drift, missing and unreadable checking of recorded keys is unchanged. Consumers get the fix after bumping their leafcutter pin and rebuilding."
commits: 
  - 73ecc50a7
breaking: false
---

## Entry
