"""
MODULE: test_acd_2100b_3
GOAL: Behavioral tests for ACD-2100b-3 -- "An agent missing from the registry
    and an agent denied permission produce different reports" -- WORKFLOW-LEVEL
    (reporting) half.

    This file covers the halt-and-render behaviour of templates/workflows-js/
    plan-feature.js's Pre-Stage-0 Workspace-Setup Dispatch Permission Gate for
    the `outcome: "agent_not_found"` and `outcome: "permission_denied"`
    verdicts. The companion SCRIPT-level tests (the three-state lookup
    itself) live in unit_tests/ac_driven_dev/test_acd_2100b_3.py -- read that
    file's module docstring before this one.

SURFACE CHANGE: see unit_tests/workflows/test_acd_2100b_1.py's module
    docstring for the full rationale. This file supplies `agent_not_found`
    and `permission_denied` verdicts directly via
    `args.workspace_setup_permission` (plus `args.workspace_setup_agent`, so
    the report is proven to name the value the workflow actually resolved,
    not a hardcoded literal) and observes the workflow's own halt and
    rendered report.

A CONFIRMED, LOWER-CONFIDENCE GAP (report, do not paper over -- ticket
    instruction): AC-4 requires the denial report to "direct the reader at
    the permission setting to change". The original (pre-surface-move) test
    required the literal token `permits_shell` to appear in that report --
    mirroring the OLD message text ("Fix ... config/agent_registry.json's
    permits_shell field ..."). Empirically, plan-feature.js's current
    `outcomeMessages.permission_denied` states that the agent "is not
    permitted to run repository-mutating shell commands" and asks the
    operator to "Report this mis-assignment to the operator" -- it never
    names the `permits_shell` field literally, unlike the message it
    replaced. `test_only_the_denied_report_names_the_permission_setting`
    below keeps the original literal-marker assertion and is expected to be
    RED against the current, unmodified plan-feature.js. This finding is
    reported at lower confidence than the ACD-2100b-1/-2/-3-i gaps because
    the criteria text ("directs the reader at the permission setting") could
    plausibly be read as satisfied by the current prose alone; the ticket's
    "do not paper over it" instruction is followed by keeping the stricter,
    literal-marker reading rather than silently adopting the looser one.

TICKET: 09_TICKET-20260826-ACD-2100b-3.md
AC: ACD-2100b-3
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

_NOT_FOUND_PHRASES = (
    "not found in the registry",
    "not listed in the registry",
    "is not in the registry",
    "not present in the registry",
)
_LISTED_PHRASES = ("is listed", "listed in the registry", "found in the registry")
_NOT_PERMITTED_PHRASES = ("does not permit", "not permitted", "denies", "denied")
_PERMISSION_SETTING_MARKERS = ("permits_shell",)


def _agent_not_found_verdict() -> dict:
    return {"permits": False, "outcome": "agent_not_found", "agent_id": _PROBE_AGENT_ID}


def _permission_denied_verdict() -> dict:
    return {"permits": False, "outcome": "permission_denied", "agent_id": _PROBE_AGENT_ID}


def _setup_calls(result) -> list:
    return [c for c in result.agent_calls if c.label in _SETUP_RELATED_LABELS]


def _report_text(result) -> str:
    parts = []
    if isinstance(result.result, dict):
        parts.append(json.dumps(result.result))
    parts.append(result.error or "")
    parts.append(result.stderr or "")
    return "\n".join(parts)


def _run_absent():
    return run_workflow_under_e2(
        _PLAN_FEATURE_JS, timeout=_TIMEOUT,
        args={
            "workspace_setup_permission": _agent_not_found_verdict(),
            "workspace_setup_agent": _PROBE_AGENT_ID,
        },
    )


def _run_denied():
    return run_workflow_under_e2(
        _PLAN_FEATURE_JS, timeout=_TIMEOUT,
        args={
            "workspace_setup_permission": _permission_denied_verdict(),
            "workspace_setup_agent": _PROBE_AGENT_ID,
        },
    )


class TestAbsentVsDeniedAgentReports(unittest.TestCase):

    def test_absent_agent_and_denied_agent_produce_different_reports(self):
        # covers: ACD-2100b-3
        # angle: criterion
        """AC-3: an `agent_not_found` verdict and a `permission_denied`
        verdict -- identical except for `.outcome` -- render reports that
        differ from each other.
        """
        report_absent = _report_text(_run_absent()).lower()
        report_denied = _report_text(_run_denied()).lower()

        self.assertNotEqual(
            report_absent, report_denied,
            "The absent-agent report is identical to the denied-agent "
            "report -- the two outcomes must produce distinguishable reports.",
        )

    def test_absent_agent_report_names_the_agent_and_says_it_was_not_found(self):
        # covers: ACD-2100b-3
        # angle: criterion
        """AC-1: the `agent_not_found` report names the agent id the check
        resolved (from args.workspace_setup_agent, not a hardcoded literal)
        and states that agent was not found in the registry, and it must not
        name a permission setting.
        """
        result = _run_absent()
        self.assertEqual(result.error, "")
        report = _report_text(result)
        report_lower = report.lower()

        self.assertIn(_PROBE_AGENT_ID, report, f"report={report!r}")
        self.assertTrue(
            any(phrase in report_lower for phrase in _NOT_FOUND_PHRASES),
            f"report={report!r}",
        )
        for marker in _PERMISSION_SETTING_MARKERS:
            self.assertNotIn(marker, report_lower, f"report={report!r}")

        self.assertIsInstance(result.result, dict)
        self.assertNotEqual(result.result.get("status"), "ok")

    def test_only_the_denied_report_names_the_permission_setting(self):
        # covers: ACD-2100b-3
        # angle: criterion
        """AC-2/AC-4 (KNOWN, LOWER-CONFIDENCE GAP -- see module docstring):
        the `permission_denied` report states the agent is listed and is not
        permitted, and (per the original, literal reading of "directs the
        reader at the permission setting") names `permits_shell`; the
        `agent_not_found` report names no permission setting either way.

        The `permits_shell` half of this test is expected to be RED against
        the current, unmodified plan-feature.js -- not softened to pass, per
        this ticket's explicit instruction.
        """
        result_absent = _run_absent()
        result_denied = _run_denied()
        report_absent = _report_text(result_absent).lower()
        report_denied_raw = _report_text(result_denied)
        report_denied = report_denied_raw.lower()

        self.assertIn(_PROBE_AGENT_ID, report_denied_raw, f"report={report_denied_raw!r}")
        self.assertTrue(
            any(phrase in report_denied for phrase in _LISTED_PHRASES),
            f"report={report_denied_raw!r}",
        )
        self.assertTrue(
            any(phrase in report_denied for phrase in _NOT_PERMITTED_PHRASES),
            f"report={report_denied_raw!r}",
        )
        for marker in _PERMISSION_SETTING_MARKERS:
            self.assertIn(
                marker, report_denied,
                f"The denied-agent report does not name the permission "
                f"setting ({marker!r}). report={report_denied_raw!r}",
            )
            self.assertNotIn(marker, report_absent, f"report={report_absent!r}")

    def test_both_outcomes_are_reached_through_the_workflow_entry_point(self):
        # covers: ACD-2100b-3
        # angle: reachability
        """Both reports are produced by driving the REAL workflow entry point
        (via run_workflow_under_e2), and in both cases no downstream
        worktree-setup step is ever dispatched, and the two runs' own
        CONSUMED, returned results differ.
        """
        result_absent = _run_absent()
        result_denied = _run_denied()
        self.assertEqual(result_absent.error, "")
        self.assertEqual(result_denied.error, "")

        for name, result in (("absent", result_absent), ("denied", result_denied)):
            self.assertFalse(
                _setup_calls(result),
                f"[{name}] a step after the check ran, but the run must "
                f"stop at the check. calls={[c.label for c in result.agent_calls]}",
            )
            self.assertIsInstance(result.result, dict, f"[{name}] result={result.result!r}")
            self.assertNotEqual(
                result.result.get("status"), "ok",
                f"[{name}] result={result.result!r}",
            )

        self.assertNotEqual(
            json.dumps(result_absent.result, sort_keys=True),
            json.dumps(result_denied.result, sort_keys=True),
            "The absent-agent and denied-agent runs' own returned results "
            f"are identical. result_absent={result_absent.result!r} "
            f"result_denied={result_denied.result!r}",
        )


if __name__ == "__main__":
    unittest.main()
