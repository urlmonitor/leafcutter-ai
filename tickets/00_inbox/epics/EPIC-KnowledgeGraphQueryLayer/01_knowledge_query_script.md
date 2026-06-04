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
ac_coverage: 0/14
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

## Agent Contracts

### python-coder

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
- [ ] AC-8: `templates/skills/knowledge-query/SKILL.md` exists, follows the same
  frontmatter schema as `templates/skills/roadmap-query/SKILL.md`, and documents all
  CLI flags with at least one example invocation per flag.
- [ ] AC-9: An entry for `knowledge-query` is present in `config/skill_registry.json`
  with `portable: true` and `template_path: "leafcutter/templates/skills/knowledge-query/"`.
- [ ] AC-10: `knowledge_query.py` exposes public functions `load_surfaces(project_root, paths_json)`,
  `extract_nodes(surface, path)`, and `extract_edges(surface, record, raw_data)` that can be
  imported by sibling scripts via `importlib.util`. <!-- scope: integration -->

**Delivers to test-writer:**
```json
{
  "module_path": "scripts/knowledge_query.py",
  "public_api": {
    "load_surfaces": "(project_root: Path, paths_json: Path) -> dict[str, Path]",
    "extract_nodes": "(surface: str, path: Path) -> Generator[NodeRecord]",
    "extract_edges": "(surface: str, record: NodeRecord, raw_data: dict) -> Generator[EdgeRecord]",
    "NodeRecord": "namedtuple('NodeRecord', ['id', 'surface', 'title', 'description', 'path'])",
    "EdgeRecord": "namedtuple('EdgeRecord', ['source_id', 'target_id', 'edge_type'])"
  },
  "cli_flags": ["--query", "--surface", "--format", "--edges", "--project-root"],
  "exit_codes": {"0": "success", "1": "paths.json not found or runtime error"}
}
```

**Delivers to documentation-expert:**
```json
{
  "skill_template": "templates/skills/knowledge-query/SKILL.md",
  "registry_entry": "config/skill_registry.json (key: knowledge-query)",
  "cli_flags": ["--query", "--surface", "--format", "--edges", "--project-root"]
}
```

#### Implementation guidance

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

1. **Surface loader** — `load_surfaces(project_root, paths_json)` reads `paths.json`,
   resolves each surface root, returns `{surface_name: Path}`. Skip surfaces where
   path does not exist and key has `_optional: true` sibling.

2. **Node extractor** — `extract_nodes(surface, path)` generator yields
   `NodeRecord(id, surface, title, description, path)`. Description extraction:
   frontmatter `description:` first; fallback to first non-blank, non-heading body line.

3. **Edge extractor** — `extract_edges(surface, record, raw_data)` generator yields
   `EdgeRecord(source_id, target_id, edge_type)`. Edge field mapping per surface
   definitions table above.

4. **Argparse CLI** — flags: `--query`, `--surface`, `--format` (text/json),
   `--edges`, `--project-root`. Default: text output, all surfaces, no filter.

5. **Error handling** — repo's four error-handling rules: all file I/O in try/except
   with specific exception types; no bare excepts; no silently-swallowed exceptions.

6. **Output rendering** — `render_text(nodes, edges, query, show_edges)` and
   `render_json(nodes, edges)` as separate functions.

**Skill template** — model on `templates/skills/roadmap-query/SKILL.md`. Required sections:
YAML frontmatter, `## When to Use`, `## Invocation`, `## Output Modes`, `## Surfaces Queried`, `## Error Behaviour`.

**Registry entry** — insert alphabetically between `glossary-bootstrap` and `package-audit`.

---

### test-writer

- [ ] AC-11: `unit_tests/test_knowledge_query.py` exists with tests covering:
  `load_surfaces` (all-present and optional-missing), `extract_nodes` (frontmatter
  description and body-line fallback), `extract_edges` (spawn_allowlist edge type),
  `--query` filter (case-insensitive), `--format json` (valid schema), missing
  `paths.json` (clean exit), and stdlib-only import validation.
- [ ] AC-12: All tests in `test_knowledge_query.py` fail (RED) before python-coder runs
  and pass (GREEN) after python-coder delivers. <!-- scope: integration -->

**Depends on python-coder:** public API signatures (`load_surfaces`, `extract_nodes`,
`extract_edges`, `NodeRecord`, `EdgeRecord`) and CLI exit codes from the Delivers-to block above.

#### Test specification

Create `unit_tests/test_knowledge_query.py`:

- `test_load_surfaces_returns_all_present_surfaces`
- `test_load_surfaces_skips_optional_missing`
- `test_extract_nodes_uses_description_frontmatter`
- `test_extract_nodes_falls_back_to_first_body_line`
- `test_extract_edges_spawn_allowlist`
- `test_query_filter_case_insensitive`
- `test_format_json_valid_schema`
- `test_missing_paths_json_exits_cleanly`
- `test_stdlib_only`

---

### documentation-expert

- [ ] AC-13: `templates/skills/knowledge-query/SKILL.md` documents exactly the CLI flags
  that `knowledge_query.py` implements — no undocumented flags, no documented flags that
  do not exist in the script.
- [ ] AC-14: A "Knowledge Query" row is present in the Architecture Reference table in
  `CLAUDE.md` pointing to the skill doc path.

**Depends on python-coder:** skill template path and CLI flags from the Delivers-to block above.

#### Tasks

1. Verify SKILL.md consistency with implemented CLI flags.
2. Add row to `docs/INDEX.md` for the new skill if not auto-generated.
3. Add "Knowledge Query" entry to CLAUDE.md Architecture Reference table.

## AC Coverage

| AC    | Test | Implementation | Validated |
|-------|------|----------------|-----------|
| AC-1  |      |                |           |
| AC-2  |      |                |           |
| AC-3  |      |                |           |
| AC-4  |      |                |           |
| AC-5  |      |                |           |
| AC-6  |      |                |           |
| AC-7  |      |                |           |
| AC-8  |      |                |           |
| AC-9  |      |                |           |
| AC-10 |      |                |           |
| AC-11 |      |                |           |
| AC-12 |      |                |           |
| AC-13 |      |                |           |
| AC-14 |      |                |           |

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Risk & Safety

- Touches money? No.
- Touches data? No — read-only traversal. No files are modified.
- Reversibility? The script is additive. Removing it does not affect any existing
  agent or build step. The skill entry in `skill_registry.json` can be removed
  without breaking anything else.
- Risk of regressions: low. The script does not integrate into the build pipeline
  by default. `generate_doc_index.py` is unchanged.
