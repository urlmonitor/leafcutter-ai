---
title: Project Roadmap
type: reference
status: active
created: 2026-09-08
last_updated: 2026-09-08
components:
- infrastructure
description: Overview of Project Roadmap.
---
<!-- AUTO-GENERATED — do not edit by hand. Source: docs/roadmap.json -->
<!-- Regenerate manually: python portable-dev-workflow/scripts/commit_guardian/regenerate_roadmap_mirror.py --manual -->
<!-- Generated: 2026-09-08T14:04:16Z -->

# Project Roadmap

> **Source of truth**: `docs/roadmap.json`  
> To update the roadmap, edit `docs/roadmap.json` and commit — this file regenerates automatically.

## Current Focus

**Current Phase**: `phase_1`
**Current Outcome**: Stable MVP that installs into any project and helps the user build good software — portable, self-onboarding, and reliable enough to use across multiple repos.

## Phases

| Phase | Title | Status |
|-------|-------|--------|
| `phase_1` | Stable Portable MVP | **ACTIVE** ← current |
| `phase_acbuild_1_foundation` | AC-Driven Build v2 — Foundation & Read-Side | Planned |
| `phase_acbuild_2a_unit_of_work` | AC-Driven Build v2 — The Requirement Becomes the Unit of Work | Planned |
| `phase_acbuild_2b_ticket_demotion` | AC-Driven Build v2 — Ticket Demoted to a Grouping Container (dogfooded) | Planned |
| `phase_acbuild_3_migration` | AC-Driven Build v2 — Consumer Migration & Legacy Removal | Planned |
| `phase_store_record_health` | Store-Record Health — the store's own claims are true | Planned |
| `phase_2` | Ecosystem Hardening | Planned |
| `phase_3` | Distribution and Community | Planned |

## Phase Details

### phase_1: Stable Portable MVP (Current)

**Status**: **ACTIVE**

A reliable package that installs into any project via build.py, self-onboards the user via interactive config, and produces correct agents/skills/hooks without manual fixup.

**Exit Criteria**:

- Clean install succeeds on a blank project with only skills_config.json present
- build.py --validate-only returns 0 with no template injection errors
- Consecutive builds produce zero git diff (idempotent)
- The self-host build leaves the repository clean and reports truthfully: no unrequested edits to tracked files, no orphaned artifacts, no false all-clear

### phase_acbuild_1_foundation: AC-Driven Build v2 — Foundation & Read-Side

**Status**: Planned

Make the AC store the single source of truth WITHOUT changing behaviour. Additive-only: optional deliverable-checklist and per-deliverable sign-off fields plus a per-AC schema_version in ac_store_schema.json; a productionised effective-prompt render tool; canonical-source path resolution; and universal agent/gate dual-read (store-or-ticket-body). All new gates run advisory/warn-mode behind a two-stage ac_unit_of_work flag ({emit:false, enforce:false}). Read-side lands before any write-side change so the build can never go green while verifying nothing.

**Exit Criteria**:

- New AC fields are OPTIONAL in ac_store_schema.json; schema_version present (default 1); whole-store validation passes on both legacy and new shapes. The schema must declare the OPTIONAL slots for every field phase 2a will author — deliverable checklist, per-deliverable sign-offs, scope boundary (out_of_scope), observable-behaviour proof, adjudication trail, and the product-truth deliverable. additionalProperties:false is ENFORCED today via jsonschema.Draft7Validator in both scripts/ac_store/validate_ac_schema.py and the commit hook, so any field authored before its slot exists is rejected at commit. This criterion is a hard gate on all write-side work (ACD-1900a).
- render_effective_prompt.py productionised and in the build deploy-manifest; a fresh agent rendered purely from the store passes the comprehension test (ACD-1700c)
- Dual-read is verified BEHAVIOURALLY on the three gates that actually degrade, each named: ac-fulfillment-gate (today signs off status:ok and reads no YAML when ac_traceability is absent), ac-validator (today sources AC Coverage, Agent Contracts and sign-offs from the ticket body that ACD-1600a-2 deletes), and check_ticket_signoff_parity (today requires a ## Sign-offs section). Evidence must be a real on-disk thin ticket driven through each gate in a fresh process — per CLAUDE.md 'Gate / Workflow ACs — Verify Behaviorally, Not by Grep', a grep for dual-read prose in an agent template is NOT evidence. Enrichment / canonical-path / surface-to-craft / consistency gates run in warn mode (ACD-1900b, ACD-1600b/c/d).
- Each agent's brief is scoped to its role and the exclusion is demonstrated, not asserted — a rendered coder brief contains no requirement-authoring or supervisor-checklist content (ACD-1700a, ACD-1700b)
- No required CI gate references a new field; ac_unit_of_work flag introduced with a documented one-commit kill-switch (ACD-1900c, ACD-1900d)

### phase_acbuild_2a_unit_of_work: AC-Driven Build v2 — The Requirement Becomes the Unit of Work

**Status**: Planned

Move the truth onto the requirement WITHOUT touching the ticket. Each AC gains a deliverable checklist naming every artifact it needs and the craft responsible, per-deliverable sign-offs recorded ON THE AC, and the five fields the gap analysis found homeless: scope boundary, observable-behaviour proof, adjudication trail, parallel-safety claim, and the product-truth deliverable. Sign-offs are DUAL-recorded (AC and ticket) in this phase — nothing is removed. This is the half of the migration that delivers the actual value the user asked for ('ACs need to store which items need to be there to say the AC is done'), and it is independently shippable: if 2b is deferred, 2a still stands on its own.

**Exit Criteria**:

- Every requirement carries a deliverable checklist naming each artifact's kind and responsible craft, validated against the requirement's change surface; a requirement that needs docs or a diagram and omits them is flagged incomplete, naming each missing kind (ACD-1800a)
- Per-deliverable sign-offs are recorded on the requirement; requirement-level done is computed solely from them; a deliverable that does not apply is recorded explicitly as not-applicable, never silently dropped (ACD-1800b). Sign-offs are DUAL-recorded on AC and ticket in this phase — the move to AC-only is 2b.
- The five gap fields land, each with its consumer still working: scope boundary (ACD-1600g — note exclusions compose by DIFFERENCE not union, or the bundle produces false blockers), observable-behaviour proof (ACD-1800f), adjudication trail and parallel-safety claim (ACD-2000), and the product-truth deliverable as a DECLARED field whose evidence is the existing derived product_truth back-reference — declaring it as a plain deliverable kind creates a status cycle, because the flow already derives impl_status from the AC's work_status
- The fast lane refuses any requirement whose checklist declares a deliverable it cannot produce. Without this, fast_lane.mark_done_built_acs() keeps marking ACs done on test coverage alone once ACD-1800b redefines done as all-deliverables-signed — a phantom-done regression introduced BY the migration, in the tool with the strongest done-proof in the repo.
- THE TICKET IS UNCHANGED. No thinning, no sign-off removal, no gate flips. Any of those belong to 2b.

### phase_acbuild_2b_ticket_demotion: AC-Driven Build v2 — Ticket Demoted to a Grouping Container (dogfooded)

**Status**: Planned

Now that the requirement carries the truth, thin the ticket. The generator emits thin tickets that reference their AC instead of copying it; sign-offs move off the ticket body in a single atomic cutover behind ac_unit_of_work.emit; the ticket becomes a grouping container that bundles requirements into one valuable feature and is done when they are. Dogfooded on leafcutter itself before any consumer sees it. Split from 2a because ADR-026 provides two independent flag stages (emit, enforce) and the roadmap should mirror them — 2a has no observable midpoint otherwise.

**Exit Criteria**:

- Generator emits thin tickets behind ac_unit_of_work.emit; sign-offs move from dual-recorded to AC-only in one atomic change (ACD-1600a, ACD-1800c). ACD-1600a must not land before ACD-1900b-5: thinning ahead of fulfillment-gate dual-read fails QUIETLY, not loudly — the gate returns status:ok having read nothing.
- check_ticket_signoff_parity reconciled with a ticket that has no ## Sign-offs section (ACD-1800c-5). Unlike the gates above this one fails LOUD — it blocks every commit — so it is a stalled-repo risk, not a phantom-green one.
- A full self-host epic built end-to-end thin + AC-sign-off, behaviorally spot-checked on a real on-disk ticket in a fresh process (ACD-1900g)
- Store backfilled to 100% (strict schema validation = 0 errors); already-done ACs grandfathered, not regressed
- ac-fulfillment-gate flips 'absent ac_traceability -> blocker' and any new done-accounting gate is promoted to required (diff-scoped) only after >=10 consecutive green self-host merges (ACD-1900c-6)
- Legacy residue closed by name, not by family: ACD-400b.yaml is already status superseded_by, but ACD-400b-4 remains active/todo carrying the sign-offs-in-ticket clause, and inbox tickets TICKET-20260813-ACD-400b-6 and -7 are actively building the old wired-ticket model. Supersede the first and triage the other two before 2a starts.

### phase_acbuild_3_migration: AC-Driven Build v2 — Consumer Migration & Legacy Removal

**Status**: Planned

Bring existing consumers across safely, then retire the old path. build.py deploys the new artifacts (all hook deps in the deploy-manifest) and warns/refuses on schema_version skew; consumers run an opt-in, idempotent backfill; dual-readers remain for >=2 minor releases while in-flight fat tickets drain; only then are fat-ticket generation and the legacy-derive path removed.

**Exit Criteria**:

- build.py deploys new hooks with all deps in the deploy-manifest and warns/refuses on schema_version skew
- Opt-in idempotent backfill ships (dry-run, --ac-store-dir, preserves notes blocks); >=1 consumer (or consumer-sim) migrated green
- Dual-readers retained >=2 minor releases; in-flight fat tickets allowed to drain; legacy fat-ticket generation and dual-read/derive removed in a dedicated release with one full green cycle
- Rollback rehearsed: ac_unit_of_work.enforce=false restores green within one commit

### phase_store_record_health: Store-Record Health — the store's own claims are true

**Status**: Planned

The AC store is the source of truth every gate reads, so a false record is a false gate. Four trees that share one subject and had no phase to belong to: ACS-1200 (a deliberately parked tree is a recognised state, not a rule to skip), ACS-1300 (the requirement-to-test link is trustworthy in both directions), ACS-1400 (a composite's done-claim is judged against the children that actually exist), and ACS-1500 (those last two are the same overloaded field, and the relation must be declared rather than inferred). None of these advance phase 1's install/idempotency exit criteria, which is why ACS-1200 and ACS-1300 left themselves unphased rather than claim a phase that did not fit — this phase is that missing home. Sequencing inside it is real and load-bearing: ACS-1500a must precede ACS-1400c's adjudication of the population it cannot safely touch, and ACS-1200a must precede ACS-1400a because the strengthened back-link rule fires against parked trees the exemption has not yet protected.

**Exit Criteria**:

- A parked tree is recognised by a positive deliberate signal rather than by the absence of children, and every health surface that infers breakage from a missing link agrees with it (ACS-1200). Absence-keyed exemptions are disqualifying: absence is also what a half-broken tree looks like.
- The requirement-to-test link is repaired in both directions of rot and stays repaired for records that never pass through the ticket pipeline (ACS-1300). Nothing in that tree writes work_status at any level — restoring an evidence link and awarding a done badge are two acts.
- The parent-to-child link is complete, and the commit-time guard's silence means exactly one thing (ACS-1400). Today it has three escape hatches and 26 of 47 known orphans are exempted by an undocumented one, so a green hook is not evidence the link was checked.
- 'Done' is explicitly NOT zero orphans: a store reporting labelled deliberate exclusions is healthy, and any criterion binding success to zero forces the six KM-200 repairs that must never happen.
- The coverage field expresses which relation each entry means, every reader asks for the relation it intends, and the ~76 records already holding both relations in one list carry their meaning across (ACS-1500). No flag day is available — several readers are pre-commit hooks and required CI gates running from the deployed layout — so staged rollout with a one-commit kill-switch is a criterion, not a preference.
- Every safety guarantee in this phase is asserted in the same invocation as a repair that genuinely happened. 'Left the parked records alone', 'byte-stable' and 'changed no done-proof verdict' are all trivially true of a tool that does nothing.

### phase_2: Ecosystem Hardening

**Status**: Planned

Handle version upgrades gracefully with template migrations and config schema evolution. Support multiple concurrent consumer projects and document the contribution workflow for new agents and skills.

**Exit Criteria**:

- Version upgrade path tested: old config + new templates produces valid output with migration warnings
- Documented contribution workflow for adding agents and skills to the package
- Config schema validation rejects unknown keys with actionable error messages

### phase_3: Distribution and Community

**Status**: Planned

Installable via a standard package manager with versioned releases, changelogs, and a documented extension mechanism for community-contributed agents and skills.

**Exit Criteria**:

- Package installable via a standard package manager (pip or npm)
- Versioned releases with auto-generated changelogs
- Extension mechanism documented and tested with at least one community-contributed agent

---

*Last regenerated: 2026-09-08T14:04:16Z. Do not edit this file directly — edit `docs/roadmap.json` instead.*
