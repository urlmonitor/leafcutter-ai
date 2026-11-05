"""
MODULE: test_acd_2100d_5_iv
GOAL: Tests for ACD-2100d-5-iv -- the startup-check reference page and the
    workflow rationale describe the start the route actually accepts.
HOW: the pages are compared with what the INSTALLED command, skill and workflow
    do: the arguments are read from the installed entry texts (ACD-2100d-5-i
    support module) and the halt reports are produced by driving the installed
    plan-feature.js through the E2 harness; nothing is typed here as an
    expectation of either.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from unit_tests.workflows._acd_2100d_5_support import (
    REPO_ROOT,
    REQUEST,
    drive,
    halt_message,
    installed_route,
    read_command_start,
    read_skill_start_args,
)

_LAYOUT = REPO_ROOT / "docs" / "reference" / "plan-feature-layout-and-startup-checks.md"
_RATIONALE = REPO_ROOT / "docs" / "reference" / "plan-feature-workflow-rationale.md"
_VERDICT = "workspace_setup_permission"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("`", "")).strip()


def _page(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _neither_report(route) -> str:
    """The report of a start with neither argument; precondition: it is the ACD-2100d-5-ii report."""
    report = halt_message(drive(route.workflow_path, {"userInput": REQUEST}))
    assert re.search(r"args\.workspace(?![\w])", report), f"the halt report does not name args.workspace: {report!r}"
    return report


class TestStartContractOnThePages(unittest.TestCase):

    def test_pages_list_the_arguments_the_entry_texts_pass_and_which_are_required(self):
        # covers: ACD-2100d-5-iv
        # angle: real_artifact
        """Every argument read from the installed command and skill is listed on the reference
        page; the page marks workspace as what a start needs and the verdict as required only
        for a start without it."""
        route = installed_route()
        names = set(read_command_start(route.command_text)) | {"userInput", *read_skill_start_args(route.skill_text)}
        page = _page(_LAYOUT)
        for name in sorted(names):
            self.assertIn(name, page, f"the reference page does not list the argument {name}")
        lines = page.splitlines()
        workspace_lines = [ln for ln in lines if re.search(r"args\.workspace(?![\w])", ln)]
        self.assertTrue(any(re.search(r"(?i)requir|needs?\b|needed", ln) for ln in workspace_lines),
                        "the page does not say a start needs args.workspace")
        verdict_lines = [ln for ln in lines if _VERDICT in ln and re.search(r"(?i)requir|needed", ln)]
        self.assertTrue(
            any(re.search(r"(?i)\bonly\b", ln) and re.search(r"(?i)without|absent|no maker|not supplied", ln)
                for ln in verdict_lines),
            "the page does not say the verdict is required only for a start without the maker's answer")

    def test_quoted_startup_halt_reports_match_the_workflow_word_for_word(self):
        # covers: ACD-2100d-5-iv
        # angle: reachability
        """The installed workflow driven to each startup halt the page quotes (neither argument, and
        the verdict outcomes) returns a report found word for word on the reference page."""
        route = installed_route()
        page = _norm(_page(_LAYOUT))
        reports = {"neither argument": _neither_report(route)}
        for outcome in ("parse_failure", "agent_not_found", "no_entries_collection", "permission_denied"):
            reports[outcome] = halt_message(
                drive(route.workflow_path, {"userInput": REQUEST}, verdict={"permits": False, "outcome": outcome}))
        for label, report in reports.items():
            self.assertTrue(report, f"{label}: the workflow produced no halt report")
            self.assertIn(_norm(report), page, f"{label}: the page does not quote the workflow's report word for word")

    def test_pages_claim_no_skill_preflight_unless_the_installed_skill_has_it(self):
        # covers: ACD-2100d-5-iv
        # angle: discrimination
        """Neither page says the skill runs a permission pre-flight, because the installed skill has no
        such step.

        Wrong versions caught: revert the fix; a page still says the skill runs the permission
        pre-flight."""
        route = installed_route()
        skill_has_step = re.search(r"(?mi)^#{2,4}\s+.*(WSP|permission)", route.skill_text) is not None
        if skill_has_step:
            return  # the installed skill really has the step, so the pages may describe it
        claim = re.compile(
            r"(?i)skill'?s?\s+(own\s+)?(permission\s+)?pre-?flight"
            r"|run by the\s+/?plan-feature\s+skill"
            r"|skill\s+(itself\s+)?runs?\s+.{0,80}(pre-?flight|check_workspace_setup_permission)"
            r"|bypassing the skill'?s?")
        excuse = re.compile(r"(?i)retired|replaced|formerly|used to")
        for path in (_LAYOUT, _RATIONALE):
            text = _norm(_page(path))
            for sentence in re.split(r"(?<=[.!?])\s+", text):
                if claim.search(sentence) and not excuse.search(sentence):
                    self.fail(f"{path.name} claims a skill permission pre-flight: {sentence[:200]!r}")

    def test_no_argument_no_verdict_row_gives_the_halt_reports_remedy(self):
        # covers: ACD-2100d-5-iv
        # angle: real_artifact
        """The reference page's row for a run with no maker's answer and no verdict contains the
        remedy of the halt report the workflow produces (the arguments and the maker script path)."""
        route = installed_route()
        report = _neither_report(route)
        rows = [ln for ln in _page(_LAYOUT).splitlines()
                if ln.startswith("|") and re.match(r"\|\s*(?i:no\b[^|]*(answer|argument|verdict)|neither)", ln)]
        self.assertEqual(len(rows), 1, f"expected exactly one no-answer/no-verdict row, found {len(rows)}")
        row = _norm(rows[0])
        remedy = set(re.findall(r"args\.\w+", report)) | set(re.findall(r"[\w./-]*worktree\.py", report))
        self.assertTrue(remedy, "the report names no remedy")
        for token in sorted(remedy):
            self.assertIn(token, row, f"the page row does not give the report's remedy {token}")


if __name__ == "__main__":
    unittest.main()
