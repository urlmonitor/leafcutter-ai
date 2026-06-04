---
title: "EPIC: Unified Knowledge Graph Query Layer"
type: epic
status: todo
components:
  - knowledge-management
  - build_pipeline
created: 2026-06-04
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: true
requires_adr: false
---

# EPIC: Unified Knowledge Graph Query Layer

## Goal

In order to give leafcutter agents and humans a single command that traverses
ALL knowledge surfaces in one pass, we need to add a unified knowledge query
script (`knowledge_query.py`), enforce the `description:` frontmatter field on
all docs, ADRs, and component files, and ship an interactive D3.js force-directed
visualization of the cross-surface knowledge graph — so that any agent can answer
"show me everything related to X" without reading every file individually.

## Context

Leafcutter already has richer, more structured data than comparable tools
(62-agent registry with bidirectional spawn graph, 26-skill registry, ticket DAG
computation, AC traceability, build manifest drift detection, feedback lifecycle,
package boundary classification). However, three capabilities are absent:

1. **No unified query surface.** Each knowledge surface (tickets, ADRs, docs,
   agents, skills, components, roadmap, glossary, feedback) is queryable only in
   isolation. There is no single command that scans descriptions and follows edges
   across all surfaces at once. The Catalyx pattern of a flat index that an agent
   can scan to answer "everything related to X" does not yet exist in leafcutter.

2. **Inconsistent `description:` coverage.** The agent registry and skill registry
   both carry one-line `description` fields for every entry. Doc files, ADRs, and
   component files have the field sporadically. `generate_doc_index.py` already
   uses the `description:` field or falls back to the first non-blank line — but
   the inconsistency means the fallback path is hit for most structured files,
   producing noisy or incomplete summaries.

3. **No graph visualization.** The edge data (spawn_allowlist, spawned_by,
   depends_on, related_docs, skills_used, files_touched) is present in structured
   files but is never rendered as a graph. There is no way to see the connectivity
   topology at a glance.

### Design constraints (settled — do not reopen)

- All scripts must be pure Python (stdlib only, no external deps).
- Must be portable (part of the leafcutter package, not project-specific).
- `knowledge_query.py` reads `paths.json` for surface discovery (no hardcoded paths).
- The query skill `/knowledge-query` is usable both by humans (CLI) and by agents
  as part of research workflows.
- The visualization script is a separate ticket that depends on the query script;
  it reuses the same index/edge extraction logic rather than reimplementing it.
- Description backfill is **docs, ADRs, and component files only** — agent templates
  and SKILL.md files are excluded because their registries already provide the
  description layer.

### Cross-reference

- `config/paths.json` — surface discovery SSOT (read by knowledge_query.py)
- `config/agent_registry.json` — 62-agent registry with bidirectional spawn graph
- `config/skill_registry.json` — 26-skill registry
- `scripts/generate_doc_index.py` — existing description-extraction pattern to reuse
- `scripts/roadmap_query.py` — model for CLI flag design and argparse structure

## Architecture Plan

### Diagrams

- `data_flow` diagram at `docs/architecture/components/knowledge-query-data-flow.md`
  (parent: `docs/architecture/components/`) — shows all surface inputs, edge types,
  and outputs (flat index, JSON, HTML).

### ADRs

No new ADR is required. The query script is an additive utility consistent with the
existing script convention. If enforcement requires a new pre-commit hook configuration
beyond the existing commit-guardian hooks, a supplemental ADR entry may be opened at
that time.

## Sub-ticket Table

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_knowledge_query_script.md](./01_knowledge_query_script.md) | Write `knowledge_query.py` — unified cross-surface index script and `/knowledge-query` skill | `[ ]` |
| 02 | [02_description_backfill_and_enforcement.md](./02_description_backfill_and_enforcement.md) | Backfill `description:` on all docs/ADRs/components and add pre-commit enforcement | `[ ]` |
| 03 | [03_knowledge_graph_visualization.md](./03_knowledge_graph_visualization.md) | Write `visualise_knowledge_graph.py` — D3.js force-directed HTML from the knowledge index | `[ ]` |

### Dependency order

```
01_knowledge_query_script
        |
        v
03_knowledge_graph_visualization   (depends on 01 — reuses edge extraction)

02_description_backfill_and_enforcement   (independent — can run in parallel with 01)
```

Tickets 01 and 02 can run in parallel. Ticket 03 must wait for ticket 01 to be
signed off (it imports or reuses the index extraction logic from `knowledge_query.py`).

## Risk & Safety

- Touches money? No.
- Touches data? No — all scripts are read-only queries except the backfill pass
  (ticket 02), which writes only to doc frontmatter. The backfill is scoped to a
  single migration script and guarded by a dry-run flag.
- Reversibility? High — new scripts are additive. Enforcement hook can be disabled
  by removing it from `.pre-commit-config.yaml`. The visualization HTML is written
  to `/tmp` (never committed). Description fields added to frontmatter are inert to
  existing agents that do not read them.
- Risk of regressions: low for tickets 01 and 03 (read-only). Medium for ticket 02
  (writes frontmatter to many files — must be tested against a dry-run mode first).
