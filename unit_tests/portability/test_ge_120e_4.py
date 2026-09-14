"""
MODULE: test_ge_120e_4
AC: GE-120e-4 — "Undoing or replaying someone else's recorded change is
    treated the same way as merging it in"

GOAL: TDD red-baseline tests for extending GE-120e-1's shared
    ``get_authored_change()`` derivation (``templates/scripts/commit_guardian/
    _authored_change.py``, already landed) to also consult ``REVERT_HEAD`` and
    ``CHERRY_PICK_HEAD`` — not just ``MERGE_HEAD`` — as one more input,
    combined with the states the commit under revision is built on, and to
    never decide the answer by asking "is a merge in particular under way".

BUSINESS CONTEXT: Ticket 35 of EPIC-TrustThatAGreenCheckActuallyChecked.
    ``source_ac``: GE-120e-4. Its own ``test_spec`` supplies the five
    behavioral test names used below; the sixth (reachability) is the
    mandatory floor test this ticket's own Test Requirements table appends
    because the AC authored no ``test_spec`` entry naming a production entry
    point.

    GE-120e-1 (ticket 28, status: done as of this file's authoring) already
    ships ``_authored_change.get_authored_change()``, consumed by
    ``check_contract_shrinking.py`` and ``check_doc_frontmatter.py``. Its
    ``_derive_authored_change()`` probes ONLY ``MERGE_HEAD`` — a revert or a
    cherry-pick leaves exactly one state to compare against (the branch tip),
    so today's derivation attributes the ENTIRE reverted/cherry-picked
    changeset to the author, and ``check_contract_shrinking.py`` objects to
    deletions the author did not write. That is precisely the defect this AC
    removes.

WHY THIS IS A GENUINE RED BASELINE, EMPIRICALLY CONFIRMED (not asserted from
    reading the source alone): a real ``git revert --no-commit HEAD`` fixture
    equivalent to ``_build_revert_fixture`` below was built by hand at
    authoring time and run through today's (unmodified)
    ``check_contract_shrinking.py``. It BLOCKED:
        [contract-shrinking guard] BLOCKED
          - test function deleted: 'test_recorded_case'
          - test file deleted: 'unit_tests/test_recorded.py'
        Production files modified:
          - prod/module.py
    confirming today's derivation attributes the reverted deletions to the
    revert's author and this check objects to them — exactly the behaviour
    Tests A/B/C/E below assert must NOT happen once GE-120e-4 lands.

WHY THESE FIXTURES ARE REAL GIT, NOT MOCKS: every assertion below is on the
    combined stdout+stderr of a REAL subprocess invocation of
    ``check_contract_shrinking.py`` against a REAL repository built with a
    real ``git revert --no-commit`` / ``git cherry-pick --no-commit``
    operation — per this AC's own Coverage note ("cover each operation by
    performing it as a real repository operation and executing the check as
    a process against the resulting staged state") and this repo's
    Real-Artifact Behavioral Test Mandate. A fresh ``git init`` repo per test
    (rather than a ``git worktree add`` off this repository) is used because
    ``check_contract_shrinking.py``, unlike ``check_doc_frontmatter.py``,
    needs no real ``docs/components.json``/``docs/FRONTMATTER.md`` context —
    same reasoning ``test_ge_120e_4_i.py`` (the sibling AC covering the
    operation-record-already-expired edge case) already used.

CROSS-LAYER SEAM (Rule 3): Tests A, B, C, and E each pipe a REAL producer
    (real git operation-record state, read by the extended
    ``_authored_change.get_authored_change()``) into the REAL consumer
    (``check_contract_shrinking.py``, run as a subprocess) and assert the
    consumer's observable exit code and output — not a mock of either side.

====================================================================
DECISION HISTORY
====================================================================
- 2026-09-07 [EPIC-TrustThatAGreenCheckActuallyChecked/35, GE-120e-4,
  test-writer]: Initial TDD red-baseline. ``_authored_change.py`` (GE-120e-1)
  already exists and imports cleanly, so these tests fail via
  ``AssertionError`` (the derivation still only recognises ``MERGE_HEAD``,
  so ``check_contract_shrinking.py`` still blocks on a bare revert/cherry-pick
  of someone else's recorded change) rather than ``ImportError`` — the
  genuine red state for this ticket's actual deliverable, empirically
  confirmed by hand against today's unmodified check (see module docstring
  above).
====================================================================
"""
# @ac-tag: GE-120e-4

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CHECK_PATH = _COMMIT_GUARDIAN_DIR / "check_contract_shrinking.py"
_RUN_HOOK_PATH = _COMMIT_GUARDIAN_DIR / "run_hook.py"

_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    from build_phases import build_commit_guardian  # type: ignore[import]
    _BUILD_PHASES_OK = True
except (ImportError, ModuleNotFoundError):
    build_commit_guardian = None  # type: ignore[assignment]
    _BUILD_PHASES_OK = False

if str(_COMMIT_GUARDIAN_DIR) not in sys.path:
    sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))

try:
    from _authored_change import get_authored_change  # type: ignore[import]
    _AUTHORED_CHANGE_OK = True
except ImportError:
    get_authored_change = None  # type: ignore[assignment]
    _AUTHORED_CHANGE_OK = False

_MISSING_DEPENDENCY_MSG = (
    "templates/scripts/commit_guardian/_authored_change.py (GE-120e-1's "
    "shared authored-change derivation) could not be imported at all. "
    "GE-120e-4 extends it, in place, to also consult REVERT_HEAD and "
    "CHERRY_PICK_HEAD — it must continue to exist and export "
    "get_authored_change()."
)

_GIT_TIMEOUT = 30


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------
def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command in *cwd*, raising with full context on failure."""
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=True,
        )
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            f"git {' '.join(args)} failed in {cwd}: "
            f"{getattr(exc, 'stderr', '') or exc}"
        ) from exc


def _run_git_probe(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command in *cwd* WITHOUT raising on non-zero exit.

    Used for existence probes (``rev-parse --verify <ref>``) where a
    non-zero exit is an expected, meaningful outcome rather than a failure.
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT,
        check=False,
    )


def _init_repo(repo: Path) -> str:
    """Create *repo* and initialise a fresh git repository in it.

    Returns:
        The name of the initial branch (queried rather than assumed, since
        git's configured default branch name varies across environments).
    """
    repo.mkdir(parents=True, exist_ok=True)
    _run_git(["init", "-q"], repo)
    _run_git(["config", "user.email", "ge120e4@test.local"], repo)
    _run_git(["config", "user.name", "GE-120e-4 Test"], repo)
    return _run_git(["symbolic-ref", "--short", "HEAD"], repo).stdout.strip()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _staged_paths(repo: Path) -> list[str]:
    result = _run_git(["diff", "--cached", "--name-only"], repo)
    return [line for line in result.stdout.splitlines() if line]


def _assert_operation_record(
    test: unittest.TestCase, repo: Path, present: str, absent: list[str],
) -> None:
    """Assert exactly one operation record exists — *present* — and every
    ref in *absent* does not, so a fixture never accidentally exercises a
    different operation than the one it claims to."""
    found = _run_git_probe(["rev-parse", "-q", "--verify", present], repo)
    test.assertEqual(
        0, found.returncode,
        f"Fixture setup failed: {present} was not set in {repo} as expected.",
    )
    for ref in absent:
        missing = _run_git_probe(["rev-parse", "-q", "--verify", ref], repo)
        test.assertNotEqual(
            0, missing.returncode,
            f"Fixture setup failed: {ref} was unexpectedly present in {repo} "
            f"— this fixture must exercise ONLY {present}.",
        )


def _run_check(repo: Path) -> subprocess.CompletedProcess:
    """Run check_contract_shrinking.py as a real subprocess against *repo*."""
    return subprocess.run(
        [sys.executable, str(_CHECK_PATH)],
        cwd=str(repo), capture_output=True, text=True, timeout=_GIT_TIMEOUT,
        check=False,
    )


def _run_check_via_entry_point(repo: Path, check_path: Path) -> subprocess.CompletedProcess:
    """Run *check_path* via the REAL commit_guardian dispatch (run_hook.py).

    This is the entry the commit_guardian manifest actually registers for
    check-contract-shrinking (``commit_guardian.json``'s ``"entry": "python
    {{output_root}}/scripts/commit_guardian/run_hook.py {{output_root}}/
    scripts/commit_guardian/check_contract_shrinking.py"``) — used for the
    reachability test so it exercises the real dispatch path, not a
    hand-picked shortcut.
    """
    run_hook = repo / "scripts" / "commit_guardian" / "run_hook.py"
    return subprocess.run(
        [sys.executable, str(run_hook), str(check_path)],
        cwd=str(repo), capture_output=True, text=True, timeout=_GIT_TIMEOUT,
        check=False,
    )


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------
def _build_revert_fixture(repo: Path) -> None:
    """Build a repo where the CURRENTLY STAGED content is a bare, no-commit
    revert of a "recorded" changeset — a large-ish undo (a production edit
    plus a brand-new test file's worth of coverage) with no author edit of
    its own on top.

    Also seeds two files (``prod/author_owned.py`` /
    ``unit_tests/test_author_owned.py``) untouched by the revert, so a later
    test can stage a genuine author violation there without rebuilding the
    fixture from scratch.
    """
    _init_repo(repo)
    _write(repo / "prod" / "module.py", "def helper():\n    return 1\n")
    _write(repo / "unit_tests" / "test_module.py", "def test_one():\n    assert True\n")
    _write(repo / "prod" / "author_owned.py", "def owned_helper():\n    return 1\n")
    _write(repo / "unit_tests" / "test_author_owned.py", "def test_owned():\n    assert True\n")
    _run_git(["add", "-A"], repo)
    _run_git(["commit", "-q", "-m", "base"], repo)

    _write(repo / "unit_tests" / "test_recorded.py", "def test_recorded_case():\n    assert True\n")
    _write(repo / "prod" / "module.py", "def helper():\n    return 2\n")
    _run_git(["add", "-A"], repo)
    _run_git(["commit", "-q", "-m", "recorded: add coverage + refactor helper"], repo)

    _run_git(["revert", "--no-commit", "HEAD"], repo)

    staged = _staged_paths(repo)
    if "unit_tests/test_recorded.py" not in staged or "prod/module.py" not in staged:
        raise RuntimeError(
            f"Fixture setup failed: expected the revert to stage "
            f"unit_tests/test_recorded.py and prod/module.py, got: {staged!r}"
        )


def _stage_author_violation(repo: Path) -> None:
    """On top of whatever operation is already staged in *repo*, stage a
    genuine, distinct author violation: delete a whole test file while
    concurrently editing its paired production file — in files the fixture's
    own operation never touched."""
    (repo / "unit_tests" / "test_author_owned.py").unlink()
    _write(repo / "prod" / "author_owned.py", "def owned_helper():\n    return 2\n")
    _run_git(["add", "-A"], repo)


def _build_cherry_pick_fixture(repo: Path) -> None:
    """Build a repo where the CURRENTLY STAGED content is a resolved-but-
    uncommitted cherry-pick of a change already recorded on another branch
    ("elsewhere") — a production edit concurrent with dropping a test
    file's worth of coverage, exactly the contract-shrinking shape, but
    recorded (committed) somewhere else first and then copied in.

    EMPIRICALLY CONFIRMED AT AUTHORING TIME (git 2.43.0): a CLEAN
    ``git cherry-pick --no-commit`` (no conflict) never writes
    ``CHERRY_PICK_HEAD`` at all — only a cherry-pick that actually
    CONFLICTS does, and the ref survives conflict resolution + `git add`
    right up until ``--continue``/``commit`` runs. So this fixture
    deliberately makes both branches edit the SAME line of the same file,
    forcing a real conflict, then resolves it by keeping the elsewhere
    (recorded) side — reproducing that recorded content here, with
    ``CHERRY_PICK_HEAD`` present and nothing yet committed. This is the
    realistic shape of "a commit that stages a copy of a change already
    recorded elsewhere ... with a record of the operation in progress".
    """
    base_branch = _init_repo(repo)
    _write(repo / "prod" / "copied.py", "def copied_helper():\n    return 1\n")
    _write(repo / "unit_tests" / "test_copied.py", "def test_copied_case():\n    assert True\n")
    _run_git(["add", "-A"], repo)
    _run_git(["commit", "-q", "-m", "base"], repo)

    _run_git(["checkout", "-q", "-b", "elsewhere"], repo)
    (repo / "unit_tests" / "test_copied.py").unlink()
    _write(repo / "prod" / "copied.py", "def copied_helper():\n    return 99\n")
    _run_git(["add", "-A"], repo)
    _run_git(["commit", "-q", "-m", "elsewhere: refactor + drop coverage"], repo)
    elsewhere_sha = _run_git(["rev-parse", "HEAD"], repo).stdout.strip()

    _run_git(["checkout", "-q", base_branch], repo)
    _write(repo / "prod" / "copied.py", "def copied_helper():\n    return 2\n")
    _run_git(["add", "-A"], repo)
    _run_git(["commit", "-q", "-m", "unrelated: conflicting edit on the same line"], repo)

    pick = _run_git_probe(["cherry-pick", elsewhere_sha], repo)
    if pick.returncode == 0:
        raise RuntimeError(
            "Fixture setup failed: expected the cherry-pick to conflict "
            f"(both branches edited the same line) but it applied cleanly. "
            f"stdout={pick.stdout!r} stderr={pick.stderr!r}"
        )
    _run_git(["checkout", "--theirs", "prod/copied.py"], repo)
    _run_git(["add", "-A"], repo)

    staged = _staged_paths(repo)
    if "unit_tests/test_copied.py" not in staged or "prod/copied.py" not in staged:
        raise RuntimeError(
            f"Fixture setup failed: expected the resolved cherry-pick to "
            f"stage unit_tests/test_copied.py and prod/copied.py, got: {staged!r}"
        )


def _build_ordinary_fixture(repo: Path) -> None:
    """Build a repo with NO operation in progress: an ordinary staged
    change that itself is a genuine contract-shrinking shape (production
    edit concurrent with a pytest.skip addition) — the negative control this
    AC's third clause requires stay true."""
    _init_repo(repo)
    _write(repo / "prod" / "plain.py", "def plain_helper():\n    return 1\n")
    _write(
        repo / "unit_tests" / "test_plain.py",
        "def test_plain_one():\n    assert True\n\n\n"
        "def test_plain_two():\n    assert True\n",
    )
    _run_git(["add", "-A"], repo)
    _run_git(["commit", "-q", "-m", "base"], repo)

    _write(repo / "prod" / "plain.py", "def plain_helper():\n    return 2\n")
    _write(
        repo / "unit_tests" / "test_plain.py",
        "def test_plain_one():\n    assert True\n\n\n"
        "def test_plain_two():\n    pytest.skip('flaky')\n    assert True\n",
    )
    _run_git(["add", "-A"], repo)


# ---------------------------------------------------------------------------
# Test A — angle: criterion
# ---------------------------------------------------------------------------
class TestUndoOfLargeRecordedChangesetRaisesNoObjection(unittest.TestCase):
    """AC-1: content present only because it undoes a named recorded change
    is absent from the change set the check inspects, and the check raises
    no objection to it — proven with a real ``git revert --no-commit``."""

    def test_ge120e4_undo_of_a_large_recorded_changeset_raises_no_objection(self) -> None:
        # covers: GE-120e-4
        # angle: criterion
        """RED today (empirically confirmed, see module docstring): today's
        derivation only recognises MERGE_HEAD, so it attributes the entire
        reverted changeset (a production edit plus a whole test file's worth
        of coverage) to the revert's author, and check_contract_shrinking.py
        blocks. Once GE-120e-4 lands, REVERT_HEAD must be consulted the same
        way MERGE_HEAD is, and the check must pass clean.
        """
        if not _AUTHORED_CHANGE_OK:
            self.fail(_MISSING_DEPENDENCY_MSG)

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            _build_revert_fixture(repo)
            _assert_operation_record(self, repo, "REVERT_HEAD", ["MERGE_HEAD", "CHERRY_PICK_HEAD"])

            result = _run_check(repo)
            combined = result.stdout + result.stderr

            self.assertEqual(
                0, result.returncode,
                "check_contract_shrinking.py must raise no objection to a "
                f"bare revert of a recorded changeset. Output:\n{combined}",
            )
            self.assertNotIn(
                "test_recorded", combined,
                f"The reverted content must not be named as a violation. Output:\n{combined}",
            )
            self.assertNotIn("BLOCKED", combined)


# ---------------------------------------------------------------------------
# Test B — angle: criterion
# ---------------------------------------------------------------------------
class TestCopyOfChangeRecordedElsewhereRaisesNoObjection(unittest.TestCase):
    """AC-1 (second half): content present only because it reproduces a
    change already recorded elsewhere is attributed to its source, not the
    author — proven with a real ``git cherry-pick --no-commit``."""

    def test_ge120e4_copy_of_a_change_recorded_elsewhere_raises_no_objection(self) -> None:
        # covers: GE-120e-4
        # angle: criterion
        """RED today: today's derivation does not recognise CHERRY_PICK_HEAD
        at all, so it attributes the entire cherry-picked changeset (a
        production edit concurrent with dropping a whole test file) to the
        person doing the cherry-pick, and the check blocks. Once GE-120e-4
        lands, the check must pass clean.
        """
        if not _AUTHORED_CHANGE_OK:
            self.fail(_MISSING_DEPENDENCY_MSG)

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            _build_cherry_pick_fixture(repo)
            _assert_operation_record(self, repo, "CHERRY_PICK_HEAD", ["MERGE_HEAD", "REVERT_HEAD"])

            result = _run_check(repo)
            combined = result.stdout + result.stderr

            self.assertEqual(
                0, result.returncode,
                "check_contract_shrinking.py must raise no objection to a "
                f"bare cherry-pick of a change recorded elsewhere. Output:\n{combined}",
            )
            self.assertNotIn(
                "test_copied", combined,
                f"The cherry-picked content must not be named as a violation. Output:\n{combined}",
            )
            self.assertNotIn("BLOCKED", combined)


# ---------------------------------------------------------------------------
# Test C — angle: criterion
# ---------------------------------------------------------------------------
class TestAuthorsOwnEditsOnTopOfTheOperationAreInspected(unittest.TestCase):
    """AC-2: content the author wrote ON TOP of the revert/cherry-pick is
    present in the inspected change set and the check reaches its verdict
    on it — proven on the SAME commit as a carried-in undo, so the exclusion
    of one and the inclusion of the other must coexist correctly."""

    def test_ge120e4_authors_own_edits_on_top_of_the_operation_are_inspected(self) -> None:
        # covers: GE-120e-4
        # angle: criterion
        """RED today: today's blocked output already names the reverted
        content (see module docstring), so this test's negative assertions
        (the reverted content must be absent) fail today for the same
        reason as Test A. Once GE-120e-4 lands: the author's own,
        independent violation (deleting unit_tests/test_author_owned.py
        while editing prod/author_owned.py — files the revert never
        touched) must still block the commit and be named in the
        objection, while the reverted content stays excluded.
        """
        if not _AUTHORED_CHANGE_OK:
            self.fail(_MISSING_DEPENDENCY_MSG)

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            _build_revert_fixture(repo)
            _assert_operation_record(self, repo, "REVERT_HEAD", ["MERGE_HEAD", "CHERRY_PICK_HEAD"])
            _stage_author_violation(repo)

            result = _run_check(repo)
            combined = result.stdout + result.stderr

            self.assertNotEqual(
                0, result.returncode,
                "The author's own, independent violation (on top of the "
                f"revert) must still block the commit. Output:\n{combined}",
            )
            self.assertIn(
                "test_author_owned.py", combined,
                f"The author's own deleted test file must be named. Output:\n{combined}",
            )
            self.assertNotIn(
                "test_recorded", combined,
                "The reverted content must NOT be attributed to the author "
                f"even though a real violation of their own coexists in the "
                f"same commit. Output:\n{combined}",
            )


# ---------------------------------------------------------------------------
# Test D — angle: boundary
# ---------------------------------------------------------------------------
class TestOrdinaryCommitChangeSetIsTheEntireStagedContent(unittest.TestCase):
    """AC-3 (negative control): with no operation in progress and one state
    to compare against, the change set is the author's entire staged
    content, so the rule narrows nothing on the common path — the one/many
    state boundary this AC's narrowing must not accidentally widen across."""

    def test_ge120e4_ordinary_commit_change_set_is_the_entire_staged_content(self) -> None:
        # covers: GE-120e-4
        # angle: boundary
        """Not expected to be RED by itself (GE-120e-1 already establishes
        this behaviour for the no-operation-record case; GE-120e-4 must not
        regress it) — included as the explicit negative control this AC's
        third clause requires, and as the test-runner's proof that the
        eventual REVERT_HEAD/CHERRY_PICK_HEAD extension does not quietly
        also narrow the ordinary path. Asserted from two independent
        angles: the shared derivation's own `.states`/`.diff_text`, AND the
        real check's process-level verdict.
        """
        if not _AUTHORED_CHANGE_OK:
            self.fail(_MISSING_DEPENDENCY_MSG)

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            _build_ordinary_fixture(repo)

            for ref in ("MERGE_HEAD", "REVERT_HEAD", "CHERRY_PICK_HEAD"):
                probe = _run_git_probe(["rev-parse", "-q", "--verify", ref], repo)
                self.assertNotEqual(
                    0, probe.returncode,
                    f"Fixture setup failed: {ref} unexpectedly present — "
                    "this fixture must have NO operation record at all.",
                )

            expected_diff = _run_git(["diff", "--cached"], repo).stdout

            authored = get_authored_change(cwd=repo)
            self.assertFalse(
                authored.could_not_check,
                f"get_authored_change() reported could_not_check on an "
                f"ordinary staged commit with no operation record — this is "
                f"the common path and must never fail here "
                f"(error={authored.error!r}).",
            )
            self.assertEqual(
                ["HEAD"], authored.states,
                "With no operation in progress, the derivation must report "
                f"exactly one state (HEAD). Got: {authored.states!r}",
            )
            self.assertEqual(
                expected_diff, authored.diff_text,
                "On an ordinary (single-state) commit, the shared "
                "derivation's diff_text must equal `git diff --cached` "
                "byte for byte — the rule narrows nothing on the common path.",
            )

            result = _run_check(repo)
            combined = result.stdout + result.stderr
            self.assertNotEqual(
                0, result.returncode,
                "Sanity check on the fixture itself: an ordinary commit "
                f"with a real contract-shrinking violation must still be "
                f"blocked. Output:\n{combined}",
            )
            self.assertIn("pytest.skip added", combined)


# ---------------------------------------------------------------------------
# Test E — angle: criterion (the load-bearing clause)
# ---------------------------------------------------------------------------
class TestCarriedInContentExcludedWithNoMergeMarkerPresent(unittest.TestCase):
    """AC-4 (load-bearing): the change set is worked out from the states the
    commit is built on and the record of the operation in progress
    TOGETHER, so it is never decided by asking whether a merge in
    particular is under way. Proven on an operation where NO merge marker
    exists at all (a bare revert): carried-in content must still be absent
    from what the check objects to, and the derivation's own provenance
    must never include "MERGE_HEAD" for this fixture."""

    def test_ge120e4_carried_in_content_excluded_with_no_merge_marker_present(self) -> None:
        # covers: GE-120e-4
        # angle: criterion
        """RED today for the same empirically-confirmed reason as Test A:
        with no MERGE_HEAD probe recognising REVERT_HEAD, today's derivation
        attributes the reverted content to the author and the check blocks.
        Deliberately does NOT rely on direct-import assertions alone (per
        this AC's own test_rationale, "Direct-import testing of the
        derivation cannot cover any of this ... the criterion is what the
        check does") — the primary assertion is the real check's
        process-level verdict; the direct `get_authored_change()` read is
        supplementary, confirming the internal provenance never routes
        through a merge-specific answer.
        """
        if not _AUTHORED_CHANGE_OK:
            self.fail(_MISSING_DEPENDENCY_MSG)

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            _build_revert_fixture(repo)
            _assert_operation_record(self, repo, "REVERT_HEAD", ["MERGE_HEAD", "CHERRY_PICK_HEAD"])

            result = _run_check(repo)
            combined = result.stdout + result.stderr
            self.assertEqual(
                0, result.returncode,
                "With no merge marker present at all (a bare revert), the "
                f"check must raise no objection to the carried-in undo. "
                f"Output:\n{combined}",
            )
            self.assertNotIn("test_recorded", combined)
            self.assertNotIn("BLOCKED", combined)

            authored = get_authored_change(cwd=repo)
            self.assertFalse(authored.could_not_check, f"error={authored.error!r}")
            self.assertNotIn(
                "MERGE_HEAD", authored.states,
                "The derivation's own provenance must never name MERGE_HEAD "
                f"for a fixture with no merge in progress — the answer must "
                f"come from the states this commit is built on plus "
                f"whichever operation record is actually present, never "
                f"from asking 'is a merge under way'. Got: {authored.states!r}",
            )
            self.assertNotIn(
                "unit_tests/test_recorded.py", authored.diff_text,
                "The shared derivation's own diff_text must exclude the "
                f"reverted file's content. Got diff_text: {authored.diff_text!r}",
            )


# ---------------------------------------------------------------------------
# Test F — angle: reachability (REQUIRED by this ticket's Test Requirements)
# ---------------------------------------------------------------------------
class TestReachableFromEntryPoint(unittest.TestCase):
    """REQUIRED reachability angle. Entry-point resolution (per the
    test-writer skill's "Reachability Entry-Point Resolution" procedure):
    this AC's test_spec names no surface, so Step 1 was walked against the
    real repository. check_contract_shrinking.py is registered as a
    pre-commit hook in commit_guardian.json with
    `"entry": "python {{output_root}}/scripts/commit_guardian/run_hook.py
    {{output_root}}/scripts/commit_guardian/check_contract_shrinking.py"` —
    a genuine Step-1-item-2 (pre-commit hook) match. Resolved to: dispatch
    via that hook's own real runner (run_hook.py) against the DEPLOYED copy
    (built via build_commit_guardian, per this ticket's own "TEMPLATE/
    DEPLOYED PARITY (ADR-001)" Implementation Note) — not a direct call to
    the check's Python function, and not the source-tree copy alone.
    """

    def test_ge_120e_4_reachable_from_entry_point(self) -> None:
        # covers: GE-120e-4
        # angle: reachability
        """RED today for the same reason as Test A/E, additionally proving
        the fix is reachable via the REAL deployed dispatch path
        (run_hook.py -> the deployed check_contract_shrinking.py), not only
        importable from templates/scripts/commit_guardian/ source.
        """
        if not _BUILD_PHASES_OK:
            self.fail(
                "scripts.build_phases.build_commit_guardian could not be "
                "imported — cannot deploy the commit_guardian scripts into "
                "the fixture repo to test the deployed entry point."
            )
        if not _AUTHORED_CHANGE_OK:
            self.fail(_MISSING_DEPENDENCY_MSG)

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            _build_revert_fixture(repo)
            _assert_operation_record(self, repo, "REVERT_HEAD", ["MERGE_HEAD", "CHERRY_PICK_HEAD"])

            written = build_commit_guardian(
                repo,
                {
                    "output_root": ".leafcutter",
                    "agents_dir": ".claude/agents",
                    "skills_dir": ".claude/skills",
                },
                dry_run=False,
                force=True,
            )
            deployed_check = repo / "scripts" / "commit_guardian" / "check_contract_shrinking.py"
            deployed_authored_change = repo / "scripts" / "commit_guardian" / "_authored_change.py"
            if written <= 0 or not deployed_check.exists() or not deployed_authored_change.exists():
                self.fail(
                    "build_commit_guardian() did not produce a deployed "
                    f"{repo}/scripts/commit_guardian/ layout including "
                    "check_contract_shrinking.py and _authored_change.py — "
                    "cannot exercise the deployed entry point."
                )

            result = _run_check_via_entry_point(repo, deployed_check)
            combined = result.stdout + result.stderr

            self.assertEqual(
                0, result.returncode,
                "The DEPLOYED check, dispatched via the real run_hook.py "
                f"entry point, must raise no objection to a bare revert of "
                f"a recorded changeset. Output:\n{combined}",
            )
            self.assertNotIn("test_recorded", combined)


if __name__ == "__main__":
    unittest.main()
