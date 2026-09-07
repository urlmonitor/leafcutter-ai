#!/usr/bin/env python3
"""
MODULE: check_declaring_files
GOAL: Prove, empirically and against a real deployed tree, that every
    declaring file a deployed guardrail reads (a schema, a vocabulary, a
    registry, or a helper module it does not itself contain) actually
    arrived — resolved ONLY from the given deployed output root, never from
    the package checkout beneath it, a parent directory, or the invoking
    process's cwd (AC BP-900h-4). ``--layout-set`` runs the same proof once
    per install layout in an enumerated set, emitting one verdict record per
    layout so a healthy layout cannot answer for a broken one (AC
    BP-900h-4-i).
BUSINESS CONTEXT: On 2026-08-18 five declaring files were confirmed absent
    from a genuine consumer install while every build test passed, because
    every build test to date installs into leafcutter's own self-hosted
    workspace, where the package source tree sits beside the deployed
    output root and each missing file resolves anyway by accident. On
    2026-08-25 the same lookup produced two contradictory field reports,
    both accurate, that turned out to differ only in the adopter's chosen
    package-directory name and in main-checkout-versus-worktree — which is
    why this script's second mode sweeps a SET of layouts rather than
    proving one.
ARCHITECTURE: The derivation and presence-check logic lives in the sibling
    module ``_declaring_files_derivation.py`` (kept separate so this file's
    own CLI/orchestration stays small and independently testable, mirroring
    ``check_consumer_install.py`` / ``_use_install_step.py``). This file
    supplies only: argument parsing, the single-layout mode
    (``--deployed-root``, optionally ``--print-inventory`` and
    ``--extra-inventory-json``), and the multi-layout sweep mode
    (``--layout-set``).

Usage::

    python scripts/ci/check_declaring_files.py --deployed-root <path> \\
        [--print-inventory] [--extra-inventory-json <path>]

    python scripts/ci/check_declaring_files.py --layout-set <config.json>

CI registration::

    - name: Check declaring files resolve from the deployed output root
      run: python leafcutter-ai/scripts/ci/check_declaring_files.py \\
             --deployed-root .leafcutter

Exit codes:
    0 — every ``ours_to_ship`` declaring file resolves under the deployed
        output root (single-layout mode), or every layout in the set is
        complete (layout-set mode). ``--print-inventory`` always exits 0.
    1 — one or more declaring files are missing (named on stdout/stderr,
        together with the guardrail that reads them and the deployed
        location they were expected at).
    2 — usage/environment error (bad arguments, unreadable
        ``--extra-inventory-json``/``--layout-set`` file, or malformed JSON).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import _declaring_files_derivation as dfd  # noqa: E402


def _load_json_list(path: Path, label: str) -> list[dict] | None:
    """Read and parse *path* as a JSON list. Prints an error and returns
    ``None`` on any I/O or parse failure — the caller maps that to exit 2.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: could not read {label} {path}: {exc}", file=sys.stderr)
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"ERROR: {label} {path} is not valid JSON: {exc}", file=sys.stderr)
        return None
    if not isinstance(data, list):
        print(f"ERROR: {label} {path} must be a JSON list, got {type(data).__name__}", file=sys.stderr)
        return None
    return data


def _format_missing_line(deployed_root: Path, entry: dict) -> str:
    expected_abs = deployed_root / entry["expected_at"]
    return (
        f"MISSING: {entry['declaring_file']} read_by={entry['read_by']} "
        f"expected_at={expected_abs}"
    )


def _build_inventory(deployed_root: Path, extra_inventory_path: Path | None) -> list[dict] | None:
    """Derive the inventory for *deployed_root* and merge in
    *extra_inventory_path* when given. Returns ``None`` (caller exits 2) on
    a malformed extras file.
    """
    inventory = dfd.derive_inventory(deployed_root)
    if extra_inventory_path is not None:
        extra = _load_json_list(extra_inventory_path, "--extra-inventory-json")
        if extra is None:
            return None
        inventory = dfd.merge_inventory(inventory, extra)
    return inventory


def _run_single_layout(
    deployed_root: Path, print_inventory: bool, extra_inventory_path: Path | None
) -> int:
    """The ``--deployed-root`` mode: derive + (print inventory | check presence)."""
    inventory = _build_inventory(deployed_root, extra_inventory_path)
    if inventory is None:
        return 2

    if print_inventory:
        print(json.dumps(inventory))
        return 0

    missing = dfd.find_missing(deployed_root, inventory)
    if not missing:
        print(f"DECLARING FILES OK: {len(inventory)} entries, all resolved under {deployed_root}")
        return 0

    print(
        f"DECLARING FILES CHECK FAILED: {len(missing)} of {len(inventory)} "
        f"entries missing under {deployed_root}.",
        file=sys.stderr,
    )
    for entry in missing:
        print(_format_missing_line(deployed_root, entry), file=sys.stderr)
    return 1


def _verdict_for_layout(layout: dict) -> dict:
    """Derive + check one layout descriptor, returning its verdict record
    (AC BP-900h-4-i's ``config_schema_fragment`` shape).
    """
    deployed_root = Path(layout["deployed_root"])
    inventory = dfd.derive_inventory(deployed_root)
    missing_entries = dfd.find_missing(deployed_root, inventory)
    missing = [
        {
            "declaring_file": entry["declaring_file"],
            "read_by": entry["read_by"],
            "expected_at": str(deployed_root / entry["expected_at"]),
        }
        for entry in missing_entries
    ]
    return {
        "layout": layout["layout"],
        "package_dir_name": layout["package_dir_name"],
        "is_worktree": layout["is_worktree"],
        "deployed_root": str(deployed_root),
        "missing": missing,
    }


def _run_layout_set(layout_set_path: Path) -> int:
    """The ``--layout-set`` mode: one verdict per layout, every layout run
    and reported regardless of whether an earlier one already failed (AC
    BP-900h-4-i's "per-layout verdicts, not first failure").
    """
    layouts = _load_json_list(layout_set_path, "--layout-set")
    if layouts is None:
        return 2

    verdicts = [_verdict_for_layout(layout) for layout in layouts]
    print(json.dumps(verdicts))
    return 1 if any(v["missing"] for v in verdicts) else 0


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--deployed-root",
        type=Path,
        help="Single-layout mode: the deployed output root to check.",
    )
    parser.add_argument(
        "--print-inventory",
        action="store_true",
        help="Print the derived (single-layout) inventory as JSON and exit 0.",
    )
    parser.add_argument(
        "--extra-inventory-json",
        type=Path,
        help="Path to a JSON list of extra inventory entries merged in (single-layout mode).",
    )
    parser.add_argument(
        "--layout-set",
        type=Path,
        help="Multi-layout mode: path to a JSON list of layout descriptors.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns an exit code (0 = OK, 1 = check failed, 2 = usage/environment error)."""
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.layout_set is not None:
        return _run_layout_set(args.layout_set)

    if args.deployed_root is not None:
        return _run_single_layout(
            args.deployed_root.resolve(), args.print_inventory, args.extra_inventory_json
        )

    print("ERROR: one of --deployed-root or --layout-set is required.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-01 [python-coder/fast-lane BP-900h-4 build set]: Created.
#   Composes the derivation/presence-check logic in
#   _declaring_files_derivation.py into a single-layout mode (BP-900h-4) and
#   a layout-set sweep mode (BP-900h-4-i), mirroring
#   check_consumer_install.py's small-CLI-over-a-sibling-module shape.
#   Resolution is always deployed_root / expected_at, with deployed_root
#   taken verbatim from --deployed-root / a layout descriptor's own
#   deployed_root field — never a search of any ancestor, decoy, or cwd —
#   which is what makes the anti-decoy test in test_bp_900h_4.py pass by
#   construction rather than by a special case.
# ====================================================================
