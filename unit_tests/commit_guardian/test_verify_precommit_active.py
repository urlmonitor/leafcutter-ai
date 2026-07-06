"""
MODULE: test_verify_precommit_active
GOAL: TDD red-baseline tests for scripts/commit_guardian/verify_precommit_active.py
BUSINESS CONTEXT: The probe orchestrates four checks (A/B/C/D), emits structured
    JSON {binary, config, git_hook, canary, failing_checks}, exits 0 on all-pass
    and non-zero on any failure.  Fail-closed: uncaught exception or timeout also
    produces a non-zero exit.  All tests are RED until the module is implemented.
ARCHITECTURE: Import-based tests exercise run_checks() via mocks so no live
    pre-commit installation is required.  Subprocess-based tests exercise the CLI
    entry point by controlling PATH and cwd.

====================================================================
DECISION HISTORY
====================================================================
- 2026-07-06 [EPIC-WorktreeQualityGateGuard/02]: Initial TDD red-baseline.
  Tests are written BEFORE verify_precommit_active.py exists.
  Expected RED states:
    - ImportError when module missing (import-based tests).
    - JSONDecodeError / self.fail() when script missing (subprocess tests).
====================================================================
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "commit_guardian" / "verify_precommit_active.py"

EXPECTED_JSON_KEYS = frozenset({"binary", "config", "git_hook", "canary", "failing_checks"})

# ---------------------------------------------------------------------------
# Module import (will fail with ModuleNotFoundError until implemented — RED)
# ---------------------------------------------------------------------------

try:
    import scripts.commit_guardian.verify_precommit_active as _vpa  # type: ignore[import]
    _IMPORT_OK = True
except (ImportError, ModuleNotFoundError):
    _vpa = None  # type: ignore[assignment]
    _IMPORT_OK = False


# ---------------------------------------------------------------------------
# Subprocess helper
# ---------------------------------------------------------------------------


def _run_probe(env_override=None, cwd=None, extra_args=None):
    """Invoke verify_precommit_active.py as a subprocess.

    Args:
        env_override: Dict of env-var overrides; ``None`` values delete the key.
        cwd: Working directory for the subprocess.
        extra_args: Additional CLI arguments appended after the script path.

    Returns:
        ``subprocess.CompletedProcess`` with stdout/stderr captured.
    """
    env = os.environ.copy()
    if env_override:
        for k, v in env_override.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
    cmd = [sys.executable, str(_SCRIPT)]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=str(cwd) if cwd else None,
    )


def _json_or_fail(test_case: unittest.TestCase, result: subprocess.CompletedProcess) -> dict:
    """Parse result.stdout as JSON, or call test_case.fail() with a diagnostic.

    Args:
        test_case: The active unittest.TestCase (provides .fail()).
        result: CompletedProcess from _run_probe().

    Returns:
        Parsed JSON dict.
    """
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        test_case.fail(
            f"Expected valid JSON on stdout from verify_precommit_active.py — "
            f"script at {_SCRIPT} may not exist yet (TDD red-baseline). "
            f"returncode={result.returncode} "
            f"stdout={result.stdout!r} "
            f"stderr={result.stderr!r}"
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestJsonOutputStructure(unittest.TestCase):
    """Output must be a JSON dict with the canonical five keys."""

    def test_json_output_structure(self):
        # covers: UNKNOWN
        """Output has exactly the required keys: binary, config, git_hook, canary, failing_checks.

        Must implement a run_checks() function (and main() that serialises its
        return value as JSON to stdout) to pass this test.
        """
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import scripts.commit_guardian.verify_precommit_active. "
                "Implement the module so run_checks() is importable and callable."
            )
        if not hasattr(_vpa, "run_checks"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose run_checks(). "
                "Add a public run_checks() function that returns the five-key result dict."
            )


class TestAllChecksPass(unittest.TestCase):
    """When all four checks return True, run_checks() reflects that."""

    def test_all_checks_pass(self):
        # covers: UNKNOWN
        """All four checks pass → result dict has binary/config/git_hook/canary all True,
        failing_checks is an empty list.

        Implement run_checks() to call the four check functions and aggregate their
        results.  The mock below patches the four check callables on the module.
        """
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import scripts.commit_guardian.verify_precommit_active. "
                "Implement the module first."
            )
        if not hasattr(_vpa, "run_checks"):
            self.fail(
                "AttributeError: verify_precommit_active has no run_checks(). "
                "Implement this function."
            )
        # Patch the four check callables by name — coder must expose them as
        # module-level callables with these names (or adjust the test).
        for attr in ("check_a_binary_on_path", "check_b_config",
                     "check_c_git_hook", "check_d_canary"):
            if not hasattr(_vpa, attr):
                self.fail(
                    f"AttributeError: verify_precommit_active does not expose {attr}(). "
                    f"Implement this check function or adjust the test to match the "
                    f"actual internal function names."
                )
        with (
            patch.object(_vpa, "check_a_binary_on_path", return_value=True),
            patch.object(_vpa, "check_b_config", return_value=True),
            patch.object(_vpa, "check_c_git_hook", return_value=True),
            patch.object(_vpa, "check_d_canary", return_value=True),
        ):
            result = _vpa.run_checks()
        for key in ("binary", "config", "git_hook", "canary"):
            self.assertTrue(
                result.get(key),
                msg=f"Expected result['{key}'] True when all checks pass. Got: {result}",
            )
        self.assertEqual(
            result.get("failing_checks"),
            [],
            msg=f"Expected failing_checks == [] when all checks pass. Got: {result}",
        )


class TestCheckAFailsBinaryNotFound(unittest.TestCase):
    """Check A: pre-commit binary absent on PATH → check A reports False."""

    def test_check_a_fails_binary_not_found(self):
        # covers: UNKNOWN
        """Running with an empty PATH means pre-commit is not found.
        The probe must exit non-zero and report binary: false in JSON output.
        """
        result = _run_probe(env_override={"PATH": ""})
        output = _json_or_fail(self, result)
        self.assertFalse(
            output.get("binary"),
            msg=f"Expected binary: false when PATH=''. Got: {output}",
        )
        self.assertIn(
            "binary",
            output.get("failing_checks", []),
            msg=f"Expected 'binary' in failing_checks. Got: {output}",
        )
        self.assertNotEqual(
            result.returncode,
            0,
            msg=f"Expected non-zero exit when check A fails. Got: {result.returncode}",
        )


class TestCheckBFailsConfigNotFound(unittest.TestCase):
    """Check B: no .pre-commit-config.yaml → check B reports False."""

    def test_check_b_fails_config_not_found(self):
        # covers: UNKNOWN
        """Running in a temp directory with no .leafcutter symlink and no
        .pre-commit-config.yaml causes check B to fail.

        Probe must exit non-zero and report config: false.
        """
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_probe(cwd=tmp)
        output = _json_or_fail(self, result)
        self.assertFalse(
            output.get("config"),
            msg=f"Expected config: false when .pre-commit-config.yaml is absent. Got: {output}",
        )
        self.assertIn(
            "config",
            output.get("failing_checks", []),
            msg=f"Expected 'config' in failing_checks. Got: {output}",
        )
        self.assertNotEqual(
            result.returncode,
            0,
            msg=f"Expected non-zero exit when check B fails (config absent). Got: {result.returncode}",
        )


class TestCheckBFailsConfigInvalidYaml(unittest.TestCase):
    """Check B: config file exists but contains invalid YAML → check B reports False."""

    def test_check_b_fails_config_invalid_yaml(self):
        # covers: UNKNOWN
        """A .pre-commit-config.yaml whose content is not valid YAML must cause
        check B to fail.  Probe exits non-zero with config: false in JSON.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Write invalid YAML directly to .pre-commit-config.yaml
            # (simulates the resolved path without a .leafcutter symlink)
            invalid_yaml = ": : { unbalanced: [ brackets"
            (tmp_path / ".pre-commit-config.yaml").write_text(
                invalid_yaml, encoding="utf-8"
            )
            result = _run_probe(cwd=tmp)
        output = _json_or_fail(self, result)
        self.assertFalse(
            output.get("config"),
            msg=f"Expected config: false when .pre-commit-config.yaml is invalid YAML. Got: {output}",
        )
        self.assertIn(
            "config",
            output.get("failing_checks", []),
            msg=f"Expected 'config' in failing_checks. Got: {output}",
        )
        self.assertNotEqual(
            result.returncode,
            0,
            msg=f"Expected non-zero exit when check B fails (invalid YAML). Got: {result.returncode}",
        )


class TestCheckCFailsHookMissingSentinel(unittest.TestCase):
    """Check C: git hook file exists but lacks the pre-commit sentinel → check C fails."""

    def test_check_c_fails_hook_missing_sentinel(self):
        # covers: UNKNOWN
        """Check C reads the shared git hook and looks for a pre-commit sentinel.
        When the hook file exists but the sentinel string is absent, check C must
        report git_hook: false.

        This test patches the module-level hook-reading function to return a hook
        body without the expected sentinel text.
        """
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import verify_precommit_active. "
                "Implement the module first."
            )
        if not hasattr(_vpa, "check_c_git_hook"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose check_c_git_hook(). "
                "Implement this check function."
            )
        if not hasattr(_vpa, "run_checks"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose run_checks(). "
                "Implement run_checks()."
            )
        with (
            patch.object(_vpa, "check_a_binary_on_path", return_value=True),
            patch.object(_vpa, "check_b_config", return_value=True),
            patch.object(_vpa, "check_c_git_hook", return_value=False),
            patch.object(_vpa, "check_d_canary", return_value=True),
        ):
            result = _vpa.run_checks()
        self.assertFalse(
            result.get("git_hook"),
            msg=f"Expected git_hook: false when sentinel is absent. Got: {result}",
        )
        self.assertIn(
            "git_hook",
            result.get("failing_checks", []),
            msg=f"Expected 'git_hook' in failing_checks. Got: {result}",
        )


class TestCheckDFailsCanaryNoOutput(unittest.TestCase):
    """Check D: canary hook invoked but does not emit PRECOMMIT_CANARY_OK → check D fails."""

    def test_check_d_fails_canary_no_output(self):
        # covers: UNKNOWN
        """Check D runs the canary hook via subprocess and inspects its stdout.
        When the subprocess returns without emitting 'PRECOMMIT_CANARY_OK', check D
        must report canary: false.

        This test patches check_d_canary to return False.
        """
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import verify_precommit_active. "
                "Implement the module first."
            )
        if not hasattr(_vpa, "check_d_canary"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose check_d_canary(). "
                "Implement this check function."
            )
        if not hasattr(_vpa, "run_checks"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose run_checks()."
            )
        with (
            patch.object(_vpa, "check_a_binary_on_path", return_value=True),
            patch.object(_vpa, "check_b_config", return_value=True),
            patch.object(_vpa, "check_c_git_hook", return_value=True),
            patch.object(_vpa, "check_d_canary", return_value=False),
        ):
            result = _vpa.run_checks()
        self.assertFalse(
            result.get("canary"),
            msg=f"Expected canary: false when canary emits no PRECOMMIT_CANARY_OK. Got: {result}",
        )
        self.assertIn(
            "canary",
            result.get("failing_checks", []),
            msg=f"Expected 'canary' in failing_checks. Got: {result}",
        )


class TestTimeoutHandling(unittest.TestCase):
    """Subprocess timeout during check D → probe exits non-zero (fail-closed)."""

    def test_timeout_handling(self):
        # covers: UNKNOWN
        """When the canary subprocess times out, the probe must exit non-zero.
        Fail-closed: a hung subprocess must not produce a zero exit code.

        This test patches check_d_canary to raise subprocess.TimeoutExpired and
        verifies that run_checks() propagates the failure appropriately.
        """
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import verify_precommit_active. "
                "Implement the module first."
            )
        if not hasattr(_vpa, "run_checks"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose run_checks()."
            )
        if not hasattr(_vpa, "check_d_canary"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose check_d_canary()."
            )
        timeout_exc = subprocess.TimeoutExpired(cmd="pre-commit run ...", timeout=5)
        with (
            patch.object(_vpa, "check_a_binary_on_path", return_value=True),
            patch.object(_vpa, "check_b_config", return_value=True),
            patch.object(_vpa, "check_c_git_hook", return_value=True),
            patch.object(_vpa, "check_d_canary", side_effect=timeout_exc),
        ):
            result = _vpa.run_checks()
        # Fail-closed: a timeout means canary check must be reported as failed
        self.assertFalse(
            result.get("canary"),
            msg=f"Expected canary: false on TimeoutExpired (fail-closed). Got: {result}",
        )
        self.assertIn(
            "canary",
            result.get("failing_checks", []),
            msg=f"Expected 'canary' in failing_checks on timeout. Got: {result}",
        )


class TestUncaughtExceptionHandling(unittest.TestCase):
    """Unexpected exception anywhere in the probe → non-zero exit (fail-closed)."""

    def test_uncaught_exception_handling(self):
        # covers: UNKNOWN
        """An unexpected exception inside run_checks() must not produce exit 0.
        The probe must catch the exception, mark the relevant check as failed,
        and return a non-passing result.

        This test patches check_b_config to raise an unexpected RuntimeError.
        """
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import verify_precommit_active. "
                "Implement the module first."
            )
        if not hasattr(_vpa, "run_checks"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose run_checks()."
            )
        if not hasattr(_vpa, "check_b_config"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose check_b_config()."
            )
        with (
            patch.object(_vpa, "check_a_binary_on_path", return_value=True),
            patch.object(_vpa, "check_b_config", side_effect=RuntimeError("unexpected")),
            patch.object(_vpa, "check_c_git_hook", return_value=True),
            patch.object(_vpa, "check_d_canary", return_value=True),
        ):
            result = _vpa.run_checks()
        # Fail-closed: an uncaught exception means at least one check is False
        self.assertTrue(
            len(result.get("failing_checks", [])) > 0,
            msg=(
                "Expected at least one entry in failing_checks when an unexpected "
                f"exception occurs (fail-closed). Got: {result}"
            ),
        )


class TestExitCodeAllPass(unittest.TestCase):
    """When all checks pass, the CLI exits 0."""

    def test_exit_code_all_pass(self):
        # covers: UNKNOWN
        """main() must sys.exit(0) when all four checks pass.

        This test invokes the module via subprocess, so _run_probe is used.
        All checks are expected to pass when the environment is properly configured.
        Since the script doesn't exist yet, this test fails RED with a JSON parse
        error (stdout will be empty when the script is missing).
        """
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import verify_precommit_active. "
                "Implement the module so main() can be called."
            )
        if not hasattr(_vpa, "main"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose main(). "
                "Add a main() CLI entry point."
            )
        # Patch all four checks to True so we can test the exit-code path in isolation
        for attr in ("check_a_binary_on_path", "check_b_config",
                     "check_c_git_hook", "check_d_canary"):
            if not hasattr(_vpa, attr):
                self.fail(
                    f"AttributeError: verify_precommit_active does not expose {attr}(). "
                    f"Implement this check function."
                )
        import io
        from unittest.mock import patch as mock_patch

        captured_stdout = io.StringIO()
        with (
            patch.object(_vpa, "check_a_binary_on_path", return_value=True),
            patch.object(_vpa, "check_b_config", return_value=True),
            patch.object(_vpa, "check_c_git_hook", return_value=True),
            patch.object(_vpa, "check_d_canary", return_value=True),
            mock_patch("sys.stdout", captured_stdout),
        ):
            try:
                _vpa.main()
                exit_code = 0
            except SystemExit as exc:
                exit_code = exc.code if exc.code is not None else 0
        self.assertEqual(
            exit_code,
            0,
            msg=f"Expected exit 0 when all checks pass. Got exit code: {exit_code}",
        )
        # Also verify the output is valid JSON with the right keys
        try:
            output = json.loads(captured_stdout.getvalue())
        except (json.JSONDecodeError, ValueError):
            self.fail(
                f"Expected valid JSON on stdout from main(). "
                f"Got: {captured_stdout.getvalue()!r}"
            )
        missing_keys = EXPECTED_JSON_KEYS - set(output.keys())
        self.assertFalse(
            missing_keys,
            msg=f"JSON output is missing keys: {missing_keys}. Got: {output}",
        )


class TestExitCodeAnyFailure(unittest.TestCase):
    """When any check fails, the CLI exits non-zero."""

    def test_exit_code_any_failure(self):
        # covers: UNKNOWN
        """main() must sys.exit with a non-zero code when any check fails.

        Check A is forced to fail by passing an empty PATH to the subprocess.
        The subprocess must emit valid JSON and exit non-zero.
        When the script doesn't exist, JSON parsing fails → RED.
        """
        result = _run_probe(env_override={"PATH": ""})
        output = _json_or_fail(self, result)
        self.assertNotEqual(
            result.returncode,
            0,
            msg=(
                f"Expected non-zero exit when at least one check fails. "
                f"Got exit code {result.returncode}. output: {output}"
            ),
        )
        # At minimum, binary should be False (PATH is empty → no pre-commit)
        self.assertFalse(
            output.get("binary"),
            msg=f"Expected binary: false with empty PATH. Got: {output}",
        )
        self.assertGreater(
            len(output.get("failing_checks", [])),
            0,
            msg=f"Expected at least one entry in failing_checks. Got: {output}",
        )


if __name__ == "__main__":
    unittest.main()
