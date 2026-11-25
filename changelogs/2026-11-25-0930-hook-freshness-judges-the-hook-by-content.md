---
title: "The pre-commit probe judges hook freshness by the hook's content, not its age"
date: "2026-11-25"
time: "09:30"
type: manual
components:
  - build_orchestration
summary: "verify_precommit_active.py's check_hook_freshness failed whenever the installed pre-commit hook was older than the resolved pre-commit config. pre-commit's hook is a shim that reads its config at run time, so its bytes never depend on the config, and linked worktrees share one hook in the common git dir while each checks out a newer config. Every newly created worktree therefore reported hook_freshness and the commit step refused to commit, although a re-install produced a byte-identical hook (seen twice on 2026-11-24, in DIAGraph and in leafcutter's own worktree). Fresh now means the hook would behave like a freshly installed one: it carries pre-commit's generated-file header, its ARGS line is hook-impl for --hook-type=pre-commit, its --config= names a file that exists under the project root, and its INSTALL_PYTHON interpreter exists. A hand-written or foreign hook, a shim for another hook type, a dangling config and a dangling interpreter still fail."
description: "BO-1700h-4 (new L2 under BO-1700h). templates/scripts/commit_guardian/verify_precommit_active.py: check_hook_freshness(hook_path, config_path, project_root=None) is content-based; new helpers _parse_precommit_shim, _shim_config_arg and _project_root_for_config; run_checks passes project_root=cwd. New test file unit_tests/commit_guardian/test_verify_precommit_hook_freshness.py builds real pre-commit-shaped shims. A correct shim older or newer than the config passes, a .leafcutter/ config resolves against the project root, and the non-shim, other-hook-type, missing-config, missing-interpreter and missing-hook cases fail. The old mtime TestCheckHookFreshness class was removed from test_verify_precommit_active.py, which is over its size limit; its three mtime tests encoded the false positive."
commits:
breaking: false
---

## Entry

Every new git worktree used to be told its pre-commit hook was stale, because the shared hook is
older than the worktree's freshly checked-out config. That blocked commits until someone
re-installed a hook that was already correct. The probe now checks what the hook actually does:
it must be pre-commit's own hook for commits, and the config file and Python it points at must
both exist. Hooks that are really broken or foreign are still caught.
