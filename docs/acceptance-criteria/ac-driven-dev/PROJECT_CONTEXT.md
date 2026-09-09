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

## ACD-400c/d/e scanner selection rules: framing note for the BA/IT-PO (2026-09-08, PO)

Three new L1s grafted onto the EXISTING `ACD-400` (loose files in
`ac-driven-dev/`, alongside `ACD-400a.yaml`), origin_agent BrainCandy, readiness
draft, priority medium, roadmap_phase phase_1. Subject: the two selection rules
in `scripts/ac_store/scan_ac_store.py` that decide what the whole build system
works on next, neither of which any acceptance criterion governs.

- **ACD-400c** — the approval gate (`_is_approved`, line 189). UNSPECIFIED.
- **ACD-400d** — the ordering rule (`_sort_ready`, lines 353-370). MIS-specified.
- **ACD-400e** — one true written account; reconciles the records that disagree.
  `depends_on` names c and d as genuine build-order prerequisites.

**Read the `notes` on all three before decomposing — they carry the verified
findings.** Four points that generalise beyond this tree:

1. **UNSPECIFIED AND MIS-SPECIFIED ARE DIFFERENT GAPS AND WARRANT DIFFERENT
   WORK.** BrainCandy's brief described both rules as ungoverned. One is. The
   other is described by `ACD-400a` and `ACD-400a-1`, and what they say is false
   — a two-key sort (complexity, id) against a shipped three-key sort (priority,
   complexity, id). Before framing any "no AC covers X" gap, check whether an AC
   covers X *wrongly*; a wrong statement is worse than silence, and it needs a
   reconciliation owner that a pure specification AC does not provide.

2. **A THIRD L1 EARNS ITS PLACE WHEN TWO SIBLINGS EACH OWN HALF OF THE SAME
   FILE.** `ACD-400a-1` is wrong in both directions at once. Hanging the repair
   as an L2 under each rule L1 produces two changes to one record, each fixing
   half, with a guaranteed conflict. Reconciliation as its own L1 depending on
   both is the clean shape. This is the shotgun-surgery smell applied to the AC
   store rather than to code.

3. **`test_readiness_gate.py` IS NOT COVERAGE FOR THE SCANNER'S APPROVAL GATE.**
   It covers `classify_readiness()` in `goal_to_epic.py` (ACD-1200b-1/-2), a
   different surface. Name-similar tests are the easiest false-green in this
   repo; grep the import, not the filename.

4. **TWO SELECTORS, TWO DELIBERATELY OPPOSITE READINESS RULES — DO NOT UNIFY
   THEM.** `BO-2400f-2` (approved, done) makes fast-lane selection
   readiness-agnostic and `BO-2400f-12-ii` forbids readiness, priority,
   req_status and status from the producibility decision. `BO-2400f-2` even
   defines itself by contrast — "unlike the normal ready-batch scan" — so an
   approved criterion in another component currently rests on a rule nobody
   wrote down. Any L2 that harmonises the two selectors contradicts an approved AC.

**Flagged to the user, NOT authored, and must not be pulled into an L2 here:**
the approval test runs before ready/blocked classification (line 1000 precedes
line 1008), so an excluded record appears in neither list and in no count. That
is an `ACS-1100` (honest coverage answers, `scope: standing`) obligation about
what the scanner OUTPUTS, not about how it SELECTS. Inherited, not duplicated.

**Placement candidates rejected** (do not re-litigate): `ACS-1000` is not an L0
despite its folder name — the file is `level: L2`. `ACS-1100` is `scope:
standing` and explicitly not a home for other surfaces. `ACS-100` is at nine L1s,
over the 7-cap. `ACD-1800`/`ACD-1600` concern what a unit of work is, not which
one is picked. `ACD-400a` itself is full at five L2s and forbids an override.
`ACD-400` now carries five L1s against the 7-cap; no `child_limit_override` is
authored and none may be added.

## ACD-2200 / ACD-2300 adoption + backfill: framing note for the BA and IT PO (2026-09-09, PO)

Two NEW sibling root L0s, `origin_agent: BrainCandy`, `readiness: draft`,
`priority: medium`, four L1s each (three free slots in each; no
`child_limit_override` is authored and none may be added):

- `ACD-2200-adoption-floor/` — *"Turn the standards on in a codebase that was not
  built under them."* `roadmap_phase: phase_1` (claim argued in its notes).
- `ACD-2300-backfill-existing-code/` — *"Code that already exists gets the
  requirements and the proof it never had."* Deliberately **unphased**, flagged for
  the user; `depends_on: [ACD-2200]`.

Full evidence, confidence labels and the rejected alternatives live in the two
L0s' `notes`. **Read those before decomposing.** Five things generalise beyond
this pair.

1. **ONE REQUEST CAN BE TWO L0s WHEN THE REGISTER ALREADY SEQUENCES IT.** The
   brief asked for backfill tooling. `KI-CG-20260908-gate-test-ac-tags` ends
   "Ratchet first, backfill opportunistically" — so the floor and the backfill are
   independently shippable and already ordered by evidence. Splitting on that seam
   also avoided a single L0 at exactly the 7-L1 cap with zero headroom.

2. **A LIVE CONTRADICTION BETWEEN TWO STORE RECORDS, RAISED AND NOT RESOLVED.**
   `ACD-800` (readiness reviewed, unbuilt since 2026-06-05) promises to backfill
   `(implemented_by, work_status)` from "text similarity and keyword heuristics".
   `ACS-1300`'s L0 forbids any record in its tree from writing `work_status` at
   all, and marks the refusal "not to be revisited". Both cannot be right.
   `ACD-2300` sides with `ACS-1300` and authors **no** field reconciler.
   `ACD-800` needs amending or retiring — a **user decision**, not the BA's.
   Note also that `ACD-800`'s method presumes a history of done TICKETS, which an
   adopting project does not have.

3. **CHECK WHETHER AN AC COVERS YOUR GAP FOR A DISJOINT POPULATION.** The brief's
   "connect existing tests to existing ACs" reads as already-owned by `ACS-1300a`
   — and is, for tests that ALREADY carry a tag (exact mechanical join, 549
   records). The unowned population is the 5,566 test functions with **no tag at
   all**, where there is no join key and the link must be *proposed*. Same
   sentence, disjoint populations, different risk. `ACD-2300b` is scoped to the
   second only. Generalises the ACD-400 lesson one step: before framing a gap,
   check not only whether an AC covers it *wrongly* but whether one covers a
   *neighbouring population* under wording that sounds identical.

4. **`implemented_by` DOES NOT NEED A RECONCILER — AUTHOR IN THE DIRECTION WHERE
   THE EVIDENCE ALREADY EXISTS.** A criterion derived from a function knows the
   function, so the implementation evidence is a by-product of authoring and can
   never be empty. A criterion matched to code afterwards always can. That is why
   the field lives inside `ACD-2300a` rather than in a fourth L1. It is the
   structural fix for the phantom-done shape recorded at
   `KI-CG-20260908-gate-ac-done-on-merge`.

5. **THE GUARANTEE L1 IS NOT OPTIONAL AND ITS NEGATIVE ARMS ARE THE LOAD-BEARING
   HALF.** `ACD-2300d` exists because the cheapest implementation of `a`, `b` and
   `c` satisfies all three while violating every safety property. Precedent:
   `ACS-1300c` and `TQ-400e`. Every clause is a promise about what does **not**
   happen, so each needs a behaviour where the tool is fed untrustworthy evidence
   and correctly refuses to write — proved by **running it**, per CLAUDE.md's
   "Gate / Workflow ACs — Verify Behaviorally, Not by Grep".

**Inherited, not restated** (do not author children for these): `ACS-1100`
(state your denominator), `ACS-1300`'s byte-stability and abstention-over-action
rules and its absolute `work_status` refusal, `TQ-400e-1`'s do-not-write rule,
`GE-127b`'s per-file ratchet as the worked example of ONE standard's floor, and
`TQ-500`/`GE-120`/`GE-126` for "an adopted standard must be able to fail".
`BP-1600a-2` is a precondition **in this repository only**, not a general
dependency — an adopting project gets the wiring from the install and still faces
`ACD-2200`'s problem.

**Do not bake a measured figure into any criteria block in either tree.** Every
number (5,566 / 499 / 252 / 49 / 354 / 549 / ~87) is a property of THIS repository
on one day. Both capabilities must work on a repository nobody here has counted.

**Identifier.** Highest taken ACD root is now `ACD-2300`. Established free
2026-09-09 by four checks, none a directory listing (loose namespace-root records
`ACD-1400`–`ACD-1405` are invisible to one): store-wide `^id: ACD-` scan (highest
was `ACD-2100`); whole-worktree grep excluding `.git`; a grep of the shared main
working tree; `git grep` against `origin/main`. Re-verify at merge time —
id allocation here is known-broken (KI-ACD-008).
