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
  test-writer: signed_off
  python-coder: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
---

# Kernel: the run store resolves independently of the caller's current directory

## Actor / Goal
In order that a host can resume a run from wherever its shell happens to be, we need the kernel to find its run store the same way regardless of the current directory.

## Context
- **CORRECTION (2026-10-02, supersedes the diagnosis below):** `repo_root()` already derives the root from the kernel package's own location, not from cwd. The real root cause: `python -m kernel` and `python -c` put the current directory first on `sys.path`. When the shell sits in another checkout of this repository (e.g. `worktrees/atlas-findability`), that checkout's `kernel/` package shadows the one on PYTHONPATH; its run store is empty, so `resume` exits 4 `run_not_found`. Verified: `PYTHONPATH=<runtime> python -c "import kernel; print(kernel.__file__)"` printed the atlas-findability kernel; the same with `python -P` printed the runtime kernel. Fix: every printed or installed command uses `-P` (`PYTHONPATH=<repo> <python> -P -m kernel`). The `LEAFCUTTER_KERNEL_RUN_ROOT` override from 54ff236e stays but does not fix this failure.
- **SUPERSEDED diagnosis:** the original text follows.
- **Live reproduction (2026-10-02):** `python -m kernel resume --run-id run-57d16125a4a94de0 …` with `PYTHONPATH` pointing at the runtime worktree failed with exit 4 `run_not_found` when the shell's current directory was another git worktree (`worktrees/atlas-findability`). The same command succeeded from the runtime worktree.
- `kernel/bootstrap.py` `resolve_run_root(config, root)` takes `root` from `repo_root()` ("this checkout"), which follows the current directory's git repository, not the kernel package's own location.

## Scope (no acceptance criteria by user decision)
- The default run root resolves from the kernel's own checkout (or an explicit config/env value), not from the caller's cwd. A run started from one directory can be resumed from any other.
- Keep `--repo-root` and config overrides working, and document the resolution order in the run-the-kernel how-to.
- Corrected scope: render `-P` into the `/leafcutter` skill command (`kernel/adapters/claude_code/install.py`) and document it in the run-the-kernel how-to; the Codex skill runs from the kernel checkout and is unaffected; `publish_command.py` is out of scope (another branch).
- Test: `tests/kernel/adapters/test_safe_path_command.py` runs `python -P -m kernel gaps --json` from a dir holding a shadow `kernel/` package and asserts the real kernel ran.
- (Superseded) Tests: start in directory A, resume from an unrelated git directory B: the run is found; an explicit override still wins.

## Comments

### 2026-10-02 12:00 — test-writer (status: ok)
feedback-id: (submit-failed)
Tests: tests/kernel/adapters/test_run_root_cwd_independent.py. Introduces explicit env override LEAFCUTTER_KERNEL_RUN_ROOT (wins over config/default); default stays checkout-anchored. The default-from-other-cwd test passes already (repo_root is package-based); the rest are red.
red_baseline:
  - test_name: test_ac2_env_var_overrides_default_and_config
    file: tests/kernel/adapters/test_run_root_cwd_independent.py
    error: "AssertionError: run root != explicit env path"
  - test_name: test_ac3_env_var_resolves_same_from_any_cwd
    file: tests/kernel/adapters/test_run_root_cwd_independent.py
    error: "AssertionError: run root != explicit env path"
  - test_name: test_ac4_resolve_run_root_honours_env_var
    file: tests/kernel/adapters/test_run_root_cwd_independent.py
    error: "AssertionError: env override ignored by resolve_run_root"
  - test_name: test_ac5_cli_status_from_other_cwd_uses_env_run_root
    file: tests/kernel/adapters/test_run_root_cwd_independent.py
    error: "AssertionError: False is not true : run store must be created at the env run root"
completion_manifest:
  cross_layer_seam_answer:
    result: covered
    producing_side: kernel.bootstrap.build_environment / resolve_run_root
    consuming_side: python -m kernel CLI subprocess from an unrelated cwd
  reachability_entry_point_answer:
    result: resolved
    entry_point: "python -m kernel gaps (CLI via subprocess from unrelated cwd)"

### 2026-10-02 13:00 — python-coder (status: ok)
feedback-id: (submit-failed)
Added RUN_ROOT_ENV_VAR (LEAFCUTTER_KERNEL_RUN_ROOT) override in kernel/bootstrap.py resolve_run_root (env > config > checkout-relative), build_environment creates run_root; documented order in docs/how-to/run-the-decision-kernel.md.
red_baseline_results:
  - test_name: test_ac2_env_var_overrides_default_and_config
    result: green
  - test_name: test_ac3_env_var_resolves_same_from_any_cwd
    result: green
  - test_name: test_ac4_resolve_run_root_honours_env_var
    result: green
  - test_name: test_ac5_cli_status_from_other_cwd_uses_env_run_root
    result: green

### 2026-10-02 14:00 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
Reviewed kernel/bootstrap.py, docs/how-to/run-the-decision-kernel.md, tests/kernel/adapters/test_run_root_cwd_independent.py. No high-confidence findings. Medium: [M-1] a relative LEAFCUTTER_KERNEL_RUN_ROOT resolves against cwd (Path.resolve), which is cwd-dependent; document that the env value should be absolute or anchor it to the checkout. [M-2] build_environment now mkdirs run_root for every command, including read-only ones. Suppressed: 1 low nit (docs paragraph partly duplicates the next sentence). Escalation: not escalated (medium count 2).

### 2026-10-02 15:00 — commit (status: ok)
feedback-id: (submit-failed)
Auto-authorized commit gate: subject "fix(kernel): resolve run store independent of cwd"; staged files: kernel/bootstrap.py, docs/how-to/run-the-decision-kernel.md, tests/kernel/adapters/test_run_root_cwd_independent.py, ticket. Unrelated CRLF-only noise (docs/agents/cards/*, LEAFCUTTER_VERSION) left unstaged.

completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true

### 2026-10-02 16:00 — python-coder (status: ok)
feedback-id: fb_2026-10-02_9ebe017a
Corrected the diagnosis (cwd-first sys.path lets another checkout's kernel/ shadow PYTHONPATH). `command_line` in kernel/adapters/claude_code/install.py now renders `PYTHONPATH=<repo> <python> -P -m kernel`; how-to documents `-P`; new test tests/kernel/adapters/test_safe_path_command.py reproduces the shadowing via subprocess. Codex skill unaffected (runs from the kernel checkout); publish_command.py untouched.
