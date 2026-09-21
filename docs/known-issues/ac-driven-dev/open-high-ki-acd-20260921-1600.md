---
title: "KI-ACD-20260921-1600 — An AC with no `risk_surface` generates a ticket with no `ac-validator` and no `ac-fulfillment-gate`, and the store validator passes it"
description: "high — every ticket generated from such a record ships without the two phases that verify the AC was satisfied"
type: reference
category: reference
status: active
created: '2026-09-21'
last_updated: '2026-09-21'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACD-20260921-1600 — An AC with no `risk_surface` generates a ticket with no `ac-validator` and no `ac-fulfillment-gate`, and the store validator passes it

- **Severity:** high — the silent half is a phantom-done vector: the generated ticket
  omits precisely the two phases that verify the AC was satisfied before commit
- **Status:** open
- **Occurrences:** 1 (2026-09-21, BO-4100 — all 33 records)
- **First seen:** 2026-09-21 · **Last seen:** 2026-09-21
- **Where:** `scripts/ac_store/generate_ticket_from_ac.py` — the branch that selects the
  computed-gates path over the legacy path, gated on `risk_surface` being present;
  `config/guardrail_gates.yaml` for the value-to-agent mapping;
  `config/ac_store_schema.json`, which does not require the field

## Symptom

`risk_surface` is optional in the AC schema and required in ticket frontmatter. The
mismatch has a loud half and a silent half, and only the loud half has been recorded
before (see KI-ACD-012 and KI-ACD-20260914-0657, which cover the same field going missing
from `goal_to_epic.py`'s `Master_Plan.md`).

**Loud half.** `ticket_frontmatter_guard` rejects the generated ticket with
`Missing required field: 'risk_surface'`. Annoying, visible, hand-patchable.

**Silent half — the reason this is filed separately.** The field's *presence* is what
switches `generate_ticket_from_ac.py` from its legacy path to the computed-gates path.
Without it the ticket is still produced, and it is materially weaker. Measured on
`BO-4100d-1`, same AC, regenerated before and after adding `risk_surface: contract_boundary`:

| agent | no `risk_surface` | with `risk_surface` |
|---|---|---|
| `ac-validator` | absent | **needed** |
| `ac-fulfillment-gate` | absent | **needed** |
| `architect-review` | absent | needed |
| `documentation-expert` | `not_needed` | needed |
| `documentation-verifier` | absent | needed |
| total entries | 8 | 14 |

`ac-validator` and `ac-fulfillment-gate` are the phases that check an AC was actually
satisfied before the commit phase locks the worktree. A ticket generated from a record
with no `risk_surface` therefore reaches `commit` with nothing having verified its own
acceptance criterion — while looking like an ordinary, complete ticket.

## Why nothing catches it

`validate_ac_schema.py` passed all 33 BO-4100 records with the field absent from every
one. The store validator cannot see the problem because the field is genuinely optional
at the schema layer; the ticket guard can see it but only fires after generation, on a
file the author then hand-patches. Neither layer reports the agents-map consequence at
all — it is invisible in both directions.

This is the same shape as KI-ACS-20260909 (`validate_ac_schema.py` passes records the
commit hook then rejects): a clean bulk validation run is not evidence about every field.

## Reproduction

1. Author a code AC with `readiness: approved` and no `risk_surface`.
2. `validate_ac_schema.py <file>` — passes.
3. `generate_ticket_from_ac.py --ac <id> --verify` — READY, no warning about the field.
4. Generate. Inspect the `agents:` block: no `ac-validator`, no `ac-fulfillment-gate`.
5. Add `risk_surface`, regenerate, diff the `agents:` block.

## Note for whoever fixes it

`internal` is not the safe default it reads as. It is the only value that does **not**
summon `architect-review` and `pr-reviewer`, so a blanket `internal` backfill across the
store would silently strip `pr-reviewer` from every ticket it touched. The remaining
values are near-identical in gate effect for `change_target: code`, except `cost`, which
suppresses `documentation-expert`.

A second-order consequence worth knowing before fixing: once `risk_surface` moves a ticket
onto the computed-gates path, the `pull-request` phase's deferral becomes
location-dependent, and the generator then refuses without `--location-kind` and
`--resolved-destination` rather than guessing. That refusal is correct, but it means
adding the field changes the generator's required arguments.

## Suggested direction (not a decision)

Either make `risk_surface` required by `config/ac_store_schema.json` so the store
validator catches it at authoring time, or make the generator fail closed when the field
is absent rather than silently taking the legacy path. The current arrangement — optional
upstream, required downstream, and load-bearing in between — is the part that makes the
failure invisible.
