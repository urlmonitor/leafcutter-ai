"""
MODULE: scripts/build_orchestration/_wvw_list.py
GOAL: The owed names and their in-scope files: the one reading shared by the writer's
    ``list`` step, its ``write`` step and (through ``_wvr_scope``) the runner.
BUSINESS CONTEXT: TQ-500g-1-ix, -x. The set of wrong versions owed must be exactly the set
    the runner later holds the tests to, so neither the route nor the preparer's reply
    ever defines it: it is derived from the AC test entries here, through the runner's
    own declared-scope reader. A name whose entries declare no in-scope file takes the
    non-test files the work changed relative to ``--base-ref`` (HEAD when empty).
ARCHITECTURE: Thin wrapper over ``_wvr_scope.resolve_scope`` and ``_wvr_scope.owed_names``
    (never a second parser of the AC store). Reads the AC store and the test files only. The
    ``list`` step prints ``{owed: [{name, files, scope}], to_prepare, decisions, error}`` with
    scope ``"declared"`` or ``"derived"``. Without a work key ``to_prepare`` equals ``owed``,
    ``decisions`` is ``[]`` and nothing is written; with one (TQ-500g-1-xi, ``keyed_decisions``)
    the owed names are planned against the work's pins (``_wvp_plan``) and the plan record
    ``<git-dir>/leafcutter/work/<work-key>/plan.json`` is the only file written;
    a to-run-later extra (TQ-500g-2-ii, read by ``_wvr_extras`` inside ``resolve_scope``) is an item with
    scope ``"derived"`` plus ``blocking: false`` and ``origin: "to_run_later"``.
    The changed files are worked out only when a name needs them, with one ``git diff``.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import _wvr_gate as gate_mod
from _wvp_plan import Decision, make_plan, write_record
from _wvp_store import PinError, git_dir, plain_segment
from _wvr_scope import ChangesError, DiffCache, OwedName, ScopedTest, changed_non_test_files, owed_names, resolve_scope

_LOG = logging.getLogger("wrong_version_writer")


@dataclass
class Derived:
    """The owed names of one preparation, the worktree root and why it failed (if it did)."""

    owed: list[OwedName] = field(default_factory=list)
    root: Path | None = None
    test_root_rel: str | None = None
    error: str = ""
    tests: list[ScopedTest] = field(default_factory=list)  # the in-scope tests: their own entries say who holds a name


def derive_owed(ac_ids: list[str], test_root: Path, ac_root: Path, base_ref: str = "HEAD") -> Derived:
    """Derive the owed names and their in-scope files for *ac_ids*.

    Args:
        ac_ids: The requirement ids whose covering tests are held to wrong versions.
        test_root: The working-tree root (also scanned for covering tests).
        ac_root: Root of the AC store.
        base_ref: The ref the work began from (empty means HEAD); read only when a name needs it.

    Returns:
        A :class:`Derived`; ``error`` is set when the AC store or test root cannot be read, or
        when a name has no declared scope and the changed files cannot be worked out.
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
    ref = base_ref or "HEAD"
    ac_rel = os.path.relpath(os.path.realpath(ac_root), os.path.realpath(root)).replace("\\", "/")
    diff = DiffCache(root, ref)
    try:
        owed = owed_names(scope.tests, test_root_rel,
                          lambda: changed_non_test_files(root, diff, test_root_rel, None if ac_rel.startswith("..") else ac_rel))
    except ChangesError as exc:
        return Derived(root=root, test_root_rel=test_root_rel, error=str(exc))
    derived = sum(o.scope == "derived" for o in owed)
    _LOG.info("base ref %s: %d names declared, %d derived", ref, len(owed) - derived, derived)
    return Derived(owed, root, test_root_rel, tests=scope.tests)


def list_payload(derived: Derived, decisions: list[Decision] | None = None) -> dict:
    """Return the ``list`` step's JSON object (fixed key order).

    Args:
        derived: The owed names (or the error).
        decisions: One ``_wvp_plan.Decision`` per owed name, or ``None`` without a work key: then
            every owed name is to be prepared and no decision is listed.

    Returns:
        ``{owed, to_prepare, decisions, error}``; ``to_prepare`` holds the owed items needing
        preparation, each byte-identical to its owed item, in owed order.
    """
    if derived.error:
        return {"owed": [], "to_prepare": [], "decisions": [], "error": derived.error}
    owed = [_item(o) for o in derived.owed]
    if decisions is None:
        return {"owed": owed, "to_prepare": list(owed), "decisions": [], "error": None}
    prepare = [item for item, d in zip(owed, decisions, strict=True) if d.to_prepare]
    return {"owed": owed, "to_prepare": prepare, "decisions": [d.shown() for d in decisions], "error": None}


def _item(owed: OwedName) -> dict:
    """One owed item; a to-run-later extra carries the two additive keys ``blocking`` and ``origin``."""
    item = {"name": owed.name, "files": list(owed.files), "scope": owed.scope}
    return {**item, "blocking": False, "origin": "to_run_later"} if owed.extra else item


def keyed_decisions(derived: Derived, test_root: Path, work_key: str) -> list[Decision]:
    """Plan every owed name for *work_key* from the work's pins and save the plan record.

    Args:
        derived: A successful :class:`Derived` (``root`` is set).
        test_root: The working-tree root the step was given.
        work_key: The work key (one plain path segment).

    Returns:
        One decision per owed name, in owed order.

    Raises:
        PinError: When the key is not a plain segment, or the pins or the record cannot be read or written.
    """
    if not plain_segment(work_key):
        msg = f"the work key {work_key!r} is not one plain path segment"
        raise PinError(msg)
    git_directory = git_dir(test_root)
    decisions, fp = make_plan(derived.owed, git_directory, work_key, derived.root, derived.test_root_rel, derived.tests)
    write_record(git_directory / "leafcutter" / "work" / work_key, work_key, decisions, fp)
    return decisions


# DECISION HISTORY
# ================================================================================
# - 2026-10-25 15:50 [python-coder]: Pins keep applied replacements per work key and are replayed on the current code; a pin-write failure fails the gate. (#EPIC-OnceANamedWrongVersionIsPreparedAnd/02) (ADR-079)
# - 2026-10-25 22:00 [python-coder]: Derived carries the in-scope tests so the plan's effect check knows which tests name a wrong version. (#EPIC-OnceANamedWrongVersionIsPreparedAnd/05) (ADR-079)
