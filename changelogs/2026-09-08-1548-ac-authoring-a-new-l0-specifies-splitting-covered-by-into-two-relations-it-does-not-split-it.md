---
title: "AC authoring: a new L0 specifies splitting covered_by into two relations — it does not split it (ACS-1500)"
date: "2026-09-08"
time: "15:48"
type: manual
components:
  - ac_store
summary: "No behaviour changed. Six new draft acceptance criteria were authored specifying how the AC store should stop overloading one field with two different meanings — proving a requirement and describing what it is made of — after measurement showed the current single field cannot be repaired safely."
description: "Adds ACS-1500 (L0) with six L1 drafts (a-f, all readiness: draft) to docs/acceptance-criteria/ac-store/, superseding placeholder ACS-1400d. No code, schema, or store records changed. The problem: covered_by carries two relations — requirement-to-test (leaf) and requirement-to-child (composite) — and done_proof decides leaf-vs-composite from that one field, so repairing a stale link can silently change what the store believes is finishable. Three measured findings drive the spec: (1) 76 records already mix both relations in one list (e.g. BP-1100e-1: seven child ids plus a test path), which the schema permits and which a naive migration would mangle; (2) the two most consequential readers (ac_coverage_resolver.py and an assigned_agent and not covered_by leafness proxy in _ac_schema_validators.py) branch on the field being empty, not on its contents, so splitting the field creates two new states neither reader currently distinguishes; (3) classifying links by whether they resolve has a real counterexample (ACD-300f-5, a child reference to a nonexistent record) that a resolution-based proxy misreads as a test link, which is why the relation must be declared rather than inferred. Migration is explicitly in scope for three of the six L1s (readers, existing records, rollout posture); there is no flag-day option since several readers are pre-commit hooks and required CI gates running from the deployed layout, so the rollout is additive-optional field, dual-read before write-side, advisory gates."
commits:
  - 047b06f20
breaking: false
---

## Entry

### What landed

Six draft acceptance criteria (ACS-1500a through -f) under a new L0, ACS-1500, in the
`ac_store` component's AC store. Nothing else. No production code, no schema change, no
store record was migrated — this entry specifies the work the way an AC-first author does
before a ticket exists, per ADR-012.

### Why it exists

`covered_by` is one field carrying two different relations: a leaf AC points it at test
files that prove the requirement; a composite AC points it at the child ACs it is made of.
`done_proof._has_resolvable_child` uses that single field to decide which kind an AC is —
so appending a child id to a parent that currently holds only test paths changes what the
store believes can be marked done. That coupling is why a population of stale
parent-child links cannot be repaired without risk, and it is the reason ACS-1400c has to
abstain rather than fix them directly.

### Three measured findings

- **76 records already hold both relations in one list.** `BP-1100e-1` carries seven child
  ids alongside a test path. The schema permits the mix, so any migration that assumes each
  `covered_by` list is wholly one kind of link would silently corrupt all 76.
- **The two riskiest readers branch on emptiness, not content.** `ac_coverage_resolver.py`
  and an `assigned_agent and not covered_by` leafness proxy in `_ac_schema_validators.py`
  both treat "no covered_by" as the meaningful signal. Once the relations are split, "no
  parts" and "no proof" become two distinct empty states, and neither reader currently knows
  which one it's looking at.
- **Classifying a link by whether it resolves has a real, data-losing counterexample.**
  `ACD-300f-5` names a child that does not exist. A resolution-based classifier calls it a
  test link; the author plainly meant a child link. Neither proxy (emptiness, resolvability)
  is authoritative — the relation has to be declared at authoring time, not inferred later.

### Scope and rollout posture

Migration is in scope for three of the six L1s (readers, existing records, transition
posture) — the field itself is judged the cheap part. No flag day is available: several
readers of `covered_by` are pre-commit hooks and required CI gates that run from the
deployed layout, so the intended shape is an additive-optional field, dual-read before any
write-side change, and advisory (non-blocking) gates during the transition.

All six L1s are `readiness: draft`. Validated: all 348 AC YAML files remain schema-valid;
the orphan count is unchanged at 47 across 22 parents.
