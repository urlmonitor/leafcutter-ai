---
title: "Architecture Decision Records"
type: reference
status: active
created: YYYY-MM-DD
last_updated: YYYY-MM-DD
components: []
---

# Architecture Decision Records

This folder contains Architecture Decision Records (ADRs) for this project. ADRs
capture significant architectural decisions — the context that motivated them, the
decision made, its consequences, and alternatives that were considered and rejected.

## Naming Convention

ADR filenames follow the pattern `ADR-NNN-<slug>.md`:

- `NNN` is a zero-padded three-digit sequence number (ADR-001, ADR-002, …).
- `<slug>` is a lowercase, hyphen-separated 3–6 word summary of the decision.
- Example: `ADR-001-use-timescaledb-for-time-series.md`

The sequence number is monotonically increasing and never reused. When an ADR is
superseded, the old ADR is marked `status: Superseded` and cross-links to the new
one — it is never deleted.

## Lifecycle

| Status | Meaning |
|--------|---------|
| `Proposed` | Draft: authored but not yet reviewed or adopted. |
| `Accepted` | Adopted: the team has committed to this decision. |
| `Deprecated` | No longer in force but kept for historical context. |
| `Superseded` | Replaced by a newer ADR (cross-link required). |

ADRs start at `Proposed`. The team promotes them to `Accepted` when the decision
is confirmed. Only the author or team may change the status.

## Bidirectional Linking Rule

Every ADR that affects an architecture diagram must list the diagram path in its
`affects_diagrams:` frontmatter field. The diagram must reciprocate by listing the
ADR path in its `related_adrs:` field. The `check-adr-cross-reference` commit-guardian
hook enforces both directions and will block a commit that breaks the invariant.

Example ADR frontmatter:

```yaml
affects_diagrams:
  - docs/architecture/c2-001-container-overview.md
```

Example diagram frontmatter:

```yaml
related_adrs:
  - docs/architecture/adrs/ADR-001-<slug>.md
```

## Authoring a New ADR

Use the `adr-author` agent:

1. Describe the decision to `documentation-expert`.
2. `documentation-expert` dispatches `adr-author` with the decision specification.
3. `adr-author` reads this README, picks the next free ADR number, writes the file,
   and returns a structured payload.

Or copy `ADR-template.md` and fill in the sections manually.

## Index

<!-- Maintain this index as new ADRs are added. -->

| ADR | Title | Status |
|-----|-------|--------|
| _Add rows here as ADRs are created_ | | |

## See Also

- `ADR-template.md` — copy this when authoring a new ADR
- `../README.md` — architecture folder conventions
- `../FRONTMATTER.md` — frontmatter field reference
