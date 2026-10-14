"""
MODULE: unit_tests/commit_guardian/test_bp_100k_3_vii.py
GOAL: Regression tests for BP-100k-3-vii -- check-output-drift must never report a
    git-ignored path or a nested worktree (a directory holding a ``.git`` entry) as
    a coverage GAP, while still censusing everything else under a scanned dir.
BUSINESS CONTEXT: In a consumer layout the manifest records ``.claude/settings.json``,
    so ``.claude/`` becomes a scan dir and the gate rglob()s all of it. Gitignored
    ``.claude/worktrees/`` (nested git worktrees) and ``.claude/.cache/`` produced
    ~79k GAP lines and blocked every commit although nothing drifted.

HARD CONSTRAINT (repo rule "Gate / Workflow ACs -- Verify Behaviorally, Not by
    Grep"): every test copies the real gate from templates/ into a synthesized
    deployed-shaped layout and RUNS it as a subprocess, asserting on GAP lines,
    the RESULT line and the exit status. No source grep, no import of the scan
    function, no build.py spawn.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CG_TEMPLATES_SRC = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_TIMEOUT = 30

_RESULT_RE = re.compile(
    r"check-output-drift:\s*RESULT\s+verified=(?P<verified>\d+)\s+uncomparable=\d+\s+"
    r"exempt=\d+\s+gaps=(?P<gaps>\d+)\s+drifted=(?P<drifted>\d+)\s+"
    r"missing=(?P<missing>\d+)\s+unreadable=(?P<unreadable>\d+)"
)

_RECORDED = b"# recorded settings\n"
_SETTINGS_KEY = ".claude/settings.json"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, data: bytes = b"unrecorded content\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _git(workspace: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(workspace),
        check=True,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
    )


def _build_workspace(
    workspace: Path, recorded: dict[str, bytes], *, gitignore: str | None
) -> Path:
    """Synthesize a deployed-shaped layout; git-init it when ``gitignore`` is given.

    ``recorded`` files are written AND recorded in the manifest with a matching
    hash. Returns the path of the deployed gate copy.
    """
    pkg_root = workspace / "leafcutter-ai"
    (pkg_root / "templates").mkdir(parents=True)
    mappings = {}
    for rel, data in recorded.items():
        _write(workspace / rel, data)
        mappings[rel] = {"template": f"templates/{rel}", "expected_output_hash": _sha(data)}
    manifest = {
        "package_root": pkg_root.name,
        "output_mappings": mappings,
        "output_mappings_error": "",
        "output_mappings_skipped_sections": [],
    }
    (workspace / ".build_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    deployed = workspace / ".leafcutter" / "scripts" / "commit_guardian"
    shutil.copytree(_CG_TEMPLATES_SRC, deployed, ignore=shutil.ignore_patterns("__pycache__"))
    if gitignore is not None:
        _git(workspace, "init", "-q")
        _git(workspace, "config", "user.name", "t")
        _git(workspace, "config", "user.email", "t@example.invalid")
        (workspace / ".gitignore").write_text(gitignore, encoding="utf-8")
    return deployed / "check_output_drift.py"


def _run(hook: Path, workspace: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("HOOK_TEST_CONFIG", None)
    return subprocess.run(
        [sys.executable, str(hook)],
        cwd=str(workspace),
        env=env,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
    )


def _gap_lines(proc: subprocess.CompletedProcess) -> list[str]:
    return [
        ln for ln in (proc.stdout + proc.stderr).splitlines() if "UNCOMPARABLE: GAP" in ln
    ]


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name)


class TestOutputDriftIgnoredScan(_Base):
    def test_bp_100k_3_vii_gitignored_and_nested_worktree_paths_are_not_gaps(self) -> None:
        # covers: BP-100k-3-vii
        # angle: failure
        """Ignored cache + nested worktree files under a scanned .claude/ are no GAPs."""
        hook = _build_workspace(
            self.ws,
            {_SETTINGS_KEY: _RECORDED},
            gitignore=".claude/.cache/\n.claude/worktrees/\n",
        )
        _write(self.ws / ".claude/.cache/blob.bin")
        _write(self.ws / ".claude/worktrees/wt1/.git", b"gitdir: /elsewhere\n")
        for i in range(5):
            _write(self.ws / f".claude/worktrees/wt1/src/file{i}.py")
        proc = _run(hook, self.ws)
        out = proc.stdout + proc.stderr
        gaps = _gap_lines(proc)
        self.assertEqual([], gaps, msg=f"ignored/nested paths must not be GAPs. Output:\n{out}")
        self.assertNotIn(".claude/.cache", out)
        self.assertNotIn(".claude/worktrees", out)
        self.assertEqual(0, proc.returncode, msg=out)
        match = _RESULT_RE.search(out)
        self.assertIsNotNone(match, msg=out)
        self.assertEqual("0", match.group("gaps"), msg=out)

    def test_bp_100k_3_vii_nested_worktree_skipped_without_git(self) -> None:
        # covers: BP-100k-3-vii
        # angle: boundary
        """No git repo: a subdir holding a .git file is still skipped by the census."""
        hook = _build_workspace(self.ws, {_SETTINGS_KEY: _RECORDED}, gitignore=None)
        self.assertFalse((self.ws / ".git").exists(), "workspace must not be a git repo")
        _write(self.ws / ".claude/worktrees/wt1/.git", b"gitdir: /elsewhere\n")
        _write(self.ws / ".claude/worktrees/wt1/src/a.py")
        _write(self.ws / ".claude/worktrees/wt1/src/b.py")
        proc = _run(hook, self.ws)
        out = proc.stdout + proc.stderr
        self.assertEqual([], _gap_lines(proc), msg=f"nested worktree must be skipped. Output:\n{out}")
        self.assertNotIn(".claude/worktrees", out)
        self.assertEqual(0, proc.returncode, msg=out)

    def test_bp_100k_3_vii_unignored_stray_still_gaps(self) -> None:
        # covers: BP-100k-3-vii
        # angle: discrimination
        """Control: an unrecorded, non-ignored file under .claude/ is a GAP (exit 2)."""
        hook = _build_workspace(
            self.ws, {_SETTINGS_KEY: _RECORDED}, gitignore=".claude/.cache/\n"
        )
        _write(self.ws / ".claude/stray_unrecorded.txt")  # ignored cache deliberately absent
        proc = _run(hook, self.ws)
        out = proc.stdout + proc.stderr
        gaps = _gap_lines(proc)
        self.assertEqual(1, len(gaps), msg=out)
        self.assertIn(".claude/stray_unrecorded.txt", gaps[0], msg=out)
        self.assertEqual(2, proc.returncode, msg=out)

    def test_bp_100k_3_vii_ignored_dir_holding_recorded_key_still_censused(self) -> None:
        # covers: BP-100k-3-vii
        # angle: discrimination
        """An ignored dir with a recorded key is walked: stray beside it GAPs, drift shows."""
        key = ".claude/vendored/recorded.txt"
        hook = _build_workspace(
            self.ws, {_SETTINGS_KEY: _RECORDED, key: b"as built\n"}, gitignore=".claude/vendored/\n"
        )
        _write(self.ws / ".claude/vendored/stray.txt")
        proc = _run(hook, self.ws)
        out = proc.stdout + proc.stderr
        gaps = _gap_lines(proc)
        self.assertEqual(1, len(gaps), msg=out)
        self.assertIn(".claude/vendored/stray.txt", gaps[0], msg=out)
        self.assertEqual(2, proc.returncode, msg=out)

        # Drift on the recorded key under the ignored dir is still detected.
        (self.ws / key).write_bytes(b"hand edited\n")
        proc2 = _run(hook, self.ws)
        out2 = proc2.stdout + proc2.stderr
        match = _RESULT_RE.search(out2)
        self.assertIsNotNone(match, msg=out2)
        self.assertEqual("1", match.group("drifted"), msg=out2)
        self.assertIn(key, out2)
        self.assertNotEqual(0, proc2.returncode, msg=out2)

    def test_bp_100k_3_vii_tracked_symlink_layout_does_not_crash(self) -> None:
        # covers: BP-100k-3-vii
        # angle: failure
        """A tracked directory symlink under a scanned dir yields a verdict, no traceback."""
        hook = _build_workspace(
            self.ws, {_SETTINGS_KEY: _RECORDED}, gitignore=".claude/.cache/\n"
        )
        _write(self.ws / ".leafcutter/agents/a.md")
        os.symlink("../.leafcutter/agents", self.ws / ".claude" / "agents")
        _git(self.ws, "add", ".claude/agents", ".gitignore")
        proc = _run(hook, self.ws)
        out = proc.stdout + proc.stderr
        self.assertNotIn("Traceback", proc.stderr, msg=out)
        self.assertIn(proc.returncode, (0, 1, 2), msg=out)
        self.assertIsNotNone(_RESULT_RE.search(out), msg=f"no verdict emitted:\n{out}")


if __name__ == "__main__":
    unittest.main()
