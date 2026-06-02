---
title: "Wire workflow scripts into build infrastructure and add template-category parity test"
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
requires_documentation:
  - explanation
  - how_to
files_touched:
  - scripts/build_helpers.py
  - scripts/build_phases.py
  - scripts/build.py
  - templates/scripts/commit_guardian/check_output_drift.py
  - tests/test_build_artifact_parity.py
  - docs/build-pipeline.md
  - docs/explanation/consolidated-output-root.md
  - docs/build-drift-hook.md
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  explanation-author: needed
  how-to-author: needed
---

# Wire workflow scripts into build infrastructure and add template-category parity test

## Actor / Goal

In order to make compiled workflow scripts reachable at `.claude/workflows/` after a build, we need to wire the `build_workflow_scripts` phase into all four supporting infrastructure layers (shim map, output mappings, artifact dir registry, source manifests) and fix the drift-detection path, so that adopters can use `build-epic.js`, `build-ticket.js`, and `create-ticket.js` without manual intervention after running `build.py`.

## Context

`build_workflow_scripts()` was added to `scripts/build_phases.py` and registered in `artifact_phases`, but the phase was never wired into the four complementary infrastructure layers that every other phase relies on. As a result, the compiled JS files are produced but never shimmed into `.claude/workflows/`, and `check_output_drift.py` scans the wrong path (`.agents/workflows/` instead of `.claude/workflows/`).

This bug belongs to the `build_pipeline` component, which orchestrates template compilation via phase-based dispatch, compare-before-write, manifest tracking, and drift detection (see `docs/build-pipeline.md`).

The root cause pattern — adding a phase function without updating all four supporting registries — went undetected because no automated test cross-validates the registries against one another. This ticket also introduces that guard.

### Architectural context (build_pipeline component)

The build pipeline operates through these four infrastructure layers, each of which must reference every phase that produces user-facing output:

| Layer | File | Purpose |
|-------|------|---------|
| Shim map | `scripts/build_helpers.py` → `install_shims()` | Maps output directory to shim target so symlinks are installed into `.claude/` |
| Output mappings | `scripts/build_helpers.py` → `_compute_output_mappings()` | Tracks source→dest pairs for compare-before-write |
| Managed artifact dirs | `scripts/build_phases.py` → `_MANAGED_ARTIFACT_DIRS` | Directories to clean during stale-artifact removal |
| Source manifests | `scripts/build.py` → `_build_source_manifests()` | Scans source templates to produce content fingerprints for drift detection |

All four must include an entry for every phase that produces output artifacts. `build_workflow_scripts` was absent from all four.

### Specific gaps

1. No `(".claude/workflows", "workflows")` entry in `install_shims()` shim_map (line 319 of `build_helpers.py`)
2. No `workflows-js` section in `_compute_output_mappings()` in `build_helpers.py`
3. No `"workflows": "workflows"` key in `_MANAGED_ARTIFACT_DIRS` in `build_phases.py` (line 998)
4. No `workflows-js` scanning block in `_build_source_manifests()` in `build.py` (after line 472)
5. `check_output_drift.py` has `_OUTPUT_DIRS` scanning `.agents/workflows/` (wrong path) instead of `.claude/workflows/`
6. `.pre-commit-config.yaml` hook file pattern is missing `.claude/workflows/`
7. `docs/build-pipeline.md` mermaid diagram does not show the `build_workflow_scripts` phase node
8. `docs/explanation/consolidated-output-root.md` shimmed outputs table is missing the `.claude/workflows/` row

## Acceptance Criteria

```gherkin
Given a clean project with a valid skills_config.json
When build.py is run (or build-self.sh)
Then .claude/workflows/ exists and contains build-epic.js, build-ticket.js, create-ticket.js
And build-self.sh exits 0 with no warnings about missing shims

Given the test suite is run after the fix
When tests/test_build_artifact_parity.py executes
Then all cross-validation assertions pass

Given a developer adds a new template category in templates/ in the future
When they add the phase function and artifact_phases entry but omit one of the four infrastructure layers
Then tests/test_build_artifact_parity.py fails with a descriptive assertion error naming the missing layer

Given check_output_drift.py runs in a pre-commit hook
When .claude/workflows/ contains compiled JS files
Then the hook scans .claude/workflows/ (not .agents/workflows/) and reports drift correctly

Given docs/build-pipeline.md is rendered
When the mermaid diagram is viewed
Then build_workflow_scripts appears as a phase node alongside all other phase nodes

Given docs/explanation/consolidated-output-root.md is rendered
When the shimmed outputs table is viewed
Then a .claude/workflows/ row is present
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request
- [ ] explanation-author
- [ ] how-to-author

## Comments

## Implementation Tasks

### Deliverable 1 — Wire workflows into all four infrastructure layers

- [ ] `scripts/build_helpers.py` — add `(".claude/workflows", "workflows")` to the `shim_map` list in `install_shims()` (around line 319, alongside the other `".claude/*"` entries)
- [ ] `scripts/build_helpers.py` — add a `workflows-js` section to `_compute_output_mappings()` following the same pattern as other JS/script sections
- [ ] `scripts/build_phases.py` — add `"workflows": "workflows"` to `_MANAGED_ARTIFACT_DIRS` dict (around line 998, alongside `"commit_guardian"`, `"doc_compliance"`, etc.)
- [ ] `scripts/build.py` — add a `workflows-js` scanning block in `_build_source_manifests()` (after line 472) and add `"workflows"` to the returned dict
- [ ] `templates/scripts/commit_guardian/check_output_drift.py` — update `_OUTPUT_DIRS` to include `.claude/workflows/` instead of (or in addition to) `.agents/workflows/`; confirm the correct path with the installed output layout

### Deliverable 2 — Add template-category parity test

- [ ] Create `tests/test_build_artifact_parity.py` as a new pytest file
- [ ] Import `shim_map` from `build_helpers.install_shims` (or extract it as a module-level constant)
- [ ] Import `_MANAGED_ARTIFACT_DIRS` from `build_phases`
- [ ] Derive the set of "template output categories" from `_compute_output_mappings()` or an equivalent authoritative source
- [ ] Assert: every category that produces user-facing output has a corresponding entry in `shim_map`
- [ ] Assert: every category has a `_MANAGED_ARTIFACT_DIRS` entry (for stale artifact cleanup)
- [ ] Assert: every shimmed output directory appears in `check_output_drift.py`'s `_OUTPUT_DIRS` list (parse the file or import the constant)
- [ ] Assert: every `_build_source_manifests()` returned key maps to a known category
- [ ] Write the test to be self-describing: assertion messages must name the offending category and the missing layer

### Deliverable 3 — Update documentation

- [ ] `docs/build-pipeline.md` — add `build_workflow_scripts` as a node in the mermaid `graph TD` diagram, with an arrow from `build.py` to the new node and a label showing the `.claude/workflows/` output
- [ ] `docs/explanation/consolidated-output-root.md` — add `.claude/workflows/` row to the shimmed outputs table (source: `templates/scripts/workflows/`, output: `.claude/workflows/`, content: compiled workflow JS scripts)
- [ ] `docs/build-drift-hook.md` — add a developer checklist section titled "Adding a new template category" that enumerates all four infrastructure layers that must be updated and references the parity test as the enforcement gate

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? All changes are additive (new entries in existing registries, new test file, doc updates). Reverting is a straight revert commit. The shim map addition creates a new symlink at `.claude/workflows/`; removal requires deleting that symlink.
- Breaking surface? The `check_output_drift.py` path fix changes which files are scanned by the pre-commit hook. If `.agents/workflows/` was being intentionally scanned (unlikely given the bug description), review before removing it.
- Test isolation: `test_build_artifact_parity.py` imports from `build_helpers` and `build_phases` — ensure those modules are importable without a live `skills_config.json` (use mocking or provide a minimal fixture if needed).
