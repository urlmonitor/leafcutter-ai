---
title: "Fix hooks deployment pipeline: add build_hooks phase and investigate /finalize-feature discovery"
status: done
components:
  - build_pipeline
created: 2026-06-01
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/build_phases.py
  - scripts/build.py
  - scripts/build_claude_settings.py
  - unit_tests/test_build_hooks.py
agents:
  architect-review: needed
  python-coder: needed
  test-writer: needed
  test-runner: not_needed
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  sql-coder: not_needed
  sql-query: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
  frontend-coder: not_needed
  status-checker: not_needed
user_facing_surface: null
roadmap_phase: phase_1
advances_current_outcome: true
---

# Fix hooks deployment pipeline: add build_hooks phase and investigate /finalize-feature discovery

## Actor / Goal

In order to make leafcutter-managed hooks reliably available to Claude Code (and
Gemini) in consumer projects, we need a `build_hooks` phase in `build_phases.py`
and a corresponding wire-up in `build.py` so that `.leafcutter/hooks/` is
populated during every build run — enabling the existing `install_shims` step to
create the `.claude/hooks/` symlink (or copy) that Claude Code requires.

## Context

The build system currently deploys agents (`build_agents`), skills (`build_skills`),
and workflows (`build_workflows`) via dedicated phase functions. Each of these writes
compiled output into the `output_root` (`.leafcutter/` by default), then
`install_shims` in `build_helpers.py` creates the canonical symlinks (or file copies
on Windows) at `.claude/agents`, `.claude/skills`, `.claude/commands`, `.claude/hooks`.

The shim map in `install_shims` already includes:

```python
(".claude/hooks", "hooks"),
(".gemini", "gemini"),
```

However, `install_shims` checks `if not source_path.exists(): continue` — if
`.leafcutter/hooks/` does not exist, the `.claude/hooks` shim is silently skipped.
The missing piece is the **build phase** that copies `templates/hooks/*.py` into
`.leafcutter/hooks/`. Without it:

1. `.leafcutter/hooks/` is never created.
2. `install_shims` skips the `.claude/hooks` entry.
3. Claude Code's pre-tool-use hook walker finds no hooks directory.
4. Every tool call may fail or degrade due to the missing hook walker path.

The `_build_source_manifests` function and `clean_stale_artifacts` already treat
`hooks` as a managed artifact type (they reference `"hooks": "hooks"` in
`_MANAGED_ARTIFACT_DIRS`), confirming the intent was always there — only the
build phase is missing.

**Problem 2 — `/finalize-feature` discovery:** A leafcutter-consuming agent
reported it could not find `/finalize-feature`. This command lives in
`templates/workflows/finalize-feature.md` and is deployed by `build_workflows`
into `.leafcutter/commands/finalize-feature.md`, then shimmed to
`.claude/commands/finalize-feature.md`. The discovery failure may be a cascade
from the hooks failure (hook walker errors prevent normal Claude Code startup
context), a missing shim, or a separate deployment gap. This ticket includes
investigation as an explicit task.

**Pattern to follow**: `build_agents` (lines 181–256 of `build_phases.py`) is the
authoritative reference pattern for `build_hooks`. It uses `TEMPLATES_DIR /
"agents"` as source, iterates `.glob("*.md")`, compiles each file, then writes to
`output_root / "agents"` via `_write(output_path, compiled, dry_run, force)`.
`build_hooks` should mirror this pattern using `TEMPLATES_DIR / "hooks"` as source
and `output_root / "hooks"` as the destination, copying hook scripts verbatim
(no template compilation — hooks are plain Python).

**Merge, not replace**: The shim strategy (`"copy"` on Windows, `"symlink"`
elsewhere) means that the hooks directory is fully replaced each build in copy mode.
Users who have project-specific hooks in `.claude/hooks/` would lose them. This
ticket must NOT replace project-specific hooks. The correct approach is to use
`shutil.copytree(src, dst, dirs_exist_ok=True)` (already used for `"copy"` shims)
which merges without deleting existing files. For symlink mode this is already
safe (the symlink resolves into `.leafcutter/hooks/` leaving any project-side hooks
in `.claude/hooks/` intact only if they are physically elsewhere — but a symlink
*replaces* the directory). Document this trade-off in the implementation and in
code comments. Consider whether the build should switch from a full directory shim
to a per-file copy for hooks to avoid clobbering project-local hooks.

## Acceptance Criteria

```gherkin
Given a consumer project has run python leafcutter-ai/scripts/build.py --target-dir .
When the build completes without --no-shims
Then .leafcutter/hooks/ exists and contains all *.py files from templates/hooks/
 And .claude/hooks/ exists (as a symlink or directory) pointing to .leafcutter/hooks/
 And .gemini/hooks/ exists when the antigravity platform is active in skills_config.json

Given a consumer project already has a project-specific hook at .claude/hooks/my_custom_hook.py
When the build runs
Then my_custom_hook.py is still present after the build completes

Given a consumer project has run build.py once
When build.py runs again (re-run / overwrite mode)
Then no hook file in .leafcutter/hooks/ is re-written if content is unchanged
 And the build summary reports up-to-date count for unchanged hooks

Given the build is run with --dry-run
When the Hooks phase executes
Then the phase prints all hook filenames it would write but writes nothing

Given a ticket for the /finalize-feature discovery issue is investigated
When the investigation is complete
Then either a root cause is identified and fixed
  Or a follow-up ticket is created documenting the exact failure mode
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

- [ ] Confirm the per-file copy approach vs. full-directory shim for hooks —
  document the decision in a code comment. The key question: should
  `install_shims` be changed to do per-file copy for hooks only (to allow
  project-local hooks to coexist), or should the current full-directory shim
  be preserved with a documented caveat?
- [ ] Verify the antigravity (Gemini) deployment path: hooks should also land
  in `.leafcutter/gemini/hooks/` when the `antigravity` platform is active,
  mirroring how `build_agents` writes to both `"agents"` and `"gemini/agents"`.

### python-coder

- [ ] In `scripts/build_phases.py`: add a `build_hooks` function following the
  pattern of `build_agents` (lines 181–256). Use `TEMPLATES_DIR / "hooks"` as
  the source directory. For each `.py` file found, copy it verbatim (no
  template compilation) to:
  - `output_root / "hooks" / <filename>` for the Claude platform
  - `output_root / "gemini" / "hooks" / <filename>` for the antigravity platform
  (when active in `config["platforms"]`).
  Use `_write` (or `shutil.copy2`) with the existing compare-before-write guard
  to avoid mtime churn on unchanged files.
- [ ] In `scripts/build.py`: add `build_hooks` to the `artifact_phases` list in
  `_run_phases` (after `build_workflows`, before `build_precommit_config` or at
  a logical position following the existing ordering). Import `build_hooks` in
  the import block at the top of `build.py`.
- [ ] Export `build_hooks` from `build_phases.py`'s public surface (add to
  module docstring's list of exported functions).
- [ ] Investigate the `/finalize-feature` discovery failure:
  - Confirm that `build_workflows` is writing `finalize-feature.md` to
    `.leafcutter/commands/`.
  - Confirm that `install_shims` is creating `.claude/commands` -> `.leafcutter/commands`.
  - If the shim exists but the command is not discoverable, document the exact
    error the consuming agent received and open a follow-up ticket.
  - If the shim is missing due to a build step ordering issue, fix it in this ticket.
- [ ] Run `python scripts/build.py --target-dir ..` (self-build) and confirm:
  - `.leafcutter/hooks/` is populated with all `templates/hooks/*.py` files.
  - `.claude/hooks` symlink (or directory) now resolves to the populated dir.

### test-writer

- [ ] Add a unit test in `unit_tests/` (matching the existing test file naming
  conventions) that calls `build_hooks(tmp_path, {}, dry_run=False, force=True)`
  and asserts:
  - Each `.py` file from `templates/hooks/` appears in
    `tmp_path / "hooks" / <filename>`.
  - File contents match the source.
- [ ] Add a dry-run test: `build_hooks(tmp_path, {}, dry_run=True, force=True)` —
  asserts no files are written and the function returns the correct would-be count.
- [ ] Add a compare-before-write test: call `build_hooks` twice; assert the
  second call reports 0 written and increments the up-to-date count.

## Out of Scope

- Changing the content of any hook script in `templates/hooks/` — hook logic
  changes are separate tickets.
- Introducing a new hook (use the `/create-hook` workflow for that).
- Modifying `install_shims` to support per-file merging (may be a follow-up if
  the architect-review step recommends it and the full-directory shim approach
  is deemed insufficient).
- Changing `settings.json` to point to `.leafcutter/hooks/` — the shim approach
  is the correct fix; `settings.json` correctly references `.claude/hooks/`.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible. `build_hooks` is an additive phase. If it
  causes issues, removing it from `artifact_phases` restores the prior behavior.
  No schema or data migrations involved.
- Platform impact? On Windows, `install_shims` falls back to `shutil.copytree`
  with `dirs_exist_ok=True` — this merges rather than replaces, so existing
  project-local hooks are preserved on Windows. On Linux/macOS, the symlink
  replaces any prior `.claude/hooks` symlink, which is the expected behavior
  (`.leafcutter/hooks` becomes the authoritative source).
