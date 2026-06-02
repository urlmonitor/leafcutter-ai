---
title: "Fix build script writing workflows to nested .claude/.claude/ instead of .leafcutter/workflows/"
status: todo
components:
  - build_pipeline
created: 2026-06-02
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/build_helpers.py
  - scripts/build_phases.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Fix build script writing workflows to nested .claude/.claude/ instead of .leafcutter/workflows/

## Actor / Goal

In order to keep the build pipeline consistent with the established shim consolidation pattern, we need to fix four hardcoded `.claude/workflows` output paths introduced in commit `a6ca06a` so that compiled workflow scripts land in `output_root/workflows/` and get shimmed to `.claude/workflows/` by the standard shim layer.

## Context

Commit `a6ca06a` wired `build_workflow_scripts` into the shim/manifest infrastructure but hardcoded `.claude/workflows` into output paths in two files. This breaks the consolidation pattern that every other artifact type follows: artifacts write to `output_root/<type>` (e.g. `.leafcutter/agents/`) and the shim layer creates the `.claude/<type>` symlink. The workflow phase bypasses this pattern and writes directly to `.claude/workflows/` — but when the shim layer then tries to create a symlink at `.claude/workflows/` pointing to `output_root/.claude/workflows/`, it would attempt to resolve `.leafcutter/.claude/workflows/` which does not exist, or worse, if `output_root` happens to be `.claude/` itself, it creates a nested `.claude/.claude/` directory.

This ticket belongs to the `build_pipeline` component (`scripts/build.py`, `scripts/build_phases.py`).

### Root cause (four hardcoded locations)

| # | File | Line | Wrong value | Correct value |
|---|------|------|-------------|---------------|
| 1 | `scripts/build_helpers.py` | ~334 | `(".claude/workflows", ".claude/workflows")` in `shim_map` | `(".claude/workflows", "workflows")` |
| 2 | `scripts/build_phases.py` | ~353 | `target_root / ".claude" / "workflows"` as `output_dir` | `target_root / "workflows"` |
| 3 | `scripts/build_helpers.py` | ~148 | `target_root / ".claude" / "workflows" / tpl.name` in `_compute_output_mappings()` | `target_root / "workflows" / tpl.name` |
| 4 | `scripts/build_phases.py` | ~262 | docstring says `<target_root>/.claude/workflows/` | docstring should say `<output_root>/workflows/` |

### Comparison: correct pattern (agents)

```python
# agents — correct pattern (target for workflows to mirror)
shim_map entry: (".claude/agents", "agents")        # canonical_rel, output_rel
output_dir    : output_root / "agents"              # in build_phases.py
output mapping: target_root / "agents" / tpl.name  # in build_helpers.py
```

### Verification steps after fix

After running `build-self.sh`:
1. `.leafcutter/workflows/` exists and contains the compiled `.js` files.
2. `.claude/workflows/` is a symlink pointing to `.leafcutter/workflows/`.
3. No `.claude/.claude/` directory is created (run `ls .claude/` and confirm no nested `.claude` entry).
4. `build-self.sh` exits 0 with no warnings about missing shims.

## Acceptance Criteria

```gherkin
Given a clean build environment with a valid skills_config.json and workflows enabled
When build-self.sh is run after the fix
Then .leafcutter/workflows/ contains the compiled workflow .js files
And .claude/workflows/ is a symlink to .leafcutter/workflows/
And no .claude/.claude/ directory exists

Given build-self.sh exits 0 after the fix
When `ls -la .claude/` is inspected
Then workflows is listed as a symlink (l---------) not a directory

Given the shim map in build_helpers.py install_shims()
When the entry for workflows is read
Then the tuple is (".claude/workflows", "workflows") matching the agents/skills/commands/hooks pattern

Given _compute_output_mappings() in build_helpers.py
When the workflow-js section is read
Then the output path resolves to target_root / "workflows" / tpl.name (not target_root / ".claude" / "workflows")
```

## Sign-offs

- [x] test-writer — 2026-06-02 14:00
- [x] python-coder — 2026-06-02 14:30
- [x] test-runner — 2026-06-02 14:30
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-02 14:00 — test-writer (status: ok)
feedback-id: fb_2026-06-02_794a0b08
completion_manifest:
  tests_written: true
  tests_are_red_before_fix: true
  coverage_includes_all_four_locations: true
Created `unit_tests/test_build_workflow_output_paths.py` with 4 failing tests (RED baseline confirmed): test_build_workflow_scripts_writes_to_output_root_workflows, test_install_shims_workflows_entry_maps_to_output_root_workflows, test_install_shims_does_not_use_nested_claude_path, and test_compute_output_mappings_workflow_js_uses_correct_output_key. All 4 tests fail against the current broken code and cover all four hardcoded locations described in the ticket.

## Implementation Tasks

### test-writer

- [x] Add or extend a test in `unit_tests/test_build_artifact_parity.py` (or a
  dedicated `test_build_workflow_scripts.py`) verifying:
  - `_compute_output_mappings()` places a sample `sample.js` under
    `<target_root>/workflows/sample.js` — not under `.claude/workflows/`.
  - `build_workflow_scripts()` (with workflows enabled and version check bypassed
    via `CLAUDE_CODE_VERSION` env var) writes the file to
    `<output_root>/workflows/` — not under `.claude/workflows/`.
  - The `shim_map` entry for workflows resolves to `output_root / "workflows"`,
    not `output_root / ".claude" / "workflows"`.

### python-coder

- [ ] `scripts/build_helpers.py` line ~334 — in `install_shims()` shim_map, change `(".claude/workflows", ".claude/workflows")` to `(".claude/workflows", "workflows")`
- [ ] `scripts/build_phases.py` line ~353 — in `build_workflow_scripts()`, change `output_dir = target_root / ".claude" / "workflows"` to `output_dir = target_root / "workflows"`
- [ ] `scripts/build_helpers.py` line ~148 — in `_compute_output_mappings()`, change `output = target_root / ".claude" / "workflows" / tpl.name` to `output = target_root / "workflows" / tpl.name`
- [ ] `scripts/build_phases.py` line ~262 — fix docstring from `<target_root>/.claude/workflows/` to `<output_root>/workflows/`
- [ ] Run `build-self.sh` and confirm the three verification checks listed in Context pass
- [ ] Run `git status` to confirm no `.claude/.claude/` directory appears as an untracked path

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? All changes are path corrections in two Python files. Reverting is a straight revert. The fix will clean up any existing `.claude/.claude/` artifact (that directory should be deleted before or after the fix to remove the confusing untracked directory).
- Breaking surface? If any consumer project has already run a build after commit `a6ca06a` and has a real `.claude/.claude/workflows/` directory, they will need to delete it and re-run build to get the correct symlink layout. No data loss risk.
