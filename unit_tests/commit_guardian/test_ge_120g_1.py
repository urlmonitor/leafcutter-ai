"""
MODULE: test_ge_120g_1
AC: GE-120g-1 — "An ordinary commit leaves the working copy holding exactly
    the content it held before, whether the checks let it through or refuse
    it"

GOAL: TDD red-baseline tests for the shared pre-commit dispatch mechanism's
    tree-cleanliness guarantee. GE-120g-1's own notes are explicit that the
    ONE mechanism shipped so far (``run_hook.py``'s ``_hook_env()``, which
    sets ``PYTHONDONTWRITEBYTECODE=1``) only suppresses ONE side channel —
    compiled-module bytecode caching — and that "how many judging checks
    alter the working copy by some route OTHER than the compiled-module
    cache has not been measured". This file exercises exactly that
    unmeasured, unaddressed residual: a judging check with a side effect
    that has nothing to do with bytecode (it appends a line to a tracked
    audit file beside itself on every invocation). Per the AC's own notes,
    this repository cannot be the fixture as it stands (its .gitignore
    already excludes ``__pycache__``, and more generally this test's
    fixture must be built fresh so nothing is excluded from version
    control) — every test below builds a REAL, ISOLATED git repository on
    disk, seeds it exactly as the AC's notes prescribe (run the check once
    OUTSIDE the guarded path, `git add -A`, commit that as the baseline —
    order is load-bearing), installs the REAL `pre-commit` framework
    (a declared dev dependency, see requirements-dev.txt) against a hook
    wired through the REAL, unmodified `run_hook.py`, and then performs a
    genuine `git commit` — "no extra command, no extra flag, and nothing
    invoked by hand" — exactly as the AC's Given/When clauses require.

WHY THIS MUST BE EXERCISED FOR REAL, OUT OF PROCESS. Per this repo's own
    CLAUDE.md ("Gate / Workflow ACs — Verify Behaviorally, Not by Grep"),
    a test that reads run_hook.py's source or asserts PYTHONDONTWRITEBYTECODE
    is merely present in a launch environment proves nothing about whether an
    ordinary commit is actually left untouched — this file never imports
    run_hook.py, check_ac_*.py, or any commit_guardian module; it only copies
    the real, unmodified run_hook.py onto disk and drives it through a real
    `pre-commit install` + `git commit`, then inspects the resulting git
    state (HEAD, `git status --porcelain`, and the tracked blob content of
    the byproduct file) — the same observables a human operator would look
    at after an "it looked fine but something's off" commit.

CONFIRMED BEHAVIOUR AT TEST-WRITER TIME (manufactured in a throwaway /tmp
    fixture built with the exact same recipe as this file's tests, 2026-09-09):
    an accepted change, staged and committed ordinarily, against a judging
    check whose ONLY side effect is appending one line to a tracked
    audit.log beside itself (no bytecode involved at all) is REFUSED by
    pre-commit's own generic "files were modified by this hook" dirty-check
    (exit 1) even though the check's OWN verdict was an explicit pass
    ("PASSED: judging check found nothing to object to"), and afterwards the
    working copy is left holding a MODIFIED, uncommitted audit.log — neither
    half of GE-120g-1's accepted-path guarantee holds. This is the valid RED
    state this ticket exists to close; # covers below record it.

====================================================================
DECISION HISTORY
====================================================================
- 2026-09-09 [test-writer/GE-120g-1]: Initial TDD red-baseline. Built a
  self-contained, real-git/real-pre-commit fixture (no shared harness
  dependency) mirroring unit_tests/portability/test_ge_120a_1.py's
  subprocess-execution discipline. Chose a non-bytecode side channel
  (an appended audit-log line) deliberately, per the AC's own notes
  forbidding any test from relying on a stated or implied COUNT of how many
  checks are affected by routes other than bytecode caching — this fixture
  demonstrates the residual gap exists at all, not how large it is.
====================================================================
"""
# @ac-tag: GE-120g-1

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]  # unit_tests/commit_guardian/ -> worktree root
_REAL_RUN_HOOK = _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "run_hook.py"
_SUBPROCESS_TIMEOUT_SECONDS = 60

_JUDGING_CHECK_SOURCE = '''
import pathlib
import sys

here = pathlib.Path(__file__).resolve().parent
repo_root = here.parent.parent  # scripts/commit_guardian/ -> repo root
audit_log = here / "audit.log"
existing = audit_log.read_text(encoding="utf-8") if audit_log.exists() else ""
audit_log.write_text(existing + "run\\n", encoding="utf-8")

tracked = repo_root / "tracked.txt"
content = tracked.read_text(encoding="utf-8") if tracked.exists() else ""
if "REJECT_MARKER" in content:
    print("BLOCKED: judging check objects to REJECT_MARKER")
    sys.exit(1)
print("PASSED: judging check found nothing to object to")
sys.exit(0)
'''


def _fixture_precondition_ok() -> str | None:
    """Return an error message if a required real source file/tool is
    missing, else None."""
    if not _REAL_RUN_HOOK.exists():
        return f"Fixture precondition failed: {_REAL_RUN_HOOK} does not exist."
    if shutil.which("pre-commit") is None:
        return (
            "Fixture precondition failed: 'pre-commit' is not on PATH "
            "(declared dev dependency per requirements-dev.txt; install it "
            "to run this test)."
        )
    return None


def _run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env if env is not None else os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


def _build_fixture_repo(tmp_root: Path) -> None:
    """Build a REAL, isolated git repository at tmp_root: the real
    run_hook.py, one synthetic judging check with a non-bytecode side
    effect, a .pre-commit-config.yaml wiring the two together, and an
    initial tracked.txt. Does NOT seed, install hooks, or commit — callers
    do that afterward in the load-bearing order the AC's notes prescribe.
    """
    commit_guardian_dir = tmp_root / "scripts" / "commit_guardian"
    commit_guardian_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_REAL_RUN_HOOK, commit_guardian_dir / "run_hook.py")
    (commit_guardian_dir / "judging_check.py").write_text(_JUDGING_CHECK_SOURCE, encoding="utf-8")

    (tmp_root / "tracked.txt").write_text("hello\n", encoding="utf-8")

    precommit_config = (
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: check-judging\n"
        "        name: Judging Check\n"
        "        entry: python scripts/commit_guardian/run_hook.py "
        "scripts/commit_guardian/judging_check.py\n"
        "        language: system\n"
        "        pass_filenames: false\n"
        "        always_run: true\n"
    )
    (tmp_root / ".pre-commit-config.yaml").write_text(precommit_config, encoding="utf-8")

    _run(["git", "init", "-q"], cwd=tmp_root)
    _run(["git", "config", "user.email", "test-writer@example.com"], cwd=tmp_root)
    _run(["git", "config", "user.name", "GE-120g-1 test fixture"], cwd=tmp_root)
    # Deliberately: no .gitignore is written — the fresh-install shape the
    # AC's Given clause requires ("excludes nothing from version control").
    _run(["git", "config", "core.autocrlf", "false"], cwd=tmp_root)


def _seed_baseline(tmp_root: Path) -> None:
    """SEEDING, mandatory and order-load-bearing (per GE-120g-1's notes):
    (1) run the check once, directly, OUTSIDE the pre-commit path, so its
    byproduct (audit.log) comes into existence; (2) git add -A; (3) commit
    that as the fixture's baseline. Seeding before the run stages nothing
    and silently defeats this test, per the AC's own explicit warning.
    """
    check_script = tmp_root / "scripts" / "commit_guardian" / "judging_check.py"
    seed_result = _run([sys.executable, str(check_script)], cwd=tmp_root)
    assert seed_result.returncode == 0, f"seeding run failed: {seed_result.stdout}{seed_result.stderr}"

    _run(["git", "add", "-A"], cwd=tmp_root)
    commit_result = _run(["git", "commit", "-m", "baseline"], cwd=tmp_root)
    assert commit_result.returncode == 0, (
        f"seed baseline commit failed: {commit_result.stdout}{commit_result.stderr}"
    )


def _install_precommit(tmp_root: Path) -> None:
    install_result = _run(["pre-commit", "install", "-f"], cwd=tmp_root)
    assert install_result.returncode == 0, (
        f"pre-commit install failed: {install_result.stdout}{install_result.stderr}"
    )


class TestAcceptedOrdinaryCommitLeavesTreeUntouched(unittest.TestCase):
    """GE-120g-1: an ordinary commit of a change every check accepts must
    complete, and the working copy's tracked content must be identical to
    what it was before the attempt began."""

    def setUp(self) -> None:
        precondition_error = _fixture_precondition_ok()
        if precondition_error:
            self.fail(precondition_error)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)
        _build_fixture_repo(self.tmp_root)
        _seed_baseline(self.tmp_root)
        _install_precommit(self.tmp_root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ge_120g_1_accepted_commit_completes_and_tree_is_clean(self) -> None:
        # covers: GE-120g-1
        # angle: reachability
        """Real entry point: `git commit` with the real, installed
        pre-commit hook dispatching through the real run_hook.py. Asserts
        BOTH halves of the AC's accepted-path guarantee: the commit
        actually completes, AND the working copy is left exactly as found
        (`git status --porcelain` empty) — not merely that the check's own
        verdict was a pass. Today the judging check's own non-bytecode
        side effect (appending to audit.log) is left in the tree and
        pre-commit's own dirty-check refuses the very first ordinary
        commit attempt, so this must currently FAIL on both assertions."""
        (self.tmp_root / "tracked.txt").write_text("hello\nworld\n", encoding="utf-8")
        _run(["git", "add", "tracked.txt"], cwd=self.tmp_root)

        head_before = _run(["git", "rev-parse", "HEAD"], cwd=self.tmp_root).stdout.strip()

        commit_result = _run(["git", "commit", "-m", "ordinary accepted change"], cwd=self.tmp_root)
        combined = commit_result.stdout + commit_result.stderr

        head_after = _run(["git", "rev-parse", "HEAD"], cwd=self.tmp_root).stdout.strip()
        status_after = _run(["git", "status", "--porcelain"], cwd=self.tmp_root).stdout

        self.assertEqual(
            0,
            commit_result.returncode,
            "An ordinary commit of a change every check accepts must "
            f"complete. HEAD before={head_before} after={head_after}. "
            f"Full pre-commit output:\n{combined}",
        )
        self.assertNotEqual(
            head_before,
            head_after,
            f"HEAD did not move — the commit did not actually complete.\n{combined}",
        )
        self.assertEqual(
            "",
            status_after,
            "The working copy must be left exactly as it was before the "
            "attempt began — no new or modified content of any kind "
            f"beside the installed checks. git status --porcelain:\n{status_after!r}\n"
            f"Full pre-commit output:\n{combined}",
        )


class TestObjectedOrdinaryCommitLeavesTreeUntouched(unittest.TestCase):
    """GE-120g-1: an ordinary commit of a change a check objects to must not
    complete, and the working copy's tracked content must again be
    identical to what it was before that attempt began."""

    def setUp(self) -> None:
        precondition_error = _fixture_precondition_ok()
        if precondition_error:
            self.fail(precondition_error)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)
        _build_fixture_repo(self.tmp_root)
        _seed_baseline(self.tmp_root)
        _install_precommit(self.tmp_root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ge_120g_1_objected_commit_is_refused_and_tree_stays_clean(self) -> None:
        # covers: GE-120g-1
        # angle: failure
        """Feed a known-bad staged change (contains REJECT_MARKER, which
        the judging check explicitly objects to) through the real entry
        point. The commit must not complete (AC's second Then), AND the
        working copy's tracked content must be identical to what it was
        before this attempt began (the same untouched-tree guarantee, on
        the refusal path). Today the judging check's audit.log side effect
        fires regardless of its own accept/reject verdict, so the tracked
        audit.log is left modified even though the commit is correctly
        refused — this must currently FAIL on the tree-cleanliness
        assertion."""
        (self.tmp_root / "tracked.txt").write_text("hello\nREJECT_MARKER\n", encoding="utf-8")
        _run(["git", "add", "tracked.txt"], cwd=self.tmp_root)

        head_before = _run(["git", "rev-parse", "HEAD"], cwd=self.tmp_root).stdout.strip()
        audit_blob_before = _run(
            ["git", "show", f"{head_before}:scripts/commit_guardian/audit.log"], cwd=self.tmp_root
        ).stdout

        commit_result = _run(["git", "commit", "-m", "ordinary objected change"], cwd=self.tmp_root)
        combined = commit_result.stdout + commit_result.stderr

        head_after = _run(["git", "rev-parse", "HEAD"], cwd=self.tmp_root).stdout.strip()
        audit_on_disk_after = (
            self.tmp_root / "scripts" / "commit_guardian" / "audit.log"
        ).read_text(encoding="utf-8")

        self.assertNotEqual(
            0,
            commit_result.returncode,
            f"A commit that a check objects to must not complete.\n{combined}",
        )
        self.assertEqual(
            head_before,
            head_after,
            f"HEAD must not move when the commit is refused.\n{combined}",
        )
        self.assertEqual(
            audit_blob_before,
            audit_on_disk_after,
            "The working copy's tracked content must be identical to what "
            "it was before this refused attempt began — the judging "
            "check's own side effect must not persist merely because it "
            f"ran. Tracked before:\n{audit_blob_before!r}\nOn disk after:\n"
            f"{audit_on_disk_after!r}\nFull pre-commit output:\n{combined}",
        )


if __name__ == "__main__":
    unittest.main()
