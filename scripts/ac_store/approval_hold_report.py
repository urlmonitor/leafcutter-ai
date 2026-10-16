#!/usr/bin/env python3
"""
MODULE: approval_hold_report
GOAL: Print, as ONE deterministic JSON document, which of the asked requirement records may be
    offered for approval and which are held back, with the hold reason of each. Read-only.
BUSINESS CONTEXT: ACD-2500c-2 (ADR-072; G4 architect note sections 2.5 and 5). The /plan-feature
    workflow body cannot read records, so before the final gate and again right before the approval
    write it asks this script, through the shell-permitted agent. An unreadable answer is read as
    "everything held", so the script fails closed: no report is ever printed next to an error.
ARCHITECTURE: `python approval_hold_report.py --ids A,B --store-root DIR [--repo-root DIR]`. Records
    are found with `_rc_records.build_id_index` (a filename walk) and read once each; the only
    predicate is `_approval_holds.approval_hold_reason`, the one approve_acs.py already uses. stdout
    is `{"approved": [ids with no hold], "held": [{id, file, reason}]}` written as bytes (LF only,
    sorted keys, ids in the order asked), `file` repo-relative POSIX. An unknown or unreadable id
    prints nothing on stdout, a message on stderr and exits 1 (2 for a usage error). `--repo-root`
    defaults to the nearest ancestor of the store holding docs/acceptance-criteria. Flat sibling
    modules; deployed to <root>/scripts/ac_store/ (RULE_CHECK_DEPLOY_MAP).

DECISION HISTORY:
  - 2026-10-14 [python-coder/ACD-2500c-2]: Created per the G4 architect note, section 2.5.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from _approval_holds import approval_hold_reason, build_report
from _rc_records import build_id_index, infer_repo_root, load_one
from _rc_report import Finding


def hold_report(repo_root: Path, store_root: Path, ids: list[str]) -> tuple[dict[str, Any] | None, str | None]:
    """The (report, None) of the asked ids, or (None, the message) for an unknown or unreadable id."""
    index = build_id_index(store_root)
    unknown = sorted(i for i in ids if i not in index)
    if unknown:
        return None, f"record ids {unknown} do not exist in the store"
    approved: list[str] = []
    held: list[dict[str, str]] = []
    for rid in ids:
        loaded = load_one(index[rid], repo_root)
        if isinstance(loaded, Finding):
            return None, f"{loaded.file}: {loaded.message}"
        reason = approval_hold_reason(loaded)
        if reason is None:
            approved.append(rid)
        else:
            held.append({"id": rid, "file": loaded.file, "reason": reason})
    return build_report(approved, held), None


def _build_parser() -> argparse.ArgumentParser:
    """The CLI parser."""
    parser = argparse.ArgumentParser(prog="approval_hold_report", description="Print which records are held from approval.")
    parser.add_argument("--ids", required=True, help="comma-separated record ids")
    parser.add_argument("--store-root", help="default <repo-root>/docs/acceptance-criteria")
    parser.add_argument("--repo-root", help="default: nearest ancestor of the store holding docs/acceptance-criteria")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry: print the JSON report on stdout; any error prints none and exits non-zero."""
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2
    ids = list(dict.fromkeys(i.strip() for i in args.ids.split(",") if i.strip()))
    if not ids:
        print("approval_hold_report: --ids names no record", file=sys.stderr)
        return 2
    if args.repo_root:
        repo_root = Path(args.repo_root).resolve()
    else:
        repo_root = infer_repo_root(Path(args.store_root) if args.store_root else Path.cwd())
    store_root = Path(args.store_root).resolve() if args.store_root else repo_root / "docs" / "acceptance-criteria"
    try:
        report, problem = hold_report(repo_root, store_root, ids)
    except OSError as exc:
        report, problem = None, str(exc)
    if report is None:
        print(f"approval_hold_report: {problem}", file=sys.stderr)
        return 1
    sys.stdout.buffer.write((json.dumps(report, sort_keys=True, ensure_ascii=True, indent=2) + "\n").encode("ascii"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
