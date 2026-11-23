"""
MODULE: unit_tests/build_orchestration/test_tq500g3ii_base_interpreter.py
GOAL: The base side of the sweep runs (TQ-500g-3-ii) runs with the LIVE repo's project interpreter and
    imports the BASE copy of the project's code, never the working tree's.
BUSINESS CONTEXT: The base side runs in a ``git archive`` export, which has no ``.git``. Resolving the
    interpreter from it fell back to ``sys.executable``; in an adopter whose dependencies live in a
    per-worktree ``.venv`` (DIAGraph) every base run crashed on the conftest import, every changed existing
    test came back inconclusive, and the gate could never pass. With the live ``.venv`` interpreter the
    other trap is its editable install: a ``.pth`` entry pointing at the WORKING TREE's ``src/``.
ARCHITECTURE: The resolution tests call ``_cs_runs._run_both`` in-process with ``run_selected`` replaced
    by a recorder. The import test builds a REAL repo with a REAL venv whose ``.pth`` editable entry names
    the working tree's ``src/``, and runs the real ``run_checks`` on both sides.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx
import unit_tests.build_orchestration._tq500g3i_fixtures as fx

_TEST = "tests/test_value.py"
_PKG = "src/pkg_tq500g3ii/__init__.py"
_BASE_TEST = "from pkg_tq500g3ii import VALUE\n\n\ndef test_value_is_base():\n    assert VALUE == 'base'\n"


def _modules():
    """``(_cs_runs, project_python)`` imported in-process (their siblings are bare imports)."""
    if str(fx.SCRIPTS) not in sys.path:
        sys.path.insert(0, str(fx.SCRIPTS))
    runs = importlib.import_module("_cs_runs")
    return runs, importlib.import_module("project_python")


def _live_repo(tmp: Path) -> tuple[Path, str]:
    """A git repo with the project package and one test committed; ``.venv`` ignored, as in an adopter."""
    root = tmp / "repo"
    gitfx.init_repo(root)
    fx.write(root / ".gitignore", ".venv/\n__pycache__/\n")
    fx.write(root / _PKG, "VALUE = 'base'\n")
    fx.write(root / _TEST, _BASE_TEST)
    return root, gitfx.commit_all(root, "base")


@pytest.mark.parametrize("kind", ["venv", "uv"])
def test_export_without_git_runs_with_the_live_roots_interpreter(tmp_path: Path, monkeypatch, kind: str):
    # covers: TQ-500g-3-ii
    # angle: failure
    # must_catch: the base side resolves its interpreter from the export (no .git) and falls back to sys.executable
    # must_catch: the two sides run with different interpreters
    runs, project_python = _modules()
    root, sha = _live_repo(tmp_path)
    if kind == "venv":
        fx.write(root / ".venv" / "bin" / "python", "")
        expected = (str(root / ".venv" / "bin" / "python"),)
    else:
        fx.write(root / "uv.lock", "version = 1\n")
        monkeypatch.setattr(project_python.shutil, "which", lambda name: "/fake/bin/uv" if name == "uv" else None)
        expected = ("/fake/bin/uv", "run", "--project", str(root), "python")
    calls = []

    def recorder(nodes, extra=None, judge=None, import_roots=()):
        cwd = nodes[0].cwd
        calls.append({"cwd": cwd, "has_git": (cwd / ".git").exists(), "judge": judge, "roots": import_roots})
        return runs.PytestRun("ran")

    monkeypatch.setattr(runs, "run_selected", recorder)
    result = runs._run_both(root, sha, [_TEST], [])
    assert result.inconclusive == [], result.inconclusive
    base, now = calls
    assert base["cwd"] != root and not base["has_git"], "the base side must run in the export (no .git)"
    assert now["cwd"] == root, now
    for side in (base, now):
        assert side["judge"] is not None and side["judge"].argv != (sys.executable,), (kind, side)
        assert side["judge"].argv == expected and side["judge"].source == kind, (kind, side)
    assert base["roots"] == (base["cwd"] / "src", base["cwd"]), "the export's src/ and root go first"
    assert now["roots"] == (), "the working tree side keeps its own import path"


def _site_packages(python: Path) -> Path:
    out = subprocess.run([str(python), "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
                         capture_output=True, text=True, check=True, timeout=60)
    return Path(out.stdout.strip())


def _venv_with_editable_install(root: Path) -> None:
    """A real ``.venv`` in *root*: pytest reachable, the project installed editable (a ``.pth`` -> live src/)."""
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(root / ".venv")],
                   check=True, capture_output=True, timeout=120)
    python = next(p for p in (root / ".venv" / "bin" / "python", root / ".venv" / "Scripts" / "python.exe")
                  if p.is_file())
    site = _site_packages(python)
    # pytest and its dependencies: the running interpreter's own site dirs (wherever this suite got pytest).
    deps = [p for p in sys.path if Path(p).name in ("site-packages", "dist-packages") and Path(p).is_dir()]
    (site / "_tq500g3ii_deps.pth").write_text("\n".join(deps) + "\n", encoding="utf-8")
    (site / "_editable_pkg_tq500g3ii.pth").write_text(str(root / "src") + "\n", encoding="utf-8")


def test_base_side_imports_the_base_code_not_the_editable_working_tree(tmp_path: Path):
    # covers: TQ-500g-3-ii
    # angle: discrimination
    # must_catch: the base side runs under sys.executable and cannot import the project package
    # must_catch: the live .venv's editable install makes the base side import the WORKING TREE's package
    runs, _project_python = _modules()
    root, sha = _live_repo(tmp_path)
    _venv_with_editable_install(root)
    fx.write(root / _PKG, "VALUE = 'now'\n")
    fx.write(root / _TEST, "import pytest\n\n\n@pytest.mark.skip(reason='later')\n" + _BASE_TEST.split("\n\n\n", 1)[1])
    pairs = [("M", _PKG), ("M", _TEST)]
    result = runs.run_checks(root, sha, pairs, "tests", [])
    assert result.inconclusive == [], f"the base side must run under the live .venv: {result.inconclusive}"
    assert [(w["file"], w["test"], w["what"]) for w in result.weakened] == [
        (_TEST, "test_value_is_base", "skipped")], f"the base run must PASS on the base copy: {result.weakened}"
