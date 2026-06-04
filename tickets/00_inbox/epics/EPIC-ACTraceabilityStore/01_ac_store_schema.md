---
title: "Define AC YAML schema and write JSON Schema validator"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on: []
priority: high
roadmap_phase: phase_2
advances_current_outcome: false
requires_diagram: false
requires_adr: true
files_touched:
  - config/ac_store_schema.json
  - templates/commit-guardian/check_ac_schema.py
  - config/agent_registry.json
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  adr-author: needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 01: Define AC YAML schema and write JSON Schema validator

## Actor / Goal

In order to give every AC file a machine-readable, versioned contract, we need
to author the canonical JSON Schema for AC YAML files and write a validation
script installed as a pre-commit hook, so that malformed AC files are rejected
at commit time before they enter the repository.

## Context

This is the foundation ticket. All other AC store work depends on a stable
schema. The schema must be accepted via ADR before any AC YAML files are
written, to prevent churn later.

### AC YAML schema (draft — subject to ADR)

```yaml
id: FIN-001                        # component-prefix + sequential number
title: "Merge main before running tests"
component: finalize               # matches docs/components.json key (or custom)
status: active                    # active | deprecated | superseded_by
superseded_by: null               # or AC ID when status == superseded_by
created_by: "EPIC-FinalizeFeatureHardening/01_merge_main_into_worktree.md"
amended_by: []                    # list of ticket refs that changed this AC
criteria: |
  Given a feature branch worktree exists
  When /finalize-feature runs
  Then git merge origin/main executes inside the worktree before test-runner
   And the workflow halts with category: merge_conflict if conflicts are detected
covered_by:
  - "unit_tests/finalize/test_merge_step.py::test_merge_main_executes_before_tests"
implemented_by:
  - "templates/workflows-js/finalize-feature.js#step_3_5"
```

### ID format

`<COMPONENT_PREFIX>-<NNN>` where:
- `COMPONENT_PREFIX` is 2–6 uppercase letters matching the component name
  abbreviation (e.g. `FIN` for `finalize`, `AUTH` for `auth`, `SUP` for
  `supervisor`).
- `NNN` is a zero-padded three-digit sequential number within the component.
- IDs are assigned at AC creation time by the BA agent. Once assigned, they
  never change.

### Validator script

`check_ac_schema.py` — a standalone stdlib script (no leafcutter imports)
installed as a commit-guardian hook. It validates each `docs/acceptance-criteria/**/*.yaml`
file against `config/ac_store_schema.json` using `jsonschema` (fallback to
manual field checks if `jsonschema` is absent).

## Acceptance Criteria

```gherkin
Given config/ac_store_schema.json is written
When the schema is read
Then it defines required fields: id, title, component, status, created_by, criteria
 And it defines optional fields: superseded_by, amended_by, covered_by, implemented_by
 And status is an enum: active, deprecated, superseded_by

Given check_ac_schema.py is run against a valid AC YAML file
When the file matches the schema
Then the script exits 0

Given check_ac_schema.py is run against an AC YAML file missing the criteria field
When the script validates the file
Then it exits 1 with a message identifying the missing field and the file path

Given check_ac_schema.py is registered in commit_guardian.json
When build.py --validate-only runs
Then no template injection errors are reported

Given an ADR is authored covering the AC store schema and ID format
When the ADR is read
Then it documents the status lifecycle, ID format, and rationale for
 separating AC files from ticket bodies
```

## Sign-offs

- [ ] architect-review
- [ ] adr-author
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### adr-author
- [ ] Author an ADR titled "AC Store: YAML schema, ID format, and
  bidirectional enforcement model." Document: (a) the rationale for
  separating ACs from ticket bodies; (b) the YAML schema fields and
  their semantics; (c) the ID format and assignment process; (d) the
  bidirectional enforcement model (pre-commit hooks); (e) the migration
  strategy for existing tests (warning-first grace period).

### architect-review
- [ ] Review the schema draft above against the existing data structures in
  `docs/components.json` and `config/agent_registry.json`. Confirm field
  names do not collide with existing leafcutter conventions. Approve or
  request changes before python-coder begins.

### python-coder
- [ ] Write `config/ac_store_schema.json` — JSON Schema (draft-07) for the
  AC YAML file format. Required fields: `id`, `title`, `component`,
  `status`, `created_by`, `criteria`. Optional: `superseded_by`,
  `amended_by`, `covered_by`, `implemented_by`. Status enum:
  `["active", "deprecated", "superseded_by"]`.
- [ ] Write `templates/commit-guardian/check_ac_schema.py` — standalone
  stdlib script. For each `.yaml` file under `docs/acceptance-criteria/`:
  load YAML, validate required fields, validate status enum, validate ID
  format regex `^[A-Z]{2,6}-[0-9]{3}$`. Exit 0 on all valid, exit 1 with
  per-file errors.
- [ ] Register `check_ac_schema.py` in `templates/commit-guardian/commit_guardian.json`
  under custom hooks (pass_filenames: false, runs on all staged files,
  filters to `docs/acceptance-criteria/**/*.yaml`).

### test-writer
- [ ] Write `unit_tests/commit_guardian/test_check_ac_schema.py`:
  - `test_valid_ac_passes` — minimal valid YAML passes.
  - `test_missing_required_field_blocked` — YAML without `criteria` exits 1.
  - `test_invalid_status_blocked` — YAML with `status: unknown` exits 1.
  - `test_invalid_id_format_blocked` — YAML with `id: NOTVALID` exits 1.
  - `test_deprecated_ac_passes` — YAML with `status: deprecated` passes.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? JSON Schema file and validator script are new files;
  fully reversible.
- The ADR step is a hard gate before any AC YAML files are written to prevent
  schema churn. The python-coder must wait for architect-review sign-off.
