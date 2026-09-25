"""
MODULE: test_km_kgs_100d_4_dotdot_escape
GOAL: Regression tests for a canonicalisation defect pr-reviewer found in
      the KM-KGS-100d-4 epic (KM-KGS-100d-4-iii): a relative value
      containing '..' that escapes the project root becomes a files node
      instead of being declined, and a value with an interior '..' that
      stays inside the root keeps the '..' segment in its node id instead
      of resolving to the canonical, already-collapsed path.
BUSINESS CONTEXT: scripts/knowledge_file_nodes.py's _is_path_shaped
    (~line 188) decides path-shapedness with `(project_root / value).exists()`,
    which really traverses '..' segments through the OS -- so
    'scripts/../..' (the project root's own parent) is judged path-shaped.
    No canonicalisation step collapses '..', so the raw, uncollapsed string
    then becomes either a NEW files node id that escapes the project root's
    own path space ('scripts/../..'), or a distinct node from the same
    file's already-collapsed spelling ('scripts/../config/paths.json' vs
    'config/paths.json'). This file is new (not the -iii owner's own test
    file) per the fast-lane coordination rule against editing another
    writer's files; it reuses the shared temp-project helper like every
    sibling in this family.
"""
from __future__ import annotations

import sys
from pathlib import Path

from km_kgs_100d_4_shared import build_criteria_fixture, run_cli, run_cli_json, write_ac_yaml

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from knowledge_query import build_knowledge_map  # noqa: E402

_NOT_A_PATH_REASON = "not a file path in this project"


def _edges(km, *, source=None, edge_type=None):
    edges = list(km.edges)
    if source is not None:
        edges = [e for e in edges if e.source_id == source]
    if edge_type is not None:
        edges = [e for e in edges if e.edge_type == edge_type]
    return edges


def test_escaping_dotdot_is_declined_not_a_files_node(tmp_path):
    # covers: KM-KGS-100d-4-iii
    # angle: failure
    """A relative value whose normalised form escapes the project root
    (e.g. 'scripts/../..', the project root's own parent) must be declined
    with reason 'not a file path in this project' -- never turned into a
    files node whose id contains '..'."""
    project_root = build_criteria_fixture(tmp_path)
    acs_dir = project_root / "docs" / "acceptance-criteria" / "example-component"
    write_ac_yaml(acs_dir, "KM-EX-070", implemented_by=["scripts/../.."])

    km = build_knowledge_map(project_root, project_root / "config" / "paths.json")
    edges = _edges(km, source="KM-EX-070", edge_type="implemented_by")
    assert not edges, (
        f"'scripts/../..' escapes the project root and must be declined, "
        f"not resolved to an edge; got {edges}"
    )
    escaping = [n.id for n in km.nodes if ".." in n.id.split("/")]
    assert not escaping, f"no node id may contain a '..' segment; got {escaping}"
    assert km.declined_count >= 1, (
        f"expected at least one declined value; got declined_count={km.declined_count}"
    )

    payload = run_cli_json(project_root)
    assert payload["declined"] >= 1, (
        f"expected the JSON export's 'declined' figure to be >= 1; got {payload['declined']}"
    )


def test_escaping_dotdot_stderr_names_the_reason(tmp_path):
    # covers: KM-KGS-100d-4-iii
    # angle: reachability
    """The shipped CLI announces the escaping '..' decline on stderr with
    the 'not a file path in this project' reason, via the real production
    entry point (subprocess), not merely the in-process map."""
    project_root = build_criteria_fixture(tmp_path)
    acs_dir = project_root / "docs" / "acceptance-criteria" / "example-component"
    write_ac_yaml(acs_dir, "KM-EX-073", implemented_by=["scripts/../.."])

    result = run_cli(project_root, extra_args=["--format", "json"])
    assert result.returncode == 0, result.stderr
    decline_lines = [line for line in result.stderr.splitlines() if line.startswith("DECLINED")]
    matching = [line for line in decline_lines if "scripts/../.." in line]
    assert matching, (
        f"expected a DECLINED stderr line naming 'scripts/../..'; got lines: {decline_lines}"
    )
    assert all(_NOT_A_PATH_REASON in line for line in matching), (
        f"expected reason {_NOT_A_PATH_REASON!r} on the decline line(s): {matching}"
    )


def test_interior_dotdot_resolves_to_canonical_node_not_raw_string(tmp_path):
    # covers: KM-KGS-100d-4-iii
    # angle: boundary
    """A value with an interior '..' that stays INSIDE the project root
    (e.g. 'scripts/../config/paths.json') must resolve to the SAME
    canonical node as the already-collapsed spelling ('config/paths.json'),
    never keep '..' in the target id or create a second, distinct node."""
    project_root = build_criteria_fixture(tmp_path)
    acs_dir = project_root / "docs" / "acceptance-criteria" / "example-component"
    write_ac_yaml(acs_dir, "KM-EX-071", implemented_by=["scripts/../config/paths.json"])
    write_ac_yaml(acs_dir, "KM-EX-072", implemented_by=["config/paths.json"])

    km = build_knowledge_map(project_root, project_root / "config" / "paths.json")
    interior_edges = _edges(km, source="KM-EX-071", edge_type="implemented_by")
    canonical_edges = _edges(km, source="KM-EX-072", edge_type="implemented_by")
    assert len(interior_edges) == 1, interior_edges
    assert len(canonical_edges) == 1, canonical_edges
    assert interior_edges[0].target_id == "config/paths.json", (
        f"'scripts/../config/paths.json' must collapse to 'config/paths.json'; "
        f"got {interior_edges[0].target_id!r}"
    )
    assert interior_edges[0].target_id == canonical_edges[0].target_id, (
        "the interior-'..' spelling and the already-collapsed spelling must land on the SAME node"
    )
    escaping = [n.id for n in km.nodes if ".." in n.id.split("/")]
    assert not escaping, f"no node id may contain '..'; got {escaping}"
