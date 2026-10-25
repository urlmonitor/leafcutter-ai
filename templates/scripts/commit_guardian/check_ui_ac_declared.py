"""
MODULE: check_ui_ac_declared.py
GOAL: Reverse-direction CI gate (GE-124e-1): select only screen (UI) acceptance
      criteria that are already done, and record every other criterion with a
      distinct, reasoned outcome.
BUSINESS CONTEXT: A finished screen criterion must declare what it renders
      (GE-124). Criteria still in progress must not be blocked, and non-UI
      criteria must never be counted as passing, or every figure built on this
      gate would be inflated by the whole non-UI store.
ARCHITECTURE: Reads the AC store through the shared index
      (_ac_store_index.get_ac_index) rather than walking the store itself.
      select_criteria() is pure; main() is the I/O boundary. Modelled on
      check_done_proof.py's --mode / --base argument surface. Diff scoping for
      ci-changed mode is GE-124e-4; until then --base is accepted and ignored.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from _ac_store_index import get_ac_index
from _resolve_root import find_project_root

CHECK_NAME = "check-ui-ac-declared"
OUTCOME_SELECTED = "selected"
OUTCOME_SKIP = "skip"
OUTCOME_OUT_OF_SCOPE = "out-of-scope"
REASON_NOT_DONE = "not-done"
REASON_NOT_UI = "not-ui"


def _targets(record: dict[str, Any]) -> list[str]:
    """Normalise change_target (scalar or list) to a list of strings."""
    value = record.get("change_target")
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]


def _classify(record: dict[str, Any]) -> dict[str, str | None]:
    """Return the {outcome, reason} entry for one AC record."""
    if "ui" not in _targets(record):
        return {"outcome": OUTCOME_OUT_OF_SCOPE, "reason": REASON_NOT_UI}
    if record.get("work_status") != "done":
        return {"outcome": OUTCOME_SKIP, "reason": REASON_NOT_DONE}
    return {"outcome": OUTCOME_SELECTED, "reason": None}


def select_criteria(index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Select done UI criteria and record an outcome for every criterion.

    Args:
        index: AC id -> parsed record mapping.

    Returns:
        Dict with ``selected`` (sorted ids), ``outcomes`` ({id: {outcome,
        reason}} for every record) and ``passed`` (always empty: selection
        alone passes nothing).
    """
    outcomes = {ac_id: _classify(rec) for ac_id, rec in sorted(index.items())}
    selected = [i for i, o in outcomes.items() if o["outcome"] == OUTCOME_SELECTED]
    return {"selected": selected, "outcomes": outcomes, "passed": []}


def _build_parser() -> argparse.ArgumentParser:
    """Return the CLI argument parser."""
    parser = argparse.ArgumentParser(description="Reverse UI-declaration gate (GE-124e-1).")
    parser.add_argument("--mode", choices=["precommit", "ci", "ci-changed"], default="ci")
    parser.add_argument("--base", metavar="REF", default="origin/main",
                        help="Git base ref for ci-changed mode (diff scoping is GE-124e-4).")
    parser.add_argument("--ac-root", metavar="DIR", default=None, help="AC store root.")
    parser.add_argument("--json", action="store_true", help="Print the JSON report.")
    return parser


def _load_index(ac_root: Path) -> dict[str, dict[str, Any]] | None:
    """Return the AC index, or None (after announcing) if it cannot be read."""
    try:
        index = get_ac_index(str(ac_root)) if ac_root.is_dir() else {}
    except OSError as exc:
        print(f"[{CHECK_NAME}] cannot read AC store {ac_root}: {exc}", file=sys.stderr)
        return None
    if not index:
        print(f"[{CHECK_NAME}] AC store {ac_root} is missing or empty; "
              "no evidence produced", file=sys.stderr)
        return None
    return index


def main(argv: list[str] | None = None) -> int:
    """Run the gate. Exit 1 when the store is unreadable in CI modes."""
    args = _build_parser().parse_args(argv)
    ac_root = Path(args.ac_root) if args.ac_root else (
        find_project_root() / "docs" / "acceptance-criteria")
    index = _load_index(ac_root)
    if index is None:
        return 0 if args.mode == "precommit" else 1
    report = select_criteria(index)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        skipped = sum(1 for o in report["outcomes"].values() if o["outcome"] == OUTCOME_SKIP)
        print(f"[{CHECK_NAME}] selected={len(report['selected'])} "
              f"skipped={skipped} total={len(index)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"[{CHECK_NAME}] unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)

# DECISION HISTORY
# ================================================================================
# - 2026-10-23 19:40 [python-coder]: Three outcomes (selected, skip not-done, out-of-scope); change_target normalised from scalar-or-list; unreadable store blocks in CI because no evidence was produced. (#EPIC-EveryScreenSaysWhichRequirementItIs/32)
