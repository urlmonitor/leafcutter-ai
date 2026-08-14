---
title: "Changelog origin/main..HEAD (PR #425) — Artifact knowledge graph and Atlas trust corrections"
date: "2026-08-14"
time: "00:16"
type: manual
components: 
  - knowledge_management
  - ux_prototyping
summary: "Added a map of how every project artifact (ACs, tickets, tests, code, docs) relates to every other artifact, visualised it in the Atlas app, and fixed six accuracy issues a review found in it."
description: "8 commits: 2 Added (new artifact knowledge-graph reference doc + machine-readable graph JSON, rendered as a draggable/exportable Atlas architecture flow, superseding the old C3-005 mermaid diagram) and 6 Fixed (KM-ADM-001..006: correct two inverted trust ratings against the actual commit-guardian hook registry, record 4 unanswerable reverse lookups as explicit absent edges, render absent edges as a visually distinct gap rather than a weak link, promote AC-to-AC DEPENDS_ON/SUPERSEDED_BY to drawn traversable edges, scope the test-covers edge to diff-scoped enforcement with a coverage-backlog ratchet, and sync the prose data-map with the JSON via a parity test)."
pr: 425
diagrams: 
  - docs/architecture/diagrams/c3-005-artifact-knowledge-graph.md
  - docs/reference/artifact-knowledge-graph.graph.json
commits: 
  - ab4e2e4eb
  - 40895cc6c
  - e6a6e353e
  - b7e9919c6
  - a9eaf66ec
  - a86cb5d71
  - f19974047
  - 966e35032
breaking: false
---

## Entry

### Added

- `docs/reference/artifact-knowledge-graph-data-map.md` — a new reference documenting
  every artifact node in leafcutter-ai (AC, Ticket, Test, SourceFile, Flow, FlowNode,
  Mockup, MockData, Pattern, Component, ADR, Doc, Changelog, GitCommit) and the exact
  field that encodes each relationship between them, with a two-axis trust rating
  (enforcement x value shape) per edge and a documented ingestable rule.
- `docs/reference/artifact-knowledge-graph.graph.json` — the same map as reusable
  machine-readable JSON; the source of truth the Atlas renders and the tests assert
  against.
- Renders the graph in the Atlas Flows view as an architecture flow (React Flow):
  draggable nodes, a crossing-reduced layered layout, per-edge trust colouring, a
  clickable edge trust panel, and a dependency-free PNG copy/export.
- Supersedes the old C3-005 mermaid diagram (retained for history).

### Fixed

Six `/quick-fix` corrections found by review, each with an AC and a covering test
(KM-ADM-001..006, component `knowledge_management`):

- **KM-ADM-001** — Trust ratings are now derived from the commit-guardian hook
  *registry*, not from a hook script merely existing on disk. Corrected two inverted
  edges: `AC -> Test` via `covered_by` is enforcement "none" (`check_ac_coverage.py`
  is unregistered and never runs); `Ticket -> SourceFile` via `files_touched` is "warn"
  (`check-predone-scope` IS registered and reports).
- **KM-ADM-002** — Adds a `status` axis (present/absent) and records the four reverse
  lookups the graph cannot answer as explicit absent edges rather than omitting them:
  `SourceFile -> AC`, `Test -> SourceFile`, `Changelog -> AC`, `Mockup -> AC`.
- **KM-ADM-003** — Atlas renders an absent relation as a visually distinct gap (red,
  long open dash, a dedicated glyph, its own legend row) so a recorded gap never reads
  as a real-but-weak link.
- **KM-ADM-004** — AC-to-AC `DEPENDS_ON` and `SUPERSEDED_BY` are promoted from
  badge-only to drawn, clickable edges via a custom self-loop edge renderer, so the
  dependency relation is traversable.
- **KM-ADM-005** — The test-covers edge now states that `check-done-proof` is
  DIFF-SCOPED, and records that 244 of 607 done ACs carry no covering test tag. Adds
  a ratchet test so the backlog cannot grow.
- **KM-ADM-006** — Syncs the prose data-map with the JSON and adds a parity test
  (with a minimum-match-count floor) so the two representations cannot silently
  disagree again.

Components touched: `knowledge_management`, `ux_prototyping` (the Atlas web app).

### Known Issues

- The 244-AC untagged-coverage backlog (KM-ADM-005) is ratcheted so it cannot grow
  further, but it is not yet retired — those 244 done ACs still carry no covering
  `# covers:` test tag.
