"""
MODULE: _shared_layout_seed
GOAL: Seed the workspace maker's own ``.leafcutter/`` state into the shared
    layout's build target, record after the ONE real build whether each seeded
    file survived byte-identical, then remove the seed so the layout is pristine.
BUSINESS CONTEXT: BO-4300a-1 IT9 (ADR-018 A1.4, EPIC-WorkspaceMakerHardening
    N3): the real install build must leave the maker's ``.leafcutter/
    workspace.json`` and ``.leafcutter/rescue/`` intact. A seeded
    ``workspace.json`` left in the shared layout would make ``workspace_root``
    treat the layout as being inside a workspace for every consumer, so the
    proof is taken from the one build and the seed is then removed.
ARCHITECTURE: Used only by ``_shared_layout_producer._produce``: ``seed_maker_state``
    before the build, ``record_and_clear_seed`` after it (before the layout is
    published, so the integrity record is taken on the pristine tree). The result
    is a sidecar JSON in the run-scoped directory, OUTSIDE the published layout and
    so outside anything a consumer copies or digests. ``read_seeded_survival``
    reads it. No build is spawned here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

__all__ = [
    "SEEDED_STATE_FILES",
    "SEEDED_SURVIVAL_FILENAME",
    "read_seeded_survival",
    "record_and_clear_seed",
    "seed_maker_state",
]

# Keyed by POSIX path relative to the layout root.
SEEDED_STATE_FILES: dict[str, bytes] = {
    ".leafcutter/workspace.json": b'{"schema": 1, "kind": "workspace-marker", "seeded_by": "shared-layout-producer"}\n',
    ".leafcutter/rescue/manifest.json": b'{"schema": 1, "rescued": ["notes/rescued-sentinel.txt"]}\n',
    ".leafcutter/rescue/notes/rescued-sentinel.txt": b"rescued bytes the real build must not touch\n",
}

# Lives in the run-scoped directory beside ``published/``, never inside it.
SEEDED_SURVIVAL_FILENAME = "seeded-survival.json"


def seed_maker_state(target_dir: Path) -> None:
    """Write SEEDED_STATE_FILES into *target_dir* before the real build runs."""
    for rel, content in SEEDED_STATE_FILES.items():
        dest = target_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)


def record_and_clear_seed(target_dir: Path, run_base: Path) -> None:
    """Record each seeded file's survival to the sidecar, then delete the seed.

    Writes ``{rel: {"present": bool, "sha256_matches": bool}}`` to
    ``run_base / SEEDED_SURVIVAL_FILENAME``, removes every seeded file from
    *target_dir*, and prunes the rescue folders that are left empty.
    """
    result: dict[str, dict[str, bool]] = {}
    for rel, content in SEEDED_STATE_FILES.items():
        path = target_dir / rel
        present = path.is_file()
        matches = present and hashlib.sha256(path.read_bytes()).hexdigest() == hashlib.sha256(content).hexdigest()
        result[rel] = {"present": present, "sha256_matches": matches}
    (run_base / SEEDED_SURVIVAL_FILENAME).write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    for rel in SEEDED_STATE_FILES:
        (target_dir / rel).unlink(missing_ok=True)
    for rel in sorted(SEEDED_STATE_FILES, key=len, reverse=True):
        for parent in (target_dir / rel).parents:
            if parent == target_dir / ".leafcutter" or parent == target_dir:
                break
            try:
                parent.rmdir()
            except OSError:
                break  # not empty: the build owns something here, leave it


def read_seeded_survival(run_base: Path) -> dict[str, dict[str, bool]]:
    """Return the sidecar written by :func:`record_and_clear_seed`.

    Raises:
        FileNotFoundError: no layout was produced in this run.
    """
    return json.loads((run_base / SEEDED_SURVIVAL_FILENAME).read_text(encoding="utf-8"))
