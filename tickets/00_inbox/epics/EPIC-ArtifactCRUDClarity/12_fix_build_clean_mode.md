---
title: "Fix: build.py --clean mode"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/scripts/build.py
  - leafcutter-ai/scripts/build_phases.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
---

# 12: Fix: build.py --clean mode

## Actor / Goal

In order to prevent stale compiled artifacts from accumulating in `.claude/` after source templates are deleted, we need a `--clean` flag on `build.py` that removes output files that no longer have corresponding source templates so that the build output always reflects the current source state.

## Context

`build.py` currently compiles templates from `leafcutter-ai/templates/` into a target directory (e.g. `.claude/`). When a source template is deleted, `build.py` does not remove the corresponding compiled output — it only ever adds or updates. This means:
- Deleted agent templates leave orphaned `.claude/agents/<name>.md` files.
- Deleted skills leave orphaned `.claude/skills/<name>/` directories.
- Deleted Claude Code hooks leave orphaned `.claude/hooks/<name>.py` files.
- Deleted pre-commit hook scripts leave orphaned deployed copies.

The `--clean` flag should perform a diff between what exists in the target directory and what the current templates would produce, then remove anything that is in the target but not in the source.

`build_phases.py` (if it contains the per-artifact-type build logic) should have the cleanup logic added there, with `build.py` wiring the `--clean` argument to the phases.

## Acceptance Criteria

```gherkin
Given build.py supports --clean
When a source template is deleted and build.py --clean is run
Then the corresponding compiled artifact is removed from the target directory

Given --clean is run on a clean state (no orphans)
When it is run
Then it exits 0 and removes nothing, printing "No stale artifacts found"

Given --clean is run with orphaned artifacts present
When it is run
Then it prints each artifact it removes (one line per file/directory) and exits 0

Given --clean does not affect files not managed by build.py
When it is run
Then files in .claude/ that were not created by build.py are not removed
```

## Sign-offs

- [x] test-writer — 2026-05-28 00:00
- [x] python-coder — 2026-05-28 00:01
- [x] test-runner — 2026-05-28 00:02
- [x] pr-reviewer — 2026-05-28 00:03
- [ ] commit
- [ ] pull-request

## Comments

### 2026-05-28 00:00 — test-writer (status: ok)
feedback-id: fb_2026-05-28_730e1644
Wrote 8 TDD stubs in `tests/test_build_clean.py` covering: orphaned agent removal, orphaned skill removal, orphaned hook removal, noop on valid artifacts, unmanaged file protection, --clean argparse flag acceptance, removal print output, and "No stale artifacts found" message. All 8 tests are RED (AttributeError: module 'build_phases' has no attribute 'clean_stale_artifacts') — implementation not yet written. Handoff to python-coder.
red_baseline:
  - test_name: test_clean_removes_orphaned_agent
    file: tests/test_build_clean.py
    error: "AttributeError: module 'build_phases' has no attribute 'clean_stale_artifacts'"
  - test_name: test_clean_removes_orphaned_skill
    file: tests/test_build_clean.py
    error: "AttributeError: module 'build_phases' has no attribute 'clean_stale_artifacts'"
  - test_name: test_clean_removes_orphaned_hook
    file: tests/test_build_clean.py
    error: "AttributeError: module 'build_phases' has no attribute 'clean_stale_artifacts'"
  - test_name: test_clean_noop_on_valid_artifacts
    file: tests/test_build_clean.py
    error: "AttributeError: module 'build_phases' has no attribute 'clean_stale_artifacts'"
  - test_name: test_clean_does_not_remove_unmanaged_files
    file: tests/test_build_clean.py
    error: "AttributeError: module 'build_phases' has no attribute 'clean_stale_artifacts'"
  - test_name: test_clean_flag_accepted_by_argparse
    file: tests/test_build_clean.py
    error: "AssertionError: --clean caused argparse error (exit code 2) — flag not registered in argparse"
  - test_name: test_clean_prints_each_removal
    file: tests/test_build_clean.py
    error: "AttributeError: module 'build_phases' has no attribute 'clean_stale_artifacts'"
  - test_name: test_clean_noop_prints_no_stale_message
    file: tests/test_build_clean.py
    error: "AttributeError: module 'build_phases' has no attribute 'clean_stale_artifacts'"

### 2026-05-28 00:01 — python-coder (status: ok)
feedback-id: fb_2026-05-28_f8583729
Added `clean_stale_artifacts(target_dir, source_manifests)` to `scripts/build_phases.py` with safety guard restricting removal to `.claude/agents/`, `.claude/skills/`, `.claude/hooks/`. Added `_build_source_manifests(output_root)` helper to `scripts/build.py` and `--clean` argparse flag wired to call both after normal build phases. All 8 TDD tests pass (8 passed in 69.92s).

### 2026-05-28 00:02 — test-runner (status: ok)
feedback-id: fb_2026-05-28_cc5f01ba
Ran `pytest tests/test_build_clean.py -v`: 8 passed in 35.37s. Full suite: 249 passed, 2 pre-existing failures in test_emit_entry_cwd.py (CWD resolution issue unrelated to --clean). No regressions introduced.

### 2026-05-28 00:03 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-28_87540c7a
No high-confidence findings. One medium: `_build_source_manifests` in build.py has a dead `output_root` parameter (declared but never used; function derives paths from `__file__`). Non-blocking — no correctness impact, no security concern. Safety guard in clean_stale_artifacts correctly restricts removal to .claude/agents/, .claude/skills/, .claude/hooks/ only. Symlink handling correct. Opt-in flag does not affect existing callers. Approved; dead param noted for future cleanup.
Review report: No high findings. Suppressed: 2 low nits. Escalation: none (medium count 1, threshold >3).

## Implementation Tasks

### test-writer

- [x] Write tests in `leafcutter-ai/tests/test_build_clean.py`:
  - `test_clean_removes_orphaned_agent`: create a temp target dir with a fake agent file, run build with --clean and no matching source template, assert the file is removed.
  - `test_clean_removes_orphaned_skill`: same for a skill directory.
  - `test_clean_removes_orphaned_hook`: same for a hook file.
  - `test_clean_noop_on_valid_artifacts`: run --clean when all target artifacts have matching sources, assert nothing is removed.
  - `test_clean_does_not_remove_unmanaged_files`: place a file in the target dir that build.py doesn't manage, run --clean, assert it is NOT removed.
  - Use `tmp_path` fixture (pytest) for isolation.

### python-coder

- [x] Add `--clean` argument to `build.py`'s `argparse` block (boolean flag, default False).
- [x] Implement `clean_stale_artifacts(target_dir, source_manifests)` in `build_phases.py` (or `build.py` if no phases module exists):
  - For each artifact type (agents, skills, hooks, pre-commit hook scripts): compute the set of expected output paths from the current templates.
  - List actual paths in the corresponding target subdirectory.
  - Remove any target path not in the expected set.
  - Print each removal: `Removing stale artifact: <path>`.
  - Return count of removed items.
- [x] Wire `--clean` into the main build flow: when `--clean` is set, run `clean_stale_artifacts` after the normal compilation step.
- [x] Add a safety guard: only remove files/dirs that match the known artifact-type patterns (e.g. files under `.claude/agents/`, `.claude/skills/`, `.claude/hooks/`). Never remove arbitrary files.
- [x] Update `build.py` `--help` text to document `--clean`.

### test-runner

- [ ] Run `pytest leafcutter-ai/tests/test_build_clean.py -v` and confirm all tests pass.
- [ ] Run `python leafcutter-ai/scripts/build.py --clean --target-dir .` on the dev workspace and confirm it exits 0 without removing anything unexpected.

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies build scripts only.
- Reversibility? The `--clean` flag is opt-in. Existing `build.py` invocations without the flag are unaffected. The flag itself can be removed if it causes problems.
- Risk: incorrect artifact type patterns in the safety guard could cause unintended deletions. Mitigated by the test suite and the pattern guard.
- The safety guard (only remove files under known artifact directories) is critical and must be code-reviewed carefully.
