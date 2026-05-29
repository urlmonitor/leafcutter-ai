---
title: "Auto-run pre-commit install after build.py generates .pre-commit-config.yaml"
status: todo
components:
  - build_pipeline
created: 2026-05-30
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/build_helpers.py
  - scripts/build.py
  - tests/test_build_shims.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
user_facing_surface: null
---

# Auto-run pre-commit install after build.py generates .pre-commit-config.yaml

## Actor / Goal

In order to close the "last mile" gap between generating the pre-commit hook config
and actually activating it, we need `build.py` to run `pre-commit install`
automatically after writing `.pre-commit-config.yaml` so that a fresh clone or
rebuild never leaves hooks silently inactive.

## Context

`build.py` already generates `.pre-commit-config.yaml` from `commit_guardian.json`
(38 hooks defined via `build_precommit.py`) and installs canonical path shims via
`install_shims()` in `build_helpers.py`. However, it never runs `pre-commit install`,
meaning the generated config exists on disk but `.git/hooks/pre-commit` is never
wired to it. Developers must remember to run `pre-commit install` manually after
every fresh clone or build.

This gap was discovered after the May 27 `.leafcutter/` consolidation and gitignore
hardening: the dev repo lost all git pre-commit hooks because nobody re-ran
`pre-commit install` after the build. Commits were going through without any
validation.

A secondary issue: if `core.hooksPath` is set to the default `.git/hooks/` path
(redundant), `pre-commit install` refuses to run because pre-commit considers this
a misconfiguration. The build step must detect this condition and unset the key
before proceeding. If `core.hooksPath` points to a non-default custom path, the
build step must warn but not override the user's choice.

A third issue: `build.py --target-dir .` writes `.leafcutter/` output to the
target directory (the workspace parent), but the git repo root may be a
subdirectory (e.g. `leafcutter-ai/`). The `.pre-commit-config.yaml` references
`.leafcutter/scripts/commit_guardian/...` paths relative to the git root, but
`.leafcutter/` lives one level up. `install_hooks()` must detect the actual git
root (via `git rev-parse --show-toplevel`) and ensure `.leafcutter/` is reachable
from it — either by symlinking or by adjusting the shim target. Without this,
`pre-commit install` succeeds but every hook fails at runtime with "No such file
or directory".

The fix lives in `build_helpers.py` (new `install_hooks()` function called from
`build.py` main, after shim installation). It must be idempotent — re-running
`build.py` multiple times must not break an already-installed hook.

## Acceptance Criteria

```gherkin
Given a project with a freshly generated .pre-commit-config.yaml and no prior pre-commit install
When build.py completes (without --no-shims)
Then pre-commit install has been run
  AND .git/hooks/pre-commit exists and is executable
  AND the build output log contains a line confirming hook installation

Given build.py is run a second time on the same project
When install_hooks() executes again
Then the outcome is identical (pre-commit install is idempotent)
  AND no error is raised

Given core.hooksPath is set to the default ".git/hooks" value
When install_hooks() detects this condition
Then it unsets core.hooksPath via git config --unset core.hooksPath
  AND proceeds to run pre-commit install successfully
  AND the build log reports that the redundant hooksPath was cleared

Given core.hooksPath is set to a non-default custom path (e.g. ".husky")
When install_hooks() detects this condition
Then it does NOT override core.hooksPath
  AND it emits a warning: "core.hooksPath is set to '<value>' (non-default); skipping pre-commit install"
  AND the build does not fail

Given --dry-run is passed to build.py
When install_hooks() is called
Then it prints "[DRY-RUN] would run pre-commit install" and does nothing

Given pre-commit is not installed in the current environment
When install_hooks() attempts to run pre-commit install
Then it prints a warning "pre-commit not found; skipping hook install"
  AND the build exits 0 (non-fatal)

Given the target-dir is a workspace parent and .git/ lives in a subdirectory
When install_hooks() detects that git rev-parse --show-toplevel differs from target_root
Then it creates a .leafcutter symlink inside the git root pointing to target_root/.leafcutter/
  AND .pre-commit-config.yaml is readable from the git root
  AND pre-commit hooks can resolve .leafcutter/scripts/... paths at runtime
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder

- [ ] Add `install_hooks(target_root: Path, dry_run: bool) -> str` to `build_helpers.py`:
  - Check whether `pre-commit` is on PATH via `shutil.which("pre-commit")`; if absent,
    print a warning and return `"skipped (pre-commit not found)"`.
  - Read `core.hooksPath` via `subprocess.run(["git", "-C", str(target_root), "config", "--get", "core.hooksPath"], ...)`;
    if the key is absent, `returncode` will be 1 — treat as unset (proceed normally).
  - If `core.hooksPath` is set to `".git/hooks"` (case-insensitive match): run
    `git -C <target_root> config --unset core.hooksPath` and log
    `"  hooks: cleared redundant core.hooksPath (.git/hooks)"`.
  - If `core.hooksPath` is set to any other non-empty value: print
    `"  [WARNING] core.hooksPath is set to '<value>' (non-default); skipping pre-commit install"` and return `"skipped (custom hooksPath)"`.
  - If `dry_run` is True: print `"  [DRY-RUN] would run pre-commit install"` and return `"dry-run"`.
  - Run `subprocess.run(["pre-commit", "install"], cwd=target_root, check=True)`.
  - On `subprocess.CalledProcessError`: print the stderr and return `"failed"` (non-fatal — do not raise).
  - On success: print `"  hooks: pre-commit install OK"` and return `"installed"`.

- [ ] Import `install_hooks` in `build.py` alongside the existing `install_shims` import.

- [ ] In `build.py` `main()`, after the `if not args.no_shims: _install_shims(...)` block,
  add:
  ```python
  print("\nHook install:")
  install_hooks(target_root, dry_run=args.dry_run)
  ```
  Use the same `args.no_shims` guard so `--no-shims` skips both shim wiring and
  hook installation.

- [ ] Update the `DECISION HISTORY` block at the bottom of `build_helpers.py` with a
  dated entry for this change.

### test-writer

- [ ] Add tests to `tests/test_build_shims.py` (or a new `tests/test_install_hooks.py`):

  - `test_install_hooks_no_precommit_binary`: patch `shutil.which` to return `None`;
    assert `install_hooks()` returns `"skipped (pre-commit not found)"` and does not
    call `subprocess.run`.

  - `test_install_hooks_dry_run`: call `install_hooks(..., dry_run=True)`;
    assert return value is `"dry-run"` and no subprocess was invoked.

  - `test_install_hooks_default_hookspath_is_unset`: patch `subprocess.run` so
    `git config --get core.hooksPath` returns `".git/hooks"` and the subsequent
    `git config --unset` and `pre-commit install` calls succeed; assert return is
    `"installed"` and the unset command was called.

  - `test_install_hooks_custom_hookspath_is_skipped`: patch so `git config --get
    core.hooksPath` returns `".husky"`; assert return is
    `"skipped (custom hooksPath)"` and `pre-commit install` was NOT called.

  - `test_install_hooks_hookspath_absent_proceeds`: patch so `git config --get
    core.hooksPath` returns a non-zero exit code (key absent); assert
    `pre-commit install` is called and return is `"installed"`.

  - `test_install_hooks_precommit_failure_is_nonfatal`: patch so `pre-commit install`
    raises `subprocess.CalledProcessError`; assert return is `"failed"` and no
    exception propagates.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible. The only side effect is running `pre-commit install`
  in the target project root; this can be undone with `pre-commit uninstall`. The
  `core.hooksPath` unset only fires when the value is the redundant default; custom
  paths are never touched.
- Shared contract: `install_hooks` is a new exported function in `build_helpers.py`.
  It does not modify any existing function signatures. The `main()` change in `build.py`
  is additive (one new print block). No downstream callers are affected.
- `--no-shims` semantics: the guard reuses `args.no_shims` to skip hook installation,
  maintaining the principle that `--no-shims` opts out of all post-build wiring steps.
  This is an extension of existing intent, not a new flag.
- Pre-commit not installed: treated as non-fatal to avoid breaking CI environments
  where pre-commit may not be available at build time (e.g. Docker images that only
  need the config file, not the hook runner).
