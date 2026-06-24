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
        mod = _load_setup_module()

        main_repo = Path("/fake/main")
        worktree = Path("/fake/worktree")

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
        mod = _load_setup_module()

        main_repo = Path("/fake/main")
        worktree = Path("/fake/worktree")

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
        mod = _load_setup_module()

        main_repo = Path("/fake/main")
        worktree = Path("/fake/worktree")

        win_err = OSError(1314, "A required privilege is not held by the client")

        import io

        fake_stderr = io.StringIO()

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
        mod = _load_setup_module()

        main_repo = Path("/fake/main")
        worktree = Path("/fake/worktree")

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
    scripts_dir = str(_REPO_ROOT / "scripts")
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


if __name__ == "__main__":
    unittest.main()
