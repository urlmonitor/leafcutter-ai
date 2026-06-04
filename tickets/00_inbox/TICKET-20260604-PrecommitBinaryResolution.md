---
title: "Fix _resolve_precommit_cmd() to validate known-path candidates before use"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/build_helpers.py
  - tests/test_install_hooks.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
ac_coverage: 0/5
---

# Fix _resolve_precommit_cmd() to validate known-path candidates before use

## Actor / Goal

As a developer running `python scripts/build.py --target-dir .` in an environment
where `pre-commit` is not on PATH, I need the "Hook install" step to emit a clear,
actionable warning — not an `[ERROR] pre-commit install failed:` — so that the
build completes successfully and I know exactly how to resolve the missing binary.

## Context

The final "Hook install" step in `build.py` calls `install_hooks()` in
`scripts/build_helpers.py`, which delegates to `_resolve_precommit_cmd()` for
binary detection. That function has a three-tier detection strategy:

1. `shutil.which("pre-commit")` — binary on PATH
2. `importlib.util.find_spec("pre_commit")` — installed Python package in current env
3. `_precommit_known_paths()` — probes hardcoded install locations
   (`~/.local/bin/pre-commit`, `<sys.executable dir>/pre-commit`, etc.)

The bug: tier 3 checks only `.is_file()` — it does not verify that the found
binary is actually runnable. On WSL2 or after a partial/broken `pip install
pre-commit`, a stale or non-executable binary can exist at
`~/.local/bin/pre-commit`. `_resolve_precommit_cmd()` returns it, then
`subprocess.run([..., "install"], check=True)` raises `subprocess.CalledProcessError`,
which is caught and surfaces as `[ERROR] pre-commit install failed:` (line 659 of
`build_helpers.py`).

The correct behaviour when no valid pre-commit binary exists is to return `None`
from `_resolve_precommit_cmd()`, causing `install_hooks()` to return
`"skipped (pre-commit not found)"` with a clear warning and pip install remedy
instructions — NOT an error that implies a configuration failure.

**Root cause location**: `scripts/build_helpers.py`, function `_resolve_precommit_cmd()`,
the loop over `_precommit_known_paths()`.

**Fix**: Before returning a known-path candidate, probe it with
`subprocess.run([str(candidate), "--version"], capture_output=True)` and skip it
if the return code is non-zero or if an `OSError` is raised (e.g. permission denied,
not-executable).

## AC References

| Ticket AC | Store AC | Component |
|-----------|----------|-----------|
| AC-1 | [BP-001](../../docs/acceptance-criteria/build_pipeline/BP-001.yaml) | build_pipeline |
| AC-2 | [BP-002](../../docs/acceptance-criteria/build_pipeline/BP-002.yaml) | build_pipeline |
| AC-3 | [BP-003](../../docs/acceptance-criteria/build_pipeline/BP-003.yaml) | build_pipeline |
| AC-4 | [BP-004](../../docs/acceptance-criteria/build_pipeline/BP-004.yaml) | build_pipeline |
| AC-5 | [BP-005](../../docs/acceptance-criteria/build_pipeline/BP-005.yaml) | build_pipeline |

## Acceptance Criteria

- [ ] AC-1: When `shutil.which` and `find_spec` both return `None` and
  `_precommit_known_paths()` yields a path whose file exists but whose
  `--version` probe exits non-zero (or raises `OSError`), `_resolve_precommit_cmd()`
  returns `None` — it does NOT return the broken path.

- [ ] AC-2: When `_resolve_precommit_cmd()` returns `None`, `install_hooks()` returns
  `"skipped (pre-commit not found)"`, emits exactly one `_warn(...)` line (not
  `_error(...)`), and makes no `subprocess.run` call for `pre-commit install`.

- [ ] AC-3: When `shutil.which("pre-commit")` returns a non-empty string,
  `_resolve_precommit_cmd()` returns `["pre-commit"]` immediately without running
  any `--version` probe on the result (tier 1 is trusted; only tier 3 candidates
  require the probe).

- [ ] AC-4: `tests/test_install_hooks.py` gains a new test class
  `TestResolvePrecommitCmdKnownPaths` containing
  `test_resolve_precommit_cmd_skips_nonexecutable_known_path` that patches
  `shutil.which` to `None`, `find_spec` to `None`, `_precommit_known_paths` to
  yield one path where `.is_file()` is `True` but the `--version` subprocess
  returns exit code 1, and asserts `_resolve_precommit_cmd()` returns `None`.

- [ ] AC-5: After the fix, `python -m pytest tests/test_install_hooks.py -v` exits
  0 with all 5 pre-existing tests plus the new test passing — no regressions.

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| AC-1 |      |                |           |
| AC-2 |      |                |           |
| AC-3 |      |                |           |
| AC-4 |      |                |           |
| AC-5 |      |                |           |

## Implementation Tasks

- [ ] In `scripts/build_helpers.py`, update the `_resolve_precommit_cmd()` function's
  known-paths loop. Replace the bare `.is_file()` check with an executability probe:

  ```python
  for candidate in _precommit_known_paths():
      if not candidate.is_file():
          continue
      try:
          probe = subprocess.run(
              [str(candidate), "--version"],
              capture_output=True,
              timeout=5,
          )
          if probe.returncode == 0:
              return [str(candidate)]
      except (OSError, subprocess.TimeoutExpired):
          continue
  return None
  ```

- [ ] Add a DECISION HISTORY entry in `scripts/build_helpers.py`'s trailing
  `# ====` block referencing this ticket.

- [ ] Add `TestResolvePrecommitCmdKnownPaths` to `tests/test_install_hooks.py`
  with the test described in AC-4. Use `patch.object(mod, "_precommit_known_paths")`
  to inject a fake path and `patch("subprocess.run", ...)` to simulate the
  non-zero `--version` probe exit code.

- [ ] Run `python -m pytest tests/test_install_hooks.py -v` and confirm all tests
  pass (AC-5).

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible — the change is additive within `_resolve_precommit_cmd()`.
  Reverting it restores the current (broken) `is_file()` check.
- Performance: The `--version` probe adds one `subprocess.run` call only in the
  case where tier-1 and tier-2 detection have already failed AND a known-path
  file exists. The timeout is capped at 5 seconds and the probe only runs at
  most once per build. Zero cost for the common happy path (pre-commit on PATH).
- Error handling: `OSError` and `subprocess.TimeoutExpired` are caught and silently
  skipped per the "continue" loop — consistent with the existing non-fatal philosophy
  of `_resolve_precommit_cmd()`.

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
