---
title: "Write visualise_knowledge_graph.py — core HTML generation and D3.js data embedding"
status: done
components:
  - knowledge-management
created: 2026-06-04
depends_on:
  - tickets/00_inbox/epics/EPIC-KnowledgeGraphQueryLayer/01a_knowledge_query_script_core.md
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
ac_coverage: 0/10
files_touched:
  - scripts/visualise_knowledge_graph.py
  - docs/architecture/agent_knowledge_system.md
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# Write visualise_knowledge_graph.py — core HTML generation and D3.js data embedding

## Actor / Goal

In order to let humans see the connectivity topology of all leafcutter knowledge
surfaces at a glance without reading individual files, we need a
`visualise_knowledge_graph.py` script that reads the node+edge index produced by
`knowledge_query.py`, builds a self-contained D3.js force-directed HTML file, and
opens it in the default browser — with no external dependencies and no output files
committed to the repo.

## Context

This ticket covers the core functionality of the visualization script: loading data
from `knowledge_query.py`, assembling the graph JSON, embedding it in an HTML
template with D3.js, and writing the output file. CLI flags `--output` and `--no-open`
are in scope; the `--surface` and `--project-root` flags are deferred to ticket 03b.

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

### Invocation (this ticket)

```bash
python scripts/visualise_knowledge_graph.py
# Writes to /tmp/leafcutter_knowledge_graph.html and opens in default browser.

python scripts/visualise_knowledge_graph.py --output /tmp/my_graph.html
# Custom output path.

python scripts/visualise_knowledge_graph.py --no-open
# Write the file but do not open the browser (useful in headless environments).
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

- [x] AC-1: Running `python scripts/visualise_knowledge_graph.py --no-open` writes a
  file to `/tmp/leafcutter_knowledge_graph.html` (or `--output` path) that is valid
  HTML containing at least one `<script>` block with embedded node and edge JSON data. <!-- signed: python-coder -->
- [x] AC-2: The embedded JSON contains `nodes` and `edges` arrays. Every node has
  `id`, `surface`, `title`, and a `color` field derived from the surface-color mapping.
  Every edge has `source`, `target`, and `type`. <!-- signed: python-coder -->
- [x] AC-3: The script is pure stdlib Python; it does NOT attempt to download D3.js at
  run time — the HTML references D3 from `https://d3js.org/d3.v7.min.js` (CDN).
  Running the script in a network-isolated environment with `--no-open` succeeds
  (writes the HTML file without error). <!-- signed: python-coder -->
- [x] AC-4: The script delegates surface traversal exclusively to `knowledge_query.py`
  (calls `load_surfaces`, `extract_nodes`, `extract_edges`). No surface path is
  hardcoded in `visualise_knowledge_graph.py` itself. <!-- signed: python-coder -->
- [x] AC-5: When `knowledge_query.py` is not found (sibling module missing), the
  script exits with a clean error message `ERROR: knowledge_query.py not found at
  <expected_path>.` and no Python traceback. <!-- signed: python-coder -->
- [x] AC-6: The script imports `knowledge_query.py` as a sibling module using
  `importlib.util.spec_from_file_location` and `module_from_spec` — the same pattern
  used by `roadmap_query.py`. No `sys.path` manipulation or relative imports.
  <!-- scope: integration --> <!-- signed: python-coder -->

**Delivers to test-writer:**
```json
{
  "module_path": "scripts/visualise_knowledge_graph.py",
  "public_constants": {
    "SURFACE_COLORS": "dict[str, str] — maps surface name to hex color"
  },
  "cli_flags": ["--output", "--no-open"],
  "exit_codes": {"0": "success", "1": "knowledge_query.py not found or runtime error"}
}
```

**Delivers to documentation-expert:**
```json
{
  "script_path": "scripts/visualise_knowledge_graph.py",
  "doc_target": "docs/architecture/agent_knowledge_system.md (new ## Visualization section)",
  "claude_md_table_entry": "Knowledge Graph Visualization",
  "cli_flags": ["--output", "--no-open"]
}
```

**Depends on:** ticket 01a's `knowledge_query.py` public API (`load_surfaces`, `extract_nodes`, `extract_edges`).

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
   `knowledge_query` as a sibling. On `FileNotFoundError`, exit cleanly per AC-5.

2. **Surface color map** — a module-level dict `SURFACE_COLORS` mapping each surface
   name to its hex color. Used for both node `color` field and edge rendering in D3.

3. **Data assembly** — call `_kq.load_surfaces(project_root, paths_json)`, then
   `_kq.extract_nodes()` and `_kq.extract_edges()` for each surface. Add `color`
   field to each node record. Serialize to JSON string.

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
   `--no-open`. (Note: `--surface` and `--project-root` are added in ticket 03b.)

7. **Error handling** — wrap all file I/O per repo rules. On empty graph (zero nodes),
   print a warning and still write the HTML (D3 handles empty data gracefully).

---

### test-writer

- [x] AC-7: `unit_tests/test_visualise_knowledge_graph.py` exists with tests covering:
  `test_writes_html_file`, `test_embedded_json_valid`, `test_nodes_have_color_field`,
  `test_no_d3_download_in_script`, and `test_missing_kq_module_exits_cleanly`. <!-- signed: test-writer -->
- [x] AC-8: All tests in `test_visualise_knowledge_graph.py` fail (RED) before
  python-coder runs and pass (GREEN) after python-coder delivers.
  <!-- scope: integration --> <!-- signed: test-writer -->

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
- `test_no_d3_download_in_script`: read the source of `visualise_knowledge_graph.py`,
  assert `urllib` / `requests` / `http.client` are not imported.
- `test_missing_kq_module_exits_cleanly`: rename/hide sibling module, call main,
  assert `SystemExit` and message contains "knowledge_query.py not found".

---

### documentation-expert

- [x] AC-9: `docs/architecture/agent_knowledge_system.md` contains a `## Visualization`
  section that describes `visualise_knowledge_graph.py`, its output format, and how to
  invoke it with at least one example command. <!-- signed: documentation-expert -->
- [x] AC-10: The Architecture Reference table in `CLAUDE.md` contains a "Knowledge Graph
  Visualization" row pointing to `scripts/visualise_knowledge_graph.py`. <!-- signed: documentation-expert -->

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
| AC-1  |      | `--no-open` writes `<!DOCTYPE html>` file with embedded `<script>` and `const DATA = ...` block | ok — 2026-06-05 |
| AC-2  |      | Node dict has `id`, `surface`, `title`, `color` from `SURFACE_COLORS`; edge dict has `source`, `target`, `type` | ok — 2026-06-05 |
| AC-3  |      | HTML template references `https://d3js.org/d3.v7.min.js`; no urllib/requests import; stdlib only | ok — 2026-06-05 |
| AC-4  |      | `_assemble_graph()` calls `kq.load_surfaces`, `kq.extract_nodes`, `kq.extract_edges`; no hardcoded paths | ok — 2026-06-05 |
| AC-5  |      | `_load_kq_module()` raises `FileNotFoundError`; `main()` catches it, prints `ERROR: knowledge_query.py not found at ...` and calls `sys.exit(1)` | ok — 2026-06-05 |
| AC-6  |      | `importlib.util.spec_from_file_location` + `module_from_spec` in `_load_kq_module()`; no `sys.path` manipulation | ok — 2026-06-05 |
| AC-7  | test_visualise_knowledge_graph.py:test_writes_html_file,test_embedded_json_valid,test_nodes_have_color_field,test_no_d3_download_in_script,test_missing_kq_module_exits_cleanly |                | ok — 2026-06-05 |
| AC-8  | test_visualise_knowledge_graph.py — all 13 tests RED (verified 2026-06-05) |                | ok — 2026-06-05 |
| AC-9  |      | Added `## Visualization` section to `docs/architecture/agent_knowledge_system.md` with output format description and 3 invocation examples | ok — 2026-06-05 |
| AC-10 |      | Added "Knowledge Graph Visualization" row to Architecture Reference table in `CLAUDE.md` pointing to `scripts/visualise_knowledge_graph.py` | ok — 2026-06-05 |

## Sign-offs

- [x] test-writer — 2026-06-05 14:30
- [x] python-coder — 2026-06-05 14:35
- [x] test-runner — 2026-06-05 14:40
- [x] documentation-expert — 2026-06-05 14:45
- [x] pr-reviewer — 2026-06-05 14:50
- [x] commit — 2026-06-05 14:55
- [x] pull-request — 2026-06-05 15:00

## Comments

### 2026-06-05 14:30 — test-writer (status: ok)
feedback-id: fb_2026-06-05_6650a4d9
completion_manifest:
  test_stubs_created: true
  all_tests_red: true
  red_baseline_captured: true
  ac_ids_covered: [UNKNOWN]
Wrote 13 failing test stubs in `unit_tests/test_visualise_knowledge_graph.py` covering the 5 named tests from AC-7 (test_writes_html_file, test_embedded_json_valid, test_nodes_have_color_field, test_no_d3_download_in_script, test_missing_kq_module_exits_cleanly) plus 8 additional structural tests (AC-1 through AC-6). All 13 tests RED (exit 1) — `_ModuleNotBuiltError` since visualise_knowledge_graph.py does not yet exist.

red_baseline:
  - test_name: test_writes_html_file
    file: unit_tests/test_visualise_knowledge_graph.py
    error: "test_visualise_knowledge_graph._ModuleNotBuiltError: /home/henzeh/projects/leafcutter/EPIC-KnowledgeGraphQueryLayer/scripts/visualise_knowledge_graph.py"
  - test_name: test_embedded_json_valid
    file: unit_tests/test_visualise_knowledge_graph.py
    error: "test_visualise_knowledge_graph._ModuleNotBuiltError: /home/henzeh/projects/leafcutter/EPIC-KnowledgeGraphQueryLayer/scripts/visualise_knowledge_graph.py"
  - test_name: test_nodes_have_color_field
    file: unit_tests/test_visualise_knowledge_graph.py
    error: "test_visualise_knowledge_graph._ModuleNotBuiltError: /home/henzeh/projects/leafcutter/EPIC-KnowledgeGraphQueryLayer/scripts/visualise_knowledge_graph.py"
  - test_name: test_no_d3_download_in_script
    file: unit_tests/test_visualise_knowledge_graph.py
    error: "FileNotFoundError: [Errno 2] No such file or directory: '.../scripts/visualise_knowledge_graph.py'"
  - test_name: test_missing_kq_module_exits_cleanly
    file: unit_tests/test_visualise_knowledge_graph.py
    error: "test_visualise_knowledge_graph._ModuleNotBuiltError: /home/henzeh/projects/leafcutter/EPIC-KnowledgeGraphQueryLayer/scripts/visualise_knowledge_graph.py"
  - test_name: test_embedded_nodes_have_required_fields
    file: unit_tests/test_visualise_knowledge_graph.py
    error: "test_visualise_knowledge_graph._ModuleNotBuiltError: /home/henzeh/projects/leafcutter/EPIC-KnowledgeGraphQueryLayer/scripts/visualise_knowledge_graph.py"
  - test_name: test_embedded_edges_have_required_fields
    file: unit_tests/test_visualise_knowledge_graph.py
    error: "test_visualise_knowledge_graph._ModuleNotBuiltError: /home/henzeh/projects/leafcutter/EPIC-KnowledgeGraphQueryLayer/scripts/visualise_knowledge_graph.py"
  - test_name: test_html_references_d3_cdn
    file: unit_tests/test_visualise_knowledge_graph.py
    error: "test_visualise_knowledge_graph._ModuleNotBuiltError: /home/henzeh/projects/leafcutter/EPIC-KnowledgeGraphQueryLayer/scripts/visualise_knowledge_graph.py"
  - test_name: test_uses_importlib_pattern
    file: unit_tests/test_visualise_knowledge_graph.py
    error: "FileNotFoundError: [Errno 2] No such file or directory: '.../scripts/visualise_knowledge_graph.py'"
  - test_name: test_agent_color_is_teal
    file: unit_tests/test_visualise_knowledge_graph.py
    error: "test_visualise_knowledge_graph._ModuleNotBuiltError: /home/henzeh/projects/leafcutter/EPIC-KnowledgeGraphQueryLayer/scripts/visualise_knowledge_graph.py"
  - test_name: test_skill_color_is_red
    file: unit_tests/test_visualise_knowledge_graph.py
    error: "test_visualise_knowledge_graph._ModuleNotBuiltError: /home/henzeh/projects/leafcutter/EPIC-KnowledgeGraphQueryLayer/scripts/visualise_knowledge_graph.py"
  - test_name: test_surface_colors_has_required_entries
    file: unit_tests/test_visualise_knowledge_graph.py
    error: "test_visualise_knowledge_graph._ModuleNotBuiltError: /home/henzeh/projects/leafcutter/EPIC-KnowledgeGraphQueryLayer/scripts/visualise_knowledge_graph.py"
  - test_name: test_ticket_color_is_yellow
    file: unit_tests/test_visualise_knowledge_graph.py
    error: "test_visualise_knowledge_graph._ModuleNotBuiltError: /home/henzeh/projects/leafcutter/EPIC-KnowledgeGraphQueryLayer/scripts/visualise_knowledge_graph.py"

### 2026-06-05 14:35 — python-coder (status: ok)
feedback-id: fb_2026-06-05_0f15fd90
completion_manifest:
  ac1_html_file_written: true
  ac2_json_nodes_edges_with_color: true
  ac3_no_d3_download_stdlib_only: true
  ac4_delegates_to_knowledge_query: true
  ac5_clean_error_on_missing_kq: true
  ac6_importlib_util_pattern: true
Implemented `scripts/visualise_knowledge_graph.py` (~150 lines). `SURFACE_COLORS` dict covers all 8 surface types plus plural aliases. `_load_kq_module()` uses `importlib.util.spec_from_file_location` + `module_from_spec` (AC-6). `main()` accepts `--output` and `--no-open` flags; handles missing `knowledge_query.py` with clean error and `sys.exit(1)` (AC-5). HTML template embeds D3 CDN reference only (AC-3). All 13 tests GREEN (13/13 passed, exit 0).

### 2026-06-05 14:40 — test-runner (status: ok)
feedback-id: fb_2026-06-05_7e81ae02
completion_manifest:
  tests_executed: true
  all_tests_green: true
  no_skipped_tests: true
Ran `python3 -m pytest unit_tests/test_visualise_knowledge_graph.py -v`. Result: 13 passed, 0 failed, exit 0. All 5 AC-7 named tests plus 8 structural tests confirmed GREEN after python-coder implementation.

### 2026-06-05 14:45 — documentation-expert (status: ok)
feedback-id: fb_2026-06-05_76f2c3a7
completion_manifest:
  visualization_section_added: true
  claude_md_table_row_added: true
Added `## Visualization` section to `docs/architecture/agent_knowledge_system.md` covering output format, the self-contained HTML file contract, CDN D3 reference, and three invocation examples (default, `--output`, `--no-open`). Added "Knowledge Graph Visualization" row to the Architecture Reference table in `CLAUDE.md` pointing to `scripts/visualise_knowledge_graph.py`.

### 2026-06-05 14:50 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_81037d01
completion_manifest:
  ac1_html_output_verified: true
  ac2_json_structure_verified: true
  ac3_no_runtime_d3_download_verified: true
  ac4_delegates_to_knowledge_query_verified: true
  ac5_clean_error_message_verified: true
  ac6_importlib_pattern_verified: true
  ac7_test_stubs_named_correctly_verified: true
  ac8_red_green_cycle_verified: true
  ac9_visualization_section_in_docs_verified: true
  ac10_claude_md_table_row_verified: true
  ruff_clean: true
  all_tests_green: true
All 10 ACs satisfied. Ruff E722/BLE001/TRY: clean. 13/13 tests GREEN. `scripts/visualise_knowledge_graph.py` is ~150 lines, stdlib-only, uses importlib.util pattern (AC-6), SURFACE_COLORS public constant (AC-2), CDN D3 reference only (AC-3). `docs/architecture/agent_knowledge_system.md` has `## Visualization` section with invocation examples. `CLAUDE.md` Architecture Reference table updated.

### 2026-06-05 14:55 — commit (status: ok)
feedback-id: fb_2026-06-05_de0eb779
completion_manifest:
  files_staged_correctly: true
  commit_succeeded: true
  no_cross_ticket_files_included: true
Committed 5 files (1031 insertions, 40 deletions) on branch `EPIC-KnowledgeGraphQueryLayer`. SHA: 425e55d. Files: `CLAUDE.md`, `docs/architecture/agent_knowledge_system.md`, `scripts/visualise_knowledge_graph.py`, `tickets/.../03a_knowledge_graph_visualization_core.md`, `unit_tests/test_visualise_knowledge_graph.py`. No cross-ticket files included.

### 2026-06-05 15:00 — pull-request (status: ok)
feedback-id: fb_2026-06-05_114bd92f
completion_manifest:
  branch_pushed: true
  pr_updated: true
Pushed branch `EPIC-KnowledgeGraphQueryLayer` to origin (54684e3..425e55d). Existing PR #63 updated with commit 425e55d. No new PR created — epic uses one PR per epic convention.

## Risk & Safety

- Touches money? No.
- Touches data? No — read-only. Output goes to `/tmp` and is never committed.
- Reversibility? Fully reversible — delete the script to remove the feature. No
  build step depends on it.
- Risk of regressions: low. The script is standalone and does not integrate into
  the build pipeline. The only coupling is the import of `knowledge_query.py` —
  if that module's public API changes, this script must be updated correspondingly.
  The `depends_on` link ensures ticket 01a is complete before this ticket is driven.
- Browser-open note: `webbrowser.open()` is a no-op in headless CI environments.
  The `--no-open` flag and the AC-3 test ensure the script does not fail in CI.
