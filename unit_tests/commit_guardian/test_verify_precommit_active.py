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
from unittest.mock import patch

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


# ---------------------------------------------------------------------------
# TICKET 03 ADDITIONS — g-1, g-2, g-3, h-1, h-2, h-3
# Added: 2026-07-06 [EPIC-WorktreeQualityGateGuard/03]
# All classes below are RED until the following functions are implemented in
# verify_precommit_active.py:
#   validate_hook_name(hook_path: Path) -> bool
#   validate_canary_stage(config_path: Path) -> bool
#   check_hook_freshness(hook_path: Path, config_path: Path) -> bool
#   resolve_hooks_path(cwd: Path) -> Path
# Additionally, test_canary_timeout_10s_returns_false is RED because the
# current check_d_canary uses timeout=5 (must be changed to 10).
# ---------------------------------------------------------------------------


class TestValidateHookName(unittest.TestCase):
    """g-1: Required-hook-ID validation. Hook file must be named exactly 'pre-commit'."""

    def test_valid_hook_name_exact(self):
        # covers: UNKNOWN
        """validate_hook_name returns True when the hook file is named exactly 'pre-commit'.

        Must implement validate_hook_name(hook_path: Path) -> bool that returns True only
        when hook_path.name == 'pre-commit' (exact match, no prefix/suffix/extension).
        """
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import verify_precommit_active. "
                "Implement the module first."
            )
        if not hasattr(_vpa, "validate_hook_name"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose validate_hook_name(). "
                "Implement validate_hook_name(hook_path: Path) -> bool."
            )
        hook_path = Path("/tmp/.git/hooks/pre-commit")
        result = _vpa.validate_hook_name(hook_path)
        self.assertTrue(
            result,
            msg=f"Expected validate_hook_name(Path('.../pre-commit')) == True. Got: {result}",
        )

    def test_invalid_hook_name_backup(self):
        # covers: UNKNOWN
        """validate_hook_name returns False when the hook is named 'pre-commit-backup'.

        A backup hook must not be accepted as the canonical pre-commit hook.
        """
        if not _IMPORT_OK:
            self.fail("ImportError: cannot import verify_precommit_active.")
        if not hasattr(_vpa, "validate_hook_name"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose validate_hook_name(). "
                "Implement validate_hook_name(hook_path: Path) -> bool."
            )
        hook_path = Path("/tmp/.git/hooks/pre-commit-backup")
        result = _vpa.validate_hook_name(hook_path)
        self.assertFalse(
            result,
            msg=f"Expected validate_hook_name(Path('.../pre-commit-backup')) == False. Got: {result}",
        )

    def test_invalid_hook_name_no_hyphen(self):
        # covers: UNKNOWN
        """validate_hook_name returns False when the hook is named 'precommit' (no hyphen).

        Hook filename must match exactly 'pre-commit'; 'precommit' is a distinct name.
        """
        if not _IMPORT_OK:
            self.fail("ImportError: cannot import verify_precommit_active.")
        if not hasattr(_vpa, "validate_hook_name"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose validate_hook_name(). "
                "Implement validate_hook_name(hook_path: Path) -> bool."
            )
        hook_path = Path("/tmp/.git/hooks/precommit")
        result = _vpa.validate_hook_name(hook_path)
        self.assertFalse(
            result,
            msg=f"Expected validate_hook_name(Path('.../precommit')) == False. Got: {result}",
        )

    def test_invalid_hook_name_dotted(self):
        # covers: UNKNOWN
        """validate_hook_name returns False when the hook is named '.pre-commit' (dot-prefixed).

        A hidden file '.pre-commit' must not pass; only the bare name 'pre-commit' is valid.
        """
        if not _IMPORT_OK:
            self.fail("ImportError: cannot import verify_precommit_active.")
        if not hasattr(_vpa, "validate_hook_name"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose validate_hook_name(). "
                "Implement validate_hook_name(hook_path: Path) -> bool."
            )
        hook_path = Path("/tmp/.git/hooks/.pre-commit")
        result = _vpa.validate_hook_name(hook_path)
        self.assertFalse(
            result,
            msg=f"Expected validate_hook_name(Path('.../.pre-commit')) == False. Got: {result}",
        )

    def test_invalid_hook_name_with_extension(self):
        # covers: UNKNOWN
        """validate_hook_name returns False when the hook is named 'pre-commit.sh' (extension present).

        Any file extension makes the name non-canonical; only the bare 'pre-commit' passes.
        """
        if not _IMPORT_OK:
            self.fail("ImportError: cannot import verify_precommit_active.")
        if not hasattr(_vpa, "validate_hook_name"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose validate_hook_name(). "
                "Implement validate_hook_name(hook_path: Path) -> bool."
            )
        hook_path = Path("/tmp/.git/hooks/pre-commit.sh")
        result = _vpa.validate_hook_name(hook_path)
        self.assertFalse(
            result,
            msg=f"Expected validate_hook_name(Path('.../pre-commit.sh')) == False. Got: {result}",
        )


class TestValidateCanaryStage(unittest.TestCase):
    """g-2/g-3: Canary anti-spoof / stage attribution. Canary must be in exactly ['manual']."""

    def _write_registry(self, tmp_dir: Path, hooks: list) -> Path:
        """Write a minimal commit_guardian.json registry to tmp_dir and return its path."""
        registry = {"hooks": hooks}
        config_path = tmp_dir / "commit_guardian.json"
        config_path.write_text(json.dumps(registry), encoding="utf-8")
        return config_path

    def test_canary_stage_manual_only(self):
        # covers: UNKNOWN
        """validate_canary_stage returns True when the canary entry has stages: ['manual'] exactly.

        Must implement validate_canary_stage(config_path: Path) -> bool that reads
        commit_guardian.json, finds the 'precommit-canary' entry, and returns True
        only when stages == ['manual'] (single-element list, exactly 'manual').
        """
        if not _IMPORT_OK:
            self.fail("ImportError: cannot import verify_precommit_active.")
        if not hasattr(_vpa, "validate_canary_stage"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose validate_canary_stage(). "
                "Implement validate_canary_stage(config_path: Path) -> bool."
            )
        with tempfile.TemporaryDirectory() as tmp:
            config_path = self._write_registry(
                Path(tmp),
                [{"id": "precommit-canary", "stages": ["manual"]}],
            )
            result = _vpa.validate_canary_stage(config_path)
        self.assertTrue(
            result,
            msg=(
                "Expected validate_canary_stage to return True when "
                f"stages=['manual']. Got: {result}"
            ),
        )

    def test_canary_stage_empty(self):
        # covers: UNKNOWN
        """validate_canary_stage returns False when the canary entry has stages: [].

        An empty stages list means the canary fires in no stage — must fail.
        """
        if not _IMPORT_OK:
            self.fail("ImportError: cannot import verify_precommit_active.")
        if not hasattr(_vpa, "validate_canary_stage"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose validate_canary_stage(). "
                "Implement validate_canary_stage(config_path: Path) -> bool."
            )
        with tempfile.TemporaryDirectory() as tmp:
            config_path = self._write_registry(
                Path(tmp),
                [{"id": "precommit-canary", "stages": []}],
            )
            result = _vpa.validate_canary_stage(config_path)
        self.assertFalse(
            result,
            msg=f"Expected validate_canary_stage to return False when stages=[]. Got: {result}",
        )

    def test_canary_stage_commit_msg(self):
        # covers: UNKNOWN
        """validate_canary_stage returns False when stages: ['commit-msg'].

        The canary must only be in the 'manual' stage; 'commit-msg' is forbidden.
        """
        if not _IMPORT_OK:
            self.fail("ImportError: cannot import verify_precommit_active.")
        if not hasattr(_vpa, "validate_canary_stage"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose validate_canary_stage(). "
                "Implement validate_canary_stage(config_path: Path) -> bool."
            )
        with tempfile.TemporaryDirectory() as tmp:
            config_path = self._write_registry(
                Path(tmp),
                [{"id": "precommit-canary", "stages": ["commit-msg"]}],
            )
            result = _vpa.validate_canary_stage(config_path)
        self.assertFalse(
            result,
            msg=(
                "Expected validate_canary_stage to return False when "
                f"stages=['commit-msg']. Got: {result}"
            ),
        )

    def test_canary_stage_multi_including_manual(self):
        # covers: UNKNOWN
        """validate_canary_stage returns False when stages include 'manual' AND another stage.

        Multi-stage registration is a spoof risk; canary must be in ONLY ['manual'].
        stages=['manual', 'pre-commit'] must fail even though 'manual' is present.
        """
        if not _IMPORT_OK:
            self.fail("ImportError: cannot import verify_precommit_active.")
        if not hasattr(_vpa, "validate_canary_stage"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose validate_canary_stage(). "
                "Implement validate_canary_stage(config_path: Path) -> bool."
            )
        with tempfile.TemporaryDirectory() as tmp:
            config_path = self._write_registry(
                Path(tmp),
                [{"id": "precommit-canary", "stages": ["manual", "pre-commit"]}],
            )
            result = _vpa.validate_canary_stage(config_path)
        self.assertFalse(
            result,
            msg=(
                "Expected validate_canary_stage to return False when "
                f"stages=['manual', 'pre-commit']. Got: {result}"
            ),
        )

    def test_canary_entry_absent(self):
        # covers: UNKNOWN
        """validate_canary_stage returns False when no 'precommit-canary' entry exists in registry.

        A missing canary entry means the canary is not installed — fail-closed.
        """
        if not _IMPORT_OK:
            self.fail("ImportError: cannot import verify_precommit_active.")
        if not hasattr(_vpa, "validate_canary_stage"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose validate_canary_stage(). "
                "Implement validate_canary_stage(config_path: Path) -> bool."
            )
        with tempfile.TemporaryDirectory() as tmp:
            config_path = self._write_registry(
                Path(tmp),
                [{"id": "some-other-hook", "stages": ["manual"]}],
            )
            result = _vpa.validate_canary_stage(config_path)
        self.assertFalse(
            result,
            msg=(
                "Expected validate_canary_stage to return False when canary entry is absent. "
                f"Got: {result}"
            ),
        )

    def test_canary_non_manual_stage(self):
        # covers: UNKNOWN
        """validate_canary_stage returns False when canary is in stages: ['pre-push'] only.

        Any non-manual stage alone must fail; the canary must never appear in push stages.
        """
        if not _IMPORT_OK:
            self.fail("ImportError: cannot import verify_precommit_active.")
        if not hasattr(_vpa, "validate_canary_stage"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose validate_canary_stage(). "
                "Implement validate_canary_stage(config_path: Path) -> bool."
            )
        with tempfile.TemporaryDirectory() as tmp:
            config_path = self._write_registry(
                Path(tmp),
                [{"id": "precommit-canary", "stages": ["pre-push"]}],
            )
            result = _vpa.validate_canary_stage(config_path)
        self.assertFalse(
            result,
            msg=(
                "Expected validate_canary_stage to return False when "
                f"stages=['pre-push']. Got: {result}"
            ),
        )


class TestCheckHookFreshness(unittest.TestCase):
    """h-1: Config freshness/drift detection. Hook must be at least as new as config."""

    def test_hook_newer_than_config(self):
        # covers: UNKNOWN
        """check_hook_freshness returns True when hook mtime > config mtime.

        Must implement check_hook_freshness(hook_path: Path, config_path: Path) -> bool
        that returns True when hook_path.stat().st_mtime >= config_path.stat().st_mtime.
        """
        if not _IMPORT_OK:
            self.fail("ImportError: cannot import verify_precommit_active.")
        if not hasattr(_vpa, "check_hook_freshness"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose check_hook_freshness(). "
                "Implement check_hook_freshness(hook_path: Path, config_path: Path) -> bool."
            )
        import time
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = tmp_path / ".pre-commit-config.yaml"
            config_path.write_text("repos: []", encoding="utf-8")
            time.sleep(0.02)  # ensure strictly different filesystem mtime
            hook_path = tmp_path / "pre-commit"
            hook_path.write_text("#!/bin/sh\n", encoding="utf-8")
            result = _vpa.check_hook_freshness(hook_path, config_path)
        self.assertTrue(
            result,
            msg=(
                "Expected check_hook_freshness to return True when hook is newer than config. "
                f"Got: {result}"
            ),
        )

    def test_hook_same_mtime_as_config(self):
        # covers: UNKNOWN
        """check_hook_freshness returns True when hook mtime == config mtime.

        Equal mtime means the hook was regenerated at the same time as config — not stale.
        """
        if not _IMPORT_OK:
            self.fail("ImportError: cannot import verify_precommit_active.")
        if not hasattr(_vpa, "check_hook_freshness"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose check_hook_freshness(). "
                "Implement check_hook_freshness(hook_path: Path, config_path: Path) -> bool."
            )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = tmp_path / ".pre-commit-config.yaml"
            hook_path = tmp_path / "pre-commit"
            config_path.write_text("repos: []", encoding="utf-8")
            hook_path.write_text("#!/bin/sh\n", encoding="utf-8")
            # Force equal mtime by copying config's mtime onto hook
            config_stat = config_path.stat()
            os.utime(hook_path, (config_stat.st_atime, config_stat.st_mtime))
            result = _vpa.check_hook_freshness(hook_path, config_path)
        self.assertTrue(
            result,
            msg=(
                "Expected check_hook_freshness to return True when hook mtime == config mtime. "
                f"Got: {result}"
            ),
        )

    def test_hook_older_than_config(self):
        # covers: UNKNOWN
        """check_hook_freshness returns False when hook mtime < config mtime (hook is stale).

        A hook older than the config means the config was updated but the hook was not
        regenerated — this is the stale/drift state that must fail.
        """
        if not _IMPORT_OK:
            self.fail("ImportError: cannot import verify_precommit_active.")
        if not hasattr(_vpa, "check_hook_freshness"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose check_hook_freshness(). "
                "Implement check_hook_freshness(hook_path: Path, config_path: Path) -> bool."
            )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = tmp_path / ".pre-commit-config.yaml"
            hook_path = tmp_path / "pre-commit"
            config_path.write_text("repos: []", encoding="utf-8")
            hook_path.write_text("#!/bin/sh\n", encoding="utf-8")
            # Force hook to be 100 seconds older than config
            config_stat = config_path.stat()
            os.utime(
                hook_path,
                (config_stat.st_atime - 100, config_stat.st_mtime - 100),
            )
            result = _vpa.check_hook_freshness(hook_path, config_path)
        self.assertFalse(
            result,
            msg=(
                "Expected check_hook_freshness to return False when hook mtime < config mtime. "
                f"Got: {result}"
            ),
        )

    def test_hook_missing_config_present(self):
        # covers: UNKNOWN
        """check_hook_freshness returns False when hook does not exist but config does.

        A missing hook with a present config is a fail-closed state (hook not installed).
        """
        if not _IMPORT_OK:
            self.fail("ImportError: cannot import verify_precommit_active.")
        if not hasattr(_vpa, "check_hook_freshness"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose check_hook_freshness(). "
                "Implement check_hook_freshness(hook_path: Path, config_path: Path) -> bool."
            )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = tmp_path / ".pre-commit-config.yaml"
            config_path.write_text("repos: []", encoding="utf-8")
            hook_path = tmp_path / "pre-commit"  # intentionally never created
            result = _vpa.check_hook_freshness(hook_path, config_path)
        self.assertFalse(
            result,
            msg=(
                "Expected check_hook_freshness to return False when hook file is absent. "
                f"Got: {result}"
            ),
        )


class TestCheckDCanaryTimeout(unittest.TestCase):
    """h-2: Canary timeout fail-closed. Timeout must be 10 seconds (ticket 03 raises it from 5)."""

    def test_canary_timeout_10s_returns_false(self):
        # covers: UNKNOWN
        """run_checks() marks canary: False when subprocess.TimeoutExpired fires at 10s.

        Ticket 03 changes the canary timeout from 5s to 10s. This test:
        (1) Simulates TimeoutExpired(timeout=10) and verifies fail-closed behavior.
        (2) Inspects check_d_canary source to assert 'timeout=10' is present (not 'timeout=5').
        The source inspection assertion is the primary RED signal until the implementation
        is updated. The mock path verifies the run_checks() fail-closed behavior.
        """
        if not _IMPORT_OK:
            self.fail("ImportError: cannot import verify_precommit_active.")
        if not hasattr(_vpa, "run_checks"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose run_checks()."
            )
        if not hasattr(_vpa, "check_d_canary"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose check_d_canary()."
            )
        # Part 1: fail-closed behavior with 10s timeout exception
        timeout_exc = subprocess.TimeoutExpired(cmd="pre-commit run ...", timeout=10)
        with (
            patch.object(_vpa, "check_a_binary_on_path", return_value=True),
            patch.object(_vpa, "check_b_config", return_value=True),
            patch.object(_vpa, "check_c_git_hook", return_value=True),
            patch.object(_vpa, "check_d_canary", side_effect=timeout_exc),
        ):
            result = _vpa.run_checks()
        self.assertFalse(
            result.get("canary"),
            msg=(
                "Expected canary: false when check_d_canary raises TimeoutExpired(timeout=10). "
                f"Got: {result}"
            ),
        )
        self.assertIn(
            "canary",
            result.get("failing_checks", []),
            msg=f"Expected 'canary' in failing_checks on 10s timeout. Got: {result}",
        )
        # Part 2: source inspection — the implementation MUST use timeout=10, not timeout=5.
        import inspect
        source = inspect.getsource(_vpa.check_d_canary)
        self.assertIn(
            "timeout=10",
            source,
            msg=(
                "verify_precommit_active.check_d_canary must use timeout=10 (ticket 03 raises "
                f"the threshold from 5 to 10). Found in source:\n{source}"
            ),
        )


class TestResolveHooksPath(unittest.TestCase):
    """h-3: hooksPath resolution. Absolute, relative, unset, and unreadable .git/config."""

    def test_hooks_path_absolute_from_git_config(self):
        # covers: UNKNOWN
        """resolve_hooks_path returns the absolute path from core.hooksPath in .git/config.

        Must implement resolve_hooks_path(cwd: Path) -> Path that reads .git/config,
        finds core.hooksPath, and returns it as-is when it is already absolute.
        """
        if not _IMPORT_OK:
            self.fail("ImportError: cannot import verify_precommit_active.")
        if not hasattr(_vpa, "resolve_hooks_path"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose resolve_hooks_path(). "
                "Implement resolve_hooks_path(cwd: Path) -> Path."
            )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            git_dir = tmp_path / ".git"
            git_dir.mkdir()
            git_config = git_dir / "config"
            git_config.write_text(
                "[core]\n\thooksPath = /absolute/hooks/path\n",
                encoding="utf-8",
            )
            result = _vpa.resolve_hooks_path(tmp_path)
        self.assertEqual(
            result,
            Path("/absolute/hooks/path"),
            msg=(
                "Expected resolve_hooks_path to return Path('/absolute/hooks/path') "
                f"for absolute core.hooksPath. Got: {result}"
            ),
        )

    def test_hooks_path_relative_from_git_config(self):
        # covers: UNKNOWN
        """resolve_hooks_path resolves a relative core.hooksPath against the worktree root.

        When core.hooksPath is a relative path (e.g. '.hooks'), it must be resolved
        relative to cwd (the worktree root), not relative to the .git directory.
        """
        if not _IMPORT_OK:
            self.fail("ImportError: cannot import verify_precommit_active.")
        if not hasattr(_vpa, "resolve_hooks_path"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose resolve_hooks_path(). "
                "Implement resolve_hooks_path(cwd: Path) -> Path."
            )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            git_dir = tmp_path / ".git"
            git_dir.mkdir()
            git_config = git_dir / "config"
            git_config.write_text(
                "[core]\n\thooksPath = .hooks\n",
                encoding="utf-8",
            )
            result = _vpa.resolve_hooks_path(tmp_path)
        expected = tmp_path / ".hooks"
        self.assertEqual(
            result,
            expected,
            msg=(
                f"Expected resolve_hooks_path to return {expected} "
                f"for relative core.hooksPath='.hooks'. Got: {result}"
            ),
        )

    def test_hooks_path_unset_falls_back_to_commondir(self):
        # covers: UNKNOWN
        """resolve_hooks_path falls back to <commondir>/hooks/ when core.hooksPath is unset.

        When .git/config has no core.hooksPath setting, resolve_hooks_path must fall
        back to the standard hooks location: .git/hooks/ (or commondir/hooks/ for worktrees).
        """
        if not _IMPORT_OK:
            self.fail("ImportError: cannot import verify_precommit_active.")
        if not hasattr(_vpa, "resolve_hooks_path"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose resolve_hooks_path(). "
                "Implement resolve_hooks_path(cwd: Path) -> Path."
            )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            git_dir = tmp_path / ".git"
            git_dir.mkdir()
            # Write a config without hooksPath
            git_config = git_dir / "config"
            git_config.write_text(
                "[core]\n\trepositoryformatversion = 0\n\tfilemode = true\n",
                encoding="utf-8",
            )
            result = _vpa.resolve_hooks_path(tmp_path)
        expected = tmp_path / ".git" / "hooks"
        self.assertEqual(
            result,
            expected,
            msg=(
                f"Expected resolve_hooks_path to fall back to {expected} "
                f"when core.hooksPath is absent. Got: {result}"
            ),
        )

    def test_hooks_path_unreadable_raises_oserror(self):
        # covers: UNKNOWN
        """resolve_hooks_path raises OSError when .git/config is unreadable.

        When .git/config exists but is not readable (permissions denied),
        resolve_hooks_path must raise OSError (fail-closed: no silent fallback).
        """
        if not _IMPORT_OK:
            self.fail("ImportError: cannot import verify_precommit_active.")
        if not hasattr(_vpa, "resolve_hooks_path"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose resolve_hooks_path(). "
                "Implement resolve_hooks_path(cwd: Path) -> Path."
            )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            git_dir = tmp_path / ".git"
            git_dir.mkdir()
            git_config = git_dir / "config"
            git_config.write_text(
                "[core]\n\thooksPath = /some/path\n",
                encoding="utf-8",
            )
            # Make .git/config unreadable
            os.chmod(git_config, 0o000)
            try:
                with self.assertRaises(OSError):
                    _vpa.resolve_hooks_path(tmp_path)
            finally:
                # Restore permissions so tempfile cleanup succeeds
                os.chmod(git_config, 0o644)


# ---------------------------------------------------------------------------
# TICKET 04 ADDITIONS — BO-1700b-1, BO-1700b-2, BO-1700b-4
# Added: 2026-07-06 [EPIC-WorktreeQualityGateGuard/04]
# Tests in Groups 2 and 3 are RED until the following functions are implemented
# in verify_precommit_active.py:
#   assert_no_allow_no_config_env() -> bool
#   remove_canary_from_manifest(config_path: Path) -> bool
# Group 1 tests exercise explicit fail-closed invariants at the import and
# subprocess level, including some combinations not covered by tickets 02/03.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Group 1: Fail-closed explicit tests (BO-1700b-1)
# ---------------------------------------------------------------------------


class TestFailClosedCheckA(unittest.TestCase):
    """BO-1700b-1: Fail-closed when check_a raises RuntimeError."""

    def test_check_a_runtime_error_marks_binary_false(self):
        # covers: BO-1700b-1
        """When check_a_binary_on_path raises RuntimeError → run_checks marks binary=False,
        'binary' in failing_checks, AND failing_checks is non-empty.

        Verifies the fail-closed invariant for check A specifically: a RuntimeError
        inside the probe cannot produce a passing result.
        """
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import verify_precommit_active. "
                "Implement the module first."
            )
        if not hasattr(_vpa, "run_checks"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose run_checks(). "
                "Implement run_checks()."
            )
        with (
            patch.object(
                _vpa,
                "check_a_binary_on_path",
                side_effect=RuntimeError("binary check exploded"),
            ),
            patch.object(_vpa, "check_b_config", return_value=True),
            patch.object(_vpa, "check_c_git_hook", return_value=True),
            patch.object(_vpa, "check_d_canary", return_value=True),
        ):
            result = _vpa.run_checks()
        self.assertFalse(
            result.get("binary"),
            msg=f"Expected binary=False when check_a raises RuntimeError. Got: {result}",
        )
        self.assertIn(
            "binary",
            result.get("failing_checks", []),
            msg=f"Expected 'binary' in failing_checks when check_a raises RuntimeError. Got: {result}",
        )
        self.assertGreater(
            len(result.get("failing_checks", [])),
            0,
            msg=f"Expected failing_checks non-empty when check_a raises. Got: {result}",
        )


class TestFailClosedCheckBException(unittest.TestCase):
    """BO-1700b-1: Fail-closed when check_b raises OSError (not just RuntimeError)."""

    def test_check_b_oserror_marks_config_false(self):
        # covers: BO-1700b-1
        """When check_b_config raises OSError → run_checks marks config=False,
        'config' in failing_checks, AND failing_checks is non-empty.

        Existing TestUncaughtExceptionHandling covers RuntimeError on check_b.
        This test explicitly verifies the OSError case so that OS-level errors
        (file unreadable, permission denied) are also caught and fail-closed.
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
            patch.object(
                _vpa, "check_b_config", side_effect=OSError("permission denied on config")
            ),
            patch.object(_vpa, "check_c_git_hook", return_value=True),
            patch.object(_vpa, "check_d_canary", return_value=True),
        ):
            result = _vpa.run_checks()
        self.assertFalse(
            result.get("config"),
            msg=f"Expected config=False when check_b raises OSError. Got: {result}",
        )
        self.assertIn(
            "config",
            result.get("failing_checks", []),
            msg=f"Expected 'config' in failing_checks when check_b raises OSError. Got: {result}",
        )
        self.assertGreater(
            len(result.get("failing_checks", [])),
            0,
            msg=f"Expected failing_checks non-empty when check_b raises OSError. Got: {result}",
        )


class TestFailClosedNoGreenOnError(unittest.TestCase):
    """BO-1700b-1: Critical — no branch allows proceed when any check errors internally."""

    def test_check_a_raises_any_exception_binary_false_failing_nonempty(self):
        # covers: BO-1700b-1
        """When check_a raises any exception (ValueError here), binary must be False
        AND failing_checks must be non-empty — no proceed path can survive.

        Verifies the critical invariant: the probe cannot produce an all-true result
        when any individual check raises internally.
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
        with (
            patch.object(
                _vpa,
                "check_a_binary_on_path",
                side_effect=ValueError("unexpected internal error in A"),
            ),
            patch.object(_vpa, "check_b_config", return_value=True),
            patch.object(_vpa, "check_c_git_hook", return_value=True),
            patch.object(_vpa, "check_d_canary", return_value=True),
        ):
            result = _vpa.run_checks()
        self.assertFalse(
            result.get("binary"),
            msg=f"Expected binary=False when check_a raises any exception. Got: {result}",
        )
        self.assertGreater(
            len(result.get("failing_checks", [])),
            0,
            msg=(
                "Expected failing_checks non-empty when check_a raises — "
                f"no proceed path is allowed. Got: {result}"
            ),
        )

    def test_check_c_raises_any_exception_git_hook_false_failing_nonempty(self):
        # covers: BO-1700b-1
        """When check_c raises any exception (PermissionError here), git_hook must be False
        AND failing_checks must be non-empty — no proceed path can survive.
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
        if not hasattr(_vpa, "check_c_git_hook"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose check_c_git_hook()."
            )
        with (
            patch.object(_vpa, "check_a_binary_on_path", return_value=True),
            patch.object(_vpa, "check_b_config", return_value=True),
            patch.object(
                _vpa,
                "check_c_git_hook",
                side_effect=PermissionError("hooks dir unreadable"),
            ),
            patch.object(_vpa, "check_d_canary", return_value=True),
        ):
            result = _vpa.run_checks()
        self.assertFalse(
            result.get("git_hook"),
            msg=f"Expected git_hook=False when check_c raises any exception. Got: {result}",
        )
        self.assertGreater(
            len(result.get("failing_checks", [])),
            0,
            msg=(
                "Expected failing_checks non-empty when check_c raises — "
                f"no proceed path is allowed. Got: {result}"
            ),
        )


class TestFailClosedSubprocessExitNonZero(unittest.TestCase):
    """BO-1700b-1: Subprocess-level fail-closed — non-zero exit when any check fails."""

    def test_empty_path_returncode_nonzero(self):
        # covers: BO-1700b-1
        """When run as a subprocess with empty PATH (check A fails), returncode must be
        non-zero. Subprocess-level verification that the main() CLI entry point exits 1,
        not 0, when a check fails.
        """
        result = _run_probe(env_override={"PATH": ""})
        output = _json_or_fail(self, result)
        self.assertNotEqual(
            result.returncode,
            0,
            msg=(
                f"Expected non-zero exit from subprocess when PATH='' (binary absent). "
                f"Got returncode={result.returncode}. output={output}"
            ),
        )
        self.assertFalse(
            output.get("binary"),
            msg=f"Expected binary=false with empty PATH in subprocess. Got: {output}",
        )
        self.assertGreater(
            len(output.get("failing_checks", [])),
            0,
            msg=f"Expected failing_checks non-empty in subprocess output. Got: {output}",
        )


class TestFailClosedTimeoutProducesNonZeroExit(unittest.TestCase):
    """BO-1700b-1: TimeoutExpired on check_d → canary=False, 'canary' in failing_checks."""

    def test_timeout_marks_canary_false_and_failing_nonempty(self):
        # covers: BO-1700b-1
        """Via mock: when check_d_canary raises TimeoutExpired, run_checks() must mark
        canary=False AND 'canary' must be in failing_checks AND failing_checks must be
        non-empty.

        Complementary to TestTimeoutHandling (ticket 02) and TestCheckDCanaryTimeout
        (ticket 03) — this version adds an explicit failing_checks length assertion to
        ensure the non-empty condition is explicitly tested.
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
        timeout_exc = subprocess.TimeoutExpired(cmd="pre-commit run canary", timeout=10)
        with (
            patch.object(_vpa, "check_a_binary_on_path", return_value=True),
            patch.object(_vpa, "check_b_config", return_value=True),
            patch.object(_vpa, "check_c_git_hook", return_value=True),
            patch.object(_vpa, "check_d_canary", side_effect=timeout_exc),
        ):
            result = _vpa.run_checks()
        self.assertFalse(
            result.get("canary"),
            msg=f"Expected canary=False on TimeoutExpired (fail-closed). Got: {result}",
        )
        self.assertIn(
            "canary",
            result.get("failing_checks", []),
            msg=f"Expected 'canary' in failing_checks on timeout. Got: {result}",
        )
        self.assertGreater(
            len(result.get("failing_checks", [])),
            0,
            msg=f"Expected failing_checks non-empty on timeout. Got: {result}",
        )


# ---------------------------------------------------------------------------
# Group 2: PRE_COMMIT_ALLOW_NO_CONFIG detection (BO-1700b-2)
# RED: assert_no_allow_no_config_env() does not exist in production code yet.
# ---------------------------------------------------------------------------


class TestPRECommitAllowNoConfigNotSet(unittest.TestCase):
    """BO-1700b-2: When PRE_COMMIT_ALLOW_NO_CONFIG is NOT set, function returns True (safe)."""

    def test_env_var_absent_returns_true(self):
        # covers: BO-1700b-2
        """assert_no_allow_no_config_env() returns True when PRE_COMMIT_ALLOW_NO_CONFIG
        is not present in os.environ.

        Must implement assert_no_allow_no_config_env() -> bool that reads os.environ
        and returns True when PRE_COMMIT_ALLOW_NO_CONFIG is absent (safe state).
        """
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import verify_precommit_active. "
                "Implement the module first."
            )
        if not hasattr(_vpa, "assert_no_allow_no_config_env"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose "
                "assert_no_allow_no_config_env(). Implement this function."
            )
        # Patch out the env var so it is definitely absent
        clean_env = {k: v for k, v in os.environ.items() if k != "PRE_COMMIT_ALLOW_NO_CONFIG"}
        with patch.dict(os.environ, clean_env, clear=True):
            result = _vpa.assert_no_allow_no_config_env()
        self.assertTrue(
            result,
            msg=(
                "Expected assert_no_allow_no_config_env() == True "
                f"when PRE_COMMIT_ALLOW_NO_CONFIG is absent. Got: {result}"
            ),
        )


class TestPRECommitAllowNoConfigSet(unittest.TestCase):
    """BO-1700b-2: When PRE_COMMIT_ALLOW_NO_CONFIG='1', function returns False or raises ValueError."""

    def test_env_var_set_to_one_returns_false_or_raises(self):
        # covers: BO-1700b-2
        """assert_no_allow_no_config_env() returns False OR raises ValueError when
        PRE_COMMIT_ALLOW_NO_CONFIG='1'.

        Setting this variable bypasses config-check and is a fatal invariant break.
        The function must signal failure by returning False or raising ValueError —
        either response is acceptable as long as it is not a truthy return.
        """
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import verify_precommit_active. "
                "Implement the module first."
            )
        if not hasattr(_vpa, "assert_no_allow_no_config_env"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose "
                "assert_no_allow_no_config_env(). Implement this function."
            )
        with patch.dict(os.environ, {"PRE_COMMIT_ALLOW_NO_CONFIG": "1"}):
            try:
                result = _vpa.assert_no_allow_no_config_env()
            except ValueError:
                return  # raising ValueError is an acceptable fail-safe signal
        self.assertFalse(
            result,
            msg=(
                "Expected assert_no_allow_no_config_env() to return False "
                f"when PRE_COMMIT_ALLOW_NO_CONFIG='1'. Got: {result}"
            ),
        )


class TestPRECommitAllowNoConfigEmptyString(unittest.TestCase):
    """BO-1700b-2: When PRE_COMMIT_ALLOW_NO_CONFIG='', function returns True (empty = safe)."""

    def test_env_var_empty_string_returns_true(self):
        # covers: BO-1700b-2
        """assert_no_allow_no_config_env() returns True when PRE_COMMIT_ALLOW_NO_CONFIG=''
        (empty string). An empty value is semantically equivalent to 'not set' for this
        guard: the bypass effect only activates when the variable has a non-empty value.
        """
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import verify_precommit_active. "
                "Implement the module first."
            )
        if not hasattr(_vpa, "assert_no_allow_no_config_env"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose "
                "assert_no_allow_no_config_env(). Implement this function."
            )
        with patch.dict(os.environ, {"PRE_COMMIT_ALLOW_NO_CONFIG": ""}):
            result = _vpa.assert_no_allow_no_config_env()
        self.assertTrue(
            result,
            msg=(
                "Expected assert_no_allow_no_config_env() == True "
                f"when PRE_COMMIT_ALLOW_NO_CONFIG='' (empty = safe). Got: {result}"
            ),
        )


class TestNoBuildFunctionSetsAllowNoConfig(unittest.TestCase):
    """BO-1700b-2: Verify that no function in verify_precommit_active.py sets PRE_COMMIT_ALLOW_NO_CONFIG."""

    def test_source_does_not_assign_allow_no_config(self):
        # covers: BO-1700b-2
        """Source inspection: the module must not assign PRE_COMMIT_ALLOW_NO_CONFIG
        into os.environ anywhere in its body. This is a static guard — no combination
        of runtime branching should produce a path that sets the bypass variable.

        The module may reference the variable name in a comment or guard read, but
        must never write it into os.environ.
        """
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import verify_precommit_active. "
                "Implement the module first."
            )
        import inspect
        source = inspect.getsource(_vpa)
        # Forbidden: any direct assignment into os.environ for the bypass var.
        # Using string search on key patterns to catch all common assignment forms.
        forbidden_patterns = [
            'os.environ["PRE_COMMIT_ALLOW_NO_CONFIG"]',
            "os.environ['PRE_COMMIT_ALLOW_NO_CONFIG']",
            'os.environ.update({"PRE_COMMIT_ALLOW_NO_CONFIG"',
            "os.environ.update({'PRE_COMMIT_ALLOW_NO_CONFIG'",
            'os.putenv("PRE_COMMIT_ALLOW_NO_CONFIG"',
            "os.putenv('PRE_COMMIT_ALLOW_NO_CONFIG'",
        ]
        for pattern in forbidden_patterns:
            self.assertNotIn(
                pattern,
                source,
                msg=(
                    "verify_precommit_active.py must NOT write PRE_COMMIT_ALLOW_NO_CONFIG "
                    f"into os.environ. Found forbidden assignment pattern: {pattern!r}"
                ),
            )


# ---------------------------------------------------------------------------
# Group 3: Canary removal / cleanup (BO-1700b-4)
# RED: remove_canary_from_manifest() does not exist in production code yet.
# ---------------------------------------------------------------------------


class TestRemoveCanaryFromManifest(unittest.TestCase):
    """BO-1700b-4: remove_canary_from_manifest removes the canary entry when present."""

    def _write_registry(self, tmp_dir: Path, hooks: list) -> Path:
        """Write a minimal commit_guardian.json registry to tmp_dir and return its path."""
        registry = {"hooks": hooks}
        config_path = tmp_dir / "commit_guardian.json"
        config_path.write_text(json.dumps(registry), encoding="utf-8")
        return config_path

    def test_canary_entry_removed(self):
        # covers: BO-1700b-4
        """When the precommit-canary entry exists with stages=['manual'], calling
        remove_canary_from_manifest removes it. After the call, validate_canary_stage
        returns False (the entry is gone or stages are empty).

        Must implement remove_canary_from_manifest(config_path: Path) -> bool that:
        - Reads commit_guardian.json at config_path
        - Finds the 'precommit-canary' entry
        - Removes it entirely (or empties its stages to [])
        - Writes the modified JSON back to disk
        - Returns True (entry was found and removed)
        """
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import verify_precommit_active. "
                "Implement the module first."
            )
        if not hasattr(_vpa, "remove_canary_from_manifest"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose "
                "remove_canary_from_manifest(). Implement this function."
            )
        if not hasattr(_vpa, "validate_canary_stage"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose "
                "validate_canary_stage(). Implement this function first (ticket 03)."
            )
        with tempfile.TemporaryDirectory() as tmp:
            config_path = self._write_registry(
                Path(tmp),
                [{"id": "precommit-canary", "stages": ["manual"]}],
            )
            removed = _vpa.remove_canary_from_manifest(config_path)
            self.assertTrue(
                removed,
                msg=(
                    "Expected remove_canary_from_manifest to return True "
                    f"when canary entry is present. Got: {removed}"
                ),
            )
            # After removal, validate_canary_stage must return False (entry gone/empty)
            still_valid = _vpa.validate_canary_stage(config_path)
        self.assertFalse(
            still_valid,
            msg=(
                "Expected validate_canary_stage to return False after "
                f"remove_canary_from_manifest — entry must be absent or stages=[]. "
                f"Got: {still_valid}"
            ),
        )


class TestRemoveCanaryFromManifestAlreadyAbsent(unittest.TestCase):
    """BO-1700b-4: When no canary entry exists, remove_canary_from_manifest returns False."""

    def _write_registry(self, tmp_dir: Path, hooks: list) -> Path:
        """Write a minimal commit_guardian.json registry to tmp_dir and return its path."""
        registry = {"hooks": hooks}
        config_path = tmp_dir / "commit_guardian.json"
        config_path.write_text(json.dumps(registry), encoding="utf-8")
        return config_path

    def test_absent_canary_returns_false(self):
        # covers: BO-1700b-4
        """When no 'precommit-canary' entry exists in the registry, calling
        remove_canary_from_manifest returns False (idempotent: nothing to remove,
        no error).
        """
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import verify_precommit_active. "
                "Implement the module first."
            )
        if not hasattr(_vpa, "remove_canary_from_manifest"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose "
                "remove_canary_from_manifest(). Implement this function."
            )
        with tempfile.TemporaryDirectory() as tmp:
            config_path = self._write_registry(
                Path(tmp),
                [{"id": "some-other-hook", "stages": ["pre-commit"]}],
            )
            result = _vpa.remove_canary_from_manifest(config_path)
        self.assertFalse(
            result,
            msg=(
                "Expected remove_canary_from_manifest to return False "
                f"when no canary entry is present (idempotent). Got: {result}"
            ),
        )


class TestRemoveCanaryFromManifestIdempotent(unittest.TestCase):
    """BO-1700b-4: Calling remove_canary_from_manifest twice is safe; second call returns False."""

    def _write_registry(self, tmp_dir: Path, hooks: list) -> Path:
        """Write a minimal commit_guardian.json registry to tmp_dir and return its path."""
        registry = {"hooks": hooks}
        config_path = tmp_dir / "commit_guardian.json"
        config_path.write_text(json.dumps(registry), encoding="utf-8")
        return config_path

    def test_second_call_returns_false_no_error(self):
        # covers: BO-1700b-4
        """Calling remove_canary_from_manifest twice on the same registry is safe:
        the first call returns True (removed), the second call returns False
        (entry already gone) and does not raise.
        """
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import verify_precommit_active. "
                "Implement the module first."
            )
        if not hasattr(_vpa, "remove_canary_from_manifest"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose "
                "remove_canary_from_manifest(). Implement this function."
            )
        with tempfile.TemporaryDirectory() as tmp:
            config_path = self._write_registry(
                Path(tmp),
                [{"id": "precommit-canary", "stages": ["manual"]}],
            )
            first = _vpa.remove_canary_from_manifest(config_path)
            self.assertTrue(
                first,
                msg=f"Expected first call to return True (entry found). Got: {first}",
            )
            try:
                second = _vpa.remove_canary_from_manifest(config_path)
            except Exception as exc:  # noqa: BLE001
                self.fail(
                    f"Expected second call to be idempotent (no raise). "
                    f"Got exception: {type(exc).__name__}: {exc}"
                )
        self.assertFalse(
            second,
            msg=(
                "Expected second call to remove_canary_from_manifest to return False "
                f"(entry already gone). Got: {second}"
            ),
        )


class TestRemoveCanaryFromManifestFileNotFound(unittest.TestCase):
    """BO-1700b-4: When config_path doesn't exist, remove_canary_from_manifest returns False."""

    def test_missing_file_returns_false(self):
        # covers: BO-1700b-4
        """When the config_path doesn't exist, remove_canary_from_manifest must return
        False (fail-safe: no raise, no crash). The caller may not have installed the
        registry yet, and that is not an error condition.
        """
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import verify_precommit_active. "
                "Implement the module first."
            )
        if not hasattr(_vpa, "remove_canary_from_manifest"):
            self.fail(
                "AttributeError: verify_precommit_active does not expose "
                "remove_canary_from_manifest(). Implement this function."
            )
        nonexistent = Path("/tmp/nonexistent_commit_guardian_xyzzy_12345.json")
        try:
            result = _vpa.remove_canary_from_manifest(nonexistent)
        except Exception as exc:  # noqa: BLE001
            self.fail(
                f"Expected remove_canary_from_manifest to return False (not raise) "
                f"when config_path doesn't exist. Got exception: {type(exc).__name__}: {exc}"
            )
        self.assertFalse(
            result,
            msg=(
                "Expected remove_canary_from_manifest to return False "
                f"when config_path doesn't exist. Got: {result}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
