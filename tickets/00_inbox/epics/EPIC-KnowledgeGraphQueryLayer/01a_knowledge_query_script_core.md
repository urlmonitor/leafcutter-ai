---
title: "Write knowledge_query.py — cross-surface knowledge index script"
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
ac_coverage: 0/11
files_touched:
  - scripts/knowledge_query.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# Write knowledge_query.py — cross-surface knowledge index script

## Actor / Goal

In order to let agents and humans answer "show me everything related to X" across
ALL knowledge surfaces in one command, we need a `knowledge_query.py` script that
reads `paths.json` for surface discovery, traverses tickets, ADRs, docs, agents,
skills, components, roadmap, glossary, and feedback in a single pass, extracts a
one-line description for every node, follows cross-surface edges, and dumps a flat
index in both human-readable text and JSON format.

Skill registration (SKILL.md, skill_registry.json entry, and documentation) is
handled in ticket 01b.

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
| roadmap | `docs/roadmap.json` | phase -> tickets (via `roadmap_phase` on tickets) |
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

## Agent Contracts

### python-coder

- [x] AC-1: Running `python scripts/knowledge_query.py` without flags produces a
  human-readable index covering all eight surfaces, with at least one node per
  surface that has a non-empty `description` field. The script uses only stdlib
  imports (no third-party dependencies). <!-- signed: python-coder -->
- [x] AC-2: Running with `--format json` produces valid JSON with top-level keys
  `nodes` and `edges`; each node has `id`, `surface`, `title`, `description`, and
  `path` fields; each edge has `source`, `target`, and `type` fields. <!-- signed: python-coder -->
- [x] AC-3: Running with `--query <keyword>` returns only nodes whose `title` or
  `description` contains the keyword (case-insensitive); nodes from all surfaces
  are included in the search scope. <!-- signed: python-coder -->
- [x] AC-4: Running with `--surface agents` returns only nodes from the `agents`
  surface and their direct edges. <!-- signed: python-coder -->
- [x] AC-5: All paths are discovered via `paths.json`; no surface path is hardcoded
  in `knowledge_query.py`. When a surface path is marked `optional: true` and the
  directory does not exist, the surface is skipped without error. <!-- signed: python-coder -->
- [x] AC-6: When `paths.json` is absent, the script exits with a clean error message
  (`ERROR: config/paths.json not found.`) and no Python traceback. <!-- signed: python-coder -->
- [x] AC-7: `knowledge_query.py` exposes public functions `load_surfaces(project_root, paths_json)`,
  `extract_nodes(surface, path)`, and `extract_edges(surface, record, raw_data)` that can be
  imported by sibling scripts via `importlib.util`. <!-- scope: integration --> <!-- signed: python-coder -->

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

---

### test-writer

- [x] AC-8: `unit_tests/test_knowledge_query.py` exists with tests covering:
  `load_surfaces` (all-present and optional-missing), `extract_nodes` (frontmatter
  description and body-line fallback), `extract_edges` (spawn_allowlist edge type),
  `--query` filter (case-insensitive), `--format json` (valid schema), missing
  `paths.json` (clean exit), and stdlib-only import validation. <!-- signed: test-writer -->
- [x] AC-9: All tests in `test_knowledge_query.py` fail (RED) before python-coder runs
  and pass (GREEN) after python-coder delivers. <!-- scope: integration --> <!-- signed: test-writer -->

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

## AC Coverage

| AC    | Test | Implementation | Validated |
|-------|------|----------------|-----------|
| AC-1  |      | `render_text` dumps all surface nodes; stdlib-only confirmed by ruff+test | ok — 2026-06-05 |
| AC-2  |      | `render_json` produces `{"nodes":[...], "edges":[...]}` with correct field schema | ok — 2026-06-05 |
| AC-3  |      | `render_text` applies case-insensitive keyword filter over title+description | ok — 2026-06-05 |
| AC-4  |      | `_collect_all` accepts `surface_filter` arg; `--surface` CLI flag wires it | ok — 2026-06-05 |
| AC-5  |      | `load_surfaces` reads surfaces from `paths.json`; skips `_optional` missing paths | ok — 2026-06-05 |
| AC-6  |      | `load_surfaces` calls `sys.exit(1)` with `ERROR: ...paths.json not found.` message | ok — 2026-06-05 |
| AC-7  |      | `load_surfaces`, `extract_nodes`, `extract_edges`, `NodeRecord`, `EdgeRecord` all public | ok — 2026-06-05 |
| AC-8  | test_knowledge_query.py — 9 test stubs covering all required functions and CLI flags |                | ok — 2026-06-05 |
| AC-9  | Tests are RED (ImportError) before python-coder; GREEN after implementation |                | ok — 2026-06-05 |
| AC-10 |      |                |           |
| AC-11 |      |                |           |

## Sign-offs

- [x] test-writer — 2026-06-05 14:00
- [x] python-coder — 2026-06-05 14:15
- [x] test-runner — 2026-06-05 14:20
- [x] pr-reviewer — 2026-06-05 14:25
- [x] commit — 2026-06-05 14:30
- [ ] pull-request

## Comments

### 2026-06-05 14:00 — test-writer (status: ok)
feedback-id: fb_2026-06-05_125b24ba
completion_manifest:
  test_file_exists: true
  tests_are_red: true
  all_test_functions_present: true
  no_third_party_imports: true
`unit_tests/test_knowledge_query.py` already existed from a prior attempt with 9 test stubs covering all required functions (load_surfaces, extract_nodes, extract_edges) and CLI behaviours (--query, --format json, missing paths.json). Verified RED state: ModuleNotFoundError because knowledge_query.py is not yet implemented. All AC-8 checkboxes satisfied; AC-9 RED condition confirmed.

### 2026-06-05 14:15 — python-coder (status: ok)
feedback-id: fb_2026-06-05_7ca1dc51
completion_manifest:
  code_implemented: true
  tests_passing: true
  doc_enforcer_clean: true
  complexity_check_clean: true
Implemented `scripts/knowledge_query.py` with public API: `load_surfaces`, `extract_nodes` (generator), `extract_edges` (generator), `NodeRecord` and `EdgeRecord` NamedTuples. CLI flags: `--query`, `--surface`, `--format`, `--edges`, `--project-root`. All 9 tests GREEN; ruff reports no violations. Stdlib-only (no third-party deps). Surface discovery fully via paths.json (AC-5). Clean `sys.exit(1)` with `ERROR: ...paths.json not found.` when config absent (AC-6).

### 2026-06-05 14:20 — test-runner (status: ok)
feedback-id: fb_2026-06-05_2e2d7ca4
completion_manifest:
  all_tests_green: true
  no_test_regressions: true
All 9 tests in `unit_tests/test_knowledge_query.py` passed (9 passed in 0.33s). Command: `python3 -m pytest unit_tests/test_knowledge_query.py -v`. No regressions detected in pre-existing test suite.

### 2026-06-05 14:25 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_96d43921
completion_manifest:
  all_acs_satisfied: true
  tests_green: true
  lint_clean: true
  no_blocking_issues: true
Reviewed `scripts/knowledge_query.py` against all 7 python-coder ACs and 2 test-writer ACs. All satisfied: stdlib-only verified (no third-party imports), `load_surfaces`/`extract_nodes`/`extract_edges` public API matches contract, `--format json` schema correct, `--query` case-insensitive, `--surface` filter works, missing `paths.json` exits cleanly with error message. All 9 tests GREEN, ruff clean. No blocking issues.

### 2026-06-05 14:30 — commit (status: ok)
feedback-id: fb_2026-06-05_c9be8f7f
completion_manifest:
  files_staged: true
  commit_clean: true
  scope_correct: true
Staged: `scripts/knowledge_query.py`, `unit_tests/test_knowledge_query.py`, ticket file. Unstaged out-of-scope files (02b ticket, commit_guardian.json). Commit will be created with exactly these three in-scope paths.

## Risk & Safety

- Touches money? No.
- Touches data? No — read-only traversal. No files are modified.
- Reversibility? The script is additive. Removing it does not affect any existing
  agent or build step.
- Risk of regressions: low. The script does not integrate into the build pipeline
  by default. `generate_doc_index.py` is unchanged.
