"""
MODULE: unit_tests/commit_guardian/test_ac_governance_merge_baseline.py
GOAL: Behavioral tests for ACS-400c-2-ii — during a merge, the amended_by audit
    judges a record against the version this commit actually amends FROM, so a
    record taken verbatim from the other parent is not reported as an amendment.
BUSINESS CONTEXT: FIELD EVIDENCE — PR #862, 2026-09-28. Two branches had each
    minted BO-4000d for a different behaviour. Resolving the collision in main's
    favour left the staged file byte-identical to MERGE_HEAD, yet the hook
    demanded an amended_by entry for criteria the committer had not written. The
    two ways out were both wrong: falsify the audit trail, or SKIP a governance
    gate. See ACS-400c-2-ii.yaml.
ARCHITECTURE: Every existing governance test runs with HOOK_NO_GIT=1, which makes
    _load_head_content return None before any git call — so none of them can
    reach this behaviour, and all would stay green through the defect AND through
    a broken fix. These tests therefore build a REAL temporary git repository,
    create a REAL id collision across two branches, and leave a REAL merge in
    progress with MERGE_HEAD on disk, then invoke the hook as a subprocess. The
    distinction under test — "differs from HEAD" versus "authored by this commit"
    — only physically exists in that arrangement.

    The negative cases carry as much weight as the positive one. The fix's whole
    risk is excusing too much; a suite with only the first test would pass just as
    happily against a hook that skipped the audit during any merge at all.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOK_SCRIPT = _REPO_ROOT / "scripts" / "commit_guardian" / "check_ac_governance.py"

_AC_REL_PATH = "docs/acceptance-criteria/test-component/ACS-TEST-COLLIDE.yaml"


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """Run one git command inside *repo* and return the completed process."""
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


def _ac_yaml(criteria: str, origin_agent: str = "business-analyst") -> str:
    """Return a minimal but schema-shaped AC record carrying *criteria*."""
    return textwrap.dedent(
        f"""\
        id: ACS-TEST-COLLIDE
        title: "Collision fixture"
        component: test-component
        level: L3
        status: active
        req_status: active
        work_status: todo
        criteria: |
          {criteria}
        depends_on: []
        origin_agent: {origin_agent}
        created: 2026-09-28
        amended_by: []
        superseded_by: null
        covered_by: []
        implemented_by: []
        """
    )


def _write(repo: Path, rel_path: str, content: str) -> None:
    """Write *content* to *rel_path* under *repo*, creating parent directories."""
    target = repo / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _init_repo(repo: Path) -> None:
    """Create a git repo with one committed AC record on the default branch."""
    _run_git(repo, "init", "-b", "main")
    _run_git(repo, "config", "user.email", "test@example.invalid")
    _run_git(repo, "config", "user.name", "Test")
    _run_git(repo, "config", "commit.gpgsign", "false")
    _write(repo, rel_path=_AC_REL_PATH, content=_ac_yaml("Given main, Then main."))
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-m", "base")


def _create_collision_merge(repo: Path) -> None:
    """Leave *repo* mid-merge with a conflict on the AC record's path.

    Both branches write a DIFFERENT record to the SAME path — the id-collision
    shape. The merge is left unresolved so each test can stage whichever content
    the case requires.
    """
    _run_git(repo, "checkout", "-b", "other")
    _write(repo, rel_path=_AC_REL_PATH, content=_ac_yaml("Given other, Then other."))
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-m", "other branch mints the same id")

    _run_git(repo, "checkout", "main")
    _write(repo, rel_path=_AC_REL_PATH, content=_ac_yaml("Given mainline, Then mainline."))
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-m", "main mints the same id differently")

    # Conflicts by construction; we resolve it per-test below.
    _run_git(repo, "merge", "other")


def _run_hook(repo: Path) -> subprocess.CompletedProcess:
    """Invoke the governance hook against *repo* with real git enabled."""
    return subprocess.run(
        [sys.executable, str(_HOOK_SCRIPT)],
        cwd=str(repo),
        env={
            **os.environ,
            "HOOK_ROOT": str(repo),
            "HOOK_AGENT_ID": "python-coder",
        },
        capture_output=True,
        text=True,
        timeout=60,
    )


class TestAcGovernanceMergeBaseline(unittest.TestCase):
    """ACS-400c-2-ii: the amended_by audit judges against the right baseline."""

    def test_a_record_taken_from_the_other_parent_is_not_an_amendment(self) -> None:
        # covers: ACS-400c-2-ii
        """Resolving an id collision in the other parent's favour must not block.

        The staged bytes are identical to MERGE_HEAD's, so this commit authored
        no change to that record — demanding an amended_by entry would record the
        merge author as having written criteria that came from another branch.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            _create_collision_merge(repo)

            # Resolve in the other parent's favour: take its bytes verbatim.
            _run_git(repo, "checkout", "--theirs", "--", _AC_REL_PATH)
            _run_git(repo, "add", "--", _AC_REL_PATH)

            # Guard the fixture itself: the premise is that the staged blob
            # matches MERGE_HEAD while DIFFERING from HEAD. If that is not true
            # the test proves nothing, so assert it rather than assume it.
            self.assertEqual(
                _run_git(repo, "diff", "--cached", "--quiet", "MERGE_HEAD").returncode,
                0,
                "fixture broken: staged content should be identical to MERGE_HEAD",
            )
            self.assertNotEqual(
                _run_git(repo, "diff", "--cached", "--quiet", "HEAD").returncode,
                0,
                "fixture broken: staged content should differ from HEAD",
            )

            result = _run_hook(repo)
            self.assertEqual(
                result.returncode,
                0,
                "A record byte-identical to a merge parent was not authored by "
                "this commit and must not be refused for a missing amended_by "
                f"entry. stdout={result.stdout!r} stderr={result.stderr!r}",
            )

    def test_a_real_criteria_edit_during_a_merge_is_still_refused(self) -> None:
        # covers: ACS-400c-2-ii
        """A merge-time edit matching NO parent must still be refused.

        This is the anti-over-broadening guard. Without it the fix could be a
        hook that simply stops auditing during any merge, and the positive test
        above would not notice.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            _create_collision_merge(repo)

            # Resolve with content of the committer's own invention.
            _write(
                repo,
                rel_path=_AC_REL_PATH,
                content=_ac_yaml("Given a hand-written resolution, Then neither parent."),
            )
            _run_git(repo, "add", "--", _AC_REL_PATH)

            self.assertNotEqual(
                _run_git(repo, "diff", "--cached", "--quiet", "MERGE_HEAD").returncode,
                0,
                "fixture broken: staged content must differ from MERGE_HEAD",
            )

            result = _run_hook(repo)
            self.assertNotEqual(
                result.returncode,
                0,
                "Criteria invented during a merge match no parent and ARE this "
                "commit's own amendment; the audit must still fire. "
                f"stdout={result.stdout!r} stderr={result.stderr!r}",
            )
            self.assertIn(
                "amended_by",
                result.stdout + result.stderr,
                "The refusal must still name the amended_by field.",
            )

    def test_outside_a_merge_a_criteria_edit_is_still_refused(self) -> None:
        # covers: ACS-400c-2-ii
        """With no merge in progress the gate is exactly as strict as before.

        The overwhelmingly common case. The parent list is [HEAD] alone, so the
        baseline resolver's loop body never runs and the resolved baseline is
        HEAD — this asserts that property through observable behaviour rather
        than by reading the code.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)

            _write(
                repo,
                rel_path=_AC_REL_PATH,
                content=_ac_yaml("Given an ordinary edit, Then refused."),
            )
            _run_git(repo, "add", "--", _AC_REL_PATH)

            self.assertFalse(
                (repo / ".git" / "MERGE_HEAD").exists(),
                "fixture broken: no merge should be in progress",
            )

            result = _run_hook(repo)
            self.assertNotEqual(
                result.returncode,
                0,
                "An ordinary criteria change with no new amended_by entry must "
                "still be refused. "
                f"stdout={result.stdout!r} stderr={result.stderr!r}",
            )


if __name__ == "__main__":
    unittest.main()
