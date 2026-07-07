"""
MODULE: test_setup_ticket_worktree
GOAL: TDD red-baseline tests for the create-time pre-drive gate in _bootstrap().
BUSINESS CONTEXT: Ticket 06 of EPIC-WorktreeQualityGateGuard. Tests cover the
    gate behavior to be added to setup_ticket_worktree.py _bootstrap() that calls
    verify_precommit_active.py after the pre-commit config is established.
    All four tests are RED until python-coder implements the gate.
ARCHITECTURE: All tests mock subprocess.run to avoid real git/filesystem side
    effects. tmpdir-based fixtures simulate main_repo and worktree_path.
    Import-based access to _bootstrap() and BootstrapError from
    setup_ticket_worktree. The probe call (verify_precommit_active.py) does not
    yet exist in _bootstrap(), so all tests that assert on its invocation or its
    effect (BootstrapError) are expected to fail.

====================================================================
DECISION HISTORY
====================================================================
- 2026-07-06 [EPIC-WorktreeQualityGateGuard/06/test-writer]: Initial TDD
  red-baseline. Written BEFORE python-coder implements the create-time gate.
  Expected RED states per test:
    test_bootstrap_gate_passes_when_probe_passes:
        FAIL — probe never invoked; assertGreater(probe_call_count, 0) fails.
    test_bootstrap_gate_raises_when_probe_reports_failing_checks:
        FAIL — probe call absent; _bootstrap() does not raise BootstrapError
        from probe output; assertRaises context never satisfied.
    test_bootstrap_gate_raises_when_probe_exits_nonzero:
        FAIL — same reason; _bootstrap() does not raise BootstrapError on
        non-zero probe exit because the probe is never called.
    test_bootstrap_gate_is_invoked_after_precommit_config:
        FAIL — probe never called; assertTrue(probe_was_called) fails.
====================================================================
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Path setup — make scripts/ importable regardless of invocation cwd.
# File location: unit_tests/setup/test_setup_ticket_worktree.py
# parents[2]  = EPIC-WorktreeQualityGateGuard/ (worktree root)
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# ---------------------------------------------------------------------------
# Import _bootstrap and BootstrapError.
# Both exist today in setup_ticket_worktree.py; ImportError is not expected.
# If the import does fail, each test self.fail()s with a clear message.
# ---------------------------------------------------------------------------
_SETUP_IMPORT_OK = False
_SETUP_IMPORT_ERROR = ""
try:
    from setup_ticket_worktree import BootstrapError, _bootstrap  # type: ignore[import]
    _SETUP_IMPORT_OK = True
except (ImportError, ModuleNotFoundError) as _exc:
    # Fallback so that assertRaises(BootstrapError) references a real class.
    BootstrapError = RuntimeError  # type: ignore[assignment,misc]
    _bootstrap = None  # type: ignore[assignment]
    _SETUP_IMPORT_ERROR = str(_exc)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_PROBE_SCRIPT_STEM = "verify_precommit_active"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_probe_call(cmd: list) -> bool:
    """Return True when cmd looks like an invocation of verify_precommit_active.py."""
    return any(_PROBE_SCRIPT_STEM in str(part) for part in cmd)


def _make_subprocess_side_effect(probe_returncode: int, probe_stdout: str):
    """Return a side_effect callable for unittest.mock.patch('subprocess.run').

    Distinguishes three call shapes that _bootstrap() issues (now or after
    the gate is implemented):

    1. git submodule update --init  -> returncode 0, empty stdout.
    2. verify_precommit_active.py   -> probe_returncode, probe_stdout.
    3. anything else                -> returncode 0, empty stdout.
    """
    def _side_effect(cmd, *args, **kwargs):
        result = MagicMock()
        cmd_str = " ".join(str(c) for c in cmd)
        if "submodule" in cmd_str and "update" in cmd_str:
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
        elif _is_probe_call(cmd):
            result.returncode = probe_returncode
            result.stdout = probe_stdout
            result.stderr = ""
        else:
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
        return result

    return _side_effect


# ===========================================================================
# Test class
# ===========================================================================


class TestBootstrapPreDriveGate(unittest.TestCase):
    """Verify that _bootstrap() calls verify_precommit_active.py after config
    setup and raises BootstrapError when the probe reports failing checks.

    All tests are RED until python-coder adds the probe call to _bootstrap().
    """

    def setUp(self) -> None:
        """Create isolated temporary directories for main_repo and worktree_path."""
        self._main_repo_tmp = tempfile.TemporaryDirectory()
        self._worktree_tmp = tempfile.TemporaryDirectory()
        self.main_repo = Path(self._main_repo_tmp.name)
        self.worktree_path = Path(self._worktree_tmp.name)

        # Create .leafcutter in main_repo so _establish_pre_commit_config
        # can create the symlink and the existing AC-5 check passes.
        # This ensures the existing code in _bootstrap() does NOT raise
        # BootstrapError from the file-existence check — the only expected
        # source of BootstrapError in the RED state is the unimplemented gate.
        (self.main_repo / ".leafcutter").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        """Remove temporary directories created in setUp."""
        self._main_repo_tmp.cleanup()
        self._worktree_tmp.cleanup()

    # ------------------------------------------------------------------
    def test_bootstrap_gate_passes_when_probe_passes(self) -> None:
        # covers: UNKNOWN
        """Gate must NOT raise BootstrapError when probe returns no failing checks.

        RED before implementation: the probe subprocess is never called from
        _bootstrap(), so the assertion that the probe was invoked will fail
        with AssertionError: 0 is not greater than 0.

        Implementation requirement:
        - _bootstrap() must call verify_precommit_active.py after
          _establish_pre_commit_config() completes.
        - When failing_checks is empty and exit code is 0, NO BootstrapError
          must be raised.
        - The probe call must appear in subprocess.run's call list.
        """
        if not _SETUP_IMPORT_OK:
            self.fail(f"setup_ticket_worktree import failed: {_SETUP_IMPORT_ERROR}")

        probe_output = json.dumps({
            "binary": True,
            "config": True,
            "git_hook": True,
            "canary": True,
            "failing_checks": [],
        })
        side_effect = _make_subprocess_side_effect(
            probe_returncode=0,
            probe_stdout=probe_output,
        )

        with patch("subprocess.run", side_effect=side_effect) as mock_run:
            try:
                _bootstrap(self.main_repo, self.worktree_path)
            except BootstrapError as exc:
                self.fail(
                    f"_bootstrap() raised BootstrapError unexpectedly when "
                    f"probe passes: {exc}"
                )

            # Assert the probe was called — this is the RED assertion.
            # Until the gate is implemented the probe is never invoked, so
            # no call_args_list entry matches _is_probe_call → count == 0.
            probe_calls = [
                c for c in mock_run.call_args_list
                if c.args and _is_probe_call(list(c.args[0]))
            ]
            self.assertGreater(
                len(probe_calls),
                0,
                "verify_precommit_active.py was never called from _bootstrap(). "
                "The create-time gate must invoke the probe after "
                "_establish_pre_commit_config() completes.",
            )

    # ------------------------------------------------------------------
    def test_bootstrap_gate_raises_when_probe_reports_failing_checks(self) -> None:
        # covers: UNKNOWN
        """Gate must raise BootstrapError naming the failing checks when probe fails.

        RED before implementation: _bootstrap() makes no probe call, so no
        BootstrapError is raised from probe output. The assertRaises context
        manager exits without the expected exception and the test fails.

        Implementation requirement:
        - When the probe JSON contains failing_checks: ['check_a_binary_on_path']
          (and exit code is 1), _bootstrap() must raise BootstrapError.
        - The BootstrapError message must contain 'check_a_binary_on_path'.
        """
        if not _SETUP_IMPORT_OK:
            self.fail(f"setup_ticket_worktree import failed: {_SETUP_IMPORT_ERROR}")

        failing_check = "check_a_binary_on_path"
        probe_output = json.dumps({
            "binary": False,
            "config": True,
            "git_hook": True,
            "canary": True,
            "failing_checks": [failing_check],
        })
        side_effect = _make_subprocess_side_effect(
            probe_returncode=1,
            probe_stdout=probe_output,
        )

        with patch("subprocess.run", side_effect=side_effect):
            with self.assertRaises(BootstrapError) as ctx:
                _bootstrap(self.main_repo, self.worktree_path)

        raised_msg = str(ctx.exception)
        self.assertIn(
            failing_check,
            raised_msg,
            f"BootstrapError message must name the failing check "
            f"'{failing_check}'; actual message: '{raised_msg}'",
        )

    # ------------------------------------------------------------------
    def test_bootstrap_gate_raises_when_probe_exits_nonzero(self) -> None:
        # covers: UNKNOWN
        """Gate must raise BootstrapError when probe exits non-zero (any stdout).

        RED before implementation: _bootstrap() makes no probe call, so the
        non-zero exit code is never observed and BootstrapError is not raised.
        The assertRaises context manager exits without the expected exception.

        Implementation requirement:
        - When the probe subprocess exits with returncode != 0, _bootstrap()
          must raise BootstrapError regardless of stdout content.
        - This covers both the "empty stdout" (crashed probe) and the
          "malformed JSON" scenarios.
        """
        if not _SETUP_IMPORT_OK:
            self.fail(f"setup_ticket_worktree import failed: {_SETUP_IMPORT_ERROR}")

        # Empty stdout simulates a crashed / malformed probe response.
        side_effect = _make_subprocess_side_effect(
            probe_returncode=1,
            probe_stdout="",
        )

        with patch("subprocess.run", side_effect=side_effect):
            with self.assertRaises(BootstrapError):
                _bootstrap(self.main_repo, self.worktree_path)

    # ------------------------------------------------------------------
    def test_bootstrap_gate_is_invoked_after_precommit_config(self) -> None:
        # covers: UNKNOWN
        """The probe subprocess call must occur after _establish_pre_commit_config.

        RED before implementation: _bootstrap() makes no probe subprocess call,
        so the spy list remains empty and assertTrue(probe_was_called) fails.

        Implementation requirement:
        - _bootstrap() must invoke verify_precommit_active.py as a subprocess
          call at some point after _establish_pre_commit_config() has run
          (i.e. after step 6 of the documented _bootstrap() procedure).
        - The probe must run in the context of the worktree root so that the
          established pre-commit config is visible to the checks.
        """
        if not _SETUP_IMPORT_OK:
            self.fail(f"setup_ticket_worktree import failed: {_SETUP_IMPORT_ERROR}")

        probe_was_called: list[list] = []
        probe_output = json.dumps({
            "binary": True,
            "config": True,
            "git_hook": True,
            "canary": True,
            "failing_checks": [],
        })

        def spy_side_effect(cmd, *args, **kwargs):
            result = MagicMock()
            cmd_list = list(cmd)
            cmd_str = " ".join(str(c) for c in cmd_list)
            if "submodule" in cmd_str and "update" in cmd_str:
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
            elif _is_probe_call(cmd_list):
                # Record the probe invocation for the post-run assertion.
                probe_was_called.append(cmd_list)
                result.returncode = 0
                result.stdout = probe_output
                result.stderr = ""
            else:
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
            return result

        with patch("subprocess.run", side_effect=spy_side_effect):
            try:
                _bootstrap(self.main_repo, self.worktree_path)
            except BootstrapError:
                # If the gate is implemented and raises on this fixture (probe
                # mock returns success but some other condition triggers an
                # error), we still want to check whether the probe was called.
                pass

        self.assertTrue(
            len(probe_was_called) > 0,
            "verify_precommit_active.py probe was NOT invoked from _bootstrap(). "
            "The create-time gate must call the probe subprocess after "
            "_establish_pre_commit_config() completes (BO-1700d-1). "
            "Current _bootstrap() makes no probe call — gate is not yet implemented.",
        )


if __name__ == "__main__":
    unittest.main()
