"""
MODULE: test_ge_122a_1_ii
GOAL: The decision-number gate must keep judging a newly authored ADR when a
    DIFFERENT staged file happens to claim the same number because it was
    merged in from origin/main. Skipping the merged-in file must never skip
    the author's own file.
BUSINESS CONTEXT: `check-decision-number-uniqueness` ->
    `check_adr_collision.py` is the one hook GE-122a-1 actually registers, so
    it is the only commit-time behaviour that changed. Its merge-in exemption
    is keyed on the ADR INTEGER rather than on the file, and its path lookup
    returns only the FIRST staged path claiming that integer. When a merge
    brings ADR-034 in from origin/main and the author independently writes
    their own ADR-034 in the same commit, the exemption drops BOTH claimants,
    the collision detector is handed an empty list, and the gate exits 0 on
    the exact double-claim it exists to catch. The double-claim then lands on
    main and has to be untangled by renaming files and every cross-reference
    to them -- the 2026-05-15 ADR-024 incident, reproduced by the guard meant
    to prevent it.
ARCHITECTURE: Drives the hook as a PROCESS against a REAL temporary git
    repository -- an actual merge in progress, actual staged files, an actual
    `refs/remotes/origin/main` -- and asserts on its exit code and emitted
    report. The behaviour under test is precisely how the hook interrogates
    git (`diff --cached`, `cat-file -e HEAD:<path>`, `ls-tree origin/main`),
    so a mocked git would test the mock, and importing the module in-process
    would not exercise the exit-code contract pre-commit actually reads.
    Each test asserts the staged set FIRST, so a fixture that failed to stage
    what the scenario needs fails as a setup error rather than masquerading
    as a behavioural result. Do NOT edit check_adr_collision.py from here.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_TEMPLATE_DIR = (
    Path(__file__).parent.parent.parent / "templates" / "scripts" / "commit_guardian"
)
_CANONICAL = _TEMPLATE_DIR / "check_adr_collision.py"

_ADR_DIR = "docs/architecture/adrs"

_MERGED_IN_ADR = "ADR-034-committed.md"
# Sorts BEFORE the merged-in file, so the buggy first-match path lookup
# resolves the integer 034 to THIS file. That ordering is the trigger.
_AUTHORED_ADR = "ADR-034-authored-by-me.md"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """Run a git command inside *repo*.

    Args:
        repo: Repository working directory.
        *args: Arguments passed to git.

    Returns:
        subprocess.CompletedProcess: The completed process.
    """
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _write_adr(repo: Path, filename: str, body: str) -> None:
    """Write an ADR file into the repository's decision directory.

    Args:
        repo: Repository working directory.
        filename: ADR filename, e.g. ``ADR-034-something.md``.
        body: File contents.
    """
    target = repo / _ADR_DIR
    target.mkdir(parents=True, exist_ok=True)
    (target / filename).write_text(body, encoding="utf-8")


def _staged_paths(repo: Path) -> list[str]:
    """Return the added/renamed paths currently staged in *repo*.

    Args:
        repo: Repository working directory.

    Returns:
        list[str]: Staged paths, exactly as the hook itself reads them.
    """
    result = _git(repo, "diff", "--cached", "--name-only", "--diff-filter=AR")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _run_hook(repo: Path) -> subprocess.CompletedProcess:
    """Execute the decision-number collision hook inside *repo*.

    The hook resolves every git read from its own process working directory,
    so it is run as a child process rooted in the fixture repository.

    Args:
        repo: Repository working directory.

    Returns:
        subprocess.CompletedProcess: Completed process carrying the hook's
            exit code, stdout report and stderr diagnostics.
    """
    return subprocess.run(
        [sys.executable, str(_CANONICAL)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(repo),
    )


@unittest.skipUnless(_CANONICAL.exists(), f"hook not found at {_CANONICAL}")
class TestMergeInExemptionIsPerFile(unittest.TestCase):
    """The merge-in exemption must excuse a file, never a whole number."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "config", "user.email", "t@example.com")
        _git(self.repo, "config", "user.name", "Test")

        # Base commit: the decision directory exists but holds no ADR yet.
        (self.repo / _ADR_DIR).mkdir(parents=True, exist_ok=True)
        (self.repo / _ADR_DIR / "README.md").write_text("decisions\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "base")

        # The author's branch forks here, BEFORE ADR-034 exists anywhere.
        _git(self.repo, "checkout", "-q", "-b", "feature")

        # Upstream authors ADR-034 and it lands on origin/main.
        _git(self.repo, "checkout", "-q", "main")
        _write_adr(self.repo, _MERGED_IN_ADR, "# ADR-034 (upstream)\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "upstream adds ADR-034")
        _git(self.repo, "update-ref", "refs/remotes/origin/main", "refs/heads/main")

        _git(self.repo, "checkout", "-q", "feature")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _merge_origin_main(self) -> None:
        """Start a merge of upstream into the feature branch, leaving it staged.

        Raises:
            AssertionError: When the merge did not stage the upstream ADR, i.e.
                the fixture is broken rather than the hook.
        """
        merge = _git(self.repo, "merge", "main", "--no-commit", "--no-ff")
        staged = _staged_paths(self.repo)
        self.assertIn(
            f"{_ADR_DIR}/{_MERGED_IN_ADR}",
            staged,
            msg=(
                "Fixture setup failed: merging upstream did not stage "
                f"{_MERGED_IN_ADR}. staged={staged} "
                f"stdout={merge.stdout} stderr={merge.stderr}"
            ),
        )

    def test_merged_in_adr_alone_is_not_reported(self) -> None:
        """Case 1 -- the behaviour the merge-in exemption exists for."""
        # covers: GE-122a-1-ii
        self._merge_origin_main()
        self.assertEqual(
            [f"{_ADR_DIR}/{_MERGED_IN_ADR}"],
            _staged_paths(self.repo),
            msg="Case 1 expects exactly the merged-in ADR to be staged.",
        )

        result = _run_hook(self.repo)

        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "An ADR merged in from origin/main was authored upstream, not "
                "here, so it must not be reported as a collision against the "
                "very ref it came from. "
                f"stdout={result.stdout} stderr={result.stderr}"
            ),
        )

    def test_authored_adr_is_reported_despite_merged_in_twin(self) -> None:
        """Case 2 -- the bug: the author's own double-claim is skipped."""
        # covers: GE-122a-1-ii
        self._merge_origin_main()
        _write_adr(self.repo, _AUTHORED_ADR, "# ADR-034 (mine)\n")
        _git(self.repo, "add", f"{_ADR_DIR}/{_AUTHORED_ADR}")

        staged = _staged_paths(self.repo)
        self.assertIn(
            f"{_ADR_DIR}/{_AUTHORED_ADR}",
            staged,
            msg=f"Fixture setup failed: the authored ADR is not staged. {staged}",
        )
        self.assertIn(
            f"{_ADR_DIR}/{_MERGED_IN_ADR}",
            staged,
            msg=f"Fixture setup failed: the merged-in ADR is not staged. {staged}",
        )

        result = _run_hook(self.repo)

        self.assertEqual(
            1,
            result.returncode,
            msg=(
                "Two staged files claim ADR-034: one merged in from "
                "origin/main and one authored in this commit. Excusing the "
                "merged-in file must not also excuse the authored one -- this "
                "is the double-claim the gate exists to catch. "
                f"stdout={result.stdout} stderr={result.stderr}"
            ),
        )
        self.assertIn(
            "034",
            result.stdout,
            msg=(
                "The report must name the contested number so the author "
                f"knows which file to renumber. stdout={result.stdout}"
            ),
        )

    def test_two_newly_authored_adrs_sharing_a_number_are_reported(self) -> None:
        """Case 3 -- the same-commit self-collision detector, unobstructed."""
        # covers: GE-122a-1-ii
        _write_adr(self.repo, "ADR-077-alpha.md", "# ADR-077 alpha\n")
        _write_adr(self.repo, "ADR-077-beta.md", "# ADR-077 beta\n")
        _git(self.repo, "add", "-A")

        staged = _staged_paths(self.repo)
        self.assertEqual(
            [f"{_ADR_DIR}/ADR-077-alpha.md", f"{_ADR_DIR}/ADR-077-beta.md"],
            sorted(staged),
            msg=f"Fixture setup failed: both ADR-077 files must be staged. {staged}",
        )

        result = _run_hook(self.repo)

        self.assertEqual(
            1,
            result.returncode,
            msg=(
                "Two brand-new files staged together claiming ADR-077 is a "
                "collision no history comparison can see, and is the literal "
                "scenario GE-122a-1 names. "
                f"stdout={result.stdout} stderr={result.stderr}"
            ),
        )
        self.assertIn(
            "077",
            result.stdout,
            msg=f"The report must name ADR-077. stdout={result.stdout}",
        )


if __name__ == "__main__":
    unittest.main()
