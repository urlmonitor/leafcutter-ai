"""
MODULE: scripts/ac_store/approve_acs.py
GOAL: Promote reviewed leaf ACs of a goal to readiness: approved without
    hand-editing YAML.
BUSINESS CONTEXT: AC ACD-1200b-5. After reviewing leaf ACs under a goal, this
    script promotes each reviewed leaf from readiness: reviewed to approved
    in-place. The mutation is append-only (exactly one amended_by entry is
    added per leaf) and idempotent: leaves already at readiness: approved are
    not written at all, ensuring byte-stability on re-run.
ARCHITECTURE: Standalone CLI script. Two modes:
    --goal <GOAL_AC_ID>: find goal AC by id, promote all reviewed leaf children.
    --ac <AC_ID>: directly promote a single AC to approved.
    Uses targeted string replacement (not full yaml.dump round-trip) to preserve
    field order and comments. Follows the same store-mutation convention as the
    sibling scripts/ac_store/mark_ac_done.py.
    Exit codes: 0 (success or no-op), 1 (not found or read error),
    2 (unexpected readiness value).
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import yaml


# Matches the complete amended_by YAML block: the key line (including any
# inline value such as "[]") plus all continuation lines that start with
# a space/tab (nested mappings) or a dash (block list items), stopping before
# the first line that begins with an identifier character (next top-level key).
_AMENDED_BY_RE = re.compile(
    r"^amended_by:.*\n(?:[ \t][^\n]*\n|-[^\n]*\n)*",
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# AC lookup helper (same pattern as mark_ac_done.py)
# ---------------------------------------------------------------------------


def _find_ac_file(ac_root: Path, ac_id: str) -> Optional[Path]:
    """Walk ac_root recursively for a YAML file whose ``id`` field matches ac_id.

    Args:
        ac_root: Root directory to search recursively.
        ac_id: The AC identifier string to match against the ``id:`` field.

    Returns:
        The first matching Path, or None if not found.
    """
    for candidate in ac_root.rglob("*.yaml"):
        try:
            data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError):
            continue
        if isinstance(data, dict) and data.get("id") == ac_id:
            return candidate
    return None


# ---------------------------------------------------------------------------
# Targeted YAML mutation helpers
# ---------------------------------------------------------------------------


def _build_amended_by_block(existing: list, new_entry: dict) -> str:
    """Render the YAML block for amended_by with new_entry appended.

    Args:
        existing: Current list of amended_by entries (may be empty).
        new_entry: New entry dict to append (keys: action, agent, date).

    Returns:
        YAML text for the complete ``amended_by:`` key-value block,
        including the trailing newline produced by yaml.dump.
    """
    new_list = list(existing) + [new_entry]
    return yaml.dump(
        {"amended_by": new_list},
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )


def _promote_leaf(ac_file: Path, dry_run: bool = False) -> int:
    """Promote a single leaf AC from readiness: reviewed to readiness: approved.

    Performs two targeted in-place mutations: replaces the ``readiness`` field
    value and appends one entry to ``amended_by``. If readiness is already
    ``approved``, the file is not written at all (byte-stable idempotency).

    Args:
        ac_file: Path to the leaf AC YAML file.
        dry_run: When True, log what would happen but do not write files.

    Returns:
        0 on success or no-op, 1 on read/write error, 2 on unexpected readiness.
    """
    try:
        raw_text = ac_file.read_text(encoding="utf-8")
        data = yaml.safe_load(raw_text)
    except (OSError, yaml.YAMLError) as exc:
        print(f"ERROR: Cannot read AC file {ac_file}: {exc}", file=sys.stderr)
        return 1

    if not isinstance(data, dict):
        print(f"ERROR: AC file {ac_file} did not parse to a dict", file=sys.stderr)
        return 1

    ac_id = data.get("id", ac_file.name)
    readiness = data.get("readiness", "")

    # Already approved — skip without touching the file (byte-stable idempotency)
    if readiness == "approved":
        print(f"no-op {ac_id}: readiness already approved")
        return 0

    if readiness != "reviewed":
        print(
            f"SKIP: {ac_id} has readiness={readiness!r} (not reviewed) — skipping",
            file=sys.stderr,
        )
        return 2

    if dry_run:
        print(f"[dry-run] would promote {ac_id} readiness reviewed -> approved")
        return 0

    # --- Targeted replacement 1: readiness field ---
    # Use simple string replacement when the exact literal is present; fall back
    # to regex for edge cases where extra whitespace exists around the value.
    if "readiness: reviewed" in raw_text:
        updated = raw_text.replace("readiness: reviewed", "readiness: approved", 1)
    else:
        updated = re.sub(
            r"^(readiness:\s*)reviewed$",
            r"\g<1>approved",
            raw_text,
            count=1,
            flags=re.MULTILINE,
        )

    # --- Targeted replacement 2: amended_by field ---
    existing_amended_by = data.get("amended_by") or []
    if not isinstance(existing_amended_by, list):
        existing_amended_by = []

    today_str = date.today().isoformat()
    new_entry = {"action": "approved", "agent": "approve_acs", "date": today_str}
    new_block = _build_amended_by_block(existing_amended_by, new_entry)

    match = _AMENDED_BY_RE.search(updated)
    if match:
        updated = updated[: match.start()] + new_block + updated[match.end() :]
    else:
        # amended_by field absent — append at end of file
        updated = updated.rstrip("\n") + "\n" + new_block

    try:
        ac_file.write_text(updated, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: Cannot write AC file {ac_file}: {exc}", file=sys.stderr)
        return 1

    print(f"promoted {ac_id} readiness reviewed -> approved")
    return 0


# ---------------------------------------------------------------------------
# Internal implementation shared by public API and CLI
# ---------------------------------------------------------------------------


def _do_approve_goal(goal_ac_id: str, ac_root: Path, dry_run: bool = False) -> int:
    """Find goal AC, enumerate covered_by leaves, promote each from reviewed to approved.

    Args:
        goal_ac_id: The AC identifier of the goal to process.
        ac_root: Root directory to search recursively for AC YAML files.
        dry_run: When True, log what would happen but do not write files.

    Returns:
        0 on success or complete no-op, 1 on goal-AC-not-found or read error,
        2 if any leaf had an unexpected readiness value.
    """
    goal_file = _find_ac_file(ac_root, goal_ac_id)
    if goal_file is None:
        print(
            f"ERROR: goal AC {goal_ac_id} not found in {ac_root}",
            file=sys.stderr,
        )
        return 1

    try:
        goal_data = yaml.safe_load(goal_file.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(
            f"ERROR: Cannot read goal AC file {goal_file}: {exc}",
            file=sys.stderr,
        )
        return 1

    if not isinstance(goal_data, dict):
        print(
            f"ERROR: Goal AC file {goal_file} did not parse to a dict",
            file=sys.stderr,
        )
        return 1

    covered_by = goal_data.get("covered_by") or []
    if not isinstance(covered_by, list):
        print(
            f"ERROR: covered_by in {goal_ac_id} is not a list: {covered_by!r}",
            file=sys.stderr,
        )
        return 1

    exit_code = 0
    for leaf_id in covered_by:
        leaf_file = _find_ac_file(ac_root, leaf_id)
        if leaf_file is None:
            print(
                f"WARNING: leaf AC {leaf_id} not found in {ac_root}",
                file=sys.stderr,
            )
            continue
        result = _promote_leaf(leaf_file, dry_run=dry_run)
        if result != 0 and exit_code == 0:
            exit_code = result
    return exit_code


# ---------------------------------------------------------------------------
# Public API (imported by tests and other scripts)
# ---------------------------------------------------------------------------


def approve_acs(goal_ac_id: str, ac_root: Path) -> None:
    """Promote all reviewed leaf ACs of a goal to readiness: approved.

    Scans ``ac_root`` recursively for the goal AC (matched by
    ``id == goal_ac_id``), reads its ``covered_by`` list, and for each listed
    leaf AC promotes it from ``readiness: reviewed`` to ``readiness: approved``
    via targeted in-place YAML mutation. Leaves already at
    ``readiness: approved`` are skipped without any file write (byte-stable
    idempotency). Exactly one ``amended_by`` entry is appended per leaf
    promoted; no other field is altered.

    Args:
        goal_ac_id: The AC identifier of the goal whose covered_by leaves
            are to be promoted.
        ac_root: Root directory to search recursively for AC YAML files.
    """
    _do_approve_goal(goal_ac_id, ac_root, dry_run=False)


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the approve_acs CLI.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Promote reviewed leaf ACs of a goal to readiness: approved "
            "in the AC YAML store."
        ),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--goal",
        metavar="GOAL_AC_ID",
        help="Goal AC identifier; all reviewed leaf children are promoted.",
    )
    mode.add_argument(
        "--ac",
        metavar="AC_ID",
        help="Directly promote a single AC to approved.",
    )
    parser.add_argument(
        "--ac-root",
        metavar="DIR",
        default="docs/acceptance-criteria/",
        help=(
            "Root directory to search for AC YAML files "
            "(default: docs/acceptance-criteria/)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would happen but do not write any files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for approve_acs.

    Args:
        argv: Argument list (defaults to sys.argv[1:] when None).

    Returns:
        Exit code: 0 on success or no-op, 1 on lookup/read error,
        2 on unexpected readiness value.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    ac_root = Path(args.ac_root)

    if args.goal:
        return _do_approve_goal(args.goal, ac_root, dry_run=args.dry_run)

    # --ac mode: directly promote a single AC
    ac_file = _find_ac_file(ac_root, args.ac)
    if ac_file is None:
        print(f"ERROR: AC {args.ac} not found in {ac_root}", file=sys.stderr)
        return 1
    return _promote_leaf(ac_file, dry_run=args.dry_run)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"[approve-acs] unexpected error, skipping: {exc}", file=sys.stderr)
        sys.exit(0)
