"""
MODULE: unit_tests/test_link_feedback_resolve.py
GOAL: Failing test stubs for the resolve_feedback.py auto-call behaviour added to
      link_feedback.py by TICKET-20260603-AutoResolveFeedbackOnTicketCreate.
      Tests verify that when --ticket is supplied to link_feedback.py, it also
      calls resolve_feedback.py on the same feedback_id, and that --commit-only
      or --pr-only invocations do NOT call resolve_feedback.py.
BUSINESS CONTEXT: Prevents resolved feedback entries from surfacing as actionable
      noise in future review runs — once a ticket is created, the originating
      feedback entry must be automatically closed.
ARCHITECTURE: Not needed.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "feedback"))

import link_feedback  # noqa: E402 — path must be set before import


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_ENTRIES = [
    {
        "feedback_id": "fb_2026-06-03_aabbccdd",
        "timestamp": "2026-06-03T10:00:00Z",
        "phase": "python-coder",
        "category": "complete",
        "note": "Sample entry for auto-resolve tests",
        "source": "agent",
        "addressed_by": [],
    },
    {
        "feedback_id": "fb_2026-06-03_eeff1122",
        "timestamp": "2026-06-03T10:01:00Z",
        "phase": "test-runner",
        "category": "complete",
        "note": "Another sample entry",
        "source": "agent",
        "addressed_by": [],
    },
]


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    """Write entries to a JSONL file."""
    with open(path, "w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    """Read all entries from a JSONL file."""
    entries = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


# ---------------------------------------------------------------------------
# Test: --ticket triggers resolve_feedback.py call
# ---------------------------------------------------------------------------


class TestLinkFeedbackCallsResolve(unittest.TestCase):
    """When --ticket is supplied, link_feedback.py must also call resolve_feedback.py."""

    def test_ticket_flag_triggers_resolve_subprocess(self) -> None:
        """When --ticket is supplied and the feedback_id exists, resolve_feedback
        subprocess is called with the correct args.

        Expects link_feedback.main() to call subprocess.run (or equivalent) with
        resolve_feedback.py --feedback-id <id> --ticket <path> --jsonl <path>.
        This test will fail until the resolve_feedback call is added to link_feedback.py.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            jsonl_path = Path(tmp) / "feedback.jsonl"
            _write_jsonl(jsonl_path, _SAMPLE_ENTRIES)

            ticket_path = "tickets/00_inbox/TICKET-20260603-AutoResolveFeedbackOnTicketCreate.md"

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="resolved fb_2026-06-03_aabbccdd", stderr="")

                result = link_feedback.main([
                    "--feedback-id", "fb_2026-06-03_aabbccdd",
                    "--ticket", ticket_path,
                    "--jsonl", str(jsonl_path),
                ])

                self.assertEqual(result, 0, "link_feedback.main should return 0 on success")

                # Assert that subprocess.run was called with resolve_feedback.py args
                called = False
                for c in mock_run.call_args_list:
                    args = c[0][0] if c[0] else c[1].get("args", [])
                    if isinstance(args, list) and any("resolve_feedback.py" in str(a) for a in args):
                        called = True
                        # Check that --feedback-id and --ticket are present
                        self.assertIn("--feedback-id", args)
                        self.assertIn("fb_2026-06-03_aabbccdd", args)
                        self.assertIn("--ticket", args)
                        self.assertIn(ticket_path, args)
                        break

                self.assertTrue(
                    called,
                    "subprocess.run was not called with resolve_feedback.py when --ticket was supplied. "
                    "link_feedback.py must call resolve_feedback.py after writing the ref."
                )

    def test_commit_only_does_not_trigger_resolve(self) -> None:
        """When only --commit is supplied (no --ticket), resolve_feedback is NOT called.

        This test will fail until the conditional guard is added to link_feedback.py.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            jsonl_path = Path(tmp) / "feedback.jsonl"
            _write_jsonl(jsonl_path, _SAMPLE_ENTRIES)

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="resolved", stderr="")

                result = link_feedback.main([
                    "--feedback-id", "fb_2026-06-03_aabbccdd",
                    "--commit", "abc123def",
                    "--jsonl", str(jsonl_path),
                ])

                self.assertEqual(result, 0, "link_feedback.main should return 0 on success")

                # Assert that subprocess.run was NOT called with resolve_feedback.py args
                called_resolve = False
                for c in mock_run.call_args_list:
                    args = c[0][0] if c[0] else c[1].get("args", [])
                    if isinstance(args, list) and any("resolve_feedback.py" in str(a) for a in args):
                        called_resolve = True
                        break

                self.assertFalse(
                    called_resolve,
                    "subprocess.run must NOT be called with resolve_feedback.py for --commit-only invocations."
                )

    def test_pr_only_does_not_trigger_resolve(self) -> None:
        """When only --pr is supplied (no --ticket), resolve_feedback is NOT called.

        This test will fail until the conditional guard is added to link_feedback.py.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            jsonl_path = Path(tmp) / "feedback.jsonl"
            _write_jsonl(jsonl_path, _SAMPLE_ENTRIES)

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="resolved", stderr="")

                result = link_feedback.main([
                    "--feedback-id", "fb_2026-06-03_aabbccdd",
                    "--pr", "42",
                    "--jsonl", str(jsonl_path),
                ])

                self.assertEqual(result, 0, "link_feedback.main should return 0 on success")

                called_resolve = False
                for c in mock_run.call_args_list:
                    args = c[0][0] if c[0] else c[1].get("args", [])
                    if isinstance(args, list) and any("resolve_feedback.py" in str(a) for a in args):
                        called_resolve = True
                        break

                self.assertFalse(
                    called_resolve,
                    "subprocess.run must NOT be called with resolve_feedback.py for --pr-only invocations."
                )


# ---------------------------------------------------------------------------
# Test: resolve_feedback.py exit code 0 with "no-op" — link_feedback still exits 0
# ---------------------------------------------------------------------------


class TestLinkFeedbackResolveNoop(unittest.TestCase):
    """When resolve_feedback.py returns exit 0 with a no-op message, link_feedback still exits 0."""

    def test_resolve_noop_does_not_change_link_exit_code(self) -> None:
        """When resolve_feedback.py exits 0 with 'no-op' stdout, link_feedback.py still exits 0.

        This test will fail until the resolve_feedback call is added to link_feedback.py.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            jsonl_path = Path(tmp) / "feedback.jsonl"
            _write_jsonl(jsonl_path, _SAMPLE_ENTRIES)

            ticket_path = "tickets/00_inbox/TICKET-20260603-AutoResolveFeedbackOnTicketCreate.md"

            with patch("subprocess.run") as mock_run:
                # resolve_feedback.py returns no-op (already resolved)
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="no-op fb_2026-06-03_aabbccdd (already resolved at 2026-06-03T09:00:00Z)",
                    stderr=""
                )

                result = link_feedback.main([
                    "--feedback-id", "fb_2026-06-03_aabbccdd",
                    "--ticket", ticket_path,
                    "--jsonl", str(jsonl_path),
                ])

                self.assertEqual(
                    result, 0,
                    "link_feedback.main must exit 0 even when resolve_feedback returns a no-op."
                )


# ---------------------------------------------------------------------------
# Test: resolve_feedback.py raises OSError — link_feedback logs but still exits 0
# ---------------------------------------------------------------------------


class TestLinkFeedbackResolveOSError(unittest.TestCase):
    """When resolve_feedback.py raises an OSError, link_feedback logs to stderr but still exits 0."""

    def test_oserror_in_resolve_does_not_fail_link(self) -> None:
        """When resolve_feedback.py raises an OSError (binary not found / path error),
        link_feedback.py logs to stderr but still exits 0 for the linking step.

        This test will fail until the try/except OSError wrapper is added around
        the subprocess.run call in link_feedback.py.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            jsonl_path = Path(tmp) / "feedback.jsonl"
            _write_jsonl(jsonl_path, _SAMPLE_ENTRIES)

            ticket_path = "tickets/00_inbox/TICKET-20260603-AutoResolveFeedbackOnTicketCreate.md"

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = OSError("No such file or directory: 'python'")

                result = link_feedback.main([
                    "--feedback-id", "fb_2026-06-03_aabbccdd",
                    "--ticket", ticket_path,
                    "--jsonl", str(jsonl_path),
                ])

                # link_feedback must not propagate the OSError — it must catch it and log
                self.assertEqual(
                    result, 0,
                    "link_feedback.main must exit 0 even when subprocess.run raises OSError. "
                    "The resolve call is best-effort; linking success takes priority."
                )


if __name__ == "__main__":
    unittest.main()

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-06-03 [TICKET-20260603-AutoResolveFeedbackOnTicketCreate]: Initial test stubs.
#   Written by test-writer as red stubs: these tests will fail with AttributeError
#   or AssertionError until link_feedback.py is updated to call resolve_feedback.py
#   after writing the addressed_by ref when --ticket is supplied.
# ====================================================================
