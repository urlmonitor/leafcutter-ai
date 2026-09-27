"""
Tests for KM-KGS-100b-2-ii: "Files named by requirements and tickets are
drawn on the page, and a missing file looks different."

Written BEFORE the fix (TDD / test-first). RED baseline expected: today
_assemble_graph() builds each DATA node with only id/surface/title/
description/color -- it never reads NodeRecord.missing, so the "missing"
key never reaches DATA at all; SURFACE_COLORS has no 'files' entry; the D3
script has no missing-only visual treatment, legend row, or tooltip branch.

All fixtures come from wrapping the REAL knowledge_query._collect_all output
(UnmarkedFilesNodeKQ) or from a real on-disk temp project (present/missing
determined by whether the file actually exists) -- never a hand-built graph.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from km_kgs_100d_4_shared import run_cli_json  # noqa: E402

from km_kgs_100b_2_shared import (  # noqa: E402
    REPO_ROOT,
    UnmarkedFilesNodeKQ,
    build_file_drawing_fixture,
    extract_data_and_colors,
    find_missing_branch_token,
    load_real_kq_module,
    load_visualiser_module,
    run_visualiser_subprocess,
)

#: Every SURFACE_COLORS entry that existed on 2026-09-25, pinned in the test
#: (no git ref) per KM-KGS-100b-2-ii's test_rationale.
_PINNED_COLORS_2026_09_25 = {
    "agent": "#2dd4bf", "agents": "#2dd4bf",
    "skill": "#f87171", "skills": "#f87171",
    "ticket": "#fbbf24", "tickets": "#fbbf24",
    "doc": "#4ade80", "docs": "#4ade80",
    "adr": "#c084fc", "adrs": "#c084fc",
    "component": "#60a5fa", "components": "#60a5fa",
    "roadmap": "#fb923c",
    "glossary": "#94a3b8",
    "acs": "#f472b6",
}


def _generate_page(tmp_path, project_root, filename="page.html"):
    mod = load_visualiser_module()
    output_path = tmp_path / filename
    with pytest.raises(SystemExit) as exc_info:
        mod.main(["--no-open", "--output", str(output_path), "--project-root", str(project_root)])
    assert exc_info.value.code == 0, "main() must exit 0"
    return output_path.read_text(encoding="utf-8")


def test_present_and_missing_file_nodes_and_edges_reach_the_page(tmp_path):
    # covers: KM-KGS-100b-2-ii
    # angle: criterion
    """Both file nodes and both implemented_by edges from KM-EX-070 reach
    DATA, each with surface 'files'."""
    project_root = build_file_drawing_fixture(tmp_path)
    html = _generate_page(tmp_path, project_root)
    data, _colors = extract_data_and_colors(html)

    by_id = {n["id"]: n for n in data["nodes"]}
    assert "scripts/foo.py" in by_id
    assert "scripts/removed_tool.py" in by_id
    assert by_id["scripts/foo.py"]["surface"] == "files"
    assert by_id["scripts/removed_tool.py"]["surface"] == "files"

    edge_pairs = {(e["source"], e["target"]) for e in data["edges"]}
    assert ("KM-EX-070", "scripts/foo.py") in edge_pairs
    assert ("KM-EX-070", "scripts/removed_tool.py") in edge_pairs


def test_missing_mark_reaches_page_data_explicitly(tmp_path):
    # covers: KM-KGS-100b-2-ii
    # angle: seam
    """DATA node for the missing file carries missing === true; the present
    file carries missing === false, as real JSON booleans, present as keys."""
    project_root = build_file_drawing_fixture(tmp_path)
    html = _generate_page(tmp_path, project_root)
    data, _colors = extract_data_and_colors(html)
    by_id = {n["id"]: n for n in data["nodes"]}

    assert "missing" in by_id["scripts/foo.py"], "present file node must carry an explicit 'missing' key"
    assert by_id["scripts/foo.py"]["missing"] is False
    assert "missing" in by_id["scripts/removed_tool.py"], "missing file node must carry an explicit 'missing' key"
    assert by_id["scripts/removed_tool.py"]["missing"] is True


def test_files_surface_has_its_own_legend_colour_and_existing_colours_unchanged(tmp_path):
    # covers: KM-KGS-100b-2-ii
    # angle: criterion
    """SURFACE_COLORS has a distinct 'files' entry; every colour that
    existed on 2026-09-25 keeps its value; the generated page's embedded
    SURFACE_COLORS JSON also carries 'files'."""
    mod = load_visualiser_module()
    for surface, color in _PINNED_COLORS_2026_09_25.items():
        assert mod.SURFACE_COLORS.get(surface) == color, f"{surface} colour must not change"

    assert "files" in mod.SURFACE_COLORS, "SURFACE_COLORS must have a 'files' entry"
    files_color = mod.SURFACE_COLORS["files"]
    assert files_color not in _PINNED_COLORS_2026_09_25.values(), "files colour must differ from every existing colour"

    project_root = build_file_drawing_fixture(tmp_path)
    html = _generate_page(tmp_path, project_root)
    _data, colors = extract_data_and_colors(html)
    assert "files" in colors


def test_missing_treatment_legend_row_and_tooltip_are_emitted(tmp_path):
    # covers: KM-KGS-100b-2-ii
    # angle: criterion
    """Static, browser-free checks: a legend row labelled exactly 'missing
    file'; a missing-only visual branch keyed on d.missing; the word
    'missing' also appears outside the legend row (i.e. in a tooltip or
    node-styling branch too)."""
    project_root = build_file_drawing_fixture(tmp_path)
    html = _generate_page(tmp_path, project_root)

    assert "missing file" in html, "legend must have a row labelled exactly 'missing file'"
    token = find_missing_branch_token(html)
    assert token, "the missing branch must set a real attribute/class name"
    assert "d.missing" in html, "some node-styling or tooltip code must branch on d.missing"
    assert html.count("missing") >= 2, (
        "'missing' must appear both in the legend row and in a tooltip/node-styling branch"
    )


def test_missing_treatment_is_not_overwritten_by_hover_or_pin(tmp_path):
    # covers: KM-KGS-100b-2-ii
    # angle: boundary
    """The attribute/class the missing branch sets must not be reassigned by
    the hover (dimming) or pin (click) handlers -- a stroke the pin styling
    overwrites would fail this test."""
    project_root = build_file_drawing_fixture(tmp_path)
    html = _generate_page(tmp_path, project_root)

    token = find_missing_branch_token(html)

    mouseover_idx = html.index("mouseover")
    mouseout_idx = html.index("mouseout")
    click_idx = html.index("'click'")
    hover_block = html[mouseover_idx:mouseout_idx]
    pin_block = html[click_idx:]

    assert token not in hover_block, f"hover handler must not touch the missing treatment {token!r}"
    assert token not in pin_block, f"pin handler must not touch the missing treatment {token!r}"


def test_unmarked_files_node_is_drawn_as_present(tmp_path, monkeypatch):
    # covers: KM-KGS-100b-2-ii
    # angle: boundary
    """Backward compatibility with map data produced before this change: a
    files-surface node carrying NO missing attribute at all must degrade to
    present, not missing, in the generated page."""
    project_root = build_file_drawing_fixture(tmp_path)
    real_kq = load_real_kq_module()
    legacy_kq = UnmarkedFilesNodeKQ(real_kq, unmark_node_id="scripts/foo.py")
    mod = load_visualiser_module()
    monkeypatch.setattr(mod, "_load_kq_module", lambda: legacy_kq)

    output_path = tmp_path / "page.html"
    with pytest.raises(SystemExit) as exc_info:
        mod.main(["--no-open", "--output", str(output_path), "--project-root", str(project_root)])
    assert exc_info.value.code == 0
    html = output_path.read_text(encoding="utf-8")
    data, _colors = extract_data_and_colors(html)
    by_id = {n["id"]: n for n in data["nodes"]}

    assert "missing" in by_id["scripts/foo.py"], "DATA node must always carry an explicit 'missing' key"
    assert by_id["scripts/foo.py"]["missing"] is False, (
        "an unmarked files node (no 'missing' attribute at all) must degrade to present"
    )


def test_real_repository_page_draws_missing_files_distinctly(tmp_path):
    # covers: KM-KGS-100b-2-ii
    # angle: real_artifact
    """Real subprocess run against the real repository: DATA has >0
    files-surface nodes, every one carries a boolean 'missing', the missing
    count is >0, that count matches knowledge_query's own JSON export for
    the same repository, and the legend markup includes the 'missing file'
    row. A missing repo root FAILS; it is never skipped."""
    assert REPO_ROOT.exists() and (REPO_ROOT / "config" / "paths.json").exists(), (
        "real repo root and config/paths.json must exist -- this must FAIL, never skip"
    )
    output_path = tmp_path / "page.html"
    result = run_visualiser_subprocess(REPO_ROOT, output_path)
    assert result.returncode == 0, result.stderr

    html = output_path.read_text(encoding="utf-8")
    data, _colors = extract_data_and_colors(html)
    files_nodes = [n for n in data["nodes"] if n["surface"] == "files"]
    assert len(files_nodes) > 0

    for n in files_nodes:
        assert "missing" in n, f"files node {n['id']!r} must carry a boolean 'missing' key"
        assert isinstance(n["missing"], bool)

    missing_count = sum(1 for n in files_nodes if n["missing"])
    assert missing_count > 0

    export = run_cli_json(REPO_ROOT)
    assert export["missing_files"] == missing_count, (
        "the page's missing count and knowledge_query's export must agree"
    )

    assert "missing file" in html
