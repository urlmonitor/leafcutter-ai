---
title: "Design and prototype symlink/shim layer for fixed-path tools"
status: todo
components:
  - build_pipeline
created: 2026-05-26
depends_on:
  - 01_adr_output_layout.md
priority: high
requires_diagram: true
requires_adr: false
agents:
  architect-review: needed
  python-coder: needed
  test-writer: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  documentation-expert: not_needed
  adr-author: not_needed
---

# 02: Design and Prototype Symlink/Shim Layer

## Goal
In order to move all `build.py` outputs under `leafcutter-project/` without
breaking Claude Code, pre-commit, or Gemini/Antigravity tooling, we need a
shim layer that places either symlinks or thin forwarding copies at the
canonical paths those tools expect.

## Context
Several tools read from hard-coded or conventionally-fixed paths:
- **Claude Code**: reads agents from `.claude/agents/`, skills from
  `.claude/skills/`, commands from `.claude/commands/`, hooks from
  `.claude/hooks/`. Whether it follows symlinks is an open question resolved
  by ticket 01.
- **pre-commit**: reads `.pre-commit-config.yaml` from the repo root. Cannot
  be relocated.
- **Gemini / Antigravity**: reads `.gemini/` and `.antigravity/` from repo
  root.

This ticket designs and prototypes the shim layer implementation that
`build.py` will use (after ticket 03 redirects phases to the new root).

Approach options (to be chosen based on ADR-001 outcome):
1. **Symlinks**: `leafcutter-project/agents -> .claude/agents/` (or vice versa).
   Lightweight; git-ignorable; does not work on Windows without Developer Mode.
2. **File copies with manifest**: `build.py` copies shim files to canonical
   paths and records them in the build manifest so they can be detected/cleaned.
3. **Hybrid**: physical copies for root-level files (`.pre-commit-config.yaml`,
   `.gemini/`, `.antigravity/`); symlinks for `.claude/` subtree.

This ticket produces:
- A `build_helpers.py` `install_shims()` function (or update to existing stub)
  that writes the appropriate shims after the main build phases run.
- Unit tests covering the shim installation logic.

## Architecture Plan

### Diagrams

- `data_flow` diagram at `leafcutter-ai/docs/architecture/c2-shim-layer.md`
  (parent: `leafcutter-ai/docs/architecture/c1-build-pipeline.md`) — shows how
  `build.py` writes to `leafcutter-project/` and then creates shims pointing
  back to canonical tool-expected paths.

## Acceptance Criteria

```gherkin
Given build.py runs with the new shim layer enabled
When a consumer project uses Claude Code after build
Then Claude Code loads agents from .claude/agents/ (whether via symlink or copy)
  and reports no missing-agent errors

Given build.py runs on a Windows machine without Developer Mode
When symlink creation fails
Then build.py falls back to file-copy shims and logs a warning
  "Symlinks unavailable; using file-copy shims"

Given build.py has run and created shims
When the developer runs git status
Then only leafcutter-project/ shows as untracked/modified (shim files at
  .claude/ are either gitignored or identical to last commit, not dirty)

Given install_shims() is called with dry_run=True
When examining the output
Then no files are written to disk and the shim plan is printed to stdout
```

## Sign-offs

- [ ] architect-review
- [ ] python-coder
- [ ] test-writer
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### architect-review
- [ ] Validate the chosen shim strategy (from ADR ticket 01) against the
  Windows symlink constraint and the git-cleanliness requirement
- [ ] Confirm the `data_flow` diagram plan covers the full handoff from
  build_phases → leafcutter-project/ → shim → canonical path

### python-coder
- [ ] Implement `install_shims(target_root, config, dry_run, force)` in
  `leafcutter-ai/scripts/build_helpers.py`
  - Reads the `shim_strategy` key from `skills_config.json`
    (`"symlink"` | `"copy"` | `"auto"`)
  - For `"auto"`: attempts symlinks; falls back to copy on PermissionError
  - Creates shims for: `.claude/agents/`, `.claude/skills/`,
    `.claude/commands/`, `.claude/hooks/`, `.pre-commit-config.yaml`,
    `.gemini/`, `.antigravity/`
  - Logs each shim created/skipped
- [ ] Add `shim_strategy` key to `leafcutter-ai/config/skills_config.default.json`
  with default `"auto"`
- [ ] Update `leafcutter-ai/config/skills_config.schema.json` to include
  `shim_strategy` enum

### test-writer
- [ ] `leafcutter-ai/tests/test_build_shims.py`:
  - `test_install_shims_symlink_mode` — verifies symlinks are created at
    canonical paths pointing into leafcutter-project/
  - `test_install_shims_copy_fallback` — patches os.symlink to raise
    PermissionError; verifies file copies are used instead
  - `test_install_shims_dry_run` — verifies no files written with dry_run=True
  - `test_shim_idempotent` — running install_shims twice produces no error and
    does not duplicate files

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? The shim layer is additive — existing files at canonical paths
  are only replaced/linked, not deleted. Reversing means removing the shims and
  restoring direct writes in build phases (ticket 03 inverse).
- Windows concern: symlinks on Windows require Developer Mode or admin. The
  `"auto"` fallback to copy shims mitigates this, but copy shims create two
  copies of each file which must be kept in sync by build.py.
