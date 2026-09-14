"""
MODULE: unit_tests/commit_guardian/test_ge_123a_1.py
GOAL: GE-123a-1 — a file recognised by its sensitive filename (e.g. ".env")
    is ALSO read line by line for its contents. Today `scan_file` appends a
    single ENV_FILE finding for a sensitive filename match and RETURNS
    immediately, so the filename finding is the ONLY finding such a file can
    ever produce. This suite pins the fix: the filename finding and the four
    content-rule findings must be ADDITIVE, never exclusive.
BUSINESS CONTEXT: see GE-123 / GE-123a notes — five files whose names marked
    them as configuration, each carrying a cloud access key, a private-key
    header, a password assignment and a high-entropy token, produced ZERO
    reported problems with one suppression line in place; the identical
    content in an ordinary source file produced four. The cause is the
    return-on-filename-match short-circuit this AC removes.
ARCHITECTURE / EXERCISE STRATEGY: per GE-123a-1's it_requirements, every arm
    is driven through `scan_files` (the multi-file entry point the pre-commit
    secrets check calls) or the scanner's own CLI subprocess — never through
    `scan_file` or the filename matcher in isolation. `scan_files` and
    `Finding` are loaded from the canonical template copy via
    `importlib.util.spec_from_file_location` (ADR-001), matching the
    convention already established in
    unit_tests/commit_guardian/test_scan_secrets_suppression.py.

    Credential-shaped fixture content is assembled at runtime from
    concatenated fragments, never written as a source literal — matching the
    convention in test_scan_secrets_suppression.py
    (test_scan_files_reports_all_findings_with_malformed_allowlist) so this
    file needs no PRIVATE_KEY / AWS_KEY suppression of its own. The four
    values below are the SAME values already proven in that sibling test to
    produce exactly one finding per rule with no cross-triggering.

DECISION HISTORY
- 2026-09-07 [GE-123a-1/test-writer]: Initial authoring, written RED against
  the pre-fix `scan_file` short-circuit. test_env_named_file_reports_
  filename_finding_plus_four_content_findings and
  test_env_named_and_ordinary_file_report_the_same_content_findings are RED
  today (an env-named file currently yields exactly one finding — ENV_FILE —
  and zero content findings). test_cli_exit_status_reports_findings_for_
  the_two_file_run is SPLIT per the AC's own test_rationale: the non-zero
  exit-code half is GREEN on arrival (the ordinary .py fixture alone already
  produces four findings, so the run already exits non-zero), but the
  nine-findings-across-two-files assertion is RED today (current run
  produces five: one ENV_FILE + four content, from the .py file only).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import ClassVar

# The canonical template source — ADR-001: edit this copy only; build.py
# propagates to the deployed copies (.claude/, .gemini/, .leafcutter/,
# worktrees/**, etc.). Do NOT point this test at a deployed copy.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCAN_SECRETS = (
    _REPO_ROOT
    / "templates"
    / "skills"
    / "security-scanner"
    / "scripts"
    / "scan_secrets.py"
)


def _load_scan_secrets() -> ModuleType:
    """Load scan_secrets.py from the canonical template path via file spec.

    Returns:
        The loaded scan_secrets module object.
    """
    spec = importlib.util.spec_from_file_location(
        "scan_secrets_under_test_ge123a1", str(_SCAN_SECRETS)
    )
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _four_recognised_lines() -> str:
    """Build the four content lines the scanner's content rules recognise.

    Assembled at runtime from concatenated fragments (never a single source
    literal) so this test file itself never contains a full credential-shaped
    string check-secrets would flag. These are the same values already
    proven in test_scan_secrets_suppression.py to produce exactly one
    finding per rule (PRIVATE_KEY, AWS_KEY, GENERIC_SECRET, ENTROPY_HIGH)
    with no cross-triggering.

    Returns:
        The four-line fixture content, newline-terminated.
    """
    pem_header = "-----BEGIN RSA " + "PRIVATE KEY-----"
    aws_key = "AKIA" + "ABCDEFGHIJKLMNOP"
    secret_value = "hunter2" + "pass1"  # exactly twelve characters
    entropy_blob = "xK9vQ2mZ8pL5" + "nR3tW6yB1cF4"
    return (
        pem_header + "\n"
        + 'aws_access_key_id = "' + aws_key + '"\n'
        + 'password = "' + secret_value + '"\n'
        + 'blob_value = "' + entropy_blob + '"\n'
    )


_CONTENT_RULE_IDS = frozenset(
    {"PRIVATE_KEY", "AWS_KEY", "GENERIC_SECRET", "ENTROPY_HIGH"}
)


class TestEnvFilenameAddsToContentScan(unittest.TestCase):
    """GE-123a-1: filename recognition adds a finding, never replaces the
    content scan."""

    _mod: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        if not _SCAN_SECRETS.exists():
            raise FileNotFoundError(
                f"canonical template not found at {_SCAN_SECRETS}"
            )
        cls._mod = _load_scan_secrets()

    def test_env_named_file_reports_filename_finding_plus_four_content_findings(
        self,
    ):
        # covers: GE-123a-1
        # angle: criterion
        """Through scan_files over a real on-disk env-named fixture carrying

        the four recognised lines, exactly five findings are returned for
        that file — the filename rule plus one finding per content rule —
        all present in the same returned result.

        FAILS TODAY: the pre-fix per-file scan appends only the ENV_FILE
        finding and returns before any content rule runs, so this env-named
        fixture currently yields exactly one finding, not five.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_path = root / ".env"
            env_path.write_text(_four_recognised_lines(), encoding="utf-8")

            findings = self._mod.scan_files([env_path], project_root=root)

            rule_ids = [f.rule_id for f in findings]
            self.assertEqual(
                len(findings),
                5,
                msg=f"expected 5 findings (filename + 4 content), got {rule_ids!r}",
            )
            self.assertEqual(
                set(rule_ids),
                {"ENV_FILE"} | _CONTENT_RULE_IDS,
                msg=f"expected filename rule plus all four content rules, got {rule_ids!r}",
            )

    def test_env_named_and_ordinary_file_report_the_same_content_findings(
        self,
    ):
        # covers: GE-123a-1
        # angle: criterion
        """An env-named fixture and an ordinary .py fixture holding

        byte-identical content are scanned in one scan_files call; the set
        of content-rule ids reported is equal for both files and the only
        difference is the extra filename finding on the env-named one.

        FAILS TODAY: the env-named fixture's content-rule set is empty
        (short-circuited before any content rule runs) while the ordinary
        fixture's is the full four-rule set — they are not equal.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = _four_recognised_lines()
            env_path = root / ".env"
            env_path.write_text(content, encoding="utf-8")
            ordinary_path = root / "secrets.py"
            ordinary_path.write_text(content, encoding="utf-8")

            findings = self._mod.scan_files(
                [env_path, ordinary_path], project_root=root
            )

            env_rule_ids = {
                f.rule_id for f in findings if f.file_path == str(env_path)
            }
            ordinary_rule_ids = {
                f.rule_id for f in findings if f.file_path == str(ordinary_path)
            }

            env_content_rule_ids = env_rule_ids - {"ENV_FILE"}
            self.assertEqual(
                env_content_rule_ids,
                ordinary_rule_ids,
                msg=(
                    "content-rule findings must be identical for the "
                    f"env-named file ({env_content_rule_ids!r}) and the "
                    f"ordinary file ({ordinary_rule_ids!r})"
                ),
            )
            self.assertIn(
                "ENV_FILE",
                env_rule_ids,
                msg="the env-named file must still carry its filename finding",
            )
            self.assertNotIn(
                "ENV_FILE",
                ordinary_rule_ids,
                msg="the ordinary file must never carry a filename finding",
            )

    def test_cli_exit_status_reports_findings_for_the_two_file_run(self):
        # covers: GE-123a-1
        # angle: reachability
        """The scanner CLI, run in a fresh subprocess with the fixture

        directory as its working directory, exits non-zero over the same
        two fixtures and its report accounts for nine findings across the
        two files.

        SPLIT per the AC's test_rationale: the non-zero exit-code assertion
        is green on arrival (the ordinary .py file alone already produces
        four findings). The nine-findings assertion is RED today — the
        current run reports five (one ENV_FILE + four content, from the
        ordinary file only), not nine.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = _four_recognised_lines()
            env_path = root / ".env"
            env_path.write_text(content, encoding="utf-8")
            ordinary_path = root / "secrets.py"
            ordinary_path.write_text(content, encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(_SCAN_SECRETS), str(env_path), str(ordinary_path)],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertNotEqual(
                result.returncode,
                0,
                msg=f"expected non-zero exit; stdout={result.stdout!r}",
            )
            self.assertIn(
                "9 secret(s) detected",
                result.stdout,
                msg=(
                    "expected the run to account for nine findings across "
                    f"the two files; got stdout={result.stdout!r}"
                ),
            )


if __name__ == "__main__":
    unittest.main()
