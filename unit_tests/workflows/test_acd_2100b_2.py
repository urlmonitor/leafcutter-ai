"""
MODULE: test_acd_2100b_2
GOAL: Behavioral tests for ACD-2100b-2 -- "A registry whose contents cannot be
    understood is reported as unusable and not as a permission verdict" --
    WORKFLOW-LEVEL (reporting) half.

    This file covers the halt-and-render behaviour of templates/workflows-js/
    plan-feature.js's Pre-Stage-0 Workspace-Setup Dispatch Permission Gate for
    the `outcome: "parse_failure"` verdict. The companion SCRIPT-level tests
    (the classification decision itself, including the confirmed AC-4
    position-tracking gap) live in
    unit_tests/ac_driven_dev/test_acd_2100b_2.py -- read that file's module
    docstring before this one.

SURFACE CHANGE: see unit_tests/workflows/test_acd_2100b_1.py's module
    docstring for the full rationale (ACD-2100b-5 moved the registry read out
    of this workflow's sandboxed body). This file supplies a `parse_failure`
    verdict directly via `args.workspace_setup_permission` and observes the
    workflow's own halt and rendered report -- the workflow makes no registry
    read and no agent dispatch of its own for this check at all.

A GAP CARRIED FORWARD FROM THE CLASSIFICATION SURFACE -- NOW CLOSED: when
    this file was first authored, check_workspace_setup_permission.py's
    `parse_failure` verdict carried no position/offset/fragment field (see
    unit_tests/ac_driven_dev/test_acd_2100b_2.py's module docstring), and
    plan-feature.js's `outcomeMessages.parse_failure` was a single static
    string that never referenced any field of the verdict, so this workflow's
    rendered report for ANY `parse_failure` verdict was identical text
    regardless of where the real interpretation failure occurred. That gap
    was closed by ACD-2100b-5's port: the verdict now carries
    `position`/`line`/`column`, and `outcomeMessages` now interpolates them.
    The primary, exhaustively tested proof that this now works lives on the
    classification surface (its
    `test_parse_failure_verdict_states_where_interpretation_failed`); it is
    not re-duplicated here since the workflow report contains strictly less
    information than the verdict it is built from.

TICKET: 08_TICKET-20260826-ACD-2100b-2.md
AC: ACD-2100b-2
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

_FORBIDDEN_PERMISSION_VERDICT_MARKERS = ("permit", "permits_shell")
_UNREADABLE_PHRASES = ("could not be read", "could not read", "cannot be read", "unreadable")
_UNINTERPRETABLE_PHRASES = (
    "could not be interpreted",
    "cannot be interpreted",
    "could not interpret",
    "failed to interpret",
)

_PARSE_FAILURE_VERDICT = {
    "permits": False,
    "outcome": "parse_failure",
    "agent_id": "worktree-agent",
    "location": "/example/repo/.leafcutter/config/agent_registry.json",
}
_READ_FAILURE_VERDICT = {
    "permits": False,
    "outcome": "read_failure",
    "agent_id": "worktree-agent",
    "location": "/example/repo/.leafcutter/config/agent_registry.json",
}


def _setup_calls(result) -> list:
    return [c for c in result.agent_calls if c.label in _SETUP_RELATED_LABELS]


def _report_text(result) -> str:
    parts = []
    if isinstance(result.result, dict):
        parts.append(json.dumps(result.result))
    parts.append(result.error or "")
    parts.append(result.stderr or "")
    return "\n".join(parts)


class TestUninterpretableRegistryReport(unittest.TestCase):

    def test_parse_failure_verdict_is_reported_as_uninterpretable(self):
        # covers: ACD-2100b-2
        # angle: criterion
        """AC-1: a `parse_failure` verdict supplied via args makes the
        workflow halt and state the registry was read but could not be
        interpreted.
        """
        result = run_workflow_under_e2(
            _PLAN_FEATURE_JS,
            timeout=_TIMEOUT,
            args={"workspace_setup_permission": dict(_PARSE_FAILURE_VERDICT)},
        )
        self.assertEqual(result.error, "", f"Harness error: {result.error}")

        report = _report_text(result).lower()
        self.assertTrue(
            any(phrase in report for phrase in _UNINTERPRETABLE_PHRASES),
            f"The report does not state the registry could not be interpreted. report={report!r}",
        )
        self.assertIsInstance(result.result, dict)
        self.assertNotEqual(
            result.result.get("status"), "ok",
            f"The run did not stop for an uninterpretable registry. result={result.result!r}",
        )

    def test_parse_failure_and_read_failure_reports_differ(self):
        # covers: ACD-2100b-2
        # angle: criterion
        """AC-2/AC-3: the `parse_failure` report and the `read_failure`
        report differ from each other, and neither contains a statement about
        agent permission.
        """
        result_parse = run_workflow_under_e2(
            _PLAN_FEATURE_JS, timeout=_TIMEOUT,
            args={"workspace_setup_permission": dict(_PARSE_FAILURE_VERDICT)},
        )
        result_read = run_workflow_under_e2(
            _PLAN_FEATURE_JS, timeout=_TIMEOUT,
            args={"workspace_setup_permission": dict(_READ_FAILURE_VERDICT)},
        )
        self.assertEqual(result_parse.error, "")
        self.assertEqual(result_read.error, "")

        report_parse = _report_text(result_parse).lower()
        report_read = _report_text(result_read).lower()

        self.assertNotEqual(
            report_parse, report_read,
            "The uninterpretable-registry report is identical to the "
            "unreadable-registry report -- the two distinct outcomes must "
            "produce distinguishable reports.",
        )
        self.assertFalse(
            any(phrase in report_read for phrase in _UNINTERPRETABLE_PHRASES),
            f"The unreadable-registry report now uses the uninterpretable "
            f"wording -- the two outcomes have collapsed. report={report_read!r}",
        )
        self.assertFalse(
            any(phrase in report_parse for phrase in _UNREADABLE_PHRASES),
            "The uninterpretable-registry report reuses the unreadable-"
            f"registry's wording instead of stating its own distinct outcome. "
            f"report={report_parse!r}",
        )
        for marker in _FORBIDDEN_PERMISSION_VERDICT_MARKERS:
            self.assertNotIn(marker, report_parse, f"marker={marker!r} report={report_parse!r}")
            self.assertNotIn(marker, report_read, f"marker={marker!r} report={report_read!r}")

    def test_parse_failure_does_not_end_the_run_with_an_unhandled_failure(self):
        # covers: ACD-2100b-2
        # angle: failure
        """The run's recorded outcome must be the interpretation report
        rather than an unhandled failure -- the harness records no top-level
        error and the workflow's own returned result is a structured halt
        stating the interpretation report, not a raw uncaught exception.
        """
        result = run_workflow_under_e2(
            _PLAN_FEATURE_JS,
            timeout=_TIMEOUT,
            args={"workspace_setup_permission": dict(_PARSE_FAILURE_VERDICT)},
        )
        self.assertEqual(
            result.error, "",
            f"An unhandled failure escaped the check rather than a recorded halt: {result.error!r}",
        )
        self.assertIsInstance(result.result, dict)
        result_text = json.dumps(result.result).lower()
        self.assertTrue(
            any(phrase in result_text for phrase in _UNINTERPRETABLE_PHRASES),
            f"The run's recorded outcome is not the interpretation report. result={result.result!r}",
        )
        for marker in _FORBIDDEN_PERMISSION_VERDICT_MARKERS:
            self.assertNotIn(marker, result_text, f"marker={marker!r} result={result.result!r}")

    def test_acd_2100b_2_reachable_from_entry_point(self):
        # covers: ACD-2100b-2
        # angle: reachability
        """Driving the REAL workflow entry point (via run_workflow_under_e2)
        with a `parse_failure` verdict produces the uninterpretable-registry
        report as the run's own CONSUMED, returned result, and the run stops
        at the check -- no downstream worktree-setup step is ever dispatched.
        """
        result = run_workflow_under_e2(
            _PLAN_FEATURE_JS,
            timeout=_TIMEOUT,
            args={"workspace_setup_permission": dict(_PARSE_FAILURE_VERDICT)},
        )
        self.assertEqual(result.error, "", f"Harness error: {result.error}")

        self.assertFalse(
            _setup_calls(result),
            "A step after the uninterpretable-registry check ran, but the "
            f"run must stop at the check. calls={[c.label for c in result.agent_calls]}",
        )
        self.assertIsInstance(
            result.result, dict,
            f"The caller observes no structured halt result at all "
            f"(result={result.result!r}) -- the halt must be CONSUMED in "
            "control flow (returned), not merely computed and discarded.",
        )
        self.assertNotEqual(result.result.get("status"), "ok")

        result_text = json.dumps(result.result).lower()
        self.assertTrue(
            any(phrase in result_text for phrase in _UNINTERPRETABLE_PHRASES),
            f"result={result.result!r}",
        )
        for marker in _FORBIDDEN_PERMISSION_VERDICT_MARKERS:
            self.assertNotIn(marker, result_text)


if __name__ == "__main__":
    unittest.main()
