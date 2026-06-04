"""
MODULE: test_pull_request_project_context
GOAL: Verify that the pull-request agent template and project context file are
    correctly wired per TICKET-20260604-PullRequestAgentProjectContext.
BUSINESS CONTEXT: The pull-request agent must read PROJECT_CONTEXT.md before
    running gh pr create, so the EMU account guard and PR writing standards are
    applied automatically. This test verifies the wiring is in place.
ARCHITECTURE: Reads template and context files directly from the repo; no
    runtime execution required — pure structural assertions.
"""

from __future__ import annotations

import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

_PULL_REQUEST_TEMPLATE = _REPO_ROOT / "templates" / "agents" / "pull-request.md"
_PROJECT_CONTEXT = (
    _REPO_ROOT / ".agents" / "agents" / "pull-request" / "PROJECT_CONTEXT.md"
)


class TestPullRequestTemplatePreflight(unittest.TestCase):
    """AC-4: pull-request template must contain Pre-Flight instruction for PROJECT_CONTEXT.md."""

    def setUp(self) -> None:
        with _PULL_REQUEST_TEMPLATE.open("r", encoding="utf-8") as f:
            self._template_text = f.read()

    def test_preflight_section_exists(self) -> None:
        """Template must contain a section named 'Pre-Flight' (AC-1, AC-4)."""
        self.assertIn(
            "Pre-Flight",
            self._template_text,
            "pull-request.md must contain a 'Pre-Flight' section header",
        )

    def test_project_context_reference_in_preflight(self) -> None:
        """Pre-Flight section must reference PROJECT_CONTEXT.md (AC-1, AC-4)."""
        # Find the Pre-Flight section and verify PROJECT_CONTEXT.md appears within it.
        preflight_idx = self._template_text.find("Pre-Flight")
        self.assertGreater(
            preflight_idx,
            -1,
            "No 'Pre-Flight' section found in pull-request.md",
        )
        # The reference to PROJECT_CONTEXT.md must appear after the Pre-Flight heading.
        context_idx = self._template_text.find("PROJECT_CONTEXT.md", preflight_idx)
        self.assertGreater(
            context_idx,
            preflight_idx,
            "PROJECT_CONTEXT.md must be referenced inside the Pre-Flight section of pull-request.md",
        )


class TestProjectContextFileExists(unittest.TestCase):
    """AC-5: .agents/agents/pull-request/PROJECT_CONTEXT.md must exist on disk."""

    def test_project_context_file_exists(self) -> None:
        """Project context file must be present at the expected repo-relative path (AC-5)."""
        self.assertTrue(
            _PROJECT_CONTEXT.exists(),
            f"Expected PROJECT_CONTEXT.md at {_PROJECT_CONTEXT} but file not found",
        )

    def test_project_context_file_is_not_empty(self) -> None:
        """Project context file must contain non-empty content."""
        self.assertGreater(
            _PROJECT_CONTEXT.stat().st_size,
            0,
            f"PROJECT_CONTEXT.md at {_PROJECT_CONTEXT} must not be empty",
        )


class TestProjectContextContent(unittest.TestCase):
    """AC-6: PROJECT_CONTEXT.md must contain EMU guard (urlmonitor) and title limit (70)."""

    def setUp(self) -> None:
        with _PROJECT_CONTEXT.open("r", encoding="utf-8") as f:
            self._context_text = f.read()

    def test_emu_guard_urlmonitor_present(self) -> None:
        """Context file must contain 'urlmonitor' for the EMU account guard (AC-2, AC-6)."""
        self.assertIn(
            "urlmonitor",
            self._context_text,
            "PROJECT_CONTEXT.md must contain 'urlmonitor' (EMU account guard instruction)",
        )

    def test_title_length_limit_70_present(self) -> None:
        """Context file must contain '70' for the PR title length limit (AC-3, AC-6)."""
        self.assertIn(
            "70",
            self._context_text,
            "PROJECT_CONTEXT.md must contain '70' (PR title length limit)",
        )

    def test_gh_auth_switch_instruction_present(self) -> None:
        """Context file must include gh auth switch instruction (AC-2)."""
        self.assertIn(
            "gh auth switch",
            self._context_text,
            "PROJECT_CONTEXT.md must contain 'gh auth switch' instruction for EMU guard",
        )

    def test_pr_summary_structure_present(self) -> None:
        """Context file must include the ## Summary / ## Test plan body structure (AC-3)."""
        self.assertIn(
            "## Summary",
            self._context_text,
            "PROJECT_CONTEXT.md must contain '## Summary' PR body structure",
        )
        self.assertIn(
            "## Test plan",
            self._context_text,
            "PROJECT_CONTEXT.md must contain '## Test plan' PR body structure",
        )


if __name__ == "__main__":
    unittest.main()
