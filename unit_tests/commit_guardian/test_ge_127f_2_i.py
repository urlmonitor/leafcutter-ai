"""
MODULE: unit_tests/commit_guardian/test_ge_127f_2_i.py
COVERS: GE-127f-2-i -- "A run that cannot establish what a change added says
    which situation it is in and refuses, rather than recording the change
    as having added nothing"

GOAL: RED test-first stubs for the fail-closed floor under
    ``AddedLineCountUnavailableError`` (shipped, deliberately UNCAUGHT, in
    ticket 07 / GE-127f-2). This ticket owns catching it at both call sites
    (``_classify_file``, ``_print_grown_file``) and printing the pinned
    ``INDETERMINATE: reason=<text>`` line, exit 2, reusing BP-1600a-2-ii's
    verdict vocabulary per architect-review's ruling -- see the ticket's own
    2026-09-29 architect-review comment.

THE EAGER-PRE-RESOLUTION PROBLEM, AND WHY EVERY DISPOSABLE-COPY FIXTURE
    BELOW CORRUPTS *ON THE CALL*, NOT BEFORE THE RUN STARTS. Empirically
    verified at authoring time (see this file's sign-off comment for the
    transcripts): ``main()`` calls ``resolve_previous_lengths()`` for EVERY
    covered staged file BEFORE classification even begins, using the exact
    same ``get_previous_content`` / ``read_current_content`` reads that
    ``resolve_added_measured_lines`` performs again later. Corrupting a
    file's HEAD blob (or its current working-tree bytes) BEFORE running the
    gate at all is deterministically caught by THAT earlier, already-shipped
    GE-127b-1-i / GE-127a-1-i floor first -- proven by direct experiment,
    producing "INDETERMINATE: reason=the previous length for ... could not
    be read: ..." (GE-127b-1-i's own wording), never this ticket's
    "the measured lines added to ... could not be established: ..." wording
    -- so it never reaches this ticket's own catch sites at all. Every
    fixture below therefore uses a disposable, git-repo-local copy of the
    gate (never templates/scripts/commit_guardian/ itself) whose OWN
    ``resolve_added_measured_lines`` name is reassigned, via
    ``_ge_127e_3_fixture``'s established ``_insert_before_main_guard`` idiom,
    to a wrapper that performs the REAL git/filesystem corruption AT CALL
    TIME -- strictly after the earlier, unrelated ``resolve_previous_lengths``
    call has already succeeded against the healthy blob -- and then
    DELEGATES to the real, unmodified ``resolve_added_measured_lines`` saved
    under a different name. This is not a monkeypatch of behaviour: the
    delegate is the genuine function, and the failure it raises is a genuine
    git/UnicodeDecodeError produced by genuinely broken on-disk state: the
    wrapper only decides WHEN the sabotage lands, never WHAT the real code
    concludes from it.

DECISION HISTORY
- 2026-09-29 [GE-127f-2-i/test-writer]: Initial authoring. See sign-off
    comment for the empirical transcripts proving both corruption timings
    reach this ticket's own two raise sites (lines ~900-904, ~908-914 of
    _file_size_ratchet.py) with distinct, contrasting reason text, and that
    an up-front (before-run) corruption instead reaches GE-127b-1-i's
    unrelated, already-shipped floor.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127a_1_ordinary_commit_fixture as fx1  # noqa: E402
import _ge_127f_2_fixture as fx  # noqa: E402
from _ge_127e_3_fixture import _insert_before_main_guard  # noqa: E402

_BASELINE = fx.BASELINE_LENGTH
_PERMITTED = fx.PERMITTED_LENGTH
_PYTHON = fx._PYTHON
_INDETERMINATE_EXIT = 2
_INDETERMINATE_RE = re.compile(r"INDETERMINATE:\s*reason=(.+)", re.IGNORECASE)

# Corrupt the previous (HEAD) blob for real, strictly AFTER delegating would
# otherwise succeed -- see module docstring's EAGER-PRE-RESOLUTION note.
_UNREACHABLE_INJECTION = r'''
_REAL_RESOLVE_ADDED_MEASURED_LINES = resolve_added_measured_lines


def resolve_added_measured_lines(filepath, parent_revisions=None):  # noqa: F811
    sha = subprocess.run(
        ["git", "rev-parse", f"HEAD:{filepath}"], capture_output=True, text=True, check=True
    ).stdout.strip()
    obj = Path(".git") / "objects" / sha[:2] / sha[2:]
    data = obj.read_bytes()
    obj.chmod(0o644)
    obj.write_bytes(data[: len(data) // 2])
    return _REAL_RESOLVE_ADDED_MEASURED_LINES(filepath, parent_revisions)
'''

# Corrupt the CURRENT working-tree bytes for real, after count_lines() (this
# same file's own earlier read, inside _classify_file) already succeeded.
_UNINTERPRETABLE_INJECTION = r'''
_REAL_RESOLVE_ADDED_MEASURED_LINES = resolve_added_measured_lines


def resolve_added_measured_lines(filepath, parent_revisions=None):  # noqa: F811
    Path(filepath).write_bytes(b"\xff\xfe\x00\x01not valid utf-8\n")
    return _REAL_RESOLVE_ADDED_MEASURED_LINES(filepath, parent_revisions)
'''

# THE BA'S INJECTION, CARRIED VERBATIM (test 4): "on any failure to
# establish the lines a change put into a file, fall back to an added-line
# count of zero and carry on." Combined with each corruption above so the
# resulting failure is genuinely raised by the real function, then swallowed.
_FALLBACK_ZERO_UNREACHABLE_INJECTION = r'''
from _file_size_ratchet import AddedLineCountUnavailableError
_REAL_RESOLVE_ADDED_MEASURED_LINES = resolve_added_measured_lines


def resolve_added_measured_lines(filepath, parent_revisions=None):  # noqa: F811
    sha = subprocess.run(
        ["git", "rev-parse", f"HEAD:{filepath}"], capture_output=True, text=True, check=True
    ).stdout.strip()
    obj = Path(".git") / "objects" / sha[:2] / sha[2:]
    data = obj.read_bytes()
    obj.chmod(0o644)
    obj.write_bytes(data[: len(data) // 2])
    try:
        return _REAL_RESOLVE_ADDED_MEASURED_LINES(filepath, parent_revisions)
    except AddedLineCountUnavailableError:
        return 0
'''

_FALLBACK_ZERO_UNINTERPRETABLE_INJECTION = r'''
from _file_size_ratchet import AddedLineCountUnavailableError
_REAL_RESOLVE_ADDED_MEASURED_LINES = resolve_added_measured_lines


def resolve_added_measured_lines(filepath, parent_revisions=None):  # noqa: F811
    Path(filepath).write_bytes(b"\xff\xfe\x00\x01not valid utf-8\n")
    try:
        return _REAL_RESOLVE_ADDED_MEASURED_LINES(filepath, parent_revisions)
    except AddedLineCountUnavailableError:
        return 0
'''

# The SAME catch-and-degrade policy, with NO corruption at all -- proves the
# injection is INERT whenever the account is genuinely available.
_FALLBACK_ZERO_PASSTHROUGH_INJECTION = r'''
from _file_size_ratchet import AddedLineCountUnavailableError
_REAL_RESOLVE_ADDED_MEASURED_LINES = resolve_added_measured_lines


def resolve_added_measured_lines(filepath, parent_revisions=None):  # noqa: F811
    try:
        return _REAL_RESOLVE_ADDED_MEASURED_LINES(filepath, parent_revisions)
    except AddedLineCountUnavailableError:
        return 0
'''


def _extract_indeterminate_reason(output: str) -> str | None:
    match = _INDETERMINATE_RE.search(output)
    return match.group(1).strip() if match else None


def _fresh_dir(testcase: unittest.TestCase) -> Path:
    tmp = tempfile.TemporaryDirectory()
    testcase.addCleanup(tmp.cleanup)
    return Path(tmp.name)


def _fresh_repo(testcase: unittest.TestCase) -> Path:
    root = _fresh_dir(testcase)
    fx.init_repo(root)
    return root


def _build_injected_disposable(root: Path, injection: str) -> None:
    """A disposable, git-repo-local copy of the gate with *injection*
    inserted before its main guard -- never templates/scripts/commit_guardian/
    itself. Reuses the already-verified PRODUCTION_MODULES copy list."""
    fx1.copy_production_modules(root)
    fx1.write_config_json(root, _PERMITTED)
    _insert_before_main_guard(root / "scripts" / "commit_guardian", injection)
    fx.init_repo(root)


def _stage_five_for_five_replacement(root: Path) -> None:
    baseline = fx.function_lines(_BASELINE, tag="v")
    fx.establish_baseline(root, baseline)
    changed = fx.replace_leading_lines(baseline, 5, "w")
    (root / "big.py").write_text(changed, encoding="utf-8")
    fx.stage_all(root)


def _run_unreachable_arm(testcase: unittest.TestCase) -> subprocess.CompletedProcess:
    root = _fresh_dir(testcase)
    _build_injected_disposable(root, _UNREACHABLE_INJECTION)
    _stage_five_for_five_replacement(root)
    return fx.run_check_in_disposable(root)


def _run_uninterpretable_arm(testcase: unittest.TestCase) -> subprocess.CompletedProcess:
    root = _fresh_dir(testcase)
    _build_injected_disposable(root, _UNINTERPRETABLE_INJECTION)
    _stage_five_for_five_replacement(root)
    return fx.run_check_in_disposable(root)


def _run_genuine_zero_arm(testcase: unittest.TestCase) -> subprocess.CompletedProcess:
    """The REAL, unmutated source tree -- a delete-only edit needs no
    corruption at all, so it is run against templates/ directly."""
    root = _fresh_repo(testcase)
    baseline = fx.function_lines(_BASELINE, tag="v")
    fx.establish_baseline(root, baseline)
    final = fx.drop_trailing_lines(baseline, 12)
    (root / "big.py").write_text(final, encoding="utf-8")
    fx.stage_all(root)
    return fx.run_check(root)


def _run_genuine_delete_arm(testcase: unittest.TestCase) -> subprocess.CompletedProcess:
    """A literal staged DELETION of an already-oversized covered file --
    MECHANISM (1) of AC-7's exit-0 guarantee, distinct from
    ``_run_genuine_zero_arm``'s MECHANISM (2) (a shrinking edit that leaves
    the file on disk throughout). The REAL, unmutated source tree -- a
    deletion needs no corruption to reach this record's subject, since it is
    not one of this ticket's two refusing situations."""
    root = _fresh_repo(testcase)
    baseline = fx.function_lines(_BASELINE, tag="v")
    target = fx.establish_baseline(root, baseline)
    target.unlink()
    fx.stage_all(root)
    return fx.run_check(root)


def _run_via_hook_in_disposable(root: Path) -> subprocess.CompletedProcess:
    script_dir = root / "scripts" / "commit_guardian"
    return subprocess.run(
        [_PYTHON, str(script_dir / "run_hook.py"), str(script_dir / "check_file_size.py")],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=fx._SUBPROCESS_TIMEOUT_SECONDS,
    )


class TestUnreachableAccountRefusesAndNamesThatSituation(unittest.TestCase):
    def test_ge_127f_2_i_an_unreachable_account_of_the_change_refuses_and_names_that_situation(self):
        # covers: GE-127f-2-i
        # angle: criterion
        """A 5-for-5 replacement of an already-oversized covered file, with
        its HEAD blob genuinely made unreadable (a truncated loose object,
        corrupted strictly after resolve_previous_lengths() already
        succeeded -- see module docstring). The commit must not complete
        (exit 2) and must name the account of the change as unreachable.

        RED TODAY: AddedLineCountUnavailableError is deliberately UNCAUGHT
        (ticket 07's own scope), so this crashes with a traceback and exits
        1, printing no "INDETERMINATE" line at all.
        """
        result = _run_unreachable_arm(self)

        self.assertEqual(
            _INDETERMINATE_EXIT,
            result.returncode,
            msg=(
                "An unreachable account of the change must refuse (exit 2), "
                f"not crash or silently pass. stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        reason = _extract_indeterminate_reason(combined)
        self.assertIsNotNone(reason, msg=f"Expected an INDETERMINATE reason. Got: {combined!r}")
        self.assertRegex(
            reason,
            r"(?i)unreachable",
            msg=f"The reason must name the account as UNREACHABLE. Got: {reason!r}",
        )


class TestUninterpretableAccountNamedApartFromUnreachable(unittest.TestCase):
    def test_ge_127f_2_i_an_uninterpretable_account_refuses_and_is_named_apart_from_the_unreachable_one(self):
        # covers: GE-127f-2-i
        # angle: criterion
        """The account is reached (HEAD blob reads fine) but the CURRENT
        content cannot be interpreted (non-UTF-8 bytes, written for real
        after count_lines() already read the original valid bytes). Must
        refuse (exit 2) and its reason text must differ from the unreachable
        arm's, asserted BY CONTRAST -- never against a hard-coded literal.

        RED TODAY: same underlying reason as the sibling test -- the
        exception is uncaught, so no reason text exists to contrast at all.
        """
        result_unreachable = _run_unreachable_arm(self)
        result_uninterpretable = _run_uninterpretable_arm(self)

        for label, result in (("unreachable", result_unreachable), ("uninterpretable", result_uninterpretable)):
            self.assertEqual(
                _INDETERMINATE_EXIT,
                result.returncode,
                msg=f"{label} arm must refuse (exit 2). stdout={result.stdout!r} stderr={result.stderr!r}",
            )

        reason_unreachable = _extract_indeterminate_reason(result_unreachable.stdout + result_unreachable.stderr)
        reason_uninterpretable = _extract_indeterminate_reason(
            result_uninterpretable.stdout + result_uninterpretable.stderr
        )
        self.assertIsNotNone(reason_unreachable, msg="Expected the unreachable arm to state a reason.")
        self.assertIsNotNone(reason_uninterpretable, msg="Expected the uninterpretable arm to state a reason.")
        self.assertNotEqual(
            reason_unreachable,
            reason_uninterpretable,
            msg=(
                "The two refusing situations must be named with DIFFERENT text. "
                f"Got: {reason_unreachable!r} vs {reason_uninterpretable!r}"
            ),
        )


class TestGenuineZeroCommitsAndIsNamedApartFromBoth(unittest.TestCase):
    def test_ge_127f_2_i_a_change_that_genuinely_added_nothing_commits_and_is_named_apart_from_both(self):
        # covers: GE-127f-2-i
        # angle: boundary
        """THE LOAD-BEARING PERMISSIVE ARM. A change that genuinely removes
        measured lines and adds none, to an already-oversized file, must
        still commit (exit 0) -- refusing it to be safe breaks GE-127f-2's
        own free arm. Its output must never carry either refusing reason,
        asserted by contrast against both real refusal runs, not a literal.

        RED TODAY only for the fixture-sanity half (the two refusing arms do
        not yet state any reason to contrast against); the exit-0 half
        already holds today and must never regress.
        """
        zero_result = _run_genuine_zero_arm(self)
        unreachable_result = _run_unreachable_arm(self)
        uninterpretable_result = _run_uninterpretable_arm(self)

        self.assertEqual(
            0,
            zero_result.returncode,
            msg=(
                "A change that genuinely added nothing must commit cleanly. "
                f"stdout={zero_result.stdout!r} stderr={zero_result.stderr!r}"
            ),
        )
        zero_combined = zero_result.stdout + zero_result.stderr
        self.assertNotIn("INDETERMINATE", zero_combined, msg="The genuine-zero arm must never borrow INDETERMINATE.")

        reason_unreachable = _extract_indeterminate_reason(unreachable_result.stdout + unreachable_result.stderr)
        reason_uninterpretable = _extract_indeterminate_reason(
            uninterpretable_result.stdout + uninterpretable_result.stderr
        )
        self.assertIsNotNone(reason_unreachable, msg="Fixture sanity: the unreachable arm must state a reason.")
        self.assertIsNotNone(
            reason_uninterpretable, msg="Fixture sanity: the uninterpretable arm must state a reason."
        )
        self.assertNotIn(reason_unreachable, zero_combined)
        self.assertNotIn(reason_uninterpretable, zero_combined)

    def test_ge_127f_2_i_a_change_that_deletes_the_file_entirely_commits_and_is_named_apart_from_both(self):
        # covers: GE-127f-2-i
        # angle: discrimination
        """MECHANISM (1) OF AC-7's EXIT-0 GUARANTEE, DISTINCT FROM THE SHRINK
        ARM ABOVE (mechanism 2, ``count_added_measured_lines`` returning 0
        while the file stays on disk). This arm exercises the SEPARATE
        ``Path(filepath).exists()`` early-return in
        ``resolve_added_measured_lines``, added in ticket 07 after a literal
        staged deletion once crashed the whole gate uncaught. pr-reviewer's
        2026-09-30 blocker: no test here ever staged a real ``unlink()``
        deletion, so a future narrowing of that early-return would silently
        reintroduce the crash with nothing going red.

        GREEN TODAY -- no live defect (pr-reviewer independently reproduced
        this arm passing). Closes a regression window; not a red stub.
        """
        delete_result = _run_genuine_delete_arm(self)
        unreachable_result = _run_unreachable_arm(self)
        uninterpretable_result = _run_uninterpretable_arm(self)

        self.assertEqual(
            0,
            delete_result.returncode,
            msg=(
                "A staged deletion of an already-oversized covered file must "
                f"commit cleanly. stdout={delete_result.stdout!r} stderr={delete_result.stderr!r}"
            ),
        )
        delete_combined = delete_result.stdout + delete_result.stderr
        self.assertNotIn(
            "INDETERMINATE", delete_combined, msg="A staged deletion must never borrow the INDETERMINATE token."
        )

        reason_unreachable = _extract_indeterminate_reason(unreachable_result.stdout + unreachable_result.stderr)
        reason_uninterpretable = _extract_indeterminate_reason(
            uninterpretable_result.stdout + uninterpretable_result.stderr
        )
        self.assertIsNotNone(reason_unreachable, msg="Fixture sanity: the unreachable arm must state a reason.")
        self.assertIsNotNone(
            reason_uninterpretable, msg="Fixture sanity: the uninterpretable arm must state a reason."
        )
        self.assertNotIn(reason_unreachable, delete_combined)
        self.assertNotIn(reason_uninterpretable, delete_combined)


class TestFallbackToZeroInjectionRedsBothRefusalsLeavesZeroGreen(unittest.TestCase):
    def test_ge_127f_2_i_the_fall_back_to_zero_injection_reds_both_refusals_and_leaves_the_genuine_zero_arm_green(
        self,
    ):
        # covers: GE-127f-2-i
        # angle: failure
        """THE MUTATION PROOF, ONE EXPERIMENT, ONE RECORDED RESULT. The BA's
        injection -- "on any failure to establish the lines a change put
        into a file, fall back to an added-line count of zero and carry on"
        -- is applied (as a catch-and-degrade wrapper around the real
        function) to THREE disposable copies: the two genuinely-corrupted
        fixtures above, and a plain passthrough copy for the genuine-zero
        fixture and for one of GE-127f-2's own healthy refusal arms.

        REQUIRED OBSERVATIONS: both corrupted arms silently COMPLETE (exit
        0) under the injection -- the wrong outcome, since a real account
        failure must refuse -- while the genuine-zero arm and GE-127f-2's
        own healthy 5-for-5 replacement (no corruption at all -- the account
        genuinely IS available here) are UNAFFECTED, i.e. read identically
        to the real, unmutated gate (zero commits clean; the healthy
        replacement is still refused). A run that reds every arm, including
        the unaffected ones, is a failure of this descriptor, not a
        stronger result -- it would mean the fixtures were never
        independent.

        This experiment is self-contained and correctly reads the same
        before and after python-coder's own fix lands, exactly like
        test_ge_127f_2_seam_and_mutation.py's own mutation proof: it proves
        the injected POLICY is wrong on its own terms, never that the real,
        unmutated gate currently behaves one way or another.
        """
        unreachable_root = _fresh_dir(self)
        _build_injected_disposable(unreachable_root, _FALLBACK_ZERO_UNREACHABLE_INJECTION)
        _stage_five_for_five_replacement(unreachable_root)
        unreachable_result = fx.run_check_in_disposable(unreachable_root)

        uninterpretable_root = _fresh_dir(self)
        _build_injected_disposable(uninterpretable_root, _FALLBACK_ZERO_UNINTERPRETABLE_INJECTION)
        _stage_five_for_five_replacement(uninterpretable_root)
        uninterpretable_result = fx.run_check_in_disposable(uninterpretable_root)

        zero_root = _fresh_dir(self)
        _build_injected_disposable(zero_root, _FALLBACK_ZERO_PASSTHROUGH_INJECTION)
        baseline = fx.function_lines(_BASELINE, tag="v")
        fx.establish_baseline(zero_root, baseline)
        (zero_root / "big.py").write_text(fx.drop_trailing_lines(baseline, 12), encoding="utf-8")
        fx.stage_all(zero_root)
        zero_result = fx.run_check_in_disposable(zero_root)

        healthy_root = _fresh_dir(self)
        _build_injected_disposable(healthy_root, _FALLBACK_ZERO_PASSTHROUGH_INJECTION)
        _stage_five_for_five_replacement(healthy_root)
        healthy_result = fx.run_check_in_disposable(healthy_root)

        observations = {
            "unreachable": unreachable_result.returncode,
            "uninterpretable": uninterpretable_result.returncode,
            "genuine_zero": zero_result.returncode,
            "healthy_replacement_unaffected": healthy_result.returncode,
        }

        self.assertEqual(
            0,
            observations["unreachable"],
            msg=(
                "WRONGLY PERMITTED under the fall-back-to-zero injection -- proof "
                f"the injection is broken, not that permitting is correct. Observations: {observations}"
            ),
        )
        self.assertEqual(
            0,
            observations["uninterpretable"],
            msg=f"WRONGLY PERMITTED under the injection, same reason. Observations: {observations}",
        )
        self.assertNotIn(
            "INDETERMINATE",
            unreachable_result.stdout + unreachable_result.stderr,
            msg="The injection must silently complete, printing no INDETERMINATE line at all.",
        )
        self.assertNotIn(
            "INDETERMINATE",
            uninterpretable_result.stdout + uninterpretable_result.stderr,
            msg="The injection must silently complete, printing no INDETERMINATE line at all.",
        )
        self.assertEqual(
            0,
            observations["genuine_zero"],
            msg=f"MUST STAY GREEN and UNAFFECTED by the injection. Observations: {observations}",
        )
        self.assertNotEqual(
            0,
            observations["healthy_replacement_unaffected"],
            msg=(
                "The injection must be INERT when the account IS genuinely "
                f"available -- GE-127f-2's own healthy refusal must still hold. Observations: {observations}"
            ),
        )
        self.assertFalse(
            all(code != 0 for code in (observations["unreachable"], observations["uninterpretable"])),
            msg=f"Both corrupted arms exiting non-zero would mean the injection had no effect. Observations: {observations}",
        )


class TestBothRefusalsReachRegisteredHookOutput(unittest.TestCase):
    def test_ge_127f_2_i_both_refusals_reach_the_registered_hook_output_with_the_indeterminate_status(self):
        # covers: GE-127f-2-i
        # angle: reachability
        """PRODUCTION ENTRY POINT. Run the unreachable-account fixture
        through the REAL, registered run_hook.py dispatcher (never main()
        called directly) and assert the INDETERMINATE line reaches the
        hook's own output under exit 2, distinguishable from the exit-1
        refusal an ordinary over-limit finding produces via the SAME hook.

        RED TODAY: the exception is uncaught, so run_hook.py's own output
        carries a traceback and exit 1 -- indistinguishable from an ordinary
        finding by exit code alone.
        """
        root = _fresh_dir(self)
        _build_injected_disposable(root, _UNREACHABLE_INJECTION)
        _stage_five_for_five_replacement(root)
        indeterminate_result = _run_via_hook_in_disposable(root)

        finding_root = _fresh_repo(self)
        (finding_root / "brand_new.py").write_text(fx.function_lines(_PERMITTED + 50, tag="z"), encoding="utf-8")
        fx.stage_all(finding_root)
        finding_result = fx.run_check_via_hook(finding_root)

        self.assertEqual(
            _INDETERMINATE_EXIT,
            indeterminate_result.returncode,
            msg=(
                "The hook's own exit status must be INDETERMINATE (2) for an "
                f"unreachable account. stdout={indeterminate_result.stdout!r} stderr={indeterminate_result.stderr!r}"
            ),
        )
        reason = _extract_indeterminate_reason(indeterminate_result.stdout + indeterminate_result.stderr)
        self.assertIsNotNone(reason, msg="Expected the hook's own output to carry an INDETERMINATE reason.")

        self.assertEqual(
            1,
            finding_result.returncode,
            msg=(
                "An ordinary over-limit finding must reach the hook as exit 1, "
                f"distinguishable from exit 2. stdout={finding_result.stdout!r} stderr={finding_result.stderr!r}"
            ),
        )
        self.assertNotEqual(indeterminate_result.returncode, finding_result.returncode)


class TestDeployedCopyRefusesAnUnestablishedCountInAColdProcess(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.target = Path(self._tmp.name)

    def test_ge_127f_2_i_the_deployed_copy_refuses_an_unestablished_count_in_a_cold_process(self):
        # covers: GE-127f-2-i
        # angle: deployed
        """After build.py, the DEPLOYED copy and every module it imports
        load and run in a cold process. The genuine-zero arm is checked
        FIRST, against the deployed copy UNMODIFIED; the unreachable-account
        injection is then applied in place to that SAME deployed copy
        (never a second build) and the second arm is checked against it.

        RED TODAY: no INDETERMINATE verdict exists in the source tree, so
        it cannot exist in the deployed copy either -- the unreachable arm
        crashes uncaught.
        """
        build_result = subprocess.run(
            [_PYTHON, str(fx._BUILD_PY), "--target-dir", str(self.target)],
            capture_output=True,
            text=True,
            timeout=fx._BUILD_TIMEOUT_SECONDS,
        )
        self.assertEqual(0, build_result.returncode, msg=f"build.py itself failed: {build_result.stderr}")

        deployed_check = self.target / "scripts" / "commit_guardian" / "check_file_size.py"
        self.assertTrue(deployed_check.exists(), msg=f"{deployed_check} was not deployed by build.py.")

        fx.init_repo(self.target)
        baseline = fx.function_lines(_BASELINE, tag="v")
        fx.establish_baseline(self.target, baseline)

        (self.target / "big.py").write_text(fx.drop_trailing_lines(baseline, 12), encoding="utf-8")
        fx.stage_all(self.target)
        zero_result = subprocess.run(
            [_PYTHON, str(deployed_check)], cwd=str(self.target), capture_output=True, text=True, timeout=30
        )
        self.assertEqual(
            0,
            zero_result.returncode,
            msg=f"Deployed genuine-zero arm must commit cleanly. stdout={zero_result.stdout!r} stderr={zero_result.stderr!r}",
        )

        _insert_before_main_guard(self.target / "scripts" / "commit_guardian", _UNREACHABLE_INJECTION)
        (self.target / "big.py").write_text(fx.replace_leading_lines(baseline, 5, "w"), encoding="utf-8")
        fx.stage_all(self.target)
        unreachable_result = subprocess.run(
            [_PYTHON, str(deployed_check)], cwd=str(self.target), capture_output=True, text=True, timeout=30
        )
        self.assertNotIn("ModuleNotFoundError", unreachable_result.stderr)
        self.assertEqual(
            _INDETERMINATE_EXIT,
            unreachable_result.returncode,
            msg=(
                "Deployed copy with an unreachable account must exit INDETERMINATE "
                f"(2). stdout={unreachable_result.stdout!r} stderr={unreachable_result.stderr!r}"
            ),
        )
        reason = _extract_indeterminate_reason(unreachable_result.stdout + unreachable_result.stderr)
        self.assertIsNotNone(reason, msg="Expected an INDETERMINATE reason from the deployed copy.")


if __name__ == "__main__":
    unittest.main()
