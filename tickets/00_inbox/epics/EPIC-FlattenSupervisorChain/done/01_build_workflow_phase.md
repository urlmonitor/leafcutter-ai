---
title: "Add build_workflow_scripts() phase to build.py with Claude Code version detection"
status: done
components:
  - build_pipeline
created: 2026-06-01
depends_on: []
priority: high
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/build.py
  - scripts/build_phases.py
  - templates/workflows-js/
  - scripts/commit_guardian/commit_guardian.json
  - skills_config.json
agents:
  architect-review: signed_off
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
user_facing_surface: null
---

# 01: Add build_workflow_scripts() phase to build.py with Claude Code version detection

## Actor / Goal

In order to install Claude Code Workflow JS scripts into consumer projects during
a build run, we need a new `build_workflow_scripts()` phase in `build.py` that
copies `.js` files from `templates/workflows-js/` to `.claude/workflows/` in the
target project, with version detection that blocks or warns on Claude Code < 2.1.154.

## Context

Claude Code Workflows require version >= 2.1.154. The `templates/workflows-js/`
directory will contain the workflow JS scripts authored in tickets 02–04. This
ticket creates the build infrastructure so those scripts are deployed correctly.

The build phase is gated on **two** conditions:

1. **Opt-in flag**: `skills_config.json → workflows.enabled` must be `true`.
   Default is `false` — workflows are experimental and must be explicitly opted
   into. If the key is absent or `false`, the phase skips silently (no warning,
   since this is the expected default state).

2. **Version check**: if the detected Claude Code version is below 2.1.154, the
   phase emits a loud warning and skips file copying (it does NOT hard-fail the
   build, so legacy installs continue working via the agent path). When the
   Claude Code version is unknown or undetectable, the phase emits a warning and
   continues (fail-open, since many CI environments do not have Claude Code
   installed).

Both conditions must pass for workflow scripts to be installed.

### Version detection strategy

Claude Code exposes its version via the `CLAUDE_CODE_VERSION` environment variable
(set automatically by the CLI). If absent, try `claude --version` via subprocess.
If both fail, emit a warning and skip the version gate.

### Phase ordering

The new phase should run after `build_agents()` and before `build_hooks()` so that
workflow scripts are in place before any hook that might reference them.

### Dual-path guarantee

The legacy supervisor agent templates (`epic-supervisor.md`,
`ticket-supervisor.md`) are still compiled by the existing `build_agents()` phase.
This ticket does NOT remove them. Consumers on older Claude Code versions continue
to receive agent files; the workflow scripts are additional outputs layered on top.

### Architectural context (from docs/vision.md)

leafcutter's build system is config-driven and phase-based. `build.py` orchestrates
phases declared in `build_phases.py`. The `build_pipeline` component owns both files.
The compare-before-write guard must apply to the new phase to maintain build
idempotency.

## Acceptance Criteria

```gherkin
Given templates/workflows-js/ contains at least one .js file
  And skills_config.json has workflows.enabled = true
  And the target project has Claude Code >= 2.1.154 (CLAUDE_CODE_VERSION env set)
When python scripts/build.py --target-dir <target>
Then .claude/workflows/<filename>.js exists in the target
 And the build output includes "Workflow scripts: N installed"

Given skills_config.json has workflows.enabled = false (or key absent)
When python scripts/build.py --target-dir <target>
Then .claude/workflows/ is NOT populated with .js files
 And the build output includes "Workflow scripts: skipped (not enabled in skills_config.json)"
 And the build exits 0

Given skills_config.json has workflows.enabled = true
  And CLAUDE_CODE_VERSION is set to "2.0.0" (below minimum)
When python scripts/build.py --target-dir <target>
Then the build output includes a warning containing "Claude Code >= 2.1.154 required"
 And .claude/workflows/ is NOT populated with .js files
 And the build exits 0 (warning only, not a hard failure)

Given skills_config.json has workflows.enabled = true
  And CLAUDE_CODE_VERSION is absent and claude --version fails
When python scripts/build.py --target-dir <target>
Then the build output includes a warning about unknown Claude Code version
 And .claude/workflows/ IS populated (fail-open)

Given build.py is run twice with no changes to workflow source files
When python scripts/build.py --target-dir <target> is run a second time
Then git diff shows no changes (compare-before-write applied to .js files)
```

## Sign-offs

- [x] architect-review — 2026-06-01 10:00
- [x] test-writer — 2026-06-01 10:10
- [x] python-coder — 2026-06-01 10:30
- [x] test-runner — 2026-06-01 10:40
- [x] pr-reviewer — 2026-06-01 10:50
- [x] commit — 2026-06-01 10:55
- [x] pull-request — 2026-06-01 11:00

## Comments

### 2026-06-01 10:00 — architect-review (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true
Classification: SMALL. Blast-radius analysis: 3 files touched (scripts/build_phases.py, scripts/build.py, templates/workflows-js/.gitkeep), all within the single `build_pipeline` component. No always-large triggers fire (no Alembic migration, no hypertable change, no public API change, no ADR contract change). Phase insertion point confirmed: after `build_agents` and before `build_hooks` in `_run_phases()`. Dual-gate design confirmed: opt-in flag (`skills_config.json → workflows.enabled`, default false) as first gate, version check as second gate. Version-detection fallback chain (env var → subprocess with 2s timeout → warn+continue fail-open) is acceptable. Compare-before-write must apply to .js files (idempotency requirement confirmed). No ADR required. No diagram required.

### 2026-06-01 10:10 — test-writer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  test_workflow_scripts_skipped_when_not_enabled: true
  test_workflow_scripts_installed_when_enabled_and_version_ok: true
  test_workflow_scripts_skipped_when_version_below_minimum: true
  test_workflow_scripts_installed_when_version_unknown: true
  test_build_workflow_phase_idempotent: true
Created `unit_tests/test_build_workflow_phase.py` with 5 failing tests covering the opt-in flag gate, version ok install, version-below-minimum skip, version-unknown fail-open, and idempotency scenarios. Tests import `build_phases.build_workflow_scripts` which does not yet exist — all 5 tests will fail red until python-coder implements the function.

### 2026-06-01 10:30 — python-coder (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  templates_workflows_js_created: true
  build_workflow_scripts_added_to_build_phases: true
  phase_registered_in_build_py: true
  tests_green: true
Implemented `build_workflow_scripts()` in `scripts/build_phases.py` with dual-gate logic (opt-in flag + version check using `packaging.version`), compare-before-write guard for `.js` files, and summary output. Registered phase in `build.py` `artifact_phases` list after `build_agents`. Created `templates/workflows-js/.gitkeep`. All 5 new tests pass; 21 tests pass total (no regressions in test_build_workflows, test_build_hooks, test_settings_allowlist, test_build_antigravity_instructions).

### 2026-06-01 10:40 — test-runner (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  all_five_tests_pass: true
  no_regressions: true
Ran `pytest unit_tests/test_build_workflow_phase.py` — 5 passed in 0.32s. Also ran full suite of importable tests (21 total): no regressions. Pre-existing import errors in test_build_version_wiring.py and test_build_changelog_placeholder.py are unrelated to this ticket (missing `release.compute_next_version` module).

### 2026-06-01 10:50 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  function_signature_matches_convention: true
  dual_gate_logic_correct: true
  version_detection_robust: true
  compare_before_write_applied: true
  tests_cover_acceptance_criteria: true
  no_regressions: true
Code review passed. `build_workflow_scripts()` matches phase function convention (target_root, config, dry_run, force → int). Dual-gate logic handles all edge cases (absent key, false, non-dict, below-minimum, unknown). `packaging.version.Version` is correct approach for semantic version comparison. Compare-before-write guard uses SHA-256 consistently with existing binary file pattern. All 5 acceptance criteria covered by tests. Minor note: `os`, `subprocess`, `packaging` imports are function-local rather than module-level — minor style divergence but not a blocker since tests pass and the pattern works.

### 2026-06-01 10:55 — commit (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  files_staged_explicitly: true
  commit_created: true
  tests_still_pass_post_commit: true
Staged and committed: scripts/build_phases.py, scripts/build.py, templates/workflows-js/.gitkeep, unit_tests/test_build_workflow_phase.py, and the ticket file. All 5 workflow phase tests pass.

### 2026-06-01 11:00 — pull-request (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  pr_deferred_to_epic_level: true
PR deferred to epic level per caller instruction (EPIC-FlattenSupervisorChain will open one PR for all tickets). Commit 78d58d0 is on branch worktree-EPIC-FlattenSupervisorChain and ready for the epic-level PR.

## Escalation

Branch: none
Reason: 3 files in one component (build_pipeline); no always-large trigger fired.

## Implementation Tasks

### architect-review

- [x] Confirm the phase insertion point (after build_agents, before build_hooks).
- [x] Confirm the dual-gate design: `skills_config.json → workflows.enabled` (opt-in, default false) AND version check.
- [x] Confirm the version-detection fallback chain is acceptable (env var → subprocess → warn + continue).
- [x] Confirm compare-before-write must apply to .js files (yes — idempotency requirement).

### python-coder

- [x] Create `templates/workflows-js/` directory with a `.gitkeep` so it is tracked before workflow scripts land.
- [x] In `scripts/build_phases.py`, add `build_workflow_scripts(config, target_dir)`:
  - **First gate — opt-in flag**: read `config["workflows"]["enabled"]` from skills_config.json. If absent or `false`, emit `Workflow scripts: skipped (not enabled in skills_config.json)` and return 0.
  - **Second gate — version check**: detect Claude Code version via `CLAUDE_CODE_VERSION` env var, then `claude --version` subprocess, then unknown.
  - Compare detected version against minimum `2.1.154` using `packaging.version` or a manual tuple comparison.
  - If below minimum: emit `[WARNING] Claude Code >= 2.1.154 required for workflow scripts. Skipping.` and return.
  - If unknown: emit `[WARNING] Claude Code version unknown. Installing workflow scripts (fail-open).` and continue.
  - Copy each `.js` file from `templates/workflows-js/` to `<target_dir>/.claude/workflows/`, using the existing compare-before-write guard.
  - Return a `PhaseResult` (or equivalent) with count of files written vs skipped.
- [x] In `scripts/build.py`, register `build_workflow_scripts` in the phase list after `build_agents` and before `build_hooks`.
- [x] Emit a summary line in `build.py`'s output block: `Workflow scripts: N installed (M unchanged)`.

### test-writer

- [x] Add `unit_tests/test_build_workflow_phase.py` (COMPLETED):
  - `test_workflow_scripts_skipped_when_not_enabled` — config has `workflows.enabled = false` (or key absent), assert `.claude/workflows/` not populated, assert "skipped (not enabled" in output.
  - `test_workflow_scripts_installed_when_enabled_and_version_ok` — config has `workflows.enabled = true`, mock `CLAUDE_CODE_VERSION=2.1.154`, assert JS files appear in target.
  - `test_workflow_scripts_skipped_when_version_below_minimum` — config enabled, mock `CLAUDE_CODE_VERSION=2.0.0`, assert target `.claude/workflows/` is empty or absent, assert warning in output.
  - `test_workflow_scripts_installed_when_version_unknown` — config enabled, unset env var and mock subprocess failure, assert files installed and warning present.
  - `test_build_workflow_phase_idempotent` — run phase twice, assert no second write occurs (compare-before-write).

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible — removing the phase registration from `build.py` restores prior behaviour. The `templates/workflows-js/` directory contains only source files; deleting it is safe.
- The version-detection subprocess call to `claude --version` could be slow in CI. Mitigation: prefer the `CLAUDE_CODE_VERSION` env var; subprocess is a last resort with a 2-second timeout.
