---
title: "Commit agent: the orphan-pytest cleanup only touches the current worktree's processes"
date: "2026-10-02"
time: "14:25"
type: manual
components: 
  - git_vcs_operations
  - supervisor_system
summary: A commit made in one session no longer kills tests that other sessions or worktrees are running on the same machine.
description: "The commit agent's Step 0 ran `pkill -f pytest` / `taskkill ... *pytest*` unconditionally, terminating every pytest process on the machine, including other Claude sessions' runs. building-epics justified it with 'workers in parallel tickets are isolated by worktree', which is false: worktrees isolate files, not processes. Step 0 now kills only processes whose working directory (POSIX, via /proc/<pid>/cwd or lsof) or command line (Windows, via Win32_Process) lies inside the current worktree root, and skips the kill when scoping is impossible on a platform. The building-epics exception is corrected to match. Built from TICKET-20261002-CommitAgentKillsOtherSessionsPytest."
tickets: 
  - TICKET-20261002-CommitAgentKillsOtherSessionsPytest
---

## Entry

### Changed

- `templates/agents/commit.md` — Step 0 kills only pytest workers belonging to the current worktree.
- `templates/skills/building-epics/SKILL.md` — the commit-phase kill exception now states the scoping.
