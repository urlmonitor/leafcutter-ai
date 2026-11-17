#!/usr/bin/env python3
"""
MODULE: design_authors_report
GOAL: Report the store's test designs by author: every design carrying an authorship mark
    grouped under its step, and every design without one listed as legacy.
BUSINESS CONTEXT: ACD-2500c-3 / ADR-071. Test designs written by the technical planner before
    the code-aware step existed are kept, not deleted; this query is how a reader (and ticket
    ACD-2500b-3, which redoes legacy designs) asks "who wrote the designs" and sees the legacy
    ones named as such.
ARCHITECTURE: A standalone, read-only CLI modelled on assignment_quality.py. `design_authors_report
    [--ac-root DIR] [--json]` walks DIR (default: docs/acceptance-criteria of this checkout) with
    Path.rglob("*.yaml") and yaml.safe_load, skipping files that are not a mapping and records
    without an `id`. Whether a design is legacy is decided ONLY by `_test_intent.is_legacy_design`;
    nothing here re-derives it. `--json` prints exactly {"by_step": {step: [id, ...]}, "legacy":
    [id, ...]} with sorted ids; text mode prints one line per step and a "legacy: N" line. It
    describes and never gates: exit 0 always. Dev-only: it is in no deploy map (like
    approve_acs.py).

DECISION HISTORY:
  - 2026-10-14 [python-coder/ACD-2500c-3]: Created per the architect note, section 2.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from _test_intent import AUTHORSHIP_KEY, is_legacy_design

DEFAULT_AC_ROOT = Path(__file__).resolve().parents[2] / "docs" / "acceptance-criteria"


def design_author(record: dict[str, Any]) -> str | None:
    """Return the authorship mark's ``step`` for a marked design, else ``None`` (no design or legacy)."""
    mark = record.get(AUTHORSHIP_KEY)
    if not record.get("test_spec") or not isinstance(mark, dict):
        return None
    return str(mark.get("step"))


def designs_by_author(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Group record ids by design author: ``{"by_step": {step: [ids]}, "legacy": [ids]}``, ids sorted."""
    by_step: dict[str, list[str]] = {}
    legacy: list[str] = []
    for record in records:
        step = design_author(record)
        if step is not None:
            by_step.setdefault(step, []).append(str(record["id"]))
        elif is_legacy_design(record):
            legacy.append(str(record["id"]))
    return {"by_step": {step: sorted(ids) for step, ids in sorted(by_step.items())}, "legacy": sorted(legacy)}


def _load_records(root: Path) -> list[dict[str, Any]]:
    """Every mapping with an ``id`` found in a YAML file under *root*; unreadable files are reported and skipped."""
    records = []
    for path in sorted(root.rglob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            print(f"[design_authors_report] skipped {path}: {exc}", file=sys.stderr)
            continue
        if isinstance(data, dict) and data.get("id"):
            records.append(data)
    return records


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; always returns 0 (the report describes, it does not gate)."""
    parser = argparse.ArgumentParser(description="Report test designs by author; unmarked designs are legacy.")
    parser.add_argument("--ac-root", type=Path, default=DEFAULT_AC_ROOT, help="AC store folder to walk.")
    parser.add_argument("--json", action="store_true", help="Print one JSON document.")
    args = parser.parse_args(argv)
    report = designs_by_author(_load_records(args.ac_root))
    if args.json:
        print(json.dumps(report, sort_keys=True))
        return 0
    for step, ids in report["by_step"].items():
        print(f"{step}: {len(ids)} ({', '.join(ids)})")
    print(f"legacy: {len(report['legacy'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
