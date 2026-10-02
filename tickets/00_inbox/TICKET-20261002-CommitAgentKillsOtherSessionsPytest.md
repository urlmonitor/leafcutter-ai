---
title: "Commit agent: the Step 0 pytest kill terminates every session's tests, not just this worktree's"
status: todo
components:
  - git_vcs_operations
  - supervisor_system
created: 2026-10-02
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: prompt
risk_surface: internal
tags:
  - commit-agent
  - multi-session
  - safety
last_updated: 2026-10-02
agents:
  llm-expert: needed
  commit: needed
---

# Commit agent: the Step 0 pytest kill terminates every session's tests, not just this worktree's

## Actor / Goal
In order to run several Claude sessions on one machine safely, we need the commit agent's
orphan-worker cleanup to touch only processes that belong to its own worktree. Today a commit
in one session can kill a test run in another.

## Context
- `templates/agents/commit.md` Step 0 runs `pkill -f "pytest"` (POSIX) and
  `taskkill /F /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *pytest*"` (Windows)
  unconditionally before every commit. The reason given is that orphan workers can hold file
  locks that hang `git commit` on Windows.
- `templates/skills/building-epics/SKILL.md` (§5.5 exception) says the unconditional kill is safe
  because "workers in parallel tickets are isolated by worktree". **That premise is false.**
  Worktrees isolate files, not processes, and `pkill -f pytest` matches every pytest process on
  the machine, including other sessions' and other worktrees'.
- **Observed 2026-10-02:** a commit agent dispatched from one session ran the kill while the
  Decision Kernel session was running tests in another worktree.
- There is a user feedback memory on killing only idle processes
  (`feedback_kill_idle_processes_only.md`, cited in the skill).

## Scope
- Scope the kill to processes whose working directory, or the command-line path they run from,
  lies inside the current worktree:
  - POSIX: e.g. `/proc/<pid>/cwd`.
  - Windows: e.g. a PowerShell/CIM query on `CommandLine` containing the worktree path.
- If scoping is impossible on a platform, skip the kill and rely on the existing lock-failure
  retry, instead of killing machine-wide.
- Correct the false premise in `building-epics` §5.5 and keep the two documents consistent.

## Out of Scope
- Changing the idle-only rule of the pre-flight sweep.

## Comments
