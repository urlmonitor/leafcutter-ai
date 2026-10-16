"""
MODULE: test_inline_work_guard.py
GOAL: Unit tests for the inline_work_guard.py PreToolUse hook.
BUSINESS CONTEXT: Validates that inline_work_guard.py correctly blocks Edit/Write
      tool calls when .build-feature.lock exists, allows them when it does not,
      writes JSONL audit records, supports warn mode, and is fail-open on exceptions.
      Tests ticket TICKET-20260527-BuildFeatureInlineWorkGuard acceptance criteria.
ARCHITECTURE: Uses subprocess to invoke the hook script with synthetic stdin payloads,
      temp directories to simulate repo root structures with/without lock files, and
      environment variables to test mode switching.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


# Path to the hook script under test
HOOK_SCRIPT = str(
    Path(__file__).parent.parent.parent
    / "templates"
    / "hooks"
    / "inline_work_guard.py"
)


def _run_hook(
    payload: dict,
    env_overrides: dict | None = None,
    cwd: str | None = None,
    hook: str = HOOK_SCRIPT,
) -> subprocess.CompletedProcess:
    """Run the inline_work_guard.py hook with the given stdin payload.

    Args:
        payload: JSON-serialisable dict sent as stdin to the hook.
        env_overrides: Optional dict of env var overrides for the subprocess.
        cwd: Working directory for the subprocess. Defaults to the temp dir.
        hook: Hook script to run. Defaults to the template source; audit tests
            pass a copy deployed into a declared install (INF-500d-4-iv).

    Returns:
        CompletedProcess with returncode, stdout, and stderr.
    """
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, hook],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
    )


class TestInlineWorkGuardNoLock(unittest.TestCase):
    """Tests for the no-lock-file scenario (allowed through)."""

    def setUp(self) -> None:
        """Create a temp directory with a fake .git to act as repo root."""
        self.tmpdir = tempfile.mkdtemp()
        (Path(self.tmpdir) / ".git").mkdir()
        self.payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(Path(self.tmpdir) / "some_file.py"),
            },
        }

    def tearDown(self) -> None:
        """Remove the temp directory."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_allows_edit_when_no_lock(self) -> None:
        """No lock file present; hook must exit 0 (allow)."""
        result = _run_hook(self.payload, cwd=self.tmpdir)
        self.assertEqual(result.returncode, 0)

    def test_allows_write_when_no_lock(self) -> None:
        """No lock file present; Write tool call must exit 0 (allow)."""
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(Path(self.tmpdir) / "new_file.py"),
                "content": "print('hello')",
            },
        }
        result = _run_hook(payload, cwd=self.tmpdir)
        self.assertEqual(result.returncode, 0)


class TestInlineWorkGuardWithLock(unittest.TestCase):
    """Tests for the lock-file-present scenario."""

    def setUp(self) -> None:
        """Create a temp directory with .git and .build-feature.lock."""
        self.tmpdir = tempfile.mkdtemp()
        (Path(self.tmpdir) / ".git").mkdir()
        self.lock_path = Path(self.tmpdir) / ".build-feature.lock"
        self.lock_path.write_text("2026-05-27T10:00:00Z 12345\n")
        self.payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(Path(self.tmpdir) / "some_file.py"),
            },
        }

    def tearDown(self) -> None:
        """Remove the temp directory."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_blocks_edit_when_lock_exists(self) -> None:
        """Lock file present in block mode; hook must exit 2."""
        result = _run_hook(self.payload, cwd=self.tmpdir)
        self.assertEqual(result.returncode, 2)

    def test_blocked_stderr_names_lock_and_instructs(self) -> None:
        """Blocked message must name .build-feature.lock and instruct dispatch."""
        result = _run_hook(self.payload, cwd=self.tmpdir)
        self.assertIn("BLOCKED", result.stderr)
        self.assertIn(".build-feature.lock", result.stderr)
        self.assertIn("supervisor", result.stderr)

    def _declared_install(self) -> tuple[str, Path]:
        """Deploy the hook into a declared install; return (hook path, audit log path).

        INF-500d-4-iv: the audit record is appended to
        <operational_log_root>/inline_work_guard.jsonl, read from the build-time
        declaration (config/knowledge_sink.json) of the hook's OWN deployed
        workspace -- no longer <repo_root>/debugging/logs, which is deleted with
        the per-drive worktree. So the hook runs from a deployed layout
        (<install>/hooks/) whose declaration is written by the real build helper
        and names a root OUTSIDE the repo the guard is judging.
        """
        import shutil

        from unit_tests.feedback import _inf_500d_4_helpers as h

        install = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, install, ignore_errors=True)
        out_root = install / ".leafcutter"
        shutil.copytree(
            Path(HOOK_SCRIPT).parent, out_root / "hooks",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        enduring = install / "enduring"
        enduring.mkdir()
        h.declare(out_root, enduring / "logs")
        log_root = Path(h.read_declaration(out_root)["operational_log_root"])
        return str(out_root / "hooks" / "inline_work_guard.py"), log_root / "inline_work_guard.jsonl"

    def test_jsonl_audit_log_written(self) -> None:
        """Block must append a JSONL record with required fields."""
        hook, audit_log = self._declared_install()

        result = _run_hook(self.payload, cwd=self.tmpdir, hook=hook)

        self.assertEqual(result.returncode, 2)
        self.assertTrue(audit_log.exists(), "Audit log file was not created under the declared root")
        # The retracted location (inside the per-drive repo root) is not written.
        self.assertFalse((Path(self.tmpdir) / "debugging").exists())
        with open(audit_log, "r", encoding="utf-8") as fh:
            lines = fh.read().strip().splitlines()
        self.assertGreater(len(lines), 0, "Audit log is empty")
        record = json.loads(lines[-1])
        # Validate required fields
        self.assertIn("timestamp", record)
        self.assertIn("tool_name", record)
        self.assertIn("file_path", record)
        self.assertIn("session_id", record)

    def test_warn_mode_exits_zero(self) -> None:
        """Warn mode with lock present must exit 0 but still write audit record."""
        result = _run_hook(
            self.payload,
            env_overrides={"INLINE_WORK_GUARD_MODE": "warn"},
            cwd=self.tmpdir,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("WARNING", result.stderr)

    def test_warn_mode_writes_audit_log(self) -> None:
        """Warn mode must still append a JSONL record."""
        hook, audit_log = self._declared_install()  # INF-500d-4-iv: declared root, not the repo

        _run_hook(
            self.payload,
            env_overrides={"INLINE_WORK_GUARD_MODE": "warn"},
            cwd=self.tmpdir,
            hook=hook,
        )

        self.assertTrue(audit_log.exists(), "Audit log not created in warn mode under the declared root")
        self.assertFalse((Path(self.tmpdir) / "debugging").exists())
        with open(audit_log, "r", encoding="utf-8") as fh:
            lines = fh.read().strip().splitlines()
        self.assertGreater(len(lines), 0, "Audit log is empty in warn mode")
        record = json.loads(lines[-1])
        self.assertEqual(record.get("mode"), "warn")

    def test_block_mode_is_default(self) -> None:
        """Without INLINE_WORK_GUARD_MODE, default mode is block (exits 2)."""
        env = {k: v for k, v in os.environ.items() if k != "INLINE_WORK_GUARD_MODE"}
        result = subprocess.run(
            [sys.executable, HOOK_SCRIPT],
            input=json.dumps(self.payload),
            capture_output=True,
            text=True,
            env=env,
            cwd=self.tmpdir,
        )
        self.assertEqual(result.returncode, 2)


class TestInlineWorkGuardFailOpen(unittest.TestCase):
    """Tests for the fail-open behaviour on exceptions."""

    def test_exception_failopen_malformed_stdin(self) -> None:
        """Malformed stdin must not block the tool call (exit 0, fail-open)."""
        result = subprocess.run(
            [sys.executable, HOOK_SCRIPT],
            input="NOT VALID JSON !!!",
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)

    def test_empty_stdin_failopen(self) -> None:
        """Empty stdin must exit 0 (fail-open)."""
        result = subprocess.run(
            [sys.executable, HOOK_SCRIPT],
            input="",
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)

    def test_no_git_repo_failopen(self) -> None:
        """When not in a git repo, hook must exit 0 (fail-open)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # No .git directory here
            payload = {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(Path(tmpdir) / "test.py")},
            }
            result = _run_hook(payload, cwd=tmpdir)
            self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
