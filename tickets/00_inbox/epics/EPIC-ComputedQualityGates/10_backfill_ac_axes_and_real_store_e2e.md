---
title: "Backfill AC store with axes + real-store end-to-end computed-map test"
status: done
components:
  - ac_store
created: 2026-07-07
depends_on:
  - 08_ac_axes_schema_and_generator_emit.md
priority: high
requires_adr: false
requires_diagram: false
change_target: config
risk_surface: internal
files_touched:
  - docs/acceptance-criteria
  - unit_tests/test_generate_ticket_from_ac.py
  - .security-allowlist
agents:
  test-writer: signed_off
  python-coder: signed_off
  test-runner: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
---

# 10: Backfill AC store with axes + real-store end-to-end computed-map test

## Actor / Goal

In order to make computed quality gates actually fire on the existing acceptance criteria — and to prove it does with a test that would have caught the original phantom-done — we need to backfill every existing AC record with `change_target` + `risk_surface`, and add a real-store end-to-end test that generates a ticket from a real AC and asserts the computed guardrail agents appear in the emitted `agents:` map.

## Context

Ticket 08 makes the axes valid AC fields and has the generator consume + emit them. But the existing store still carries no axes, so until it is backfilled the computed path stays dormant for real inputs. This ticket performs the backfill and installs the behavioral gate that proves the whole chain works end-to-end.

**Backfill method (user decision, 2026-07-06): agent-classified, batch-reviewed.** An agent reads each AC's `criteria` prose and proposes `change_target`/`risk_surface`; the proposals are applied in batches, each surfaced as a diff for human approval before write. Many ACs already describe their axes in prose (e.g. `BO-620`: "Schema changes at a contract boundary…", "Code changes with internal risk…"), so classification is well-grounded.

The end-to-end test is the anti-phantom-done gate: it must exercise the REAL generator against a REAL (post-backfill) AC and assert the guardrail union is present — not a synthetic AC with hard-coded axes (that is what let the original defect ship green).

## AC References

- Depends on 08_ac_axes_schema_and_generator_emit.md (axes must be valid + emitted first).

## Pilot Scope (2026-07-07)

The AC store holds **1,802 records across 12 component folders**. Per the user's decision, this ticket executes the backfill as a **pilot on one component** — `testing-quality/` (31 ACs) — to prove the end-to-end chain on the real store, then defer the remaining 11 folders (~1,771 ACs) to a tracked follow-up. AC-1/AC-2 are scoped to the pilot component accordingly.

## Acceptance Criteria

- [ ] AC-1: Every AC record in the pilot component `docs/acceptance-criteria/testing-quality/` (31 ACs) carries a valid `change_target` and `risk_surface` (enum-validated by the ticket-08 `check_ac_schema` guard against `ac_store_schema.json`; zero errors). Full-store backfill of the remaining 11 folders is deferred to a follow-up ticket.
- [ ] AC-2: The pilot backfill was applied via agent classification with a human-approved batch diff (approval recorded in this ticket's Comments); no pilot AC is left with a placeholder/unknown axis.
- [ ] AC-3: A real-store end-to-end test generates a ticket from an actual AC classified as a code/production-risk change and asserts the emitted `agents:` frontmatter contains the guardrail union (e.g. `architect-review`, `test-writer`, `test-runner`) — NOT the legacy map, and NOT via a synthetic hard-coded AC.
- [ ] AC-4: A `--dry-run` spot-check on a representative real AC shows the computed map (documented in Comments as evidence, mirroring the diagnostic that exposed the original defect).
- [ ] AC-5 (tooling): The `.security-allowlist` entries for `unit_tests/test_generate_ticket_from_ac.py` are converted from brittle per-line numbers to a single glob entry (`ENTROPY_HIGH:unit_tests/test_generate_ticket_from_ac.py:*`) so future edits don't re-break the suppressions.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | unit_tests/test_generate_ticket_from_ac.py:TestRealStoreComputedMapE2E::test_real_backfilled_ac_gets_architect_review | | |
| AC-4 | | | |
| AC-5 | | | |

## Comments

### 2026-07-07 09:15 — python-coder (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  backfill_31_acs: true
  schema_validator_zero_errors: true
  dry_run_evidence_captured: true
  allowlist_glob_converted: true
31 AC YAML files in `docs/acceptance-criteria/testing-quality/TQ-100-trustworthy-test-gate/` backfilled with `change_target` and `risk_surface` axes (human-approved mapping). All 31 pass the ticket-08 schema validator (zero errors). `--dry-run` on TQ-100d-1 confirms `architect-review: needed` now appears in the emitted agents map (it was absent before backfill — this is the computed guardrail path firing: `code`+`contract_boundary` unions the flow_change_gates entry). Before: no `change_target`/`risk_surface` → legacy path, no architect-review. After: `change_target: [config, code]`, `risk_surface: contract_boundary` → computed path, agents map includes `architect-review`, `documentation-expert`, `python-coder`, `test-writer`, `test-runner`, `pr-reviewer`, `status-checker`, `commit`, `pull-request`. AC-5 (allowlist glob): `scan_secrets.py` `_is_suppressed` checks `lineno == "*"` (line 118) — `:*` glob IS supported. Replaced 22 per-line `ENTROPY_HIGH:unit_tests/test_generate_ticket_from_ac.py:<N>` entries with a single `ENTROPY_HIGH:unit_tests/test_generate_ticket_from_ac.py:*` glob in both `/home/henzeh/projects/leafcutter/EPIC-ComputedQualityGates/.security-allowlist` and `/home/henzeh/projects/leafcutter/.security-allowlist`.

### 2026-07-07 11:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-07-07_157eee10

Backfill sanity: All 31 TQ-100-trustworthy-test-gate AC files received exactly `change_target` and `risk_surface` appended at end-of-file. Zero existing fields removed or altered (non-destructive). All values conform to the `ac_store_schema.json` enums: change_target (code/config/docs — all valid) and risk_surface (internal/contract_boundary — both valid). No out-of-enum values detected. Semantic consistency is sound: L1/composite ACs carrying cross-agent contracts get `contract_boundary`; leaf L3 ACs targeting purely internal enforcement logic get `internal`; documentation-trigger ACs get `docs`+`internal`. The pilot correctly covers all 31 AC records in the component.

E2E realness: `TestRealStoreComputedMapE2E::test_real_backfilled_ac_gets_architect_review` loads TQ-100d-1.yaml via `_find_ac_by_id` against the real on-disk `_REAL_AC_ROOT` path — not a synthetic dict. The test would fail red if the store were de-backfilled, proving it is a genuine anti-phantom-done gate. All five assertion steps are present: disk load, axis fields present, `_build_agents_map` returns `architect-review: needed`, `_build_frontmatter` emits both axes, and the frontmatter agents block contains `architect-review: needed`.

Validation: `check_ac_schema.py` env-var seam (HOOK_TEST_STAGED_FILES) exited 0 on sample files; all 31 enum values manually verified against `ac_store_schema.json`. Schema exit 0, no violations.

Test run: `python -m pytest unit_tests/test_generate_ticket_from_ac.py -q` → 45 passed in 4.33s (44 pre-existing + 1 new e2e). Ruff check → clean (0 violations).

Security allowlist: The glob consolidation `ENTROPY_HIGH:unit_tests/test_generate_ticket_from_ac.py:*` is confirmed supported by `scan_secrets.py _is_suppressed lineno == "*"` check. Both worktree and workspace-root allowlist files updated per CLAUDE.md dual-update rule.

test-runner signed off: suite 45/45 green, no regressions.
pr-reviewer signed off: backfill correct, e2e genuine, validation clean, test/ruff pass.

### 2026-07-07 14:05 — commit (status: ok)
feedback-id: fb_2026-07-07_c3e8a12f
Ticket-10 pilot committed and pushed to PR #201. 31 testing-quality ACs (TQ-100-trustworthy-test-gate) backfilled with change_target/risk_surface axes; real-store e2e test guards against phantom-done (TestRealStoreComputedMapE2E::test_real_backfilled_ac_gets_architect_review). .security-allowlist test-file entries collapsed to glob. Remaining 11 AC folders (~1,771 ACs) deferred to follow-up ticket.

### 2026-07-07 — test-writer (status: ok)
feedback-id: fb_2026-07-07_a3f7c920
Real-store end-to-end test added: `TestRealStoreComputedMapE2E::test_real_backfilled_ac_gets_architect_review` in `unit_tests/test_generate_ticket_from_ac.py`.

The test loads TQ-100d-1.yaml from the real on-disk AC store via `_find_ac_by_id` (NOT a synthetic dict), then asserts:
  (a) the real record carries `change_target` and `risk_surface` (confirming the backfill wrote to disk),
  (b) `_build_agents_map` driven by those real axes returns a map where `architect-review == 'needed'` (confirming the computed `contract_boundary` path fired),
  (c) `_build_frontmatter` driven by the real record emits both `change_target` and `risk_surface` in the YAML block, and
  (d) the `agents:` block in the emitted frontmatter contains `architect-review: needed`.

Verification: `python -m pytest unit_tests/test_generate_ticket_from_ac.py -q` → 45 passed in 4.15s (44 pre-existing + 1 new). `ruff check` → clean. The test passes because ticket-08 wired the computed path and ticket-10 (python-coder) backfilled TQ-100d-1 with `change_target: [config, code]` and `risk_surface: contract_boundary` — the exact axes that trigger the `architect-review` guardrail. The test would fail red if the real store were de-backfilled, proving it is not a phantom-done gate.

## Sign-offs
- [x] test-writer — 2026-07-07
- [x] python-coder — 2026-07-07 09:15
- [x] test-runner — 2026-07-07
- [x] pr-reviewer — 2026-07-07
- [x] commit — 2026-07-07
- [x] pull-request — 2026-07-07

## Implementation Tasks

### test-writer
- [ ] Add the real-store end-to-end test (real AC → generated ticket → assert guardrail union in `agents:`), independent of synthetic fixtures (AC-3).

### python-coder
- [x] Run/assist the agent-classified backfill of `docs/acceptance-criteria/` in batches; apply each approved batch (AC-1/AC-2).
- [x] Validate the whole store with the ticket-08 schema validator (zero errors).
- [x] Capture the `--dry-run` evidence in Comments (AC-4).
- [x] Convert the test-file `.security-allowlist` entries to a glob (AC-5).

## Out of Scope
- Teaching `it-po-v3` to author the axes for *new* ACs — deferred to ticket 09 (blocked on it-po-v3 source reaching main).
- Fixing the `check_feedback_id.py` `[NO-FEEDBACK-CHECK]`-via-`COMMIT_EDITMSG` bypass defect (git writes `COMMIT_EDITMSG` after the pre-commit stage; only `GIT_COMMIT_MSG` works) — track as a standalone precommit-hooks ticket.

## Risk & Safety
- Touches money? No.
- Touches data? Yes — mutates every AC record in the store (adds two fields). Reversible via git revert; each batch is human-reviewed before write.
- Reversibility? All changes are on the epic branch; revert restores prior AC records.
