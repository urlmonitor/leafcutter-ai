#!/usr/bin/env python3
"""
backfill_components.py — Backfill the `components` list on pre-enforcement ACs.

The knowledge graph reads the LIST field `components` to build
component_membership edges, but historically ACs only carried the SCALAR
`component` field. This one-shot, idempotent backfill brings existing ACs up to
standard so a component query returns a populated, connected answer
retroactively — not only for new work.

Strategy (KM-KGS-100e-5, KM-KGS-100e-5-i):
  For each AC YAML that has an `id` but no non-empty `components` list:
    - If its scalar `component` names a valid registry component
      (docs/acceptance-criteria/index.yaml), set `components: [<component>]`.
    - Otherwise (scalar missing, blank, or not in the registry) do NOT guess —
      report the file for human review and leave it unchanged.

Idempotent: an AC that already has a non-empty `components` list is skipped.
Uses targeted line insertion (not a YAML round-trip) to preserve formatting,
matching backfill_readiness.py.

Usage:
    python3 scripts/ac_store/backfill_components.py [--dry-run] \\
        [--ac-store-dir <path>] [--index <path>]

Exit codes:
    0 - success (including when files were reported for review)
    1 - a real error occurred (unreadable store dir, write failures)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from _ac_components import load_registry_ids

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent
_DEFAULT_AC_STORE = _REPO_ROOT / "docs" / "acceptance-criteria"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill the `components` list onto ACs that only carry the legacy "
            "scalar `component` field, so the knowledge graph can build "
            "component_membership edges for them."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without writing any files.",
    )
    parser.add_argument(
        "--ac-store-dir",
        default=str(_DEFAULT_AC_STORE),
        help=f"Path to the AC store directory. Default: {_DEFAULT_AC_STORE}",
    )
    parser.add_argument(
        "--index",
        default=None,
        help="Path to the components.json registry. Default: <ac-store-dir>/../components.json",
    )
    return parser.parse_args()


def _has_nonempty_components(data: dict) -> bool:
    """True when the AC already declares a non-empty `components` list."""
    raw = data.get("components")
    return isinstance(raw, list) and any(
        isinstance(v, str) and v.strip() for v in raw
    )


def _insert_after_id_line(content: str, block: str) -> str:
    """Insert a YAML block immediately after the first top-level `id:` line.

    Preserves original formatting. Falls back to appending at EOF if no `id:`
    line is found (should not happen for AC files).
    """
    lines = content.splitlines(keepends=True)
    insert_idx = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("id:") and not line[0].isspace():
            insert_idx = i + 1
            break

    if insert_idx is not None:
        lines.insert(insert_idx, block)
    else:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(block)
    return "".join(lines)


def _backfill_file(
    path: Path,
    registry_ids: set[str],
    dry_run: bool,
) -> str:
    """Backfill one AC file.

    Returns one of: "skipped" (already has components or not an AC),
    "backfilled" (list added / would be added), "review" (component could not
    be inferred safely — reported, left unchanged), or "error".
    """
    try:
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
    except (yaml.YAMLError, OSError) as exc:
        print(f"WARNING: cannot read {path}: {exc}", file=sys.stderr)
        return "error"

    if not isinstance(data, dict) or "id" not in data:
        return "skipped"

    if _has_nonempty_components(data):
        return "skipped"  # idempotent

    scalar = data.get("component")
    inferred = scalar.strip() if isinstance(scalar, str) and scalar.strip() else None

    if inferred is None or inferred not in registry_ids:
        reason = (
            "no scalar `component`"
            if inferred is None
            else f"scalar component '{inferred}' not in registry"
        )
        print(f"REVIEW: {path} — {reason}; left unchanged (needs human review).")
        return "review"

    if dry_run:
        print(f"[dry-run] Would backfill {path} -> components: [{inferred}]")
        return "backfilled"

    block = f"components:\n  - {inferred}\n"
    new_content = _insert_after_id_line(content, block)
    try:
        path.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot write {path}: {exc}", file=sys.stderr)
        return "error"
    print(f"Backfilled {path} -> components: [{inferred}]")
    return "backfilled"


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns exit code (0 = success, 1 = errors)."""
    if argv is not None:
        sys.argv = [sys.argv[0], *argv]
    args = _parse_args()

    ac_store_dir = Path(args.ac_store_dir)
    if not ac_store_dir.is_dir():
        print(f"ERROR: AC store directory not found: {ac_store_dir}", file=sys.stderr)
        return 1

    index_path = Path(args.index) if args.index else (ac_store_dir.parent / "components.json")
    registry_ids = load_registry_ids(index_path)
    if not registry_ids:
        print(
            f"ERROR: could not load a component registry from {index_path}; "
            "refusing to backfill without a registry to validate against.",
            file=sys.stderr,
        )
        return 1

    counts = {"backfilled": 0, "skipped": 0, "review": 0, "error": 0}
    review_files: list[Path] = []

    for path in sorted(ac_store_dir.rglob("*.yaml")):
        if path.name == "index.yaml":
            continue
        result = _backfill_file(path, registry_ids, dry_run=args.dry_run)
        counts[result] += 1
        if result == "review":
            review_files.append(path)

    mode = "dry-run" if args.dry_run else "actual"
    action = "Would backfill" if args.dry_run else "Backfilled"
    print(
        f"\nComponents backfill complete ({mode}):\n"
        f"  {action}: {counts['backfilled']} files\n"
        f"  Skipped (already have components / not an AC): {counts['skipped']} files\n"
        f"  Needs review (component not inferable): {counts['review']} files\n"
        f"  Errors: {counts['error']} files"
    )
    if review_files:
        print("\nFiles needing human review (component could not be inferred):")
        for p in review_files:
            print(f"  - {p}")

    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
