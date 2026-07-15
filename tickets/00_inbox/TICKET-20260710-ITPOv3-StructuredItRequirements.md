---
title: "it-po-v3: emit structured it_requirements for package-surface ACs"
status: todo
components:
  - build_orchestration
created: '2026-07-10'
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/it-po-v3.md
agents:
  architect-review: not_needed
  llm-expert: needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
---

# it-po-v3: emit structured it_requirements for package-surface ACs

## Summary

The `it-po-v3` agent emits `it_requirements` as a plain list of strings for every
AC it enriches. But `config/ac_store_schema.json` has a conditional rule: when an AC
has `assigned_agent: python-coder` AND `component` in `build_pipeline` or
`build-orchestration` (a "package-surface" AC), `it_requirements` MUST be a structured
object with five required fields (`config_schema_fragment`, `reference_file_path`,
`n_location_rule`, `required_skills`, `post_write_commands`). Because it-po-v3 does not
know this rule, its output fails the `check-ac-schema` commit hook for those ACs.

## Background

Observed during the EPIC-LiveSurfaceTesting revival (PR #266, 2026-07-10): it-po-v3
enriched the BO-2100 tree and produced list-form `it_requirements` for 8 python-coder /
build-orchestration ACs (BO-2100b-1-i, c-1, c-2, c-3, c-3-i, d-1, d-2, d-3). The commit
correctly halted on `check-ac-schema`; it-po-v3 had to be re-dispatched with explicit
instructions to produce the structured object. The agent template should carry that
knowledge so the first pass is schema-compliant.

This likely also affects `it-po` (v2) and any other enrichment agent that writes
`it_requirements`; scope the fix to it-po-v3 but note the sibling in the body.

## Acceptance Criteria

- [ ] AC-1: The it-po-v3 template instructs the agent that package-surface ACs
  (`assigned_agent: python-coder` AND `component` in `build_pipeline`/`build-orchestration`)
  require `it_requirements` as a structured object with all five schema-required fields,
  and to emit that shape on the first pass.
- [ ] AC-2: The template documents that non-package-surface ACs keep the list/string form,
  so the change does not over-apply the structured shape.
- [ ] AC-3: The `prompt-audit` skill (or a manual review) confirms the updated template
  references the exact five field names from `config/ac_store_schema.json`.

## Sign-offs

- [ ] llm-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
