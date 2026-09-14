"""
MODULE: scripts.ac_store._xref_ac_store
GOAL: Load AC YAML records from the AC store and narrow them to the set that
    is genuinely eligible for cross_reference_audit.py's backfill scan.
BUSINESS CONTEXT: cross_reference_audit.py backfills `implemented_by` for ACs
    whose acceptance criteria match an already-done ticket, so work finished
    before the AC-driven flow existed gets linked retroactively. This module
    owns the audit's INPUT selection: reading every AC YAML under the store
    root, then narrowing that set to records that are actually candidates —
    still `todo`, not yet linked, and still in force (not retired via
    status: deprecated / superseded / superseded_by).
ARCHITECTURE: Sibling module to cross_reference_audit.py inside
    scripts/ac_store/. It is never executed directly; cross_reference_audit.py
    imports it via the bare-import sys.path bootstrap documented in that
    module's header, so this file works whether the entry point is run as a
    script (`python3 scripts/ac_store/cross_reference_audit.py`) or imported
    as a package (`from scripts.ac_store.cross_reference_audit import ...`).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

_log = logging.getLogger(__name__)

# AC `status` values meaning the record is retired (config/ac_store_schema.json).
_RETIRED_AC_STATUSES: frozenset[str] = frozenset({"deprecated", "superseded", "superseded_by"})


def _load_ac_yamls(ac_root: Path) -> list[dict[str, Any]]:
    """Load all AC YAML files from the AC store directory tree.

    Returns a list of dicts with at least: id, title, criteria, component,
    work_status, implemented_by. Skips files that cannot be parsed.
    """
    acs: list[dict[str, Any]] = []
    if not ac_root.exists():
        _log.warning("AC root does not exist: %s", ac_root)
        return acs

    for yaml_path in sorted(ac_root.rglob("*.yaml")):
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            if not isinstance(data, dict):
                _log.warning("Skipping non-dict YAML: %s", yaml_path)
                continue
            data["_path"] = str(yaml_path)
            acs.append(data)
        except yaml.YAMLError as exc:
            _log.warning("YAML parse error in %s: %s", yaml_path, exc)
        except OSError as exc:
            _log.warning("Cannot read %s: %s", yaml_path, exc)
    return acs


def _filter_todo_acs(acs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only in-force ACs with work_status: todo and implemented_by: [].

    An AC is additionally required to be in force: its `status` field must be
    absent (defaults to "active", mirroring the existing work_status default)
    or explicitly "active". Records retired via status: deprecated,
    superseded, or superseded_by are excluded even when their work_status and
    implemented_by fields still look eligible, since retirement changes
    neither of those fields.
    """
    result = []
    for ac in acs:
        retired = ac.get("status", "active") in _RETIRED_AC_STATUSES
        work_status = ac.get("work_status", "todo")
        implemented_by = ac.get("implemented_by", [])
        if not retired and work_status == "todo" and not implemented_by:
            result.append(ac)
    return result


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [python-coder/ACS-1600a-1]: Excluded retired ACs (status:
  deprecated / superseded / superseded_by) from _filter_todo_acs candidate
  selection via the new _RETIRED_AC_STATUSES constant. Previously the
  selector read only work_status and implemented_by, so a record retired to
  status: deprecated stayed an eligible backfill candidate — retirement
  changes neither of the fields the selector reads. This was live while the
  ACD-800 tree was being retired to eleven deprecated records in PR #768,
  every one of which kept work_status: todo and implemented_by: [].
- 2026-09-14 [python-coder]: Extracted from cross_reference_audit.py into this
  module (AC-store loading/filtering) as part of the file-size split required
  by check-file-size (GE-127b-1) — the source file had grown to 557 content
  lines against the 400-line limit. Moved verbatim; no behaviour changed.
====================================================================
"""
