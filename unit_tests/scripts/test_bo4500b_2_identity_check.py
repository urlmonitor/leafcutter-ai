"""
MODULE: unit_tests/scripts/test_bo4500b_2_identity_check.py
GOAL: BO-4500b-2 - the identity check names every installed copy of a shared block that differs
    from its rendered source, discovers routes from installed text, and reports per-block counts.
    Implementation target: scripts/shared_block_identity.py::check_identity (see _bo4500b2_support).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo4500b2_support as T  # noqa: E402
import _bo4500b1_support as S  # noqa: E402

ROUTE_D = "// route D\n" + S.pair("ALPHA-ANSWER") + "console.log('d');\n"


def _installed(tmp_path, monkeypatch, routes=None):
    pkg = S.make_package(tmp_path, monkeypatch, routes=routes)
    wf = S.install(pkg)
    return pkg, wf


def _flip_char(body: bytes) -> bytes:
    return body.replace(b"alpha", b"alphA", 1)


def test_edited_copy_is_named_with_block_and_first_differing_line(tmp_path, monkeypatch):
    # covers: BO-4500b-2
    # angle: criterion
    """One character changed in route B's installed ALPHA text: B, ALPHA-ANSWER and its 1-based line named."""
    pkg, wf = _installed(tmp_path, monkeypatch)
    layout = T.private_copy(wf, tmp_path)
    route_b = layout / "workflows" / "route-b.js"
    T.edit_block_body(route_b, "ALPHA-ANSWER", _flip_char)
    result = T.run_check(layout, pkg.root)
    assert result["passed"] is False
    d = T.diff_for(result, "route-b.js")
    assert d["block"] == "ALPHA-ANSWER"
    lines = route_b.read_bytes().split(b"\n")
    expected = next(i for i, ln in enumerate(lines, 1) if b"alphA" in ln)
    assert d["first_differing_line"] == expected
    assert "ALPHA-ANSWER" in result["message"] and "route-b.js" in result["message"]


def test_undrifted_route_is_not_named(tmp_path, monkeypatch):
    # covers: BO-4500b-2
    # angle: discrimination
    """Wrong version caught: name every consumer whenever any copy drifts."""
    pkg, wf = _installed(tmp_path, monkeypatch)
    layout = T.private_copy(wf, tmp_path)
    T.edit_block_body(layout / "workflows" / "route-b.js", "ALPHA-ANSWER", _flip_char)
    result = T.run_check(layout, pkg.root)
    assert len(result["differences"]) == 1
    assert not T.named(result, "route-a.js")
    assert T.named(result, "route-b.js")


def test_newly_added_route_is_discovered_without_changing_the_check(tmp_path, monkeypatch):
    # covers: BO-4500b-2
    # angle: discrimination
    """Wrong version caught: a hard-coded list of routes to check."""
    routes = dict(S.ROUTES)
    routes["route-d.js"] = ROUTE_D
    pkg, wf = _installed(tmp_path, monkeypatch, routes=routes)
    layout = T.private_copy(wf, tmp_path)
    T.edit_block_body(layout / "workflows" / "route-d.js", "ALPHA-ANSWER", _flip_char)
    result = T.run_check(layout, pkg.root)
    assert result["passed"] is False
    assert [d["route"].endswith("route-d.js") for d in result["differences"]] == [True]
    assert not T.named(result, "route-a.js") and not T.named(result, "route-b.js")


def test_correct_install_passes_with_rendered_placeholders(tmp_path, monkeypatch):
    # covers: BO-4500b-2
    # angle: criterion
    """ALPHA source holds {{config.output_root}}; the untouched install matches the RENDERED source."""
    pkg, wf = _installed(tmp_path, monkeypatch)
    assert "{{config." in S.SOURCES["alpha-answer.js"]
    installed = (wf / "route-a.js").read_text(encoding="utf-8")
    assert ".leafcutter" in installed and "{{config." not in installed
    result = T.run_check(wf.parent, pkg.root)
    assert result["passed"] is True, result["message"]
    assert result["differences"] == []


def test_pass_report_lists_inspected_count_and_routes_per_block(tmp_path, monkeypatch):
    # covers: BO-4500b-2
    # angle: criterion
    """ALPHA is carried by routes A and B (2 copies); BETA only by B (1 copy)."""
    pkg, wf = _installed(tmp_path, monkeypatch)
    result = T.run_check(wf.parent, pkg.root)
    assert result["passed"] is True, result["message"]
    by_block = {m["block"]: m for m in result["matched"]}
    assert set(by_block) == {"ALPHA-ANSWER", "BETA-ANSWER"}
    assert by_block["ALPHA-ANSWER"]["inspected"] == 2
    assert [r.rsplit("/", 1)[-1] for r in sorted(by_block["ALPHA-ANSWER"]["routes"])] == ["route-a.js", "route-b.js"]
    assert by_block["BETA-ANSWER"]["inspected"] == 1
    assert [r.rsplit("/", 1)[-1] for r in by_block["BETA-ANSWER"]["routes"]] == ["route-b.js"]


def test_identity_check_is_reachable_after_a_real_install(tmp_path, monkeypatch):
    # covers: BO-4500b-2
    # angle: reachability
    """Real build_workflow_scripts install, then the check over that layout: passes, non-empty report."""
    pkg = S.make_package(tmp_path, monkeypatch)
    wf = S.install(pkg)
    assert (wf / "route-a.js").exists()
    result = T.run_check(wf.parent, pkg.root)
    assert result["passed"] is True, result["message"]
    assert result["inspected_total"] == 3
    assert result["matched"]
