"""
MODULE: unit_tests/scripts/test_bo4500b_1_shared_block_fill.py
GOAL: BO-4500b-1 -- a block written once is filled into every route that marks a place for it,
    byte for byte, each time the package is installed (general mechanism, ALPHA/BETA/GAMMA).
RED TODAY: build_phases_workflows.py only knows WORKSPACE-ANSWER, so ALPHA/BETA pairs stay empty.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bo4500b1_support as S  # noqa: E402
from template_compiler import inject_config  # noqa: E402

ALPHA = S.SOURCES["alpha-answer.js"].replace("{{config.output_root}}", ".leafcutter")
BETA = S.SOURCES["beta-answer.js"]


def _read(out: Path, name: str) -> str:
    return (out / name).read_text(encoding="utf-8")


def test_fill_is_byte_exact_per_named_block(tmp_path, monkeypatch):
    # covers: BO-4500b-1
    # angle: criterion
    """Text between each installed marker pair equals the named block's source bytes."""
    out = S.install(S.make_package(tmp_path, monkeypatch))
    assert S.between(_read(out, "route-a.js"), "ALPHA-ANSWER") == ALPHA
    assert S.between(_read(out, "route-b.js"), "ALPHA-ANSWER") == ALPHA
    assert S.between(_read(out, "route-b.js"), "BETA-ANSWER") == BETA


def test_marker_free_route_equals_unfilled_install_output(tmp_path, monkeypatch):
    # covers: BO-4500b-1
    # angle: criterion
    """Route C equals its template after config injection only (and the fill did happen elsewhere)."""
    pkg = S.make_package(tmp_path, monkeypatch)
    out = S.install(pkg)
    assert S.between(_read(out, "route-a.js"), "ALPHA-ANSWER") == ALPHA, "fill did not run on route A"
    expected = inject_config(S.ROUTES["route-c.js"], {"output_root": ".leafcutter"})
    assert _read(out, "route-c.js") == expected


def test_templates_keep_empty_marker_pairs_after_install(tmp_path, monkeypatch):
    # covers: BO-4500b-1
    # angle: criterion
    """Templates are byte-identical after install and each pair is still empty."""
    pkg = S.make_package(tmp_path, monkeypatch)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in pkg.wf.glob("*.js")}
    out = S.install(pkg)
    assert S.between(_read(out, "route-a.js"), "ALPHA-ANSWER") == ALPHA, "fill did not run"
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in pkg.wf.glob("*.js")}
    assert before == after
    assert S.between((pkg.wf / "route-a.js").read_text(encoding="utf-8"), "ALPHA-ANSWER") == ""


def test_changed_source_line_reaches_every_consumer(tmp_path, monkeypatch):
    # covers: BO-4500b-1
    # angle: criterion
    """Change one ALPHA line, install again: A and B carry it, nothing carries the old line."""
    pkg = S.make_package(tmp_path, monkeypatch)
    out = S.install(pkg)
    assert "alpha .leafcutter" in _read(out, "route-a.js"), "first install did not fill"
    src = pkg.wf / "_shared" / "alpha-answer.js"
    src.write_text(src.read_text(encoding="utf-8").replace("alpha {{", "ALPHA-CHANGED {{"), encoding="utf-8")
    out = S.install(pkg)
    for name in ("route-a.js", "route-b.js"):
        text = _read(out, name)
        assert "ALPHA-CHANGED .leafcutter" in text, name
        assert "return 'alpha .leafcutter'" not in text, name


def test_reinstall_with_no_change_is_byte_stable_and_writes_nothing(tmp_path, monkeypatch):
    # covers: BO-4500b-1
    # angle: criterion
    """A further install with unchanged inputs leaves bytes and mtimes untouched."""
    pkg = S.make_package(tmp_path, monkeypatch)
    out = S.install(pkg)
    assert S.between(_read(out, "route-a.js"), "ALPHA-ANSWER") == ALPHA, "fill did not run"
    snap = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in out.glob("*.js")}
    for p in out.glob("*.js"):
        os.utime(p, ns=(1_000_000_000, 1_000_000_000))
    snap = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in out.glob("*.js")}
    out = S.install(pkg)
    assert snap == {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in out.glob("*.js")}


def test_block_placeholder_is_resolved_in_every_copy(tmp_path, monkeypatch):
    # covers: BO-4500b-1
    # angle: criterion
    """{{config.output_root}} inside ALPHA is resolved in every copy; no raw token ships."""
    out = S.install(S.make_package(tmp_path, monkeypatch), {"output_root": ".custom-root"})
    for name in ("route-a.js", "route-b.js"):
        block = S.between(_read(out, name), "ALPHA-ANSWER")
        assert block is not None and "alpha .custom-root" in block, name
        assert "{{config" not in block, name


def test_new_block_fills_new_consumer(tmp_path, monkeypatch):
    # covers: BO-4500b-1
    # angle: criterion
    """Add only a GAMMA source and a marker pair in route C: route C carries GAMMA's text."""
    routes = dict(S.ROUTES)
    routes["route-c.js"] = routes["route-c.js"] + S.pair("GAMMA-ANSWER")
    sources = dict(S.SOURCES)
    sources[S.GAMMA[0]] = S.GAMMA[1]
    out = S.install(S.make_package(tmp_path, monkeypatch, routes, sources))
    assert S.between(_read(out, "route-c.js"), "GAMMA-ANSWER") == S.GAMMA[1]


def test_no_install_code_change_needed_for_new_block(tmp_path, monkeypatch):
    # covers: BO-4500b-1
    # angle: discrimination
    """GAMMA works with the module unmodified, and the module holds no block or consumer list.

    Wrong versions caught: a hard-coded list of block names; a hard-coded list of consumer routes.
    """
    module_src = (S.SCRIPTS_DIR / "build_phases_workflows.py").read_text(encoding="utf-8")
    code = "\n".join(line for line in module_src.splitlines() if not line.lstrip().startswith("#"))
    assert not re.search(r"""['"][A-Z][A-Z0-9-]*-ANSWER""", code), "block name literal in the install code"
    assert not re.search(r"""['"](?:fast-lane-ship|plan-feature|quick-fix|finalize-feature)\.js['"]""", code)
    routes = dict(S.ROUTES)
    routes["route-c.js"] = routes["route-c.js"] + S.pair("GAMMA-ANSWER")
    sources = dict(S.SOURCES)
    sources[S.GAMMA[0]] = S.GAMMA[1]
    out = S.install(S.make_package(tmp_path, monkeypatch, routes, sources))
    assert S.between(_read(out, "route-c.js"), "GAMMA-ANSWER") == S.GAMMA[1]


def test_fill_and_check_are_engine_free(tmp_path, monkeypatch):
    # covers: BO-4500b-1
    # angle: criterion
    """No node on PATH: the fill still runs and the installed text is judged by text alone."""
    empty_bin = tmp_path / "emptybin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))
    out = S.install(S.make_package(tmp_path, monkeypatch))
    assert S.between(_read(out, "route-a.js"), "ALPHA-ANSWER") == ALPHA
    assert S.between(_read(out, "route-b.js"), "BETA-ANSWER") == BETA


def test_shared_block_fill_is_reachable_from_the_workflow_build_phase(tmp_path, monkeypatch):
    # covers: BO-4500b-1
    # angle: reachability
    """The re-exported build_phases.build_workflow_scripts entry point fills the marker pairs."""
    assert pytest.importorskip("build_phases").build_workflow_scripts is not None
    pkg = S.make_package(tmp_path, monkeypatch)
    written = S.build_phases.build_workflow_scripts(
        pkg.target, {"workflows": {"enabled": True}, "output_root": ".leafcutter"}, dry_run=False, force=True)
    assert written == 3
    assert S.between(_read(pkg.target / "workflows", "route-a.js"), "ALPHA-ANSWER") == ALPHA


def test_installed_routes_are_written_to_the_real_output_location(tmp_path, monkeypatch):
    # covers: BO-4500b-1
    # angle: real_artifact
    """Read the installed files back from disk as bytes and compare with the block sources."""
    pkg = S.make_package(tmp_path, monkeypatch)
    S.install(pkg)
    raw = (pkg.target / "workflows" / "route-b.js").read_bytes()
    assert ALPHA.encode() in raw and BETA.encode() in raw
    assert raw.count(b"// ALPHA-ANSWER-START\n" + ALPHA.encode() + b"// ALPHA-ANSWER-END") == 1
