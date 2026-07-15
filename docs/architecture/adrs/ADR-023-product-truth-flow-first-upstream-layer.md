---
title: "ADR-023: Product-Truth Store as the Flow-First Upstream Layer Beside the AC Store"
description: "Records the decision to introduce a second structured store — the product-truth store (flows, mockups, mock data) — as the flow-first upstream authoring surface that GENERATES acceptance criteria, while the AC store remains the single authoritative backlog. Reconciles ADR-010 by scoping the AC store's authority to the backlog and positioning flows as the upstream product-intent surface. Covers flow-first authoring, ACs derived from flow steps, derived impl_status rolled up from work_status, and the Leafcutter Atlas as the read surface."
type: "adr"
status: "accepted"
created: "2026-07-14"
last_updated: "2026-07-14"
deciders:
  - BrainCandy
components:
  - ux_prototyping
  - ac_store
  - build_pipeline
related_docs:
  - docs/architecture/adrs/ADR-010-ac-store-as-authoritative-backlog.md
  - docs/architecture/adrs/ADR-007-contract-driven-acs.md
  - docs/architecture/components/ux-prototyping.md
  - docs/product-truth/README.md
  - docs/how-to/authoring-product-truth-artifacts.md
  - docs/how-to/product-truth-schema-reference.md
related_code:
  - docs/product-truth/schemas/flow.schema.json
  - docs/product-truth/schemas/mock-data.schema.json
  - docs/product-truth/schemas/mockup.schema.json
  - docs/product-truth/schemas/classifier-eval.schema.json
  - docs/product-truth/scripts/validate_product_truth.py
  - leafcutter-web/lib/data/flows.ts
---

# ADR-023: Product-Truth Store as the Flow-First Upstream Layer Beside the AC Store

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-07-14 |
| Deciders | BrainCandy |
| Author | documentation-expert |
| Supersedes | — |
| Amends | ADR-010 (scopes its "single source of backlog truth" claim — see "Relationship to ADR-010") |

## Context

ADR-010 established the **AC YAML store** (`docs/acceptance-criteria/`) as the
authoritative backlog: `scan_ac_store.py` reads it to find ready leaf ACs, and
`generate_ticket_from_ac.py` turns a single AC into a ticket. That inversion
solved *how work is queued* — but it left an upstream gap.

The AC store starts at the criterion. Nothing above it captures the **product
intent** an acceptance criterion is supposed to encode:

- **What exists** — the entities a feature reasons about (`Plant`, `Customer`,
  `Order`) and a canonical dataset for them.
- **The journey** — the ordered steps and "what-if" branches a person (or an
  agent, or a pipeline) walks through end to end.
- **The screens** — the surfaces each step renders.

Historically that intent lived only in a human's head or in ticket prose. Two
recurring failure modes followed:

1. **Synthetic-fixture drift.** Each ticket invented its own sample data, so the
   `Plant` a test used never matched the `Plant` a mockup drew or the `Plant` the
   product owner reviewed. There was no single canonical dataset per entity.
2. **ACs authored without a journey.** Behavioral ACs were written per ticket
   with no shared picture of the flow they belonged to, so coverage gaps and
   contradictory scenarios were invisible until integration.

The `docs/product-truth/` store (seeded and hand-walked 2026-07-10, see its
`README.md`) exists to close this gap. It holds three artifact kinds — **Flows**,
**Mockups**, and **Mock Data** — plus a **classifier eval** set that decides
which of the three a request needs. Each artifact is machine-readable JSON
validated against a schema, carries the same `readiness` lifecycle
(`draft → reviewed → approved`) reviewed by a persona, and cross-references the
others and the AC store by stable ids.

The store shipped with schemas, a validator, a searchable `index.json` manifest,
a mandatory "search → add-vs-create" authoring protocol, and a live read surface
(the Leafcutter Atlas, `leafcutter-web/`). What it lacked was a recorded
decision. In particular it appears to **collide with ADR-010**: if flows are
where product truth is authored, which store is authoritative? This ADR records
the decision and resolves that ambiguity.

## Decision

**The product-truth store is adopted as a second structured store that sits
beside the AC store as the flow-first *upstream authoring surface*. Flows are the
primary product-intent artifact; acceptance criteria are *derived from* flow
steps. The AC store remains the single authoritative *backlog*.**

The two stores have distinct, non-overlapping authorities:

| Store | Authoritative for | Not authoritative for |
|---|---|---|
| **Product-truth** (`docs/product-truth/`) | Product intent — journeys (Flows), screens (Mockups), canonical data (Mock Data). The upstream "what & why" that a persona reviews as a picture. | The backlog. It carries no `work_status` and queues no work. |
| **AC store** (`docs/acceptance-criteria/`) | The backlog — `work_status`, dependency ordering, ticket generation (ADR-010). The downstream "is it ready / is it done." | Product intent. It has no notion of a journey, a screen, or a dataset. |

Five concrete rules realise this:

1. **Flow-first authoring.** A feature's journey is authored as a Flow
   (`<product>/<name>.flow.json`) before its ACs exist. Each step and branch
   carries plain-language `human`/`summary` text plus `acceptance_scenarios`
   (Given/When/Then seeds). Mockups and Mock Data are authored alongside, keyed
   to the same entities. Authoring follows the mandatory **search →
   add-vs-create** protocol (search `index.json` by component + entity + flow;
   EXTEND a matching artifact in place, else CREATE and register it) so there is
   exactly one canonical dataset per entity per component — killing the
   synthetic-fixture drift.

2. **ACs are derived from flow steps.** The `business-analyst` reads a flow
   step's `acceptance_scenarios` and decomposes them into L2/L3 AC YAML files in
   the AC store. Each step/branch then records the resulting AC ids in its
   `implements: [...]` list. This is the **authored** link and the source of
   truth for flow↔AC linkage. The AC store is thus *generated from* the flow
   store, not authored independently of it.

3. **`impl_status` is derived, rolled up from `work_status`.** A step's
   `impl_status` (`not_started | in_progress | done`) is **never hand-edited**.
   It is computed from the `work_status` of every AC in its `implements` list
   (which itself bottoms out on ticket `status: done`), or — when the step has
   `expands_to` — from the child flow's rollup. `impl_summary` rolls the whole
   flow up. The flow store reads status *from* the AC store; it never writes a
   competing status. The Atlas resolves this live at read time
   (`leafcutter-web/lib/data/flows.ts` → `acById(id).workStatus`), with the
   flow JSON's stored `impl_status` used only as a fallback for AC ids that do
   not resolve.

4. **The Leafcutter Atlas is the read surface.** `leafcutter-web/` renders both
   stores live from the repo on each request. Flows are shown coloured by their
   derived build status; clicking an AC finds the steps whose `implements`
   contains it. The Atlas (and the generated `.md` rendering of each flow) are
   **read-only views** — the `.flow.json` stays the single source of truth for
   the journey.

5. **Validation gates the store.** `docs/product-truth/scripts/validate_product_truth.py`
   checks schema conformance, `index.json` mirroring, entity-registry membership,
   step/branch id uniqueness, `acceptance_scenarios.for` resolution,
   `impl_summary` correctness, mock-data invariants, and classifier `outcome`
   consistency. It is wired into the commit gates alongside the AC gates.
   Unresolved `implements` AC ids are warnings (a seed flow may reference
   not-yet-authored ACs).

The downstream build pipeline is unchanged: the `business-analyst` still emits
AC YAML, `scan_ac_store.py` still queries the backlog, and
`generate_ticket_from_ac.py` still produces tickets. The product-truth store
feeds *into* that pipeline by giving the BA a reviewed journey to decompose; it
does not replace any stage of it.

### Relationship to ADR-010 (reconciliation / amendment)

ADR-010's decision line reads: *"The AC YAML store becomes the authoritative
source of truth for the leafcutter-ai build backlog,"* and its consequences
speak of a *"single source of backlog truth."* Read narrowly that is still
exactly true and is **not** changed by this ADR. This ADR **amends only the
scope** of that claim, to remove the ambiguity a second store creates:

- **ADR-010 remains authoritative for the backlog.** `work_status`, dependency
  ordering, readiness for build, and ticket generation all live in the AC store.
  The product-truth store adds no second `work_status` and queues no work.
  There is still exactly one backlog.
- **The product-truth store is authoritative for product intent, upstream of the
  backlog.** It is the surface on which journeys, screens, and canonical data are
  authored and persona-reviewed *before* ACs exist.
- **The stores relate by generation, not competition.** Flows GENERATE ACs
  (rule 2); ACs feed the backlog (ADR-010); the backlog's `work_status` is READ
  BACK to derive flow `impl_status` (rule 3). The arrow of authority is:
  **product intent (flows) → acceptance criteria (backlog) → tickets →
  work_status → derived flow status**. No cycle, no dual ownership of any single
  fact.

In one sentence: **the AC store stays the single authoritative backlog; the
product-truth store becomes the flow-first upstream authoring surface that
generates the ACs which populate that backlog.** ADR-010 is amended (its
authority scoped to "the backlog"), not superseded.

## Consequences

### Positive

- **One canonical dataset per entity per component.** The add-vs-create protocol
  and the `entity_registry` in `index.json` make duplicating a dataset a hard
  validation failure. This directly kills the synthetic-fixture drift that
  repeatedly let broken features pass green tests.
- **ACs gain a reviewed journey.** Behavioral ACs are decomposed from a flow a
  persona has approved, so coverage gaps and contradictory scenarios surface at
  authoring time, on one shared picture, instead of at integration.
- **Live, honest status.** Because `impl_status` is derived from AC
  `work_status` and never hand-edited, the Atlas shows the true build state of a
  journey; a flow cannot claim "done" while its ACs are `todo`.
- **The picture and the machine artifact are the same file.** Agents read the
  JSON; personas review the rendered view; both are projections of one
  `.flow.json`. No parallel prose spec to drift.
- **The seam to other projects is preserved.** The Atlas resolves its repo root
  via `LEAFCUTTER_REPO_ROOT`, so the same read surface can host other projects'
  product-truth stores later.

### Negative

- **A second store to keep consistent.** `index.json` and its derived indexes
  (`by_component`, `by_entity`, `by_flow`) must stay in sync with `artifacts[]`,
  and the `implements` links must stay in sync with the AC store. The validator
  enforces most of this, but a new authoring discipline is now required.
- **Authoring order matters.** The value depends on flows being authored (or at
  least sketched) before ACs. An AC written directly in the store with no
  originating flow is still valid for the backlog but bypasses the product-intent
  layer — the store cannot force flow-first authoring, only reward it.
- **Derived status depends on accurate `implements` links.** If a step's
  `implements` list is wrong or empty, its derived `impl_status` is
  meaningless. The link is authored by the BA and is only as good as that step.
- **Two review lifecycles.** Both stores carry `readiness: draft → reviewed →
  approved`. A feature is only fully reviewed when both its flow and its ACs are
  approved; operators must track both.

### Neutral

- The build pipeline (`scan_ac_store.py`, `generate_ticket_from_ac.py`, phase
  agents) is untouched. No downstream component is aware a flow existed upstream.
- Consumer agents extend rather than replace their behaviour: `business-analyst`
  now derives ACs from flow steps, `test-writer` builds fixtures from Mock Data
  `records`, `frontend-coder` builds screens to match Mockups, and
  `user-surface-smoker` asserts the built screen matches the approved Mockup.
- The `.md` rendering of each flow and the Atlas are read-only views; the
  `.flow.json` remains the single source of truth for the journey.

## Alternatives

### Alternative A — Encode product intent inside the AC store (no second store)

Add journey/screen/dataset metadata as new fields on AC YAML files rather than a
separate store.

**Rejected.** A journey is a graph of ordered steps and branches spanning many
ACs; a dataset is shared across many ACs; a screen is rendered by many steps.
Flattening these many-to-many structures into per-AC fields would duplicate the
data across ACs and lose the shared canonical dataset — reintroducing exactly the
synthetic-fixture drift this store exists to kill. It would also overload the AC
schema (ADR-007b) far beyond its purpose.

### Alternative B — Make flows the backlog (supersede ADR-010)

Let flow steps carry `work_status` directly and have the scanner queue work from
flows, retiring the AC store as the backlog.

**Rejected.** ADR-010's inversion (AC-store-as-backlog, ticket generation,
dependency resolution, bidirectional traceability) is proven and load-bearing.
Flows are a coarse-grained journey view; the AC store tracks requirements at four
levels (L0–L3) with `superseded_by`/`amended_by` history and per-criterion
dependency ordering. Collapsing the backlog into flows would sacrifice that
granularity and audit trail. The right relationship is generation, not
replacement.

### Alternative C — Keep product truth as prose docs / mockup HTML only

Continue capturing journeys and screens as free-form documents and standalone
HTML mockups, with no machine-readable schema or cross-reference.

**Rejected.** Prose and orphan HTML cannot be validated, searched by
component/entity, linked to ACs, or coloured by live build status. The whole
value — one connected web keyed on stable ids, with derived status — depends on
the artifacts being schema-conformant JSON. This is the status quo the store
replaces.

### Alternative D — Hand-edit `impl_status` on flow steps

Let authors set each step's `impl_status` directly instead of deriving it.

**Rejected.** Hand-edited status is the phantom-done failure mode: a flow would
claim "done" while its ACs sit `todo`. Deriving `impl_status` from AC
`work_status` guarantees the picture cannot lie about the machine state, and lets
the validator flag drift. This is a hard rule (rule 3), not a preference.

## References

- [ADR-010 — AC Store as Authoritative Backlog](ADR-010-ac-store-as-authoritative-backlog.md) — the backlog inversion this ADR amends (scopes its authority to "the backlog").
- [ADR-007 — Contract-Driven Acceptance Criteria](ADR-007-contract-driven-acs.md) — the per-agent AC format the BA emits when decomposing a flow step.
- [docs/architecture/components/ux-prototyping.md](../components/ux-prototyping.md) — the component architecture doc for the product-truth store.
- [docs/product-truth/README.md](../../product-truth/README.md) — the store's operational README (layout, linkage, seeds).
- [docs/how-to/authoring-product-truth-artifacts.md](../../how-to/authoring-product-truth-artifacts.md) — the by-hand authoring guide (search → add-vs-create protocol).
- [docs/how-to/product-truth-schema-reference.md](../../how-to/product-truth-schema-reference.md) — field-by-field reference for the four schemas.
- `docs/product-truth/scripts/validate_product_truth.py` — the schema + cross-ref + impl-rollup validator wired into the commit gates.
- `leafcutter-web/lib/data/flows.ts` — the Atlas loader that resolves each step's `implements` to live AC `work_status` and rolls up `impl_status`.
