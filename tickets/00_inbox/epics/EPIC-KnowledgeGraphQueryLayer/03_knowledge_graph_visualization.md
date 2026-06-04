---
title: "Write visualise_knowledge_graph.py — D3.js force-directed graph from the knowledge index"
status: todo
components:
  - knowledge-management
created: 2026-06-04
depends_on:
  - tickets/00_inbox/epics/EPIC-KnowledgeGraphQueryLayer/01_knowledge_query_script.md
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
ac_coverage: 0/12
files_touched:
  - scripts/visualise_knowledge_graph.py
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

# Write visualise_knowledge_graph.py — D3.js force-directed graph from the knowledge index

## Actor / Goal

In order to let humans see the connectivity topology of all leafcutter knowledge
surfaces at a glance without reading individual files, we need a
`visualise_knowledge_graph.py` script that reads the node+edge index produced by
`knowledge_query.py`, builds a self-contained D3.js force-directed HTML file, and
opens it in the default browser — with no external dependencies and no output files
committed to the repo.

## Context

This ticket is the "nice-to-have" visualization piece of the EPIC. It depends on
`01_knowledge_query_script.md` because it reuses `knowledge_query.py`'s
`load_surfaces`, `extract_nodes`, and `extract_edges` functions rather than
reimplementing surface traversal. The two scripts must not duplicate surface
discovery or edge extraction logic.

### Design constraints (settled)

- Pure Python stdlib only — no `pip install` required.
- Output is a single self-contained `.html` file written to `/tmp/` (never
  committed to the repo).
- The HTML file contains inlined D3.js (fetched from a CDN at render time by the
  browser, not downloaded by the Python script — the Python script only writes the
  HTML template with the data embedded as JSON).
- Script is approximately 100–150 lines, consistent with the Catalyx reference
  (`visualise.py` was ~100 lines).

### Graph specification

**Nodes:** Every structured file = one node. Colored by surface type:
- `agent` → teal (`#2dd4bf`)
- `skill` → red (`#f87171`)
- `ticket` → yellow (`#fbbf24`)
- `doc` → green (`#4ade80`)
- `adr` → purple (`#c084fc`)
- `component` → blue (`#60a5fa`)
- `roadmap` → orange (`#fb923c`)
- `glossary` → gray (`#94a3b8`)

**Node sizing:** Radius proportional to edge-degree (min 4px, max 18px, linear
scale between min-degree and max-degree in the graph).

**Edges:** All cross-reference edges from `extract_edges()`. Edge color is a
lower-opacity version of the source node's surface color.

**Interactivity:**
- Hover on a node highlights all its direct neighbors and dims all other nodes.
- Click a node pins it; click again unpins.
- Node label shows on hover (the `title` field from the node record).
- Legend in the top-right corner shows surface → color mapping.

### Invocation

```bash
python scripts/visualise_knowledge_graph.py
# Writes to /tmp/leafcutter_knowledge_graph.html and opens in default browser.

python scripts/visualise_knowledge_graph.py --output /tmp/my_graph.html
# Custom output path.

python scripts/visualise_knowledge_graph.py --no-open
# Write the file but do not open the browser (useful in headless environments).

python scripts/visualise_knowledge_graph.py --surface agents skills
# Only include nodes and edges from the specified surfaces.

python scripts/visualise_knowledge_graph.py --project-root <path>
# Run from outside project root.
```

### Integration with knowledge_query.py

The script imports `knowledge_query` as a sibling module using the same
`importlib.util` pattern already established in `roadmap_query.py`:

```python
import importlib.util as _ilu
_kq = _ilu.module_from_spec(
    _s := _ilu.spec_from_file_location(
        "knowledge_query",
        Path(__file__).resolve().parent / "knowledge_query.py"
    )
)
_s.loader.exec_module(_kq)
```

Then calls `_kq.load_surfaces(...)`, `_kq.extract_nodes(...)`, and
`_kq.extract_edges(...)` directly. No duplication of surface traversal or edge
extraction.

## Agent Contracts

### python-coder

- [ ] AC-1: Running `python scripts/visualise_knowledge_graph.py --no-open` writes a
  file to `/tmp/leafcutter_knowledge_graph.html` (or `--output` path) that is valid
  HTML containing at least one `<script>` block with embedded node and edge JSON data.
- [ ] AC-2: The embedded JSON contains `nodes` and `edges` arrays. Every node has
  `id`, `surface`, `title`, and a `color` field derived from the surface-color mapping.
  Every edge has `source`, `target`, and `type`.
- [ ] AC-3: The script is pure stdlib Python; it does NOT attempt to download D3.js at
  run time — the HTML references D3 from `https://d3js.org/d3.v7.min.js` (CDN).
  Running the script in a network-isolated environment with `--no-open` succeeds
  (writes the HTML file without error).
- [ ] AC-4: The script delegates surface traversal exclusively to `knowledge_query.py`
  (calls `load_surfaces`, `extract_nodes`, `extract_edges`). No surface path is
  hardcoded in `visualise_knowledge_graph.py` itself.
- [ ] AC-5: Running with `--surface agents skills` produces a graph containing only
  nodes from the `agents` and `skills` surfaces and edges between them; nodes from
  all other surfaces are absent from the embedded JSON.
- [ ] AC-6: The script accepts `--project-root <path>` and passes it to
  `knowledge_query.py`'s surface loader without error.
- [ ] AC-7: When `knowledge_query.py` is not found (sibling module missing), the
  script exits with a clean error message `ERROR: knowledge_query.py not found at
  <expected_path>.` and no Python traceback.
- [ ] AC-8: The script imports `knowledge_query.py` as a sibling module using
  `importlib.util.spec_from_file_location` and `module_from_spec` — the same pattern
  used by `roadmap_query.py`. No `sys.path` manipulation or relative imports.
  <!-- scope: integration -->

**Delivers to test-writer:**
```json
{
  "module_path": "scripts/visualise_knowledge_graph.py",
  "public_constants": {
    "SURFACE_COLORS": "dict[str, str] — maps surface name to hex color"
  },
  "cli_flags": ["--output", "--no-open", "--surface", "--project-root"],
  "exit_codes": {"0": "success", "1": "knowledge_query.py not found or runtime error"}
}
```

**Delivers to documentation-expert:**
```json
{
  "script_path": "scripts/visualise_knowledge_graph.py",
  "doc_target": "docs/architecture/agent_knowledge_system.md (new ## Visualization section)",
  "claude_md_table_entry": "Knowledge Graph Visualization",
  "cli_flags": ["--output", "--no-open", "--surface", "--project-root"]
}
```

**Depends on:** ticket 01's `knowledge_query.py` public API (`load_surfaces`, `extract_nodes`, `extract_edges`).

#### Implementation guidance

Module-level docstring:
```python
"""
MODULE: visualise_knowledge_graph
GOAL: Generate a self-contained D3.js force-directed HTML visualization of the
      leafcutter knowledge graph from all surfaces defined in paths.json.
BUSINESS CONTEXT: Lets humans see the cross-surface connectivity topology at a
      glance — which agents spawn which, which tickets depend on which, which
      docs are referenced by which agents.
ARCHITECTURE: Delegates surface traversal and edge extraction to knowledge_query.py
      (sibling module, loaded via importlib.util). Embeds node/edge JSON into an
      HTML template string. Writes to /tmp. Opens in default browser via
      webbrowser.open(). Pure stdlib. ~120 lines.
"""
```

Key implementation points:

1. **Module loader** — use `importlib.util` pattern from `roadmap_query.py` to load
   `knowledge_query` as a sibling. On `FileNotFoundError`, exit cleanly per AC-7.

2. **Surface color map** — a module-level dict `SURFACE_COLORS` mapping each surface
   name to its hex color. Used for both node `color` field and edge rendering in D3.

3. **Data assembly** — call `_kq.load_surfaces(project_root, paths_json)`, then
   `_kq.extract_nodes()` and `_kq.extract_edges()` for each surface. Apply
   `--surface` filter if specified. Add `color` field to each node record.
   Serialize to JSON string.

4. **HTML template** — an `HTML_TEMPLATE` module-level constant (multiline string)
   containing:
   - `<!DOCTYPE html>` with a single `<div id="graph">` container.
   - `<script src="https://d3js.org/d3.v7.min.js"></script>` (CDN reference only).
   - A `<script>` block with `const DATA = __DATA_JSON__;` (Python replaces the
     placeholder with the serialized JSON).
   - D3 force simulation setup: `forceSimulation`, `forceManyBody`, `forceLink`,
     `forceCenter`.
   - Node circles colored by `d.color`, radius by degree.
   - Edge lines with opacity 0.4.
   - Hover handler: dim non-neighbors, show tooltip with `d.title`.
   - Legend: `<g>` elements in top-right corner, one row per surface with color dot
     and label.
   The template is written inline in the Python source — no separate `.html` file
   to maintain.

5. **Output and browser open** — write the rendered HTML to the output path. Unless
   `--no-open`, call `webbrowser.open(f"file://{output_path.resolve()}")`.

6. **Argparse** — flags: `--output` (default `/tmp/leafcutter_knowledge_graph.html`),
   `--no-open`, `--surface` (nargs=`+`), `--project-root`.

7. **Error handling** — wrap all file I/O per repo rules. On empty graph (zero nodes),
   print a warning and still write the HTML (D3 handles empty data gracefully).

---

### test-writer

- [ ] AC-9: `unit_tests/test_visualise_knowledge_graph.py` exists with tests covering:
  `test_writes_html_file`, `test_embedded_json_valid`, `test_nodes_have_color_field`,
  `test_surface_filter_excludes_others`, `test_no_d3_download_in_script`,
  `test_missing_kq_module_exits_cleanly`, and `test_project_root_flag_passed_to_kq`.
- [ ] AC-10: All tests in `test_visualise_knowledge_graph.py` fail (RED) before
  python-coder runs and pass (GREEN) after python-coder delivers.
  <!-- scope: integration -->

**Depends on python-coder:** public constants (`SURFACE_COLORS`), CLI flags, and exit
codes from the Delivers-to block above.

#### Test specification

Create `unit_tests/test_visualise_knowledge_graph.py`.

Because the script writes HTML to disk, tests use `tmp_path` (pytest fixture) for
output path injection, and mock the `knowledge_query` module's functions to avoid
needing a real project structure.

- `test_writes_html_file`: call with `--no-open`, assert output file exists and
  contains `<!DOCTYPE html>`.
- `test_embedded_json_valid`: parse the `const DATA = ` block from the HTML,
  assert valid JSON with `nodes` and `edges` keys.
- `test_nodes_have_color_field`: mock `extract_nodes` returning one agent node,
  assert embedded node has `color` matching `SURFACE_COLORS["agent"]`.
- `test_surface_filter_excludes_others`: call with `--surface agents`, mock data
  with agent and ticket nodes, assert only agent nodes in embedded JSON.
- `test_no_d3_download_in_script`: read the source of `visualise_knowledge_graph.py`,
  assert `urllib` / `requests` / `http.client` are not imported.
- `test_missing_kq_module_exits_cleanly`: rename/hide sibling module, call main,
  assert `SystemExit` and message contains "knowledge_query.py not found".
- `test_project_root_flag_passed_to_kq`: mock `load_surfaces`, assert it is called
  with the value passed to `--project-root`.

---

### documentation-expert

- [ ] AC-11: `docs/architecture/agent_knowledge_system.md` contains a `## Visualization`
  section that describes `visualise_knowledge_graph.py`, its output format, and how to
  invoke it with at least one example command.
- [ ] AC-12: The Architecture Reference table in `CLAUDE.md` contains a "Knowledge Graph
  Visualization" row pointing to `scripts/visualise_knowledge_graph.py`.

**Depends on python-coder:** script path and CLI flags from the Delivers-to block above.

#### Tasks

1. Add a one-paragraph note to `docs/architecture/agent_knowledge_system.md` under
   a new `## Visualization` section describing `visualise_knowledge_graph.py`,
   its output, and how to invoke it.
2. Add the script to the Architecture Reference table in `CLAUDE.md` (same table
   that lists Agent Knowledge Plane, Agent Knowledge System, Agent Delivery Workflows).

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
- Touches data? No — read-only. Output goes to `/tmp` and is never committed.
- Reversibility? Fully reversible — delete the script to remove the feature. No
  build step depends on it.
- Risk of regressions: low. The script is standalone and does not integrate into
  the build pipeline. The only coupling is the import of `knowledge_query.py` —
  if that module's public API changes, this script must be updated correspondingly.
  The `depends_on` link ensures ticket 01 is complete before this ticket is driven.
- Browser-open note: `webbrowser.open()` is a no-op in headless CI environments.
  The `--no-open` flag and the AC-3 test ensure the script does not fail in CI.
