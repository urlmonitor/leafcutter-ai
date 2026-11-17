"""
MODULE: unit_tests/scripts/test_bo4500b_2_i_crlf_and_newline.py
GOAL: BO-4500b-2-i - a copy whose WHOLE file was converted to CRLF, and a copy that lost the final
    newline of its block body, are each named. Split from test_bo4500b_2_i_whitespace_drift.py
    for file size.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo4500b2_support as T  # noqa: E402
import _bo4500b1_support as S  # noqa: E402

SOURCES = {"alpha-answer.js": "function alphaBlock() {\n\n  return 'alpha {{config.output_root}}';\n}\n"}
ROUTES = {f"route-{x}.js": f"// route {x.upper()}\n" + S.pair("ALPHA-ANSWER") + "console.log(1);\n" for x in "abc"}


def _layout(tmp_path, monkeypatch):
    pkg = S.make_package(tmp_path, monkeypatch, routes=ROUTES, sources=SOURCES)
    wf = S.install(pkg)
    return pkg, T.private_copy(wf, tmp_path)


def test_whole_file_crlf_route_is_named_with_a_line_and_still_counted(tmp_path, monkeypatch):
    # covers: BO-4500b-2-i
    # angle: discrimination
    """Wrong version caught: find the copy only through a byte-exact LF START line, so a route
    converted whole to CRLF is never inspected and the check passes."""
    pkg, layout = _layout(tmp_path, monkeypatch)
    route_b = layout / "workflows" / "route-b.js"
    raw = route_b.read_bytes()
    assert b"\r" not in raw
    route_b.write_bytes(raw.replace(b"\n", b"\r\n"))
    result = T.run_check(layout, pkg.root)
    assert result["passed"] is False
    entry = T.diff_for(result, "route-b.js")
    assert entry["block"] == "ALPHA-ANSWER"
    assert entry["first_differing_line"] == 3
    assert result["inspected_total"] == 3
    assert not T.named(result, "route-a.js")
    assert not T.named(result, "route-c.js")


def test_missing_final_newline_of_block_body_is_named(tmp_path, monkeypatch):
    # covers: BO-4500b-2-i
    # angle: discrimination
    """Wrong version caught: tolerate a missing trailing newline (strip the body before comparing)."""
    pkg, layout = _layout(tmp_path, monkeypatch)
    route_c = layout / "workflows" / "route-c.js"
    T.edit_block_body(route_c, "ALPHA-ANSWER", lambda body: body[:-1])
    assert b"}// ALPHA-ANSWER-END" in route_c.read_bytes()
    result = T.run_check(layout, pkg.root)
    assert result["passed"] is False
    entry = T.diff_for(result, "route-c.js")
    assert entry["block"] == "ALPHA-ANSWER"
    assert isinstance(entry["first_differing_line"], int) and entry["first_differing_line"] >= 3
    assert not T.named(result, "route-a.js")
    assert result["inspected_total"] == 3


def test_start_without_end_and_end_without_start_are_reported(tmp_path, monkeypatch):
    # covers: BO-4500b-2
    # angle: failure
    """Wrong version caught: skip a START with no END, or an END whose START was corrupted, silently."""
    pkg, layout = _layout(tmp_path, monkeypatch)
    route_a = layout / "workflows" / "route-a.js"
    route_a.write_bytes(route_a.read_bytes().replace(b"// ALPHA-ANSWER-END", b"// nothing"))
    route_b = layout / "workflows" / "route-b.js"
    route_b.write_bytes(route_b.read_bytes().replace(b"// ALPHA-ANSWER-START", b"// ALPHA-ANSWER-STRAT"))
    result = T.run_check(layout, pkg.root)
    assert result["passed"] is False
    problems = {(u["route"].rsplit("/", 1)[-1], u["problem"]) for u in result["unpaired"]}
    assert problems == {("route-a.js", "START without END"), ("route-b.js", "END without START")}
    assert "route-a.js" in result["message"] and "route-b.js" in result["message"]


def test_hand_kept_and_unknown_blocks_are_reported_not_failed(tmp_path, monkeypatch):
    # covers: BO-4500b-2
    # angle: boundary
    """Wrong version caught: drop marker pairs of unknown blocks silently, or fail on them."""
    pkg, layout = _layout(tmp_path, monkeypatch)
    route_c = layout / "workflows" / "route-c.js"
    route_c.write_bytes(route_c.read_bytes() + b"// OTHER-THING-START\nx\n// OTHER-THING-END\n")
    result = T.run_check(layout, pkg.root)
    assert result["passed"] is True, result["message"]
    assert [(n["route"].rsplit("/", 1)[-1], n["block"]) for n in result["not_checked"]] == [
        ("route-c.js", "OTHER-THING")
    ]
    assert "OTHER-THING" in result["message"]
