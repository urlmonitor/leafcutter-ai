"""
MODULE: unit_tests/build_orchestration/_commit_step_support.py
GOAL: Shared scratch-repository helpers for the BO-4500a-1 tests of the shared
      commit step (templates/scripts/commit_changes.py).

CLI CONTRACT UNDER TEST (the shape the python-coder must build; the tests pin it):

    python templates/scripts/commit_changes.py --message-file <FILE> [PATH ...]

  * cwd is the workspace (the git working tree the step was started in).
  * PATH arguments are the explicit, caller-named, repo-relative files.
  * The commit message is read from the file named by --message-file.
  * The project's checks are the repository's own git pre-commit hook
    (.git/hooks/pre-commit); the step never skips hooks.
  * Standard output is exactly ONE JSON object (BO-4500a-4 answer contract).

Every helper runs the REAL script as a subprocess against a REAL scratch git
repository and reads the result back from git. Nothing here mocks git or the
step. Scratch directories live under TMPDIR (the run's scratch home).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STEP = REPO_ROOT / "templates" / "scripts" / "commit_changes.py"
REAL_COVERED_BY_HOOK = (
    REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_ac_parent_covered_by.py"
)

BRANCH = "feature/x"
MESSAGE = "feat: exercise the shared commit step\n"


def _clean_env(scratch: Path) -> dict[str, str]:
    """Environment for every child process: scratch TMPDIR, no inherited git plumbing."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    for key in ("TMPDIR", "TEMP", "TMP"):
        env[key] = str(scratch)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


class StepScenario:
    """One scratch repository on branch feature/x plus helpers to drive the step."""

    def __init__(self, case: unittest.TestCase, branch: str = BRANCH) -> None:
        self.case = case
        self.scratch = Path(tempfile.mkdtemp(prefix="bo4500a1_"))
        case.addCleanup(shutil.rmtree, str(self.scratch), True)
        self.env = _clean_env(self.scratch)
        self.parent = self.scratch / "work"
        self.repo = self.parent / "repo"
        self.repo.mkdir(parents=True)
        self.message_file = self.scratch / "message.txt"
        self.message_file.write_text(MESSAGE, encoding="utf-8")
        self.git("init", "-q", "-b", branch)
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        self.git("config", "commit.gpgsign", "false")

    # -- git plumbing ---------------------------------------------------
    def git(self, *args: str) -> str:
        proc = subprocess.run(
            ["git", *args],
            cwd=self.repo,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            self.case.fail(f"fixture git {args} failed: {proc.stderr}")
        return proc.stdout

    def write(self, rel: str, text: str) -> Path:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def seed_and_commit(self, files: dict[str, str]) -> None:
        """Write files and record them as the baseline commit."""
        for rel, text in files.items():
            self.write(rel, text)
        self.git("add", "--", *files)
        self.git("commit", "-q", "-m", "baseline")

    def install_hook(self, body: str) -> None:
        hook = self.repo / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        hook.chmod(0o755)

    # -- observations ---------------------------------------------------
    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def head_files(self) -> list[str]:
        out = self.git("show", "--name-only", "--format=", "HEAD")
        return sorted(line for line in out.splitlines() if line)

    def head_name_status(self) -> list[str]:
        out = self.git("show", "--name-status", "--format=", "HEAD")
        return sorted(line for line in out.splitlines() if line)

    def index_entries(self) -> dict[str, str]:
        """path -> '<mode> <blob>' for every entry in the index."""
        entries: dict[str, str] = {}
        for line in self.git("ls-files", "-s").splitlines():
            meta, path = line.split("\t", 1)
            mode, blob, _stage = meta.split()
            entries[path] = f"{mode} {blob}"
        return entries

    def staged_names(self) -> list[str]:
        out = self.git("diff", "--cached", "--name-only")
        return sorted(line for line in out.splitlines() if line)

    def porcelain(self) -> dict[str, str]:
        """path -> two-character XY status from git status --porcelain."""
        result: dict[str, str] = {}
        for line in self.git("status", "--porcelain", "--untracked-files=all").splitlines():
            result[line[3:]] = line[:2]
        return result

    def commit_count(self) -> int:
        return int(self.git("rev-list", "--count", "HEAD").strip())

    def read(self, rel: str) -> bytes:
        return (self.repo / rel).read_bytes()

    def committed_text(self, rel: str) -> str:
        return self.git("show", f"HEAD:{rel}")

    # -- the step -------------------------------------------------------
    def run_raw(self, argv: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(STEP), *argv],
            cwd=self.repo,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

    def run_step(self, paths: list[str], extra: list[str] | None = None) -> dict:
        """Run the real step and return its parsed answer.

        Fails the test (AssertionError) unless standard output is exactly one
        JSON object, so an absent or crashing step is an assertion-shaped red.
        """
        argv = ["--message-file", str(self.message_file), *(extra or []), *paths]
        proc = self.run_raw(argv)
        try:
            answer = json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.case.fail(
                "step stdout was not exactly one JSON object: "
                f"rc={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr[-400:]!r}"
            )
        self.case.assertIsInstance(answer, dict, "answer must be a JSON object")
        return answer
