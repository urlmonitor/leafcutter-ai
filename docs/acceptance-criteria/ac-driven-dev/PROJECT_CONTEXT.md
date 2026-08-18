---
description: Conventions and standing notes for authoring/decomposing ACs in the ac-driven-dev
  component (prefix ACD), including the AC-Driven Build v2 migration ordering.
created: '2026-08-17'
last_updated: '2026-08-17'
type: reference
status: active
title: "ac-driven-dev — AC store context"
components:
  - ac_driven_dev
---
# ac-driven-dev — AC store context

Conventions and standing notes for authoring/decomposing ACs in the
`ac-driven-dev` component (prefix `ACD`). Best-effort knowledge, captured by
authoring agents across runs.

Most of this file exists to stop the next agent re-investigating something that
has already been checked against the code. Where a claim below says
**verified**, someone ran the grep or the probe — treat it as fact. Where it
says **corrects**, an existing note or ADR says the opposite and is wrong.

## The migration: ordering authority

The AC-Driven Build v2 migration spans ACD-1600 / ACD-1700 / ACD-1800 /
ACD-1900 / ACD-2000 and is governed by
`docs/architecture/adrs/ADR-026-ac-driven-build-v2-phased-migration.md`.

**The migration plan is the ordering authority, not the AC numbering.** The two
disagree in at least four places — ACD-1600a is lettered before ACD-1600b but
ships after it; ACD-1600c is lettered after 1600b but must land with or before
it; ACD-1700c is lettered last in its tree but must be built third-from-first.

As of 2026-08-14 the order is **encoded in `depends_on`**, not just described in
prose. Before that date every L1 listed only its parent L0, so a supervisor
batching by `depends_on` saw twelve independent leaves. If you are tempted to
"simplify" a `depends_on` list, read the `amended_by` entry on that file first —
each edge has a recorded reason.

The load-bearing invariant, from ADR-026:

> Read-side before write-side. Every agent **and gate** must dual-read
> (store or ticket-body) BEFORE the ticket is thinned or sign-offs move.

Note ACD-1600b covers the **agent** half and ACD-1900b the **gate** half.
Neither alone satisfies the invariant.

## Roadmap phases

`phase_acbuild_2_cutover` was **split on 2026-08-14** into:

- `phase_acbuild_2a_unit_of_work` — the requirement gains the deliverable
  checklist, per-deliverable sign-offs, and the five gap fields. **The ticket is
  unchanged.** Independently shippable.
- `phase_acbuild_2b_ticket_demotion` — the ticket is thinned and sign-offs move
  off it.

The old id no longer exists in `docs/roadmap.json`. Nothing validates
`roadmap_phase` against the roadmap, so a stale value fails silently rather than
blocking a commit — check the id exists before using it.

## Verified orphans — declared triggers with no AC-side home

Four fields are named by an agent template or runbook as the thing that drives
behaviour, and have **zero occurrences in both `config/ac_store_schema.json` and
`scripts/ac_store/generate_ticket_from_ac.py`**:

| field | named by | consequence |
|---|---|---|
| `declares_side_effect` | generator's own routing (~line 903) | see below — the worst of the four |
| `user_facing_surface` | `config/agent_registry.json` (~2597) as the legacy `user-surface-smoker` trigger | second orphaned trigger for the same agent |
| `live_surface_test` | `live-surface-tester` (registry ~2663) | the agent exists and is registered; nothing can request it |
| `test_failure_rework_cap` | `building-epics/SKILL.md` §4 (~784), "configurable per-ticket via ticket frontmatter" | the cap cannot actually be overridden |

**`declares_side_effect` is the sharpest case, and an earlier analysis got it
backwards.** It was claimed to exist at `ac_store_schema.json:637`; line 637 is
`product_truth`, and the field has zero occurrences in the schema and zero ACs
carrying it. Because the schema sets top-level `additionalProperties: false`, it
**cannot legally be authored on an AC at all**. The generator's routing at ~903
(`if declares_side_effect: all_needed.add("user-surface-smoker")`) and its
non-overridable enforcement at ~920 are live but dead-ended.

Compounding it: `generate_ticket_from_ac.py` contains **zero** occurrences of
`Smoke Fixture` or `actuation_contract`, while `user-surface-smoker` reads its
assertions from a `## Smoke Fixture` ticket-body block. Its algorithm is "for
each stanza in the block" — with no block, the loop body never executes and the
gate passes vacuously. Same failure shape as the BO-2900 tree: a check that
never ran, read as a check that passed.

Any AC giving these a home must deliver the **declaration slot** as well as the
**content**, and the three smoker/tester triggers should share one mechanism
rather than spawning a third.

## Schema enforcement — corrects ACD-1900a's notes

`additionalProperties: false` (schema line 15) **is enforced today.**
ACD-1900a's notes say the schema declares it but nothing enforces it and the
validator docstring is wrong. That was true before the ACS-200e fix; it is not
true now. Verified empirically — a probe AC carrying an unknown field, run
through `scripts/ac_store/validate_ac_schema.py` (which uses
`jsonschema.Draft7Validator`, ~line 152):

```
schema violation at <root> — Additional properties are not allowed
('declares_side_effect' was unexpected)
```

exit 1. The commit hook `scripts/commit_guardian/check_ac_schema.py` uses the
same mechanism.

**Consequence for sequencing:** ACD-1900a is a **hard gate** on every write-side
item, not a compatibility nicety. Any AC authored with a new field before its
optional slot exists is rejected at commit time.

## done_proof is NOT at risk from thinning — corrects ADR-026

ADR-026's Context lists "done_proof losing its evidence anchors" as one of three
phantom-green hazards. Verified false: `scripts/ac_store/done_proof.py` contains
no ticket reference, and
`verify_done_eligible(ac_id, *, ac_root, test_root)` anchors on the AC store and
on `# covers:` tags in tests — neither of which a thin ticket touches.

It is the **reference design** for AC-anchored evidence and ACD-1800b's
per-deliverable sign-off should extend its model rather than invent a parallel
one. Do not spend migration effort defending it. The other two hazards in that
list are real and confirmed:

- `ac-fulfillment-gate` (`templates/agents/ac-fulfillment-gate.md`, Step 1)
  signs off `(status: ok)` immediately and reads no YAML when `ac_traceability`
  is absent.
- `ac-validator` sources its AC Coverage table, Agent Contracts, and sign-offs
  from the **ticket body** that ACD-1600a-2 removes — it then finds an empty
  table and reports zero unmet criteria.

A third, `check_ticket_signoff_parity`, requires a `## Sign-offs` section and so
fails **loud** (blocks every commit) rather than silent. Classify it separately;
a stalled repo is a different risk from a false green.

## Validator and hook gotchas

- `scripts/ac_store/validate_ac_schema.py` **silently passes a directory
  argument** — `No YAML files to validate.` with exit 0. Always pass an explicit
  glob (`<folder>/*.yaml`). CLAUDE.md's bulk pre-flight snippet uses the
  directory form and is therefore a no-op as written. Tracked at ACS-1100a-2.
- Child caps (`scripts/commit_guardian/check_ac_limits.py`): 7 L1 per L0, 5 L2
  per L1, tested as `child_count > limit`. As of 2026-08-14 **ACD-1600 and
  ACD-1900 are full at 7**; ACD-1800 is at 6.
- `depends_on`, `criteria`, `title`, `req_status` are **write-locked** by
  `check_ac_governance.py`. Authorized writers: `product-owner`,
  `business-analyst`, `it-po`, and any human identity.
- Parent `covered_by` must list every child id or
  `check_ac_parent_covered_by.py` blocks the commit.

## Cross-tree hazards flagged for the BA

- **Product-truth is a derived back-reference, not an authored one.** The
  `product_truth` field (schema ~648) is tool-owned, generated by
  `generate_product_truth.py` as the inversion of flow steps whose `implements`
  names the AC. The flow's `impl_status` derives from the AC's `work_status`.
  Adding `flow` as a plain deliverable kind therefore creates a **status cycle**.
  A declared product-truth deliverable needs its own authored field, with the
  derived one serving as its evidence.
- **Exclusions do not compose by union** (ACD-1600g). One member's
  `out_of_scope` is routinely another member's `files_touched` — that is what a
  bundle is for. The composition rule is a difference: out of scope for the
  bundle only when some member excludes it AND no member's `files_touched` names
  it. A naive union produces false blockers on every bundle.
- **`_update_ac_work_status()`** in `scripts/build_orchestration/fast_lane.py`
  (~113-125) does a full `yaml.safe_load` → `yaml.safe_dump` rewrite of the
  entire AC record on every claim and release. Any append-only trail added by
  ACD-2000a is round-tripped through that on every ACD-2000b claim.
- **The existing claim is not atomic** (`fast_lane.py` ~181/193/203) — a
  read-check-write with no owner and no timestamp, released only on graceful
  exit. ACD-2000b's "never stuck as someone else's" promise is not satisfied by
  the current release-on-failure path.
- **The fast lane will regress when ACD-1800b lands.**
  `fast_lane.mark_done_built_acs()` marks ACs done on test coverage alone. Once
  done means all-deliverables-signed, that becomes a phantom-done regression
  introduced by the migration itself, in the tool with the strongest done proof
  in the repo.

## Framing preference (user: BrainCandy)

- User-authored ACs set `origin_agent: BrainCandy`; BA-created ACs set
  `origin_agent: business-analyst`.
- New L0/L1 ACs are written `priority: medium`, `readiness: draft`; priority and
  readiness are finalised at the workflow's final gate, not at authoring time.
- L1 `criteria` is customer-benefit language with no engineering jargon. The
  technical findings, hazards, and verified code references go in `notes`, where
  the BA and IT PO read them.
