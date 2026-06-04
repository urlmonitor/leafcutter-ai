---
title: "Write knowledge_query.py — unified cross-surface knowledge index script and /knowledge-query skill"
status: todo
components:
  - knowledge-management
created: 2026-06-04
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
ac_coverage: 0/9
files_touched:
  - scripts/knowledge_query.py
  - templates/skills/knowledge-query/SKILL.md
  - config/skill_registry.json
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# Write knowledge_query.py — unified cross-surface knowledge index script and /knowledge-query skill

## Actor / Goal

In order to let agents and humans answer "show me everything related to X" across
ALL knowledge surfaces in one command, we need a `knowledge_query.py` script that
reads `paths.json` for surface discovery, traverses tickets, ADRs, docs, agents,
skills, components, roadmap, glossary, and feedback in a single pass, extracts a
one-line description for every node, follows cross-surface edges, and dumps a flat
index in both human-readable text and JSON format.

## Context

`generate_doc_index.py` already demonstrates the description-extraction pattern
(frontmatter `description:` field with fallback to first non-blank line). The
existing `roadmap_query.py` demonstrates the argparse structure and error-handling
convention used by all scripts in this repo.

The new script extends these patterns to all eight knowledge surfaces and adds edge
traversal. It does not replace `generate_doc_index.py` (which produces `docs/INDEX.md`
for the build pipeline) — it is a separate query-time utility.

### Surface definitions

| Surface | Source file(s) | Edge fields |
|---------|---------------|-------------|
| agents | `config/agent_registry.json` | `spawn_allowlist`, `spawned_by`, `skills_used` |
| skills | `config/skill_registry.json` | `dependencies` |
| tickets | `tickets/00_inbox/**/*.md`, `tickets/01_todo/**/*.md` | `depends_on`, `files_touched`, `agents` map |
| docs | `docs/**/*.md` (non-ticket) | `related_docs`, `related_code` |
| ADRs | `docs/architecture/adrs/*.md` | `related_docs`, `related_code` |
| components | `docs/architecture/components/*.md` | `related_docs`, `related_code` |
| roadmap | `docs/roadmap.json` | phase → tickets (via `roadmap_phase` on tickets) |
| glossary | `docs/glossary.md` | none (leaf surface) |

`paths.json` is the single source of discovery. The script reads it to locate
each surface root rather than hardcoding paths. When a surface path carries
`optional: true` and the path does not exist, the surface is silently skipped.

### Output format

```
# Knowledge Index
Generated: 2026-06-04T09:00:00Z
Surfaces: 8   Nodes: 142   Edges: 287

## agents (62)
  [agent] business-analyst — Extracts structured requirements from user requests...
    -> skills: ticket-authoring, test-planner
    -> spawned_by: create-ticket

  [agent] python-coder — Writes production-quality Python following repo conventions.
    -> spawned_by: ticket-supervisor

## tickets (14)
  [ticket] TICKET-20260604-KnowledgeQueryScript — Write knowledge_query.py...
    -> depends_on: (none)
    -> files_touched: scripts/knowledge_query.py

...
```

JSON output (`--format json`) produces `{"nodes": [...], "edges": [...]}` where
each node has `{id, surface, title, description, path}` and each edge has
`{source, target, type}`.

### CLI flags

```
python scripts/knowledge_query.py --query "roadmap"        # filter nodes by keyword
python scripts/knowledge_query.py --surface agents         # restrict to one surface
python scripts/knowledge_query.py --format json            # machine-readable output
python scripts/knowledge_query.py --edges                  # include edge list in output
python scripts/knowledge_query.py --project-root <path>   # run from outside project root
```

Without `--query`, the script dumps the full index for all surfaces.

### Skill registration

After the script is written, a `/knowledge-query` skill must be registered:
- Template at `templates/skills/knowledge-query/SKILL.md`
- Entry added to `config/skill_registry.json`

The skill wraps the CLI invocation pattern — same purpose as `/roadmap-query` but
for cross-surface knowledge.

## Acceptance Criteria

- [ ] AC-1: Running `python scripts/knowledge_query.py` without flags produces a
  human-readable index covering all eight surfaces, with at least one node per
  surface that has a non-empty `description` field.
- [ ] AC-2: Running with `--format json` produces valid JSON with top-level keys
  `nodes` and `edges`; each node has `id`, `surface`, `title`, `description`, and
  `path` fields; each edge has `source`, `target`, and `type` fields.
- [ ] AC-3: Running with `--query <keyword>` returns only nodes whose `title` or
  `description` contains the keyword (case-insensitive); nodes from all surfaces
  are included in the search scope.
- [ ] AC-4: Running with `--surface agents` returns only nodes from the `agents`
  surface and their direct edges.
- [ ] AC-5: All paths are discovered via `paths.json`; no surface path is hardcoded
  in `knowledge_query.py`. When a surface path is marked `optional: true` and the
  directory does not exist, the surface is skipped without error.
- [ ] AC-6: When `paths.json` is absent, the script exits with a clean error message
  (`ERROR: config/paths.json not found.`) and no Python traceback.
- [ ] AC-7: The script is pure stdlib Python (no imports outside the standard library).
  Running `python -c "import knowledge_query"` from the scripts directory succeeds
  with only stdlib present.
- [ ] AC-8: `templates/skills/knowledge-query/SKILL.md` exists, follows the same
  frontmatter schema as `templates/skills/roadmap-query/SKILL.md`, and documents all
  CLI flags with at least one example invocation per flag.
- [ ] AC-9: An entry for `knowledge-query` is present in `config/skill_registry.json`
  with `portable: true` and `template_path: "leafcutter/templates/skills/knowledge-query/"`.

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| AC-1 |      |                |           |
| AC-2 |      |                |           |
| AC-3 |      |                |           |
| AC-4 |      |                |           |
| AC-5 |      |                |           |
| AC-6 |      |                |           |
| AC-7 |      |                |           |
| AC-8 |      |                |           |
| AC-9 |      |                |           |

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder

**Deliverable 1 — `scripts/knowledge_query.py`**

Module-level docstring must follow the `roadmap_query.py` convention:
```python
"""
MODULE: knowledge_query
GOAL: Single-pass traversal of all knowledge surfaces defined in paths.json.
      Produces a flat node+edge index for cross-surface search and graph export.
BUSINESS CONTEXT: Gives agents and humans a one-command answer to
    "show me everything related to X" across all leafcutter knowledge surfaces.
ARCHITECTURE: ...
"""
```

Key implementation points:

1. **Surface loader** — a `load_surfaces(project_root, paths_json)` function that
   reads `paths.json`, resolves each surface root, and returns a dict of
   `{surface_name: Path}`. Skip surfaces where the path does not exist and the
   key has an `_optional: true` sibling (match the naming convention in paths.json,
   e.g. `explanation_optional: true`).

2. **Node extractor** — a `extract_nodes(surface, path)` generator that yields
   `NodeRecord(id, surface, title, description, path)`. Description extraction
   logic: read frontmatter `description:` field first; if absent, fall back to
   the first non-blank, non-heading line of the body (replicating
   `generate_doc_index.py`'s pattern). For JSON registries (agents, skills,
   roadmap), extract from the list items directly.

3. **Edge extractor** — an `extract_edges(surface, record, raw_data)` generator
   that yields `EdgeRecord(source_id, target_id, edge_type)`. Edge field mapping
   is defined in the surface definitions table above.

4. **Argparse CLI** — flags: `--query`, `--surface`, `--format` (text/json),
   `--edges`, `--project-root`. Default: text output, all surfaces, no filter.

5. **Error handling** — follow the repo's four error-handling rules (see CLAUDE.md):
   all file I/O wrapped in `try/except` with specific exception types; no bare
   excepts; no silently-swallowed exceptions.

6. **Output rendering** — `render_text(nodes, edges, query, show_edges)` and
   `render_json(nodes, edges)` as separate functions. `render_text` groups nodes
   by surface with a header line and indented edge list (see Output format section).

**Deliverable 2 — `templates/skills/knowledge-query/SKILL.md`**

Model on `templates/skills/roadmap-query/SKILL.md`. Sections required:
- YAML frontmatter with `name`, `description`, `portable: true`, `allowed-tools: Bash, Read`
- `## When to Use`
- `## Invocation` (one example per CLI flag)
- `## Output Modes` (text and JSON)
- `## Surfaces Queried` (table of all eight surfaces)
- `## Error Behaviour`

**Deliverable 3 — `config/skill_registry.json` amendment**

Add entry:
```json
{
  "id": "knowledge-query",
  "name": "Knowledge Query",
  "portable": true,
  "domain": null,
  "template_path": "leafcutter/templates/skills/knowledge-query/",
  "dependencies": []
}
```
Insert alphabetically between `glossary-bootstrap` and `package-audit`.

### test-writer

Create `unit_tests/test_knowledge_query.py`:

- `test_load_surfaces_returns_all_present_surfaces`: mock filesystem with all
  surface directories present, assert all eight keys returned.
- `test_load_surfaces_skips_optional_missing`: mark a surface optional, delete
  its directory, assert it is absent from result.
- `test_extract_nodes_uses_description_frontmatter`: file with `description:`
  field, assert `record.description` equals the frontmatter value.
- `test_extract_nodes_falls_back_to_first_body_line`: file with no `description:`
  field but body text, assert `record.description` equals first non-blank line.
- `test_extract_edges_spawn_allowlist`: agent entry with `spawn_allowlist`,
  assert edges with `type="spawn_allowlist"` are yielded.
- `test_query_filter_case_insensitive`: full index with mixed-case descriptions,
  `--query "roadmap"`, assert only matching nodes returned.
- `test_format_json_valid_schema`: render JSON output, parse with `json.loads`,
  assert top-level keys and node/edge schemas.
- `test_missing_paths_json_exits_cleanly`: no `paths.json` present, call main,
  assert `SystemExit` and message contains "paths.json not found".
- `test_stdlib_only`: introspect `knowledge_query` module's imports, assert no
  third-party packages.

### documentation-expert

After python-coder and test-runner sign off:

1. Verify `templates/skills/knowledge-query/SKILL.md` is consistent with the
   implemented CLI flags (no undocumented flags, no documented flags that do not exist).
2. Add a row to `docs/INDEX.md` for the new skill if it is not auto-generated by
   the next `generate_doc_index.py` run.
3. Add a "Knowledge Query" entry to the Architecture Reference table in `CLAUDE.md`
   pointing to the skill doc.

## Risk & Safety

- Touches money? No.
- Touches data? No — read-only traversal. No files are modified.
- Reversibility? The script is additive. Removing it does not affect any existing
  agent or build step. The skill entry in `skill_registry.json` can be removed
  without breaking anything else.
- Risk of regressions: low. The script does not integrate into the build pipeline
  by default. `generate_doc_index.py` is unchanged.
