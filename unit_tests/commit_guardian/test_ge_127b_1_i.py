"""
MODULE: unit_tests/commit_guardian/test_ge_127b_1_i.py
COVERS: GE-127b-1-i -- "A run that could not establish any previous length
    says which situation it is in and refuses, and a clean run states how
    many files it compared"

GOAL: RED test-first stubs for the fail-closed floor under GE-127b-1's
    ratchet. The production module under test,
    templates/scripts/commit_guardian/check_file_size.py (plus its sibling
    _file_size_ratchet.py), still encodes the SUPERSEDED three-refusing
    reading as of this resync -- see PreviousLengthSourceError's "holds no
    covered file whatsoever" branch in resolve_head_covered_paths() and its
    "HEAD does not resolve" branch, both of which currently refuse (exit 2)
    situations the 2026-09-01 criteria correction requires to COMPLETE
    (exit 0). python-coder must narrow the refusing set to exactly two --
    source unreachable, source uninterpretable -- per GE-127b-1-i's
    it_requirements, reusing BP-100n-4-ii's verdict vocabulary
    ("INDETERMINATE: reason=<text>" with a 0/1/2 exit-status contract)
    unchanged.

BUSINESS CONTEXT: see
    docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/GE-127b-1-i.yaml.
    This record exists to stop a FIFTH guard in this repository shipping the
    exact fail-open shape four prior guards shipped (KI-CG-034, KI-CG-012,
    KI-CG-018, the AC-store validator's bare-directory no-op): an error path
    that silently yields an empty population instead of raising a named,
    refusing INDETERMINATE verdict. It ALSO exists to stop the opposite
    defect the 2026-09-01 correction fixes: a successfully-empty history
    being folded into that same refusing set, which deadlocks every fresh
    consumer-project install (the first commit adding a covered file is
    refused forever, since no later commit can ever populate the history
    that refusal is blocking on).

VERDICT VOCABULARY, PINNED BY THE AC AND REUSED HERE UNCHANGED (see
    check_hook_trigger_reachability.py and check_build_drift.py in this same
    directory for prior art of the SAME contract in this repo):
      - exit 0: clean run, compared-count stated and (if > 0) nothing grew.
        An empty history additionally names itself in this outcome, as
        "EMPTY HISTORY: reason=<text>" -- pinned here as the target wording
        BECAUSE it must NOT borrow the INDETERMINATE token (bound to exit 2
        by the pinned contract) while still following this repo's
        established "TOKEN: reason=<text>" naming convention (INDETERMINATE,
        UNCOMPARABLE, UNREACHABLE, DUPLICATE-ID, REJECTED EXEMPTION ENTRY).
      - exit 1: a reported finding (e.g. GE-127b-1's grew-and-refused case).
      - exit 2: INDETERMINATE -- previous-length source could not be
        established, printed as "INDETERMINATE: reason=<text>".

EXERCISE STRATEGY: identical to test_ge_127b_1.py -- real git repos, real
    commits, real staged content, real subprocess invocations of the actual
    check_file_size.py / run_hook.py / deployed build.py output. The TWO
    unresolvable-source scenarios are constructed by making the lookup
    GENUINELY unavailable at run time (a working copy that is not a git
    repository at all; a HEAD blob that is not valid UTF-8) rather than by
    asserting an error branch exists in the source, per BP-100k-4-i's
    standing constraint this AC's doc_links cite explicitly. The TWO
    completing empty-history scenarios (a HEAD tree with zero covered
    files; an unborn HEAD with no commit at all) are constructed the same
    way, for the same reason -- neither may be built as a stand-in for
    "unreachable" per the 2026-09-01 correction.

DECISION HISTORY
- 2026-09-01 [GE-127b-1-i/test-writer]: Initial authoring of all nine RED
    test stubs per GE-127b-1-i's test_spec. Verified RED via
    `python -m unittest discover -s unit_tests/commit_guardian -t . -p
    "test_ge_127b_1_i.py"` -- see the test-writer sign-off comment on the
    ticket for the exact captured failures.
- 2026-09-07 [GE-127b-1-i-resync/test-writer]: TEST RESYNC to the
    2026-09-01 criteria correction (removes the empty-history case from the
    refusing set) and the same-day it-po enrichment-resync (reclassifies an
    unborn HEAD as the empty-history case rather than the
    cannot-be-reached one). Renamed and rewrote the third-situation test to
    test_ge_127b_1_i_a_history_holding_no_covered_file_completes_and_is_named_apart_from_both_refusals,
    asserting BOTH halves (completes AND is named apart) by contrast across
    all three named situations, never against a hard-coded literal. Fixed
    every "unreachable" fixture in this module that had built an unborn
    HEAD (test 1, the pairwise-distinctness test, the absence-asserting
    test, the reachability test, the deployed test) to instead build a
    working copy that is genuinely not a git repository -- an unborn HEAD
    is now the empty-history completing case and building it as
    "unreachable" would silently reinstate the exact bootstrap deadlock the
    correction removed, one layer down in the test suite instead of the
    criteria. Narrowed the absence-asserting test and its pairwise
    counterpart from three unresolvable situations to two. Pinned
    "EMPTY HISTORY: reason=<text>" as the target wording for the
    completing-but-named path, distinct from the INDETERMINATE token by
    design (see VERDICT VOCABULARY above). RED IS EXPECTED AND CORRECT:
    check_file_size.py / _file_size_ratchet.py still refuse the
    empty-history fixtures (PreviousLengthSourceError's "holds no covered
    file whatsoever" and "HEAD does not resolve" branches), so the
    rewritten completing-path assertions fail until python-coder narrows
    the refusing set. Verified via
    `python -m unittest discover -s unit_tests/commit_guardian -t . -p
    "test_ge_127b_1_i.py"` -- see the test-writer sign-off comment on the
    ticket for the exact captured failures.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CHECK_FILE_SIZE = _COMMIT_GUARDIAN_DIR / "check_file_size.py"
_RUN_HOOK = _COMMIT_GUARDIAN_DIR / "run_hook.py"
_BUILD_PY = _REPO_ROOT / "scripts" / "build.py"
_CONFIG_PATH = _COMMIT_GUARDIAN_DIR / "commit_guardian.json"

_PYTHON = sys.executable
_SUBPROCESS_TIMEOUT_SECONDS = 30
_BUILD_TIMEOUT_SECONDS = 120

_CONFIG = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
_PY_LIMIT = _CONFIG["file_size"]["line_limits"][".py"]

_INDETERMINATE_EXIT = 2
_FINDING_EXIT = 1
_CLEAN_EXIT = 0

# Loose extraction of "the number of files compared" from the gate's own
# output -- deliberately tolerant of the eventual exact phrasing, since the
# production wording does not exist yet. Any implementation MUST print a
# number adjacent to the word "compar" (matches "compared"/"comparing"/
# "comparison") for these tests to find it.
_COMPARED_COUNT_RE = re.compile(r"compar\w*\D{0,20}(\d+)", re.IGNORECASE)
_INDETERMINATE_RE = re.compile(r"INDETERMINATE:\s*reason=(.+)", re.IGNORECASE)
# Pinned target wording for the completing-but-named empty-history path (see
# the module docstring's VERDICT VOCABULARY section for why this must be a
# DIFFERENT token from INDETERMINATE, which the pinned contract binds to
# exit 2 -- an empty history completes at exit 0).
_EMPTY_HISTORY_RE = re.compile(r"EMPTY HISTORY:\s*reason=(.+)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Fixture helpers (mirrors test_ge_127b_1.py's conventions)
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=check,
    )


def _init_repo(root: Path) -> None:
    _git(["init", "-q"], root)
    _git(["config", "user.email", "test-writer@example.com"], root)
    _git(["config", "user.name", "GE-127b-1-i test fixture"], root)


def _commit_all(root: Path, message: str) -> None:
    _git(["add", "-A"], root)
    _git(["commit", "-q", "-m", message], root)


def _stage_all(root: Path) -> None:
    _git(["add", "-A"], root)


def _content(n_lines: int, tag: str = "v") -> str:
    return "\n".join(f"{tag}_{i:06d} = {i}" for i in range(n_lines)) + "\n"


def _run_check(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_PYTHON, str(_CHECK_FILE_SIZE)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _run_check_via_hook(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_PYTHON, str(_RUN_HOOK), str(_CHECK_FILE_SIZE)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _extract_compared_count(output: str) -> int | None:
    match = _COMPARED_COUNT_RE.search(output)
    if match is None:
        return None
    return int(match.group(1))


def _extract_indeterminate_reason(output: str) -> str | None:
    match = _INDETERMINATE_RE.search(output)
    if match is None:
        return None
    return match.group(1).strip()


def _extract_empty_history_naming(output: str) -> str | None:
    match = _EMPTY_HISTORY_RE.search(output)
    if match is None:
        return None
    return match.group(1).strip()


def _make_unreachable_source_root(root: Path) -> None:
    """Build a GENUINELY broken previous-length source: a working copy that
    is not a git repository at all.

    This is the "cannot be reached at all" situation -- a broken
    environment, distinct from BOTH empty-history completing scenarios (a
    populated HEAD holding no covered file; an unborn HEAD with no commit
    at all). Deliberately never calls `_init_repo()` and never stages
    anything -- there is no git index to stage into.

    Args:
        root: Directory to create the broken working copy in. Must not
            already exist as a git repository.
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "fresh.py").write_text(_content(10), encoding="utf-8")


def _make_uninterpretable_source_root(root: Path) -> None:
    """Build a source that resolves but whose HEAD blob cannot be decoded.

    Args:
        root: Directory to initialize a real git repository in.
    """
    root.mkdir(parents=True, exist_ok=True)
    _init_repo(root)
    bad = root / "bad.py"
    bad.write_bytes(b"\xff\xfe\x00\x01not valid utf-8\n")
    _commit_all(root, "commit a file with an undecodable HEAD blob")
    bad.write_text(_content(10), encoding="utf-8")
    _stage_all(root)


def _make_empty_history_populated_root(root: Path) -> None:
    """Build a repository whose HEAD resolves (a real commit exists) and
    holds no covered file at all -- only a non-covered README.md.

    Per the 2026-09-01 criteria correction this COMPLETES (exit 0) and is
    additionally named in the outcome apart from both refusing situations.
    This is the identical fixture GE-127b-1's fourth arm
    (test_ge_127b_1_a_newly_added_file_below_its_limit_commits_and_is_not_treated_as_having_grown)
    requires exit 0 for.

    Args:
        root: Directory to initialize a real git repository in.
    """
    root.mkdir(parents=True, exist_ok=True)
    _init_repo(root)
    (root / "README.md").write_text("no covered files here\n", encoding="utf-8")
    _commit_all(root, "HEAD holds only a non-covered file")
    (root / "fresh.py").write_text(_content(10), encoding="utf-8")
    _stage_all(root)


def _make_unborn_head_root(root: Path) -> None:
    """Build a repository with no commit at all -- HEAD does not resolve.

    RECLASSIFIED per the 2026-09-01 correction and the same-day it-po
    enrichment-resync: an unborn HEAD is the EMPTY-HISTORY completing case,
    NOT the source-unreachable one. A repository at its first commit is an
    ordinary day-one state of a healthy system (the discriminating
    question the correction pins), never evidence of a broken environment.
    Building this as "unreachable" would silently reinstate the exact
    bootstrap deadlock the correction removed: the very first commit into a
    fresh repository has no HEAD, so it would be refused forever.

    Args:
        root: Directory to initialize a real git repository in.
    """
    root.mkdir(parents=True, exist_ok=True)
    _init_repo(root)
    (root / "fresh.py").write_text(_content(10), encoding="utf-8")
    _stage_all(root)


class SourceFixtureTestCase(unittest.TestCase):
    """Shared tempdir + git-repo scaffolding."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)


# ---------------------------------------------------------------------------
# 1. Source unreadable -- no HEAD commit exists at all
# ---------------------------------------------------------------------------


class TestUnreadableSourceNamesItselfAndRefuses(SourceFixtureTestCase):
    def test_ge_127b_1_i_an_unreadable_previous_length_source_is_named_as_such_and_refuses(self):
        # covers: GE-127b-1-i
        # angle: failure
        """With the previous-length source made GENUINELY unavailable at run
        time -- a working copy that is not a git repository at all -- the
        executed gate must state that the previous lengths could not be
        established, name this specific situation as the could-not-be-read
        one, and the commit must not complete (exit 2, INDETERMINATE).

        DO NOT use a repository with no commit yet (an unborn HEAD) as this
        fixture: per the 2026-09-01 criteria correction and the same-day
        it-po enrichment-resync, an unborn HEAD is the EMPTY-HISTORY case
        that must COMPLETE, and building it here would reinstate the
        bootstrap deadlock the correction removed while looking like a
        passing test.

        RED TODAY: check_file_size.py's get_staged_files() calls
        `git diff --cached --name-status` with check=True and no
        surrounding try/except; against a working copy that is not a git
        repository at all this raises subprocess.CalledProcessError
        uncaught, crashing the process with a traceback rather than
        emitting a named INDETERMINATE verdict.
        """
        _make_unreachable_source_root(self.root)

        result = _run_check(self.root)

        self.assertEqual(
            _INDETERMINATE_EXIT,
            result.returncode,
            msg=(
                "An unresolvable HEAD must produce the INDETERMINATE exit code "
                f"(2), not a crash or a silent pass/fail. stdout={result.stdout!r} "
                f"stderr={result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        reason = _extract_indeterminate_reason(combined)
        self.assertIsNotNone(
            reason,
            msg=f"Expected an 'INDETERMINATE: reason=...' line. Got: {combined!r}",
        )


# ---------------------------------------------------------------------------
# 2. Source uninterpretable -- HEAD blob is not decodable
# ---------------------------------------------------------------------------


class TestUninterpretableSourceNamesDistinctReasonAndRefuses(SourceFixtureTestCase):
    def test_ge_127b_1_i_an_uninterpretable_previous_length_source_names_its_own_reason_and_refuses(self):
        # covers: GE-127b-1-i
        # angle: failure
        """A source that resolves (HEAD exists) but whose content cannot be
        interpreted -- a HEAD blob that cannot be decoded in the encoding
        the standard reads -- must be reported with a reason naming that
        situation specifically, distinct in text from the could-not-be-read
        one, and the commit must not complete (exit 2).

        RED TODAY: check_file_size.py has no previous-length lookup of any
        kind, so it never attempts to decode a HEAD blob and never emits an
        INDETERMINATE verdict at all.
        """
        _init_repo(self.root)
        bad = self.root / "bad.py"
        # Invalid UTF-8 byte sequence committed as the file's HEAD content.
        bad.write_bytes(b"\xff\xfe\x00\x01not valid utf-8\n")
        _commit_all(self.root, "commit a file with an undecodable HEAD blob")

        bad.write_text(_content(10), encoding="utf-8")
        _stage_all(self.root)

        result = _run_check(self.root)

        self.assertEqual(
            _INDETERMINATE_EXIT,
            result.returncode,
            msg=(
                "An undecodable HEAD blob must produce the INDETERMINATE exit "
                f"code (2). stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        reason = _extract_indeterminate_reason(combined)
        self.assertIsNotNone(
            reason,
            msg=f"Expected an 'INDETERMINATE: reason=...' line. Got: {combined!r}",
        )


# ---------------------------------------------------------------------------
# 3. An empty history completes and is named apart from both refusals --
#    THE ANTI-DEADLOCK DESCRIPTOR (2026-09-01 correction)
# ---------------------------------------------------------------------------


class TestEmptyHistoryCompletesAndIsNamedApartFromBothRefusals(SourceFixtureTestCase):
    def test_ge_127b_1_i_a_history_holding_no_covered_file_completes_and_is_named_apart_from_both_refusals(
        self,
    ):
        # covers: GE-127b-1-i
        # angle: boundary
        """THE ANTI-DEADLOCK DESCRIPTOR -- BOTH HALVES ARE MANDATORY AND
        NEITHER SUBSTITUTES FOR THE OTHER. A source that resolves
        successfully and holds no covered file at all -- a repository whose
        history contains none (only a README.md), and separately one with
        no commit at all (an unborn HEAD) -- is exercised by staging the
        first covered file into it and performing an ordinary commit.

        HALF ONE: the commit COMPLETES (exit 0), for BOTH empty-history
        sub-fixtures. Exit status alone would let an implementation pass
        while emitting nothing about the empty history, which is the
        readability half of the criterion -- so this half alone is not
        sufficient, see HALF TWO.

        HALF TWO: the outcome NAMES that situation, and the naming text is
        distinct from the reason text emitted by BOTH refusing runs. Naming
        alone would let an implementation emit the sentence and still
        refuse, which is the deadlock -- so this half alone is not
        sufficient either.

        Half two is asserted BY CONTRAST: all three named situations
        (unreachable, uninterpretable, empty-history) are exercised in this
        one test, and their extracted texts are required to be pairwise
        distinct -- never asserted against a hard-coded literal, so an
        implementation cannot satisfy this by choosing any fixed wording
        the test author happened to guess.

        This descriptor is the executable form of the 2026-09-01
        correction: an empty history is an ordinary day-one state of any
        consumer project, and refusing it means the first commit that would
        populate the history is the one being refused, so no later commit
        can ever fix it and only a hook bypass escapes.

        RED TODAY: check_file_size.py / _file_size_ratchet.py still refuse
        BOTH empty-history sub-fixtures (PreviousLengthSourceError's "holds
        no covered file whatsoever" branch for the populated-but-empty
        case, and its "HEAD does not resolve" branch for the unborn-HEAD
        case) -- both currently exit 2 (INDETERMINATE), contradicting HALF
        ONE. No "EMPTY HISTORY: reason=..." wording exists anywhere in the
        source, contradicting HALF TWO.
        """
        # (a) unreachable: a working copy that is not a git repository.
        unreachable_root = self.root / "unreachable"
        _make_unreachable_source_root(unreachable_root)
        result_a = _run_check(unreachable_root)

        # (b) uninterpretable: HEAD blob not valid UTF-8.
        uninterpretable_root = self.root / "uninterpretable"
        _make_uninterpretable_source_root(uninterpretable_root)
        result_b = _run_check(uninterpretable_root)

        # (c) empty history, sub-fixture 1: HEAD resolves (a real commit
        # exists), holds no covered file.
        empty_populated_root = self.root / "empty_populated"
        _make_empty_history_populated_root(empty_populated_root)
        result_c = _run_check(empty_populated_root)

        # (d) empty history, sub-fixture 2: unborn HEAD, no commit at all.
        # RECLASSIFIED per the 2026-09-01 correction -- this belongs HERE,
        # not among the refusing fixtures above.
        unborn_root = self.root / "unborn"
        _make_unborn_head_root(unborn_root)
        result_d = _run_check(unborn_root)

        # --- Fixture sanity: the two refusing fixtures actually refuse. ---
        # This test's contrast is meaningless if either failed to construct
        # the refusing situation it claims to.
        self.assertEqual(
            _INDETERMINATE_EXIT,
            result_a.returncode,
            msg=(
                "Fixture sanity: the unreachable-source fixture must refuse "
                f"(exit 2). stdout={result_a.stdout!r} stderr={result_a.stderr!r}"
            ),
        )
        self.assertEqual(
            _INDETERMINATE_EXIT,
            result_b.returncode,
            msg=(
                "Fixture sanity: the uninterpretable-source fixture must "
                f"refuse (exit 2). stdout={result_b.stdout!r} stderr={result_b.stderr!r}"
            ),
        )

        # --- HALF ONE: both empty-history sub-fixtures COMPLETE. ---
        self.assertEqual(
            _CLEAN_EXIT,
            result_c.returncode,
            msg=(
                "A populated HEAD holding no covered file must COMPLETE "
                "(exit 0) -- this is the identical fixture GE-127b-1's "
                "fourth arm requires exit 0 for. Refusing it deadlocks a "
                f"fresh repository. stdout={result_c.stdout!r} stderr={result_c.stderr!r}"
            ),
        )
        self.assertEqual(
            _CLEAN_EXIT,
            result_d.returncode,
            msg=(
                "An unborn HEAD (no commit at all) is the EMPTY-HISTORY "
                "case per the 2026-09-01 correction and must COMPLETE "
                f"(exit 0), not be treated as unreachable. stdout={result_d.stdout!r} "
                f"stderr={result_d.stderr!r}"
            ),
        )

        # --- HALF TWO: the empty history is NAMED, distinct from both
        # refusing reasons, asserted by contrast across all three
        # situations. ---
        reason_a = _extract_indeterminate_reason(result_a.stdout + result_a.stderr)
        reason_b = _extract_indeterminate_reason(result_b.stdout + result_b.stderr)
        naming_c = _extract_empty_history_naming(result_c.stdout + result_c.stderr)
        naming_d = _extract_empty_history_naming(result_d.stdout + result_d.stderr)

        self.assertIsNotNone(
            reason_a, msg=f"Expected an 'INDETERMINATE: reason=...' line. Got: {result_a.stdout + result_a.stderr!r}"
        )
        self.assertIsNotNone(
            reason_b, msg=f"Expected an 'INDETERMINATE: reason=...' line. Got: {result_b.stdout + result_b.stderr!r}"
        )
        self.assertIsNotNone(
            naming_c,
            msg=(
                "Expected the empty history to be named in the exit-0 "
                f"outcome. Got: {result_c.stdout + result_c.stderr!r}"
            ),
        )
        self.assertIsNotNone(
            naming_d,
            msg=(
                "Expected the empty history to be named in the exit-0 "
                f"outcome. Got: {result_d.stdout + result_d.stderr!r}"
            ),
        )
        self.assertEqual(
            naming_c,
            naming_d,
            msg="Both empty-history sub-fixtures name the SAME situation and must produce the same text.",
        )

        texts = {reason_a, reason_b, naming_c}
        self.assertEqual(
            3,
            len(texts),
            msg=(
                "The two refusing reasons and the empty-history naming must "
                f"be pairwise distinct. Got: reason_a={reason_a!r} "
                f"reason_b={reason_b!r} naming_c={naming_c!r}"
            ),
        )

    def test_ge_127b_1_i_the_two_unresolvable_reasons_are_pairwise_distinct(self):
        # covers: GE-127b-1-i
        # angle: failure
        """THE TWO REFUSING SITUATIONS ARE DISTINGUISHED BY NAME. Build both
        unresolvable scenarios (unreachable working copy, uninterpretable
        blob) and assert their extracted reason strings are distinct --
        collapsing them into a shared message costs the reader the only
        information that separates a broken environment from a source that
        resolves but carries content that cannot be read.

        NARROWED from three to two situations per the 2026-09-01 criteria
        correction: an empty history is no longer part of this refusing
        arithmetic (see the anti-deadlock descriptor above for its own,
        separate naming requirement).

        RED TODAY: no INDETERMINATE verdict exists in either scenario, so
        no reason string can be extracted at all.
        """
        unreachable_root = self.root / "unreachable"
        _make_unreachable_source_root(unreachable_root)
        result_a = _run_check(unreachable_root)
        reason_a = _extract_indeterminate_reason(result_a.stdout + result_a.stderr)

        uninterpretable_root = self.root / "uninterpretable"
        _make_uninterpretable_source_root(uninterpretable_root)
        result_b = _run_check(uninterpretable_root)
        reason_b = _extract_indeterminate_reason(result_b.stdout + result_b.stderr)

        self.assertIsNotNone(reason_a, msg=f"Both scenarios must emit an INDETERMINATE reason. Got: {reason_a!r}")
        self.assertIsNotNone(reason_b, msg=f"Both scenarios must emit an INDETERMINATE reason. Got: {reason_b!r}")
        self.assertNotEqual(
            reason_a,
            reason_b,
            msg=f"The two unresolvable reasons must be distinct. Got: {reason_a!r} vs {reason_b!r}",
        )


# ---------------------------------------------------------------------------
# 4. The seam: all-new-files commit against a populated history completes
# ---------------------------------------------------------------------------


class TestAllNewFilesCommitAgainstPopulatedHistoryCompletes(SourceFixtureTestCase):
    def test_ge_127b_1_i_a_commit_adding_only_new_covered_files_against_a_populated_history_completes(self):
        # covers: GE-127b-1-i
        # angle: seam
        """THE SEAM DESCRIPTOR THAT KEEPS THIS RECORD FROM BREAKING ITS
        PARENT. In a repository whose HEAD already holds at least one
        covered file, stage a commit consisting only of NEWLY ADDED covered
        files, all below their permitted lengths. The commit must complete
        (exit 0), and the outcome must state a compared count of ZERO
        without that zero causing a refusal. An implementation that reads
        "holds a previous length for no file whatsoever" as the PER-COMMIT
        lookup result rather than as the resolution of the SOURCE refuses
        this commit and contradicts GE-127b-1's fourth arm. This descriptor
        and GE-127b-1's newly-added-file descriptor must be green
        simultaneously.

        RED TODAY: no compared-count is ever stated in the output.
        """
        _init_repo(self.root)
        existing = self.root / "existing.py"
        existing.write_text(_content(20), encoding="utf-8")
        _commit_all(self.root, "HEAD holds one covered file")

        brand_new = self.root / "brand_new.py"
        brand_new.write_text(_content(15), encoding="utf-8")
        _stage_all(self.root)

        result = _run_check(self.root)

        self.assertEqual(
            _CLEAN_EXIT,
            result.returncode,
            msg=(
                "A commit staging only newly added covered files, against a "
                "populated HEAD, must complete. "
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        count = _extract_compared_count(combined)
        self.assertEqual(
            0,
            count,
            msg=(
                "The outcome must state a compared count of ZERO (no staged file "
                f"had a predecessor). Got count={count!r} from: {combined!r}"
            ),
        )


# ---------------------------------------------------------------------------
# 5. Neither unavailable situation reports false all-clear
# ---------------------------------------------------------------------------


class TestUnavailableSituationsNeverReportFalseAllClear(SourceFixtureTestCase):
    def test_ge_127b_1_i_neither_unavailable_situation_reports_any_file_as_not_having_grown(self):
        # covers: GE-127b-1-i
        # angle: failure
        """In NEITHER of the two unresolvable situations may the commit
        complete as though every staged covered file had been compared
        against its previous length and found not to have grown.

        NARROWED from three to two situations per the 2026-09-01 criteria
        correction: an empty history is no longer an unresolvable situation
        -- it is a completing one (see the anti-deadlock descriptor above),
        so it is deliberately EXCLUDED from this test's fixture set. Folding
        it back in here would reintroduce, in the test suite, exactly the
        bootstrap deadlock the correction removed from the criteria.

        NAMED MUTATION (mandatory): a lookup that yields an EMPTY collection
        on error rather than raising/returning an unavailability signal is
        the exact fail-open shape all four cited precedents (KI-CG-034,
        KI-CG-012, KI-CG-018, the AC-store validator bare-directory no-op)
        actually shipped. The injection BITES HARDER after the correction,
        not less: an empty result is now the COMPLETING empty-history path,
        so an unavailable source laundered into an empty collection is no
        longer merely a false all-clear -- it is a genuine exit 0. Under
        that injection every file compares against nothing on BOTH of the
        two unavailable fixtures below, the run states zero files compared,
        and the commit completes; this descriptor must go RED, and it must
        fail BY THE COMMIT OUTCOME (not merely by missing text), then
        return to green on revert. Operationalized here as: neither
        unresolvable scenario may exit 0 (clean).

        ADDITIONAL CHECK THE CORRECTED DESCRIPTOR REQUIRES: the mutation is
        only genuinely load-bearing if it is caught HERE, on the unavailable
        fixtures, rather than by accidentally breaking the legitimate empty
        case -- so whoever executes this injection (python-coder /
        pr-reviewer; test-writer does not itself run mutation testing
        against production code) must ALSO confirm that
        test_ge_127b_1_i_a_history_holding_no_covered_file_completes_and_is_named_apart_from_both_refusals
        stays GREEN under the same injection. If that test goes red too, the
        injection broke the wrong thing and the mutation has not actually
        verified this descriptor's load-bearing-ness.

        RED TODAY: check_file_size.py's `count_lines()` already does a
        fail-open shape (a bare `except (OSError, UnicodeDecodeError):
        return 0`) for the CURRENT staged content it reads, but the
        previous-length lookup itself is not yet fail-open -- it raises
        PreviousLengthSourceError. Today this test is RED for a different
        reason: the unreachable fixture crashes uncaught (no try/except
        around get_staged_files()) instead of reporting exit 2.
        """
        # (a) unreachable: a working copy that is not a git repository.
        unreachable_root = self.root / "unreachable"
        _make_unreachable_source_root(unreachable_root)
        result_a = _run_check(unreachable_root)

        # (b) uninterpretable: HEAD blob not valid UTF-8.
        uninterpretable_root = self.root / "uninterpretable"
        _make_uninterpretable_source_root(uninterpretable_root)
        result_b = _run_check(uninterpretable_root)

        for label, result in (("unreachable", result_a), ("uninterpretable", result_b)):
            self.assertNotEqual(
                _CLEAN_EXIT,
                result.returncode,
                msg=(
                    f"Scenario {label!r} must NOT exit 0 (which would look like a "
                    "clean run that compared everything and found no growth). "
                    f"stdout={result.stdout!r} stderr={result.stderr!r}"
                ),
            )
            self.assertEqual(
                _INDETERMINATE_EXIT,
                result.returncode,
                msg=(
                    f"Scenario {label!r} must exit with the INDETERMINATE code (2), "
                    f"not merely 'not 0'. stdout={result.stdout!r} stderr={result.stderr!r}"
                ),
            )


# ---------------------------------------------------------------------------
# 6. Compared count moves by variation, never against a hard-coded literal
# ---------------------------------------------------------------------------


class TestComparedCountMovesWithNumberOfCoveredFilesStaged(SourceFixtureTestCase):
    def test_ge_127b_1_i_the_stated_compared_count_moves_with_the_number_of_covered_files_staged(self):
        # covers: GE-127b-1-i
        # angle: real_artifact
        """ASSERT BY VARIATION, NEVER AGAINST A LITERAL. Run the gate twice
        over repositories with a differing number of covered files that
        have predecessors, and require the stated compared-count read from
        the gate's own output to move with it (1, then 2).

        RED TODAY: no compared-count is ever stated in the output, so no
        match is found in either run.
        """
        # Run 1: one covered file with a predecessor.
        run1_root = self.root / "run1"
        run1_root.mkdir()
        _init_repo(run1_root)
        (run1_root / "a.py").write_text(_content(20), encoding="utf-8")
        _commit_all(run1_root, "one covered file with a predecessor")
        (run1_root / "a.py").write_text(_content(21), encoding="utf-8")
        _stage_all(run1_root)
        result1 = _run_check(run1_root)
        count1 = _extract_compared_count(result1.stdout + result1.stderr)

        # Run 2: two covered files with predecessors.
        run2_root = self.root / "run2"
        run2_root.mkdir()
        _init_repo(run2_root)
        (run2_root / "a.py").write_text(_content(20), encoding="utf-8")
        (run2_root / "b.py").write_text(_content(20), encoding="utf-8")
        _commit_all(run2_root, "two covered files with predecessors")
        (run2_root / "a.py").write_text(_content(21), encoding="utf-8")
        (run2_root / "b.py").write_text(_content(21), encoding="utf-8")
        _stage_all(run2_root)
        result2 = _run_check(run2_root)
        count2 = _extract_compared_count(result2.stdout + result2.stderr)

        self.assertIsNotNone(count1, msg=f"Run 1 must state a compared count. Got: {result1.stdout!r}")
        self.assertIsNotNone(count2, msg=f"Run 2 must state a compared count. Got: {result2.stdout!r}")
        self.assertEqual(1, count1, msg=f"Run 1 staged 1 file with a predecessor, got count={count1!r}")
        self.assertEqual(2, count2, msg=f"Run 2 staged 2 files with predecessors, got count={count2!r}")


# ---------------------------------------------------------------------------
# 7. A clean run's positive count is what makes it clean
# ---------------------------------------------------------------------------


class TestCleanRunStatesPositiveComparedCount(SourceFixtureTestCase):
    def test_ge_127b_1_i_a_clean_run_states_a_positive_compared_count_and_that_is_what_makes_it_clean(self):
        # covers: GE-127b-1-i
        # angle: criterion
        """Over a run in which at least one staged covered file has a
        predecessor and none has grown, the stated compared-count read from
        the gate's own output must be greater than zero -- it is that
        POSITIVE number, not the absence of findings, that establishes the
        run as clean.

        RED TODAY: no compared-count is ever stated in the output.
        """
        _init_repo(self.root)
        stable = self.root / "stable.py"
        stable.write_text(_content(20, tag="a"), encoding="utf-8")
        _commit_all(self.root, "establish a covered file")

        # Same length, different content -- a pure edit, no growth.
        stable.write_text(_content(20, tag="b"), encoding="utf-8")
        _stage_all(self.root)

        result = _run_check(self.root)

        self.assertEqual(
            _CLEAN_EXIT,
            result.returncode,
            msg=f"A run with no growth must be clean. stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        combined = result.stdout + result.stderr
        count = _extract_compared_count(combined)
        self.assertIsNotNone(count, msg=f"Expected a stated compared count. Got: {combined!r}")
        self.assertGreater(
            count,
            0,
            msg=f"The compared count must be positive (not merely absent-of-findings). Got: {count!r}",
        )


# ---------------------------------------------------------------------------
# 8. Reachability -- count and INDETERMINATE reach the registered hook output
# ---------------------------------------------------------------------------


class TestCountAndIndeterminateReachRegisteredHookOutput(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_ge_127b_1_i_the_count_and_the_indeterminate_verdict_reach_the_registered_hook_output(self):
        # covers: GE-127b-1-i
        # angle: reachability
        """PRODUCTION ENTRY POINT. Run the gate through the registered hook
        path (run_hook.py) and assert the compared-count appears on a
        determinate run and the INDETERMINATE verdict with its named reason
        appears on an unresolvable one -- with the exit status being the
        real commit outcome in both cases.

        The unresolvable fixture here is a working copy that is not a git
        repository at all -- NOT an unborn HEAD, which per the 2026-09-01
        correction is the empty-history completing case and must exit 0,
        not 2 (see the anti-deadlock descriptor above).

        RED TODAY: neither output exists yet in either scenario.
        """
        # Determinate run: one covered file with a predecessor, no growth.
        determinate_root = self.root / "determinate"
        determinate_root.mkdir()
        _init_repo(determinate_root)
        stable = determinate_root / "stable.py"
        stable.write_text(_content(20, tag="a"), encoding="utf-8")
        _commit_all(determinate_root, "establish a covered file")
        stable.write_text(_content(20, tag="b"), encoding="utf-8")
        _stage_all(determinate_root)
        determinate_result = _run_check_via_hook(determinate_root)

        self.assertEqual(_CLEAN_EXIT, determinate_result.returncode)
        combined_determinate = determinate_result.stdout + determinate_result.stderr
        count = _extract_compared_count(combined_determinate)
        self.assertIsNotNone(count, msg=f"Expected a stated compared count. Got: {combined_determinate!r}")
        self.assertGreater(count, 0)

        # Unresolvable run: a working copy that is not a git repository at
        # all. NOT an unborn HEAD -- that is the empty-history completing
        # case per the 2026-09-01 correction and must exit 0.
        unresolvable_root = self.root / "unresolvable"
        _make_unreachable_source_root(unresolvable_root)
        unresolvable_result = _run_check_via_hook(unresolvable_root)

        self.assertEqual(_INDETERMINATE_EXIT, unresolvable_result.returncode)
        combined_unresolvable = unresolvable_result.stdout + unresolvable_result.stderr
        reason = _extract_indeterminate_reason(combined_unresolvable)
        self.assertIsNotNone(reason, msg=f"Expected an INDETERMINATE reason. Got: {combined_unresolvable!r}")


# ---------------------------------------------------------------------------
# 9. Deployed -- fails closed in the deployed, cold-process copy
# ---------------------------------------------------------------------------


class TestDeployedCopyFailsClosedWhenSourceUnavailable(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.target = Path(self._tmp.name)

    def test_ge_127b_1_i_the_deployed_copy_fails_closed_when_the_previous_length_source_is_unavailable(self):
        # covers: GE-127b-1-i
        # angle: deployed
        """After build.py, the DEPLOYED copy and every module it imports
        must load and run in a cold process. With the previous-length
        source made genuinely unavailable, it must emit the INDETERMINATE
        verdict with its named reason and exit non-zero; over a real,
        populated, non-growing run it must state a compared count greater
        than zero and exit zero. Source-tree greenness cannot substitute:
        the hook runs from the deployed layout.

        The unavailable fixture here is the deployed target directory
        BEFORE it is ever made a git repository at all -- NOT an unborn
        HEAD (a `git init`-ed repo with no commit), which per the
        2026-09-01 correction is the empty-history completing case and
        must exit 0, not 2.

        RED TODAY: no such verdict exists in the source tree, so it cannot
        exist in the deployed copy either.
        """
        build_result = subprocess.run(
            [_PYTHON, str(_BUILD_PY), "--target-dir", str(self.target)],
            capture_output=True,
            text=True,
            timeout=_BUILD_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            0,
            build_result.returncode,
            msg=f"build.py itself failed: stdout={build_result.stdout} stderr={build_result.stderr}",
        )

        deployed_check = self.target / "scripts" / "commit_guardian" / "check_file_size.py"
        self.assertTrue(deployed_check.exists(), msg=f"{deployed_check} was not deployed by build.py.")

        # Unresolvable: the deployed target is NOT (yet) a git repository at
        # all -- a genuinely broken environment. Deliberately no
        # `_init_repo()` call here.
        (self.target / "fresh.py").write_text(_content(10), encoding="utf-8")

        unresolvable_result = subprocess.run(
            [_PYTHON, str(deployed_check)],
            cwd=str(self.target),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
        self.assertNotIn("ModuleNotFoundError", unresolvable_result.stderr)
        self.assertEqual(
            _INDETERMINATE_EXIT,
            unresolvable_result.returncode,
            msg=(
                "Deployed copy with an unresolvable HEAD must exit INDETERMINATE "
                f"(2). stdout={unresolvable_result.stdout!r} stderr={unresolvable_result.stderr!r}"
            ),
        )
        combined = unresolvable_result.stdout + unresolvable_result.stderr
        reason = _extract_indeterminate_reason(combined)
        self.assertIsNotNone(reason, msg=f"Expected an INDETERMINATE reason. Got: {combined!r}")

        # Now make the target a real git repository, establish a populated,
        # non-growing HEAD, and verify the positive path.
        _init_repo(self.target)
        _commit_all(self.target, "establish HEAD with the new covered file")
        stable = self.target / "fresh.py"
        stable.write_text(_content(10, tag="b"), encoding="utf-8")
        _stage_all(self.target)

        clean_result = subprocess.run(
            [_PYTHON, str(deployed_check)],
            cwd=str(self.target),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            _CLEAN_EXIT,
            clean_result.returncode,
            msg=(
                "Deployed copy over a real, populated, non-growing run must exit "
                f"clean (0). stdout={clean_result.stdout!r} stderr={clean_result.stderr!r}"
            ),
        )
        clean_combined = clean_result.stdout + clean_result.stderr
        count = _extract_compared_count(clean_combined)
        self.assertIsNotNone(count, msg=f"Expected a stated compared count. Got: {clean_combined!r}")
        self.assertGreater(count, 0)


if __name__ == "__main__":
    unittest.main()
