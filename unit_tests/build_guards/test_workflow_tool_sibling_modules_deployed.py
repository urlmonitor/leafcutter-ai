"""
MODULE: test_workflow_tool_sibling_modules_deployed
GOAL: Guard that every sibling module a deployed workflow tool loads through
    ``_load_sibling_module("X")`` ships with it: deployed by
    ``build_workflow_tools`` AND listed by ``_manifest_workflow_tool_scripts``.
TICKET: TICKET-20261006-DeployKnowledgeRendering
BUSINESS CONTEXT: knowledge_query.py loads its sibling modules by file path at
    import time (``_load_sibling_module``), so a sibling left out of the deploy
    set crashes every consumer install's ``.leafcutter/scripts/knowledge_query.py``
    with FileNotFoundError. Commit c2ddb6f12 shipped exactly that for
    knowledge_rendering.py. Nothing caught it: the manifest/deploy parity
    checks still agreed (both hand lists missed the file), and the BP-900g-8
    closure guard follows ``import`` statements only, never a dynamic load.
ARCHITECTURE: Runs the real ``build_workflow_tools`` against the real package
    source into a temp target (never this worktree), parses every deployed
    ``.py`` with ``ast`` for ``_load_sibling_module`` calls whose first
    argument is a string literal, and checks each named module against both
    the deployed file set and ``_manifest_workflow_tool_scripts``. Scanning the
    DEPLOYED set rather than a fixed file list makes the check transitive: a
    shipped sibling that loads a further sibling is scanned too. The gap finder
    is a pure function so its failure path is exercised on a synthetic tool
    as well (non-vacuity), independent of the real scripts.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build_phases  # noqa: E402
from build_phases_knowledge import _manifest_workflow_tool_scripts  # noqa: E402

_LOADER_NAME = "_load_sibling_module"
_DEPLOY_SIDE = "build_workflow_tools deploy"
_MANIFEST_SIDE = "_manifest_workflow_tool_scripts"


def _sibling_module_literals(source: str) -> list[str]:
    """Return every module name passed as a string literal to ``_load_sibling_module``.

    Matches both a bare call (``_load_sibling_module("x")``) and an attribute
    call (``kq._load_sibling_module("x")``). A non-literal argument (the
    loader's own ``module_name`` parameter, or prose in a docstring) is not a
    call with a string constant and is ignored.

    Args:
        source: Python source text of one deployed tool.

    Returns:
        Module names in source order, duplicates kept.
    """
    names: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        first = node.args[0]
        if func_name == _LOADER_NAME and isinstance(first, ast.Constant) and isinstance(first.value, str):
            names.append(first.value)
    return names


def _sibling_loads(scripts_dir: Path, deployed: set[str]) -> list[tuple[str, str]]:
    """Return ``(tool, module)`` for every sibling literal in a deployed ``.py`` tool."""
    loads: list[tuple[str, str]] = []
    for tool in sorted(name for name in deployed if name.endswith(".py")):
        source = (scripts_dir / tool).read_text(encoding="utf-8")
        loads.extend((tool, module) for module in _sibling_module_literals(source))
    return loads


def _sibling_gaps(scripts_dir: Path, deployed: set[str], manifest: set[str]) -> list[tuple[str, str, str]]:
    """Return ``(tool, module, missing_from)`` for each sibling load that does not ship.

    Args:
        scripts_dir: Directory holding the deployed tools to scan.
        deployed: File names ``build_workflow_tools`` wrote into *scripts_dir*.
        manifest: ``scripts/<name>`` entries from ``_manifest_workflow_tool_scripts``.

    Returns:
        One entry per (load, side) gap, sorted; empty when every load ships.
    """
    gaps: set[tuple[str, str, str]] = set()
    for tool, module in _sibling_loads(scripts_dir, deployed):
        if f"{module}.py" not in deployed:
            gaps.add((tool, module, _DEPLOY_SIDE))
        if f"scripts/{module}.py" not in manifest:
            gaps.add((tool, module, _MANIFEST_SIDE))
    return sorted(gaps)


@pytest.fixture(scope="module")
def deployed_workflow_tools(tmp_path_factory):
    """Run the real build_workflow_tools into a fresh temp target.

    Returns:
        ``(scripts_dir, deployed_names)`` for the temp target's ``scripts/``.
    """
    target = tmp_path_factory.mktemp("workflow_tools_target")
    build_phases.build_workflow_tools(target, {}, dry_run=False, force=True)
    scripts_dir = target / "scripts"
    return scripts_dir, {p.name for p in scripts_dir.iterdir() if p.is_file()}


def test_every_sibling_module_a_deployed_tool_loads_is_deployed_and_in_the_manifest(deployed_workflow_tools):
    # covers: KM-KGS-100a-3-xi
    # angle: deployed
    """Every ``_load_sibling_module("X")`` literal in a deployed workflow tool
    names a module that build_workflow_tools deployed byte-identical to its
    source AND that _manifest_workflow_tool_scripts lists. All gaps are
    reported together."""
    scripts_dir, deployed = deployed_workflow_tools
    loads = _sibling_loads(scripts_dir, deployed)
    assert loads, (
        f"no _load_sibling_module literal found in any deployed tool {sorted(deployed)} -- "
        "the scan is vacuous (did the loader get renamed?)"
    )

    manifest = _manifest_workflow_tool_scripts(build_phases.PACKAGE_ROOT)
    gaps = _sibling_gaps(scripts_dir, deployed, manifest)
    assert not gaps, (
        "sibling module(s) loaded by a deployed workflow tool do not ship -- add each to "
        "WORKFLOW_TOOL_SCRIPTS in scripts/build_phases_knowledge.py:\n"
        + "\n".join(f"  {tool} loads {module!r}: missing from {side}" for tool, module, side in gaps)
    )

    source_dir = build_phases.PACKAGE_ROOT / "scripts"
    drifted = sorted(
        {module for _tool, module in loads
         if (scripts_dir / f"{module}.py").read_bytes() != (source_dir / f"{module}.py").read_bytes()}
    )
    assert not drifted, f"deployed sibling module(s) differ from their source: {drifted}"


def test_guard_names_a_sibling_module_left_out_of_the_deploy_set(tmp_path):
    # covers: KM-KGS-100a-3-xi
    # angle: failure
    """On a synthetic tool, the gap finder names a sibling missing from the
    deploy set and one missing from the manifest, each on its own side; it
    ignores a non-literal loader argument; and it reports nothing once both
    siblings ship on both sides."""
    (tmp_path / "tool.py").write_text(
        '"""Mentions _load_sibling_module(name) in prose only."""\n'
        "def _load_sibling_module(module_name):\n"
        "    return module_name\n"
        '_a = _load_sibling_module("sibling_a")\n'
        'import types; _ns = types.SimpleNamespace(_load_sibling_module=_load_sibling_module)\n'
        '_b = _ns._load_sibling_module("sibling_b")\n',
        encoding="utf-8",
    )
    for sibling in ("sibling_a.py", "sibling_b.py"):
        (tmp_path / sibling).write_text("VALUE = 1\n", encoding="utf-8")

    gaps = _sibling_gaps(
        tmp_path,
        deployed={"tool.py", "sibling_a.py"},
        manifest={"scripts/tool.py", "scripts/sibling_b.py"},
    )
    assert gaps == [
        ("tool.py", "sibling_a", _MANIFEST_SIDE),
        ("tool.py", "sibling_b", _DEPLOY_SIDE),
    ], f"unexpected gap report: {gaps}"

    shipped = _sibling_gaps(
        tmp_path,
        deployed={"tool.py", "sibling_a.py", "sibling_b.py"},
        manifest={"scripts/tool.py", "scripts/sibling_a.py", "scripts/sibling_b.py"},
    )
    assert shipped == [], f"gap reported although every sibling ships: {shipped}"
