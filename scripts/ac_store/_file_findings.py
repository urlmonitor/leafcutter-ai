"""
MODULE: _file_findings
GOAL: The one place that names the file-findings record keys, its verdict and decision vocabularies,
    and the single predicate "which findings still wait for the technical planner".
BUSINESS CONTEXT: ACD-2500d-3-i (ADR-072; G4 architect note, sections 3 and 5). A file finding that
    says the assigned file only describes a behaviour, or that the behaviour lives elsewhere, needs
    a recorded planner decision before the requirement may be approved. The approval hold and the
    workflow hand-back must read the SAME answer from the record on disk, never from a carried flag
    that could drift from the findings.
ARCHITECTURE: Pure functions and name constants, no I/O. The constants mirror the schema properties
    ``file_findings`` and ``file_findings_opened_files`` of config/ac_store_schema.json; a lockstep
    test asserts each constant and each enum equals the schema's own. A ``consistent`` finding needs
    no decision, so ``undecided_findings`` ignores it. Deployed flat into <root>/scripts/ac_store/
    (see scripts/build_phases_ac_store_rc.py).
"""

from __future__ import annotations

from typing import Any

FINDINGS_KEY = "file_findings"
FINDINGS_OPENED_KEY = "file_findings_opened_files"

VERDICT_CONSISTENT = "consistent"
VERDICT_DESCRIBES = "describes, does not implement"
VERDICT_ABSENT = "absent, not to-be-created"
VERDICT_ELSEWHERE = "behaviour found elsewhere"
VERDICTS: tuple[str, ...] = (VERDICT_CONSISTENT, VERDICT_DESCRIBES, VERDICT_ABSENT, VERDICT_ELSEWHERE)

CHOICES: tuple[str, ...] = ("reassign", "split", "assignment stands")
DECIDER = "it-po"


def findings_of(record: Any) -> list[dict[str, Any]] | None:
    """Return the record's finding dicts, or ``None`` when the step has not run (no list)."""
    value = record.get(FINDINGS_KEY)
    if not isinstance(value, list):
        return None
    return [item for item in value if isinstance(item, dict)]


def undecided_findings(record: Any) -> list[dict[str, Any]]:
    """Return the findings that wait for a planner decision, in stored order.

    A finding waits when its verdict is not ``consistent`` and it carries no decision object.
    An absent or non-list field has none.
    """
    return [
        item for item in findings_of(record) or []
        if item.get("verdict") != VERDICT_CONSISTENT and not isinstance(item.get("decision"), dict)
    ]
