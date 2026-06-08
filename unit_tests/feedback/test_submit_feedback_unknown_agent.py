"""
MODULE: unit_tests/feedback/test_submit_feedback_unknown_agent.py
GOAL: Verify AC INF-100c-3-i — Unknown agent is still rejected with a clear error.
      When an agent name that is not listed in any allowed_writers list attempts
      to submit feedback, the submission must be rejected and the error message
      must name both the agent and the category it attempted to write to.
BUSINESS CONTEXT: The allowed_writers lists in feedback_categories.yaml enumerate
      every standard phase agent. An unrecognised agent id (e.g. a typo, a
      retired agent, or a probing script) must be refused at the validation
      chokepoint in submit_feedback.py with an error message that is actionable:
      the operator must be able to see which agent was rejected and for which
      category without inspecting the source.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUBMIT_SCRIPT = _REPO_ROOT / "scripts" / "feedback" / "submit_feedback.py"


def _run_submit(
    phase: str,
    category: str,
    jsonl_path: Path,
    ticket: str = "tickets/00_inbox/TICKET-20260608-INF-100c-3-i.md",
) -> subprocess.CompletedProcess:
    """Run submit_feedback.py and return the CompletedProcess."""
    return subprocess.run(
        [
            sys.executable,
            str(_SUBMIT_SCRIPT),
            "--ticket", ticket,
            "--phase", phase,
            "--category", category,
            "--note", "unknown-agent rejection test probe",
            "--jsonl", str(jsonl_path),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(_REPO_ROOT),
    )


# ---------------------------------------------------------------------------
# Tests — rejection
# ---------------------------------------------------------------------------


class TestUnknownAgentRejected:
    """AC INF-100c-3-i: unknown agent is rejected with an error naming agent + category."""

    def test_unknown_agent_exits_nonzero(self, tmp_path: Path) -> None:
        """submit_feedback.py must exit with a non-zero code when phase is unknown.

        Covers: INF-100c-3-i (rejection gate).
        """
        # covers: INF-100c-3-i
        jsonl_path = tmp_path / "feedback.jsonl"
        result = _run_submit("ghost-agent", "complete", jsonl_path)
        assert result.returncode != 0, (
            "Expected non-zero exit when phase='ghost-agent' is not in allowed_writers, "
            f"got returncode={result.returncode}. stderr={result.stderr!r}"
        )

    def test_error_message_names_the_agent(self, tmp_path: Path) -> None:
        """The rejection error message must name the unknown agent.

        Covers: INF-100c-3-i (error names agent).
        """
        # covers: INF-100c-3-i
        jsonl_path = tmp_path / "feedback.jsonl"
        unknown_agent = "ghost-agent"
        result = _run_submit(unknown_agent, "complete", jsonl_path)
        assert result.returncode != 0
        assert unknown_agent in result.stderr, (
            f"Expected the agent name '{unknown_agent}' to appear in the error message. "
            f"stderr={result.stderr!r}"
        )

    def test_error_message_names_the_category(self, tmp_path: Path) -> None:
        """The rejection error message must name the category the agent attempted to write.

        Covers: INF-100c-3-i (error names category).
        """
        # covers: INF-100c-3-i
        jsonl_path = tmp_path / "feedback.jsonl"
        category = "complete"
        result = _run_submit("ghost-agent", category, jsonl_path)
        assert result.returncode != 0
        assert category in result.stderr, (
            f"Expected the category name '{category}' to appear in the error message. "
            f"stderr={result.stderr!r}"
        )

    def test_error_message_names_both_agent_and_category(self, tmp_path: Path) -> None:
        """The rejection error message must name both the agent and the category.

        This is the primary acceptance test for INF-100c-3-i.
        Covers: INF-100c-3-i.
        """
        # covers: INF-100c-3-i
        jsonl_path = tmp_path / "feedback.jsonl"
        unknown_agent = "rogue-script"
        category = "knowledge-gap"
        result = _run_submit(unknown_agent, category, jsonl_path)
        assert result.returncode != 0, (
            f"Expected rejection for unknown agent '{unknown_agent}', "
            f"got returncode=0. stdout={result.stdout!r}"
        )
        assert unknown_agent in result.stderr, (
            f"Agent name '{unknown_agent}' missing from error message. "
            f"stderr={result.stderr!r}"
        )
        assert category in result.stderr, (
            f"Category name '{category}' missing from error message. "
            f"stderr={result.stderr!r}"
        )

    def test_no_jsonl_entry_written_on_rejection(self, tmp_path: Path) -> None:
        """A rejected submission must not write any entry to the feedback JSONL.

        Covers: INF-100c-3-i (rejection is complete — no partial write).
        """
        # covers: INF-100c-3-i
        jsonl_path = tmp_path / "feedback.jsonl"
        result = _run_submit("ghost-agent", "complete", jsonl_path)
        assert result.returncode != 0
        assert not jsonl_path.exists() or jsonl_path.read_text(encoding="utf-8").strip() == "", (
            "Expected no JSONL entry on rejection, but feedback.jsonl has content: "
            f"{jsonl_path.read_text(encoding='utf-8')!r}"
        )

    def test_no_feedback_id_on_stdout_on_rejection(self, tmp_path: Path) -> None:
        """A rejected submission must not print a feedback_id to stdout.

        Covers: INF-100c-3-i (rejection is clean — no false success signal).
        """
        # covers: INF-100c-3-i
        jsonl_path = tmp_path / "feedback.jsonl"
        result = _run_submit("ghost-agent", "complete", jsonl_path)
        assert result.returncode != 0
        stdout = result.stdout.strip()
        assert not stdout, (
            f"Expected empty stdout on rejection, got: {stdout!r}"
        )

    def test_rejection_consistent_across_all_categories(self, tmp_path: Path) -> None:
        """An unknown agent must be rejected for every category, not just some.

        Covers: INF-100c-3-i (rejection applies to all categories).
        """
        # covers: INF-100c-3-i
        unknown_agent = "mystery-agent"
        # Sample a cross-section of categories that allow broad writers.
        categories = ["complete", "knowledge-gap", "tooling-issue", "success-pattern"]
        for category in categories:
            jsonl_path = tmp_path / f"feedback_{category}.jsonl"
            result = _run_submit(unknown_agent, category, jsonl_path)
            assert result.returncode != 0, (
                f"Expected rejection for unknown agent '{unknown_agent}' "
                f"on category '{category}', but got returncode=0."
            )
            assert unknown_agent in result.stderr, (
                f"Agent name '{unknown_agent}' missing from error for category '{category}'."
            )
            assert category in result.stderr, (
                f"Category name '{category}' missing from error for category '{category}'."
            )

    def test_typo_agent_name_is_rejected(self, tmp_path: Path) -> None:
        """A slight typo in an agent name (e.g. 'pytohn-coder') must be rejected.

        This guards against partial-match logic that could accidentally allow
        near-miss names. Only exact matches in allowed_writers should pass.
        Covers: INF-100c-3-i.
        """
        # covers: INF-100c-3-i
        jsonl_path = tmp_path / "feedback.jsonl"
        typo_agent = "pytohn-coder"  # intentional typo of python-coder
        category = "complete"
        result = _run_submit(typo_agent, category, jsonl_path)
        assert result.returncode != 0, (
            f"Expected rejection for typo agent '{typo_agent}', "
            f"got returncode=0. stdout={result.stdout!r}"
        )
        assert typo_agent in result.stderr, (
            f"Typo agent name '{typo_agent}' missing from rejection error. "
            f"stderr={result.stderr!r}"
        )

    def test_hook_source_bypasses_writer_check(self, tmp_path: Path) -> None:
        """When --source hook is used, the writer check is bypassed (hook writers are allowed).

        This is a negative-space test: confirms hook mode is not affected by
        the agent allowed_writers check. Covers: INF-100c-3-i boundary condition.
        """
        # covers: INF-100c-3-i (boundary — hook mode is exempt)
        jsonl_path = tmp_path / "feedback.jsonl"
        result = subprocess.run(
            [
                sys.executable,
                str(_SUBMIT_SCRIPT),
                "--phase", "check_contract_shrinking",
                "--source", "hook",
                "--hook-name", "check_contract_shrinking",
                "--outcome", "warn",
                "--category", "process-finding",
                "--note", "hook-mode bypass test",
                "--jsonl", str(jsonl_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(_REPO_ROOT),
        )
        assert result.returncode == 0, (
            "Expected hook-mode submission to succeed (writer check bypassed). "
            f"stderr={result.stderr!r}"
        )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-06-08 [python-coder/EPIC-FeedbackPortability/03_TICKET-20260608-INF-100c-3-i]:
#   Initial test suite for AC INF-100c-3-i: unknown agent rejection with clear error.
#   Tests: exit code non-zero, error names agent, error names category, both together,
#   no JSONL entry on rejection, no stdout feedback_id on rejection, rejection across all
#   categories, typo detection, and hook-mode bypass (boundary condition).
#   The implementation in _validate_writer already satisfies the AC; these tests
#   document and guard the behaviour. (#EPIC-FeedbackPortability)
# ====================================================================
