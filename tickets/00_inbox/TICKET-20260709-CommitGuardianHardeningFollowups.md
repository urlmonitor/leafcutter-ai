---
title: "Commit-guardian hardening follow-ups: parity-hook enforcement gap, diagram dead-SSOT, missing docstring_parser dep"
status: todo
components:
  - commit_guardian
  - precommit_hooks
created: 2026-07-09
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
files_touched:
  - templates/scripts/commit_guardian/check_hook_parity.py
  - templates/scripts/commit_guardian/diagram_type_validators.py
  - templates/commit-guardian/diagram_type_validators.py
  - templates/commit-guardian/commit_guardian.json
  - requirements-dev.txt
  - unit_tests/commit_guardian/test_check_hook_parity.py
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
complexity: medium
---

# Commit-guardian hardening follow-ups

## Actor / Goal

In order to close the correctness/hygiene debt surfaced by the EPIC-Phase1ReadyHardening
code review, we need to make the flagship parity hook enforce (or honestly document) its
charter, clean up the deliberately-deferred diagram-type dead-SSOT, and declare a missing
runtime dependency — so the commit-guardian subsystem does what it claims and does not
silently break on a fresh environment.

## Context

Deferred findings from the EPIC-Phase1ReadyHardening code review (merged via PR #223).
None block runtime today; all are debt in the commit-guardian + build subsystem.

- H-2/M-1 were left as a design decision at review time.
- L-3/L-4/L-5 (diagram dead-SSOT) were **explicitly scoped out** by EPIC-Phase1ReadyHardening
  ticket 02 ("the dead-SSOT architecture … is OUT OF SCOPE — fix the effective runtime enum
  source only"). This ticket is where that deferred cleanup lands.
- The `docstring_parser` gap was surfaced by the behavioral spot-check.

**Explicitly NOT in scope:** the test-writer auto-skip / missing `## Test Requirements`
bug. That is already being addressed on branch EPIC-PromptAssemblyHardening (PR #247) —
do not duplicate it here.

## Acceptance Criteria

- [ ] AC-1: `check_hook_parity` enforces or honestly documents its charter. Given the hook whose stated purpose is catching "a hook added in one location but not shipped to another," when it runs, `check_deployed_parity` currently always returns `[]` (non-blocking) and the script/manifest checks compare filenames/IDs only (content-blind — divergent `diagram_type_validators.py` copies pass); then EITHER add a blocking canonical→deployed + content-hash check gated on a build-freshness signal (so a pre-build staging state does not self-block, but a genuinely undeployed/stale hook DOES block), OR update the hook docstring and its AC to state that ship-direction and content parity are owned by `check_build_drift` — so the deliverable does not claim a guarantee it does not enforce.
- [ ] AC-2: Diagram-type dead-SSOT cleanup. Given the canonical `diagram_type_validators.py` resolves `_DIAGRAM_TYPES_JSON` to `templates/leafcutter/config/diagram_types.json` which never exists (the real file is `config/diagram_types.json`), silently riding the `DOC_FM_DIAGRAM_TYPE_VALUES` fallback; when this ticket runs, the SSOT path is corrected to the real file and the fallback path logs a WARNING (no silent swallow), AND the dead `doc_frontmatter.diagram_type_values` block is removed from the legacy `templates/commit-guardian/commit_guardian.json` and the never-imported divergent legacy `templates/commit-guardian/diagram_type_validators.py` is either removed or reduced to a minimal parity stub. Accept/reject behavior for `data_flow`/`user_flow`/`agent_flow`/`dataflow` (and rejection of bogus values) is unchanged.
- [ ] AC-3: `docstring_parser` is declared as a dependency. Given `check_docstrings` / `docstring_validators` import `docstring_parser`, which is absent from `requirements-dev.txt`; when a fresh environment runs those hooks, they must not fail with `ModuleNotFoundError` — `docstring_parser` is added to `requirements-dev.txt`.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [ ] AC-1: decide enforce-vs-document; implement the chosen path in `check_hook_parity.py` (+ update its ACs/docstring); add a test for the chosen behavior.
- [ ] AC-2: fix canonical `_DIAGRAM_TYPES_JSON` path + log-on-fallback; strip dead legacy manifest block + minimize/remove legacy validator; keep enum behavior green.
- [ ] AC-3: add `docstring_parser` to `requirements-dev.txt`; add/confirm an import smoke test for `check_docstrings` + `docstring_validators`.
- [ ] Tests for each AC (test-writer authors real tests — see NOT-in-scope note; do not rely on the auto-skip path).

## Risk & Safety
- Touches money? No.
- Touches data? No — commit-guardian hooks + a dev dependency declaration.
- Reversibility? Fully reversible (config/hook edits, additive dep). AC-2 removes dead code — confirm the legacy validator is genuinely never imported before deletion (the review verified this, but re-check at implementation time).
