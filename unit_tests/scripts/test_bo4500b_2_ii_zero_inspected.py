"""
MODULE: unit_tests/scripts/test_bo4500b_2_ii_zero_inspected.py
GOAL: BO-4500b-2-ii - a check that inspected nothing fails; declared-awaiting blocks are listed
    separately; an undeclared source with no installed copy fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo4500b2_support as T  # noqa: E402
import _bo4500b1_support as S  # noqa: E402

ALPHA_ONLY_ROUTES = {"route-a.js": S.ROUTES["route-a.js"], "route-c.js": S.ROUTES["route-c.js"]}


def _awaiting_beta(tmp_path, monkeypatch):
    pkg = S.make_package(tmp_path, monkeypatch, routes=ALPHA_ONLY_ROUTES)
    (pkg.wf / "_shared" / "awaiting-adoption.json").write_text(
        json.dumps({"BETA-ANSWER": ["BO-9999-x"]}), encoding="utf-8")
    return pkg, S.install(pkg)


def test_zero_inspected_copies_fails_naming_the_location(tmp_path, monkeypatch):
    # covers: BO-4500b-2-ii
    # angle: failure
    """Wrong versions caught: report a pass on nothing; skip silently when no routes are found."""
    pkg = S.make_package(tmp_path, monkeypatch, routes={}, sources={})
    empty = tmp_path / "empty_location"
    empty.mkdir()
    result = T.run_check(empty, pkg.root)
    assert result["passed"] is False
    assert result["inspected_total"] == 0
    assert "zero installed copies" in result["message"].lower()
    assert str(empty) in result["message"]


def test_declared_block_with_no_copy_is_listed_as_not_inspected(tmp_path, monkeypatch):
    # covers: BO-4500b-2-ii
    # angle: criterion
    """BETA declared awaiting adoption, no installed copy: listed as not inspected, check still passes."""
    pkg, wf = _awaiting_beta(tmp_path, monkeypatch)
    result = T.run_check(wf.parent, pkg.root)
    assert result["passed"] is True, result["message"]
    assert [n["block"] for n in result["not_inspected"]] == ["BETA-ANSWER"]
    assert "awaits adoption" in result["not_inspected"][0]["reason"].lower() or \
        "awaiting adoption" in result["not_inspected"][0]["reason"].lower()
    assert "BETA-ANSWER" in result["message"]


def test_uninspected_block_is_not_counted_as_matched(tmp_path, monkeypatch):
    # covers: BO-4500b-2-ii
    # angle: discrimination
    """Wrong version caught: count a declared but uninspected block among the matched blocks."""
    pkg, wf = _awaiting_beta(tmp_path, monkeypatch)
    result = T.run_check(wf.parent, pkg.root)
    assert [m["block"] for m in result["matched"]] == ["ALPHA-ANSWER"]
    assert result["matched"][0]["inspected"] == 1


def test_undeclared_block_without_copy_fails(tmp_path, monkeypatch):
    # covers: BO-4500b-2-ii
    # angle: failure
    """ALPHA source exists, undeclared, installed routes carry only BETA: fails naming ALPHA-ANSWER."""
    routes = {"route-b2.js": "// route\n" + S.pair("BETA-ANSWER") + "x();\n", "route-c.js": S.ROUTES["route-c.js"]}
    pkg = S.make_package(tmp_path, monkeypatch, routes=routes, sources={"beta-answer.js": S.SOURCES["beta-answer.js"]})
    wf = S.install(pkg)
    # the source appears after the install, as when consumers were removed since an earlier layout
    (pkg.wf / "_shared" / "alpha-answer.js").write_text(S.SOURCES["alpha-answer.js"], encoding="utf-8")
    result = T.run_check(wf.parent, pkg.root)
    assert result["passed"] is False
    assert result["missing_blocks"] == ["ALPHA-ANSWER"]
    assert "ALPHA-ANSWER" in result["message"] and "no installed copy" in result["message"].lower()


def test_zero_copy_failure_is_reachable_after_a_real_install(tmp_path, monkeypatch):
    # covers: BO-4500b-2-ii
    # angle: reachability
    """Real install of templates marking no block, then the check on that layout fails with zero inspected."""
    routes = {"route-c.js": S.ROUTES["route-c.js"]}
    pkg = S.make_package(tmp_path, monkeypatch, routes=routes, sources={})
    wf = S.install(pkg)
    assert (wf / "route-c.js").exists()
    result = T.run_check(wf.parent, pkg.root)
    assert result["passed"] is False
    assert "zero installed copies" in result["message"].lower()
    assert str(wf.parent) in result["message"]
