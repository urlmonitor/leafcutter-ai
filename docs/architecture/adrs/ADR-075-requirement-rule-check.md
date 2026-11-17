---
title: "ADR-075: Mechanical Requirement Rules Are Checked by One Fail-Closed Rule Check"
description: "Requirement rules with one right answer are judged by one rule check made of rule families, run as a fail-closed gate after every /plan-feature authoring stage, repairing only through a guarded writer and only with a usable before-state. An agent's memory of a rule, or its own report of a stage, cannot be trusted to hold a requirement record to that rule."
type: "adr"
status: "active"
created: "2026-10-21"
last_updated: "2026-10-21"
deciders:
  - BrainCandy
  - adr-author
components:
  - ac_store
  - ac_driven_dev
related_docs:
  - docs/reference/requirement-rule-check.md
  - docs/architecture/adrs/ADR-072-code-aware-test-designer-may-read-source.md
  - docs/architecture/adrs/ADR-071-test-intent-is-not-a-test-contract.md
  - docs/architecture/components/ac-driven-dev.md
  - docs/architecture/diagrams/c3-030-requirement-rule-check-components.md
  - docs/reference/ac-readiness-and-assignment-gates.md
  - docs/acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent/ACD-2500a-5-i.yaml
related_code:
  - scripts/ac_store/requirement_rule_check.py
  - scripts/ac_store/_rc_edit.py
  - scripts/ac_store/_rc_changed.py
  - scripts/ac_store/_rc_records.py
  - scripts/ac_store/_rc_report.py
  - scripts/ac_store/_rc_readiness.py
  - scripts/ac_store/_rc_declared.py
  - scripts/ac_store/_rc_protected_fields.py
  - scripts/ac_store/assignment_quality.py
  - scripts/ac_store/_impl_readiness_gate.py
  - scripts/ac_store/_approval_holds.py
  - scripts/build_phases_ac_store_rc.py
  - config/surface_craft_map.yaml
  - templates/workflows-js/plan-feature.js
---

# ADR-075: Mechanical Requirement Rules Are Checked by One Fail-Closed Rule Check

## Status

| Field | Value |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-10-21 |
| **Author** | adr-author (ticket `06_TICKET-20261021-ACD-2500a-5-i`, EPIC-RightJobRightAgentFollowUps) |
| **Supersedes** | None |

---

## Context

The L0 goal ACD-2500 ("every part of a requirement is written by whoever can actually get
it right") moved the planning rules that have exactly one right answer out of agent
instructions and into a script: the requirement rule check, built under ACD-2500a-1,
ACD-2500a-2 and ACD-2500a-3 and extended by ACD-2500a-2-vi, -vii and -viii. This record
is written under
[ACD-2500a-5-i](../../acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent/ACD-2500a-5-i.yaml).
What the check reports and how each rule family judges a record are in the
[requirement rule check reference](../../reference/requirement-rule-check.md). This ADR
records why it is built this way and does not repeat that reference.

Before the check, the rules lived in prose that an authoring agent had to remember:
add the child to the parent's `covered_by`, fill `components`, never raise `readiness`
to `approved`, keep producer and consumer contracts in step, assign the specialist the
file surface calls for. `/plan-feature` then took the stage agent's word that the stage
was done. Each rule broke in practice:

- A rule an agent forgets is not reported by anyone. The miss shows up later, at commit
  time or at build time, far from the stage that caused it.
- A stage report written by the agent can be wrong. The agent may skip the check, run it
  on the wrong folder, or describe a failed run as clean.
- A repair written by an agent, or by a load-and-dump of the YAML, can change fields
  nobody asked it to change.
- A check fed the agent's own list of written ids read a mistyped list as all clear, and
  a parent the check repaired was never committed.
- A repairing run without a before-state treated every record as new and reset approved
  records to `draft` (KI-ACS-20261015, fixed by ACD-2500a-2-viii).
- Once the code-aware test designer of
  [ADR-072](ADR-072-code-aware-test-designer-may-read-source.md) and the technical
  planner's hand-back pass edit records that already exist, only prose in
  `templates/agents/test-designer.md` stopped them from changing fields they do not own.

Leaving this undecided costs twice. Each new rule would invent its own place and output,
and the workflow's signal that a stage is complete would stay in agent prose.

---

## Decision

### 1. One rule check made of rule families

Every mechanical requirement rule MUST be judged by one script,
`scripts/ac_store/requirement_rule_check.py`. Each rule is a rule family in its own
`scripts/ac_store/_rc_<name>.py` module, registered once in that script's `FAMILIES`
list and in `AC_STORE_DEPLOY_MAP` (`scripts/build_phases_ac_store_rc.py`).

- A family MUST be a pure `evaluate_record(ctx, record)` that returns findings. It MUST
  NOT write.
- All families MUST report through one finding record and one report. The report format
  and the registration steps are in the
  [reference](../../reference/requirement-rule-check.md).
- A rule the store's record check already enforces (`validate_ac_schema._validate_file`)
  MUST be reached by calling that check, never by writing it a second time. There MUST be
  at most one finding per rule and subject.

### 2. A fail-closed gate after every authoring stage

`/plan-feature` (`runRuleCheck` in `templates/workflows-js/plan-feature.js`) MUST run the
check after each authoring stage and before that stage's user gate. A stage MUST NOT be
reported complete unless the exit code is `0`, the verdict is `passed` and
`records_checked` is above zero. The workflow reads the exit code and the JSON report,
never the stage agent's prose.

The script MUST fail closed. Every inconclusive path MUST end in a `failed` finding,
never a silent pass: zero records, an unreadable record, a family that raises or returns
something other than a finding, an unreadable rule source, an unknown `--stage`, a git
failure. A failed check MUST send its findings back to the stage agent as edit feedback,
even when the user chose `approve`.

### 3. Repair only where one answer exists, through a guarded writer, with a before-state

1. A family MUST propose a repair only where exactly one right value exists. Today that
   is the parent back-link (`covered_by`), a single derivable graph component
   (`components`), and restoring an agent-raised `readiness`. Every other violation
   MUST be `needs a decision`.
2. `scripts/ac_store/_rc_edit.py` MUST be the only writer. It MUST refuse any field
   outside `REPAIRABLE_FIELDS = {covered_by, components, readiness}`
   (`ProtectedFieldError`). It MUST edit text in place, never by load-and-dump. It MUST
   replace the file only after proving that the old and new YAML differ in the target
   key alone and that the key holds the intended value.
3. The orchestrator MUST evaluate again after it repairs: evaluate, apply repairs,
   reload the written records, evaluate again. A repair the writer refused, or a
   violation still present on the second pass, MUST be `failed`.
4. Repairs MUST be applied only when the run has a usable before-state (`--before-ref`
   or `--before-snapshot`). A run with no usable before-state MUST write nothing. That
   covers no before-state given, a ref that does not resolve, and a snapshot that cannot
   be read (`Context.has_before_state` is the one test). In that run every proposed
   repair MUST be reported as `needs a decision` naming the change it would have made,
   and the readiness and protected-field families MUST list each record as
   `not evaluated: no before-state`. The report MUST say whether a before-state was
   given and whether repairs were applied. An authoring-stage run without a usable
   before-state MUST also carry a `failed` finding, so the gate still fails.

### 4. `--changed-since` finds the records itself

The check MUST be able to take its scope from git: `--changed-since REV` checks every
record file under the store that is modified, added or untracked against `REV`
(`_rc_changed.py`). The report MUST then list `records_to_commit`, which includes
parents the check repaired. `/plan-feature` MUST use this mode and stage those files
with the stage commit. Nothing changed, or a git failure, MUST be `failed`.

### 5. `config/surface_craft_map.yaml` is the one surface-to-specialist authority

Which specialist owns a file surface MUST be read only from `config/surface_craft_map.yaml`
through `assignment_quality.load_map` / `resolve_craft_in`. The `specialist versus
surface` family MUST NOT hold a second file-type table. A path the map does not cover
MUST be `not evaluated`, never a mismatch. An unreadable map MUST be `failed`.

### 6. `HOLD_REASONS` is the one hold-reason vocabulary

`HOLD_REASONS` in `scripts/ac_store/_impl_readiness_gate.py` MUST be the only list of
reasons a record can be held from approval or dispatch. Every gate that emits a hold
reason MUST read it and MUST NOT keep a local list. `_approval_holds.py` MUST raise on a
reason outside it. A state that is a hold (for example `file finding undecided`) MUST be
reported as that hold and MUST NOT also be raised as a rule-check finding.

### 7. The protected-field family is the backstop for fields a stage does not own

The `protected fields` family (`scripts/ac_store/_rc_protected_fields.py`) MUST compare,
for every record that existed at stage start, each field in `PROTECTED_FIELDS` and
`DESIGN_OUTPUT_FIELDS` against the record committed at the before-ref.

- Which fields a stage may change MUST be read from one table, `OWNER_MAP`. Changing
  what one stage may change MUST be one edit to that table.
- `test-design` owns the test designer's outputs.
- `itpo-handback`, the technical planner's hand-back pass, owns `assigned_agent`, each
  file finding's `decision`, `it_requirements`, `declared_files`, `delivers_to` and
  `expects_from`, per the user decision of 2026-10-20 (ACD-2500a-2-vii).
- Any other change to a compared field MUST be `needs a decision`, one per field, naming
  the stage. The family MUST NOT repair.
- A stage the owner map does not list (`po`, `ba`, `itpo`, `approval`, which own these
  fields) MUST be `not evaluated`, never failed. The same applies to a record created
  during the stage, a readiness-only snapshot and a run with no before-state.
- A `covered_by` entry the check's own back-link repair added in the same run MUST NOT
  count as the stage's change.

---

## Consequences

### Positive

- A forgotten rule is reported at the stage that broke it, by file, record and family.
  It no longer surfaces at commit or build time.
- A stage is complete only by exit code and report, so an agent cannot report its way
  past the gate.
- No bug in a family can write a field outside the three repairable ones, or change any
  byte outside the target key.
- A by-hand run without a before-state is safe: it reports what it would repair and
  changes nothing.
- The surface map, the hold reasons and the per-stage owner map each have one place to
  edit. Adding a rule is one module plus two registrations.

### Negative

- Any check failure, including a git or rule-source problem unrelated to the stage's
  work, blocks the stage until it is fixed or the edit-retry limit returns an error.
- The protected-field family needs a git before-ref. With a readiness-only snapshot it
  is `not evaluated`, so a snapshot-driven run has no field backstop.
- Contract symmetry is checked for presence only. Whether two contract texts agree stays
  with the technical planner.
- Rules that only the commit hooks run (test contract, side effect, pattern bindings) are
  not repeated by the check, so a stage can pass and the commit still fail.

### Operational

- The reference doc must be kept in step with the code. A new family, stage or
  disposition is documented there, not here.
- The check and every `_rc_*.py` module deploy flat into `<root>/scripts/ac_store/`. A
  module missing from `AC_STORE_DEPLOY_MAP` breaks the consumer copy.
- Callers running the check by hand on an authoring stage must pass `--before-ref` or
  `--before-snapshot` if they want repairs applied.

---

## Alternatives

- **Keep the rules as instructions the authoring agents must remember** (for decision 1).
  Rejected. A forgotten instruction produces no signal at all. Each agent template would
  carry its own copy of every rule, and the copies drift apart.
- **Let the stage agent run the check and report the result** (decision 2). Rejected. The
  workflow would still read prose. An agent that skips the run, checks the wrong folder,
  or summarises a failed report as clean would advance the stage.
- **Repair every violation the check can name, or repair without a before-state**
  (decision 3). Rejected. Where more than one value is plausible, a repair is a guess
  written into a requirement. Without a before-state every record looks new, and the
  readiness repair reset approved records to `draft` (KI-ACS-20261015).
- **Check the ids the stage agent says it wrote** (decision 4). Rejected. A mistyped or
  incomplete list reads as all clear. A parent the check repaired is not in the list, so
  it was never committed.
- **Give the rule check its own file-type-to-specialist table** (decision 5). Rejected.
  It would drift from `config/surface_craft_map.yaml`, which the assignment-quality check
  already reads. The two checks would then disagree on the same path.
- **Let each gate keep its own hold-reason list, or report holds as rule-check findings**
  (decision 6). Rejected. Two lists drift, and a reason one gate emits becomes unknown
  to another. A hold reported a second time as a finding is counted twice and blocks a
  stage that is only waiting for a person.
- **Rely on the prose in `test-designer.md` and the commit-time governance hook**
  (decision 7). Rejected. Prose is the memory the check replaces. `check_ac_governance`
  protects only `criteria`, `title`, `req_status` and `depends_on`, and it runs at
  commit. It does not know which stage made a change or which fields that stage owns.
  Reverting the change automatically was also rejected: whether the stage or the
  committed value is right is a decision for a person.

---

## References

- [Requirement rule check reference](../../reference/requirement-rule-check.md): CLI,
  report, dispositions, family criteria, fail-closed paths, family registration.
- [ADR-072](ADR-072-code-aware-test-designer-may-read-source.md): the test designer whose
  edits the protected-field family guards.
- [ADR-071](ADR-071-test-intent-is-not-a-test-contract.md): test intent versus the test
  contract, judged by the test intent and test design families.
- [AC readiness and assignment gates](../../reference/ac-readiness-and-assignment-gates.md):
  the surface map and `HOLD_REASONS`.
- [c3-030 requirement rule check components](../diagrams/c3-030-requirement-rule-check-components.md).
