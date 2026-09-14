"""
MODULE: unit_tests/commit_guardian/test_ki_cg_20260908_file_size_ratchet_merge_aware.py
COVERS: KI-CG-20260908-file-size-ratchet-refuses-merge-commits

GOAL: Prove the file-size ratchet (GE-127b-1 / GE-127b-1-i, backed by
    _file_size_ratchet.py) is merge-aware: a merge's permitted previous
    length for a file is the MOST PERMISSIVE (maximum) length across every
    parent of the commit -- HEAD plus every parent named in MERGE_HEAD --
    not HEAD's alone.

BUSINESS CONTEXT: Reproduced live in worktree
    /home/henzeh/projects/leafcutter/worktrees/bp-100n-4: merging
    origin/main into a feature branch was refused on seven files whose
    growth was authored entirely on main, in commits that had themselves
    already passed this same gate. Judging a merge against HEAD alone made
    every already-accepted growth on the OTHER side look like new growth
    the merge author introduced. See check_package_surface_declaration.py's
    module docstring for the sibling defect this fix mirrors, including the
    documented `git rev-parse -q --verify MERGE_HEAD` octopus-merge trap
    (it reads only the FIRST line of MERGE_HEAD).

EXERCISE STRATEGY: every descriptor drives a REAL `git init`, real commits,
    and a REAL `git merge --no-commit` (or an ordinary `git add`) to build
    an actual in-progress merge state on disk, then invokes the REAL
    check_file_size.py as a subprocess and reads its actual exit code and
    output -- never a mocked git call, never a hand-written MERGE_HEAD.
    Mirrors the established pattern in test_ge_127b_1.py and
    test_ac_limits_merge_scope.py in this same directory.

DECISION HISTORY
- 2026-09-08 [python-coder/KI-CG-20260908-file-size-ratchet-refuses-merge-commits]:
    Initial authoring. Verified RED against the pre-fix _file_size_ratchet.py
    (HEAD-only previous-length resolution) via `git stash` of the production
    change and a full run of this file; verified GREEN after unstashing.
- 2026-09-08 [BrainCandy/GE-127b-2]: added the covers tag below. GE-127b-2 was
    authored independently of this file, against the same defect and to the same
    conclusion -- a merge's permitted previous length is the most permissive across
    every parent. Rather than ship a second implementation, the AC was pointed at
    the behaviour this file already proves. No test was changed; only the claim of
    what these descriptors cover was made explicit.
- 2026-09-08 [BrainCandy/GE-127b-2]: the covers tag was first written HERE, at
    module level, immediately below this docstring. It does not count there, and
    nothing said so: the pre-commit check-done-proof gate searches the staged text
    for the tag anywhere and passed, while CI's oracle
    (scripts/ac_store/done_proof.py:875-877) skips any line whose enclosing
    function is None -- so a Python covers tag is only seen when it sits INSIDE a
    test function. The two gates disagree about what a covers tag is; filed as
    KI-CG-20260908-covers-tag-must-be-inside-a-test-function. The tag now sits in
    the three descriptors that actually prove the rule.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CHECK_FILE_SIZE = _COMMIT_GUARDIAN_DIR / "check_file_size.py"
_CONFIG_PATH = _COMMIT_GUARDIAN_DIR / "commit_guardian.json"

_PYTHON = sys.executable
_SUBPROCESS_TIMEOUT_SECONDS = 30

_CONFIG = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
_PY_LIMIT = _CONFIG["file_size"]["line_limits"][".py"]


# ---------------------------------------------------------------------------
# Fixture helpers (mirrors test_ge_127b_1.py's conventions)
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run a real git command in *cwd*.

    Args:
        args: Arguments to pass to `git` (without the leading "git").
        cwd: Working directory to run the command in.
        check: Whether to raise on non-zero exit.

    Returns:
        The completed process.
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=check,
    )


def _init_repo(root: Path) -> None:
    """Initialize a real git repository with a deterministic committer identity."""
    _git(["init", "-q", "-b", "main"], root)
    _git(["config", "user.email", "test-writer@example.com"], root)
    _git(["config", "user.name", "KI-CG-20260908 test fixture"], root)


def _commit_all(root: Path, message: str) -> None:
    """Stage everything and make a real commit."""
    _git(["add", "-A"], root)
    _git(["commit", "-q", "-m", message], root)


def _stage_all(root: Path) -> None:
    """Stage everything without committing."""
    _git(["add", "-A"], root)


def _content(n_lines: int, tag: str = "v") -> str:
    """Build deterministic, docstring-free plain-text file content.

    Args:
        n_lines: Exact number of lines the resulting content must count as.
        tag: A label folded into each line.

    Returns:
        Content ending in a single trailing newline, counting as n_lines.
    """
    return "\n".join(f"{tag}_{i:06d} = {i}" for i in range(n_lines)) + "\n"


def _marker_content(n_lines: int, marker_index: int, marker: str) -> str:
    """Build deterministic content with one distinguishing line, for conflicts.

    Args:
        n_lines: Exact number of lines the resulting content must count as.
        marker_index: Index of the line to replace with *marker*.
        marker: The distinguishing text for that line.

    Returns:
        Content ending in a single trailing newline, counting as n_lines.
    """
    lines = [f"v_{i:06d} = {i}" for i in range(n_lines)]
    lines[marker_index] = marker
    return "\n".join(lines) + "\n"


def _run_check(cwd: Path) -> subprocess.CompletedProcess:
    """Invoke the real check_file_size.py against staged content in *cwd*."""
    return subprocess.run(
        [_PYTHON, str(_CHECK_FILE_SIZE)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


class MergeFixtureTestCase(unittest.TestCase):
    """Shared tempdir + git-repo scaffolding."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        _init_repo(self.root)


# ---------------------------------------------------------------------------
# 1. The mandatory positive arm: the other side's legitimate growth is adopted
# ---------------------------------------------------------------------------


class TestMergeAdoptingAlreadyGrownFileFromOtherParentPasses(MergeFixtureTestCase):
    def test_a_merge_that_adopts_an_already_grown_oversized_file_from_the_other_parent_passes(self):
        # covers: KI-CG-20260908-file-size-ratchet-refuses-merge-commits
        # covers: GE-127b-2
        """THE MANDATORY POSITIVE ARM. big.py is already oversized (450
        lines, limit 400) at the point main and feature diverge. main then
        grows it further (500 lines) in a commit that was, on main's own
        history, already vetted by this same gate -- exactly the shape of
        the live defect (scripts/build_phases.py 1884 -> 1906 authored
        entirely on main). feature never touches big.py. Merging main into
        feature adopts main's 500-line version verbatim (no conflict, since
        only main touched the file) and MUST commit cleanly.

        MUTATION-SENSITIVE: on the pre-fix ratchet (HEAD-only previous
        -length resolution), the previous length resolved is feature's HEAD
        value (450), so the merge-adopted 500 looks like growth from 450 and
        is refused. This is the exact defect reported live.
        """
        big = self.root / "big.py"
        big.write_text(_content(450), encoding="utf-8")
        _commit_all(self.root, "base: establish oversized file")

        _git(["checkout", "-q", "-b", "feature"], self.root)
        (self.root / "feature_only.py").write_text(_content(20), encoding="utf-8")
        _commit_all(self.root, "feature work, unrelated to big.py")

        _git(["checkout", "-q", "main"], self.root)
        big.write_text(_content(500), encoding="utf-8")
        _commit_all(self.root, "main grows the already-oversized file further")

        _git(["checkout", "-q", "feature"], self.root)
        merge = _git(["merge", "main", "--no-commit", "--no-ff"], self.root, check=False)
        self.assertEqual(
            0, merge.returncode,
            msg=f"fixture sanity: expected a clean, non-conflicting merge. stderr={merge.stderr!r}",
        )
        self.assertEqual(500, len(big.read_text(encoding="utf-8").splitlines()))

        result = _run_check(self.root)

        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "A merge that adopts an already-grown oversized file verbatim "
                f"from the other parent must commit cleanly. stdout={result.stdout!r} "
                f"stderr={result.stderr!r}"
            ),
        )


# ---------------------------------------------------------------------------
# 2. The negative control: growth authored BY the merge itself is refused
# ---------------------------------------------------------------------------


class TestMergeResultLargerThanEveryParentIsRefused(MergeFixtureTestCase):
    def test_a_merge_result_larger_than_every_parent_is_still_refused(self):
        # covers: KI-CG-20260908-file-size-ratchet-refuses-merge-commits
        # covers: GE-127b-2
        """THE NEGATIVE CONTROL. Both feature and main edit the SAME line of
        an already-oversized big.py (450 lines each), forcing a genuine
        content conflict. The merge author resolves it by writing content
        LONGER than either parent (470 lines) -- growth this commit, not
        either side's history, is responsible for. It MUST still be
        refused: merge-awareness must widen the permitted baseline to the
        max of the parents, never to "unlimited".
        """
        big = self.root / "big.py"
        big.write_text(_marker_content(450, 9, "base_marker"), encoding="utf-8")
        _commit_all(self.root, "base: establish oversized file")

        _git(["checkout", "-q", "-b", "feature"], self.root)
        big.write_text(_marker_content(450, 9, "feature_marker"), encoding="utf-8")
        _commit_all(self.root, "feature edits the marker line")

        _git(["checkout", "-q", "main"], self.root)
        big.write_text(_marker_content(450, 9, "main_marker"), encoding="utf-8")
        _commit_all(self.root, "main edits the marker line differently")

        _git(["checkout", "-q", "feature"], self.root)
        merge = _git(["merge", "main", "--no-commit", "--no-ff"], self.root, check=False)
        self.assertNotEqual(
            0, merge.returncode,
            msg="fixture sanity: expected a genuine conflict on the marker line",
        )

        # Resolve the conflict by hand, growing the file past BOTH parents.
        big.write_text(_content(470, tag="resolved"), encoding="utf-8")
        _stage_all(self.root)

        result = _run_check(self.root)

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "Growth introduced while resolving a merge conflict -- beyond "
                "what EITHER parent already had -- must still be refused. "
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )


# ---------------------------------------------------------------------------
# 3. Regression guards: the ordinary (non-merge) ratchet is untouched
# ---------------------------------------------------------------------------


class TestOrdinaryCommitGrowingOversizedFileIsStillRefused(MergeFixtureTestCase):
    def test_a_normal_non_merge_commit_that_grows_an_oversized_file_is_still_refused(self):
        # covers: KI-CG-20260908-file-size-ratchet-refuses-merge-commits
        """REGRESSION GUARD. Outside any merge, growing an already-oversized
        file must still be refused -- proves the fix did not simply widen
        the baseline unconditionally or disable the ratchet.
        """
        big = self.root / "big.py"
        big.write_text(_content(450), encoding="utf-8")
        _commit_all(self.root, "establish oversized file")

        big.write_text(_content(451), encoding="utf-8")
        _stage_all(self.root)

        result = _run_check(self.root)

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "A normal, non-merge commit that grows an already-oversized "
                f"file must still be refused. stdout={result.stdout!r} "
                f"stderr={result.stderr!r}"
            ),
        )


class TestOrdinaryCommitCrossingTheLimitIsStillRefused(MergeFixtureTestCase):
    def test_a_normal_non_merge_commit_crossing_the_limit_is_still_refused(self):
        # covers: KI-CG-20260908-file-size-ratchet-refuses-merge-commits
        """REGRESSION GUARD. Outside any merge, a file crossing the absolute
        limit for the first time must still be refused -- proves the fix did
        not disable the crossing-refusal path either.
        """
        (self.root / "README.md").write_text("placeholder\n", encoding="utf-8")
        _commit_all(self.root, "baseline with no covered files")

        new_file = self.root / "fresh.py"
        new_file.write_text(_content(_PY_LIMIT + 1), encoding="utf-8")
        _stage_all(self.root)

        result = _run_check(self.root)

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "A normal, non-merge commit that crosses the absolute limit "
                f"must still be refused. stdout={result.stdout!r} "
                f"stderr={result.stderr!r}"
            ),
        )


# ---------------------------------------------------------------------------
# 4. Octopus merge: every line of MERGE_HEAD must be read, not just the first
# ---------------------------------------------------------------------------


class TestOctopusMergeReadsEveryMergeHeadLine(MergeFixtureTestCase):
    def test_an_octopus_merge_reads_every_merge_head_line_not_only_the_first(self):
        # covers: KI-CG-20260908-file-size-ratchet-refuses-merge-commits
        # covers: GE-127b-2
        """THE OCTOPUS DESCRIPTOR. Three branches merge into feature at once:
        branchB touches an unrelated file only; branchC is the ONLY one that
        grows the already-oversized big.py (450 -> 460, still over the 400
        limit). feature's own HEAD still has big.py at 450. `MERGE_HEAD`
        will therefore hold two lines -- branchB first, branchC second.

        MUTATION-SENSITIVE to exactly the documented `git rev-parse -q
        --verify MERGE_HEAD` mistake: that probe reads only the FIRST line
        of MERGE_HEAD (branchB here), which never touched big.py, so an
        implementation making that mistake would resolve a baseline of
        max(HEAD=450, branchB=450) = 450 and WRONGLY refuse the merge-
        adopted 460. Only reading BOTH MERGE_HEAD lines finds branchC's 460
        and correctly permits it.
        """
        big = self.root / "big.py"
        big.write_text(_content(450), encoding="utf-8")
        _commit_all(self.root, "base: establish oversized file")

        _git(["checkout", "-q", "-b", "feature"], self.root)
        (self.root / "feature_only.py").write_text(_content(10), encoding="utf-8")
        _commit_all(self.root, "feature work, unrelated to big.py")

        _git(["checkout", "-q", "main"], self.root)
        _git(["checkout", "-q", "-b", "branchB"], self.root)
        (self.root / "branchB_only.py").write_text(_content(10), encoding="utf-8")
        _commit_all(self.root, "branchB work, unrelated to big.py")

        _git(["checkout", "-q", "main"], self.root)
        _git(["checkout", "-q", "-b", "branchC"], self.root)
        big.write_text(_content(460), encoding="utf-8")
        _commit_all(self.root, "branchC grows the already-oversized file legitimately")

        _git(["checkout", "-q", "feature"], self.root)
        merge = _git(
            ["merge", "branchB", "branchC", "--no-commit", "--no-ff"],
            self.root,
            check=False,
        )
        self.assertEqual(
            0, merge.returncode,
            msg=f"fixture sanity: expected a clean octopus merge. stderr={merge.stderr!r}",
        )

        merge_head_path = _git(
            ["rev-parse", "--git-path", "MERGE_HEAD"], self.root
        ).stdout.strip()
        merge_head_lines = [
            line
            for line in (self.root / merge_head_path).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(
            2,
            len(merge_head_lines),
            msg=(
                "fixture sanity: expected exactly two additional parents "
                f"(branchB, branchC) in MERGE_HEAD. Got: {merge_head_lines!r}"
            ),
        )
        self.assertEqual(460, len(big.read_text(encoding="utf-8").splitlines()))

        result = _run_check(self.root)

        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "An octopus merge whose SECOND additional parent (branchC) "
                "legitimately grew an already-oversized file must commit "
                f"cleanly -- every MERGE_HEAD line must be read. "
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )


# ---------------------------------------------------------------------------
# 5. Fail-closed: an unreadable MERGE_HEAD is INDETERMINATE, never a silent pass
# ---------------------------------------------------------------------------


@unittest.skipIf(os.name == "nt", "POSIX permission bits are not meaningful on Windows")
class TestUnreadableMergeHeadIsIndeterminate(MergeFixtureTestCase):
    def test_a_merge_in_progress_with_an_unreadable_merge_head_is_indeterminate(self):
        # covers: KI-CG-20260908-file-size-ratchet-refuses-merge-commits
        """FAIL-CLOSED ON AMBIGUITY. A merge is known to be in progress (the
        MERGE_HEAD path resolves) but the file itself cannot be read -- its
        parent set cannot be established. This must exit 2 (INDETERMINATE),
        never a silent pass and never a misclassification as "not merging".
        """
        big = self.root / "big.py"
        big.write_text(_content(450), encoding="utf-8")
        _commit_all(self.root, "base: establish oversized file")

        _git(["checkout", "-q", "-b", "feature"], self.root)
        (self.root / "feature_only.py").write_text(_content(10), encoding="utf-8")
        _commit_all(self.root, "feature work")

        _git(["checkout", "-q", "main"], self.root)
        big.write_text(_content(460), encoding="utf-8")
        _commit_all(self.root, "main grows the file")

        _git(["checkout", "-q", "feature"], self.root)
        merge = _git(["merge", "main", "--no-commit", "--no-ff"], self.root, check=False)
        self.assertEqual(0, merge.returncode)

        merge_head_path = self.root / _git(
            ["rev-parse", "--git-path", "MERGE_HEAD"], self.root
        ).stdout.strip()
        original_mode = merge_head_path.stat().st_mode
        merge_head_path.chmod(0o000)
        self.addCleanup(lambda: merge_head_path.chmod(original_mode))

        try:
            result = _run_check(self.root)
        finally:
            merge_head_path.chmod(original_mode)

        # Running as root (some CI containers) bypasses permission bits
        # entirely; skip rather than false-fail in that environment.
        if result.returncode == 0 and "INDETERMINATE" not in (result.stdout + result.stderr):
            self.skipTest("permission bits were not enforced (likely running as root)")

        self.assertEqual(
            2,
            result.returncode,
            msg=(
                "An unreadable MERGE_HEAD during a real merge must be "
                f"INDETERMINATE (exit 2). stdout={result.stdout!r} "
                f"stderr={result.stderr!r}"
            ),
        )
        self.assertIn(
            "INDETERMINATE",
            result.stdout + result.stderr,
            msg="The outcome must name the situation as INDETERMINATE.",
        )


if __name__ == "__main__":
    unittest.main()
