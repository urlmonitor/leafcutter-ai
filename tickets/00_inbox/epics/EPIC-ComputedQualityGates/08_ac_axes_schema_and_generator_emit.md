---
title: "AC axes in schema + generator emits axes into generated tickets"
status: todo
components:
  - ac_store
created: 2026-07-07
depends_on:
  - 07_wire_computed_agents_map.md
priority: high
requires_adr: false
requires_diagram: false
change_target: schema
risk_surface: internal
files_touched:
  - config/ac_schema.json
  - config/ac_store_schema.json
  - docs/reference/ac-schema.md
  - templates/docs/reference/ac-schema.md
  - scripts/ac_store/validate_ac_schema.py
  - templates/scripts/commit_guardian/_ac_schema_validators.py
  - scripts/ac_store/generate_ticket_from_ac.py
  - config/guardrail_gates.yaml
  - unit_tests/test_generate_ticket_from_ac.py
  - unit_tests/commit_guardian/test_check_ac_schema.py
agents:
  test-writer: needed
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 08: AC axes in schema + generator emits axes into generated tickets

## Actor / Goal

In order for computed quality gates to fire on real acceptance criteria, we need the AC record to carry `change_target` + `risk_surface` as first-class, validated fields, and the ticket generator to emit those axes into the ticket frontmatter it produces — so the computed path in `_build_agents_map` (landed in ticket 07) receives real classification data instead of `None`.

## Context

Ticket 07 wired `_build_agents_map` to read `change_target`/`risk_surface` from the AC record and reconciled `config/guardrail_gates.yaml` to the ADR-017 blast-radius vocabulary. But a real-path check (`generate_ticket_from_ac.py --ac BO-620 --dry-run`) proved the feature is still inert: **no AC record in the store carries the axes**, and the generator never emits them into generated tickets. So `ac.get("change_target")` is `None` for every real AC → legacy agent map.

This ticket closes the AC-store half of that gap: it makes the axes valid+enforced AC fields and has the generator both consume and *emit* them. It also folds in the non-blocking findings from ticket 07's pre-PR review.

Canonical vocabulary (must match `templates/hooks/ticket_frontmatter_guard.py` `ALLOWED_CHANGE_TARGETS`/`ALLOWED_RISK_SURFACES`, per the user's 2026-07-06 decision to keep the ADR-017 blast-radius vocabulary canonical):
- `change_target`: code, schema, ui, infrastructure, pipeline, prompt, model, config, docs, dependency
- `risk_surface`: internal, contract_boundary, auth, privacy, safety, cost

Backfilling existing AC records with the axes and the real-store end-to-end assertion live in ticket 10. Teaching `it-po-v3` to author the axes lives in ticket 09 (deferred).

## AC References

- Builds on 07_wire_computed_agents_map.md (computed path + guardrail vocabulary).

## Acceptance Criteria

- [ ] AC-1: The AC record schema (`config/ac_schema.json` / `config/ac_store_schema.json`) defines optional `change_target` (enum of the 10 blast-radius values, string or list) and `risk_surface` (enum of the 6 values, string) fields; `docs/reference/ac-schema.md` documents them.
- [ ] AC-2: `validate_ac_schema.py` (and the mirrored `_ac_schema_validators.py`) reject an AC whose `change_target` or `risk_surface` is present but not in the canonical enum; absent is allowed (optional field).
- [ ] AC-3: A vocabulary-contract assertion guarantees the AC-schema enum for both axes is identical to the guard's `ALLOWED_CHANGE_TARGETS`/`ALLOWED_RISK_SURFACES` and to the `config/guardrail_gates.yaml` key sets (single source of truth; blocks on drift).
- [ ] AC-4: `_build_frontmatter` in `generate_ticket_from_ac.py` emits `change_target` and `risk_surface` into generated ticket frontmatter whenever the source AC carries them (omits them when absent).
- [ ] AC-5 (finding H-1): `_build_agents_map` logs a WARNING (project logger) when a `(change_target, risk_surface)` lookup finds no guardrail entry, so a silent empty gate set is never invisible again.
- [ ] AC-6 (findings M-1/M-2/M-3): `_build_ticket_body` accepts a pre-computed agents map instead of recomputing it (M-1); `change_target` normalization is extracted into one helper reused at all call sites (M-2); `config/guardrail_gates.yaml` `flow_change_gates` is migrated to the blast-radius `risk_surface` vocabulary (M-3).
- [ ] AC-7: All prior ticket-07 tests remain green; new tests cover AC-1..AC-6.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |
| AC-7 | | | |

## Comments

## Sign-offs
- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### test-writer
- [ ] Add schema-validation tests (valid/invalid axis values; absent allowed) to `unit_tests/commit_guardian/test_check_ac_schema.py`.
- [ ] Add the vocabulary-contract test (AC-schema enum == guard enum == guardrail_gates.yaml keys) for both axes.
- [ ] Add generator tests asserting `_build_frontmatter` emits the axes when the AC has them and omits them when absent (AC-4).
- [ ] Add a test asserting the WARNING is logged on a guardrail lookup miss (AC-5, via caplog).

### python-coder
- [ ] Add `change_target`/`risk_surface` to `config/ac_schema.json` + `config/ac_store_schema.json` (optional, enum-constrained) and document in `docs/reference/ac-schema.md` (+ templates mirror).
- [ ] Extend `validate_ac_schema.py` and `_ac_schema_validators.py` to enforce the enums when present.
- [ ] Emit the axes from `_build_frontmatter` when the source AC carries them (AC-4).
- [ ] Add the WARNING-on-miss log in `_build_agents_map` (AC-5).
- [ ] Refactor: pass the computed agents map into `_build_ticket_body` (M-1); extract `_normalize_change_target(ac)` helper (M-2); migrate `flow_change_gates` risk_surface labels to blast-radius vocab (M-3).

## Risk & Safety
- Touches money? No.
- Touches data? Adds optional fields to the AC schema; existing ACs remain valid (fields optional until ticket 10 backfills). Fully reversible.
- Reversibility? All code/config/schema on the epic branch; revert the commit to restore prior behavior.
