"""
MODULE: test_km_kgs_100d_4_real
GOAL: TDD stubs for KM-KGS-100d-4's whole-repository arm -- every edge
      target in the REAL graph is a node (zero dangling edges), with pinned
      floors on file-path edge counts so "zero dangling" can never be
      reached by silently dropping edges instead of resolving them.
BUSINESS CONTEXT: see docs/acceptance-criteria/knowledge-management/
    KM-KGS-100-knowledge-graph-surfaces/KM-KGS-100d-4.yaml, test_spec entries
    test_real_repository_every_edge_target_is_a_node_without_losing_file_edges
    and test_real_repository_files_nodes_are_canonical_unique_and_counted.
    A single module-scoped build (about 5s) is shared by both tests, per the
    "no re-walking the whole store twice" convention this repo already uses
    (see test_km_kgs_100a_3_viii.py's whole_store_scan fixture). A missing
    repo root or paths.json FAILS naming the path -- this module never calls
    pytest.skip.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_REAL_PATHS_JSON = _REPO_ROOT / "config" / "paths.json"
sys.path.insert(0, str(_SCRIPTS_DIR))

from knowledge_query import build_knowledge_map  # noqa: E402

# Pinned floors (measured 2026-09-25 on branch feature/km-file-nodes-acs):
# 1,608 of 1,609 implemented_by edges and 678 of 4,713 covered_by edges
# survived only via the file_path_fields exemption. Once every file-path
# edge resolves to a real node instead of being dropped, these floors must
# still hold -- "zero dangling" must never be reachable by dropping edges.
_IMPLEMENTED_BY_FLOOR = 1500
_COVERED_BY_FLOOR = 4500


@pytest.fixture(scope="module")
def real_map():
    """Build the real repository's knowledge map exactly once per session."""
    assert _REAL_PATHS_JSON.is_file(), (
        f"real config/paths.json not found at {_REAL_PATHS_JSON} -- this "
        "test must FAIL, never skip, on a missing repo root"
    )
    return build_knowledge_map(_REPO_ROOT, _REAL_PATHS_JSON)


def test_real_repository_every_edge_target_is_a_node_without_losing_file_edges(real_map):
    # covers: KM-KGS-100d-4
    # angle: real_artifact
    """Zero dangling edges in the real graph, with pinned file-path edge floors."""
    node_ids = {n.id for n in real_map.nodes}
    dangling = [e for e in real_map.edges if e.target_id not in node_ids]
    assert not dangling, (
        f"{len(dangling)} edge(s) target an id that is no node in the real "
        f"graph (zero-dangling is required once file_path_fields exemption "
        f"retires); first few: {dangling[:5]}"
    )

    implemented_by = [e for e in real_map.edges if e.edge_type == "implemented_by"]
    covered_by = [e for e in real_map.edges if e.edge_type == "covered_by"]
    files_touched = [e for e in real_map.edges if e.edge_type == "files_touched"]

    assert len(implemented_by) >= _IMPLEMENTED_BY_FLOOR, (
        f"expected >= {_IMPLEMENTED_BY_FLOOR} implemented_by edges "
        f"(1609 measured 2026-09-25); got {len(implemented_by)} -- a low "
        f"count with zero dangling would mean edges were dropped, not resolved"
    )
    assert len(covered_by) >= _COVERED_BY_FLOOR, (
        f"expected >= {_COVERED_BY_FLOOR} covered_by edges "
        f"(4713 measured 2026-09-25); got {len(covered_by)}"
    )
    assert len(files_touched) > 0, (
        "expected > 0 files_touched edges from the tickets surface "
        f"(KM-KGS-100c-4); got {len(files_touched)}"
    )


def test_real_repository_files_nodes_are_canonical_unique_and_counted(real_map):
    # covers: KM-KGS-100d-4
    # angle: real_artifact
    """Real files-surface nodes are canonical, unique, and counted; at least
    one implemented_by edge lands on a ticket's own node; at least one real
    '#anchor' value produces an edge whose anchor is the text after '#'."""
    files_nodes = [n for n in real_map.nodes if n.surface == "files"]
    assert len(files_nodes) > 0, (
        f"expected > 0 files-surface nodes in the real graph; got "
        f"{len(files_nodes)} (files-node count stated per KM-KGS-100d-4)"
    )

    ids = [n.id for n in files_nodes]
    assert len(ids) == len(set(ids)), (
        f"files-surface node ids must be unique; found duplicates among "
        f"{len(ids)} ids"
    )
    for node_id in ids:
        assert not Path(node_id).is_absolute(), f"files node id must be repo-relative: {node_id!r}"
        assert "\\" not in node_id, f"files node id must use '/' only: {node_id!r}"
        assert not node_id.startswith("./"), f"files node id must have no leading './': {node_id!r}"
        assert not node_id.endswith("/"), f"files node id must have no trailing '/': {node_id!r}"
        assert "#" not in node_id, f"files node id must carry no '#anchor' suffix: {node_id!r}"
        assert "::" not in node_id, f"files node id must carry no '::test' suffix: {node_id!r}"
        # pr-reviewer regression (KM-KGS-100d-4-iii): a '..' segment must
        # never survive into a files node id -- it must have collapsed to
        # its canonical path, or been declined if it escaped the root.
        assert ".." not in node_id.split("/"), f"files node id must carry no '..' segment: {node_id!r}"

    ticket_ids = {n.id for n in real_map.nodes if n.surface == "tickets"}
    impl_edges_to_tickets = [
        e for e in real_map.edges if e.edge_type == "implemented_by" and e.target_id in ticket_ids
    ]
    assert impl_edges_to_tickets, (
        "expected at least one implemented_by edge to end on a tickets-"
        "surface node (477 values named an existing ticket's own path, "
        "measured 2026-09-25)"
    )

    # A real, evidence-backed '#anchor' value: docs/acceptance-criteria's
    # KM-KGS-100d-4.yaml itself names this file in implemented_by.
    anchored = [
        e
        for e in real_map.edges
        if e.edge_type == "implemented_by"
        and e.target_id == "scripts/commit_guardian/check_ac_limits.py"
        and getattr(e, "anchor", None) == "_check_limits"
    ]
    assert anchored, (
        "expected an implemented_by edge to "
        "'scripts/commit_guardian/check_ac_limits.py' carrying anchor "
        "'_check_limits' (the real value 'scripts/commit_guardian/"
        "check_ac_limits.py#_check_limits' appears in the AC store)"
    )
