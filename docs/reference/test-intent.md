---
title: "Reference: Test Intent and Test-Design Provenance"
description: "Lookup reference for test_intent (what the IT PO says must be tested, one entry per outcome clause), the one clause-normalisation rule, the design-pending and legacy-design predicates, the per-entry and authorship fields of a test design, and the by-author report."
type: reference
status: active
created: 2026-10-14
last_updated: 2026-10-14
components:
  - ac_store
  - ac_driven_dev
related_docs:
  - docs/reference/ac-schema.md
  - docs/reference/requirement-rule-check.md
  - docs/architecture/adrs/ADR-071-test-intent-is-not-a-test-contract.md
  - config/ac_store_schema.json
  - scripts/ac_store/_test_intent.py
  - scripts/ac_store/_rc_test_intent.py
  - scripts/ac_store/design_authors_report.py
---

# Test Intent and Test-Design Provenance

`test_intent` records what must be tested; it is not a test contract (ADR-071). The test design (`test_spec`) is written later by the code-aware step. Field rows live in [ac-schema.md](ac-schema.md); this page states the rules that are defined once, in `scripts/ac_store/_test_intent.py`.

---

## What test intent is

`test_intent` is a per-outcome needs-test decision with a reason. It is a list with one `{clause, needs_test, reason}` entry per outcome clause of `criteria`, including each clause that needs no test.

| Key | Type | Meaning |
|---|---|---|
| `clause` | string | The outcome clause, matched to `criteria` under `normalise_clause`. |
| `needs_test` | boolean | Whether the clause needs a test. |
| `reason` | string | One sentence: why the clause does or does not need a test. |

Test intent is **not a test contract** ([ADR-071](../architecture/adrs/ADR-071-test-intent-is-not-a-test-contract.md)). It names no test, directory, framework, type, angle or strategy. A record with intent and no design has no test contract.

## Who writes what

| Artifact | Written by | Never written by |
|---|---|---|
| `test_intent` | The technical planner (the IT PO) | The code-aware test-design step |
| `test_spec`, `test_design_authorship`, `test_design_opened_files` | The code-aware test-design step | The IT PO |
| `must_catch` (an existing optional `test_spec` entry field, TQ-500f-2) | The code-aware test-design step only | The IT PO |

The presence of `must_catch`, or of angle `discrimination` (TQ-500f-1), on an entry is the code-aware step's bug-fix or gate declaration. The field rules are in [ac-schema.md](ac-schema.md) (`must_catch`, `angle`) and the angle set in [test-angles.md](../testing/test-angles.md); neither is restated here.

## Intent with no design cannot be approved or built

`design_pending(record)` is true for a record with intent and no design. At approval, a record that has a design is also held when a `needs_test` true clause has no `test_spec` entry whose `proves_clause` matches it under `normalise_clause` (`uncovered_needs_test_clauses`). Four points hold such a record, each with the reason `test design pending`:

| Point | Where | Effect |
|---|---|---|
| Approval | `approve_acs.py`, through `_approval_holds.approval_hold_reason` | Not promoted and not written; reported as `held <id>: test design pending`, or as an entry of `held` with `--json`. |
| Readiness gate | `_impl_readiness_gate.py` | Reported instead of `missing test contract`; always held, whatever `--enforce-impl-readiness` and `schema_version` say. |
| Ticket generator | `generate_ticket_from_ac.py` (`_gtfa_tests_section.py`) | Refuses with `TestDesignPendingError`; no ticket is written. |
| Commit check | `_test_design_pending.py`, called by `validate_test_contract` | An approved leaf code AC with intent and no `test_spec` fails with a `test design pending` message. |

`--json` on `approve_acs.py` prints exactly `{"approved": [id], "held": [{"id", "file", "reason"}]}`; `reason` is a member of `HOLD_REASONS`. The reason table is in [ac-readiness-and-assignment-gates.md](ac-readiness-and-assignment-gates.md#hold-reasons).

## Designs written before the change

A design written before the code-aware step existed is kept, not deleted, and its record gains no intent, hold reason or readiness change. It is told apart from a code-aware design by the missing `test_design_authorship` mark: `is_legacy_design(record)` is the only test. `design_authors_report.py` lists every such record under `legacy`.

---

## Outcome clauses

`outcome_clauses(criteria)` is the single parser for intent. A clause is the text after each `Then`, and after each `And` that follows the first `Then`; continuation lines are joined with single spaces. An `And` before the first `Then` continues the Given or When and is not an outcome. (The ticket generator's own `Then` matcher has no `And` and no continuation lines and is left alone.)

## The normalisation rule

`normalise_clause(text)` is the only matching rule, applied by every consumer: whitespace runs collapse to one space, the ends are stripped, and **one** trailing `,` `;` or `.` is dropped. Punctuation inside the clause stays. This keeps a clause matching its entry when a later clause is appended and the old last clause's `.` becomes `,`.

## Predicates

| Function | True when |
|---|---|
| `design_pending(record)` | `test_intent` is non-empty and `test_spec` is absent, null or empty |
| `is_legacy_design(record)` | `test_spec` is non-empty and the record has no `test_design_authorship` mark |

A record with no design is neither legacy nor code-aware. Nothing re-derives either predicate.

## Design fields

Per-entry keys of `test_spec` (all optional): `proves_clause` (the verbatim `test_intent[].clause`, matched under `normalise_clause`), `code_file`, `to_be_created`, `convention_test_file`. Record-level: `test_design_authorship` (`{step, date}`) and `test_design_opened_files`. Each has a constant in `_test_intent.py` (`ENTRY_CLAUSE_KEY`, `ENTRY_CODE_FILE_KEY`, `ENTRY_TO_BE_CREATED_KEY`, `ENTRY_CONVENTION_KEY`, `AUTHORSHIP_KEY`, `OPENED_FILES_KEY`); a test asserts each is a declared schema property. An entry key the schema does not declare is rejected by name by `_ac_schema_test_spec_validators.py`, which reads the declared set from the schema.

## Reports

- Rule family `test intent coverage` (`requirement_rule_check.py`): `needs a decision` for an outcome clause with no entry (`detail.kind` `missing`), an entry whose clause is gone (`stale`) and a clause with two entries (`duplicate`). Only records with a non-empty `test_intent` are evaluated.
- `python scripts/ac_store/design_authors_report.py [--ac-root DIR] [--json]` lists designs by the mark's `step` and every unmarked design under `legacy`. It describes and never gates (exit 0); it is in no deploy map.
