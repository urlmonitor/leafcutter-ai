"""
MODULE: scripts/build_orchestration/_wvw_list.py
GOAL: The owed names and their in-scope files: the one reading shared by the writer's
    ``list`` step, its ``write`` step and (through ``_wvr_scope``) the runner.
BUSINESS CONTEXT: TQ-500g-1-ix. The set of wrong versions owed must be exactly the set
    the runner later holds the tests to, so neither the route nor the preparer's reply
    ever defines it: it is derived from the AC test entries here, through the runner's
    own declared-scope reader.
ARCHITECTURE: Thin wrapper over ``_wvr_scope.resolve_scope`` and ``_wvr_scope.owed_names``
    (never a second parser of the AC store). Reads the AC store and the test files only;
    writes nothing. The ``list`` step prints ``{owed: [{name, files}], error}``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import _wvr_gate as gate_mod
from _wvr_scope import OwedName, owed_names, resolve_scope


@dataclass
class Derived:
    """The owed names of one preparation, the worktree root and why it failed (if it did)."""

    owed: list[OwedName] = field(default_factory=list)
    root: Path | None = None
    test_root_rel: str | None = None
    error: str = ""


def derive_owed(ac_ids: list[str], test_root: Path, ac_root: Path) -> Derived:
    """Derive the owed names and their in-scope files for *ac_ids*.

    Args:
        ac_ids: The requirement ids whose covering tests are held to wrong versions.
        test_root: The working-tree root (also scanned for covering tests).
        ac_root: Root of the AC store.

    Returns:
        A :class:`Derived`; ``error`` is set when the AC store or test root cannot be read.
    """
    if not test_root.is_dir():
        return Derived(error=f"the test root cannot be read: {test_root} is not a directory")
    try:
        root = Path(gate_mod.git_text(test_root, "rev-parse", "--show-toplevel"))
    except gate_mod.GateError as exc:
        return Derived(error=f"the test root is not inside a git working tree: {exc}")
    rel = os.path.relpath(os.path.realpath(test_root), os.path.realpath(root)).replace("\\", "/")
    test_root_rel = None if rel in {".", ""} or rel.startswith("..") else rel
    if not ac_ids:
        return Derived([], root, test_root_rel)
    scope = resolve_scope(ac_ids, test_root, ac_root)
    if scope.problem:
        return Derived(root=root, test_root_rel=test_root_rel, error=scope.problem)
    return Derived(owed_names(scope.tests, test_root_rel), root, test_root_rel)


def list_payload(derived: Derived) -> dict:
    """Return the ``list`` step's JSON object (fixed key order)."""
    owed = [] if derived.error else [{"name": o.name, "files": list(o.files)} for o in derived.owed]
    return {"owed": owed, "error": derived.error or None}
