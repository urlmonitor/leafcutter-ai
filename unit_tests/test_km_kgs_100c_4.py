"""
MODULE: test_km_kgs_100c_4
GOAL: TDD stubs for KM-KGS-100c-4 — a ticket's files_touched declarations
      become ticket-to-file edges in the knowledge map.
BUSINESS CONTEXT: config/paths.json's tickets surface declares files_touched
    in edge_fields but has no file_path_fields entry, so build_knowledge_map()
    drops every files_touched edge as a phantom (target is a file path, never
    a node id). The fix is declarative only: add files_touched to the tickets
    surface's file_path_fields, mirroring the acs surface's implemented_by /
    covered_by. These tests go through the REAL config/paths.json content and
    the real public build_knowledge_map()/render_json() so they fail with or
    without a hand-built edges dict, and pass only once the declaration is
    fixed.

IT-PO FOLLOW-UP (2026-09-25): these three tests are superseded by
    KM-KGS-100d-4, which changes what the tickets file_path_fields
    declaration MEANS: a files_touched value no longer just survives the
    phantom filter as a raw-string leaf -- it resolves to a real
    files-surface node, exactly like implemented_by/covered_by. The two
    "produce edges" tests are strengthened to assert the target is a
    files-surface node (and, for the controlled ticket whose declared
    paths do not exist on disk, that the node is marked missing per
    KM-KGS-100d-4-ii). The exemption test's regex half (which asserted a
    _PHANTOM_FILTER_EXEMPT-style code region existed) is replaced with a
    behavioural check, because KM-KGS-100d-4 deletes that region entirely.
"""

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_REAL_PATHS_JSON = _REPO_ROOT / "config" / "paths.json"
_KNOWLEDGE_QUERY_SCRIPT = _SCRIPTS_DIR / "knowledge_query.py"

sys.path.insert(0, str(_SCRIPTS_DIR))

from knowledge_query import build_knowledge_map  # noqa: E402


def _build_controlled_project(tmp_path):
    """Copy the real config/paths.json byte-for-byte into a temp project.

    Adds a minimal ticket under tickets/ declaring two files_touched paths
    that are not node ids anywhere in the graph. No other surface directory
    is created: extract_nodes() no-ops on a missing path (see
    knowledge_query.extract_nodes), so the build succeeds using only the
    real paths.json plus this one ticket file.
    """
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    real_bytes = _REAL_PATHS_JSON.read_bytes()
    (config_dir / "paths.json").write_bytes(real_bytes)

    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir(parents=True)
    ticket_content = (
        "---\n"
        "id: TICKET-KM-KGS-100C-4-TEST\n"
        "title: Controlled ticket for files_touched edge test\n"
        "agents:\n"
        "  python-coder: needed\n"
        "depends_on: []\n"
        "files_touched:\n"
        "  - scripts/does_not_exist_as_a_node.py\n"
        "  - unit_tests/also_not_a_node.py\n"
        "---\n\n"
        "# Controlled ticket\n\nBody text.\n"
    )
    (tickets_dir / "controlled_ticket.md").write_text(
        ticket_content, encoding="utf-8"
    )
    return tmp_path, config_dir / "paths.json"


def test_ticket_files_touched_produce_edges_to_declared_paths(tmp_path):
    # covers: KM-KGS-100c-4
    # angle: criterion
    """A ticket's files_touched values become files_touched edges, target as read.

    Red before the fix: build_knowledge_map()'s phantom-edge filter drops
    both edges because their targets ("scripts/does_not_exist_as_a_node.py",
    "unit_tests/also_not_a_node.py") are not node ids and the tickets surface
    has no file_path_fields exemption in the copied real paths.json.
    """
    project_root, paths_json = _build_controlled_project(tmp_path)
    km = build_knowledge_map(project_root, paths_json)

    ticket_ids = {n.id for n in km.nodes if n.surface == "tickets"}
    assert "TICKET-KM-KGS-100C-4-TEST" in ticket_ids, (
        "controlled ticket node must be produced before edges can be asserted"
    )

    files_touched_edges = [e for e in km.edges if e.edge_type == "files_touched"]
    targets = {e.target_id for e in files_touched_edges if e.source_id == "TICKET-KM-KGS-100C-4-TEST"}
    assert targets == {
        "scripts/does_not_exist_as_a_node.py",
        "unit_tests/also_not_a_node.py",
    }, (
        f"expected two files_touched edges with path-string targets as read; "
        f"got {targets} (0 expected before the fix — the phantom filter drops "
        f"both because tickets has no file_path_fields entry)"
    )

    # KM-KGS-100d-4 follow-up: the targets must be real files-surface nodes,
    # not raw-string leaves surviving only the exemption, and KM-KGS-100d-4-ii
    # marks them missing since neither declared path exists on disk here.
    files_nodes = {n.id: n for n in km.nodes if n.surface == "files"}
    for target in targets:
        assert target in files_nodes, (
            f"{target!r} must be a files-surface node, not a raw-string leaf; "
            f"files nodes present: {sorted(files_nodes)}"
        )
        assert getattr(files_nodes[target], "missing", None) is True, (
            f"{target!r} does not exist on disk in this fixture and must be "
            f"marked missing: True (KM-KGS-100d-4-ii)"
        )


def test_real_repository_graph_contains_files_touched_edges():
    # covers: KM-KGS-100c-4
    # angle: real_artifact
    """The real repository's graph, via the real JSON export, gains ticket-to-file edges.

    Runs the shipped knowledge_query.py CLI (the real production entry point)
    as a subprocess against this worktree's real project root. Red before the
    fix: 1160 tickets declare 3057 files_touched values yet the phantom
    filter drops all of them, so 0 files_touched edges are emitted.

    Asserts source membership against the SET of ids the tickets surface
    produced, rather than an id -> surface dict built from all nodes. Node
    ids are bare filename stems, not namespaced by surface, so a ticket and
    a doc that happen to share a stem (e.g.
    "TICKET-20260601-FixHooksDeploymentPipeline" as both a ticket and its
    retrospective under docs/retrospectives/) collide in a dict keyed only
    by id — whichever surface is traversed last wins. That collision is a
    real pre-existing defect tracked separately; it is not this AC's concern
    and must not be worked around here. Membership-in-set is immune to the
    collision because it only asks "is this id one the tickets surface
    produced", not "what is the single surface this id resolves to".
    """
    result = subprocess.run(
        [
            sys.executable,
            str(_KNOWLEDGE_QUERY_SCRIPT),
            "--project-root",
            str(_REPO_ROOT),
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"knowledge_query.py must exit 0; stderr: {result.stderr}"
    payload = json.loads(result.stdout)
    ticket_ids = {n["id"] for n in payload["nodes"] if n["surface"] == "tickets"}
    node_by_id = {n["id"]: n for n in payload["nodes"]}

    files_touched_edges = [e for e in payload["edges"] if e["type"] == "files_touched"]
    assert len(files_touched_edges) > 0, (
        "expected more than 0 files_touched edges from the real repository; "
        "got 0 (KM-KGS-100c-4 — the tickets surface has no file_path_fields "
        "exemption, so every files_touched edge is dropped as a phantom)"
    )
    for edge in files_touched_edges:
        assert edge["source"] in ticket_ids, (
            f"files_touched edge {edge} must be sourced from an id the tickets "
            f"surface produced; source={edge['source']!r} is not in the "
            f"tickets-surface id set"
        )
        assert isinstance(edge["target"], str) and edge["target"], (
            f"files_touched edge target must be the path string as read: {edge}"
        )
        # KM-KGS-100d-4 follow-up: the phantom filter no longer merely
        # exempts this edge type -- its target must be a real node.
        assert edge["target"] in node_by_id, (
            f"files_touched edge {edge} must end on a real node, not a "
            f"raw-string leaf; target {edge['target']!r} is no node's id"
        )
    assert any(node_by_id[e["target"]]["surface"] == "files" for e in files_touched_edges), (
        "expected at least one files_touched edge to end on a files-surface node"
    )


def test_files_touched_exemption_is_declared_not_special_cased(tmp_path):
    # covers: KM-KGS-100c-4
    # angle: boundary
    """The fix is declarative (paths.json only); no files_touched/tickets code branch.

    Asserts the real config/paths.json tickets surface declares files_touched
    in file_path_fields, mirroring the acs surface's implemented_by /
    covered_by. KM-KGS-100d-4 REPLACEMENT (IT-PO, 2026-09-25): the second
    half used to regex-inspect knowledge_query.py's dynamic_exempt/
    effective_exempt code region for a hardcoded 'files_touched'/'tickets'
    literal -- that region is DELETED by KM-KGS-100d-4's per-surface
    resolution, so a regex match on it can no longer prove anything.
    Replaced with a BEHAVIOURAL check: an AC's implemented_by value and a
    ticket's files_touched value naming the SAME missing path must resolve
    through the identical declaration-driven mechanism onto the SAME single
    files node -- proving files_touched is not special-cased relative to
    implemented_by, without reading source text.
    """
    data = json.loads(_REAL_PATHS_JSON.read_text(encoding="utf-8"))
    tickets_cfg = data["surfaces"]["tickets"]
    file_path_fields = tickets_cfg.get("file_path_fields", [])
    assert "files_touched" in file_path_fields, (
        "config/paths.json's tickets surface must declare 'files_touched' in "
        "file_path_fields, mirroring the acs surface's implemented_by/"
        f"covered_by; got file_path_fields={file_path_fields!r}"
    )

    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "paths.json").write_bytes(_REAL_PATHS_JSON.read_bytes())

    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir(parents=True)
    (tickets_dir / "shared.md").write_text(
        "---\nid: TICKET-SHARED\ntitle: Shared\nfiles_touched:\n"
        "  - scripts/shared_missing.py\n---\n\nBody.\n",
        encoding="utf-8",
    )
    acs_dir = tmp_path / "docs" / "acceptance-criteria" / "example-component"
    acs_dir.mkdir(parents=True)
    (acs_dir / "KM-EX-090.yaml").write_text(
        "id: KM-EX-090\ntitle: Shared\nimplemented_by:\n"
        "  - scripts/shared_missing.py\ncovered_by: []\ndepends_on: []\ncomponents: []\n",
        encoding="utf-8",
    )

    km = build_knowledge_map(tmp_path, config_dir / "paths.json")
    shared_nodes = [n for n in km.nodes if n.id == "scripts/shared_missing.py"]
    assert len(shared_nodes) == 1 and shared_nodes[0].surface == "files", (
        f"implemented_by and files_touched must resolve the same path onto "
        f"exactly ONE files node, not two mechanisms; got {shared_nodes}"
    )
    edges_to_shared = {e.source_id for e in km.edges if e.target_id == "scripts/shared_missing.py"}
    assert edges_to_shared == {"KM-EX-090", "TICKET-SHARED"}, (
        f"both the acs implemented_by edge and the tickets files_touched edge "
        f"must land on the same node; sources found: {edges_to_shared}"
    )
