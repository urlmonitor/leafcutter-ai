---
title: "Kernel: the run store resolves independently of the caller's current directory"
status: todo
components:
  - decision_kernel
created: 2026-10-02
depends_on: []
priority: medium
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
last_updated: 2026-10-02
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel: the run store resolves independently of the caller's current directory

## Actor / Goal
In order that a host can resume a run from wherever its shell happens to be, we need the kernel to find its run store the same way regardless of the current directory.

## Context
- **Live reproduction (2026-10-02):** `python -m kernel resume --run-id run-57d16125a4a94de0 …` with `PYTHONPATH` pointing at the runtime worktree failed with exit 4 `run_not_found` when the shell's current directory was another git worktree (`worktrees/atlas-findability`). The same command succeeded from the runtime worktree.
- `kernel/bootstrap.py` `resolve_run_root(config, root)` takes `root` from `repo_root()` ("this checkout"), which follows the current directory's git repository, not the kernel package's own location.

## Scope (no acceptance criteria by user decision)
- The default run root resolves from the kernel's own checkout (or an explicit config/env value), not from the caller's cwd. A run started from one directory can be resumed from any other.
- Keep `--repo-root` and config overrides working, and document the resolution order in the run-the-kernel how-to.
- Tests: start in directory A, resume from an unrelated git directory B: the run is found; an explicit override still wins.

## Comments
