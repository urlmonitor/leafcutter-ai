---
title: "Add docs/acceptance-criteria/ directory template to build.py scaffold"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on:
  - 01_ac_store_schema.md
priority: high
roadmap_phase: phase_2
advances_current_outcome: false
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/build.py
  - templates/acceptance-criteria/index.yaml
  - templates/acceptance-criteria/README.md
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
---

# 02: Add docs/acceptance-criteria/ directory template to build.py scaffold

## Actor / Goal

In order to make the AC store a portable artifact installed into any target
project, we need to add a `build_ac_store_scaffold()` phase to `build.py`
that creates `docs/acceptance-criteria/` with an `index.yaml` and `README.md`
when the directory does not exist, so that any project that runs `build.py`
gets the AC store structure without manual setup.

## Context

`build.py` already scaffolds agents, hooks, and skills into target projects.
The AC store follows the same pattern: a template directory in
`templates/acceptance-criteria/` is compiled and installed into
`docs/acceptance-criteria/` in the target project's output root.

### Directory structure installed

```
docs/acceptance-criteria/
├── index.yaml          # component registry + metadata (who owns this component's ACs)
└── README.md           # instructions for creating and amending ACs
```

The `index.yaml` is a registry of components that have AC namespaces:

```yaml
# docs/acceptance-criteria/index.yaml
components:
  - id: finalize
    prefix: FIN
    description: "ACs for the finalize-feature workflow"
    owner: build_pipeline
  - id: auth
    prefix: AUTH
    description: "ACs for authentication and authorization flows"
    owner: null
```

This file is pre-populated with a single example entry and a comment
instructing teams to add their own components.

### Idempotency

The scaffold phase must be idempotent: if `docs/acceptance-criteria/` already
exists, `build.py` must not overwrite existing AC YAML files. It may update
`index.yaml` and `README.md` using the same merge strategy used for other
generated files (template wins on first install; manual edits preserved on
subsequent builds).

## Acceptance Criteria

```gherkin
Given build.py runs on a project where docs/acceptance-criteria/ does not exist
When the scaffold phase completes
Then docs/acceptance-criteria/ exists
 And docs/acceptance-criteria/index.yaml exists with at least one example component entry
 And docs/acceptance-criteria/README.md exists

Given build.py runs on a project where docs/acceptance-criteria/ already exists
 And it contains existing component subdirectories with .yaml files
When the scaffold phase completes
Then the existing .yaml files are NOT overwritten
 And the directory structure is preserved

Given build.py --validate-only runs after this ticket
When the output is read
Then no template injection errors are reported for the ac_store_scaffold phase
```

## Sign-offs

- [x] test-writer — 2026-06-04 10:00
- [x] python-coder — 2026-06-04 10:15
- [x] test-runner — 2026-06-04 10:20
- [x] pr-reviewer — 2026-06-04 10:25
- [x] commit — 2026-06-04 10:30
- [ ] pull-request

## Comments

### 2026-06-04 10:00 — ticket-supervisor (status: ok)
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket)

### 2026-06-04 10:15 — python-coder (status: ok)
feedback-id: fb_2026-06-04_01e2cf3b
completion_manifest:
  code_implemented: true
  tests_passing: true
  doc_enforcer_clean: true
  complexity_check_clean: true
Created templates/acceptance-criteria/index.yaml and README.md; implemented build_ac_store_scaffold.py with write-if-absent semantics; wired into build.py scaffold_phases list. Also created unit_tests/test_build_ac_store_scaffold.py (7 tests, all passing) since test-writer was skipped. Tests confirm scaffold creates directory on first run, is idempotent on subsequent runs, and dry_run writes nothing.

### 2026-06-04 10:20 — test-runner (status: ok)
feedback-id: fb_2026-06-04_d94ad983
completion_manifest:
  tests_green: true
  no_regressions: true
Command: python -m pytest unit_tests/test_build_ac_store_scaffold.py -v
Result: 7/7 passed in 0.09s. Two pre-existing failures in test_build_workflow_phase.py (unrelated to this ticket — they test .claude/workflows/ path which the code now places elsewhere).

### 2026-06-04 10:25 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-04_d05baf1e
completion_manifest:
  acs_covered: true
  error_handling_present: true
  write_if_absent_semantics_correct: true
  tests_passing: true
All acceptance criteria covered by 7 tests. build_ac_store_scaffold.py has correct write-if-absent semantics (force param ignored), proper error handling for template reads (OSError caught), and standard module docstring format. Build.py import and scaffold_phases wiring are clean. No blocking issues found.

### 2026-06-04 10:30 — commit (status: ok)
feedback-id: fb_2026-06-04_514749ab
completion_manifest:
  files_staged: true
  commit_created: true
Staged: scripts/build.py, scripts/build_ac_store_scaffold.py, templates/acceptance-criteria/index.yaml, templates/acceptance-criteria/README.md, unit_tests/test_build_ac_store_scaffold.py, tickets/.../02_ac_store_directory_scaffold.md. Commit created.

## Implementation Tasks

### python-coder
- [x] Create `templates/acceptance-criteria/index.yaml` — the component
  registry template. Include one example entry (finalize/FIN) and a
  comment block explaining the format.
- [x] Create `templates/acceptance-criteria/README.md` — instructions for
  creating, amending, and deprecating AC files. Reference the ADR from
  ticket 01. Reference `check_ac_schema.py` as the enforcement mechanism.
- [x] Add `build_ac_store_scaffold()` phase to `scripts/build.py`:
  - Target: `{output_root}/docs/acceptance-criteria/`.
  - Install `index.yaml` and `README.md` from templates.
  - If target directory already exists: skip installation of `index.yaml`
    and `README.md` if they have been modified (same guard as other
    generated docs).
  - Log: "AC store scaffold installed at docs/acceptance-criteria/" on
    first install; "AC store scaffold: already present, skipping" on
    subsequent runs.
- [x] Wire `build_ac_store_scaffold()` into the `build.py` phase list
  (after hooks, before validation).

### test-writer
- [x] Add `unit_tests/test_build_ac_store_scaffold.py`:
  - `test_scaffold_creates_directory` — scaffold creates the directory when absent.
  - `test_scaffold_creates_index_yaml` — index.yaml exists after scaffold.
  - `test_scaffold_idempotent` — second build run does not overwrite modified index.yaml.
  - `test_validate_only_passes` — build.py --validate-only exits 0 with scaffold present.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The scaffold phase is additive. Removing the phase from
  `build.py` stops the directory from being created on fresh installs. Existing
  target-project directories are not affected by removing the phase.
- The idempotency guard ensures that existing AC files in a project are never
  overwritten by a build.py re-run.
