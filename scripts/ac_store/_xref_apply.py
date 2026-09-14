"""
MODULE: scripts.ac_store._xref_apply
GOAL: Write cross_reference_audit.py's high-confidence backfill matches back
    to their AC YAML files.
BUSINESS CONTEXT: AC-4 requires --apply to write `implemented_by` for
    high-confidence matches only, and AC-6 requires that write to be
    idempotent — running --apply twice against an AC that is already linked
    must not duplicate the entry.
ARCHITECTURE: Sibling module to cross_reference_audit.py inside
    scripts/ac_store/. It is never executed directly; cross_reference_audit.py
    imports it via the bare-import sys.path bootstrap documented in that
    module's header, so this file works whether the entry point is run as a
    script or imported as a package. Consumes the MatchRecord shape defined
    in _xref_matching.py.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from _xref_matching import MatchRecord

_log = logging.getLogger(__name__)


def _apply_backfill(matches: list[MatchRecord]) -> int:
    """Write implemented_by for high-confidence matches.

    Returns the number of ACs modified.
    """
    modified = 0
    for match in matches:
        if match["confidence"] != "high":
            continue

        ac = match.get("_ac", {})
        ac_path_str = ac.get("_path")
        if not ac_path_str:
            _log.warning("No _path for AC %s — skipping apply", match["ac_id"])
            continue

        ac_path = Path(ac_path_str)
        ticket_path = match["ticket_path"]

        # Re-read the AC YAML fresh to avoid stale state
        try:
            with open(ac_path, encoding="utf-8") as fh:
                ac_data = yaml.safe_load(fh)
        except (OSError, yaml.YAMLError) as exc:
            _log.warning("Cannot re-read AC %s for apply: %s", ac_path, exc)
            continue

        if not isinstance(ac_data, dict):
            _log.warning("AC file %s is not a dict — skipping apply", ac_path)
            continue

        implemented_by = ac_data.get("implemented_by", [])
        if not isinstance(implemented_by, list):
            implemented_by = []

        # Idempotency check — AC-6
        if ticket_path in implemented_by:
            _log.info(
                "no-op (already linked): %s already has %s in implemented_by",
                match["ac_id"],
                ticket_path,
            )
            continue

        implemented_by.append(ticket_path)
        ac_data["implemented_by"] = implemented_by
        ac_data["work_status"] = "done"

        try:
            with open(ac_path, "w", encoding="utf-8") as fh:
                yaml.dump(
                    ac_data,
                    fh,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )
            _log.info(
                "Applied: %s ← %s (work_status: done)", match["ac_id"], ticket_path
            )
            modified += 1
        except OSError as exc:
            _log.error("Cannot write AC %s: %s", ac_path, exc)

    return modified


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [python-coder]: Extracted from cross_reference_audit.py into this
  module (the --apply backfill writer) as part of the file-size split
  required by check-file-size (GE-127b-1) — the source file had grown to 557
  content lines against the 400-line limit. Moved verbatim; no behaviour
  changed.
====================================================================
"""
