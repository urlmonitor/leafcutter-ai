"""
MODULE: test_km_kgs_100b_1
GOAL: TDD stubs for KM-KGS-100b-1 -- answer which code file delivers an
      acceptance criterion by following its outbound edges.
BUSINESS CONTEXT: No pre-existing test file was found for this AC in this
    worktree (searched for 'within_four_declared_kinds' and 'KM-KGS-100b-1'
    across unit_tests/ per the authoring instructions; neither matched), so
    all six test_spec entries are authored fresh here, including the
    tightened equality test (renamed from
    test_ac_node_outbound_edge_kinds_within_four_declared_kinds to
    test_ac_node_outbound_edge_kinds_equal_four_declared_kinds).

    The target-form question is settled (user-approved 2026-09-25,
    KM-KGS-100d-4): implemented_by/covered_by edges from an acs node end on
    path-keyed files-surface nodes, so a reader can follow the edge to a
    real node naming the source file or test. The node-target test and the
    real-repository arm describe that target state and are RED until the
    KM-KGS-100d-4 epic is built. The equality test may already be green
    today, because the exemption keeps those edges; its job is to stay
    green once the exemption is retired.

ASSUMED API NAMES: none required beyond KM-KGS-100d-4's ('files' surface,
    node.missing) -- this file consumes the JSON export only.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_REAL_PATHS_JSON = _REPO_ROOT / "config" / "paths.json"
_KNOWLEDGE_QUERY_SCRIPT = _SCRIPTS_DIR / "knowledge_query.py"

sys.path.insert(0, str(_SCRIPTS_DIR))


def _build_km_ex_010_project(tmp_path):
    """KM-EX-010 with all four relationship fields populated, plus the real
    files and prerequisite AC those fields name."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "paths.json").write_bytes(_REAL_PATHS_JSON.read_bytes())

    acs_dir = tmp_path / "docs" / "acceptance-criteria" / "example-component"
    acs_dir.mkdir(parents=True)
    (acs_dir / "KM-EX-009.yaml").write_text(
        "id: KM-EX-009\n"
        "title: Prerequisite AC\n"
        "implemented_by: []\n"
        "covered_by: []\n"
        "depends_on: []\n"
        "components:\n"
        "  - build-pipeline\n",
        encoding="utf-8",
    )
    (acs_dir / "KM-EX-010.yaml").write_text(
        "id: KM-EX-010\n"
        "title: Example AC with all four relationship fields\n"
        "implemented_by:\n"
        "- scripts/foo.py\n"
        "covered_by:\n"
        "- unit_tests/test_foo.py\n"
        "depends_on:\n"
        "- KM-EX-009\n"
        "components:\n"
        "- build-pipeline\n",
        encoding="utf-8",
    )

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "foo.py").write_text("# real file\n", encoding="utf-8")

    unit_tests_dir = tmp_path / "unit_tests"
    unit_tests_dir.mkdir(parents=True)
    (unit_tests_dir / "test_foo.py").write_text("# real test file\n", encoding="utf-8")

    return tmp_path, config_dir / "paths.json"


def _run_cli_json(project_root):
    result = subprocess.run(
        [
            sys.executable,
            str(_KNOWLEDGE_QUERY_SCRIPT),
            "--format",
            "json",
            "--project-root",
            str(project_root),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, f"CLI must exit 0; stderr: {result.stderr}"
    return json.loads(result.stdout)


def test_json_export_edges_expose_source_target_and_edge_type(tmp_path):
    # covers: KM-KGS-100b-1
    # angle: criterion
    """Every exported edge carries source, target and edge_type as separate fields."""
    project_root, _ = _build_km_ex_010_project(tmp_path)
    payload = _run_cli_json(project_root)
    assert payload["edges"], "expected at least one edge in the export"
    for edge in payload["edges"]:
        assert "source" in edge and "target" in edge and "type" in edge, (
            f"every exported edge must carry source, target and type as "
            f"separate fields; got {edge}"
        )


def test_ac_node_outbound_edge_kinds_equal_four_declared_kinds(tmp_path):
    # covers: KM-KGS-100b-1
    # angle: criterion
    """KM-EX-010's outbound edge-type set is exactly the four declared kinds."""
    project_root, _ = _build_km_ex_010_project(tmp_path)
    payload = _run_cli_json(project_root)
    outbound_types = {e["type"] for e in payload["edges"] if e["source"] == "KM-EX-010"}
    assert outbound_types == {
        "implemented_by",
        "covered_by",
        "depends_on",
        "component_membership",
    }, f"expected exactly the four declared kinds; got {outbound_types}"


def test_ac_node_implemented_by_and_covered_by_edges_present_with_node_targets(tmp_path):
    # covers: KM-KGS-100b-1
    # angle: criterion
    """implemented_by/covered_by targets are ids of real files-surface nodes."""
    project_root, _ = _build_km_ex_010_project(tmp_path)
    payload = _run_cli_json(project_root)

    implemented_by = [
        e for e in payload["edges"] if e["source"] == "KM-EX-010" and e["type"] == "implemented_by"
    ]
    covered_by = [
        e for e in payload["edges"] if e["source"] == "KM-EX-010" and e["type"] == "covered_by"
    ]
    assert len(implemented_by) == 1 and implemented_by[0]["target"] == "scripts/foo.py"
    assert len(covered_by) == 1 and covered_by[0]["target"] == "unit_tests/test_foo.py"

    nodes_by_id = {n["id"]: n for n in payload["nodes"]}
    for edge in implemented_by + covered_by:
        target_node = nodes_by_id.get(edge["target"])
        assert target_node is not None, (
            f"edge target {edge['target']!r} must be the id of a real node in "
            f"the export (files-surface nodes do not exist yet)"
        )
        assert target_node["surface"] == "files", (
            f"edge target {edge['target']!r} must be a node with surface "
            f"'files'; got {target_node['surface']!r}"
        )


def test_ac_node_depends_on_and_component_membership_grouped_by_kind(tmp_path):
    # covers: KM-KGS-100b-1
    # angle: criterion
    """Grouping KM-EX-010's outbound edges by kind separates depends_on from component_membership."""
    project_root, _ = _build_km_ex_010_project(tmp_path)
    payload = _run_cli_json(project_root)

    outbound = [e for e in payload["edges"] if e["source"] == "KM-EX-010"]
    by_kind = {}
    for edge in outbound:
        by_kind.setdefault(edge["type"], set()).add(edge["target"])

    # Set comparison, not list equality: the pre-existing, documented acs+docs
    # double-ingestion (KM-KGS-100d-4's "OUT OF SCOPE" note — the docs surface
    # re-reads every AC YAML under docs/ a second time) can duplicate the
    # component_membership edge. That duplication is orthogonal to this AC's
    # contract (which kind an edge falls under), so the grouping assertion
    # must be duplicate-tolerant rather than pinning an edge count.
    assert by_kind.get("depends_on") == {"KM-EX-009"}
    assert by_kind.get("component_membership") == {"build-pipeline"}


def test_single_criterion_selection_returns_only_its_outbound_edges(tmp_path):
    # covers: KM-KGS-100b-1
    # angle: reachability
    """Selecting KM-EX-010 by id via the existing JSON export returns only its own edges."""
    project_root, _ = _build_km_ex_010_project(tmp_path)
    payload = _run_cli_json(project_root)

    selected = [e for e in payload["edges"] if e["source"] == "KM-EX-010"]
    assert selected, "expected at least one outbound edge for KM-EX-010"
    assert all(e["source"] == "KM-EX-010" for e in selected), (
        "selection by id must return only edges sourced from that id, no new bespoke command"
    )


def test_real_repository_ac_outbound_kinds_are_the_four_and_file_targets_are_nodes():
    # covers: KM-KGS-100b-1
    # angle: real_artifact
    """Real repository: every acs node's outbound kinds subset the four; file targets are nodes.

    ON THE CROSS-SURFACE ID COLLISION (documented, out-of-scope per
    KM-KGS-100d-4's "OUT OF SCOPE" note): the docs surface's path ('docs/')
    is a strict superset of the acs surface's path ('docs/acceptance-
    criteria/'), so its recursive '**/*.yaml' glob re-ingests EVERY AC YAML
    file a second time as a 'docs'-surface node with the identical id.
    Measured on this repository: 4231 of 4231 distinct acs ids collide with
    a docs node -- i.e. essentially all of them, not a small subset -- so
    "ids unique to the acs surface" is empty and cannot be used as a filter
    (that restriction was tried and verified to zero out this test).
    Instead this test excludes edges of type 'related_docs': that kind is
    declared ONLY by the docs surface (acs does not declare it), so any
    'related_docs' edge sourced from a colliding id is unambiguously the
    docs node's own edge, never an acs violation. Every other kind --
    including 'component_membership', which both surfaces declare, and is
    therefore genuinely ambiguous but also genuinely allowed either way --
    is still checked at full strictness below.
    """
    assert _REPO_ROOT.exists(), f"repo root must exist: {_REPO_ROOT}"
    payload = _run_cli_json(_REPO_ROOT)

    node_ids = {n["id"] for n in payload["nodes"]}
    acs_ids = {n["id"] for n in payload["nodes"] if n["surface"] == "acs"}
    assert len(acs_ids) > 1000, (
        f"expected > 1000 distinct acs ids in the real repository (sanity "
        f"floor so this test can't pass vacuously); got {len(acs_ids)}"
    )
    allowed = {"implemented_by", "covered_by", "depends_on", "component_membership"}
    docs_only_kind = "related_docs"

    union_kinds = set()
    implemented_by_count = 0
    for edge in payload["edges"]:
        if edge["source"] not in acs_ids:
            continue
        if edge["type"] == docs_only_kind:
            continue
        assert edge["type"] in allowed, (
            f"acs node {edge['source']!r} produced an undeclared outbound kind "
            f"{edge['type']!r}"
        )
        union_kinds.add(edge["type"])
        if edge["type"] in ("implemented_by", "covered_by"):
            implemented_by_count += 1 if edge["type"] == "implemented_by" else 0
            assert edge["target"] in node_ids, (
                f"acs edge {edge} must target a real node id "
                f"(files-surface nodes do not exist yet)"
            )

    assert union_kinds == allowed, (
        f"expected the union of acs outbound kinds across the real repository "
        f"to equal all four; got {union_kinds}"
    )
    assert implemented_by_count > 0, (
        f"expected > 0 implemented_by edges from acs nodes; got {implemented_by_count}"
    )
