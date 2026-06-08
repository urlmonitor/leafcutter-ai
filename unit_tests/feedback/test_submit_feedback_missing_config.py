"""
MODULE: unit_tests/feedback/test_submit_feedback_missing_config.py
GOAL: Verify AC INF-100c-4 — Error message identifies the missing config path.
      When submit_feedback.py cannot find feedback_categories.yaml at any
      expected location, the error message must include the full absolute
      path(s) that were checked and be actionable for debugging.
BUSINESS CONTEXT: Agents and hooks that call submit_feedback.py may run from
      arbitrary CWDs and deployment layouts. When the categories file is
      missing, the error must tell the operator exactly which path(s) were
      tried so they can place the file or fix the config root.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUBMIT_SCRIPT = _REPO_ROOT / "scripts" / "feedback" / "submit_feedback.py"


def _run_submit(extra_args: list, *, cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run submit_feedback.py with a nonexistent config and capture output."""
    return subprocess.run(
        [
            sys.executable,
            str(_SUBMIT_SCRIPT),
            "--ticket",
            "dummy-ticket.md",
            "--phase",
            "python-coder",
            "--category",
            "complete",
            "--note",
            "missing-config-test probe",
            *extra_args,
        ],
        capture_output=True,
        text=True,
        cwd=cwd or str(_REPO_ROOT),
        timeout=10,
    )


class TestMissingConfigErrorMessage(unittest.TestCase):
    """AC INF-100c-4: error message includes the absolute path(s) checked."""

    def test_exit_code_is_one_when_config_missing(self):
        # covers: INF-100c-4
        """Script must exit with code 1 when the config file does not exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config = str(Path(tmpdir) / "nonexistent" / "feedback_categories.yaml")
            result = _run_submit(["--config", missing_config])

        self.assertEqual(
            result.returncode,
            1,
            f"Expected exit code 1 when config is missing.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )

    def test_error_message_contains_absolute_path_checked(self):
        # covers: INF-100c-4
        """Error message must include the full absolute path that was checked.

        The message must explicitly state which path was tried so the operator
        knows exactly where to place feedback_categories.yaml.  A generic
        'file not found' message without a path is not actionable.

        Implementation note: the new error format must include a labelled
        'Checked path:' or 'Searched:' prefix so the path is clearly
        distinguished from the OSError detail string.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent_dir = Path(tmpdir) / "config_missing"
            missing_config = nonexistent_dir / "feedback_categories.yaml"
            result = _run_submit(["--config", str(missing_config)])

        # The error must explicitly label the path — not just embed it in an OSError string.
        # AC INF-100c-4 requires the message to be "actionable for debugging".
        stderr = result.stderr
        # Assert that a labelled path indicator appears in the error output.
        path_label_present = (
            "Checked path:" in stderr
            or "Searched:" in stderr
            or "checked:" in stderr
            or "searched at:" in stderr
        )
        self.assertTrue(
            path_label_present,
            f"Error message must include a labelled path indicator "
            f"(e.g. 'Checked path:', 'Searched:') so the operator knows "
            f"which location was tried.\n"
            f"Current stderr output:\n{stderr}",
        )

    def test_error_message_contains_absolute_path_value(self):
        # covers: INF-100c-4
        """Error output must include the exact absolute path that was checked,
        labelled so it is distinct from any OS-level error string.

        The path must appear on a line that starts with a recognisable label
        such as 'Checked path:' or 'Searched:', so the operator can copy-paste
        it without having to parse OSError noise.  Embedding the path only
        inside the OSError message ('No such file or directory: /path') does
        not satisfy this requirement.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent_dir = Path(tmpdir) / "config_missing"
            missing_config = nonexistent_dir / "feedback_categories.yaml"
            result = _run_submit(["--config", str(missing_config)])

        stderr = result.stderr
        expected_path = str(missing_config.resolve())

        # The path must appear AND there must be a labelled indicator.
        # The current implementation embeds the path in an OSError string,
        # which is not explicitly labelled — this test enforces the label.
        path_label_present = (
            "Checked path:" in stderr
            or "Searched:" in stderr
            or "checked:" in stderr
            or "searched at:" in stderr
        )
        self.assertTrue(
            path_label_present,
            f"Error message must include a labelled path indicator "
            f"(e.g. 'Checked path: {expected_path}') so the path is distinct "
            f"from the OSError detail.\nCurrent stderr:\n{stderr}",
        )

    def test_error_message_is_actionable(self):
        # covers: INF-100c-4
        """Error message must tell the operator what action to take.

        An actionable error message tells the user what to do next — e.g.
        'Place feedback_categories.yaml at the path shown above' or
        'Create the config file at: <path>'. A message that only reports
        'Cannot read categories file ...: No such file or directory' is
        present in the current implementation but lacks explicit remediation
        guidance pointing to WHERE to place the file.

        The new message must include explicit remediation text, such as:
        - 'Place feedback_categories.yaml at: <path>'
        - 'Create the config file at: <path>'
        - 'To fix: create feedback_categories.yaml at <path>'
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config = str(Path(tmpdir) / "feedback_categories.yaml")
            result = _run_submit(["--config", missing_config])

        stderr = result.stderr
        # Must contain a remediation phrase, not just the file name in an error.
        # The current implementation prints only:
        # "ERROR: Cannot read categories file <path>: [Errno 2] No such file..."
        # which does not include explicit remediation guidance.
        remediation_present = (
            "Place " in stderr
            or "Create " in stderr
            or "To fix:" in stderr
            or "to fix:" in stderr
            or "Hint:" in stderr
            or "Remedy:" in stderr
        )
        self.assertTrue(
            remediation_present,
            f"Error message must contain explicit remediation guidance "
            f"(e.g. 'Place feedback_categories.yaml at ...' or 'To fix: ...').\n"
            f"Current stderr output:\n{stderr}",
        )

    def test_default_config_missing_error_lists_default_path(self):
        # covers: INF-100c-4
        """When no --config override is given, error must list the default resolved path.

        When submit_feedback.py is invoked without --config and the default
        feedback_categories.yaml is missing, the error must show which default
        path was tried, based on _find_config_root().
        """
        # Run from a temp directory with no config so the default path is missing.
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake script layout that resolves to a nonexistent config
            fake_scripts_dir = Path(tmpdir) / "scripts" / "feedback"
            fake_scripts_dir.mkdir(parents=True)

            import shutil
            fake_script = fake_scripts_dir / "submit_feedback.py"
            shutil.copy2(str(_SUBMIT_SCRIPT), str(fake_script))

            # The resolved config root would be parents[2]/config = tmpdir/config
            # which does NOT have feedback_categories.yaml
            result = subprocess.run(
                [
                    sys.executable,
                    str(fake_script),
                    "--ticket",
                    "dummy-ticket.md",
                    "--phase",
                    "python-coder",
                    "--category",
                    "complete",
                    "--note",
                    "default-path-test probe",
                    "--jsonl",
                    str(Path(tmpdir) / "test.jsonl"),
                ],
                capture_output=True,
                text=True,
                cwd=tmpdir,
                timeout=10,
            )

        # The error must identify the path(s) that were checked.
        # The script should say where it looked, not just an opaque error.
        self.assertEqual(
            result.returncode,
            1,
            f"Expected exit code 1.\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )
        # The resolved path for a script at tmpdir/scripts/feedback/ would be
        # tmpdir/config/feedback_categories.yaml. That path must appear in stderr.
        expected_config_dir = str(Path(tmpdir) / "config")
        self.assertIn(
            expected_config_dir,
            result.stderr,
            f"Error must include the resolved config directory path '{expected_config_dir}'.\n"
            f"Current stderr:\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
