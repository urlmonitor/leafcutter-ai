---
title: "ADR-010: AC Store as Authoritative Backlog — Source-of-Truth Inversion"
type: "adr"
status: "accepted"
created: "2026-06-05"
last_updated: "2026-06-05"
deciders:
  - BrainCandy
components:
  - ac-store
  - ticket-creation
  - build_pipeline
related_docs:
  - docs/architecture/diagrams/c2-001-ac-driven-pipeline.md
  - docs/acceptance-criteria/index.yaml
  - docs/architecture/adrs/ADR-007-contract-driven-acs.md
  - docs/architecture/adrs/ADR-007-ac-store-schema-id-format-enforcement.md
  - tickets/00_inbox/epics/EPIC-ACDrivenDevelopment/01_ac_scanner_and_ticket_generator.md
---

# ADR-010: AC Store as Authoritative Backlog — Source-of-Truth Inversion

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-06-05 |
| Deciders | BrainCandy |
| Author | adr-author |
| Supersedes | — |

## Context

The leafcutter-ai build pipeline has two existing layers of structured
requirement artefacts:

1. **Ticket files** (`tickets/00_inbox/*.md`) — the unit of work dispatched to
   `epic-supervisor` and `ticket-supervisor`. Each ticket contains an `agents:`
   map, `files_touched`, and `## Acceptance Criteria`.

2. **The AC YAML store** (`docs/acceptance-criteria/`) — a hierarchical store
   of structured YAML files introduced by ADR-007b. Each YAML file encodes a
   single acceptance criterion with fields including `id`, `level` (L0–L3),
   `work_status` (todo/done), `assigned_agent`, `depends_on`, `doc_links`, and
   `criteria` (Gherkin). The store currently holds 100+ structured requirements
   across multiple component namespaces (`ac-driven-dev`, `ac-store`,
   `build-orchestration`, etc.).

Under the original design, **tickets were the primary artefact**: a human (or
`create-ticket` orchestrator) wrote tickets, and ACs were either embedded in
those tickets or cross-referenced from the store. The AC store was a
secondary, documentation-layer artefact — useful for traceability and coverage
analysis, but not itself the driver of work.

This design creates a coordination problem as the AC store grows:

- **Manual ticket creation is a bottleneck.** A human must read the AC store,
  identify which ACs are ready for implementation, and hand-write a ticket that
  correctly maps `files_touched`, `agents`, and `criteria` from the AC YAML.
  This is mechanical work prone to transcription error.

- **Bidirectional traceability is not enforced.** There is no automated link
  from a ticket back to its originating AC, so it is unclear which ACs are
  "in flight" and which are unstarted. The `implemented_by` field in the AC
  YAML exists in the schema but is never populated automatically.

- **Backlog state is split across two surfaces.** The AC store tracks
  `work_status: todo/done` per AC; tickets track their own lifecycle via the
  `agents:` map sign-offs. These two surfaces can drift: an AC may be marked
  `done` without a passing ticket, or a ticket may exist for an AC that has
  never been reflected in `work_status`.

The AC store already contains everything required to generate a valid ticket:
`criteria` (Gherkin), `assigned_agent`, `doc_links` (maps to `files_touched`),
`depends_on` (dependency ordering), and `estimated_complexity` (priority
sorting). The only missing piece is the automated step that reads the store and
produces the ticket.

## Decision

**The AC YAML store becomes the authoritative source of truth for the
leafcutter-ai build backlog.** Tickets remain the unit of execution (they are
still what `epic-supervisor` processes), but they are now *derived artefacts*
generated from the AC store rather than primary hand-authored inputs.

This source-of-truth inversion is realised by two new scripts:

1. **`scan_ac_store.py`** — reads `docs/acceptance-criteria/` and returns a
   priority-sorted list of leaf-level ACs (L2/L3) with `work_status: todo`,
   `status: active`, and all `depends_on` resolved (all dependencies have
   `work_status: done`). Acts as a machine-readable backlog query.

2. **`generate_ticket_from_ac.py`** — accepts a single AC id, reads its YAML,
   and writes a fully-wired ticket file to `tickets/00_inbox/`. After writing,
   it performs an `implemented_by` back-write into the source AC YAML, creating
   the bidirectional traceability link.

The existing build pipeline (`epic-supervisor`, `ticket-supervisor`, phase
agents) is unchanged. Generated tickets are structurally identical to
hand-written tickets; no downstream component is aware of how a ticket was
created. The component diagram for this pipeline is at
[docs/architecture/diagrams/c2-001-ac-driven-pipeline.md](../diagrams/c2-001-ac-driven-pipeline.md).

## Consequences

### Positive

- **Eliminates mechanical ticket transcription.** The mapping from AC YAML
  fields to ticket frontmatter fields (`doc_links → files_touched`,
  `assigned_agent → agents`, `criteria → ## Acceptance Criteria`) is
  deterministic and automated. Transcription errors are removed.
- **Single source of backlog truth.** `work_status` in the AC store is the
  canonical readiness signal. Querying `scan_ac_store.py` gives an
  authoritative, real-time view of what is ready to build, without cross-
  referencing the tickets directory.
- **Automatic bidirectional traceability.** The `implemented_by` back-write
  means every AC in the store can be queried to find its implementing ticket.
  The inverse link (`source_ac` in the ticket frontmatter) means every ticket
  can be traced back to its AC. Both links are populated at ticket-creation
  time without human action.
- **Dependency ordering is computed, not manual.** `scan_ac_store.py` resolves
  the `depends_on` graph and excludes blocked ACs automatically. A human no
  longer needs to reason about dependency ordering when choosing which AC to
  work on next.
- **Idempotency guard prevents duplication.** The generator checks for an
  existing ticket with `source_ac: <ac_id>` before writing. Re-running the
  generator for the same AC is safe and produces a clear non-zero exit with an
  explanatory message.

### Negative

- **AC store completeness becomes a hard prerequisite.** For an AC to produce a
  valid ticket, its YAML must have `assigned_agent`, non-empty `criteria`,
  and ideally populated `doc_links`. An AC store with sparse or incomplete
  fields produces lower-quality generated tickets. The store must be kept
  accurate for this inversion to deliver its value.
- **`work_status` discipline is mandatory.** If `work_status: done` is not
  updated when an AC is implemented (e.g. tests pass and the ticket is closed
  but the AC YAML is not updated), the scanner will re-surface that AC as
  ready. Enforcement of `work_status` updates at ticket-close time must become
  part of the phase-agent sign-off protocol.
- **YAML round-trip risk on `implemented_by` write.** Writing to the source AC
  YAML post-ticket-creation is a mutation of a store that otherwise lives under
  strict schema enforcement. A careless full `yaml.dump` round-trip can reorder
  fields or alter quoting, introducing noisy diffs. Mitigation: the generator
  uses a targeted field update (not a full dump) for the `implemented_by` list.
- **Generated tickets are less expressive for novel or ambiguous work.**
  Machine-generated tickets are deterministic mappings from AC YAML fields.
  They do not capture the narrative context, risk annotations, or architectural
  rationale that a human ticket author might add for complex or exploratory
  work. For such work, hand-authored tickets remain the appropriate mechanism.

### Neutral

- The `create-ticket` orchestrator and `business-analyst` / IT PO pipeline
  (ADR-007) are unchanged. Hand-written tickets created through that pipeline
  remain valid and coexist with generated tickets in `tickets/00_inbox/`.
  Generated tickets carry `source_ac:` in their frontmatter; hand-written
  tickets do not. No downstream component distinguishes between them.
- The existing pre-commit hook `ticket_frontmatter_guard` applies to generated
  tickets unchanged. The generator is responsible for producing frontmatter
  that passes the guard; tests verify this via `AC-6` (Gherkin) in the ticket.

## Alternatives

### Alternative A — Ticket-First (status quo)

Keep tickets as the primary artefact. ACs remain documentation-layer
cross-references in ticket bodies, and the AC store is used only for coverage
analysis, not for driving work.

**Rejected.** This alternative preserves the manual transcription bottleneck
and the bidirectional traceability gap. As the AC store grows to hundreds of
entries, the cost of manual transcription compounds. The AC store already
contains all the fields required to generate a ticket; refusing to automate
this is wasteful.

### Alternative B — AC-First without a dedicated scanner script

Use the AC store as the authoritative backlog but rely on ad-hoc shell commands
or human inspection to identify ready ACs, without a dedicated `scan_ac_store.py`.

**Rejected.** Without a machine-readable query interface, the backlog is not
usable by automation (e.g. the planned `/build-ac` command in ticket 04 of this
epic). The dependency resolution logic — determining which ACs are unblocked —
is non-trivial and error-prone when done manually. A dedicated, tested script
with a defined JSON output schema is required.

### Alternative C — AC store generates tickets at commit time (CI-driven)

Add a CI step that automatically generates and commits tickets for all `todo`
ACs at each push, without a manual invocation step.

**Not rejected — deferred.** Fully automated ticket generation at CI time is a
reasonable future evolution. However, it requires resolving several open
questions: which `todo` ACs should generate tickets immediately vs which should
be held back (e.g. ACs that depend on architectural decisions not yet made)?
How are generated tickets reviewed before entering the build queue? For the
current phase, the semi-automated model (operator invokes the generator per AC)
is preferred because it preserves human control over the build queue without
the complexity of a CI-driven auto-generation loop.

### Alternative D — Replace the AC store with tickets directly

Remove the AC YAML store entirely. Encode all structured AC metadata
(`level`, `work_status`, `depends_on`, `estimated_complexity`) directly in
ticket frontmatter rather than in a separate YAML store.

**Rejected.** The AC store serves purposes beyond ticket generation: it tracks
requirements at multiple levels of granularity (L0 epics down to L3 leaf
tasks), records `superseded_by` and `amended_by` history, and provides a
stable audit surface that is not tied to the lifecycle of any individual ticket.
Collapsing this structure into ticket frontmatter would sacrifice the
hierarchical relationship between ACs (parent/child coverage) and the
requirement-level audit trail. The store was introduced precisely because
flat ticket frontmatter was insufficient (ADR-007b).

## References

- [ADR-007 — Contract-Driven Acceptance Criteria](ADR-007-contract-driven-acs.md) — establishes the per-agent AC format and two-phase ticket creation pipeline that this ADR's generated tickets must comply with.
- [ADR-007b — AC Store Schema and ID Format Enforcement](ADR-007-ac-store-schema-id-format-enforcement.md) — defines the YAML schema and field semantics (`level`, `work_status`, `depends_on`, `doc_links`, `implemented_by`) that `scan_ac_store.py` and `generate_ticket_from_ac.py` consume.
- [Component diagram: AC-Driven Ticket Generation Pipeline](../diagrams/c2-001-ac-driven-pipeline.md) — shows the data flow from AC store through scanner and generator to ticket file and back-write.
- [docs/acceptance-criteria/index.yaml](../../acceptance-criteria/index.yaml) — component registry enumerating the namespaces (`ac-driven-dev`, `ac-store`, `build-orchestration`, etc.) that the scanner walks.
- EPIC-ACDrivenDevelopment ticket 01 — the commissioning ticket for this ADR and the two scripts it covers.
