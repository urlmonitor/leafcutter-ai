"""
Tests for KM-KGS-100b-2-i: "The knowledge-map page draws even when a
relationship's far end is not on the page."

Written BEFORE the fix (TDD / test-first). RED baseline expected: today
_assemble_graph() in scripts/visualise_knowledge_graph.py only filters
dangling edges in the multi-surface (len(surface) > 1) branch; the
no-restriction and single-surface branches pass every edge straight to the
page unfiltered, so an injected dangling edge reaches d3.forceLink().id()
and the adjacency[t].add(s) build unguarded.

All fixtures come from wrapping the REAL knowledge_query._collect_all output
(GhostEdgeKQ) -- never a hand-built graph.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from km_kgs_100b_2_shared import (  # noqa: E402
    REPO_ROOT,
    GhostEdgeKQ,
    LEFT_OUT_RE,
    assert_script_shape_unchanged,
    build_dangling_edge_fixture,
    extract_data_and_colors,
    load_real_kq_module,
    load_visualiser_module,
    replay_adjacency_and_forcelink,
    run_visualiser_subprocess,
    sf_for,
)

BRANCHES = [None, ["acs"], ["acs", "tickets"]]
BRANCH_IDS = ["no-restriction", "surface-acs", "surface-acs-tickets"]


def _run_main(mod, project_root, output_path, surface_args):
    argv = ["--no-open", "--output", str(output_path), "--project-root", str(project_root)]
    if surface_args:
        argv += ["--surface", *surface_args]
    with pytest.raises(SystemExit) as exc_info:
        mod.main(argv)
    assert exc_info.value.code == 0, "main() must exit 0"


@pytest.mark.parametrize("surface_args", BRANCHES, ids=BRANCH_IDS)
def test_page_edges_have_both_ends_drawn_in_every_branch(tmp_path, monkeypatch, surface_args):
    # covers: KM-KGS-100b-2-i
    # angle: criterion
    """Every DATA edge's ends are DATA.nodes ids in every branch; the
    dangling edge (KM-EX-060 -> an id no node carries) is left out; the real
    edge KM-EX-060 -> KM-EX-059 survives."""
    project_root = build_dangling_edge_fixture(tmp_path)
    real_kq = load_real_kq_module()
    ghost_kq = GhostEdgeKQ(real_kq, source_id="KM-EX-060", ghost_target_id="KM-EX-GHOST")
    mod = load_visualiser_module()
    monkeypatch.setattr(mod, "_load_kq_module", lambda: ghost_kq)

    output_path = tmp_path / "page.html"
    _run_main(mod, project_root, output_path, surface_args)

    html = output_path.read_text(encoding="utf-8")
    data, _colors = extract_data_and_colors(html)
    node_ids = {n["id"] for n in data["nodes"]}

    for edge in data["edges"]:
        assert edge["source"] in node_ids, f"dangling source in {edge!r}"
        assert edge["target"] in node_ids, f"dangling target in {edge!r}"

    edge_pairs = {(e["source"], e["target"]) for e in data["edges"]}
    assert ("KM-EX-060", "KM-EX-059") in edge_pairs, "the real edge must still be drawn"
    assert not any(
        s == "KM-EX-GHOST" or t == "KM-EX-GHOST" for s, t in edge_pairs
    ), "the ghost edge must be left out, not crash the page"


@pytest.mark.parametrize("surface_args", BRANCHES, ids=BRANCH_IDS)
def test_page_script_link_and_adjacency_builds_cannot_hit_unknown_id(tmp_path, monkeypatch, surface_args):
    # covers: KM-KGS-100b-2-i
    # angle: seam
    """Static anchor proves the shipped script still builds adjacency and
    resolves forceLink the modelled way; the Python replay of both crash
    sites must not hit an unknown id; KM-EX-060's adjacency set is exactly
    itself plus its drawn neighbours."""
    project_root = build_dangling_edge_fixture(tmp_path)
    real_kq = load_real_kq_module()
    ghost_kq = GhostEdgeKQ(real_kq, source_id="KM-EX-060", ghost_target_id="KM-EX-GHOST")
    mod = load_visualiser_module()
    monkeypatch.setattr(mod, "_load_kq_module", lambda: ghost_kq)

    output_path = tmp_path / "page.html"
    _run_main(mod, project_root, output_path, surface_args)

    html = output_path.read_text(encoding="utf-8")
    assert_script_shape_unchanged(html)

    data, _colors = extract_data_and_colors(html)
    adjacency = replay_adjacency_and_forcelink(data)

    if "KM-EX-060" in adjacency:
        expected = {"KM-EX-060"}
        for e in data["edges"]:
            if e["source"] == "KM-EX-060":
                expected.add(e["target"])
            if e["target"] == "KM-EX-060":
                expected.add(e["source"])
        assert adjacency["KM-EX-060"] == expected


@pytest.mark.parametrize("surface_args", BRANCHES, ids=BRANCH_IDS)
def test_left_out_count_and_denominator_on_stderr_zero_included(tmp_path, monkeypatch, capsys, surface_args):
    # covers: KM-KGS-100b-2-i
    # angle: criterion
    """stderr always states how many relationships were left out and out of
    how many; 0 is stated explicitly when nothing was left out; the stated
    denominator reconciles with len(DATA.edges) + left_out.

    ASSUMED FORMAT (not pinned by the AC or its test_rationale): "Left out N
    of M relationships" on stderr, matched via km_kgs_100b_2_shared.LEFT_OUT_RE.
    """
    project_root = build_dangling_edge_fixture(tmp_path)
    real_kq = load_real_kq_module()
    sf = sf_for(surface_args)
    paths_json = project_root / "config" / "paths.json"

    for with_ghost in (True, False):
        kq = (
            GhostEdgeKQ(real_kq, source_id="KM-EX-060", ghost_target_id="KM-EX-GHOST")
            if with_ghost
            else real_kq
        )
        mod = load_visualiser_module()
        monkeypatch.setattr(mod, "_load_kq_module", lambda kq=kq: kq)

        output_path = tmp_path / f"page_{with_ghost}.html"
        _run_main(mod, project_root, output_path, surface_args)
        captured = capsys.readouterr()

        html = output_path.read_text(encoding="utf-8")
        data, _colors = extract_data_and_colors(html)
        final_edge_count = len(data["edges"])

        _raw_nodes, raw_edges = kq._collect_all(project_root, paths_json, surface_filter=sf)
        raw_count = len(raw_edges)

        match = LEFT_OUT_RE.search(captured.err)
        assert match is not None, f"stderr must state a left-out count; got: {captured.err!r}"
        left_out, denominator = int(match.group(1)), int(match.group(2))

        assert left_out == raw_count - final_edge_count, (
            f"left-out ({left_out}) must equal raw edges handed to the assembler "
            f"({raw_count}) minus DATA.edges ({final_edge_count})"
        )
        assert denominator == raw_count, "denominator must reconcile with the page"

        if not with_ghost and surface_args is None:
            assert left_out == 0, "no-ghost, no-restriction run must state 0 left out explicitly"


@pytest.mark.parametrize("surface_args", BRANCHES, ids=BRANCH_IDS)
def test_real_repository_pages_draw_with_no_dangling_edge_in_every_branch(tmp_path, surface_args):
    # covers: KM-KGS-100b-2-i
    # angle: real_artifact
    """Real subprocess against the real repository. The dangling-edge guard
    itself is currently satisfied against the real repo (0 dangling edges
    since KM-KGS-100d-4 / PR #899), but the left-out stderr message
    (ASSUMED FORMAT) does not exist in any branch yet -- RED via that."""
    assert REPO_ROOT.exists() and (REPO_ROOT / "config" / "paths.json").exists(), (
        "real repo root and config/paths.json must exist -- this must FAIL, never skip"
    )
    output_path = tmp_path / "page.html"
    extra_args = ["--surface", *surface_args] if surface_args else []
    result = run_visualiser_subprocess(REPO_ROOT, output_path, extra_args=extra_args)
    assert result.returncode == 0, result.stderr

    html = output_path.read_text(encoding="utf-8")
    data, _colors = extract_data_and_colors(html)
    assert len(data["nodes"]) > 0

    node_ids = {n["id"] for n in data["nodes"]}
    for edge in data["edges"]:
        assert edge["source"] in node_ids
        assert edge["target"] in node_ids
    replay_adjacency_and_forcelink(data)

    match = LEFT_OUT_RE.search(result.stderr)
    assert match is not None, f"stderr must state a left-out count; got: {result.stderr!r}"
