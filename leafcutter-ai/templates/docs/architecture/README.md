---
title: "Architecture Documentation"
type: reference
status: active
created: YYYY-MM-DD
last_updated: YYYY-MM-DD
components: []
---

# Architecture Documentation

This folder contains architecture documentation for this project. The documentation
follows the C4 model (Context, Container, Component) and the Diataxis documentation
framework, enforced by agents and commit-guardian hooks shipped in leafcutter.

## Folder Layout

```
docs/architecture/
├── README.md                     # This file — folder guide and conventions index
├── FRONTMATTER.md                # Reference: every frontmatter field explained
├── adrs/
│   ├── README.md                 # ADR folder guide and naming convention
│   ├── ADR-template.md           # Copy this when authoring a new ADR
│   └── ADR-NNN-<slug>.md         # Numbered decision records (ADR-001, ADR-002, …)
├── c1-001-system-context.md      # L1: System-context diagram (one per project)
├── c2-NNN-<slug>.md              # L2: Container diagrams (services, databases, queues)
└── c3-NNN-<slug>.md              # L3: Component diagrams (modules within containers)
```

### File-naming convention

Architecture diagram files use the prefix convention `c{level}-{seq:03d}-{slug}.md`:

| Prefix | C4 Level | Description |
|--------|----------|-------------|
| `c1-`  | L1 — Context   | System boundary and external actors |
| `c2-`  | L2 — Container | Services, databases, messaging queues |
| `c3-`  | L3 — Component | Modules and packages within a container |

Sequence numbers are zero-padded to three digits and monotonically increasing
within each level. Slugs are lowercase, hyphen-separated, 3–6 words. See
`FRONTMATTER.md` for the `diagram_type` values valid at each level.

## Frontmatter Quick Reference

Every architecture doc requires YAML frontmatter between `---` delimiters. The
minimum required fields are:

```yaml
---
title: "Human-readable title"
type: reference          # or adr — see FRONTMATTER.md for full list
status: active           # active | draft | deprecated
created: YYYY-MM-DD
last_updated: YYYY-MM-DD
components: []           # component IDs from docs/components.json
flight_level: L2-Container  # for diagram docs — L1-Context | L2-Container | L3-Component
diagram_type: dataflow   # for diagram docs — see FRONTMATTER.md for enum
parent: null             # or path to parent diagram
children: []             # paths to child diagrams
root: false              # true only for the single L1 system-context doc
affects_diagrams: []     # for ADRs — paths to diagrams this decision affects
related_adrs: []         # for diagram docs — paths to ADRs that govern this diagram
---
```

For the full field reference and all allowed enum values, read `FRONTMATTER.md`.

## Conventions

### Bidirectional Linking

Every architecture diagram that is governed by an ADR must appear in the ADR's
`affects_diagrams:` list. The diagram must list the ADR in its `related_adrs:` list.
Both directions must be present — commit-guardian rejects one-sided links.

### Diagrams Before Coders

Architecture diagrams are the source of truth for system structure. When a code
change would alter the system boundary, data flow, or component topology, the
diagram must be updated in the same commit (or before). Use `[NO-ARCH-UPDATE]`
in the commit message to bypass when the change is a pure rename or vendored code.

### ADR Lifecycle

ADRs start at `status: Proposed`. The author or team promotes them to `Accepted`
when the decision is adopted. Superseded ADRs are marked `status: Superseded` and
cross-link to the superseding ADR. Never delete ADRs.

## See Also

- `FRONTMATTER.md` — full frontmatter field reference
- `adrs/README.md` — ADR folder guide
- `adrs/ADR-template.md` — template for new ADRs
- `c1-001-system-context.md` — starter L1 diagram (edit after seeding)
