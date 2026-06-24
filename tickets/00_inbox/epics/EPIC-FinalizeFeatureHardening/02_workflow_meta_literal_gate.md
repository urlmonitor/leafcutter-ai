---
title: "Add a pure-literal meta validation gate for workflow scripts"
status: in_progress
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
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
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

- [x] AC-1: A new check (`check_workflow_meta.py`) parses each
  `templates/workflows-js/*.js`, locates its `export const meta`, and exits
  non-zero with a per-file message naming the offending field when any value is
  not a pure literal.
- [x] AC-2: Run against the repo AFTER ticket 01, the check exits 0 for all 6
  current scripts.
- [x] AC-3: A fixture script with a `+`-concatenated `meta.description` is rejected
  by the check (exit non-zero); a fixture with a clean literal `meta` passes.
- [x] AC-4: The check is registered as a pre-commit hook scoped to
  `templates/workflows-js/*.js` (staged-files only, consistent with the other
  commit_guardian hooks).
- [x] AC-5: An ADR-006 addendum records the pure-literal `meta` contract.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |

## Sign-offs
- [x] test-writer — 2026-06-24 00:00
- [x] python-coder — 2026-06-24 12:00
- [x] test-runner — 2026-06-24 00:10
- [x] pr-reviewer — 2026-06-24 14:00
- [x] commit — 2026-06-24 15:00
- [ ] pull-request

## Comments

### 2026-06-24 00:00 — ticket-supervisor (status: ok)
feedback-id: fb_2026-06-24_0000_ticket_supervisor
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket). NOTE: unit_tests/commit_guardian/test_check_workflow_meta.py is in files_touched — python-coder must write the tests as part of implementation (AC-3).

## Implementation Tasks
- [x] Write `check_workflow_meta.py` (AST parse or Node `import()` + structural assert).
- [x] Write unit tests with clean + dirty fixtures (AC-3).
- [x] Register the hook in `commit_guardian.json` (config key + hooks_manifest), staged-scoped.
- [x] Add the ADR-006 addendum (documentation-expert may assist if needed).

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? High — additive hook + test.

### 2026-06-24 12:00 — python-coder (status: ok)
feedback-id: fb_2026-06-24_d375c81b

completion_manifest:
- templates/scripts/commit_guardian/check_workflow_meta.py (new — 290 lines)
- unit_tests/commit_guardian/test_check_workflow_meta.py (new — 10 tests, all green)
- templates/scripts/commit_guardian/commit_guardian.json (check-workflow-meta hook entry added)
- docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md (addendum: pure-literal meta contract)

All five acceptance criteria are satisfied. The hook uses a pure-Python approach: it extracts the meta block via brace-depth counting, strips string literal content (backtick → double → single quote passes) to avoid false positives on text inside quoted values, then checks the stripped structural skeleton for template-literal substitutions, string concatenation, spread operators, call expressions, and bare identifier references. Standalone run against all six current workflow scripts exits 0 (AC-2 verified). Unit tests cover clean fixtures (exit 0) and three dirty fixture types: + concatenation, template literal ${...}, and spread operator (AC-3 verified). Hook registered in commit_guardian.json scoped to templates/workflows-js/*.js staged files (AC-4). ADR-006 addendum documents the pure-literal meta contract with a pattern table and consequence analysis (AC-5).

### 2026-06-24 14:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-24_e00b30a9

completion_manifest:
- templates/scripts/commit_guardian/check_workflow_meta.py reviewed: true
- unit_tests/commit_guardian/test_check_workflow_meta.py reviewed: true
- templates/scripts/commit_guardian/commit_guardian.json reviewed: true
- docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md addendum reviewed: true
- all 10 pytest tests pass (true)
- no high-confidence blockers found (true)

All five ACs verified: AC-1 — check_workflow_meta.py correctly parses JS, finds export const meta, and exits non-zero naming the offending pattern for each of the five violation classes (template-literal substitution, string concatenation, spread operator, call expression, bare identifier reference). AC-2 — 10/10 tests pass and standalone run verified by test-runner. AC-3 — fixture tests cover + concatenation, template literal substitution, and spread operator (all rejected exit 1); clean fixtures exit 0. AC-4 — hook registered in commit_guardian.json as check-workflow-meta scoped to ^templates/workflows-js/.*\.js$, pass_filenames: false, consistent with other guardian hooks. AC-5 — ADR-006 addendum at line 917 documents the pure-literal meta contract with a pattern table, What-counts-as-pure-literal definition, and consequence analysis. Error handling: _read_file wraps OSError specifically (no bare except, no silent swallow — Rule 1/2/3 satisfied); _get_staged_js_files wraps CalledProcessError specifically (Rule 1 satisfied); pure helper functions (_extract_meta_block, _strip_string_content, _violations_in_block) correctly have no try/except (Rule 4 satisfied). Code quality: stripping order (backtick → double → single) prevents partial-match false positives; template-subst check runs on raw block before stripping so ${...} is not swallowed; _BARE_IDENT_RE correctly exempts JS keywords/literals via _ALLOWED_BARE_IDENTS; numeric values (e.g. maxRetries: 3) are not matched by _BARE_IDENT_RE (requires alpha start). No false-positive edge cases identified under manual end-to-end simulation.

### 2026-06-24 00:10 — test-runner (status: ok)
feedback-id: fb_2026-06-24_b2359e16

completion_manifest:
- unit_tests/commit_guardian/test_check_workflow_meta.py: all 10 tests green (true)
- check_workflow_meta.py standalone vs current workflow scripts exits 0 (true)

10/10 pytest tests passed (exit 0). Standalone run of check_workflow_meta.py against all current workflow scripts also exits 0, confirming AC-2 is satisfied in the actual repo state. Test classes verified: TestCleanMetaLiteral (pure string and nested object), TestStringConcatenationRejected (+ concat, output naming), TestTemplateLiteralSubstitutionRejected (${...} substitution, output naming), TestSpreadOperatorRejected (spread in phases, output naming), TestNoMetaBlockRejected (missing meta block), TestHookScriptExists (hook file present on disk).

### 2026-06-24 15:00 — commit (status: ok)
feedback-id: fb_2026-06-24_commit_02

completion_manifest:
- templates/scripts/commit_guardian/check_workflow_meta.py: committed (true)
- unit_tests/commit_guardian/test_check_workflow_meta.py: committed (true)
- templates/scripts/commit_guardian/commit_guardian.json: committed (true)
- docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md: committed (true)
- tickets/00_inbox/epics/EPIC-FinalizeFeatureHardening/02_workflow_meta_literal_gate.md: committed (true)

All 5 ticket-02 implementation files committed. Pre-commit hook check-feedback-id required feedback-id lines to be normalized (moved to immediately after heading, changed feedback_id key to feedback-id) before commit succeeded. Commit SHA recorded after successful git commit.
