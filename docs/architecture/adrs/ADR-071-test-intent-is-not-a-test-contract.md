---
title: "ADR-071: Test Intent Is Not a Test Contract"
description: "The IT PO's per-clause test_intent records only which outcomes need proof and why; the test design (test_spec) is written by the code-aware test-design step, and a leaf code requirement carrying intent alone is held as 'test design pending' everywhere it could be approved, built or committed. The planner cannot see the code, so a test design it writes cannot be trusted."
type: "adr"
status: "active"
created: "2026-10-14"
last_updated: "2026-10-14"
deciders:
  - BrainCandy
  - adr-author
components:
  - ac_driven_dev
  - testing_quality
related_docs:
  - docs/architecture/adrs/ADR-026-ac-driven-build-v2-phased-migration.md
  - docs/architecture/adrs/ADR-009-itpo-no-source-code-access.md
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/architecture/components/ac-driven-dev.md
  - docs/reference/ac-schema.md
  - docs/reference/ac-readiness-and-assignment-gates.md
  - docs/acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent/ACD-2500b.yaml
  - docs/acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent/ACD-2500b-2.yaml
  - docs/acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent/ACD-2500b-3.yaml
related_code:
  - config/ac_store_schema.json
  - templates/agents/it-po.md
  - scripts/ac_store/_impl_readiness_gate.py
  - scripts/ac_store/approve_acs.py
  - scripts/ac_store/_gtfa_tests_section.py
  - scripts/ac_store/_gtfa_cli.py
  - templates/scripts/commit_guardian/_ac_schema_validators.py
---

# ADR-071: Test Intent Is Not a Test Contract

## Status

| Field | Value |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-10-14 |
| **Author** | adr-author (on request from BrainCandy) |
| **Supersedes** | None |

---

## Context

The L0 goal [ACD-2500](../../acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent/ACD-2500.yaml)
("every part of a requirement is written by whoever can actually get it right") splits the
technical planner's (IT PO's) job. Today the IT PO writes the test contract (`test_spec`):
test names, target directories, frameworks, types and angles. It does this without being
allowed to read code or tests
([ADR-009](ADR-009-itpo-no-source-code-access.md)), so the design it writes is not grounded
in the code it is meant to test. The test writer then trusts a design nobody checked
against the code.

[ACD-2500b](../../acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent/ACD-2500b.yaml)
narrows the planner to what it can judge: for each outcome clause it says whether the
clause needs a test and why. That record, `test_intent`, is a list of
`{clause, needs_test, reason}` entries, one per Then/And outcome clause. Test design moves
to the code-aware test-design step (ACD-2500c), which has read the code.

This split opens a gap. A record can now carry intent and no design. If any approval,
build or commit path took intent as "the test contract", the test writer would get less
guidance than today. The ticket generator's per-Then fallback would also quietly invent a
test list for the record, which is the silent path the user brief forbids. The store also
holds a large set of older planner-written `test_spec` records (1,357 on 2026-09-25, 941
of them approved). Those must keep working and must stay distinguishable from new designs.

The decision was worked out in the G3 architect review of
[EPIC-RightJobRightAgent](../../../tickets/00_inbox/epics/EPIC-RightJobRightAgent/Master_Plan.md)
(ticket 20, comment 2026-10-14 09:52, sections 2, 6 and 7). It is recorded for ticket 21
(ACD-2500b-1-i). Groups C, D and E of the epic depend on it. Without a binding record, each
of the four enforcement points (approval, readiness gate, generator, commit check) would
make up its own rule for "intent but no design".

---

## Decision

### 1. test_intent is not a test contract

`test_intent` MUST record only, per outcome clause, the clause text, `needs_test`
(boolean) and a one-sentence `reason`. It MUST NOT carry test names, directories,
frameworks, types, angles, strategy, isolation level or `must_catch`. Its schema in
`config/ac_store_schema.json` is a plain array with closed items (`additionalProperties:
false`, all three keys required) and MUST NOT use `oneOf`.

No gate, check or generator will accept `test_intent` as satisfying the rule "an approved
leaf code requirement carries a test contract" (ACD-1600c-1/-2). That rule is not weakened.
The test contract stays `test_spec` (or `test_required: false` for a prompt- or docs-only
record).

### 2. The IT PO MUST NOT write test_spec

The IT PO (`templates/agents/it-po.md`) MUST write `test_intent` and MUST NOT write
`test_spec`, set `hold_reason`, or raise readiness. The test design (`test_spec`) MUST be
written by the code-aware test-design step (ACD-2500c), which marks its output with the
record-level authorship mark defined in ACD-2500c-3. A record that already carries a
`test_spec` is left untouched by the IT PO and gets no `test_intent`.

### 3. Intent alone is held at every point it could slip through

A leaf code requirement whose `test_intent` is non-empty and whose `test_spec` is absent or
empty (the predicate `design_pending(record)` in `scripts/ac_store/_test_intent.py`) is in
the `test design pending` state. Each enforcement point MUST refuse or hold it, and MUST
use that reason, not `missing test contract`:

| Point | Behaviour |
|---|---|
| Approval step (`scripts/ac_store/approve_acs.py`) | Does not raise the record to `approved`. Reports it under `held` with reason `test design pending`. Writes nothing to the held record. It also holds a record that has a needs-test clause no design entry covers. |
| Implementation-readiness gate (`scripts/ac_store/_impl_readiness_gate.py`) | Returns `test design pending` instead of `missing test contract`. The record is left out of the dispatch set. |
| Ticket generator (`_gtfa_tests_section.py`, `_gtfa_cli.py`) | Raises `TestDesignPendingError`, prints `ERROR: generation refused - AC '<id>': test design pending`, exits 1 and writes nothing. The per-Then fallback MUST NOT run for a record carrying `test_intent`. |
| Commit check (`validate_test_contract` in `templates/scripts/commit_guardian/_ac_schema_validators.py`) | Rejects a staged change that leaves an approved record in this state, naming the file and `test design pending`. |

These points MUST read the field values. They MUST NOT key on AC ids.

### 4. The hold-reason vocabulary is closed and defined once

The only list of hold reasons is `HOLD_REASONS` in `scripts/ac_store/_impl_readiness_gate.py`:
`missing file targets`, `missing test contract`, `test design pending`,
`reference file pending`, `file finding undecided`. A gate that emits a hold reason MUST
import it from there. A module MUST NOT keep a local copy. `implementation_readiness_reasons`
MUST raise `ValueError` for a record `hold_reason` outside `HOLD_REASONS`. The approval
holds MUST assert that every reason they emit is a member. Adding a reason means editing
that tuple and its table in `docs/reference/ac-readiness-and-assignment-gates.md` in the
same change.

### 5. test design pending is always held

`is_held_back` MUST return True for a record whose reasons include `test design pending`,
whatever `enforce` and `schema_version` say. The other reasons keep their current
advisory-below-`schema_version`-2 behaviour.

This is consistent with
[ADR-026](ADR-026-ac-driven-build-v2-phased-migration.md) safety rules 3 ("advisory before
required") and 4 ("tolerant readers: absence of a new field = legacy mode"), and does not
amend them. Those rules protect records written before a new field existed. This reason
can fire only when the new `test_intent` field is present, and only records written after
this change carry that field. So no legacy record can reach it, and a record without the
field is still read in legacy mode as rule 4 requires. Rule 3 still governs the gate as a
whole. Only this reason is exempt from the advisory mode, because releasing it to a
builder would bring back the silent per-Then fallback that section 3 forbids.

### 6. Legacy designs are kept and identified by one predicate

A `test_spec` without the code-aware authorship mark is a **legacy design**. It MUST be
kept unchanged. No bulk migration will rewrite, reclassify, reset or re-ready a legacy
record. A legacy record MUST NOT gain `test_intent` or be flagged `test design pending`.
Its implementation-ready classification is the same before and after this change.

The single predicate is `is_legacy_design(record)` in `scripts/ac_store/_test_intent.py`
(`test_spec` non-empty AND authorship mark absent). The mark is the record field
`test_design_authorship` (`{step, date}`), and each code-aware `test_spec` entry names the
outcome clause it proves in `proves_clause` (ACD-2500c-3). Every consumer (gate, approval step,
by-author query) MUST call it. A consumer MUST NOT re-derive it. A user can send one named legacy
record through the code-aware step. Its `test_spec` is replaced only after the new design
passes the rule check. It then carries the mark and stops being legacy.

---

## Consequences

### Positive

- Test designs are written by a step that has read the code, so the test writer's guidance
  can be trusted (the ACD-2500 outcome).
- One meaning of "intent but no design" covers approval, the queue, the generator and the
  commit. None of the four can quietly turn intent into a made-up test list.
- The closed, single hold-reason list makes a mistyped or invented reason fail loudly
  instead of passing through the gate as an opaque string.
- The schema errors name `test_intent.<n>` and the bad key, because the property is a
  plain array. No hand-rolled validator is needed.
- Legacy records keep building with no store-wide write. Provenance can be queried from day
  one through the missing mark.

### Negative

- Requirements from the new planner cannot be built until the code-aware step (ACD-2500c)
  exists. G3 MUST NOT reach main without group C, or `reviewed` intent records have no
  path to a design.
- `test design pending` departs from the gate's usual advisory mode. This is a deliberate
  but real exception that readers of ADR-026 have to learn about here.
- Two kinds of `test_spec` (legacy and code-aware) live side by side for an open-ended
  period. Consumers that care about provenance must call `is_legacy_design`.
- The plan-feature final gate does not yet run `approve_acs.py` (it asks a status-checker
  agent to edit the YAML). Until that is wired, the readiness gate and the commit check
  are the backstops for the approval rule.

### Operational

- A new rule family `test intent coverage` in the requirement rule check reports missing,
  stale and duplicate intent entries as `needs a decision`. It never repairs them, and it
  evaluates only records that carry `test_intent`.
- Outcome clauses for intent are parsed only by `_test_intent.outcome_clauses` and compared
  through `normalise_clause` (whitespace collapsed, trailing `,` `;` `.` dropped). The
  generator's legacy per-Then fallback is not changed.
- `approve_acs.py --json` prints `{approved: [id], held: [{id, file, reason}]}`. The default
  text output gains one `held <id>: <reason>` line per held record.
- The prose reference for intent, the pending state and legacy treatment is
  `docs/reference/test-intent.md`. `docs/reference/ac-schema.md` carries the field row and
  links to it.

---

## Alternatives

- **Declare test_intent with a schema `oneOf` (or a null branch).** Rejected. jsonschema
  collapses `oneOf` failures into "is not valid under any of the given schemas" and loses
  the failing index and key. That is why `test_spec` needed the hand-rolled
  `_ac_schema_test_spec_validators.py`. A plain closed-items array keeps the errors precise
  in both validators at zero added lines.
- **Let the IT PO keep writing test_spec, with intent added alongside.** Rejected. The IT PO
  cannot read code or tests (ADR-009), so the design stays ungrounded. That is the defect
  ACD-2500 exists to remove. Two authors for one field would also make provenance
  impossible to tell apart.
- **Migrate legacy designs in bulk (reclassify as intent or reset to `reviewed`).**
  Rejected. It would rewrite about 1,357 records and pull 941 approved ones out of the
  buildable queue in one change. That breaks ACD-2500b-3 and ADR-026 rule 4. The missing
  authorship mark already tells legacy records apart, and records can be redesigned one at
  a time on request.

---

## References

- Originating ACs: ACD-2500b, ACD-2500b-1, ACD-2500b-1-i, ACD-2500b-2, ACD-2500b-2-i,
  ACD-2500b-3, ACD-2500b-4 under
  `docs/acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent/`.
- Architect review: `tickets/00_inbox/epics/EPIC-RightJobRightAgent/20_TICKET-20261012-ACD-2500b-1.md`,
  comment 2026-10-14 09:52.
- [ADR-026](ADR-026-ac-driven-build-v2-phased-migration.md) — phased migration safety rules
  (adopted, not amended).
- [ADR-009](ADR-009-itpo-no-source-code-access.md) — the IT PO has no source-code access.
- [ADR-001](ADR-001-self-hosting-boundary.md) — canonical and deployed commit-check copies
  stay in parity through the build.
