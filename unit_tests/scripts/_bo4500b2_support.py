"""
MODULE: unit_tests/scripts/_bo4500b2_support.py
GOAL: Shared helpers for the BO-4500b-2 identity-check tests. Builds on _bo4500b1_support (real
    build_workflow_scripts install into a temporary layout; no build.py subprocess, TQ-600a).

Contract the tests pin for scripts/shared_block_identity.py::

    check_identity(layout_root: Path, package_root: Path, config: dict) -> dict

    result keys:
      passed: bool
      message: str                     human text; on failure names every offender and the location
      differences: [{route, block, first_differing_line}]   route = installed path (ends in the
                                       route file name), line 1-based in the INSTALLED file
      matched: [{block, inspected, routes}]   blocks whose inspected copies all matched
      not_inspected: [{block, reason}] declared awaiting adoption, no installed copy
      missing_blocks: [str]            source, not declared, no installed copy
      inspected_total: int
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo4500b1_support as S  # noqa: E402,F401

CONFIG: dict[str, Any] = {"workflows": {"enabled": True}, "output_root": ".leafcutter"}


def run_check(layout_root: Path, package_root: Path) -> dict[str, Any]:
    """Call the identity check after the fixture install/edits have really run.

    The fixture work before this call reaches real code; a missing module is reported as an
    assertion at the point of use, so the red is the check's result being absent, not a collection error.
    """
    import importlib.util

    spec = importlib.util.find_spec("shared_block_identity")
    assert spec is not None, "scripts/shared_block_identity.py must provide check_identity (module missing)"
    from shared_block_identity import check_identity

    return check_identity(Path(layout_root), Path(package_root), dict(CONFIG))


def private_copy(installed: Path, tmp_path: Path) -> Path:
    """Copy the installed workflows dir to a private layout root so edits never touch the original."""
    import shutil

    dest = tmp_path / "private_layout" / "workflows"
    shutil.copytree(installed, dest)
    return dest.parent


def edit_block_body(path: Path, name: str, fn) -> None:
    """Apply ``fn(bytes)->bytes`` to the bytes between the START line and the END marker of ``name``."""
    raw = path.read_bytes()
    start = f"// {name}-START\n".encode()
    a = raw.index(start) + len(start)
    b = raw.index(f"// {name}-END".encode())
    path.write_bytes(raw[:a] + fn(raw[a:b]) + raw[b:])


def named(result: dict[str, Any], route_file: str) -> bool:
    """True when ``route_file`` appears in a difference entry or in the failure message."""
    in_diffs = any(route_file in d["route"] for d in result["differences"])
    return in_diffs or route_file in result["message"]


def diff_for(result: dict[str, Any], route_file: str) -> dict[str, Any]:
    """The single difference entry whose route ends with ``route_file``."""
    hits = [d for d in result["differences"] if d["route"].endswith(route_file)]
    assert len(hits) == 1, (route_file, result["differences"])
    return hits[0]
