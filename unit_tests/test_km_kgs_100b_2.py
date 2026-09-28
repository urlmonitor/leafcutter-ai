"""
Tests for KM-KGS-100b-2 (L2): "Acceptance criteria and their links are
visible in the knowledge-graph visualization."

This L2's own promise: criterion nodes, their four outbound edge kinds
(implemented_by, covered_by, depends_on, component_membership), edges land
on nodes of the right surface, and 'acs' appears in the legend with its own
colour. Reuses the KM-KGS-100d-4 "criteria fixture" (via the shared helper's
km_ex_010_extra option, which does not change the fixture's default shape)
and the visualiser DATA extractor / adjacency replay shared with
KM-KGS-100b-2-i and -ii. Does NOT duplicate those children's dangling-edge,
left-out-count or missing-file tests (test_rationale).

KNOWN GAP, recorded rather than pinned (test_rationale): under --surface acs
tickets, the multi-surface branch keeps only nodes whose surface is listed,
so files/component-hub edges from acs nodes are dropped there. Test 2 below
deliberately does not assert them.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from km_kgs_100d_4_shared import build_criteria_fixture  # noqa: E402

from km_kgs_100b_2_shared import (  # noqa: E402
    REPO_ROOT,
    extract_data_and_colors,
    load_visualiser_module,
    replay_adjacency_and_forcelink,
    run_visualiser_subprocess,
)

_KM_EX_010_EXTRA = {"depends_on": ["KM-EX-012"], "components": ["build-pipeline"]}
_CRITERION_IDS = ("KM-EX-010", "KM-EX-011", "KM-EX-011-i", "KM-EX-012")


def _build_fixture(tmp_path):
    return build_criteria_fixture(tmp_path, km_ex_010_extra=_KM_EX_010_EXTRA)


def _generate_page(tmp_path, project_root, surface_args=None, filename="page.html"):
    mod = load_visualiser_module()
    output_path = tmp_path / filename
    argv = ["--no-open", "--output", str(output_path), "--project-root", str(project_root)]
    if surface_args:
        argv += ["--surface", *surface_args]
    with pytest.raises(SystemExit) as exc_info:
        mod.main(argv)
    assert exc_info.value.code == 0, "main() must exit 0"
    return output_path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "surface_args,km_ex_012_target,km_ex_012_target_surface",
    [
        (None, "T-1", "tickets"),
        (["acs"], "tickets/T-1.md", "files"),
    ],
    ids=["no-restriction", "surface-acs"],
)
def test_page_data_holds_criteria_and_edges_to_files_tests_dependencies_and_component(
    tmp_path, surface_args, km_ex_012_target, km_ex_012_target_surface,
):
    # covers: KM-KGS-100b-2
    # angle: criterion
    """DATA.nodes holds the four criterion ids (surface 'acs'); DATA.edges
    holds KM-EX-010 implemented_by scripts/foo.py (files), KM-EX-011
    covered_by unit_tests/test_foo.py (files), KM-EX-010 depends_on
    KM-EX-012 (acs), KM-EX-010 component_membership build-pipeline
    (components); KM-EX-012's implemented_by edge lands on the ticket node
    'T-1' with no restriction, and on the files node 'tickets/T-1.md' under
    --surface acs (KM-KGS-100d-4-iv's ticket-path fallback). Every endpoint
    asserted is a DATA.nodes id."""
    project_root = _build_fixture(tmp_path)
    html = _generate_page(tmp_path, project_root, surface_args)
    data, _colors = extract_data_and_colors(html)
    node_ids = {n["id"] for n in data["nodes"]}
    by_id = {n["id"]: n for n in data["nodes"]}

    for crit_id in _CRITERION_IDS:
        assert crit_id in node_ids, f"{crit_id} missing from DATA.nodes"
        assert by_id[crit_id]["surface"] == "acs"

    edges = {(e["source"], e["target"], e["type"]) for e in data["edges"]}

    assert ("KM-EX-010", "scripts/foo.py", "implemented_by") in edges
    assert by_id["scripts/foo.py"]["surface"] == "files"

    assert ("KM-EX-011", "unit_tests/test_foo.py", "covered_by") in edges
    assert by_id["unit_tests/test_foo.py"]["surface"] == "files"

    assert ("KM-EX-010", "KM-EX-012", "depends_on") in edges

    assert ("KM-EX-010", "build-pipeline", "component_membership") in edges
    assert by_id["build-pipeline"]["surface"] == "components"

    assert ("KM-EX-012", km_ex_012_target, "implemented_by") in edges
    assert by_id[km_ex_012_target]["surface"] == km_ex_012_target_surface

    for edge in data["edges"]:
        assert edge["source"] in node_ids, f"dangling source in {edge!r}"
        assert edge["target"] in node_ids, f"dangling target in {edge!r}"


def test_multi_surface_page_keeps_criterion_edges_whose_ends_are_drawn(tmp_path):
    # covers: KM-KGS-100b-2
    # angle: boundary
    """Under --surface acs tickets, the four criterion ids and 'T-1' are
    drawn; KM-EX-010 depends_on KM-EX-012 and KM-EX-012 implemented_by T-1
    survive; the files/component edges are NOT asserted here (KNOWN GAP)."""
    project_root = _build_fixture(tmp_path)
    html = _generate_page(tmp_path, project_root, ["acs", "tickets"])
    data, _colors = extract_data_and_colors(html)
    node_ids = {n["id"] for n in data["nodes"]}

    for crit_id in _CRITERION_IDS:
        assert crit_id in node_ids, f"{crit_id} missing from DATA.nodes"
    assert "T-1" in node_ids

    edge_pairs = {(e["source"], e["target"]) for e in data["edges"]}
    assert ("KM-EX-010", "KM-EX-012") in edge_pairs
    assert ("KM-EX-012", "T-1") in edge_pairs

    replay_adjacency_and_forcelink(data)


def test_acs_surface_is_in_the_page_legend_with_its_own_colour(tmp_path):
    # covers: KM-KGS-100b-2
    # angle: criterion
    """The embedded SURFACE_COLORS JSON has an 'acs' entry whose value
    differs from every other entry; every acs-surface DATA node carries that
    colour; the shownSurfaces legend loop replay includes 'acs'."""
    project_root = _build_fixture(tmp_path)
    html = _generate_page(tmp_path, project_root)
    data, colors = extract_data_and_colors(html)

    assert "acs" in colors
    acs_color = colors["acs"]
    assert all(c != acs_color for surf, c in colors.items() if surf != "acs")

    acs_nodes = [n for n in data["nodes"] if n["surface"] == "acs"]
    assert len(acs_nodes) > 0
    for n in acs_nodes:
        assert n["color"] == acs_color

    shown_surfaces = {n["surface"] for n in data["nodes"]}
    legend_entries = [s for s in colors if s in shown_surfaces]
    assert "acs" in legend_entries


def test_real_repository_default_page_draws_criteria_with_all_four_edge_kinds(tmp_path):
    # covers: KM-KGS-100b-2
    # angle: real_artifact
    """The shipped visualiser against the real repository: >0 acs nodes; for
    each of implemented_by, covered_by, depends_on and component_membership,
    at least one edge from an acs node with both ends being DATA.nodes ids;
    at least one implemented_by/covered_by edge from an acs node ends on a
    'files' node; at least one covered_by/depends_on edge ends on another
    'acs' node; at least one component_membership edge ends on a
    'components' node; the legend replay includes 'acs'. A missing repo
    root FAILS; it is never skipped."""
    assert REPO_ROOT.exists() and (REPO_ROOT / "config" / "paths.json").exists(), (
        "real repo root and config/paths.json must exist -- this must FAIL, never skip"
    )
    output_path = tmp_path / "page.html"
    result = run_visualiser_subprocess(REPO_ROOT, output_path)
    assert result.returncode == 0, result.stderr

    html = output_path.read_text(encoding="utf-8")
    data, colors = extract_data_and_colors(html)
    node_ids = {n["id"] for n in data["nodes"]}
    by_id = {n["id"]: n for n in data["nodes"]}

    acs_ids = {n["id"] for n in data["nodes"] if n["surface"] == "acs"}
    assert len(acs_ids) > 0

    by_type: dict[str, list] = {}
    for e in data["edges"]:
        if e["source"] in acs_ids:
            by_type.setdefault(e["type"], []).append(e)

    for etype in ("implemented_by", "covered_by", "depends_on", "component_membership"):
        assert etype in by_type and len(by_type[etype]) > 0, f"expected >=1 {etype} edge from an acs node"
        for e in by_type[etype]:
            assert e["source"] in node_ids
            assert e["target"] in node_ids

    assert any(by_id[e["target"]]["surface"] == "files" for e in by_type["implemented_by"])
    assert any(by_id[e["target"]]["surface"] == "files" for e in by_type["covered_by"])
    assert any(
        by_id[e["target"]]["surface"] == "acs" for e in by_type["covered_by"] + by_type["depends_on"]
    )
    assert any(by_id[e["target"]]["surface"] == "components" for e in by_type["component_membership"])

    shown_surfaces = {n["surface"] for n in data["nodes"]}
    legend_entries = [s for s in colors if s in shown_surfaces]
    assert "acs" in legend_entries
