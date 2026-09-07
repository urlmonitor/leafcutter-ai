"""
MODULE: unit_tests/commit_guardian/test_bp_100k_4_i.py
GOAL: BP-100k-4-i — the paired NEGATIVE case for BP-100k-4. The reachability
    check must raise no false alarm on gates that legitimately fire, and must
    fail — never silently pass — when it cannot determine reachability at
    all (registry unreadable, or the repository's tracked-path set cannot be
    obtained). See docs/acceptance-criteria/build_pipeline/
    BP-100-reliable-builds/BP-100k-4-i.yaml.
BUSINESS CONTEXT: Without this paired case, the cheapest way to satisfy
    BP-100k-4 is to report every gate unreachable (blocks every commit), and
    the second cheapest is to report every gate reachable whenever anything
    goes wrong reading the registry or the tracked-path set (restores the
    exact silent-pass defect BP-100k-4 exists to remove, one level up). Both
    shortcuts are pinned down here.

CONTRACT EXERCISED (see test_bp_100k_4.py's module docstring for the full
    contract specification of check_hook_trigger_reachability.py — this file
    exercises the SAME script, focusing on its clean-pass and indeterminate
    paths):
      - Zero-unreachable, determinate run → exit 0, and the RESULT line's
        unreachable count is exactly 0.
      - A whole-tree gate declaring ``always_run: true`` with NO ``files``
        key must NOT be flagged merely for lacking a path filter — this is
        the legitimate shape, not a defect.
      - When the tracked-path lookup (``git ls-files``) cannot be performed
        at all (exercised here by running outside any git repository — a
        genuinely broken precondition, not a mocked error branch), the check
        must emit an ``INDETERMINATE: reason=<...>`` line and exit non-zero.
        It must never report ``unreachable=0`` in this situation.
      - When the registry cannot be read/parsed (exercised here via
        HOOK_TEST_CONFIG pointing at a deliberately corrupt, non-JSON file
        — genuinely broken, not a mocked exception), the same indeterminate
        contract applies: an INDETERMINATE line, non-zero exit, and never a
        clean ``unreachable=0`` verdict.

HARD CONSTRAINT (repo standing rule, "Gate / Workflow ACs — Verify
    Behaviorally, Not by Grep"): every test below EXECUTES
    check_hook_trigger_reachability.py as a subprocess against a real,
    synthesized git repository (or deliberately NOT a git repository, for the
    indeterminate cases) — never a grep of commit_guardian.json's text or of
    the check's own source for an error-handling branch.

RED BASELINE (expected, captured before check_hook_trigger_reachability.py is
    written): every test in this file is RED because the script does not
    exist yet — every subprocess invocation exits non-zero with "can't open
    file ..." on stderr, which fails the exit-code and RESULT/INDETERMINATE-
    line assertions below for the right reason: the check this AC requires
    has not been built yet.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATES_DIR = _REPO_ROOT / "templates"
_CG_TEMPLATES_SRC = _TEMPLATES_DIR / "scripts" / "commit_guardian"
_REACHABILITY_HOOK_SRC = _CG_TEMPLATES_SRC / "check_hook_trigger_reachability.py"
_REAL_REGISTRY = _CG_TEMPLATES_SRC / "commit_guardian.json"

_SUBPROCESS_TIMEOUT_SECONDS = 20

_RESULT_LINE_RE = re.compile(
    r"check-hook-trigger-reachability:\s*RESULT\s+total=(\d+)\s+unreachable=(\d+)",
    re.IGNORECASE,
)
_INDETERMINATE_LINE_RE = re.compile(r"INDETERMINATE:\s*reason=(.+)")
_CLEAN_ZERO_UNREACHABLE_RE = re.compile(r"unreachable=0\b")


# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_bp_100k_4.py; duplicated per house convention
# of self-contained sibling test files)
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git subcommand against *cwd* and return the completed process.

    Args:
        args: Git subcommand and its arguments (without the leading "git").
        cwd: Working directory to run git in.

    Returns:
        The completed subprocess result (never raises on non-zero exit).
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


def _init_repo(repo: Path) -> None:
    """Initialize a fresh, minimally-configured git repo at *repo*.

    Args:
        repo: Directory to initialize as a git repository (created if absent).
    """
    repo.mkdir(parents=True, exist_ok=True)
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "bp100k4itest@example.com"], repo)
    _git(["config", "user.name", "BP-100k-4-i Test"], repo)


def _commit_all(repo: Path, message: str) -> None:
    """Stage everything currently on disk under *repo* and commit it.

    Args:
        repo: Git repository root.
        message: Commit message.
    """
    _git(["add", "-A"], repo)
    _git(["commit", "-m", message], repo)


def _write_registry_config(entries: list[dict]) -> str:
    """Write a HOOK_TEST_CONFIG-shaped registry override via the real
    JSON serializer (never a hand-typed literal, per the Fixture
    Authenticity Rule).

    Args:
        entries: The ``hooks_manifest.hooks`` list to embed.

    Returns:
        Absolute path to the temp JSON file written.
    """
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"hooks_manifest": {"hooks": entries}}, f)
    return path


def _run_reachability_hook(
    cwd: Path, hook_test_config_path: str | None = None
) -> subprocess.CompletedProcess:
    """Execute check_hook_trigger_reachability.py as a subprocess.

    Args:
        cwd: Working directory for the subprocess.
        hook_test_config_path: Optional path to a HOOK_TEST_CONFIG override
            JSON file. When None, the real commit_guardian.json fallback
            chain is exercised instead.

    Returns:
        The completed subprocess result (returncode, stdout, stderr).
    """
    env = os.environ.copy()
    if hook_test_config_path is not None:
        env["HOOK_TEST_CONFIG"] = hook_test_config_path
    return subprocess.run(
        [sys.executable, str(_REACHABILITY_HOOK_SRC)],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


# ---------------------------------------------------------------------------
# test_spec 1: the real registry yields zero unreachable gates, exit 0.
# ---------------------------------------------------------------------------


class TestRealRegistryYieldsZeroUnreachableGatesAndExitsZero(unittest.TestCase):
    """The check, executed over the repository's real registry in a fresh
    checkout, reports an unreachable count of exactly zero and exits zero.

    SUBJECT CHOICE (2026-08-25): the registry under test is the SOURCE file
    at templates/scripts/commit_guardian/commit_guardian.json, supplied via
    HOOK_TEST_CONFIG, not the deployed copy the hook's fallback chain would
    reach at ``<cwd>/scripts/commit_guardian/commit_guardian.json``. That
    path is a symlink into a build-output tree SHARED by every worktree in
    this workspace, so it holds whatever worktree built last rather than the
    branch under test — this test was seen flipping red three times in one
    session while the source registry held the fix throughout (KI-BP-013).
    The source file is also the right subject on the merits: it is the
    version-controlled artifact a reviewer reads and a PR changes. See the
    matching note in test_bp_100k_4.py for the full rationale.
    """

    def test_real_registry_yields_zero_unreachable_gates_and_exits_zero(self) -> None:
        # covers: BP-100k-4-i
        result = _run_reachability_hook(
            _REPO_ROOT, hook_test_config_path=str(_REAL_REGISTRY)
        )
        combined = result.stdout + result.stderr

        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "A determinate run over the real registry with zero "
                f"unreachable gates must exit 0. Output:\n{combined}"
            ),
        )
        match = _RESULT_LINE_RE.search(combined)
        self.assertIsNotNone(
            match,
            msg=f"No RESULT summary line from a run over the real registry. Output:\n{combined}",
        )
        assert match is not None  # narrowing for mypy; assertIsNotNone above is the real check
        self.assertEqual(
            0,
            int(match.group(2)),
            msg=f"Expected zero unreachable gates in the real registry. Output:\n{combined}",
        )


# ---------------------------------------------------------------------------
# test_spec 2: a whole-tree gate without a path filter is not flagged.
# ---------------------------------------------------------------------------


class TestWholeTreeGateWithoutAPathFilterIsNotFlagged(unittest.TestCase):
    """A gate that declares always_run: true and carries no files key is
    reported reachable — never flagged merely for lacking a path filter."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = Path(self._tmpdir.name)
        _init_repo(self.repo)
        (self.repo / "README.md").write_text("# repo\n", encoding="utf-8")
        _commit_all(self.repo, "chore: seed minimal repo")

        self.config_path = _write_registry_config(
            [
                {
                    "id": "ensure-precommit-config-fixture",
                    "always_run": True,
                    "pass_filenames": False,
                }
            ]
        )
        self.addCleanup(os.unlink, self.config_path)

    def test_whole_tree_gate_without_a_path_filter_is_not_flagged(self) -> None:
        # covers: BP-100k-4-i
        result = _run_reachability_hook(self.repo, self.config_path)
        combined = result.stdout + result.stderr

        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "A whole-tree gate with no files key is legitimate and must "
                f"not block the commit. Output:\n{combined}"
            ),
        )
        self.assertNotIn(
            "UNREACHABLE: ensure-precommit-config-fixture",
            combined,
            msg=(
                "A whole-tree gate without a files filter was wrongly "
                f"flagged as unreachable. Output:\n{combined}"
            ),
        )
        match = _RESULT_LINE_RE.search(combined)
        self.assertIsNotNone(
            match, msg=f"No RESULT summary line was emitted. Output:\n{combined}"
        )
        assert match is not None  # narrowing for mypy; assertIsNotNone above is the real check
        self.assertEqual(
            0,
            int(match.group(2)),
            msg=f"Expected zero unreachable gates. Output:\n{combined}",
        )


# ---------------------------------------------------------------------------
# test_spec 3: an unobtainable tracked-path set produces a named failure.
# ---------------------------------------------------------------------------


class TestUnobtainableTrackedPathSetProducesANamedFailure(unittest.TestCase):
    """When the tracked-path lookup is made genuinely unavailable at run
    time (this cwd is deliberately NOT a git repository — the lookup fails
    for real, not via a mocked error branch), the check states that it
    could not determine reachability, names the reason, and exits non-zero.
    It must never report unreachable=0 in this situation."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        # Deliberately NOT git-initialized — `git ls-files` run here fails
        # with "not a git repository", making the tracked-path lookup
        # genuinely unavailable rather than mocked.
        self.not_a_repo = Path(self._tmpdir.name)

        self.config_path = _write_registry_config(
            [
                {
                    "id": "irrelevant-gate",
                    "files": "^templates/agents/",
                    "pass_filenames": False,
                }
            ]
        )
        self.addCleanup(os.unlink, self.config_path)

    def test_unobtainable_tracked_path_set_produces_a_named_failure(self) -> None:
        # covers: BP-100k-4-i
        result = _run_reachability_hook(self.not_a_repo, self.config_path)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "The check must fail (non-zero exit) when the repository's "
                f"tracked-path set cannot be obtained. Output:\n{combined}"
            ),
        )
        match = _INDETERMINATE_LINE_RE.search(combined)
        self.assertIsNotNone(
            match,
            msg=(
                "No INDETERMINATE line was emitted when the tracked-path "
                f"lookup was made genuinely unavailable. Output:\n{combined}"
            ),
        )
        self.assertNotRegex(
            combined,
            _CLEAN_ZERO_UNREACHABLE_RE,
            msg=(
                "The check must never report a clean unreachable=0 verdict "
                "when it could not determine the tracked-path set. "
                f"Output:\n{combined}"
            ),
        )


# ---------------------------------------------------------------------------
# test_spec 4: an unreadable registry is not reported as all-reachable.
# ---------------------------------------------------------------------------


class TestUnreadableRegistryIsNotReportedAsAllReachable(unittest.TestCase):
    """With the registry made genuinely unreadable (a deliberately corrupt,
    non-JSON HOOK_TEST_CONFIG file — not a mocked exception), the check does
    not emit a clean zero-unreachable verdict; it emits the indeterminate
    verdict and exits non-zero."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = Path(self._tmpdir.name)
        _init_repo(self.repo)
        (self.repo / "README.md").write_text("# repo\n", encoding="utf-8")
        _commit_all(self.repo, "chore: seed minimal repo")

        # Deliberately malformed — not a hand-typed VALID literal standing in
        # for real JSON, but genuinely corrupt content, so the failure this
        # test pins is a real parse failure, not a simulated one.
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{ this is not valid json and never parses ")
        self.config_path = path
        self.addCleanup(os.unlink, self.config_path)

    def test_unreadable_registry_is_not_reported_as_all_reachable(self) -> None:
        # covers: BP-100k-4-i
        result = _run_reachability_hook(self.repo, self.config_path)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "The check must fail (non-zero exit) when the registry "
                f"cannot be read/parsed. Output:\n{combined}"
            ),
        )
        self.assertNotRegex(
            combined,
            _CLEAN_ZERO_UNREACHABLE_RE,
            msg=(
                "A corrupt/unreadable registry must never be reported as a "
                f"clean, all-reachable pass. Output:\n{combined}"
            ),
        )
        match = _INDETERMINATE_LINE_RE.search(combined)
        self.assertIsNotNone(
            match,
            msg=(
                "No INDETERMINATE verdict was emitted for an unreadable "
                f"registry. Output:\n{combined}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
