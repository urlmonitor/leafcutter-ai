"""
MODULE: unit_tests/scripts/test_bo4500b_2_i_whitespace_drift.py
GOAL: BO-4500b-2-i - whitespace and line-ending drift is drift: the comparison is byte exact.
    Block body line N of a copy sits at installed-file line N+2 (header comment + START marker).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo4500b2_support as T  # noqa: E402
import _bo4500b1_support as S  # noqa: E402

SOURCES = {"alpha-answer.js": "function alphaBlock() {\n\n  return 'alpha {{config.output_root}}';\n}\n"}
ROUTES = {f"route-{x}.js": f"// route {x.upper()}\n" + S.pair("ALPHA-ANSWER") + "console.log(1);\n" for x in "abc"}


def _drifted(tmp_path, monkeypatch):
    pkg = S.make_package(tmp_path, monkeypatch, routes=ROUTES, sources=SOURCES)
    wf = S.install(pkg)
    layout = T.private_copy(wf, tmp_path)
    base = layout / "workflows"

    def trailing_space(body: bytes) -> bytes:
        first, rest = body.split(b"\n", 1)
        return first + b"\n" + rest.split(b"\n", 1)[0] + b" \n" + rest.split(b"\n", 1)[1]

    T.edit_block_body(base / "route-a.js", "ALPHA-ANSWER", trailing_space)
    T.edit_block_body(base / "route-b.js", "ALPHA-ANSWER", lambda b: b.replace(b"\n", b"\r\n"))
    T.edit_block_body(base / "route-c.js", "ALPHA-ANSWER", lambda b: b.replace(b"\n\n", b"\n", 1))
    return pkg, layout


def test_trailing_space_crlf_and_removed_blank_line_are_each_named(tmp_path, monkeypatch):
    # covers: BO-4500b-2-i
    # angle: discrimination
    """Wrong versions caught: strip trailing whitespace; normalise line endings; tolerate a missing blank line."""
    pkg, layout = _drifted(tmp_path, monkeypatch)
    result = T.run_check(layout, pkg.root)
    assert result["passed"] is False
    assert len(result["differences"]) == 3
    for route in ("route-a.js", "route-b.js", "route-c.js"):
        d = T.diff_for(result, route)
        assert d["block"] == "ALPHA-ANSWER"
        assert isinstance(d["first_differing_line"], int) and d["first_differing_line"] >= 1
    assert T.diff_for(result, "route-a.js")["first_differing_line"] == 4
    assert T.diff_for(result, "route-b.js")["first_differing_line"] == 3
    assert T.diff_for(result, "route-c.js")["first_differing_line"] == 4


def test_no_whitespace_normalised_copy_is_reported_as_match(tmp_path, monkeypatch):
    # covers: BO-4500b-2-i
    # angle: discrimination
    """Wrong version caught: read the installed copy in text mode so CRLF becomes LF before comparing."""
    pkg, layout = _drifted(tmp_path, monkeypatch)
    assert b"\r\n" in (layout / "workflows" / "route-b.js").read_bytes()
    result = T.run_check(layout, pkg.root)
    matched_routes = [r for m in result["matched"] for r in m["routes"]]
    assert matched_routes == []
    assert result["passed"] is False


def test_whitespace_drift_is_reachable_after_a_real_install(tmp_path, monkeypatch):
    # covers: BO-4500b-2-i
    # angle: reachability
    """Real install first proves the untouched layout passes, then the edited private copy fails."""
    pkg = S.make_package(tmp_path, monkeypatch, routes=ROUTES, sources=SOURCES)
    wf = S.install(pkg)
    clean = T.run_check(wf.parent, pkg.root)
    assert clean["passed"] is True, clean["message"]
    layout = T.private_copy(wf, tmp_path)
    T.edit_block_body(layout / "workflows" / "route-a.js", "ALPHA-ANSWER", lambda b: b.replace(b"\n", b" \n", 1))
    result = T.run_check(layout, pkg.root)
    assert result["passed"] is False
    assert T.diff_for(result, "route-a.js")["block"] == "ALPHA-ANSWER"
    assert not T.named(result, "route-b.js")
