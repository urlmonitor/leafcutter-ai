"""
MODULE: unit_tests/scripts/_bo4500b1_support.py
GOAL: Temporary-package fixtures for BO-4500b-1: ALPHA/BETA/GAMMA blocks and routes A/B/C,
    installed through the REAL build_workflow_scripts (no per-test build.py subprocess).

Marker grammar (same as WORKSPACE-ANSWER): ``// <NAME>-START`` / ``// <NAME>-END``; the source of
block NAME is ``_shared/<name-lowercased>.js``.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_phases  # noqa: E402

SOURCES = {
    "alpha-answer.js": "function alphaBlock() {\n  return 'alpha {{config.output_root}}';\n}\n",
    "beta-answer.js": "function betaBlock() {\n  return 'beta';\n}\n",
}
GAMMA = ("gamma-answer.js", "function gammaBlock() {\n  return 'gamma';\n}\n")


def pair(name: str) -> str:
    """Return an empty START/END marker pair for block ``name``."""
    return f"// {name}-START\n// {name}-END\n"


ROUTES = {
    "route-a.js": "// route A\n" + pair("ALPHA-ANSWER") + "console.log('a {{config.output_root}}');\n",
    "route-b.js": "// route B\n" + pair("ALPHA-ANSWER") + "// middle\n" + pair("BETA-ANSWER") + "console.log('b');\n",
    "route-c.js": "// route C {{config.output_root}}\nconsole.log('c');\n",
}


@dataclass
class Package:
    root: Path
    wf: Path
    target: Path


def make_package(tmp_path: Path, monkeypatch, routes: dict[str, str] | None = None,
                 sources: dict[str, str] | None = None) -> Package:
    """Lay out a fixture package of block sources and routes, pointing build_phases at it."""
    root = tmp_path / "pkg"
    wf = root / "templates" / "workflows-js"
    (wf / "_shared").mkdir(parents=True)
    for name, text in (sources if sources is not None else SOURCES).items():
        (wf / "_shared" / name).write_text(text, encoding="utf-8")
    for name, text in (routes if routes is not None else ROUTES).items():
        (wf / name).write_text(text, encoding="utf-8")
    monkeypatch.setattr(build_phases, "TEMPLATES_DIR", root / "templates")
    monkeypatch.setattr(build_phases, "PACKAGE_ROOT", root)
    monkeypatch.setenv("CLAUDE_CODE_VERSION", "2.5.0")
    return Package(root=root, wf=wf, target=tmp_path / "target")


def install(pkg: Package, extra_config: dict[str, Any] | None = None) -> Path:
    """Run the real workflow-scripts install for ``pkg``; return the installed workflows dir."""
    config: dict[str, Any] = {"workflows": {"enabled": True}, "output_root": ".leafcutter"}
    config.update(extra_config or {})
    build_phases.build_workflow_scripts(pkg.target, config, dry_run=False, force=True)
    return pkg.target / "workflows"


def between(text: str, name: str) -> str | None:
    """Text between the START line and the END marker of ``name`` (None if the pair is absent)."""
    start = f"// {name}-START\n"
    a = text.find(start)
    b = text.find(f"// {name}-END")
    if a == -1 or b == -1 or b < a:
        return None
    return text[a + len(start):b]
