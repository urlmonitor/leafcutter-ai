"""
MODULE: unit_tests/commit_guardian/test_ge_127b_2.py
COVERS: GE-127b-2 -- "During a merge, a file's previous length is resolved
    against the merge's other parent as well as HEAD, so a file inherited
    from the incoming branch is not judged as newly authored"

GOAL: RED test-first stub reproducing the observed 2026-09-08 incident: a
    merge is refused with "FILE TOO LARGE" for a covered file that is
    already committed on the branch being merged IN but does not exist at
    all on the branch being merged INTO. During a merge, the literal ref
    HEAD is the receiving branch's PRE-merge tip, so
    _file_size_ratchet.get_previous_length() resolves no previous length for
    that path, and check_file_size.py's _classify_file() falls through to
    the absolute-limit branch, judging an inherited file as brand new.

    python-coder must widen get_previous_length() (or its caller) to also
    consult MERGE_HEAD when HEAD holds no blob for the path AND a merge is
    genuinely in progress (MERGE_HEAD resolves), per GE-127b-2's
    it_requirements, WITHOUT exempting merge commits wholesale -- a
    genuinely new oversized file (present on neither parent) must still be
    refused inside a merge exactly as it is outside one.

BUSINESS CONTEXT: see
    docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/GE-127b-2.yaml
    and KI-CG-20260908-ratchet-reads-pre-merge-head in
    docs/known-issues/commit-guardian.md. Reproduces, in miniature, the
    d0271d413 incident that required SKIP=check-file-size to complete a
    real merge of origin/main.

EXERCISE STRATEGY (per CLAUDE.md "Gate / Workflow ACs -- Verify
    Behaviorally, Not by Grep" and this repo's Fixture Authenticity Rule):
    every descriptor below performs a REAL `git init`, REAL divergent
    branch history, and a REAL `git merge --no-commit` (which populates a
    REAL MERGE_HEAD) before invoking the REAL check_file_size.py as a
    subprocess and reading the actual process exit code and stdout/stderr --
    never a source-grep, never a direct function call against an in-memory
    fixture describing "the other parent". The exit code IS the commit
    outcome: 0 = merge completes, non-zero = merge is refused. This mirrors
    the established pattern in
    unit_tests/commit_guardian/test_ge_127b_1.py in this same directory.

NEGATIVE CONTROL: the second test below stages, in the SAME merge, a
    genuinely new oversized file that exists on NEITHER parent. It asserts
    the merge is STILL refused, naming that file. This assertion already
    holds on today's UNFIXED code (both files are refused today, for the
    same wrong reason), so it stays green across the fix -- it exists to
    prove the first test's green-after-fix outcome is tied to a real
    per-file MERGE_HEAD lookup, not to a fixture that fails to invoke the
    gate at all, or to an implementation that exempts every file touched by
    a merge wholesale (which would flip THIS test to unexpectedly green in
    a way the fixture can catch by asserting the refusal names the right
    file).

DECISION HISTORY
- 2026-09-08 [GE-127b-2/test-writer]: Initial authoring of the RED
    reproduction test and its negative control. Verified RED via
    `python -m unittest discover -s unit_tests/commit_guardian -t . -p
    "test_ge_127b_2.py"` -- see the test-writer sign-off comment on the
    ticket for the exact captured failure.
"""

from __future__ import annotations

import json
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

# Read the REAL per-extension limit from the real config, rather than
# hardcoding a number that could silently drift out of sync with it.
_CONFIG = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
_PY_LIMIT = _CONFIG["file_size"]["line_limits"][".py"]


# ---------------------------------------------------------------------------
# Fixture helpers (deliberately self-contained -- see test_ge_127b_1.py for
# the identical pattern used elsewhere in this directory).
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run a real git command in *cwd*.

    Args:
        args: Arguments to pass to `git` (without the leading "git").
        cwd: Working directory to run the command in.
        check: Whether to raise on non-zero exit (fixture setup only).

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
    """Initialize a real git repository with a deterministic committer
    identity and a deterministic initial branch name ("main"), regardless
    of the host's `init.defaultBranch` configuration.
    """
    _git(["init", "-q"], root)
    _git(["config", "user.email", "test-writer@example.com"], root)
    _git(["config", "user.name", "GE-127b-2 test fixture"], root)


def _commit_all(root: Path, message: str) -> None:
    """Stage everything and make a real commit."""
    _git(["add", "-A"], root)
    _git(["commit", "-q", "-m", message], root)


def _stage_all(root: Path) -> None:
    """Stage everything without committing."""
    _git(["add", "-A"], root)


def _content(n_lines: int, tag: str = "v") -> str:
    """Build deterministic, docstring-free plain-text file content.

    No triple-quote or block-comment delimiter appears anywhere in the
    output, so check_file_size.py's docstring/comment stripping is a no-op
    and the counted length is exactly `n_lines`.

    Args:
        n_lines: Exact number of lines the resulting content must count as.
        tag: A label folded into each line, used to make two same-length
            fixtures textually distinguishable.

    Returns:
        Content ending in a single trailing newline, counting as n_lines.
    """
    return "\n".join(f"{tag}_{i:06d} = {i}" for i in range(n_lines)) + "\n"


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
    """Shared tempdir + git-repo scaffolding for merge-shaped fixtures.

    setUp() establishes two divergent branches, "main" (the receiving
    branch) and "incoming" (the branch being merged in), so that merging
    "incoming" into "main" is a genuine, non-fast-forward merge that
    produces a real MERGE_HEAD -- a fast-forward merge would never populate
    it and would not reproduce the bug at all.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        _init_repo(self.root)

        (self.root / "README.md").write_text("root commit\n", encoding="utf-8")
        _commit_all(self.root, "root commit")
        # Deterministic branch name regardless of host init.defaultBranch.
        _git(["branch", "-M", "main"], self.root)

        _git(["checkout", "-b", "incoming"], self.root)

    def _diverge_main_and_merge(self) -> subprocess.CompletedProcess:
        """Return to "main", add an unrelated commit so the merge cannot
        fast-forward, then merge "incoming" into "main" WITHOUT committing
        -- this leaves a real MERGE_HEAD in place, exactly the state
        check_file_size.py runs in mid-merge.

        Returns:
            The completed `git merge` process (fixture setup only; the
            caller asserts on its own sanity, not on this return value
            being the commit outcome).
        """
        _git(["checkout", "main"], self.root)
        (self.root / "main_only.txt").write_text("main-only change\n", encoding="utf-8")
        _commit_all(self.root, "add main-only file to force a real (non-ff) merge")

        return _git(["merge", "--no-commit", "--no-ff", "incoming"], self.root, check=False)


# ---------------------------------------------------------------------------
# 1. THE RED BASELINE -- reproduces the observed d0271d413 refusal
# ---------------------------------------------------------------------------


class TestMergeInheritedOversizedFileIsNotRefused(MergeFixtureTestCase):
    def test_ge_127b_2_a_merge_is_not_refused_for_an_oversized_file_inherited_from_the_incoming_branch(self):
        # covers: GE-127b-2
        # angle: criterion
        """THE RED BASELINE. A covered file well above its permitted length
        is committed on the "incoming" branch. The "main" (receiving)
        branch has NEVER held that file at all -- so at the literal ref
        HEAD (main's PRE-merge tip), the file has no blob whatsoever.
        Merging "incoming" into "main" must complete: the file arrives
        unchanged from the branch it was inherited from, so it authors no
        new content and must not be judged as newly authored.

        RED TODAY: get_previous_length() only ever consults HEAD. During
        the merge, HEAD holds no blob for big.py, so get_previous_length()
        returns None, and check_file_size.py's _classify_file() falls
        through to the absolute-limit branch, refusing it as "FILE TOO
        LARGE" -- exactly the observed 2026-09-08 incident in miniature.
        """
        oversized_length = _PY_LIMIT + 50
        big = self.root / "big.py"
        big.write_text(_content(oversized_length), encoding="utf-8")
        _commit_all(self.root, "add oversized file on the incoming branch")

        merge_result = self._diverge_main_and_merge()
        self.assertEqual(
            0,
            merge_result.returncode,
            msg=(
                "Fixture sanity: the merge itself must not conflict. "
                f"stdout={merge_result.stdout!r} stderr={merge_result.stderr!r}"
            ),
        )
        merge_head_check = _git(["rev-parse", "--verify", "MERGE_HEAD"], self.root, check=False)
        self.assertEqual(
            0,
            merge_head_check.returncode,
            msg="Fixture sanity: MERGE_HEAD must resolve while the merge is in progress.",
        )

        result = _run_check(self.root)

        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "A merge must not refuse a covered file that is already "
                "oversized on the incoming branch but simply did not exist "
                "before on the receiving branch -- the merge authors no new "
                f"content for it. stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )


# ---------------------------------------------------------------------------
# 2. THE MANDATORY NEGATIVE CONTROL -- a genuinely new file is still refused
# ---------------------------------------------------------------------------


class TestMergeGenuinelyNewOversizedFileIsStillRefused(MergeFixtureTestCase):
    def test_ge_127b_2_a_genuinely_new_oversized_file_in_the_same_merge_is_still_refused(self):
        # covers: GE-127b-2
        # angle: criterion
        """THE MANDATORY NEGATIVE CONTROL. In the same merge shape as above
        (an oversized file inherited cleanly from "incoming"), additionally
        stage a SECOND covered file, above its permitted length, that
        exists on NEITHER parent -- authored fresh, on top of the merge
        itself. The merge must still be refused, and the refusal must name
        the genuinely new file.

        This assertion holds on BOTH today's unfixed code (which refuses
        every file with no previous length, including this one, for the
        wrong reason) AND on a correct fix (which must still refuse a file
        present on no parent). It is included so a future implementation
        that exempts merges wholesale -- the single most likely wrong fix
        for the sibling RED test above -- cannot pass silently: exempting
        every file touched by a merge would flip THIS test's file-naming
        assertion false the moment such an implementation lands, because
        the genuinely new file would no longer be named as refused either.
        """
        oversized_length = _PY_LIMIT + 50
        big = self.root / "big.py"
        big.write_text(_content(oversized_length), encoding="utf-8")
        _commit_all(self.root, "add oversized file on the incoming branch")

        merge_result = self._diverge_main_and_merge()
        self.assertEqual(
            0,
            merge_result.returncode,
            msg=(
                "Fixture sanity: the merge itself must not conflict. "
                f"stdout={merge_result.stdout!r} stderr={merge_result.stderr!r}"
            ),
        )

        brand_new = self.root / "brand_new.py"
        brand_new.write_text(_content(oversized_length, tag="w"), encoding="utf-8")
        _stage_all(self.root)

        result = _run_check(self.root)

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "A covered file present on NEITHER parent, added fresh "
                "inside a merge, must still be refused -- a merge authors "
                "no new content only when it does not. "
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertIn(
            "brand_new.py",
            combined,
            msg=f"The refusal must name the genuinely new file. Got: {combined!r}",
        )


if __name__ == "__main__":
    unittest.main()
