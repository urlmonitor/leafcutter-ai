---
title: "ADR-022: Mockups Are the Real Application in Mock Mode (Data-Layer Mock Provider or Throwaway Real-DB Seed)"
description: "Records the now-decided model for how product-truth mockups work: a mockup is NOT standalone HTML and is NOT an isolated /mockups preview component — it is the REAL application running in MOCK MODE (same stack, same routes/components, data swapped to mock, toggled on, deployed to a shareable dev URL for review). Two flavors under one mock-mode concept: UI-heavy (a data-layer mock PROVIDER returns product-truth mock-data records, no DB) and DB-heavy (the mock-data artifact is a TYPED DATA MODEL plus seed rows that seeds a THROWAWAY instance of the project's REAL DB engine — Postgres / MSSQL / Neo4j — so the schema itself can be prototyped on the real running site before any migration exists). The mock-data artifact thus becomes the schema prototype that feeds forward on approval: sql-coder builds the real schema from the typed model, test-writer seeds fixtures from the seed rows, frontend-coder hardens the mock-mode screens, user-surface-smoker asserts the built screen matches the approved mock-mode screen. Extends ADR-020 and supersedes the interim bespoke-HTML and isolated-/mockups-preview-component approaches (draft-only, never merged)."
type: "adr"
status: "proposed"
created: "2026-07-15"
last_updated: "2026-07-15"
deciders:
  - BrainCandy
components:
  - ux_prototyping
  - build_pipeline
related_docs:
  - docs/architecture/adrs/ADR-020-product-truth-flow-first-upstream-layer.md
  - docs/architecture/components/ux-prototyping.md
  - docs/product-truth/README.md
  - docs/how-to/authoring-product-truth-artifacts.md
  - docs/how-to/product-truth-schema-reference.md
related_code:
  - docs/product-truth/schemas/mockup.schema.json
  - docs/product-truth/schemas/mock-data.schema.json
  - docs/product-truth/scripts/validate_product_truth.py
  - leafcutter-web/lib/data/flows.ts
---

# ADR-022: Mockups Are the Real Application in Mock Mode (Data-Layer Mock Provider or Throwaway Real-DB Seed)

## Status

| Field | Value |
|---|---|
| Status | Proposed (draft — not yet approved) |
| Date | 2026-07-15 |
| Deciders | BrainCandy |
| Author | documentation-expert |
| Supersedes | — (supersedes two *unmerged, draft-only* interim approaches — see "Alternatives") |
| Extends | ADR-020 (adds the mock-mode realization model to the product-truth layer ADR-020 established) |

## Context

ADR-020 adopted the product-truth store as the flow-first upstream layer, holding
three artifact kinds — **Flows**, **Mockups**, and **Mock Data**. It fixed *where*
mockups and mock data live and *how* they link to ACs, but it deliberately did not
pin down *what a mockup physically is* or *how a reviewer sees it running*. Two
interim answers were sketched and neither was ever merged:

1. **Bespoke standalone HTML.** Each mockup was a self-contained `.html` file
   (the legacy `renders` field). Cheap to author, but it is not the product: it
   drifts from the app's real components, cannot exercise real routing or state,
   and throws away everything on build.
2. **Isolated `/mockups/<screen>` preview components.** A newer draft (reflected
   in the current `mockup.schema.json` `app_component` field and in UXP-541 as
   amended 2026-07-15) mounted each mockup as a *real component in the app's
   stack* but in an *isolated preview area* (`/mockups/<screen>` + a `/mockups`
   index) on the app's dev server. Closer to real, but still a parallel surface:
   the reviewer looks at a preview page, not the actual application flowing
   through its actual routes, and the preview components are still throwaway
   scaffolding distinct from the screens the build will ship.

Both share a defect: **the thing the persona reviews is not the thing the build
hardens into production.** That is the same gap ADR-020 exists to close one level
down (the picture and the machine artifact must be the same file) — here the
*running screen* the PO approves must be the *running screen* the build ships.

A second, sharper need surfaced while dogfooding: some prototypes are not about
the UI at all — they are about **the data structure**. Before committing to a
schema (a set of Postgres tables, an MSSQL model, a Neo4j graph shape), you want
to *see the real site running on that structure*, click through it, and share it
for review — **before any migration exists**. A HTML mockup or a UI-only preview
component cannot do this: there is no real engine behind it, so the schema is
never actually exercised. A portable stand-in (e.g. SQLite) is not faithful to
the features (graph traversals, MSSQL-specific types, Postgres constraints) the
real engine provides, so a schema that "works" against the stand-in can still be
wrong against the target engine.

This ADR records the decided model that resolves both: mockups are the real app
in mock mode, with a UI-heavy flavor (mock data provider) and a DB-heavy flavor
(typed data model + seed rows seeding a throwaway real-engine instance).

## Decision

**A mockup is the REAL application running in "MOCK MODE": the same stack, the
same routes and components, with data swapped to mock, toggled on, and deployable
to a shareable dev URL for review and feedback. It is NOT standalone HTML and is
NOT an isolated `/mockups/<screen>` preview component.** (Standalone HTML remains
allowed only when the product itself is plain HTML, or as an explicit, early-stage
throwaway with no framework to mount into.)

### 1. Two prototype flavors under one "mock mode" concept

| Flavor | What it prototypes | How mock mode realizes it |
|---|---|---|
| **UI-heavy** | The screens and journey | A **data-layer mock PROVIDER** returns records straight from the product-truth **mock-data** store at the app's data-access seam. **No database is involved.** The real components render real routes against provider-supplied records. |
| **DB-heavy** | The data **structure** itself | The mock-data artifact is a **TYPED DATA MODEL** (entities → typed fields + relations/keys) **plus seed rows**. Mock mode **seeds a THROWAWAY instance of the project's REAL DB engine** (Postgres / MSSQL / Neo4j / …) from that artifact and points the app's DB connection at it. You prototype the schema itself, see the real site running on it, and share it — all before any real migration exists. |

Both flavors are the *same* application binary/build with the *same* routes and
components; they differ only in what sits behind the data-access seam.

### 2. The mock-data artifact is the schema prototype (feed-forward on approval)

Because the DB-heavy flavor's mock-data artifact is a typed data model plus seed
rows, an **approved** mock-data artifact *is* the approved schema prototype. On
approval it feeds forward into the build pipeline:

- **`sql-coder`** builds the real DB schema (tables / graph model / constraints)
  from the **typed data model**.
- **`test-writer`** seeds fixtures from the **same seed rows** the PO reviewed.
- **`frontend-coder`** hardens the mock-mode screens into production screens
  (swaps the mock provider / throwaway DB for the real data source, promotes the
  screens out of mock-mode scaffolding into their production location).
- **`user-surface-smoker`** asserts the built screen matches the **approved
  mock-mode screen**.

This is the DB analog of ADR-020's principle "the mockup is the seed the build
hardens": here the mock-data artifact is the seed the *schema* build hardens.

### 3. Toggle mechanism (proposed default)

The recommended, proposed default:

- An **env-based "mock build"** of the real app, served as a **dedicated
  shareable dev URL** for review/feedback.
- A **data-access seam** that selects mock-vs-real **at the data layer** (the
  provider for UI-heavy; the throwaway-DB connection target for DB-heavy).
- An optional **per-project override** (cookie / query-param / URL-prefix) for
  finer-grained mock toggling where a whole separate build is undesirable.
- A **stack-detection step** (from `package.json` + framework config) determines
  the concrete integration points per framework, and — for DB-heavy — the seeding
  path per DB engine.

Alternatives to the toggle are recorded below; the env-based mock build + data
seam is the proposed default, not the only permissible mechanism.

### 4. Supersession of the interim approaches

This model **supersedes** (a) authoring **bespoke standalone HTML** mockups and
(b) mounting **isolated `/mockups/<screen>` preview components**. Both were
draft-only and never merged. The current `mockup.schema.json` `app_component`
shape (which encodes the isolated-preview-route convention) is retained for
migration but is no longer the target model — see "Impact / follow-on work".

## Consequences

### Positive

- **The reviewed screen is the shipped screen.** The persona approves the real
  app flowing through its real routes; the build hardens that exact surface. The
  parallel-preview drift is gone.
- **The data structure can be prototyped on the real engine.** A schema is
  clicked-through and shared on the actual Postgres / MSSQL / Neo4j engine before
  a migration is written, so engine-specific mistakes surface at review time.
- **One artifact feeds four consumers.** The typed model + seed rows drives the
  real schema (sql-coder), fixtures (test-writer), the hardened screens
  (frontend-coder), and the smoke assertion (user-surface-smoker) — one approved
  source, no re-authoring.
- **Sharing is a URL, not a file.** Review/feedback happens against a running
  dev URL of the real app, not an inert HTML file or a preview index page.

### Negative / costs

- **Richer mock-data authoring.** The mock-data artifact must now carry a typed
  data model (entities → typed fields, relations, keys) in addition to sample
  records — a heavier authoring burden than today's untyped `fields: name→string`.
- **Per-stack and per-DB-engine integration work.** Mock mode must be wired per
  framework (the data-access seam) and, for DB-heavy, per DB engine (the
  throwaway-instance seeding path). This is real, recurring integration effort.
- **A new mock-mode runtime.** The env-based mock build, the data-access seam, and
  the throwaway-DB provisioning/seeding/teardown are new machinery to build,
  operate, and keep faithful to the real app.
- **Two toggle surfaces to keep honest.** The env build and the optional
  per-request override must agree; a stale override must never leak mock data
  into a real deployment.

### Neutral

- The product-truth store's *linkage* model (ADR-020) is unchanged: mockups still
  key to mock-data and to flow steps by stable ids; status is still derived.
- The Atlas remains a read surface; only *what it shows for a mockup* changes
  (link to the running mock-mode route / screenshot rather than embedded HTML).

## Alternatives

### Alternative A — Standalone HTML mockups (status quo legacy)

Author each mockup as a self-contained `.html` file (`renders`).

**Rejected.** It is not the product — it cannot exercise real routing, state, or
data, drifts from the app's real components, and is discarded on build, so the
reviewed artifact is never the shipped artifact. Retained ONLY for the plain-HTML
product case and explicit early-stage throwaways (`early_stage_html`).

### Alternative B — Isolated `/mockups/<screen>` preview components

Mount each mockup as a real stack component but in an isolated preview area on the
dev server (the current `app_component` + `/mockups` convention).

**Rejected as the target model.** It is a real component but still a *parallel
surface*: the reviewer sees a preview page, not the actual application flowing
through its real routes, and the preview scaffolding is throwaway distinct from
the screens the build ships. Mock mode runs the real routes instead. (Draft-only,
never merged.)

### Alternative C — Portable SQLite for the mock DB (DB-heavy flavor)

Seed a portable SQLite database instead of a throwaway instance of the project's
real engine.

**Rejected.** SQLite is not faithful to the target engines' features — Neo4j
graph traversals, MSSQL-specific types/procedures, Postgres constraints and
extensions. A schema that validates against SQLite can still be wrong against the
real engine, defeating the whole point of prototyping the structure on the real
site. Mock mode seeds a throwaway instance of the *actual* engine.

### Alternative D — Keep mockups UI-only (no DB-heavy flavor)

Support only the data-layer mock provider; never seed a database.

**Rejected.** It cannot prototype the data structure itself — the sharpest need
that motivated this ADR. The two-flavor model keeps the cheap UI-only path *and*
adds the schema-prototyping path.

## References

- [ADR-020 — Product-Truth Store as the Flow-First Upstream Layer](ADR-020-product-truth-flow-first-upstream-layer.md) — the layer this ADR extends; establishes the mockup/mock-data artifacts and the "picture = machine artifact" principle this ADR applies to the running screen.
- `docs/acceptance-criteria/ux-prototyping/UXP-540-pt-authoring-agents/UXP-540.yaml` — the mock-data-author AC; its `fields` must gain the typed model + seed rows this ADR requires.
- `docs/acceptance-criteria/ux-prototyping/UXP-540-pt-authoring-agents/UXP-541.yaml` — the mockup-author AC; currently specifies the isolated `/mockups/<screen>` preview model this ADR supersedes.
- `docs/product-truth/schemas/mockup.schema.json` — current mockup shape (`app_component`, `renders`, `early_stage_html`); the mock-mode model changes what `app_component` should express.
- `docs/product-truth/schemas/mock-data.schema.json` — current mock-data shape (untyped `fields`); must gain typed fields + relations/keys.
- [docs/product-truth/README.md](../../product-truth/README.md) — the store's operational README (Mockups + Mock Data sections).

## Impact / follow-on work

Concrete changes required to implement this decision. This is a checklist for the
orchestrator to drive next — **nothing below is done by this ADR** (which only
records the decision):

- [ ] **`mock-data.schema.json` → typed data model.** Extend the per-entity shape
      from untyped `fields: name→string` to a typed data model (fields with types,
      plus relations / foreign keys / graph edges), keeping the existing sample
      `records` as the seed rows. Add DB-engine hints where needed.
- [ ] **`mockup.schema.json` — rework `app_component` for mock mode.** `app_component`
      already exists but encodes the isolated-`/mockups`-preview convention; rework
      it to express "real app in mock mode" (real route on the real app, mock-mode
      toggle, shareable dev URL) rather than an isolated preview route. Keep
      `renders`/`early_stage_html` for the plain-HTML / early-stage exception.
- [ ] **New mock-mode runtime + data-access seam.** Build the env-based mock build,
      the data-layer seam that selects mock-vs-real, the UI-heavy mock provider
      (records from the mock-data store), and the optional per-request override.
- [ ] **Mock-DB seeding per engine (DB-heavy flavor).** Provision, seed (from the
      typed model + seed rows), point the app at, and tear down a throwaway
      instance of the project's real DB engine — per engine (Postgres / MSSQL /
      Neo4j / …).
- [ ] **Stack-detection step.** From `package.json` + config, determine the
      per-framework integration points (seam wiring) and per-engine seeding path.
- [ ] **Rework the authoring agents + prompts.** Update `mock-data-author`
      (typed model + seed rows) and `mockup-author` (produce mock-mode screens on
      the real app, not isolated preview components) and their pipeline prompts /
      gold examples.
- [ ] **Feed-forward wiring on approval.** Wire sql-coder (real schema from typed
      model), test-writer (fixtures from seed rows), frontend-coder (harden
      mock-mode screens), user-surface-smoker (assert built screen matches approved
      mock-mode screen).
- [ ] **New ACs.** Author ACs for mock-mode (toggle + shareable dev URL + data
      seam), the typed data model, and per-engine DB seeding; supersede/amend
      UXP-541 (isolated-preview model) and enrich UXP-540 (typed model).
- [ ] **Atlas `/flows` drawer.** Link the step drawer to the running mock-mode
      route / screenshot instead of embedding mockup HTML (the ADR-020 follow-up
      already noted against the flow-drawer AC).
