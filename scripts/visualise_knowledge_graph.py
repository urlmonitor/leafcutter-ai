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
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import webbrowser
from pathlib import Path

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

#: Maps each surface name to its display hex colour in the D3 graph.
SURFACE_COLORS: dict[str, str] = {
    "agent": "#2dd4bf",
    "agents": "#2dd4bf",
    "skill": "#f87171",
    "skills": "#f87171",
    "ticket": "#fbbf24",
    "tickets": "#fbbf24",
    "doc": "#4ade80",
    "docs": "#4ade80",
    "adr": "#c084fc",
    "adrs": "#c084fc",
    "component": "#60a5fa",
    "components": "#60a5fa",
    "roadmap": "#fb923c",
    "glossary": "#94a3b8",
}

# ---------------------------------------------------------------------------
# knowledge_query module loader
# ---------------------------------------------------------------------------

_KQ_PATH = Path(__file__).resolve().parent / "knowledge_query.py"


def _load_kq_module():
    """Load knowledge_query.py as a sibling module via importlib.util.

    Returns:
        The loaded knowledge_query module.

    Raises:
        FileNotFoundError: When knowledge_query.py is not found.
    """
    if not _KQ_PATH.exists():
        raise FileNotFoundError(str(_KQ_PATH))
    spec = importlib.util.spec_from_file_location("knowledge_query", _KQ_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Leafcutter Knowledge Graph</title>
<style>
  body { margin: 0; background: #0f172a; color: #e2e8f0; font-family: sans-serif; }
  svg { width: 100vw; height: 100vh; display: block; }
  .node circle { stroke: #1e293b; stroke-width: 1.5px; cursor: pointer; }
  .node text { font-size: 11px; fill: #94a3b8; pointer-events: none; }
  .link { stroke-opacity: 0.4; }
  #legend { position: fixed; top: 16px; right: 16px; background: rgba(15,23,42,0.85);
            border: 1px solid #334155; border-radius: 6px; padding: 10px 14px; }
  #legend h4 { margin: 0 0 8px 0; font-size: 12px; color: #94a3b8; text-transform: uppercase; }
  .legend-row { display: flex; align-items: center; gap: 8px; margin: 4px 0; font-size: 12px; }
  .legend-dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
  #tooltip { position: fixed; background: rgba(30,41,59,0.95); border: 1px solid #475569;
             border-radius: 4px; padding: 6px 10px; font-size: 12px; pointer-events: none;
             display: none; max-width: 260px; word-break: break-word; }
</style>
</head>
<body>
<svg id="graph"></svg>
<div id="legend"></div>
<div id="tooltip"></div>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const DATA = __DATA_JSON__;

const SURFACE_COLORS = __SURFACE_COLORS_JSON__;

// ── Build legend ────────────────────────────────────────────────────────────
const legendEl = document.getElementById('legend');
const legendTitle = document.createElement('h4');
legendTitle.textContent = 'Surface';
legendEl.appendChild(legendTitle);
const shownSurfaces = new Set(DATA.nodes.map(d => d.surface));
Object.entries(SURFACE_COLORS).forEach(([surface, color]) => {
  if (!shownSurfaces.has(surface)) return;
  const row = document.createElement('div');
  row.className = 'legend-row';
  row.innerHTML = '<div class="legend-dot" style="background:' + color + '"></div>'
                + '<span>' + surface + '</span>';
  legendEl.appendChild(row);
});

// ── Compute degree for node sizing ──────────────────────────────────────────
const degreeMap = {};
DATA.nodes.forEach(n => { degreeMap[n.id] = 0; });
DATA.edges.forEach(e => {
  if (degreeMap[e.source] !== undefined) degreeMap[e.source]++;
  if (degreeMap[e.target] !== undefined) degreeMap[e.target]++;
});
const degrees = Object.values(degreeMap);
const minDeg = Math.min(...degrees, 0);
const maxDeg = Math.max(...degrees, 1);
const rScale = d => {
  const d_ = degreeMap[typeof d === 'object' ? d.id : d] || 0;
  if (maxDeg === minDeg) return 8;
  return 4 + ((d_ - minDeg) / (maxDeg - minDeg)) * 14;
};

// ── D3 force simulation ──────────────────────────────────────────────────────
const svg = d3.select('#graph');
const width = window.innerWidth;
const height = window.innerHeight;

const simulation = d3.forceSimulation(DATA.nodes)
  .force('link', d3.forceLink(DATA.edges)
    .id(d => d.id)
    .distance(80))
  .force('charge', d3.forceManyBody().strength(-180))
  .force('center', d3.forceCenter(width / 2, height / 2))
  .force('collision', d3.forceCollide().radius(d => rScale(d) + 4));

const g = svg.append('g');

// ── Zoom & pan ───────────────────────────────────────────────────────────────
svg.call(d3.zoom().scaleExtent([0.1, 8]).on('zoom', event => {
  g.attr('transform', event.transform);
}));

// ── Edges ────────────────────────────────────────────────────────────────────
const link = g.append('g').selectAll('line')
  .data(DATA.edges)
  .join('line')
    .attr('class', 'link')
    .attr('stroke', d => {
      const src = typeof d.source === 'object' ? d.source.id : d.source;
      const srcNode = DATA.nodes.find(n => n.id === src);
      return srcNode ? srcNode.color : '#475569';
    })
    .attr('stroke-width', 1.5);

// ── Nodes ────────────────────────────────────────────────────────────────────
const tooltip = document.getElementById('tooltip');

const node = g.append('g').selectAll('g')
  .data(DATA.nodes)
  .join('g')
    .attr('class', 'node')
    .call(d3.drag()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x; d.fy = d.y;
      })
      .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        if (!d.pinned) { d.fx = null; d.fy = null; }
      }));

node.append('circle')
  .attr('r', d => rScale(d))
  .attr('fill', d => d.color || '#94a3b8');

// ── Hover: dim non-neighbors ─────────────────────────────────────────────────
const adjacency = {};
DATA.nodes.forEach(n => { adjacency[n.id] = new Set([n.id]); });
DATA.edges.forEach(e => {
  const s = typeof e.source === 'object' ? e.source.id : e.source;
  const t = typeof e.target === 'object' ? e.target.id : e.target;
  adjacency[s].add(t);
  adjacency[t].add(s);
});

node
  .on('mouseover', (event, d) => {
    tooltip.style.display = 'block';
    tooltip.textContent = d.title || d.id;
    node.selectAll('circle').attr('opacity', n =>
      adjacency[d.id].has(n.id) ? 1 : 0.15);
    link.attr('stroke-opacity', e => {
      const s = typeof e.source === 'object' ? e.source.id : e.source;
      const t = typeof e.target === 'object' ? e.target.id : e.target;
      return (s === d.id || t === d.id) ? 0.9 : 0.05;
    });
  })
  .on('mousemove', event => {
    tooltip.style.left = (event.clientX + 14) + 'px';
    tooltip.style.top  = (event.clientY - 8) + 'px';
  })
  .on('mouseout', () => {
    tooltip.style.display = 'none';
    node.selectAll('circle').attr('opacity', 1);
    link.attr('stroke-opacity', 0.4);
  })
  .on('click', (event, d) => {
    d.pinned = !d.pinned;
    if (d.pinned) { d.fx = d.x; d.fy = d.y; }
    else { d.fx = null; d.fy = null; }
    d3.select(event.currentTarget).select('circle')
      .attr('stroke', d.pinned ? '#f8fafc' : '#1e293b')
      .attr('stroke-width', d.pinned ? 3 : 1.5);
  });

// ── Simulation tick ───────────────────────────────────────────────────────────
simulation.on('tick', () => {
  link
    .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
    .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
  node.attr('transform', d => 'translate(' + d.x + ',' + d.y + ')');
});

window.addEventListener('resize', () => {
  simulation.force('center', d3.forceCenter(window.innerWidth / 2, window.innerHeight / 2));
});
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Data assembly helpers
# ---------------------------------------------------------------------------


def _assemble_graph(
    kq,
    project_root: Path | None = None,
    surface_filter: list[str] | None = None,
) -> dict:
    """Assemble nodes and edges by delegating to knowledge_query._collect_all.

    Returns:
        Dict with 'nodes' and 'edges' lists suitable for JSON serialisation.
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    paths_json = project_root / "config" / "paths.json"

    sf = surface_filter[0] if surface_filter and len(surface_filter) == 1 else None
    node_records, edge_records = kq._collect_all(project_root, paths_json, surface_filter=sf)

    if surface_filter and len(surface_filter) > 1:
        allowed = set(surface_filter)
        node_records = [n for n in node_records if n.surface in allowed]
        kept_ids = {n.id for n in node_records}
        edge_records = [e for e in edge_records if e.source_id in kept_ids and e.target_id in kept_ids]

    nodes = []
    seen: set[str] = set()
    for nr in node_records:
        if nr.id in seen:
            continue
        seen.add(nr.id)
        nodes.append({
            "id": nr.id,
            "surface": nr.surface,
            "title": nr.title,
            "description": nr.description,
            "color": SURFACE_COLORS.get(nr.surface, "#94a3b8"),
        })

    edges = [
        {"source": e.source_id, "target": e.target_id, "type": e.edge_type}
        for e in edge_records
    ]

    return {"nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """Entry point for the visualise_knowledge_graph CLI.

    Args:
        argv: Argument list. Defaults to sys.argv[1:] when None.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Generate a self-contained D3.js force-directed HTML visualization "
            "of the leafcutter knowledge graph."
        )
    )
    parser.add_argument(
        "--output",
        default="/tmp/leafcutter_knowledge_graph.html",
        help="Output HTML file path (default: /tmp/leafcutter_knowledge_graph.html).",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Write the HTML file but do not open the browser.",
    )
    parser.add_argument(
        "--surface",
        nargs="+",
        default=None,
        metavar="SURFACE",
        help=(
            "Restrict the graph to one or more named surfaces "
            "(e.g. --surface agents skills). "
            "When omitted, all surfaces are included."
        ),
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Override the project root directory passed to load_surfaces(). "
            "When omitted, auto-detects from the script's location."
        ),
    )
    args = parser.parse_args(argv)

    # Load knowledge_query sibling module
    try:
        kq = _load_kq_module()
    except FileNotFoundError:
        print(
            f"ERROR: knowledge_query.py not found at {_KQ_PATH}.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Assemble graph data
    graph = _assemble_graph(
        kq,
        project_root=args.project_root,
        surface_filter=args.surface,
    )

    if not graph["nodes"]:
        print(
            "Warning: knowledge graph is empty (zero nodes). "
            "The HTML file will still be written.",
            file=sys.stderr,
        )

    # Embed data into template
    data_json = json.dumps(graph, indent=None, separators=(",", ":"))
    surface_colors_json = json.dumps(
        {k: v for k, v in SURFACE_COLORS.items()},
        separators=(",", ":"),
    )
    html = HTML_TEMPLATE.replace("__DATA_JSON__", data_json)
    html = html.replace("__SURFACE_COLORS_JSON__", surface_colors_json)

    # Write output file
    output_path = Path(args.output)
    try:
        output_path.write_text(html, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: Cannot write to {output_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Knowledge graph written to: {output_path}")

    # Open in browser unless suppressed
    if not args.no_open:
        webbrowser.open(f"file://{output_path.resolve()}")

    sys.exit(0)


if __name__ == "__main__":
    main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 14:35 [EPIC-KnowledgeGraphQueryLayer/03a]: Initial implementation.
  Pure stdlib D3.js force-directed graph visualization. Delegates to
  knowledge_query.py via importlib.util (AC-6). SURFACE_COLORS public constant
  (AC-2). Embeds node/edge JSON in HTML template (AC-1, AC-2). CDN-only D3
  reference (AC-3). Clean error on missing knowledge_query.py (AC-5). Argparse
  flags --output and --no-open (AC-1). Zero network I/O in Python (AC-3).
  (#EPIC-KnowledgeGraphQueryLayer/03a)
- 2026-06-05 14:40 [EPIC-KnowledgeGraphQueryLayer/03b]: Added --surface and --project-root
  argparse flags. --surface (nargs='+') filters surfaces dict before node extraction
  and post-filters edges to exclude cross-surface links (AC-1). --project-root (type=Path)
  overrides auto-detect and is passed as project_root to load_surfaces() (AC-2).
  _assemble_graph() now accepts optional project_root and surface_filter parameters.
  (#EPIC-KnowledgeGraphQueryLayer/03b)
====================================================================
"""
