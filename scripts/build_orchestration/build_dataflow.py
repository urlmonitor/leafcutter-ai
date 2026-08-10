#!/usr/bin/env python3
"""
build_dataflow.py — Export the build backlog as a JSON dataflow (BO-2400f-6).

Pulls every acceptance criterion that still needs building out of the AC YAML
store and emits a machine-readable dataflow document: one node per not-done
leaf (L2/L3) AC, each carrying its dependency edges and a ``ready`` flag, plus a
dependency-ordered ``build_order`` and roll-up totals.

Two scopes:

* **store** (default): every not-done leaf in the whole store — the full backlog.
* **connected** (``--ac <id>``): only the connected build set of one AC (its
  subtree ∪ its unmet-dependency closure), readiness-agnostic. This is the exact
  set ``/fast-lane-build <id>`` would build.

The export is deterministic — the same store state yields byte-identical JSON —
so the artifact can be committed and regenerated with a clean diff.

Usage:
    python build_dataflow.py --ac-root docs/acceptance-criteria \\
        [--ac BO-2400] [--out docs/build-dataflow.json]

Exit codes:
    0  Success (an empty backlog is a valid, clean result).
    1  A ``--ac`` id was supplied that does not exist in the store.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path wiring — reuse the resolver and scan helpers without a package install.
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_AC_STORE_DIR = _SCRIPTS_DIR / "ac_store"
if str(_AC_STORE_DIR) not in sys.path:
    sys.path.insert(0, str(_AC_STORE_DIR))

from fast_lane import (  # noqa: E402
    _topo_order_build_set,
    resolve_connected_build_set,
)
from scan_ac_store import (  # noqa: E402
    _build_id_index,
    _drain_cycles,
    _is_dep_done,
    _is_leaf,
    _load_ac,
    _walk_ac_yamls,
)

SCHEMA_VERSION = 1
_DEFAULT_OUT_NAME = "build-dataflow.json"


# ---------------------------------------------------------------------------
# Store loading
# ---------------------------------------------------------------------------


def _load_store(ac_root: Path) -> dict[str, dict]:
    """Load the AC store into an acyclic id → record index.

    Args:
        ac_root: Root directory of the AC YAML store.

    Returns:
        Mapping from AC id to its record (dependency cycles drained).
    """
    records: list[dict] = []
    if ac_root.exists():
        for path in _walk_ac_yamls(ac_root):
            record = _load_ac(path)
            if record is not None:
                records.append(record)
    id_index = _build_id_index(records)
    _drain_cycles(id_index, records)
    return id_index


def _build_parent_map(id_index: dict[str, dict]) -> dict[str, str]:
    """Return a child-id → parent-id map derived from ``covered_by`` edges.

    Args:
        id_index: Full id-to-record mapping.

    Returns:
        Mapping from each covered child id to the id of the AC that covers it.
        A child covered by more than one parent keeps the alphabetically-first
        parent (deterministic).
    """
    parent_of: dict[str, str] = {}
    for parent_id in sorted(id_index):
        for child_id in id_index[parent_id].get("covered_by") or []:
            # First (alphabetical) parent wins — deterministic and stable.
            parent_of.setdefault(child_id, parent_id)
    return parent_of


# ---------------------------------------------------------------------------
# Node assembly
# ---------------------------------------------------------------------------


def _relative_path(raw_path: str, path_base: Path) -> str:
    """Return *raw_path* relative to *path_base* when possible (portable artifact).

    Args:
        raw_path: The absolute ``_path`` recorded on the AC.
        path_base: Base directory to relativise against (repo root).

    Returns:
        The path relative to *path_base*, or *raw_path* unchanged when it is not
        under *path_base* (or is empty).
    """
    if not raw_path:
        return ""
    try:
        return str(Path(raw_path).resolve().relative_to(path_base))
    except ValueError:
        return raw_path


def _node_for(
    ac_id: str,
    id_index: dict[str, dict],
    parent_of: dict[str, str],
    path_base: Path,
) -> dict:
    """Build the dataflow node dict for a single AC id.

    Args:
        ac_id: The AC id to describe.
        id_index: Full id-to-record mapping.
        parent_of: Child-to-parent map from :func:`_build_parent_map`.
        path_base: Repo root to make the ``path`` field relative to (portable).

    Returns:
        A node dict with dependency edges, an ``unmet_deps`` list, and a
        ``ready`` flag (True when no dependency is outstanding).
    """
    rec = id_index.get(ac_id) or {}
    depends_on: list[str] = list(rec.get("depends_on") or [])
    unmet_deps = [dep for dep in depends_on if not _is_dep_done(dep, id_index)]
    return {
        "id": ac_id,
        "title": rec.get("title", ""),
        "component": rec.get("component", ""),
        "level": rec.get("level", ""),
        "work_status": rec.get("work_status", ""),
        "readiness": rec.get("readiness", ""),
        "test_required": rec.get("test_required", True),
        "parent": parent_of.get(ac_id),
        "depends_on": depends_on,
        "unmet_deps": unmet_deps,
        "ready": not unmet_deps,
        "path": _relative_path(rec.get("_path", ""), path_base),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_dataflow(*, ac_root: Path, ac: str | None = None) -> dict:
    """Return the build-backlog dataflow document.

    Args:
        ac_root: Root directory of the AC YAML store.
        ac: When given, restrict the export to that AC's connected build set
            (subtree ∪ unmet-deps closure, readiness-agnostic). When ``None``,
            export every not-done leaf in the whole store.

    Returns:
        The dataflow dict (see the module docstring for the shape).

    Raises:
        ValueError: When *ac* is supplied but does not exist in the store
            (message names the missing id — never a silent empty artifact).
    """
    id_index = _load_store(ac_root)
    parent_of = _build_parent_map(id_index)
    # Repo root = parent of the AC store's parent (docs/acceptance-criteria -> repo).
    path_base = ac_root.resolve().parent.parent

    if ac is not None:
        # Connected scope. resolve_connected_build_set raises ValueError naming
        # a missing id and returns the set already in dependency order.
        build_order = resolve_connected_build_set(ac, ac_root=ac_root)
        node_ids = set(build_order)
        mode = "connected"
    else:
        # Store scope: every not-done leaf, dependency-ordered.
        node_ids = {
            ac_id
            for ac_id, rec in id_index.items()
            if _is_leaf(rec) and rec.get("work_status", "") != "done"
        }
        build_order = _topo_order_build_set(node_ids, id_index)
        mode = "store"

    nodes = {
        ac_id: _node_for(ac_id, id_index, parent_of, path_base)
        for ac_id in sorted(node_ids)
    }
    ready_count = sum(1 for node in nodes.values() if node["ready"])

    return {
        "schema_version": SCHEMA_VERSION,
        "scope": {"mode": mode, "ac": ac, "ac_root": str(ac_root)},
        "totals": {
            "todo_leaves": len(nodes),
            "ready": ready_count,
            "blocked": len(nodes) - ready_count,
        },
        "build_order": build_order,
        "nodes": nodes,
    }


def _serialise(doc: dict) -> str:
    """Serialise *doc* to deterministic, clean-diff JSON (trailing newline).

    Args:
        doc: The dataflow document.

    Returns:
        A JSON string with sorted keys, two-space indent, and a trailing newline.
    """
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the build_dataflow CLI."""
    parser = argparse.ArgumentParser(
        description=(
            "Export the build backlog as a JSON dataflow of the acceptance "
            "criteria that still need building (BO-2400f-6)."
        ),
    )
    parser.add_argument(
        "--ac-root", required=True, metavar="DIR",
        help="Root of the AC YAML store (e.g. docs/acceptance-criteria).",
    )
    parser.add_argument(
        "--ac", metavar="ID", default=None,
        help="Restrict to this AC's connected build set (default: whole store).",
    )
    parser.add_argument(
        "--out", metavar="FILE", default=None,
        help="Output path (default: <ac-root>/../build-dataflow.json).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point — write the dataflow JSON artifact.

    Args:
        argv: Argument list. Defaults to ``sys.argv[1:]`` when ``None``.

    Returns:
        0 on success; 1 when a supplied ``--ac`` id is not in the store.
    """
    args = _build_parser().parse_args(argv)
    ac_root = Path(args.ac_root)
    out_path = Path(args.out) if args.out else ac_root.parent / _DEFAULT_OUT_NAME

    try:
        doc = build_dataflow(ac_root=ac_root, ac=args.ac)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_serialise(doc), encoding="utf-8")

    totals = doc["totals"]
    print(
        f"{out_path} — {totals['todo_leaves']} leaves to build "
        f"({totals['ready']} ready, {totals['blocked']} blocked)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
