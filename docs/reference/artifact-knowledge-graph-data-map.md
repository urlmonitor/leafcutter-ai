---
title: "Reference: Artifact Knowledge Graph — Data Map"
description: "Node table, edge table, trust ratings, gaps, and graph-build guidance for the leafcutter-ai artifact knowledge graph. Foundation for queries on AC implementation status, test coverage, and product-truth linkage."
type: reference
status: active
created: 2026-08-12
last_updated: 2026-08-12
components:
  - knowledge_management
related_docs:
  - docs/architecture/diagrams/c3-005-artifact-knowledge-graph.md
  - config/paths.json
  - config/ac_store_schema.json
  - docs/product-truth/schemas/flow.schema.json
  - docs/reference/ac-schema.md
  - docs/how-to/product-truth-schema-reference.md
---

# Artifact Knowledge Graph — Data Map

A cross-artifact data map for building a queryable knowledge graph over leafcutter-ai's
core artifact types. Covers which artifact types exist, which fields encode relationships,
how far each relationship can be trusted, and which edges require pre-processing before
graph ingestion.

**Machine-readable source of truth:** the node/edge model in this document is mirrored as a
single reusable JSON graph at
[`docs/reference/artifact-knowledge-graph.graph.json`](artifact-knowledge-graph.graph.json).
That file drives the Atlas **Flows** overview ("Artifact knowledge-graph data map",
`architecture` kind) and is the shape the future dynamic (live-instance) graph will emit.
Prefer the JSON + the Atlas view for the visual; the legacy mermaid diagram
(`c3-005-artifact-knowledge-graph.md`) is superseded.

---

## Node Types

One row per artifact type that participates as a node in the graph.

| Artifact Type | Glob / Path | Primary Key / ID Format | Schema / Reference | Notes |
|---|---|---|---|---|
| AC | `docs/acceptance-criteria/**/*.yaml` | `id` field — pattern `PREFIX-NNN[x[-N[-y]]]`, e.g. `ACS-500a-1` | `config/ac_store_schema.json`, `docs/reference/ac-schema.md` | Hierarchical: L0 (portfolio) → L1 (feature) → L2 (story) → L3 (sub-task). Parent ID derived algorithmically by stripping the last segment. |
| Ticket | `tickets/**/*.md` | Filename `TICKET-YYYYMMDD-<AC-ID>.md`; machine key: `ac_traceability.id` in frontmatter | YAML frontmatter (no JSON schema) | Generated from ACs by `generate_ticket_from_ac.py`. The `source_ac` frontmatter field also holds the generating AC ID. |
| Test | `unit_tests/**/*.py` | File path (repo-relative); function identity: `<path>::<function>` | `# covers: <AC-ID>` inline comment convention | Test functions link to ACs via inline tags, not a separate metadata file. |
| SourceFile | `scripts/**`, `templates/**`, application code | Repo-relative file path, optionally with `#anchor` | No dedicated schema | Only an edge target; no node-level schema. |
| Flow | `docs/product-truth/flows/**/*.flow.json` | `id` field — pattern `<product>/<name>`, e.g. `leafcutter/ac-lifecycle` | `docs/product-truth/schemas/flow.schema.json` | Contains steps and branches; each step/branch may reference ACs via `implements[]`. |
| Mockup | `docs/product-truth/mockups/**/*.mockup.json` | `id` field (`<product>/<name>`); bare `screen` field used by flow steps | `docs/product-truth/schemas/mockup.schema.json` | `screen` is the resolvable reference key that flow steps use (NOT `id`). |
| MockData | `docs/product-truth/mock-data/**/*.mock.json` | `id` field — pattern `<product>/<name>` | `docs/product-truth/schemas/mock-data.schema.json` | One canonical dataset per entity per component; grows in-place, never duplicated. |
| Changelog | `changelogs/**/*.md` | Filename `YYYY-MM-DD-HHMM-<slug>.md` | YAML frontmatter validated by `scripts/changelog/emit_entry.py` | Required fields: `title`, `date`, `time`, `type`, `components`, `summary`, `description`. Optional: `commits[]`, `adrs[]`, `epic`, `ticket`. |
| Component | `docs/components.json` | Underscore `id` (e.g. `ac_driven_dev`); 42 registered IDs | `docs/components.json` | Referenced by `components` field on ACs, tickets, docs, and changelog entries. Separate from the AC-store kebab `component` namespace key. |

---

## Edge Table

One row per directed relationship between artifact types, keyed by the **field** that encodes it. Several field-rows collapse to one **Canonical Edge** (the relationship label a graph should use); e.g. the parent-child relationship is encoded by up to four different fields (see Gap 9). Trust is split into two orthogonal axes, per the data-expert review:

- **Enforcement** — how strongly the link is guaranteed: `enforced` (a pre-commit hook and/or required CI gate blocks violations), `warn` (tooling warns but never blocks), `none` (no tooling reads it), `derived-validated` (machine-generated **and** its freshness/parity is blocked at commit), `derived-raw` (machine-generated with no freshness guard).
- **Shape** — how clean the value is for ingestion: `clean` (single unambiguous form), `ambiguous` (one field multiplexes several edge types — must be partitioned), `freetext` (unresolvable string), `derived`.

A link is ingestable as-is only when it is `enforced`/`derived-validated` **and** `clean`. Everything else needs the reconciliation noted in "Graph Ingestion Readiness".

| Canonical Edge | Source | Field | Target | Cardinality | Enforcement | Shape | Notes (writer / hook / caveat) |
|---|---|---|---|---|---|---|---|
| `PARENT_OF` | AC | ID-derivation (no field) | AC (parent) | Many-to-one | n/a (algorithmic) | clean | **Canonical** parent source: strip the last ID segment (`ACS-500a-1` → `ACS-500a`). |
| `PARENT_OF` | AC | `parent` (explicit) | AC (parent) | Many-to-one | none | clean | `config/ac_store_schema.json:499-503` — used only when the parent cannot be derived from the ID (C2). No target-existence check. |
| `PARENT_OF` (integrity) | AC (parent) | `covered_by` (child-AC entries) | AC (child) | One-to-many | enforced | ambiguous | `check-ac-parent-covered-by` (commit_guardian.json:866-877, ACS-100i-2) **blocks** a child commit whose parent omits the back-link (C3). Field shared with test paths (Gap 3). |
| `DEPENDS_ON` / `COMPOSES_PATTERN` | AC | `depends_on` | AC | Many-to-many | enforced | ambiguous | `check-ac-circular-deps` blocks cycles; `check-ac-governance` write-locks the field. **Target-existence NOT validated** (items are bare strings). Multiplexes parent + pattern-composition + true dependency (C1, Gap 8) — must be partitioned. |
| `COMPOSES_PATTERN` | AC | `implements_pattern` | Pattern (AC) | Many-to-one | enforced | clean | `check-ac-pattern-refs` (commit_guardian.json:892-903) + `check-ac-schema` (:946-957) block bad/dropped pattern refs and missing slot bindings (C6). |
| `SUPERSEDED_BY` | AC | `superseded_by` | AC (successor) | One-to-many | none | clean | No hook verifies the target AC exists. |
| `IMPLEMENTED_BY_TICKET` / `IMPLEMENTED_BY_SOURCE` | AC | `implemented_by` | Ticket **or** SourceFile | Array | none | ambiguous | **UNTRUSTED.** Three coexisting shapes (ticket `.md` path / source path `#anchor` / empty). Schema says "source paths" (`ac_store_schema.json` L112-120) but `generate_ticket_from_ac.py`, `cross_reference_audit.py` write ticket paths; `audit_ac_area.py:247-290` splits on `.md` (Gap 1). |
| `TRACES_TO` | Ticket | `ac_traceability` | AC | One-to-one | enforced | clean | `{ id, path }`; `ac-fulfillment-gate` is a mandatory pre-commit phase. |
| — (display) | Ticket | `source_ac` | AC | One-to-one | none | clean | Informational; no hook. |
| `TESTED_BY` | AC | `covered_by` (test entries) | Test | Array | warn | ambiguous | `check_ac_coverage.py` returns 0 unconditionally (`:234`) — warn-only (C4). Field shared with child-AC entries (Gap 3). |
| `COVERS` | Test | `# covers: <AC-ID>` (inline) | AC | Many-to-many | enforced (for `done` ACs) | clean | Real enforcer is `check-done-proof` (commit_guardian.json:1054-1064): pre-commit **+ required CI backstop** for `work_status: done` ACs; warn otherwise (C5). Coverage regex captures only the **base id** — ingest the full token yourself (Gap 11). |
| `TOUCHES` | Ticket | `files_touched` | SourceFile | Array | none | clean (semantic drift) | Declared ≠ actual is a known phantom-done mode; `change-scope-reviewer` detects but does not block. |
| `TICKET_DEPENDS_ON` | Ticket | `depends_on` | **AC** (not Ticket) | Array | none | clean (misleading name) | Values are AC IDs despite the name; do NOT build Ticket→Ticket edges from it (Gap 7). |
| `IMPLEMENTS` | FlowNode (step/branch) | `steps[].implements` | AC | Array | enforced (shape + parity); **target-existence warn-only** | clean | `check-product-truth-validate` enforces schema shape and the derived-parity inversion; a flow can still reference a nonexistent AC and commit (C8, Gap 10). `flow.schema.json:43` calls this the authored source of truth for graph↔AC linkage. |
| `REALIZED_BY` (reverse of `IMPLEMENTS`) | AC | `product_truth` | Flow / FlowNode | Array | derived-validated | derived | GENERATED by `generate_product_truth.py` — never hand-edited. **Drift-blocked at commit**: `check-product-truth-validate` D2 parity (`validate_product_truth.py:362-385`) + `check-product-truth-generate --check` both error on staleness (C7 — corrects old Gap 6). |
| `RENDERS` | FlowNode (step) | `steps[].screen` | Mockup | One-to-one | enforced | clean | Bare `screen` id → `Mockup.screen`; validated by `validate_product_truth.py` (check D4). |
| `USES_DATA` | Flow | `mock_data_ref` | MockData | One-to-one | enforced | clean | Validated by `validate_product_truth.py`. |
| `USES_DATA` | Mockup | `mock_data_ref` | MockData | One-to-one | enforced | clean | Validated by `validate_product_truth.py`. |
| `USES_DATA` (reverse) | MockData | `used_by.flows` / `.mockups` / `.tests` | Flow / Mockup / Test | Arrays | derived-raw | derived | No enforced update protocol; may be incomplete — rebuild from forward refs, don't trust stored. |
| `MEMBER_OF` | Any artifact | `components` | Component | Array | enforced (AC) / none (others) | clean | AC schema enum validates against `docs/components.json`; no equivalent enforcement on tickets, docs, or changelog. |
| `MEMBER_OF` | Changelog | `components` | Component | Array | none | clean | No hook validates. |
| `REFERENCES_ADR` | Changelog | `adrs` | ADR | Array | none | clean | No hook validates the ADR exists. |
| `RECORDS_COMMIT` | Changelog | `commits` | GitCommit | Array | none | often-empty | Frequently `[]`; unreliable for changelog→commit joins. |
| `MENTIONS_TICKET` | Changelog | `ticket` | Ticket | Scalar | none | freetext | Free-text basename; not programmatically resolvable (Gap 2). |
| `DOCUMENTS` | AC | `doc_links` | Doc | Array | none | mixed (string or `{path, relationship, status, relevance}`) | Informational; no cross-reference enforcement. |

> **Reader note (C9):** `config/paths.json` indexes only four AC edge fields for `knowledge_query.py` — `implemented_by`, `covered_by`, `depends_on`, `components`. It does **not** index `superseded_by`, `implements_pattern`, `product_truth`, or `doc_links`; a graph build must ingest those separately.

---

## Gaps and Ambiguities

Known gaps in the encoding of relationships across the artifact store.

### Gap 1 — `AC.implemented_by` field-shape divergence (CRITICAL)

The JSON schema (`config/ac_store_schema.json` L112-120) documents `implemented_by` as "source file paths (optionally with #anchor)". However, `generate_ticket_from_ac.py` writes ticket .md paths (e.g. `tickets/TICKET-20260720-ACD-1200a-11-i.md`), and `cross_reference_audit.py` also writes ticket paths via backfill. The ac-audit reader (`templates/skills/ac-audit/scripts/audit_ac_area.py:247-290`) detects ticket paths by checking for `.md` in the string and then reads the ticket's `files_touched` to obtain the actual source files. All three shapes — ticket path, source path, and empty list — coexist in the live store. This field is explicitly treated as UNTRUSTED by ac-audit and cannot be used as a reliable AC→SourceFile link without preprocessing.

### Gap 2 — Changelog has no direct link to ACs or tickets

The changelog entry frontmatter provides `components` (underscore IDs), `commits` (git SHAs, often empty), `adrs` (ADR IDs), and optionally a free-text `ticket` basename. There is no field linking a changelog entry to specific AC IDs, and no field linking it to a ticket file path. "Which ACs does this release include?" cannot be answered from changelog data alone without joining on git SHAs → commits → files_touched → ACs — and `commits` is frequently empty.

### Gap 3 — `AC.covered_by` dual use

The `covered_by` field on an AC is used for two entirely different purposes: (1) test-coverage links (test file paths, optionally with `::function`) and (2) parent-to-child hierarchy links (child AC IDs). An entry like `- ACS-500a-1` in a parent AC's `covered_by` is a child AC ID, while an entry like `- unit_tests/test_ac_store.py::test_foo` is a test path. Distinguishing them requires string-pattern matching. This dual use means the field cannot be used as a simple test-coverage list without pre-processing to separate the two entry classes.

### Gap 4 — No direct Mockup → AC link

There is no field on a Mockup artifact that references AC IDs. The traversal path is Mockup ← Flow step → AC (via `steps[].screen` and `steps[].implements`). "Which ACs govern this screen?" cannot be answered from the Mockup file alone; traversal via the Flow is required.

### Gap 5 — Test → SourceFile relationship not declared

The relationship between a test file and the source file it exercises is implicit (typically by naming convention: `test_foo.py` tests `foo.py`), not declared in any metadata field. There is no `tests_file:` or `subject:` field on test files. "What is the test coverage of source file X?" is unanswerable from metadata alone.

### Gap 6 — `AC.product_truth` is DERIVED but drift-blocked at commit (corrected)

> **Correction (data-expert review, C7):** the earlier claim that "there is no pre-commit hook that regenerates or validates it" is **wrong**. The `product_truth` array is GENERATED by `generate_product_truth.py` and never hand-edited, but its freshness **is** enforced at commit by two active hooks whenever any product-truth artifact **or any AC YAML** is staged:
>
> - `check-product-truth-validate` (commit_guardian.json:987-998) runs `validate_product_truth.py`, whose check **D2** (`validate_product_truth.py:362-385`) errors if `AC.product_truth` does not invert `Flow.steps[].implements`. `jsonschema` is a hard dependency (exits 2 if absent — never a silent no-op).
> - `check-product-truth-generate --check` (:1000-1011) errors if regenerating would change any `product_truth` / `impl_status` / index — i.e. **staleness is a hard commit failure**.
>
> Because flipping an AC's `work_status` stages its YAML, the drift window is largely closed. Treat `product_truth` as `derived-validated`, not stale-by-default. The only escape hatches are `--no-verify` or an out-of-band flow edit that stages neither side.

### Gap 7 — `Ticket.depends_on` references AC IDs, not ticket paths

The `depends_on` field on a ticket frontmatter references AC IDs (e.g. `depends_on: [ACD-1200a-11]`), not other ticket file paths. The `config/paths.json` `tickets` surface declares `depends_on` as an `edge_field`, which `knowledge_query.py` indexes as a Ticket→AC edge. The field name implies ticket-to-ticket dependency but the values resolve to ACs, not tickets. Graph builders must not treat this as a Ticket→Ticket edge.

### Gap 8 — `AC.depends_on` is multi-use (parent + pattern-composition + dependency)

`config/ac_store_schema.json:198-213` defines `depends_on` as an array serving **two documented purposes** — structural parent-child hierarchy links **and** pattern-composition links (a composite pattern lists its atomic component pattern IDs) — in addition to any true cross-AC dependency. The no-cycle DAG invariant is enforced (`check-ac-circular-deps`) and the field is write-locked (`check-ac-governance`), but the three senses are **not disambiguated in-field**. A graph builder that treats every `depends_on` entry as a dependency will return structural parents and pattern components as if they were dependencies — noise that defeats the "what depends on X / what to watch out for when refactoring" query. Partition entries by cross-checking against ID-derivation (parent) and the pattern registry (composition) before emitting `DEPENDS_ON` edges. Symmetric to Gap 3.

### Gap 9 — Parent-child has four redundant, potentially-disagreeing encodings

The AC parent relationship can be expressed by: (1) **ID-derivation** (strip the last segment — the canonical source), (2) the explicit **`parent`** field (`ac_store_schema.json:499-503`, used when the parent is not ID-derivable), (3) a **`depends_on`** parent entry (Gap 8), and (4) the parent's **`covered_by`** child back-link (enforced by `check-ac-parent-covered-by`, C3). These can disagree. Recommended canonical model: derive `PARENT_OF` from the ID (falling back to `parent` when present), and treat the `covered_by` back-link as the **integrity check**, not a second parent source.

### Gap 10 — `Flow.steps[].implements` target-existence is warn-only

`validate_product_truth.py` (`:15`, `:215-217`) checks that each `implements` AC id resolves, but only as a **WARNING** — a flow can reference a typo'd or nonexistent AC and still commit. The schema *shape* and the derived reverse-parity (`REALIZED_BY`) are error-enforced, so the edge is structurally sound, but a small fraction of forward `IMPLEMENTS` targets may dangle. This directly weakens the Flow↔AC query the refactor-impact use case depends on. Recommended fix before relying on it: flip the target-existence warning to an error in `validate_product_truth.py`. Surface unresolved targets as a data-quality signal in any UI (see Atlas rendering).

### Gap 11 — The covers-tag coverage regex truncates hierarchical AC ids

`check_ac_coverage.py:41` parses `# covers:` tags with `#\s*covers:\s*([A-Z]{2,6}-[0-9]{3,})`, which captures only the **base id** (`ACS-500`) and drops hierarchical suffixes (`ACS-500a-1`). A graph builder that reuses this regex will mis-attribute `COVERS` edges to the parent AC. Ingest the full tag token yourself; do not reuse that regex.

---

## Graph Ingestion Readiness

Edges and fields grouped by ingestion readiness for a graph build.

### Reliable enough to ingest as-is

The following edges are enforced by pre-commit hooks or schema validators and can be ingested without preprocessing:

- `PARENT_OF` (AC→AC) — derive from the ID (canonical); the enforced `covered_by` child back-link (`check-ac-parent-covered-by`) is the integrity check (see Gap 9).
- `COMPOSES_PATTERN` via `AC.implements_pattern` (AC→Pattern) — enforced by `check-ac-pattern-refs` + `check-ac-schema`.
- `TRACES_TO` via `Ticket.ac_traceability` (Ticket→AC) — enforced by `ac-fulfillment-gate`; object with `id` and `path`.
- `IMPLEMENTS` via `Flow.steps[].implements` (FlowNode→AC) — shape + reverse-parity enforced; **accept but flag** dangling targets (target-existence is warn-only, Gap 10).
- `REALIZED_BY` via `AC.product_truth` (AC→Flow) — `derived-validated`; drift-blocked at commit (corrected Gap 6). Safe for "which flows does this AC touch".
- `COVERS` via test `# covers:` tags (Test→AC) — enforced for `done` ACs (`check-done-proof`, pre-commit + required CI). Parse the **full** id token, not the base-id regex (Gap 11).
- `MEMBER_OF` via `AC.components` (AC→Component) — schema-validated enum against `docs/components.json`.
- `RENDERS` via `Flow.steps[].screen` (FlowNode→Mockup) — validated by `validate_product_truth.py`.
- `USES_DATA` via `Flow.mock_data_ref` / `Mockup.mock_data_ref` (→MockData) — validated by `validate_product_truth.py`.

### Need reconciliation before ingestion

The following fields require preprocessing before use as graph edges:

- `AC.depends_on` — partition into parent-hierarchy vs pattern-composition vs true dependency by cross-checking ID-derivation and the pattern registry; emit only the true-dependency entries as `DEPENDS_ON` (see Gap 8). Without this, "what depends on X" is polluted by parents and pattern parts.
- `AC.implemented_by` — filter entries containing `.md` (ticket paths → `IMPLEMENTED_BY_TICKET`) separately from those not containing `.md` (source paths → `IMPLEMENTED_BY_SOURCE`). Treat empty lists as unlinked. Prefer traversing AC→Ticket→`files_touched` for source files (see Gap 1). UNTRUSTED.
- `AC.covered_by` — separate entries matching `unit_tests/**` or `tests/**` (test paths → `TESTED_BY`) from entries matching the AC ID pattern (child AC IDs → `PARENT_OF` back-link). Each class is a different edge type (see Gap 3).
- `Changelog.commits` — often empty; do not rely on this field for changelog→commit linkage without confirming the array is non-empty.
- `Changelog.ticket` — free-text string; not a resolvable path or ID. Requires fuzzy matching or manual resolution (see Gap 2).
- `MockData.used_by.*` — may be incomplete; rebuild from forward refs rather than trusting the stored value.

### Edges not yet encoded

The following relationships have no metadata field; they cannot be ingested from artifact data alone:

- Changelog → AC: no field exists; must be reconstructed indirectly via git SHAs when available.
- Test → SourceFile: no metadata field; must infer from file naming conventions.
- Mockup → AC: no direct field; must traverse via Flow step (see Gap 4).

---

## See Also

- [AC Schema Reference](docs/reference/ac-schema.md) — field-by-field reference for AC YAML, including `id` pattern rules, `work_status` enum, and all edge fields documented above.
- [Product Truth Schema Reference](docs/how-to/product-truth-schema-reference.md) — how-to for authoring flows, mockups, and mock data; covers `steps[].implements`, `screen`, and `mock_data_ref` fields.
- [Artifact Knowledge Graph JSON](artifact-knowledge-graph.graph.json) — machine-readable node/edge model; drives the Atlas Flows overview and is the reusable graph source.
- [Artifact Knowledge Graph diagram](docs/architecture/diagrams/c3-005-artifact-knowledge-graph.md) — **superseded** by the JSON + Atlas view; retained for history only.
- `config/paths.json` — canonical path patterns for each artifact surface; `edge_fields` keys declare which frontmatter fields `knowledge_query.py` indexes as graph edges.
- `config/ac_store_schema.json` — JSON Schema for AC YAML files; the primary authoritative source for field types and constraints on AC nodes and their edge fields.
