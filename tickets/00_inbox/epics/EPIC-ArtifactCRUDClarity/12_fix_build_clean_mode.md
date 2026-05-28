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
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
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

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### test-writer

- [ ] Write tests in `leafcutter-ai/tests/test_build_clean.py`:
  - `test_clean_removes_orphaned_agent`: create a temp target dir with a fake agent file, run build with --clean and no matching source template, assert the file is removed.
  - `test_clean_removes_orphaned_skill`: same for a skill directory.
  - `test_clean_removes_orphaned_hook`: same for a hook file.
  - `test_clean_noop_on_valid_artifacts`: run --clean when all target artifacts have matching sources, assert nothing is removed.
  - `test_clean_does_not_remove_unmanaged_files`: place a file in the target dir that build.py doesn't manage, run --clean, assert it is NOT removed.
  - Use `tmp_path` fixture (pytest) for isolation.

### python-coder

- [ ] Add `--clean` argument to `build.py`'s `argparse` block (boolean flag, default False).
- [ ] Implement `clean_stale_artifacts(target_dir, source_manifests)` in `build_phases.py` (or `build.py` if no phases module exists):
  - For each artifact type (agents, skills, hooks, pre-commit hook scripts): compute the set of expected output paths from the current templates.
  - List actual paths in the corresponding target subdirectory.
  - Remove any target path not in the expected set.
  - Print each removal: `Removing stale artifact: <path>`.
  - Return count of removed items.
- [ ] Wire `--clean` into the main build flow: when `--clean` is set, run `clean_stale_artifacts` after the normal compilation step.
- [ ] Add a safety guard: only remove files/dirs that match the known artifact-type patterns (e.g. files under `.claude/agents/`, `.claude/skills/`, `.claude/hooks/`). Never remove arbitrary files.
- [ ] Update `build.py` `--help` text to document `--clean`.

### test-runner

- [ ] Run `pytest leafcutter-ai/tests/test_build_clean.py -v` and confirm all tests pass.
- [ ] Run `python leafcutter-ai/scripts/build.py --clean --target-dir .` on the dev workspace and confirm it exits 0 without removing anything unexpected.

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies build scripts only.
- Reversibility? The `--clean` flag is opt-in. Existing `build.py` invocations without the flag are unaffected. The flag itself can be removed if it causes problems.
- Risk: incorrect artifact type patterns in the safety guard could cause unintended deletions. Mitigated by the test suite and the pattern guard.
- The safety guard (only remove files under known artifact directories) is critical and must be code-reviewed carefully.
