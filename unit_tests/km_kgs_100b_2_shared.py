"""
MODULE: km_kgs_100b_2_shared
GOAL: Shared temp-project fixture builders, module loaders, DATA extractor,
      ghost-edge / unmarked-node wrappers, and the browser-free
      adjacency/forceLink replay used by the KM-KGS-100b-2 / -i / -ii family
      of visualiser tests.
BUSINESS CONTEXT: KM-KGS-100b-2-i and -ii both reuse "the shared temp-project
    helper, DATA extractor, and adjacency/forceLink replay" (per their own
    test_rationale fields), and KM-KGS-100d-4_shared.py already establishes
    the convention of one non-test-named helper module per family so the
    duplicate-code check does not fire. This module is that helper for the
    visualiser (scripts/visualise_knowledge_graph.py) side; the
    knowledge_query.py-side helper (temp AC/ticket fixtures, the CLI runner)
    stays in km_kgs_100d_4_shared.py and is reused here, not duplicated.
    It is intentionally NOT named test_*.py so pytest never collects it as a
    test module; it carries no # covers:/# angle: tags because it has no
    test functions of its own.
ARCHITECTURE: Every wrapper here WRAPS the real knowledge_query.py output
    (loaded fresh via load_real_kq_module()) and only ever appends or
    substitutes individual records -- it never hand-builds a graph from
    scratch, per this ticket's "wrap the real _collect_all output ... never
    replace it with a hand-built graph" instruction.
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

from km_kgs_100d_4_shared import (
    REPO_ROOT,
    copy_real_paths_json,
    subprocess_env,
    write_ac_yaml,
    write_ticket,
)

SCRIPTS_DIR = REPO_ROOT / "scripts"
VISUALISER_SCRIPT = SCRIPTS_DIR / "visualise_knowledge_graph.py"
KNOWLEDGE_QUERY_SCRIPT = SCRIPTS_DIR / "knowledge_query.py"

# ---------------------------------------------------------------------------
# Regexes: DATA/SURFACE_COLORS extraction, left-out-count message
# ---------------------------------------------------------------------------

_DATA_RE = re.compile(r"const DATA\s*=\s*(\{.*?\});\s*\n\s*const SURFACE_COLORS", re.DOTALL)
_SURFACE_COLORS_RE = re.compile(r"const SURFACE_COLORS\s*=\s*(\{.*?\});", re.DOTALL)

#: ASSUMED FORMAT (not pinned by any AC or test_rationale): "Left out N of M
#: relationships". No implementation exists yet to observe the real wording
#: from, so this is a clearly-named assumption -- see the test-writer report.
LEFT_OUT_RE = re.compile(r"[Ll]eft out (\d+) of (\d+)")

_MISSING_BRANCH_PATTERNS = (
    re.compile(r"classed\(\s*['\"]([\w-]+)['\"]\s*,\s*d(?:ata)?\s*=>\s*d(?:ata)?\.missing"),
    re.compile(r"attr\(\s*['\"]([\w-]+)['\"]\s*,\s*d(?:ata)?\s*=>\s*d(?:ata)?\.missing"),
    re.compile(r"d\.missing\s*\?\s*['\"]([\w-]+)['\"]"),
)


# ---------------------------------------------------------------------------
# Module loaders
# ---------------------------------------------------------------------------


def load_visualiser_module():
    """Dynamically load visualise_knowledge_graph.py from scripts/ (fresh
    module object each call, so per-test monkeypatching never leaks)."""
    if not VISUALISER_SCRIPT.exists():
        raise ImportError(str(VISUALISER_SCRIPT))
    spec = importlib.util.spec_from_file_location(
        "visualise_knowledge_graph_kgs2", VISUALISER_SCRIPT
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_real_kq_module():
    """Load the real knowledge_query.py sibling module directly (fresh)."""
    spec = importlib.util.spec_from_file_location("knowledge_query_kgs2", KNOWLEDGE_QUERY_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sf_for(surface_args: list[str] | None) -> str | None:
    """Mirror _assemble_graph's own single-vs-multi surface_filter rule."""
    if surface_args and len(surface_args) == 1:
        return surface_args[0]
    return None


# ---------------------------------------------------------------------------
# DATA extraction
# ---------------------------------------------------------------------------


def extract_data_and_colors(html: str) -> tuple[dict, dict]:
    """Extract the embedded DATA and SURFACE_COLORS JSON blocks from the
    generated HTML, via json.loads (never a hand-parsed literal)."""
    import json

    data_match = _DATA_RE.search(html)
    assert data_match is not None, "Could not find 'const DATA = ...' block in HTML"
    colors_match = _SURFACE_COLORS_RE.search(html)
    assert colors_match is not None, "Could not find 'const SURFACE_COLORS = ...' block in HTML"
    return json.loads(data_match.group(1)), json.loads(colors_match.group(1))


# ---------------------------------------------------------------------------
# Real-_collect_all wrappers (never a hand-built graph)
# ---------------------------------------------------------------------------


class GhostEdgeKQ:
    """Wraps the REAL knowledge_query module: real _collect_all output plus
    one appended EdgeRecord whose target is an id no node on the map
    carries -- exactly the criterion's "far end is an id that no node on the
    map carries".
    """

    def __init__(self, real_kq, source_id: str, ghost_target_id: str, edge_type: str = "depends_on"):
        self._real_kq = real_kq
        self._source_id = source_id
        self._ghost_target_id = ghost_target_id
        self._edge_type = edge_type
        self.NodeRecord = real_kq.NodeRecord
        self.EdgeRecord = real_kq.EdgeRecord

    def _collect_all(self, project_root, paths_json, surface_filter=None):
        nodes, edges = self._real_kq._collect_all(
            project_root, paths_json, surface_filter=surface_filter
        )
        ghost = self._real_kq.EdgeRecord(
            source_id=self._source_id,
            target_id=self._ghost_target_id,
            edge_type=self._edge_type,
        )
        return nodes, list(edges) + [ghost]


class _LegacyNodeRecordNoMissing:
    """A files-surface node shaped like pre-KM-KGS-100d-4-ii map data: it has
    NO 'missing' attribute at all (not even a False default), so a consumer
    that reads n.missing directly (rather than getattr(n, 'missing', False))
    breaks on it -- proving real backward compatibility, not merely a False
    value on a real NodeRecord.
    """

    def __init__(self, id, surface, title, description, path):  # noqa: A002
        self.id = id
        self.surface = surface
        self.title = title
        self.description = description
        self.path = path


class UnmarkedFilesNodeKQ:
    """Wraps the REAL knowledge_query module: real _collect_all output, but
    the node whose id is ``unmark_node_id`` is replaced by an equivalent
    object carrying no 'missing' attribute at all.
    """

    def __init__(self, real_kq, unmark_node_id: str):
        self._real_kq = real_kq
        self._unmark_node_id = unmark_node_id
        self.NodeRecord = real_kq.NodeRecord
        self.EdgeRecord = real_kq.EdgeRecord

    def _collect_all(self, project_root, paths_json, surface_filter=None):
        nodes, edges = self._real_kq._collect_all(
            project_root, paths_json, surface_filter=surface_filter
        )
        patched = []
        for n in nodes:
            if n.id == self._unmark_node_id:
                patched.append(
                    _LegacyNodeRecordNoMissing(
                        id=n.id, surface=n.surface, title=n.title,
                        description=n.description, path=n.path,
                    )
                )
            else:
                patched.append(n)
        return patched, edges


# ---------------------------------------------------------------------------
# Browser-free replay of the two D3 crash sites
# ---------------------------------------------------------------------------

ADJACENCY_BUILD_ANCHOR = "DATA.nodes.forEach(n => { adjacency[n.id] = new Set([n.id]); });"
ADJACENCY_ADD_ANCHORS = ("adjacency[s].add(t);", "adjacency[t].add(s);")
FORCELINK_ID_ANCHOR = ".id(d => d.id)"


def assert_script_shape_unchanged(html: str) -> None:
    """Static anchor: the shipped script still builds adjacency from
    DATA.nodes, still does adjacency[s].add(t)/adjacency[t].add(s) for every
    edge, and still resolves forceLink via '.id(d => d.id)'. Fails if the
    script's shape changes, so the Python replay below keeps modelling the
    real shipped script rather than a stale assumption about it.
    """
    assert ADJACENCY_BUILD_ANCHOR in html, "adjacency build anchor not found in generated script"
    for anchor in ADJACENCY_ADD_ANCHORS:
        assert anchor in html, f"adjacency add anchor {anchor!r} not found in generated script"
    assert FORCELINK_ID_ANCHOR in html, "forceLink id anchor not found in generated script"


def replay_adjacency_and_forcelink(data: dict) -> dict:
    """Browser-free Python replay of the two crash sites: d3.forceLink(...)
    .id(d => d.id), and the adjacency[s].add(t) / adjacency[t].add(s) build
    around line 197. Raises AssertionError naming the offending edge on any
    endpoint id that is not a DATA.nodes id -- the same shape of failure d3
    throws 'node not found' for, and the same KeyError the plain adjacency
    indexing throws.
    """
    node_ids = {n["id"] for n in data["nodes"]}
    adjacency: dict[str, set] = {nid: {nid} for nid in node_ids}
    forcelink_id_map = {nid: nid for nid in node_ids}
    for e in data["edges"]:
        s, t = e["source"], e["target"]
        assert s in forcelink_id_map, f"forceLink().id() cannot resolve source of edge {e!r}"
        assert t in forcelink_id_map, f"forceLink().id() cannot resolve target of edge {e!r}"
        assert s in adjacency, f"adjacency[{s!r}] does not exist for edge {e!r}"
        assert t in adjacency, f"adjacency[{t!r}] does not exist for edge {e!r}"
        adjacency[s].add(t)
        adjacency[t].add(s)
    return adjacency


def find_missing_branch_token(html: str) -> str:
    """Best-effort static discovery of the attribute/class name a
    d.missing-keyed branch sets in the generated script. Tries several
    reasonable D3 idioms (ASSUMED -- not pinned by any AC, since the
    treatment does not exist yet); raises AssertionError naming the search
    if none match, which is the correct RED result before implementation.
    """
    for pattern in _MISSING_BRANCH_PATTERNS:
        m = pattern.search(html)
        if m:
            return m.group(1)
    raise AssertionError(
        "no d.missing-keyed attribute/class branch found in generated script "
        "(tried classed()/attr()/ternary idioms -- see km_kgs_100b_2_shared.py "
        "_MISSING_BRANCH_PATTERNS for the exact assumed forms)"
    )


# ---------------------------------------------------------------------------
# Subprocess runner (real-artifact arms)
# ---------------------------------------------------------------------------


def run_visualiser_subprocess(project_root: Path, output_path: Path, extra_args=None, timeout=60):
    """Run the shipped visualise_knowledge_graph.py as a real subprocess."""
    args = [
        sys.executable, str(VISUALISER_SCRIPT),
        "--no-open", "--output", str(output_path),
        "--project-root", str(project_root),
    ]
    args += list(extra_args or [])
    return subprocess.run(
        args, capture_output=True, text=True, timeout=timeout, env=subprocess_env()
    )


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def build_dangling_edge_fixture(tmp_path: Path) -> Path:
    """KM-KGS-100b-2-i's criterion fixture: KM-EX-060 (depends_on
    [KM-EX-059], components [build-pipeline]), KM-EX-059, and ticket
    tickets/T-6.md. The dangling edge itself (KM-EX-060 -> an id no node
    carries) is injected by GhostEdgeKQ, never written into this fixture --
    this fixture only supplies the "one edge to a node on the page" half of
    the criterion.
    """
    copy_real_paths_json(tmp_path)
    acs_dir = tmp_path / "docs" / "acceptance-criteria" / "example-component"
    write_ac_yaml(acs_dir, "KM-EX-060", depends_on=["KM-EX-059"], components=["build-pipeline"])
    write_ac_yaml(acs_dir, "KM-EX-059")
    write_ticket(tmp_path / "tickets", "T-6", filename="T-6.md")
    return tmp_path


def build_file_drawing_fixture(tmp_path: Path) -> Path:
    """KM-KGS-100b-2-ii's criterion fixture: files-surface node
    'scripts/foo.py' (present -- written to disk) and
    'scripts/removed_tool.py' (missing -- never written to disk), each named
    by KM-EX-070's implemented_by list.
    """
    copy_real_paths_json(tmp_path)
    acs_dir = tmp_path / "docs" / "acceptance-criteria" / "example-component"
    write_ac_yaml(acs_dir, "KM-EX-070", implemented_by=["scripts/foo.py", "scripts/removed_tool.py"])
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts" / "foo.py").write_text("# fixture\n", encoding="utf-8")
    return tmp_path
