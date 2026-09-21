#!/usr/bin/env python3
"""
cross_reference_audit.py — Cross-reference AC store against existing tickets.

Scans existing tickets and finds ones whose acceptance criteria match AC criteria
so that `implemented_by` can be backfilled for ACs that were already implemented
before the AC-driven flow existed.

Usage:
    python3 scripts/ac_store/cross_reference_audit.py [options]

Options:
    --ac-root PATH              Root directory of the AC store (default:
                                docs/acceptance-criteria/ relative to worktree root).
    --tickets-root PATH         Root directory of tickets (default: tickets/ relative
                                to worktree root).
    --apply                     Write backfill to AC YAML files (default: read-only).
    --json                      Output matches as JSON in addition to human-readable.
    --min-confidence {high,medium}
                                Minimum confidence level to report (default: medium).

Exit codes:
    0  Success (even when no matches found — empty is valid).
    1  One or more AC YAML or ticket files could not be read or parsed.

# AC-1: Audit finds exact-criteria matches (confidence: high)
# AC-2: Audit finds keyword matches at medium confidence
# AC-3: No false positives for unrelated tickets
# AC-4: --apply writes implemented_by for high-confidence matches only
# AC-5: Report is written to debugging/logs/
# AC-6: --apply is idempotent for already-linked ACs

MODULE: scripts.ac_store.cross_reference_audit
GOAL: CLI entry point that orchestrates the AC-to-ticket backfill audit.
BUSINESS CONTEXT: Owns argument parsing and the top-level run sequence only —
    load ACs, filter to candidates, load done tickets, match, report, and
    optionally apply. Each of those steps' actual logic lives in a sibling
    module (see ARCHITECTURE) so this file stays a thin, readable
    orchestration layer.
ARCHITECTURE: Sibling modules `_xref_ac_store.py`, `_xref_tickets.py`,
    `_xref_matching.py`, `_xref_report.py`, and `_xref_apply.py` live
    alongside this file in scripts/ac_store/ and hold the AC-store loading/
    filtering, ticket loading/parsing, the two matching passes, report/output
    rendering, and the --apply backfill writer respectively. They are loaded
    via bare imports (e.g. `from _xref_ac_store import ...`) rather than
    relative imports, because this file must work both when executed directly
    (`python3 scripts/ac_store/cross_reference_audit.py`, where Python puts
    this directory at sys.path[0] automatically) and when imported as a
    package (`from scripts.ac_store.cross_reference_audit import
    _filter_todo_acs`, where pytest's `pythonpath = .` only puts the repo
    root on sys.path). The sys.path bootstrap immediately below makes both
    invocation styles resolve the same bare imports. ACS-900e names this
    module's AC-to-source traceability resolution as a contract other tooling
    is expected to reuse rather than re-implement — the split preserves that
    surface unchanged: every name importable from this module before the
    split (`_filter_todo_acs`, `_load_ac_yamls`, `_find_matches`, etc.) is
    still importable from it after the split, via the imports below.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

# Sibling modules live alongside this script; ensure this directory is on
# sys.path so the bare imports below resolve both when this file is executed
# directly (sys.path[0] is already this directory in that case) and when it
# is imported as a package (`from scripts.ac_store.cross_reference_audit
# import ...`), where only the repo root is on sys.path.
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from _xref_ac_store import _filter_todo_acs, _load_ac_yamls  # noqa: E402
from _xref_apply import _apply_backfill  # noqa: E402
from _xref_matching import _find_matches  # noqa: E402
from _xref_report import _print_match, _write_report  # noqa: E402
from _xref_tickets import _load_done_tickets  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_AC_ROOT: str = "docs/acceptance-criteria"
_DEFAULT_TICKETS_ROOT: str = "tickets"
_DEFAULT_LOGS_DIR: str = "debugging/logs"

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    stream=sys.stderr,
)
_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Worktree root detection
# ---------------------------------------------------------------------------

def _detect_worktree_root() -> Path:
    """Walk up from this file to find the worktree root (directory with tickets/)."""
    candidate = Path(__file__).resolve().parent
    for _ in range(6):
        if (candidate / "tickets").exists() or (candidate / "docs").exists():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cross-reference AC store against existing tickets for backfill.",
    )
    parser.add_argument(
        "--ac-root",
        default=None,
        help=f"Root directory of the AC store (default: {_DEFAULT_AC_ROOT})",
    )
    parser.add_argument(
        "--tickets-root",
        default=None,
        help=f"Root directory of tickets (default: {_DEFAULT_TICKETS_ROOT})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Write backfill to AC YAML files (default: read-only)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        dest="output_json",
        help="Also print matches as JSON to stdout",
    )
    parser.add_argument(
        "--min-confidence",
        choices=["high", "medium"],
        default="medium",
        help="Minimum confidence level to report (default: medium)",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    worktree_root = _detect_worktree_root()

    ac_root = Path(args.ac_root) if args.ac_root else worktree_root / _DEFAULT_AC_ROOT
    tickets_root = (
        Path(args.tickets_root)
        if args.tickets_root
        else worktree_root / _DEFAULT_TICKETS_ROOT
    )
    logs_dir = worktree_root / _DEFAULT_LOGS_DIR

    _log.info("AC root: %s", ac_root)
    _log.info("Tickets root: %s", tickets_root)

    # Load data
    all_acs = _load_ac_yamls(ac_root)
    _log.info("Loaded %d AC YAML files", len(all_acs))

    todo_acs = _filter_todo_acs(all_acs)
    _log.info("Filtered to %d todo ACs with empty implemented_by", len(todo_acs))

    done_tickets = _load_done_tickets(tickets_root)
    _log.info("Loaded %d done tickets", len(done_tickets))

    # Run matching
    matches = _find_matches(todo_acs, done_tickets)

    # Filter by minimum confidence
    if args.min_confidence == "high":
        matches = [m for m in matches if m["confidence"] == "high"]

    # Print human-readable output
    if not matches:
        print("No matches found.")
    else:
        print(f"\nFound {len(matches)} match(es):")
        for match in matches:
            _print_match(match)

    # Write report — AC-5
    report_path = _write_report(matches, logs_dir)

    # JSON output flag
    if args.output_json:
        report = {
            "run_date": date.today().isoformat(),
            "matches": [
                {
                    "ac_id": m["ac_id"],
                    "ticket_path": m["ticket_path"],
                    "confidence": m["confidence"],
                    "reason": m["reason"],
                }
                for m in matches
            ],
        }
        print("\n--- JSON Output ---")
        print(json.dumps(report, indent=2))

    # Apply backfill — AC-4, AC-6
    if args.apply:
        high_count = sum(1 for m in matches if m["confidence"] == "high")
        print(
            f"\n--apply: processing {high_count} high-confidence match(es) "
            f"(medium-confidence matches are skipped)."
        )
        modified = _apply_backfill(matches)
        print(f"Applied {modified} AC backfill(s).")

    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [python-coder]: Split this file into cross_reference_audit.py
  (CLI entry point + orchestration) plus five sibling modules —
  _xref_ac_store.py, _xref_tickets.py, _xref_matching.py, _xref_report.py,
  _xref_apply.py — because it had grown to 557 content lines against the
  400-line limit check-file-size enforces. Pure structural refactor: every
  function moved verbatim into the sibling that matches its concern (AC-store
  loading/filtering, ticket loading/parsing, the two matching passes, report/
  output rendering, and the --apply backfill writer respectively); no
  behaviour changed, and every name previously importable from this module
  (`_filter_todo_acs`, `_load_ac_yamls`, `_find_matches`, `_apply_backfill`,
  etc.) remains importable from it via the re-exporting imports above. See
  _xref_ac_store.py's DECISION HISTORY for the ACS-1600a-1 retired-status fix
  this split carried through unchanged. Deploy manifest updated in the same
  commit: scripts/build_phases.py's AC_STORE_DEPLOY_MAP now lists all five new
  sibling files, since a module imported by a deployed hook/script but absent
  from that map raises ModuleNotFoundError in a consumer install even though
  local tests (which import from source) stay green.
====================================================================
"""
