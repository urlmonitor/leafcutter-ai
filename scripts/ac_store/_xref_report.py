"""
MODULE: scripts.ac_store._xref_report
GOAL: Render cross_reference_audit.py's matches to the terminal and to a
    persisted JSON report.
BUSINESS CONTEXT: AC-5 requires every audit run to leave a JSON report behind
    in debugging/logs/, independent of whether any match was found, so the
    run's outcome can be inspected later without re-running the audit.
ARCHITECTURE: Sibling module to cross_reference_audit.py inside
    scripts/ac_store/. It is never executed directly; cross_reference_audit.py
    imports it via the bare-import sys.path bootstrap documented in that
    module's header, so this file works whether the entry point is run as a
    script or imported as a package. Consumes the MatchRecord shape defined
    in _xref_matching.py.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date
from pathlib import Path

from _xref_matching import MatchRecord

_log = logging.getLogger(__name__)


def _print_match(match: MatchRecord) -> None:
    """Print a single match in human-readable format."""
    ac_id = match["ac_id"]
    ticket_path = match["ticket_path"]
    confidence = match["confidence"]
    reason = match["reason"]

    ac_title = match.get("_ac", {}).get("title", "")
    ticket_name = Path(ticket_path).name

    print(f"\nMATCH (confidence: {confidence}):")
    print(f"  AC:     {ac_id} — \"{ac_title}\"")
    print(f"  Ticket: {ticket_name}")
    print(f"          {ticket_path}")
    print(f"  Reason: {reason}")


def _write_report(
    matches: list[MatchRecord],
    logs_dir: Path,
) -> Path:
    """Write the JSON report to debugging/logs/ and return the file path."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().strftime("%Y%m%d")
    report_path = logs_dir / f"ac_cross_reference_audit_{today}.json"

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

    try:
        with open(report_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
        _log.info("Report written to %s", report_path)
    except OSError as exc:
        _log.error("Cannot write report to %s: %s", report_path, exc)
        sys.exit(1)

    return report_path


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [python-coder]: Extracted from cross_reference_audit.py into this
  module (report/output rendering) as part of the file-size split required by
  check-file-size (GE-127b-1) — the source file had grown to 557 content
  lines against the 400-line limit. Moved verbatim; no behaviour changed.
====================================================================
"""
