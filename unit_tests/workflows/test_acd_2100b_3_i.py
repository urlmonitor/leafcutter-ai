"""
MODULE: test_acd_2100b_3_i
GOAL: Behavioral tests for ACD-2100b-3-i -- "A registry that holds no agent
    entries is reported as unusable rather than as a missing agent" --
    WORKFLOW-LEVEL (reporting) half.

    This file covers the halt-and-render behaviour of templates/workflows-js/
    plan-feature.js's Pre-Stage-0 Workspace-Setup Dispatch Permission Gate for
    the `outcome: "no_entries_collection"` verdict. The companion SCRIPT-level
    tests (the classification decision itself, including the AC-1
    "what was found" gap that was closed by ACD-2100b-5's port) live in
    unit_tests/ac_driven_dev/test_acd_2100b_3_i.py -- read that file's module
    docstring before this one.

SURFACE CHANGE: see unit_tests/workflows/test_acd_2100b_1.py's module
    docstring for the full rationale. This file supplies a
    `no_entries_collection` verdict directly via
    `args.workspace_setup_permission` and observes the workflow's own halt
    and rendered report.

A GAP CARRIED FORWARD FROM THE CLASSIFICATION SURFACE -- NOW CLOSED: when
    this file was first authored, check_workspace_setup_permission.py's
    `no_entries_collection` verdict carried no "what was found" field (see
    unit_tests/ac_driven_dev/test_acd_2100b_3_i.py's module docstring), and
    plan-feature.js's `outcomeMessages.no_entries_collection` was a single
    static string that never referenced any field of the verdict, so this
    workflow's rendered report for a `no_entries_collection` verdict could
    not name the malformed value or its type. That gap was closed by
    ACD-2100b-5's port: the verdict now carries `agents_type`/`agents_value`,
    and `outcomeMessages` now interpolates them. The primary, exhaustively
    tested proof that this now works lives on the classification surface; it
    is not re-duplicated here for the same reason given in
    unit_tests/workflows/test_acd_2100b_2.py's module docstring (the workflow
    report contains strictly less information than the verdict it renders
    from).

TICKET: 10_TICKET-20260826-ACD-2100b-3-i.md
AC: ACD-2100b-3-i
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"

_TIMEOUT = 20
_SETUP_RELATED_LABELS = ("resolve-worktree-setup-script-path", "worktree-setup")

_PROBE_AGENT_ID = "zqm7_probe_worktree_agent_44xk"

_COULD_NOT_BE_USED_PHRASES = (
    "could not be used",
    "cannot be used",
    "could not be interpreted",
    "is not a list",
    "is not an array",
    "not a list of agent entries",
    "no entries collection",
    "no agent entries",
)
_ABSENCE_PHRASES = (
    "not found in the registry",
    "not listed in the registry",
    "is not in the registry",
    "not present in the registry",
)
_DENIAL_PHRASES = ("is not permitted", "denies", "denied")
_PERMISSION_SETTING_MARKERS = ("permits_shell",)


def _no_entries_collection_verdict() -> dict:
    return {"permits": False, "outcome": "no_entries_collection", "agent_id": _PROBE_AGENT_ID}


def _setup_calls(result) -> list:
    return [c for c in result.agent_calls if c.label in _SETUP_RELATED_LABELS]


def _report_text(result) -> str:
    parts = []
    if isinstance(result.result, dict):
        parts.append(json.dumps(result.result))
    parts.append(result.error or "")
    parts.append(result.stderr or "")
    return "\n".join(parts)


def _run_no_entries_collection():
    return run_workflow_under_e2(
        _PLAN_FEATURE_JS, timeout=_TIMEOUT,
        args={
            "workspace_setup_permission": _no_entries_collection_verdict(),
            "workspace_setup_agent": _PROBE_AGENT_ID,
        },
    )


class TestNoEntriesCollectionReport(unittest.TestCase):

    def test_no_entries_collection_verdict_reports_could_not_be_used(self):
        # covers: ACD-2100b-3-i
        # angle: criterion
        """AC-1 (report half): a `no_entries_collection` verdict supplied via
        args makes the workflow halt and state the registry could not be
        used. The "what was found" naming half of AC-1 is proven on the
        classification surface (unit_tests/ac_driven_dev/
        test_acd_2100b_3_i.py).
        """
        result = _run_no_entries_collection()
        self.assertEqual(result.error, "", f"Harness error: {result.error}")

        report = _report_text(result)
        report_lower = report.lower()
        self.assertTrue(
            any(phrase in report_lower for phrase in _COULD_NOT_BE_USED_PHRASES),
            f"report={report!r}",
        )

    def test_no_entries_collection_report_asserts_neither_absence_nor_denial(self):
        # covers: ACD-2100b-3-i
        # angle: criterion
        """AC-2/AC-3: the no-entries-collection report contains no statement
        that any agent is absent from the registry, and no statement that any
        agent lacks permission -- 'not found' is never worded as 'denied',
        and vice versa.
        """
        result = _run_no_entries_collection()
        self.assertEqual(result.error, "")
        report_lower = _report_text(result).lower()

        for phrase in _ABSENCE_PHRASES:
            self.assertNotIn(phrase, report_lower, f"report={report_lower!r}")
        for phrase in _DENIAL_PHRASES:
            self.assertNotIn(phrase, report_lower, f"report={report_lower!r}")
        for marker in _PERMISSION_SETTING_MARKERS:
            self.assertNotIn(marker, report_lower, f"report={report_lower!r}")

    def test_no_entries_collection_does_not_raise_an_unhandled_failure(self):
        # covers: ACD-2100b-3-i
        # angle: failure
        """The run's recorded outcome must be the report rather than an
        unhandled failure -- the harness records no top-level error and the
        workflow's own returned result is a structured halt.
        """
        result = _run_no_entries_collection()
        self.assertEqual(
            result.error, "",
            f"An unhandled failure escaped the check: {result.error!r}",
        )
        self.assertIsInstance(result.result, dict, f"result={result.result!r}")
        self.assertNotEqual(result.result.get("status"), "ok", f"result={result.result!r}")

    def test_outcome_is_produced_through_the_workflow_entry_point(self):
        # covers: ACD-2100b-3-i
        # angle: reachability
        """The report is produced by driving the REAL workflow entry point
        (via run_workflow_under_e2), and the run stops at the check -- no
        downstream worktree-setup step is ever dispatched -- with the
        recorded outcome CONSUMED (returned) rather than merely computed and
        discarded.
        """
        result = _run_no_entries_collection()
        self.assertEqual(result.error, "", f"Harness error: {result.error}")

        self.assertFalse(
            _setup_calls(result),
            "A step after the no-entries-collection check ran, but the run "
            f"must stop at the check. calls={[c.label for c in result.agent_calls]}",
        )
        self.assertIsInstance(
            result.result, dict,
            f"The caller observes no structured halt result at all "
            f"(result={result.result!r}) -- the halt must be CONSUMED in "
            "control flow (returned), not merely computed and discarded.",
        )
        self.assertNotEqual(result.result.get("status"), "ok", f"result={result.result!r}")


if __name__ == "__main__":
    unittest.main()
