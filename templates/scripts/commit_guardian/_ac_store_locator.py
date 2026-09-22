"""
MODULE: _ac_store_locator
GOAL: Resolve the ac_store/ directory check_done_proof.py imports done_proof
    from, and put it on sys.path, across every layout this repository's
    commit-guardian hook runs in.
BUSINESS CONTEXT: check_done_proof.py needs `done_proof` (scripts/ac_store/)
    to be importable regardless of where it is invoked from: the deployed
    layout, a self-hosted dev workspace build, or the raw templates/ source
    tree (where templates/scripts/ac_store/ is a deploy-source stub holding
    no .py files at all, and the real done_proof.py lives at the true
    project root instead). This module is the single place that resolution
    logic lives.
ARCHITECTURE: A sibling module inside templates/scripts/commit_guardian/ --
    build_commit_guardian (scripts/build_phases_lifecycle.py) copies every
    file in that directory verbatim (via `cg_dir.rglob("*")`) to
    <target_root>/scripts/commit_guardian/, so this file needs no entry of
    its own in any hardcoded deploy_map; it deploys purely by being a sibling
    of check_done_proof.py, the same way `_resolve_root.py` already does.
    Relocated out of check_done_proof.py (BP-100n-4-ii-ii) to buy back
    file-size-ratchet headroom after the BO-2500a-1-ii conjunction carve-out
    pushed that file over its baseline -- pure move, no behaviour change.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def resolve_ac_store_dir() -> Path | None:
    """Return the ac_store directory to import ``done_proof`` from, if any.

    Tries two candidates, in priority order:

    1. The immediate sibling ``ac_store/`` next to this file's own directory
       (``_HERE.parent / "ac_store"``) — correct for the deployed layout and
       a self-hosted dev workspace build, where commit_guardian/ and
       ac_store/ are TRUE siblings.
    2. A project-root walk from THIS FILE'S OWN location (never
       ``Path.cwd()``, which inside a pre-commit hook subprocess — or a unit
       test that ``git init``'s a scratch directory as its working
       directory, such as the BO-2500a-1-ii reachability CLI tests — names
       an unrelated repository) looking for ``.git`` or ``CLAUDE.md``, then
       ``<project_root>/scripts/ac_store``. This is the shape of the raw
       ``templates/scripts/commit_guardian/`` source tree, where candidate 1
       resolves to an empty deploy-source stub and the real ``done_proof.py``
       lives at the true project root instead — not a sibling of this file
       at all.

    Returns:
        The first candidate directory that actually contains
        ``done_proof.py``, or ``None`` when neither does.
    """
    candidates = [_HERE.parent / "ac_store"]
    for ancestor in [_HERE, *_HERE.parents]:
        if (ancestor / ".git").exists() or (ancestor / "CLAUDE.md").exists():
            candidates.append(ancestor / "scripts" / "ac_store")
            break
    for candidate in candidates:
        if (candidate / "done_proof.py").is_file():
            return candidate
    return None


def ensure_ac_store_on_syspath() -> None:
    """Insert the resolved ac_store directory onto ``sys.path``, if found.

    A no-op when :func:`resolve_ac_store_dir` finds neither candidate — the
    caller's subsequent ``from done_proof import ...`` then raises normally
    and its existing fallback path takes over.
    """
    ac_store = resolve_ac_store_dir()
    if ac_store is not None and str(ac_store) not in sys.path:
        sys.path.insert(0, str(ac_store))
