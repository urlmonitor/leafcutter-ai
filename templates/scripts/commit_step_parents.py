#!/usr/bin/env python3
"""
MODULE: commit_step_parents
GOAL: Work out the structural parent records of the AC records a caller names to
    the shared commit step, so an edited parent is committed with its children
    (BO-4500a-1-ii).
BUSINESS CONTEXT: Leaving the edited parent unstaged recreated KI-BO-20260928 as an
    apparent success. Split out of commit_changes.py so the step stays under the
    file-size limit; behaviour is unchanged by the split.
ARCHITECTURE: Stdlib only. Parent ids come from the canonical
    scripts/ac_store/ac_parent_id.py (never a private copy); when that module is
    not deployed beside this file, naming an AC record is refused (fail closed).

DECISION HISTORY:
  - 2026-10-16 [BO-4500]: Created by moving _load_derive_parent_id, _record_id,
    _find_parent_file and parent_candidates out of commit_changes.py verbatim.
"""

from __future__ import annotations

import importlib.util
import os
import re
from collections.abc import Callable
from pathlib import Path

from commit_step_base import StepRefusal

_AC_STORE_DEFAULT = "docs/acceptance-criteria"
_AC_STORE_ENV = "LEAFCUTTER_AC_STORE_ROOT"


def _load_derive_parent_id() -> Callable[[str], str | None] | None:
    """Load the canonical derive_parent_id; None when the module is not deployed."""
    here = Path(__file__).resolve().parent
    # Deployed: scripts/ac_store beside this file. Source tree: <repo>/scripts/ac_store.
    for candidate in (
        here / "ac_store" / "ac_parent_id.py",
        here.parent.parent / "scripts" / "ac_store" / "ac_parent_id.py",
    ):
        if not candidate.is_file():
            continue
        spec = importlib.util.spec_from_file_location("ac_parent_id", str(candidate))
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.derive_parent_id
    return None


def _record_id(path: Path) -> str:
    """Read an AC record's id (first top-level id: line); fall back to the file stem."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return path.stem
    match = re.search(r"^id:\s*['\"]?([^\s'\"#]+)", text, re.MULTILINE)
    return match.group(1) if match else path.stem


def _find_parent_file(child: Path, parent_id: str, store: Path) -> Path | None:
    """Locate the parent record: same folder first, then anywhere in the AC store."""
    sibling = child.parent / f"{parent_id}.yaml"
    if sibling.is_file():
        return sibling
    return next(iter(sorted(store.rglob(f"{parent_id}.yaml"))), None) if store.is_dir() else None


def parent_candidates(named: list[str], root: Path) -> list[str]:
    """Return repo-relative structural parents (one hop) of the named AC records."""
    store_rel = os.environ.get(_AC_STORE_ENV, _AC_STORE_DEFAULT).strip("/")
    records = [rel for rel in named if rel.endswith(".yaml") and rel.startswith(store_rel + "/")]
    if not records:
        return []
    derive = _load_derive_parent_id()
    if derive is None:
        # Fail closed: AC records are being committed but their parents cannot be
        # worked out, so silently committing without them would recreate
        # KI-BO-20260928 (the edited parent left unstaged) as an apparent success.
        msg = (
            "AC records were named but the parent resolver (ac_store/ac_parent_id.py) "
            "is not deployed beside this script, so their edited parents cannot be "
            f"included: {', '.join(records)}"
        )
        raise StepRefusal("step_parent_resolver_unavailable", msg)
    found: list[str] = []
    for rel in named:
        if not rel.endswith(".yaml") or not rel.startswith(store_rel + "/"):
            continue
        parent_id = derive(_record_id(root / rel))
        parent = _find_parent_file(root / rel, parent_id, root / store_rel) if parent_id else None
        if parent is not None:
            parent_rel = parent.relative_to(root).as_posix()
            if parent_rel not in named and parent_rel not in found:
                found.append(parent_rel)
    return found
