"""
Return-value dataclasses for the work-item duplicate repair.

MODULE: _work_item_repair_types
GOAL: Define the two small, importable dataclasses (``Resolution`` and
    ``RepairReport``) that make up the public contract returned by
    ``repair_work_item_duplicates.repair_work_item_duplicates()``. Split into
    its own file so the orchestrator, planning, and I/O modules can all share
    one definition without any of them exceeding the project's
    400-line-per-new-file limit.
BUSINESS CONTEXT: GE-122e-2 ("each work item that exists twice is reduced to
    the one copy that is right") fixes this exact shape in
    unit_tests/commit_guardian/test_ge_122e_2.py's "CONTRACT UNDER TEST" --
    ``report.resolutions`` must be a list of ``Resolution`` objects, one per
    identifier actually repaired, and must NOT be narrowed without updating
    every consumer of that test contract.
ARCHITECTURE: Pure data holders, no behaviour, no I/O.

DOC_LINKS:
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122e-2.yaml

DECISION HISTORY:
  - 2026-08-18 [python-coder/GE-122e-2]: Extracted from
    repair_work_item_duplicates.py to keep every new file in this directory
    under the check-file-size 400-line limit for new files.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Resolution:
    """One repaired work-item identifier.

    Attributes:
        identifier: The contested "TICKET-*.md" basename.
        survivor_path: Absolute path to the one file left behind.
        deleted_path: Absolute path to the file this repair removed.
        resolution: Short label for the decision taken.
        reason: Human-readable explanation, recorded verbatim on the
            survivor file's own on-disk content.
    """

    identifier: str
    survivor_path: str
    deleted_path: str
    resolution: str
    reason: str


@dataclass
class RepairReport:
    """The result of one ``repair_work_item_duplicates`` call.

    Attributes:
        resolutions: One Resolution per identifier actually repaired in this
            call. Empty when nothing was left to repair.
    """

    resolutions: list[Resolution] = field(default_factory=list)
