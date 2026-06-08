#!/usr/bin/env python3
"""
MODULE: scan_ac_orphans
GOAL: Store-wide integrity scan that detects child AC YAML files whose parent's
    covered_by field does not include them, then reports the orphaned children
    grouped by parent for readability.
BUSINESS CONTEXT: The AC store enforces a bidirectional parent-child link: when
    a child AC exists on disk, the parent's covered_by field must list that child.
    Pre-commit hooks (check_ac_parent_covered_by.py) enforce this at commit time,
    but they only catch freshly staged files. This scan catches existing orphans
    that pre-date the hook or slipped through during manual edits. Running it as
    part of a CI gate or an ad-hoc operator command closes the gap. The scan
    reuses derive_parent_id() from ac_parent_id.py so the parent-derivation
    logic is never duplicated.
ARCHITECTURE: Pure-stdlib with optional PyYAML. Walks docs/acceptance-criteria/
    recursively, loads all .yaml files, builds an in-memory id→record index, then
    for every non-root AC checks whether its structural parent's covered_by list
    includes it. Reports grouped by parent. Exits 0 when no orphans are found,
    exits 1 when one or more orphans are found, exits 2 on a YAML load error.

DOC_LINKS:
  - docs/reference/ac-schema.md
  - docs/architecture/adrs/ADR-007-ac-store-schema-id-format-enforcement.md

DECISION HISTORY:
  - 2026-06-08 [python-coder/ACS-100i-4]: Created scan_ac_orphans.py.
    Implements ACS-100i-4: store-wide scan that detects and reports orphaned
    child ACs (children whose parent covered_by omits them). Reuses
    derive_parent_id() from ac_parent_id.py. Exits 0 (clean), 1 (orphans found),
    or 2 (YAML load error). Groups orphans by parent in human-readable output.
    (#EPIC-AcParentChildLinkEnforcement/04)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import]
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_AC_ROOT = "docs/acceptance-criteria"

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

AcRecord = dict[str, Any]


# ---------------------------------------------------------------------------
# Worktree root detection
# ---------------------------------------------------------------------------


def _find_worktree_root(start: Path) -> Path:
    """Walk up from *start* until a directory containing a .git file/dir is found.

    Args:
        start: Starting path for the upward search.

    Returns:
        The worktree root path.

    Raises:
        FileNotFoundError: When no .git marker is found before the filesystem root.
    """
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    raise FileNotFoundError(  # noqa: TRY003
        f"Could not locate worktree root from {start}"
    )


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


def _load_ac(path: Path) -> AcRecord | None:
    """Load and return a single AC YAML file.

    Args:
        path: Absolute path to the YAML file.

    Returns:
        Parsed AC dict on success, None on parse or I/O failure (error to stderr).
    """
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"ERROR: {path}: could not read file: {exc}", file=sys.stderr)
        return None

    if _YAML_AVAILABLE:
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            print(f"ERROR: {path}: YAML parse error: {exc}", file=sys.stderr)
            return None
        if not isinstance(data, dict):
            print(
                f"ERROR: {path}: expected a YAML mapping, got {type(data).__name__}",
                file=sys.stderr,
            )
            return None
    else:
        # Minimal fallback: parse top-level scalars only.
        data = {}
        for raw_line in content.splitlines():
            line = raw_line.rstrip()
            if not line or line.startswith("#") or line[:1] in (" ", "\t"):
                continue
            if ":" in line:
                key, _, value = line.partition(":")
                data[key.strip()] = value.strip()

    data["_path"] = str(path)
    return data


def _extract_covered_by(data: AcRecord) -> list[str]:
    """Extract the covered_by list from a parsed AC YAML dict.

    Handles PyYAML list, empty list, and the minimal-fallback string form.

    Args:
        data: Parsed YAML dict from an AC file.

    Returns:
        List of child AC ID strings. Empty list when covered_by is absent or empty.
    """
    raw = data.get("covered_by")
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if item is not None and str(item).strip()]
    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped in ("[]", ""):
            return []
        stripped = stripped.strip("[]")
        return [item.strip() for item in stripped.split(",") if item.strip()]
    return []


# ---------------------------------------------------------------------------
# derive_parent_id import (graceful fallback)
# ---------------------------------------------------------------------------


def _get_derive_parent_id():
    """Import and return the derive_parent_id function.

    Attempts three strategies:
    1. Standard package import.
    2. Locate ac_parent_id.py relative to this script's location.
    3. Locate ac_parent_id.py relative to the project root.

    Returns:
        The derive_parent_id callable.

    Raises:
        ImportError: When the module cannot be found by any strategy.
    """
    try:
        from scripts.ac_store.ac_parent_id import derive_parent_id  # type: ignore[import]
    except ImportError:
        pass
    else:
        return derive_parent_id

    import importlib.util

    def _load_from_path(module_path: Path):
        """Load derive_parent_id from an explicit path.

        Args:
            module_path: Absolute path to ac_parent_id.py.

        Returns:
            The derive_parent_id callable, or None on failure.
        """
        spec = importlib.util.spec_from_file_location("ac_parent_id", str(module_path))
        if spec is None or spec.loader is None:
            return None
        try:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
        except (ImportError, AttributeError, OSError) as exc:
            print(
                f"[scan_ac_orphans] WARNING: could not load ac_parent_id from {module_path}: {exc}",
                file=sys.stderr,
            )
            return None
        else:
            return mod.derive_parent_id

    # Strategy 2: relative to this script.
    script_dir = Path(__file__).resolve().parent
    candidate = script_dir / "ac_parent_id.py"
    if candidate.exists():
        fn = _load_from_path(candidate)
        if fn is not None:
            return fn

    # Strategy 3: project root walk.
    for ancestor in [Path.cwd(), *Path.cwd().parents]:
        if (ancestor / ".git").exists() or (ancestor / "CLAUDE.md").exists():
            candidate3 = ancestor / "scripts" / "ac_store" / "ac_parent_id.py"
            if candidate3.exists():
                fn = _load_from_path(candidate3)
                if fn is not None:
                    return fn
            break

    msg = "ac_parent_id.py not found via package import, script-relative, or project-root walk."
    raise ImportError(msg)


# ---------------------------------------------------------------------------
# Orphan detection
# ---------------------------------------------------------------------------


def _build_id_index(records: list[AcRecord]) -> dict[str, AcRecord]:
    """Build a mapping from AC id to record dict.

    Args:
        records: All successfully loaded AC records.

    Returns:
        Dict mapping id → AcRecord.
    """
    index: dict[str, AcRecord] = {}
    for rec in records:
        ac_id = rec.get("id")
        if isinstance(ac_id, str) and ac_id.strip():
            index[ac_id.strip()] = rec
    return index


def find_orphaned_children(
    id_index: dict[str, AcRecord],
    derive_parent_id,
) -> dict[str, list[dict[str, str]]]:
    """Find all child ACs whose immediate parent's covered_by omits them.

    For every AC in *id_index* that has a parent (i.e. derive_parent_id
    returns a non-None value), check whether the parent record's covered_by
    list contains the child's ID. If not, the child is an orphan.

    Args:
        id_index: Full id-to-record mapping built from the AC store.
        derive_parent_id: The derive_parent_id callable from ac_parent_id module.

    Returns:
        Dict mapping parent_id → list of orphan dicts, where each orphan dict
        contains keys: child_id, parent_id, parent_file.
        Returns an empty dict when no orphans are found.
    """
    orphans: dict[str, list[dict[str, str]]] = {}

    for child_id, child_rec in id_index.items():
        parent_id = derive_parent_id(child_id)
        if parent_id is None:
            # Root-level AC — no parent to check.
            continue

        parent_rec = id_index.get(parent_id)
        if parent_rec is None:
            # Parent not found in the store — structural issue, but not
            # the responsibility of this scan (a missing-parent scan is
            # a separate concern).
            continue

        covered_by = _extract_covered_by(parent_rec)
        if child_id not in covered_by:
            entry = {
                "child_id": child_id,
                "parent_id": parent_id,
                "parent_file": parent_rec.get("_path", "(unknown)"),
            }
            if parent_id not in orphans:
                orphans[parent_id] = []
            orphans[parent_id].append(entry)

    return orphans


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _print_orphan_report(orphans: dict[str, list[dict[str, str]]]) -> None:
    """Print the orphan report grouped by parent to stdout.

    Args:
        orphans: Dict mapping parent_id → list of orphan entries.
    """
    total = sum(len(v) for v in orphans.values())
    print(f"ORPHANED CHILDREN ({total} found, grouped by parent):")
    print()
    for parent_id in sorted(orphans):
        entries = orphans[parent_id]
        # Use the parent file path from the first entry.
        parent_file = entries[0]["parent_file"] if entries else "(unknown)"
        print(f"  Parent: {parent_id}")
        print(f"  Parent file: {parent_file}")
        print(f"  Orphaned children ({len(entries)}):")
        for entry in sorted(entries, key=lambda e: e["child_id"]):
            print(f"    - {entry['child_id']}")
        print()


def _print_clean_report(total_checked: int) -> None:
    """Print the all-clean summary to stdout.

    Args:
        total_checked: Total number of child ACs examined.
    """
    print(f"OK — {total_checked} child ACs checked, no orphans found.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Store-wide integrity scan: detect child AC YAML files whose "
            "parent's covered_by field does not include them."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ac-root",
        dest="ac_root",
        default=None,
        help=(
            f"Root directory of the AC store (default: {_DEFAULT_AC_ROOT} "
            "relative to the worktree root)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for scan_ac_orphans.py.

    Args:
        argv: Command-line arguments (default: sys.argv[1:]).

    Returns:
        Exit code: 0 when no orphans found, 1 when orphans found,
        2 on YAML load errors.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Resolve ac_root.
    if args.ac_root:
        ac_root = Path(args.ac_root)
    else:
        try:
            worktree = _find_worktree_root(Path(__file__))
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        ac_root = worktree / _DEFAULT_AC_ROOT

    if not ac_root.exists():
        print(f"ERROR: AC root directory not found: {ac_root}", file=sys.stderr)
        return 2

    # Load derive_parent_id.
    try:
        derive_parent_id = _get_derive_parent_id()
    except ImportError as exc:
        print(f"ERROR: cannot import derive_parent_id: {exc}", file=sys.stderr)
        return 2

    # Load all YAML files.
    yaml_paths = sorted(ac_root.rglob("*.yaml"))
    all_records: list[AcRecord] = []
    load_errors = 0

    for path in yaml_paths:
        record = _load_ac(path)
        if record is None:
            load_errors += 1
        else:
            all_records.append(record)

    if load_errors:
        print(
            f"ERROR: {load_errors} AC YAML file(s) could not be loaded. "
            "Fix parse errors before running the orphan scan.",
            file=sys.stderr,
        )
        return 2

    # Build id index.
    id_index = _build_id_index(all_records)

    # Find orphans.
    orphans = find_orphaned_children(id_index, derive_parent_id)

    # Count child ACs checked (those with a derivable parent in the index).
    children_checked = sum(
        1 for ac_id in id_index if derive_parent_id(ac_id) in id_index
    )

    if orphans:
        _print_orphan_report(orphans)
        return 1

    _print_clean_report(children_checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
