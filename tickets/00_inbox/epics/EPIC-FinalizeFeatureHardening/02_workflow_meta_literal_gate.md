---
title: "Add a pure-literal meta validation gate for workflow scripts"
status: todo
components:
  - build_pipeline
  - precommit_hooks
created: 2026-06-24
depends_on:
  - 01_collapse_workflow_meta_literals.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: true
files_touched:
  - templates/scripts/commit_guardian/check_workflow_meta.py
  - unit_tests/commit_guardian/test_check_workflow_meta.py
  - templates/scripts/commit_guardian/commit_guardian.json
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

# 02: Add a pure-literal meta validation gate for workflow scripts

## Actor / Goal

In order to prevent the `meta must be a pure literal` failure from ever
recurring, we need a mechanical gate that parses every
`templates/workflows-js/*.js` `meta` block and fails when any value is not a
pure literal — so a careless `+` never ships unnoticed again.

## Context

The root cause of the finalize blocker is not just the offending strings (ticket
01 fixes those) — it is the **absence of any gate**. `build_phases.py` byte-copies
the workflow scripts without parsing them, and no test or pre-commit hook checks
`meta`. The contract is therefore enforced only by the closed-source `Workflow`
tool at invoke time, for the one script you happen to run. Four scripts carried
the latent defect undetected for exactly this reason.

A small validator can `import()`/parse each script and assert that `meta` and all
nested values (`description`, `name`, `phases[]`, and any object entries) are
string/array/object literals with no `BinaryExpression`, identifier, call, spread,
or template-literal-with-substitution nodes.

This ticket also adds an ADR-006 addendum documenting the pure-literal `meta`
contract as a package invariant.

## Acceptance Criteria

- [ ] AC-1: A new check (`check_workflow_meta.py`) parses each
  `templates/workflows-js/*.js`, locates its `export const meta`, and exits
  non-zero with a per-file message naming the offending field when any value is
  not a pure literal.
- [ ] AC-2: Run against the repo AFTER ticket 01, the check exits 0 for all 6
  current scripts.
- [ ] AC-3: A fixture script with a `+`-concatenated `meta.description` is rejected
  by the check (exit non-zero); a fixture with a clean literal `meta` passes.
- [ ] AC-4: The check is registered as a pre-commit hook scoped to
  `templates/workflows-js/*.js` (staged-files only, consistent with the other
  commit_guardian hooks).
- [ ] AC-5: An ADR-006 addendum records the pure-literal `meta` contract.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |

## Comments

## Implementation Tasks
- [ ] Write `check_workflow_meta.py` (AST parse or Node `import()` + structural assert).
- [ ] Write unit tests with clean + dirty fixtures (AC-3).
- [ ] Register the hook in `commit_guardian.json` (config key + hooks_manifest), staged-scoped.
- [ ] Add the ADR-006 addendum (documentation-expert may assist if needed).

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? High — additive hook + test.
