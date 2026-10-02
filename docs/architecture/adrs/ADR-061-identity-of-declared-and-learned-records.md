---
title: "ADR-061: Identity — Existing Ids Stay, Decisions Get a Kernel-Minted Id, Records Are Keyed by Repository, Kind and Id"
description: "Records keep the ids the repository already uses (component snake ids, AC PREFIX-NNN, ADR-NNN, roadmap phase ids); decisions get a kernel-minted dec-<16hex> id; a record is identified by the key (repository_id, kind, id). No new namespaced id scheme such as ac:component:name is introduced."
type: "adr"
status: "active"
created: "2026-10-01"
last_updated: "2026-10-01"
deciders:
  - BrainCandy
components:
  - decision_kernel
related_docs:
  - docs/architecture/adrs/ADR-059-decision-store-reviewable-yaml-records-now-graph-later.md
  - docs/architecture/adrs/ADR-060-source-of-truth-and-approval-authority.md
  - docs/analysis/2026-10-01-neo4j-colony-memory-concept-3-graph-model-ids-provenance.md
  - docs/analysis/2026-10-01-colony-memory-stage0-delta.md
  - tickets/00_inbox/TICKET-20261001-KernelDecisionStore.md
related_code:
  - kernel/contracts/base.py
  - kernel/capabilities/decision/state.py
  - kernel/memory/models.py
  - kernel/memory/vocab.py
---

# ADR-061: Identity — Existing Ids Stay, Decisions Get a Kernel-Minted Id, Records Are Keyed by Repository, Kind and Id

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-01 |
| Deciders | BrainCandy |
| Author | Claude Code, recording the user's decisions in [TICKET-20261001-KernelDecisionStore](../../../tickets/00_inbox/TICKET-20261001-KernelDecisionStore.md) |
| Supersedes | None |

## Context

The colony concept proposes semantic ids such as `component:retrieval`,
`ac:retrieval:cache.force_refresh` and `adr:retrieval:caching-strategy`, and generated ids such as
`decision:<uuid>`
([concept part 3](../../analysis/2026-10-01-neo4j-colony-memory-concept-3-graph-model-ids-provenance.md),
section 11). Its rule is that only entities whose identity must survive refactoring need a
manually declared id. The repository already has ids for most of them: component ids in
`docs/components.json`, AC ids `PREFIX-NNN`, ADR numbers, roadmap phase ids. The Stage 0 review
warned that an ingester which invents its own mapping creates a second id system.

## Decision

### 1. Existing entities keep their existing ids

A record MUST refer to a component by its snake id in `docs/components.json`, an acceptance
criterion by its `PREFIX-NNN` id, an ADR by `ADR-NNN`, a roadmap phase by its id in
`docs/roadmap.json`, and a capability by its registry id. No `ac:x:y` or `component:x` scheme is
introduced; a backend that wants a namespaced form derives it from the key in section 3.

### 2. Decisions get a kernel-minted `dec-<16hex>` id

A decision id is `dec-` plus 16 lowercase hex characters, derived from the work item that owns
the decision (`derive_decision_id`), so every pause of one decision shares it and a filed record
maps one to one onto the run's `Decision`. A record file is named `<id>.yaml`. Ids are unique in
the store (checked by `decisions validate`) and a `supersedes`, `superseded_by` or `related` link
MUST name an existing id.

### 3. The identity key is (repository_id, kind, id)

A record carries `repository_id` and `kind` (`decision`). `repository_id` comes from
`memory.repository_id` in the kernel config and falls back to the scope's workspace id. Inside one
repository the id alone is unique; the key is what a shared or graph store uses so two repositories
cannot collide.

### 4. Filters use only existing vocabularies

A record's classification filters MUST be drawn from the values already defined elsewhere:
component ids, the `change_target` and `risk_surface` enums of `config/ac_store_schema.json`,
roadmap phase ids, and the file-type globs of `templates/rules/*.md`. `decisions validate` reads
those sources and rejects any other value.

## Consequences

### Positive

- One id system. A decision cites ADR-056 or `decision_kernel` exactly as everything else does.
- A decision id is stable across pauses and restarts, and unique without a registry.

### Negative

- A decision id says nothing about its subject; the title and the index carry that.
- The roadmap phase vocabulary changes over time, so an old record can name a retired phase; the
  validator reports it and a person decides whether to correct the record.

### Operational

- `kernel/memory/vocab.py` reads the vocabularies; `kernel/memory/models.py` holds the id and key
  patterns.

## Alternatives

- **The concept's namespaced semantic ids (`ac:retrieval:cache.force_refresh`).** Rejected: the
  repository already has AC, ADR and component ids, and a second scheme would need a mapping.
- **Random UUIDs for decisions.** Rejected: a work-item-derived id is stable across the pauses of
  one decision, and the `dec-` prefix matches the kernel's id helpers.
- **Per-record vocabularies.** Rejected: a filter value nobody else uses cannot find the record.

## References

- [ADR-059: Decision store](ADR-059-decision-store-reviewable-yaml-records-now-graph-later.md)
- [ADR-060: Source of truth and approval authority](ADR-060-source-of-truth-and-approval-authority.md)
- [Colony memory concept, part 3](../../analysis/2026-10-01-neo4j-colony-memory-concept-3-graph-model-ids-provenance.md)
