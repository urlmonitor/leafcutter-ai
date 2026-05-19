# scripts/worktree

Utility scripts for git worktree lifecycle management — specifically the
pre-removal sweep that ensures no orphaned background worker processes or
residual log files survive after an epic's close flow.

## Purpose

Provides `sweep_processes.py`, a cross-platform Python helper invoked by
the `close-worktree` workflow (Phase 3.5) and the `worktree-agent` remove
action before every `git worktree remove` call. Prevents the class of
failure where held-open file handles block OS-level directory deletion.

## Key Files

| File | Role |
|------|------|
| `sweep_processes.py` | Main module: `SweepResult`, `sweep()`, `sweep_log_files()`, `main()` CLI |
| `__init__.py` | Package init — re-exports `SweepResult`, `sweep`, `sweep_log_files` |

## CLI Usage

```bash
# Live sweep (kills processes, removes log files, prints JSON SweepResult)
python leafcutter/scripts/worktree/sweep_processes.py "<worktree-path>"

# Dry run (print what would be killed/removed, do nothing)
python leafcutter/scripts/worktree/sweep_processes.py "<worktree-path>" --dry-run

# Use a specific skills_config.json
python leafcutter/scripts/worktree/sweep_processes.py "<worktree-path>" --config .claude/skills_config.json
```

Exit 0 on clean sweep; exit 1 on any conflict or error.

## Critical Context

- The `protected_paths` check fires **before** any `kill()` call. If any
  process matches, the sweep aborts entirely without killing anything.
- `kill_residual_processes: false` in `skills_config.json` degrades gracefully
  to summary mode: running PIDs are reported in `conflict_pids` with no kill.
- Config is loaded via `../config_loader.py`; safe defaults apply when
  `skills_config.json` is absent (`kill=true`, `log_globs=["*.log"]`,
  `protected_paths=[]`).

## Maintenance

- Add new log glob patterns to `worktree_cleanup.log_globs` in
  `config/skills_config.default.json` — no code change needed.
- Add protected process substrings to `worktree_cleanup.protected_paths` in
  the adopter's `.claude/skills_config.json`.
- Tests live in `leafcutter/tests/test_sweep_processes.py`.
