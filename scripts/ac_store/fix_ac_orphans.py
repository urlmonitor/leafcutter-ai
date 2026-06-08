#!/usr/bin/env python3
"""
MODULE: fix_ac_orphans
GOAL: Auto-repair all orphaned parent-child links in the AC store by appending
    missing child IDs to each parent's covered_by list.
BUSINESS CONTEXT: The AC store has 583+ pre-existing orphans — children whose
    parent's covered_by field doesn't list them. The check-ac-parent-covered-by
    pre-commit hook now blocks all commits that touch AC files until these are
    fixed. This script performs the bulk repair in one pass.
ARCHITECTURE: Reuses scan_ac_orphans.find_orphaned_children() for detection,
    then performs in-place YAML edits on parent files. Uses yaml.safe_load +
    yaml.dump for round-trip editing (preserves structure, may reformat).
    Alternatively falls back to regex-based covered_by patching when PyYAML
    would mangle the file.

DECISION HISTORY:
  - 2026-06-08 [python-coder/ACS-100i-2-i]: Created fix_ac_orphans.py.
    Bulk repair script for store-wide covered_by orphans. Reuses
    scan_ac_orphans detection logic, patches parent YAML in-place.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

from scan_ac_orphans import (
    _build_id_index,
    _find_worktree_root,
    _load_ac,
    find_orphaned_children,
    _get_derive_parent_id,
    _DEFAULT_AC_ROOT,
)


def _patch_covered_by(file_path: Path, children_to_add: list[str]) -> bool:
    """Patch a parent YAML file's covered_by field to include missing children.

    Uses regex-based line editing to preserve file formatting as much as possible.
    Handles three cases:
      1. covered_by: []  → covered_by: [existing..., new...]
      2. covered_by:\\n  - item  → append new items
      3. covered_by field missing → append it at the end

    Args:
        file_path: Path to the parent YAML file.
        children_to_add: List of child AC IDs to append.

    Returns:
        True if the file was modified, False if no changes were needed.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"  WARNING: cannot read {file_path}: {exc}", file=sys.stderr)
        return False

    original = content
    lines = content.splitlines(keepends=True)

    # Find the covered_by line
    covered_by_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("covered_by:"):
            covered_by_idx = i
            break

    if covered_by_idx is None:
        # No covered_by field — append one at the end
        new_lines = ["covered_by:\n"]
        for child_id in sorted(children_to_add):
            new_lines.append(f"  - {child_id}\n")
        content = content.rstrip("\n") + "\n" + "".join(new_lines)
    else:
        line = lines[covered_by_idx]

        # Case 1: inline empty list — covered_by: []
        if re.search(r"covered_by:\s*\[\s*\]", line):
            items = sorted(children_to_add)
            if len(items) <= 3:
                replacement = f"covered_by: [{', '.join(items)}]\n"
            else:
                replacement = "covered_by:\n" + "".join(f"  - {c}\n" for c in items)
            lines[covered_by_idx] = replacement
            content = "".join(lines)

        # Case 2: inline list with items — covered_by: [A, B, C]
        elif re.search(r"covered_by:\s*\[.+\]", line):
            match = re.search(r"covered_by:\s*\[(.+)\]", line)
            if match:
                existing = [x.strip() for x in match.group(1).split(",") if x.strip()]
                combined = existing + sorted(set(children_to_add) - set(existing))
                if len(combined) <= 5:
                    replacement = f"covered_by: [{', '.join(combined)}]\n"
                else:
                    replacement = "covered_by:\n" + "".join(f"  - {c}\n" for c in combined)
                lines[covered_by_idx] = replacement
                content = "".join(lines)

        # Case 3: block list — covered_by:\n  - item\n  - item
        elif line.strip() == "covered_by:":
            # Find the end of the existing block list
            insert_idx = covered_by_idx + 1
            while insert_idx < len(lines) and re.match(r"^\s+-\s", lines[insert_idx]):
                insert_idx += 1
            # Insert new items before the next non-list-item line
            new_items = [f"  - {child_id}\n" for child_id in sorted(children_to_add)]
            for j, item in enumerate(new_items):
                lines.insert(insert_idx + j, item)
            content = "".join(lines)

        # Case 4: block list with YAML flow — covered_by:\n  - item
        else:
            # Fallback: load with PyYAML, modify, dump
            try:
                data = yaml.safe_load(original)
            except yaml.YAMLError:
                print(f"  WARNING: cannot parse {file_path} for patching", file=sys.stderr)
                return False

            if not isinstance(data, dict):
                return False

            existing = data.get("covered_by") or []
            if not isinstance(existing, list):
                existing = []
            data["covered_by"] = existing + sorted(set(children_to_add) - set(existing))
            content = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)

    if content == original:
        return False

    try:
        file_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        print(f"  WARNING: cannot write {file_path}: {exc}", file=sys.stderr)
        return False

    return True


def main(argv: list[str] | None = None) -> int:
    """Fix all orphaned parent-child links in the AC store.

    Args:
        argv: Command-line arguments.

    Returns:
        0 on success (all orphans fixed or none found), 1 on partial failure, 2 on fatal error.
    """
    parser = argparse.ArgumentParser(
        description="Fix orphaned AC parent-child links by updating parent covered_by fields.",
    )
    parser.add_argument(
        "--ac-root",
        default=None,
        help=f"AC store root (default: {_DEFAULT_AC_ROOT} relative to worktree root)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be fixed without writing any files.",
    )
    args = parser.parse_args(argv)

    # Resolve AC root
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
        print(f"ERROR: AC root not found: {ac_root}", file=sys.stderr)
        return 2

    # Load derive_parent_id
    try:
        derive_parent_id = _get_derive_parent_id()
    except ImportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    # Load all YAML files
    yaml_paths = sorted(ac_root.rglob("*.yaml"))
    all_records = []
    for path in yaml_paths:
        record = _load_ac(path)
        if record is not None:
            all_records.append(record)

    print(f"Loaded {len(all_records)} AC files from {ac_root}")

    # Build index and find orphans
    id_index = _build_id_index(all_records)
    orphans = find_orphaned_children(id_index, derive_parent_id)

    if not orphans:
        print("No orphans found. Store is clean.")
        return 0

    total_orphans = sum(len(v) for v in orphans.values())
    print(f"Found {total_orphans} orphans across {len(orphans)} parents.")
    print()

    if args.dry_run:
        for parent_id in sorted(orphans):
            entries = orphans[parent_id]
            parent_file = entries[0]["parent_file"]
            children = sorted(e["child_id"] for e in entries)
            print(f"  {parent_id} ({parent_file})")
            print(f"    Would add: {', '.join(children)}")
        print(f"\nDry run complete. {total_orphans} orphans would be fixed.")
        return 0

    # Fix orphans
    fixed = 0
    failed = 0

    for parent_id in sorted(orphans):
        entries = orphans[parent_id]
        parent_file = Path(entries[0]["parent_file"])
        children_to_add = sorted(e["child_id"] for e in entries)

        success = _patch_covered_by(parent_file, children_to_add)
        if success:
            fixed += len(children_to_add)
            print(f"  FIXED {parent_id}: added {', '.join(children_to_add)}")
        else:
            failed += len(children_to_add)
            print(f"  FAILED {parent_id}: could not patch {parent_file}")

    print()
    print(f"Done. Fixed: {fixed}, Failed: {failed}, Total: {total_orphans}")

    if failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
