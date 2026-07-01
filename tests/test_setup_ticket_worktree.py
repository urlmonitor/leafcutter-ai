"""
Tests for _bootstrap() in templates/scripts/setup_ticket_worktree.py.

These are TDD stubs written BEFORE python-coder implements the symlink feature.
All new tests in this file are expected to be RED (failing) until python-coder
replaces the shutil.copy call for .env with os.symlink + OSError fallback.

Tests use unittest.mock.patch to avoid filesystem or subprocess calls.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SETUP_SCRIPT = _REPO_ROOT / "templates" / "scripts" / "setup_ticket_worktree.py"
_SCRIPTS_SETUP_SCRIPT = _REPO_ROOT / "scripts" / "setup_ticket_worktree.py"


def _load_setup_module():
    """Load setup_ticket_worktree from its absolute path."""
    scripts_dir = str(_REPO_ROOT / "templates" / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(
        "setup_ticket_worktree", _SETUP_SCRIPT
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["setup_ticket_worktree"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestBootstrapEnvIsSymlinked(unittest.TestCase):
    """_bootstrap() creates a symlink for .env, not a copy."""

    def test_bootstrap_env_is_symlinked(self):
        """
        Given the main_repo/.env file exists,
        When _bootstrap() is called,
        Then os.symlink is called with (main_repo/.env, worktree/.env)
        And shutil.copy is NOT called for .env.
        """
        import tempfile

        mod = _load_setup_module()

        with tempfile.TemporaryDirectory() as tmp:
            main_repo = Path(tmp) / "main"
            worktree = Path(tmp) / "worktree"
            main_repo.mkdir()
            worktree.mkdir()

            # Pre-create the config so the AC-5 probe passes
            (worktree / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")

            with (
                patch.object(mod.os, "symlink") as mock_symlink,
                patch.object(mod.shutil, "copy") as mock_copy,
                patch.object(mod.subprocess, "run"),
            ):
                mod._bootstrap(main_repo, worktree)

        # os.symlink must be called for .env
        mock_symlink.assert_any_call(main_repo / ".env", worktree / ".env")

        # shutil.copy must NOT be called for .env
        copy_calls_for_env = [
            c for c in mock_copy.call_args_list if ".env" in str(c)
        ]
        self.assertEqual(
            copy_calls_for_env,
            [],
            "shutil.copy should not be called for .env when symlink succeeds",
        )


class TestBootstrapEnvSymlinkSkippedWhenMissing(unittest.TestCase):
    """_bootstrap() silently skips .env when the source does not exist."""

    def test_bootstrap_env_symlink_skipped_when_missing(self):
        """
        Given main_repo/.env does not exist (os.symlink raises FileNotFoundError),
        When _bootstrap() is called,
        Then no exception propagates and no .env symlink/copy is created.
        """
        import tempfile

        mod = _load_setup_module()

        with tempfile.TemporaryDirectory() as tmp:
            main_repo = Path(tmp) / "main"
            worktree = Path(tmp) / "worktree"
            main_repo.mkdir()
            worktree.mkdir()

            # Pre-create the config so the AC-5 probe passes
            (worktree / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")

            with (
                patch.object(
                    mod.os, "symlink", side_effect=FileNotFoundError("no such file")
                ),
                patch.object(mod.shutil, "copy") as mock_copy,
                patch.object(mod.subprocess, "run"),
            ):
                # Must not raise
                mod._bootstrap(main_repo, worktree)

        # shutil.copy should not be called for .env as a fallback for
        # FileNotFoundError (source simply doesn't exist)
        copy_calls_for_env = [
            c for c in mock_copy.call_args_list if ".env" in str(c)
        ]
        self.assertEqual(
            copy_calls_for_env,
            [],
            "shutil.copy should not be called for .env when source is missing",
        )


class TestBootstrapEnvFallbackOnOSError(unittest.TestCase):
    """_bootstrap() falls back to shutil.copy when os.symlink raises OSError."""

    def test_bootstrap_env_fallback_on_oserror(self):
        """
        Given os.symlink raises OSError (e.g. WinError 1314 or EPERM),
        When _bootstrap() is called,
        Then shutil.copy is called for .env as fallback
        And a warning is printed to stderr.
        """
        import io
        import tempfile

        mod = _load_setup_module()

        win_err = OSError(1314, "A required privilege is not held by the client")

        fake_stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as tmp:
            main_repo = Path(tmp) / "main"
            worktree = Path(tmp) / "worktree"
            main_repo.mkdir()
            worktree.mkdir()

            # Pre-create the config so the AC-5 probe passes
            (worktree / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")

            with (
                patch.object(mod.os, "symlink", side_effect=win_err),
                patch.object(mod.shutil, "copy") as mock_copy,
                patch.object(mod.subprocess, "run"),
                patch("sys.stderr", fake_stderr),
            ):
                mod._bootstrap(main_repo, worktree)

        # shutil.copy must be called for .env as fallback
        mock_copy.assert_any_call(main_repo / ".env", worktree / ".env")

        # A warning must have been written to stderr
        warning_output = fake_stderr.getvalue()
        self.assertTrue(
            len(warning_output) > 0,
            "A warning should be printed to stderr when falling back from symlink to copy",
        )


class TestBootstrapMcpJsonStillCopied(unittest.TestCase):
    """_bootstrap() always copies .mcp.json, never symlinks it."""

    def test_bootstrap_mcp_json_still_copied(self):
        """
        Given main_repo/.mcp.json exists,
        When _bootstrap() is called,
        Then shutil.copy is called for .mcp.json (regardless of the .env path).
        """
        import tempfile

        mod = _load_setup_module()

        with tempfile.TemporaryDirectory() as tmp:
            main_repo = Path(tmp) / "main"
            worktree = Path(tmp) / "worktree"
            main_repo.mkdir()
            worktree.mkdir()

            # Pre-create the config so the AC-5 probe passes
            (worktree / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")

            with (
                patch.object(mod.os, "symlink"),
                patch.object(mod.shutil, "copy") as mock_copy,
                patch.object(mod.subprocess, "run"),
            ):
                mod._bootstrap(main_repo, worktree)

        # shutil.copy must be called for .mcp.json
        mock_copy.assert_any_call(main_repo / ".mcp.json", worktree / ".mcp.json")


class TestSetupTicketDoesNotMoveTicketFile(unittest.TestCase):
    """cmd_setup_ticket() never calls git mv — ticket stays in its original folder."""

    def test_setup_ticket_does_not_move_ticket_file(self):
        """
        Given setup-ticket is called with a ticket in 00_inbox/,
        When the script exits 0,
        Then git mv was never called and the returned JSON contains the
        original 00_inbox/ path in ticket_path_final.
        """
        mod = _load_setup_module()

        # Fake ticket in 00_inbox/
        ticket_path_str = "/fake/repo/tickets/00_inbox/TICKET-20260603-TestNoMove.md"

        git_mv_calls: list = []

        def fake_run(cmd, **kwargs):
            # Intercept any git mv call
            if isinstance(cmd, list) and "git" in cmd and "mv" in cmd:
                git_mv_calls.append(cmd)
                raise AssertionError  # git mv must not be called
            mock_result = MagicMock()
            if cmd[0] == "git" and cmd[1:3] == ["rev-parse", "--show-toplevel"]:
                mock_result.stdout = "/fake/repo\n"
                mock_result.returncode = 0
            elif cmd[0] == "git" and cmd[1:3] == ["worktree", "list"]:
                mock_result.stdout = ""
                mock_result.returncode = 0
            elif cmd[0] == "git" and cmd[1:3] == ["worktree", "add"]:
                mock_result.returncode = 0
            else:
                mock_result.returncode = 0
            return mock_result

        import io
        fake_stdout = io.StringIO()

        with (
            patch.object(mod.subprocess, "run", side_effect=fake_run),
            patch("sys.stdout", fake_stdout),
            patch.object(mod.os, "chdir"),
            patch.object(mod.Path, "mkdir"),
            patch.object(mod, "_bootstrap"),
            patch.object(mod, "_install_drift_hook"),
            patch.object(mod, "_install_pre_commit_shims"),
            patch.object(mod, "_worktree_exists", return_value=(False, None)),
            patch.object(mod, "_create_worktree", return_value=Path("/fake/worktrees/testnomore")),
            patch.object(mod, "_git_toplevel", return_value=Path("/fake/repo")),
        ):
            import argparse as ap
            args = ap.Namespace(ticket_path=ticket_path_str, branch=None)
            mod.cmd_setup_ticket(args)

        # git mv must never have been called
        self.assertEqual(git_mv_calls, [], "git mv must not be called by setup_ticket()")

        # Returned JSON must contain original 00_inbox/ path
        output = fake_stdout.getvalue().strip()
        import json as _json
        payload = _json.loads(output)
        self.assertIn("ticket_path_final", payload)
        self.assertIn("00_inbox", payload["ticket_path_final"])
        # Must NOT contain 01_todo
        self.assertNotIn("01_todo", payload["ticket_path_final"])

    def test_setup_ticket_accepts_01_todo_ticket(self):
        """
        Given setup-ticket is called with a ticket already in 01_todo/,
        When the script exits 0,
        Then the ticket file remains in 01_todo/ and no git mv is issued.
        """
        mod = _load_setup_module()

        ticket_path_str = "/fake/repo/tickets/01_todo/TICKET-20260603-AlreadyInTodo.md"

        git_mv_calls: list = []

        def fake_run(cmd, **kwargs):
            if isinstance(cmd, list) and "git" in cmd and "mv" in cmd:
                git_mv_calls.append(cmd)
                raise AssertionError  # git mv must not be called
            mock_result = MagicMock()
            if cmd[0] == "git" and cmd[1:3] == ["rev-parse", "--show-toplevel"]:
                mock_result.stdout = "/fake/repo\n"
            return mock_result

        import io
        fake_stdout = io.StringIO()

        with (
            patch.object(mod.subprocess, "run", side_effect=fake_run),
            patch("sys.stdout", fake_stdout),
            patch.object(mod.os, "chdir"),
            patch.object(mod.Path, "mkdir"),
            patch.object(mod, "_bootstrap"),
            patch.object(mod, "_install_drift_hook"),
            patch.object(mod, "_install_pre_commit_shims"),
            patch.object(mod, "_worktree_exists", return_value=(False, None)),
            patch.object(mod, "_create_worktree", return_value=Path("/fake/worktrees/alreadyintodo")),
            patch.object(mod, "_git_toplevel", return_value=Path("/fake/repo")),
        ):
            import argparse as ap
            args = ap.Namespace(ticket_path=ticket_path_str, branch=None)
            mod.cmd_setup_ticket(args)

        self.assertEqual(git_mv_calls, [], "git mv must not be called")

        output = fake_stdout.getvalue().strip()
        import json as _json
        payload = _json.loads(output)
        self.assertIn("ticket_path_final", payload)
        self.assertIn("01_todo", payload["ticket_path_final"])

    def test_move_ticket_function_absent(self):
        """
        Given setup_ticket_worktree.py is loaded,
        When _move_ticket is searched for in the module,
        Then the attribute does not exist (zero matches).
        """
        mod = _load_setup_module()
        self.assertFalse(
            hasattr(mod, "_move_ticket"),
            "_move_ticket function must not exist in the module after removal",
        )


class TestBootstrapRunsBuildPy(unittest.TestCase):
    """_bootstrap() runs build.py when present, skips with warning when absent."""

    def test_bootstrap_runs_build_py_when_present(self):
        """
        Given scripts/build.py exists in main_repo,
        When _bootstrap() is called,
        Then subprocess.run is called with a command list containing 'build.py'
        and '--target-dir'.
        """
        # covers: UNKNOWN
        mod = _load_setup_module()

        main_repo = Path("/fake/main")
        worktree = Path("/fake/worktree")

        def fake_path_exists(self_path):
            """Return True for any path — including build.py."""
            return True

        with (
            patch.object(mod.os, "symlink"),
            patch.object(mod.shutil, "copy"),
            patch.object(mod.subprocess, "run") as mock_run,
            patch.object(mod.Path, "exists", fake_path_exists),
        ):
            mod._bootstrap(main_repo, worktree)

        # Collect all cmd lists passed to subprocess.run
        all_cmds = [str(c) for c in mock_run.call_args_list]
        build_calls = [c for c in all_cmds if "build.py" in c and "--target-dir" in c]
        self.assertTrue(
            len(build_calls) > 0,
            f"subprocess.run was not called with build.py and --target-dir. "
            f"All calls: {all_cmds}",
        )

    def test_bootstrap_skips_build_py_when_absent(self):
        """
        Given scripts/build.py does NOT exist in main_repo,
        When _bootstrap() is called,
        Then no subprocess.run call containing 'build.py' is made,
        and a warning is emitted to stderr.
        """
        # covers: UNKNOWN
        mod = _load_setup_module()

        main_repo = Path("/fake/main")
        worktree = Path("/fake/worktree")

        import io
        fake_stderr = io.StringIO()

        def fake_path_exists(self_path):
            """Return False for build.py, True for everything else."""
            return "build.py" not in str(self_path)

        with (
            patch.object(mod.os, "symlink"),
            patch.object(mod.shutil, "copy"),
            patch.object(mod.subprocess, "run") as mock_run,
            patch.object(mod.Path, "exists", fake_path_exists),
            patch("sys.stderr", fake_stderr),
        ):
            mod._bootstrap(main_repo, worktree)

        # No subprocess.run call for build.py
        all_cmds = [str(c) for c in mock_run.call_args_list]
        build_calls = [c for c in all_cmds if "build.py" in c]
        self.assertEqual(
            build_calls,
            [],
            f"subprocess.run must not be called with build.py when it is absent. "
            f"All calls: {all_cmds}",
        )

        # A warning must have been written to stderr
        warning_output = fake_stderr.getvalue()
        self.assertIn(
            "WARNING",
            warning_output,
            "A WARNING must be printed to stderr when build.py is absent",
        )


def _load_scripts_setup_module():
    """Load setup_ticket_worktree from scripts/ (the canonical source, not templates/)."""
    module_name = "setup_ticket_worktree_scripts"
    spec = importlib.util.spec_from_file_location(
        module_name, _SCRIPTS_SETUP_SCRIPT
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests for ticket 07: Detect dependency manager + non-fatal install failures
# (scripts/setup_ticket_worktree.py — canonical source copy)
# ---------------------------------------------------------------------------


class TestBootstrapPoetryRepo(unittest.TestCase):
    """_bootstrap() selects 'poetry install --no-root' when pyproject.toml is present (AC-1)."""

    def test_bootstrap_uses_poetry_when_pyproject_toml_present(self):
        """
        Given a worktree whose root contains pyproject.toml,
        When _bootstrap() is called,
        Then subprocess.run is called with ['poetry', 'install', '--no-root']
        and pip is NOT invoked.

        STUB — fails until python-coder implements manifest detection.
        """
        mod = _load_scripts_setup_module()

        main_repo = Path("/fake/main")
        worktree = Path("/fake/worktree")

        def fake_exists(self_path):
            # pyproject.toml present; requirements files absent
            if "pyproject.toml" in str(self_path):
                return True
            if "requirements" in str(self_path):
                return False
            return True  # build.py and others exist

        with (
            patch.object(mod.os, "symlink"),
            patch.object(mod.shutil, "copy"),
            patch.object(mod.subprocess, "run") as mock_run,
            patch.object(mod.Path, "exists", fake_exists),
        ):
            mod._bootstrap(main_repo, worktree)

        all_cmds = [str(c) for c in mock_run.call_args_list]
        poetry_calls = [c for c in all_cmds if "poetry" in c and "install" in c]
        pip_calls = [c for c in all_cmds if "pip" in c and "install" in c]

        self.assertTrue(
            len(poetry_calls) > 0,
            f"Expected subprocess.run with poetry install; calls: {all_cmds}",
        )
        self.assertEqual(
            pip_calls,
            [],
            f"pip install must not be called when pyproject.toml is present; calls: {all_cmds}",
        )


class TestBootstrapPipRepo(unittest.TestCase):
    """_bootstrap() uses 'pip install -r requirements-dev.txt' when that file is present (AC-1)."""

    def test_bootstrap_uses_pip_when_requirements_dev_txt_present(self):
        """
        Given a worktree whose root contains requirements-dev.txt but NOT pyproject.toml,
        When _bootstrap() is called,
        Then subprocess.run is called with [python, '-m', 'pip', 'install', '-r', ...]
        and poetry is NOT invoked.

        STUB — fails until python-coder implements manifest detection.
        """
        mod = _load_scripts_setup_module()

        main_repo = Path("/fake/main")
        worktree = Path("/fake/worktree")

        def fake_exists(self_path):
            path_str = str(self_path)
            if "pyproject.toml" in path_str:
                return False
            if "requirements-dev.txt" in path_str:
                return True
            if "requirements.txt" in path_str:
                return True
            return True  # build.py and others exist

        with (
            patch.object(mod.os, "symlink"),
            patch.object(mod.shutil, "copy"),
            patch.object(mod.subprocess, "run") as mock_run,
            patch.object(mod.Path, "exists", fake_exists),
        ):
            mod._bootstrap(main_repo, worktree)

        all_cmds = [str(c) for c in mock_run.call_args_list]
        pip_calls = [c for c in all_cmds if "pip" in c and "install" in c]
        poetry_calls = [c for c in all_cmds if "poetry" in c]

        self.assertTrue(
            len(pip_calls) > 0,
            f"Expected subprocess.run with pip install -r; calls: {all_cmds}",
        )
        self.assertEqual(
            poetry_calls,
            [],
            f"poetry must not be called when pyproject.toml is absent; calls: {all_cmds}",
        )


class TestBootstrapNoManifestRepo(unittest.TestCase):
    """_bootstrap() skips the dep-install step when neither pyproject.toml nor requirements*.txt exist (AC-1)."""

    def test_bootstrap_skips_dep_install_when_no_manifest(self):
        """
        Given a worktree with no pyproject.toml and no requirements*.txt,
        When _bootstrap() is called,
        Then no subprocess.run call invokes 'poetry' or 'pip install'.

        STUB — fails until python-coder implements manifest detection.
        """
        mod = _load_scripts_setup_module()

        main_repo = Path("/fake/main")
        worktree = Path("/fake/worktree")

        def fake_exists(self_path):
            path_str = str(self_path)
            if "pyproject.toml" in path_str:
                return False
            if "requirements" in path_str:
                return False
            return True  # build.py present

        with (
            patch.object(mod.os, "symlink"),
            patch.object(mod.shutil, "copy"),
            patch.object(mod.subprocess, "run") as mock_run,
            patch.object(mod.Path, "exists", fake_exists),
        ):
            mod._bootstrap(main_repo, worktree)

        all_cmds = [str(c) for c in mock_run.call_args_list]
        dep_calls = [
            c for c in all_cmds
            if ("poetry" in c and "install" in c) or ("pip" in c and "install" in c)
        ]

        self.assertEqual(
            dep_calls,
            [],
            f"No dep-install call expected when no manifest exists; calls: {all_cmds}",
        )


class TestBootstrapInstallFailureNonFatal(unittest.TestCase):
    """A dependency install failure must be logged as WARNING and NOT abort bootstrap (AC-2)."""

    def test_bootstrap_install_failure_is_non_fatal(self):
        """
        Given the dependency install command exits non-zero (CalledProcessError),
        When _bootstrap() is called,
        Then no exception propagates to the caller,
        AND a WARNING is printed to stderr,
        AND build.py is still executed afterwards (bootstrap continues).

        STUB — fails until python-coder wraps the install in try/except+warn+continue.
        """
        import io

        mod = _load_scripts_setup_module()

        main_repo = Path("/fake/main")
        worktree = Path("/fake/worktree")

        fake_stderr = io.StringIO()

        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd) if isinstance(cmd, list) else str(cmd)
            if "poetry" in cmd_str and "install" in cmd_str:
                raise subprocess.CalledProcessError(1, cmd)
            if "pip" in cmd_str and "install" in cmd_str:
                raise subprocess.CalledProcessError(1, cmd)
            # All other calls succeed
            return MagicMock(returncode=0)

        def fake_exists(self_path):
            # pyproject.toml present so we trigger poetry path
            if "pyproject.toml" in str(self_path):
                return True
            return True

        with (
            patch.object(mod.os, "symlink"),
            patch.object(mod.shutil, "copy"),
            patch.object(mod.subprocess, "run", side_effect=fake_run),
            patch.object(mod.Path, "exists", fake_exists),
            patch("sys.stderr", fake_stderr),
        ):
            # Must NOT raise; if the current code re-raises, this will fail
            try:
                mod._bootstrap(main_repo, worktree)
            except (subprocess.SubprocessError, subprocess.CalledProcessError) as exc:
                self.fail(
                    f"_bootstrap() must not re-raise a dep-install failure; got: {exc}"
                )

        warning_output = fake_stderr.getvalue()
        self.assertIn(
            "WARNING",
            warning_output,
            "A WARNING must be emitted to stderr when dep install fails",
        )


# ---------------------------------------------------------------------------
# Mirror tests: templates/scripts/setup_ticket_worktree.py must match (AC-4)
# ---------------------------------------------------------------------------


class TestTemplateBootstrapPoetryRepo(unittest.TestCase):
    """templates/scripts/_bootstrap() also selects poetry when pyproject.toml present (AC-4)."""

    def test_template_bootstrap_uses_poetry_when_pyproject_toml_present(self):
        """
        Given pyproject.toml present in templates/ copy,
        When _bootstrap() is called,
        Then subprocess.run includes poetry install.

        STUB — fails until the fix is mirrored to templates/scripts/.
        """
        mod = _load_setup_module()

        main_repo = Path("/fake/main")
        worktree = Path("/fake/worktree")

        def fake_exists(self_path):
            if "pyproject.toml" in str(self_path):
                return True
            if "requirements" in str(self_path):
                return False
            return True

        with (
            patch.object(mod.os, "symlink"),
            patch.object(mod.shutil, "copy"),
            patch.object(mod.subprocess, "run") as mock_run,
            patch.object(mod.Path, "exists", fake_exists),
        ):
            mod._bootstrap(main_repo, worktree)

        all_cmds = [str(c) for c in mock_run.call_args_list]
        poetry_calls = [c for c in all_cmds if "poetry" in c and "install" in c]
        self.assertTrue(
            len(poetry_calls) > 0,
            f"templates/ copy must also use poetry when pyproject.toml present; calls: {all_cmds}",
        )


class TestTemplateBootstrapInstallFailureNonFatal(unittest.TestCase):
    """templates/scripts/_bootstrap() also makes install failures non-fatal (AC-4)."""

    def test_template_bootstrap_install_failure_is_non_fatal(self):
        """
        Given the dep install fails in the templates/ copy,
        When _bootstrap() is called,
        Then no exception propagates and a WARNING is emitted.

        STUB — fails until the fix is mirrored to templates/scripts/.
        """
        import io

        mod = _load_setup_module()

        main_repo = Path("/fake/main")
        worktree = Path("/fake/worktree")

        fake_stderr = io.StringIO()

        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd) if isinstance(cmd, list) else str(cmd)
            if "poetry" in cmd_str and "install" in cmd_str:
                raise subprocess.CalledProcessError(1, cmd)
            if "pip" in cmd_str and "install" in cmd_str:
                raise subprocess.CalledProcessError(1, cmd)
            return MagicMock(returncode=0)

        def fake_exists(self_path):
            if "pyproject.toml" in str(self_path):
                return True
            return True

        with (
            patch.object(mod.os, "symlink"),
            patch.object(mod.shutil, "copy"),
            patch.object(mod.subprocess, "run", side_effect=fake_run),
            patch.object(mod.Path, "exists", fake_exists),
            patch("sys.stderr", fake_stderr),
        ):
            try:
                mod._bootstrap(main_repo, worktree)
            except (subprocess.SubprocessError, subprocess.CalledProcessError) as exc:
                self.fail(
                    f"templates/_bootstrap() must not re-raise a dep-install failure; got: {exc}"
                )

        warning_output = fake_stderr.getvalue()
        self.assertIn(
            "WARNING",
            warning_output,
            "templates/ copy must emit WARNING when dep install fails",
        )


# ---------------------------------------------------------------------------
# Post-hoc verification tests for TICKET-20260617-Worktree_Precommit_Bootstrap
# (AC-1, AC-2, AC-3, AC-5 coverage)
# These tests verify the IMPLEMENTED behavior — they must pass GREEN.
# ---------------------------------------------------------------------------


class TestBootstrapErrorClassmethod(unittest.TestCase):
    """Unit tests for BootstrapError.missing_config factory and class hierarchy."""

    def test_ac5_bootstrap_error_is_runtime_error_subclass(self):
        # covers: UNKNOWN
        """BootstrapError must be a RuntimeError subclass (AC-5 structured error)."""
        mod = _load_scripts_setup_module()
        self.assertTrue(
            issubclass(mod.BootstrapError, RuntimeError),
            "BootstrapError must subclass RuntimeError",
        )

    def test_ac5_missing_config_without_build_exc(self):
        # covers: UNKNOWN
        """missing_config(path, build_exc=None) must produce a message referencing the path
        without mentioning 'build.py failed'."""
        mod = _load_scripts_setup_module()
        path = Path("/fake/worktree/.pre-commit-config.yaml")
        err = mod.BootstrapError.missing_config(path)
        self.assertIsInstance(err, mod.BootstrapError)
        msg = str(err)
        self.assertIn("AC-5", msg, "Error message must contain AC-5 tag")
        self.assertIn(str(path), msg, "Error message must name the missing path")
        self.assertNotIn(
            "build.py failed",
            msg,
            "Message must not claim build.py failed when build_exc is None",
        )

    def test_ac5_missing_config_with_build_exc_names_build_failure(self):
        # covers: UNKNOWN
        """missing_config(path, build_exc=<exc>) must produce a message containing 'build.py failed'."""
        mod = _load_scripts_setup_module()
        path = Path("/fake/worktree/.pre-commit-config.yaml")
        build_exc = subprocess.CalledProcessError(1, ["python", "build.py"])
        err = mod.BootstrapError.missing_config(path, build_exc=build_exc)
        self.assertIsInstance(err, mod.BootstrapError)
        msg = str(err)
        self.assertIn("AC-5", msg, "Error message must contain AC-5 tag")
        self.assertIn(
            "build.py failed",
            msg,
            "Error message must contain 'build.py failed' when build_exc is provided",
        )


class TestBootstrapAC5RaisesWhenConfigAbsent(unittest.TestCase):
    """AC-5: _bootstrap raises BootstrapError when .pre-commit-config.yaml is absent
    after the build step.  Uses tmp_path-based real directories so Path.exists()
    is reliable, and monkeypatches subprocess.run."""

    def _make_fake_run(self, mod, worktree_path: Path, *, raise_on_build: bool = False):
        """Return a fake subprocess.run that handles git/dep calls and optionally
        raises CalledProcessError when build.py is invoked."""

        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd) if isinstance(cmd, list) else str(cmd)
            if "submodule" in cmd_str:
                return MagicMock(returncode=0)
            if "poetry" in cmd_str or "pip" in cmd_str:
                return MagicMock(returncode=0)
            if "build.py" in cmd_str and "--target-dir" in cmd_str:
                if raise_on_build:
                    raise subprocess.CalledProcessError(1, cmd)
                # Do NOT create .pre-commit-config.yaml — leave it absent
                return MagicMock(returncode=0)
            return MagicMock(returncode=0)

        return fake_run

    def test_ac5_raises_when_build_ran_but_config_absent(self):
        # covers: UNKNOWN
        """AC-5(a): build.py was found and ran (exit 0) but produced no config — BootstrapError raised."""
        import tempfile

        mod = _load_scripts_setup_module()

        with tempfile.TemporaryDirectory() as tmp:
            main_repo = Path(tmp) / "main"
            worktree = Path(tmp) / "worktree"
            main_repo.mkdir()
            worktree.mkdir()

            # Create a build.py candidate so the script finds and runs it
            scripts_dir = worktree / "scripts"
            scripts_dir.mkdir()
            (scripts_dir / "build.py").write_text("# stub", encoding="utf-8")

            # No .pre-commit-config.yaml created by fake_run → probe fails
            fake_run = self._make_fake_run(mod, worktree, raise_on_build=False)

            with (
                patch.object(mod.os, "symlink"),
                patch.object(mod.shutil, "copy"),
                patch.object(mod.subprocess, "run", side_effect=fake_run),
            ):
                with self.assertRaises(mod.BootstrapError) as cm:
                    mod._bootstrap(main_repo, worktree)

            err_msg = str(cm.exception)
            self.assertIn("AC-5", err_msg)
            # build_exc is None here (build succeeded) so message should not say "failed"
            self.assertNotIn("build.py failed", err_msg)

    def test_ac5_raises_when_build_not_found(self):
        # covers: UNKNOWN
        """AC-5(b): build.py NOT found — BootstrapError STILL raised (H-1 fix: warn-and-continue removed)."""
        import tempfile

        mod = _load_scripts_setup_module()

        with tempfile.TemporaryDirectory() as tmp:
            main_repo = Path(tmp) / "main"
            worktree = Path(tmp) / "worktree"
            main_repo.mkdir()
            worktree.mkdir()

            # No build.py candidates created → build_script is None
            # No .pre-commit-config.yaml either → probe fails

            def fake_run(cmd, **kwargs):
                cmd_str = " ".join(str(c) for c in cmd) if isinstance(cmd, list) else str(cmd)
                if "submodule" in cmd_str:
                    return MagicMock(returncode=0)
                if "poetry" in cmd_str or "pip" in cmd_str:
                    return MagicMock(returncode=0)
                return MagicMock(returncode=0)

            with (
                patch.object(mod.os, "symlink"),
                patch.object(mod.shutil, "copy"),
                patch.object(mod.subprocess, "run", side_effect=fake_run),
            ):
                with self.assertRaises(mod.BootstrapError) as cm:
                    mod._bootstrap(main_repo, worktree)

            err_msg = str(cm.exception)
            self.assertIn("AC-5", err_msg)

    def test_ac5_raises_with_build_exc_when_called_process_error(self):
        # covers: UNKNOWN
        """AC-5(c): build.py raises CalledProcessError → BootstrapError raised AND message names build failure."""
        import tempfile

        mod = _load_scripts_setup_module()

        with tempfile.TemporaryDirectory() as tmp:
            main_repo = Path(tmp) / "main"
            worktree = Path(tmp) / "worktree"
            main_repo.mkdir()
            worktree.mkdir()

            # Create build.py so it is found
            scripts_dir = worktree / "scripts"
            scripts_dir.mkdir()
            (scripts_dir / "build.py").write_text("# stub", encoding="utf-8")

            # No .pre-commit-config.yaml, build raises CalledProcessError
            fake_run = self._make_fake_run(mod, worktree, raise_on_build=True)

            with (
                patch.object(mod.os, "symlink"),
                patch.object(mod.shutil, "copy"),
                patch.object(mod.subprocess, "run", side_effect=fake_run),
            ):
                with self.assertRaises(mod.BootstrapError) as cm:
                    mod._bootstrap(main_repo, worktree)

            err_msg = str(cm.exception)
            self.assertIn("AC-5", err_msg)
            self.assertIn(
                "build.py failed",
                err_msg,
                "Error message must mention 'build.py failed' when CalledProcessError was captured",
            )


class TestBootstrapAC1HappyPath(unittest.TestCase):
    """AC-1: _bootstrap returns normally when .pre-commit-config.yaml exists after the build step."""

    def test_ac1_no_bootstrap_error_when_config_present(self):
        # covers: UNKNOWN
        """AC-1: happy path — .pre-commit-config.yaml present after build → no BootstrapError."""
        import tempfile

        mod = _load_scripts_setup_module()

        with tempfile.TemporaryDirectory() as tmp:
            main_repo = Path(tmp) / "main"
            worktree = Path(tmp) / "worktree"
            main_repo.mkdir()
            worktree.mkdir()

            # Create build.py so it is found
            scripts_dir = worktree / "scripts"
            scripts_dir.mkdir()
            (scripts_dir / "build.py").write_text("# stub", encoding="utf-8")

            def fake_run(cmd, **kwargs):
                cmd_str = " ".join(str(c) for c in cmd) if isinstance(cmd, list) else str(cmd)
                if "submodule" in cmd_str:
                    return MagicMock(returncode=0)
                if "poetry" in cmd_str or "pip" in cmd_str:
                    return MagicMock(returncode=0)
                if "build.py" in cmd_str and "--target-dir" in cmd_str:
                    # Simulate a successful build: create .pre-commit-config.yaml
                    (worktree / ".pre-commit-config.yaml").write_text(
                        "repos: []\n", encoding="utf-8"
                    )
                    return MagicMock(returncode=0)
                return MagicMock(returncode=0)

            with (
                patch.object(mod.os, "symlink"),
                patch.object(mod.shutil, "copy"),
                patch.object(mod.subprocess, "run", side_effect=fake_run),
            ):
                # Must not raise
                try:
                    mod._bootstrap(main_repo, worktree)
                except mod.BootstrapError as exc:
                    self.fail(
                        f"_bootstrap() must not raise BootstrapError when "
                        f".pre-commit-config.yaml is present; got: {exc}"
                    )

    def test_ac1_config_resolvable_at_worktree_root_after_bootstrap(self):
        # covers: UNKNOWN
        """AC-1: after a successful _bootstrap, .pre-commit-config.yaml exists at the worktree root.
        This is the precondition that makes pre-commit hooks active (AC-2 probe-level coverage)."""
        import tempfile

        mod = _load_scripts_setup_module()

        with tempfile.TemporaryDirectory() as tmp:
            main_repo = Path(tmp) / "main"
            worktree = Path(tmp) / "worktree"
            main_repo.mkdir()
            worktree.mkdir()

            scripts_dir = worktree / "scripts"
            scripts_dir.mkdir()
            (scripts_dir / "build.py").write_text("# stub", encoding="utf-8")

            config_path = worktree / ".pre-commit-config.yaml"

            def fake_run(cmd, **kwargs):
                cmd_str = " ".join(str(c) for c in cmd) if isinstance(cmd, list) else str(cmd)
                if "submodule" in cmd_str:
                    return MagicMock(returncode=0)
                if "poetry" in cmd_str or "pip" in cmd_str:
                    return MagicMock(returncode=0)
                if "build.py" in cmd_str and "--target-dir" in cmd_str:
                    config_path.write_text("repos: []\n", encoding="utf-8")
                    return MagicMock(returncode=0)
                return MagicMock(returncode=0)

            with (
                patch.object(mod.os, "symlink"),
                patch.object(mod.shutil, "copy"),
                patch.object(mod.subprocess, "run", side_effect=fake_run),
            ):
                mod._bootstrap(main_repo, worktree)

            # The guarantee the probe provides: a successful _bootstrap implies
            # the config exists at the worktree root, making hooks activatable.
            # AC-2 (a real commit runs hooks) is an integration property that
            # requires an actual git repo + pre-commit install; it is documented
            # here as covered at the probe level — the probe is the necessary
            # precondition for hooks to be active in the worktree.
            self.assertTrue(
                config_path.exists(),
                f".pre-commit-config.yaml must exist at worktree root after "
                f"successful _bootstrap; path checked: {config_path}",
            )


class TestBootstrapAC3Idempotency(unittest.TestCase):
    """AC-3: bootstrap is idempotent and does not mutate the main repo."""

    def test_ac3_main_repo_tree_unchanged_after_bootstrap(self):
        # covers: UNKNOWN
        """AC-3(i): _bootstrap must not create or modify any file under main_repo."""
        import tempfile

        mod = _load_scripts_setup_module()

        with tempfile.TemporaryDirectory() as tmp:
            main_repo = Path(tmp) / "main"
            worktree = Path(tmp) / "worktree"
            main_repo.mkdir()
            worktree.mkdir()

            scripts_dir = worktree / "scripts"
            scripts_dir.mkdir()
            (scripts_dir / "build.py").write_text("# stub", encoding="utf-8")

            def fake_run(cmd, **kwargs):
                cmd_str = " ".join(str(c) for c in cmd) if isinstance(cmd, list) else str(cmd)
                if "submodule" in cmd_str:
                    return MagicMock(returncode=0)
                if "poetry" in cmd_str or "pip" in cmd_str:
                    return MagicMock(returncode=0)
                if "build.py" in cmd_str and "--target-dir" in cmd_str:
                    (worktree / ".pre-commit-config.yaml").write_text(
                        "repos: []\n", encoding="utf-8"
                    )
                    return MagicMock(returncode=0)
                return MagicMock(returncode=0)

            # Capture main_repo contents before
            def _tree_snapshot(root: Path) -> set:
                return {str(p) for p in root.rglob("*")}

            snapshot_before = _tree_snapshot(main_repo)

            with (
                patch.object(mod.os, "symlink"),
                patch.object(mod.shutil, "copy"),
                patch.object(mod.subprocess, "run", side_effect=fake_run),
            ):
                mod._bootstrap(main_repo, worktree)

            snapshot_after = _tree_snapshot(main_repo)
            self.assertEqual(
                snapshot_before,
                snapshot_after,
                f"_bootstrap() must not create/modify files under main_repo. "
                f"New files: {snapshot_after - snapshot_before}",
            )

    def test_ac3_running_successful_bootstrap_twice_is_safe(self):
        # covers: UNKNOWN
        """AC-3(ii): running _bootstrap twice on a worktree that already has the config is safe."""
        import tempfile

        mod = _load_scripts_setup_module()

        with tempfile.TemporaryDirectory() as tmp:
            main_repo = Path(tmp) / "main"
            worktree = Path(tmp) / "worktree"
            main_repo.mkdir()
            worktree.mkdir()

            scripts_dir = worktree / "scripts"
            scripts_dir.mkdir()
            (scripts_dir / "build.py").write_text("# stub", encoding="utf-8")

            # Pre-create config so both runs see it
            (worktree / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")

            def fake_run(cmd, **kwargs):
                cmd_str = " ".join(str(c) for c in cmd) if isinstance(cmd, list) else str(cmd)
                if "submodule" in cmd_str:
                    return MagicMock(returncode=0)
                if "poetry" in cmd_str or "pip" in cmd_str:
                    return MagicMock(returncode=0)
                # build.py run succeeds without re-creating the file
                return MagicMock(returncode=0)

            with (
                patch.object(mod.os, "symlink"),
                patch.object(mod.shutil, "copy"),
                patch.object(mod.subprocess, "run", side_effect=fake_run),
            ):
                try:
                    mod._bootstrap(main_repo, worktree)
                    mod._bootstrap(main_repo, worktree)
                except mod.BootstrapError as exc:
                    self.fail(
                        f"Running _bootstrap twice must be safe; got BootstrapError: {exc}"
                    )
                except Exception as exc:  # noqa: BLE001
                    self.fail(f"Running _bootstrap twice raised unexpected exception: {exc}")


class TestBootstrapAC2ProbeGuarantee(unittest.TestCase):
    """AC-2 probe-level coverage.

    AC-2 ("a real commit inside the worktree runs the hooks") is fundamentally an
    integration property that requires a real git repository, a staged file that
    violates a hook, and a pre-commit install step.  That level of integration
    test cannot be run in a pure unit environment without spawning a full git repo,
    running `pre-commit install`, and invoking `git commit`.

    This test class covers the necessary precondition that AC-2 relies on:
    a successful _bootstrap guarantees that .pre-commit-config.yaml is resolvable
    at the worktree root.  When the probe passes, hooks CAN fire; when it fails,
    BootstrapError is raised before the drive continues (ensuring AC-2 is never
    silently violated by a missing config).

    A full integration test (create git repo, pre-commit install, commit with
    violation, assert hook fires) would be correct but is out of scope for the
    unit test suite.  It is marked as MANUAL in the comment below.
    """

    def test_ac2_probe_precondition_config_present_implies_hooks_activatable(self):
        # covers: UNKNOWN
        """AC-2 probe: successful _bootstrap implies config at worktree root (necessary for hooks).

        This test verifies that the probe _bootstrap() performs is the exact
        precondition required for pre-commit hooks to be active.  If this test
        passes, the AC-5 guard is working; if AC-5 guard works, no drive can
        proceed with a silently-disabled hook config.
        """
        import tempfile

        mod = _load_scripts_setup_module()

        with tempfile.TemporaryDirectory() as tmp:
            main_repo = Path(tmp) / "main"
            worktree = Path(tmp) / "worktree"
            main_repo.mkdir()
            worktree.mkdir()

            scripts_dir = worktree / "scripts"
            scripts_dir.mkdir()
            (scripts_dir / "build.py").write_text("# stub", encoding="utf-8")

            config_path = worktree / ".pre-commit-config.yaml"

            def fake_run(cmd, **kwargs):
                cmd_str = " ".join(str(c) for c in cmd) if isinstance(cmd, list) else str(cmd)
                if "submodule" in cmd_str:
                    return MagicMock(returncode=0)
                if "poetry" in cmd_str or "pip" in cmd_str:
                    return MagicMock(returncode=0)
                if "build.py" in cmd_str and "--target-dir" in cmd_str:
                    config_path.write_text("repos: []\n", encoding="utf-8")
                    return MagicMock(returncode=0)
                return MagicMock(returncode=0)

            with (
                patch.object(mod.os, "symlink"),
                patch.object(mod.shutil, "copy"),
                patch.object(mod.subprocess, "run", side_effect=fake_run),
            ):
                mod._bootstrap(main_repo, worktree)

            # The probe guarantees: if _bootstrap returned without BootstrapError,
            # .pre-commit-config.yaml MUST exist at the worktree root.
            # This is the precondition for pre-commit hooks to fire on `git commit`.
            self.assertTrue(
                config_path.exists(),
                "AC-2 precondition: .pre-commit-config.yaml must be resolvable "
                "at worktree root after a BootstrapError-free _bootstrap call",
            )

    # NOTE: A full integration test for AC-2 ("a real commit runs the hooks")
    # would require:
    #   1. Initialising a real git repo in a tmp dir.
    #   2. Running `python build.py --target-dir <worktree>` to materialise hooks.
    #   3. Running `pre-commit install` inside the worktree.
    #   4. Staging a file that violates a hook (e.g. missing `description:` field).
    #   5. Attempting `git commit` without PRE_COMMIT_ALLOW_NO_CONFIG=1.
    #   6. Asserting the commit is blocked with a hook violation message.
    # This requires network access (pre-commit downloads hooks), a real git binary,
    # and the full leafcutter package built into the worktree.  It is classified
    # as a MANUAL integration test and is not automated here.


if __name__ == "__main__":
    unittest.main()
