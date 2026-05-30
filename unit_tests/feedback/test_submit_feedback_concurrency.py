"""
MODULE: unit_tests/feedback/test_submit_feedback_concurrency.py
GOAL: Verify that submit_feedback.py is atomic under concurrent invocations:
      no partial writes, no lost correlation IDs, sidecar file written on
      success, and sidecar path printed to stderr for fallback recovery.
BUSINESS CONTEXT: Under batch-parallel epic drives, 3 of 26 feedback events
      previously lost their correlation IDs due to a race condition in
      submit_feedback.py. These tests validate the fix (fcntl.flock advisory
      lock + sidecar temp file) introduced by TICKET-20260528-FeedbackCorrelationIDLoss.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUBMIT_SCRIPT = _REPO_ROOT / "scripts" / "feedback" / "submit_feedback.py"

# Minimal valid CLI arguments for submit_feedback.py
_BASE_ARGS = [
    sys.executable,
    str(_SUBMIT_SCRIPT),
    "--ticket", "tickets/00_inbox/TICKET-20260528-FeedbackCorrelationIDLoss.md",
    "--phase", "test-writer",
    "--category", "complete",
    "--note", "concurrency test probe",
]


def _run_submit(jsonl_path: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    """Run submit_feedback.py synchronously and return the CompletedProcess."""
    args = _BASE_ARGS + ["--jsonl", str(jsonl_path)]
    if extra_args:
        args += extra_args
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(_REPO_ROOT),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestConcurrentWrites:
    """Tests for concurrent invocations of submit_feedback.py."""

    def test_concurrent_writes_produce_no_partial_entries(self, tmp_path: Path) -> None:
        """5 concurrent writes must each produce a valid, complete JSONL entry."""
        jsonl_path = tmp_path / "feedback.jsonl"
        n = 5

        # Spawn N processes simultaneously
        procs = [
            subprocess.Popen(
                _BASE_ARGS + ["--jsonl", str(jsonl_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(_REPO_ROOT),
            )
            for _ in range(n)
        ]

        # Wait for all to complete
        results = [p.communicate(timeout=30) for p in procs]

        # Verify all processes exited cleanly
        for i, (proc, (stdout, stderr)) in enumerate(zip(procs, results)):
            assert proc.returncode == 0, (
                f"Process {i} exited {proc.returncode}: stderr={stderr!r}"
            )

        # Read and parse every JSONL line
        assert jsonl_path.exists(), "feedback.jsonl was not created"
        lines = jsonl_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == n, (
            f"Expected {n} JSONL lines, got {len(lines)}: {lines!r}"
        )

        for idx, line in enumerate(lines):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                pytest.fail(f"Line {idx} is not valid JSON: {exc}\nLine: {line!r}")

            assert "feedback_id" in entry, f"Line {idx} missing 'feedback_id': {entry!r}"
            assert entry["feedback_id"], f"Line {idx} has empty 'feedback_id': {entry!r}"

    def test_no_submit_failed_sentinel_under_load(self, tmp_path: Path) -> None:
        """5 concurrent invocations must each return a non-empty feedback_id on stdout."""
        jsonl_path = tmp_path / "feedback.jsonl"
        n = 5

        procs = [
            subprocess.Popen(
                _BASE_ARGS + ["--jsonl", str(jsonl_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(_REPO_ROOT),
            )
            for _ in range(n)
        ]

        results = [p.communicate(timeout=30) for p in procs]

        for i, (proc, (stdout, stderr)) in enumerate(zip(procs, results)):
            assert proc.returncode == 0, (
                f"Process {i} exited {proc.returncode}: stderr={stderr!r}"
            )
            captured_id = stdout.strip()
            assert captured_id, (
                f"Process {i} produced empty stdout — feedback_id was lost. stderr={stderr!r}"
            )
            assert captured_id != "(submit-failed)", (
                f"Process {i} captured the (submit-failed) sentinel instead of a real ID"
            )
            assert re.match(r"^fb_\d{4}-\d{2}-\d{2}_[0-9a-f]{8}$", captured_id), (
                f"Process {i} stdout does not look like a valid feedback_id: {captured_id!r}"
            )


class TestSidecarFile:
    """Tests for the sidecar temp-file written on successful submission."""

    def test_sidecar_file_written_on_success(self, tmp_path: Path) -> None:
        """A single successful invocation must produce a sidecar .txt file in tempdir."""
        jsonl_path = tmp_path / "feedback.jsonl"
        result = _run_submit(jsonl_path)

        assert result.returncode == 0, (
            f"submit_feedback.py exited {result.returncode}: stderr={result.stderr!r}"
        )

        feedback_id = result.stdout.strip()
        assert feedback_id, "stdout was empty — no feedback_id returned"

        # The sidecar path is printed to stderr as: sidecar:<path>/feedback_id_<epoch>.txt
        stderr_text = result.stderr
        sidecar_match = re.search(r"sidecar:(.+/feedback_id_\d+\.txt)", stderr_text)
        assert sidecar_match, (
            f"Expected sidecar path in stderr but found none. stderr={stderr_text!r}"
        )

        sidecar_path = Path(sidecar_match.group(1))
        assert sidecar_path.exists(), (
            f"Sidecar file {sidecar_path} does not exist after successful run"
        )

        sidecar_content = sidecar_path.read_text(encoding="utf-8").strip()
        assert sidecar_content == feedback_id, (
            f"Sidecar content {sidecar_content!r} does not match stdout feedback_id {feedback_id!r}"
        )

    def test_sidecar_path_printed_to_stderr(self, tmp_path: Path) -> None:
        """The sidecar file path must appear on stderr and resolve to an existing file."""
        jsonl_path = tmp_path / "feedback.jsonl"
        result = _run_submit(jsonl_path)

        assert result.returncode == 0, (
            f"submit_feedback.py exited {result.returncode}: stderr={result.stderr!r}"
        )

        stderr_text = result.stderr
        # Expect a line like: sidecar:<tempdir>/feedback_id_1234567890.txt
        sidecar_match = re.search(r"sidecar:(.+/feedback_id_\d+\.txt)", stderr_text)
        assert sidecar_match, (
            f"Expected a sidecar path ending in .txt in stderr. stderr={stderr_text!r}"
        )

        sidecar_path = Path(sidecar_match.group(1))
        assert sidecar_path.exists(), (
            f"Sidecar path {sidecar_path} found in stderr but file does not exist"
        )
        assert sidecar_path.suffix == ".txt", (
            f"Sidecar path {sidecar_path} does not end in .txt"
        )

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-30 [test-writer/TICKET-20260528-FeedbackCorrelationIDLoss]:
#   Initial test suite for submit_feedback.py concurrency fix.
#   Tests cover: 5-concurrent writes (no partial entries), no (submit-failed)
#   sentinel under load, sidecar file creation, and sidecar path on stderr.
#   Platform: WSL2/Linux (fcntl-based locking is safe; Windows fallback is
#   lower priority per ticket Risk & Safety section).
# ====================================================================
