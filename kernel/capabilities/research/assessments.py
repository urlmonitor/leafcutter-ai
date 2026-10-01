"""Retain conditional per-need assessments without best-result overwrite.
MODULE: kernel.capabilities.research.assessments
GOAL: Keep partial and conflicting child interpretations visible across research resumes.
BUSINESS CONTEXT: A stronger sufficiency vote cannot verify a supplied historical report.
ARCHITECTURE: Pure merge and coverage guards over existing research state.
"""
from __future__ import annotations

import json
from kernel.contracts.enums import NeedStatus
from kernel.capabilities.research.state import Collected
from pydantic import JsonValue


def merge_assessments(out: Collected, incoming: dict[str, dict[str, JsonValue]]) -> None:
    """Retain matching reports once and conflicting reports under an unresolved envelope.

    Args:
        out: Collected research evidence and assessment state.
        incoming: Attributed per-need child assessments.
    """
    for need_id, report in incoming.items():
        previous = out.assessments.get(need_id)
        if previous is None or previous == report:
            out.assessments[need_id] = report
            continue
        reports = previous.get("reports", [previous]) if previous.get("assessment_conflict") else [previous]
        keyed = {json.dumps(item, sort_keys=True): item for item in [*reports, report]}
        out.assessments[need_id] = {
            "status": "unresolved", "assessment_conflict": True,
            "reports": [keyed[key] for key in sorted(keyed)],
            "limitations": ["Child assessments disagree; no report supersedes another."],
        }


def guard_assessments(out: Collected) -> None:
    """Keep conditional assessment coverage partial after all child bundle merges.

    Args:
        out: Mutable collected research state.
    """
    for need_id, report in out.assessments.items():
        if report.get("status") in {"fulfilled", "supported"}:
            continue
        if out.coverage.get(need_id) is NeedStatus.SATISFIED:
            out.coverage[need_id] = NeedStatus.PARTIAL
        note = f"need {need_id}: conditional assessment remains {report.get('status', 'unresolved')}"
        if note not in out.limitations:
            out.limitations.append(note)


# DECISION HISTORY
# - 2026-10-01 23:00 [python-coder]: Preserve conflicting child reports without partial-to-ready overwrite. (#EPIC-RepositoryResearchAnswers/TICKET-20261001-KM-500f-2)
