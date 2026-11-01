---
title: "Reference: Test-Free Declarations"
description: "Lookup reference for a requirement record declared test-free (test_required false with a stated test_rationale): what lifts the done-proof covering-test rule, the two meanings of test_rationale, which checks refuse a missing or duplicated reason, where the eligibility rules live, and what the typed verified_by record will change."
type: reference
status: active
created: 2026-10-25
last_updated: 2026-10-25
components:
  - ac_store
  - build_orchestration
  - testing_quality
related_docs:
  - docs/reference/ac-schema.md
  - docs/how-to/prove-ac-done.md
  - docs/how-to/done-proof-enforcement.md
  - docs/architecture/components/phantom-done-prevention.md
  - docs/architecture/adrs/ADR-076-verification-methods-for-non-test-requirements.md
  - docs/acceptance-criteria/testing-quality/TQ-400-durable-done-proof/TQ-400e-6.yaml
  - config/ac_store_schema.json
  - scripts/ac_store/_done_proof_phase_helpers.py
---

# Reference: Test-Free Declarations

A requirement record normally reaches `work_status: done` only when a passing
test tagged `# covers:<AC-ID>` proves it. A record that no test can prove (a
documentation page, a prose-only change) may instead be **declared test-free**.
This page states what that declaration is, what it lifts, and what the word
`test_rationale` means in each place it appears.

## The declaration

A test-free declaration is two existing fields on the record, and nothing else:

| Field | Required value |
|---|---|
| `test_required` | exactly `false` (the YAML boolean) |
| `test_rationale` | a string that is non-empty after whitespace is stripped |

Both must hold. The predicate is `is_covers_tag_waived` in
`scripts/ac_store/_done_proof_phase_helpers.py` (BO-2500a-1-ii). It is the one
shared test every layer consults: the static pre-commit scan, the done-proof
oracle, and the CI sweeps. No layer carries its own copy.

| Record state | Result |
|---|---|
| `test_required: false` and a non-empty `test_rationale` | The covering-test rule is lifted: the record is not required to carry a `# covers:` tag. |
| `test_required: false` and `test_rationale` absent, null, empty or whitespace-only | Refused: the record is reported unproven, like a record with no declaration. |
| `test_required: true`, absent or null | Never waived, whatever `test_rationale` says. |

The reason's wording is not judged for quality by the waiver; only its presence
is tested. The waiver lifts the rule that a covering test must exist. It does
not mark anything done by itself.

## The two meanings of `test_rationale`

`test_rationale` is one field with two meanings, which depend on the record
around it. They are separate statements:

1. **With `test_required` false:** it is the reason no test can prove the
   record. It is the reason the waiver above reads.
2. **Alongside a `test_spec`:** it justifies the shape of that test contract,
   that is, why this coverage is right and why a weaker shape (typically a
   direct-import unit test) would not be.

A record with `test_required` true or absent uses meaning 2 only, and the field
stays optional for it. The store schema description of the field in
`config/ac_store_schema.json` states the same two meanings.

## Checks that refuse a reason

| Rule | Record | What it refuses |
|---|---|---|
| Shared waiver predicate (BO-2500a-1-ii) | the done gate | A declaration without a non-empty reason does not waive the covering-test rule at mark-done time. |
| Authoring-side refusal (BO-2500a-8-i) | the commit-time record check, `check-ac-schema` | A record set to `test_required: false` with an absent or blank reason is refused when it is added or changed, at every readiness. This brings the authoring side in line with the done gate. |
| Duplicate-reason refusal (BO-2500a-8-v) | the commit-time record check, `check-ac-schema` | A `test_required: false` record whose reason, once normalised, is identical to another test-free record's reason is refused, naming the record it duplicates. Reasons attached to a `test_spec` are never compared. |

Each rule applies to a record when that record is itself changed. A stored
record that predates a rule is not refused by an unrelated commit.

## Who may carry a declaration

When a declaration is honoured, when it is refused, and which records may carry
one are stated once, in the exemption rulebook
[TQ-400e-6](../acceptance-criteria/testing-quality/TQ-400-durable-done-proof/TQ-400e-6.yaml).
This page does not repeat those conditions; read the rulebook for them.

## What is coming: a typed `verified_by` record

[ADR-076](../architecture/adrs/ADR-076-verification-methods-for-non-test-requirements.md)
decides that a prose reason alone will no longer be enough to prove a test-free
record done. BO-2500f will require a typed `verified_by` record, naming how the
requirement is verified, when the record is marked done. Until it ships, the
two-field declaration above is what the gates read.

## Related

- [AC schema reference](ac-schema.md), the field table.
- [How to prove an AC is done](../how-to/prove-ac-done.md).
- [How proof-of-done enforcement works](../how-to/done-proof-enforcement.md).
- [Phantom-done prevention](../architecture/components/phantom-done-prevention.md).
