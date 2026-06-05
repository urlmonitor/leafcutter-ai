#!/usr/bin/env python3
"""
backfill_readiness.py — One-shot backfill script for readiness/priority fields.

Usage:
    python3 scripts/ac_store/backfill_readiness.py [--dry-run] [--ac-store-dir <path>]

Walks all YAML files under docs/acceptance-criteria/ (or the given directory).
For each file that has an 'id:' field and no 'readiness:' field:
  - Adds readiness: reviewed
  - Adds priority: medium (user must promote to approved; scanner ignores reviewed ACs)

Idempotent: skips files that already have 'readiness'.
Uses targeted line insertion (not full YAML round-trip) to preserve file formatting.
Reports count of files modified.

AC-8: Existing ACs are backfilled with readiness: reviewed, priority: medium.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Repo root discovery
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent
_DEFAULT_AC_STORE = _REPO_ROOT / "docs" / "acceptance-criteria"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill readiness: reviewed and priority: medium into AC YAML files "
            "that were authored before those fields were introduced."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print which files would be modified without writing any changes.",
    )
    parser.add_argument(
        "--ac-store-dir",
        default=str(_DEFAULT_AC_STORE),
        help=f"Path to the AC store directory. Default: {_DEFAULT_AC_STORE}",
    )
    return parser.parse_args()


def _file_is_ac(path: Path) -> bool:
    """Return True if the YAML file contains an 'id:' field (looks like an AC)."""
    try:
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        return isinstance(data, dict) and "id" in data
    except (yaml.YAMLError, OSError):
        return False


def _insert_after_id_line(content: str, field: str, value: str) -> str:
    """Insert 'field: value' after the first line starting with 'id:'.

    Uses targeted line insertion to preserve the original file formatting.
    If 'id:' is not found, appends the field at the end.
    """
    lines = content.splitlines(keepends=True)
    insert_idx = None

    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("id:"):
            insert_idx = i + 1
            break

    new_line = f"{field}: {value}\n"

    if insert_idx is not None:
        lines.insert(insert_idx, new_line)
    else:
        # Fallback: append at end
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(new_line)

    return "".join(lines)


def _backfill_file(path: Path, dry_run: bool) -> bool:
    """Backfill readiness and priority fields into the given YAML file.

    Returns True if the file was (or would be) modified, False if skipped.
    """
    try:
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
    except (yaml.YAMLError, OSError) as exc:
        print(f"WARNING: Cannot read {path}: {exc}", file=sys.stderr)
        return False

    if not isinstance(data, dict) or "id" not in data:
        return False

    # Already has readiness — idempotent skip
    if "readiness" in data:
        return False

    # Needs backfill
    if dry_run:
        print(f"[dry-run] Would backfill: {path}")
        return True

    # Insert readiness and priority using targeted line insertion.
    # Insert both after 'id:' line.
    # We insert priority first (bottom of insertion point), then readiness
    # so the final order ends up: id, readiness, priority in the file.
    new_content = content

    if "priority" not in data:
        new_content = _insert_after_id_line(new_content, "priority", "medium")

    if "readiness" not in data:
        new_content = _insert_after_id_line(new_content, "readiness", "reviewed")

    try:
        path.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: Cannot write {path}: {exc}", file=sys.stderr)
        return False
    else:
        print(f"Backfilled: {path}")
        return True


def main() -> int:
    """Entry point. Returns exit code (0 = success, 1 = errors)."""
    args = _parse_args()

    ac_store_dir = Path(args.ac_store_dir)
    if not ac_store_dir.exists():
        print(
            f"ERROR: AC store directory not found: {ac_store_dir}",
            file=sys.stderr,
        )
        return 1

    yaml_files = sorted(ac_store_dir.rglob("*.yaml"))

    if not yaml_files:
        print(f"No YAML files found under {ac_store_dir}.")
        return 0

    modified = 0
    skipped = 0
    errors = 0

    for path in yaml_files:
        try:
            result = _backfill_file(path, dry_run=args.dry_run)
            if result:
                modified += 1
            else:
                skipped += 1
        except (OSError, yaml.YAMLError, ValueError) as exc:
            print(f"ERROR processing {path}: {exc}", file=sys.stderr)
            errors += 1

    mode = "dry-run" if args.dry_run else "actual"
    action = "Would modify" if args.dry_run else "Modified"
    print(
        f"\nBackfill complete ({mode} mode):\n"
        f"  {action}: {modified} files\n"
        f"  Skipped (already have readiness): {skipped} files\n"
        f"  Errors: {errors} files"
    )

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
