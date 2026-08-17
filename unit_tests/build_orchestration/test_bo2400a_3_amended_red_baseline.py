"""
MODULE: unit_tests/build_orchestration/test_bo2400a_3_amended_red_baseline.py
GOAL: RED test stubs for the AMENDED verify_red_baseline contract — BO-2400a-3
      and its decomposed children BO-2400a-3-i through BO-2400a-3-viii
      (amended 2026-08-17, see docs/acceptance-criteria/build-orchestration/
      BO-2400-fast-lane-build/BO-2400a-3*.yaml).

BACKGROUND: The pre-amendment `verify_red_baseline` treated every covers-tagged
test as "newly added" and halted the fast-lane loop on the FIRST test that
reported PASSED — even when that test was long pre-existing and green because
an earlier slice of the batch AC had already shipped.  This halted two live
runs (BO-2400g-1, TKT-600a-1) on partially-implemented ACs whose covering
tests were legitimately part-green.  The amendment:

  * derives a newly-added / pre-existing partition from git at test-function
    granularity (BO-2400a-3-ii, -iii) instead of trusting every covers tag,
  * excludes pre-existing tests from the verdict while still reporting them
    (BO-2400a-3-iv),
  * passes the gate when >=1 newly-added covering test is red, rather than
    requiring ALL of them to be red, and reports newly-added greens as
    non-fatal `green_at_baseline` entries (BO-2400a-3-v),
  * classifies FAILED/XFAIL as red, PASSED/XPASS as green, and
    SKIPPED/ERROR/unrecognised as inconclusive (BO-2400a-3-vi),
  * fails closed with a named reason when the git partition cannot be
    resolved (BO-2400a-3-vii),
  * is idempotent over an unchanged worktree (BO-2400a-3-viii),
  * and names exactly one of three halt reasons when no newly-added test is
    red (BO-2400a-3-i).

=== Pinned interface contract under test (NOT yet implemented) ===

Location: scripts/build_orchestration/fast_lane.py

    def verify_red_baseline(
        *, ac_ids: list[str], test_root: Path, base_ref: str | None = None
    ) -> dict

Returns a dict with:
    "gate_passed" (bool)
    "reason" (str | None) -- None when passed, otherwise exactly one of:
        "no_new_covering_tests", "all_new_tests_green_at_baseline",
        "no_red_outcome_among_new_tests", "baseline_partition_unavailable"
    "red", "green_at_baseline", "inconclusive", "preexisting" (list[dict]) --
        each entry: {"nodeid": str, "ac_id": str, "outcome": str}

The key "all_red" from the pre-amendment contract is REMOVED.  Do NOT assert
its presence -- a version-skewed caller reading a missing key as falsy must
fail closed, not silently pass.

The current on-disk `verify_red_baseline` (as of this file's authoring) still
has the PRE-amendment signature `(*, ac_ids, test_root)` and PRE-amendment
return shape `{"all_red", "offender", "offender_ac_id"}`.  Every test below is
therefore expected to be RED against today's implementation: calls that pass
`base_ref` raise TypeError (param does not exist yet); calls that inspect the
pinned keys via `.get(...)` observe `None` and fail their assertions.  See the
`red_baseline` block in this ticket's sign-off comment for the captured
strict-mode run.

NOTE ON XFAIL MASKING: these ACs are `work_status: todo`, so the repository's
`pytest_ac_enforcement` plugin downgrades AssertionError failures on the
OUTER test functions below (tagged `# covers: BO-2400a-3-*`) to XFAIL under a
normal run.  Run with `AC_ENFORCE_STRICT=1` to see the true FAILED status.
This masking does NOT apply to the INNER fixture test files written into the
temporary git repositories below -- those live outside the repo's pytest
rootdir, so pytest never loads `pytest.ini`'s addopts/plugin for them, and
their PASSED/FAILED/etc. outcomes are genuine, unmasked pytest outcomes
consumed as verify_red_baseline's raw input.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from inspect import signature
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Repo path wiring — same pattern as test_bo2400a_fast_lane.py
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MODULE_DIR = _REPO_ROOT / "scripts" / "build_orchestration"
sys.path.insert(0, str(_MODULE_DIR))

# fast_lane.py already exists (pre-amendment verify_red_baseline lives here),
# so this import itself does NOT raise ImportError.  The RED signal for this
# file comes from the pinned base_ref kwarg / gate_passed+reason+red+... keys
# not yet existing on the current implementation.
from fast_lane import verify_red_baseline  # noqa: E402


# ---------------------------------------------------------------------------
# Git fixture helpers — real git repos, real commits, real test files.
# ---------------------------------------------------------------------------


def _run_git(args: list[str], cwd: Path) -> str:
    """Run a git subcommand in *cwd* and return stdout; raise on failure."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed in {cwd} (exit {result.returncode}): "
            f"{result.stderr}"
        )
    return result.stdout


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _run_git(["init", "-b", "main", "-q"], cwd=path)
    _run_git(["config", "user.email", "test-writer@example.com"], cwd=path)
    _run_git(["config", "user.name", "Test Writer"], cwd=path)
    _run_git(["config", "core.autocrlf", "false"], cwd=path)


def _commit_all(path: Path, message: str) -> None:
    _run_git(["add", "-A"], cwd=path)
    _run_git(["commit", "-q", "-m", message], cwd=path)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def _make_worktree(tmp_root: Path, base_files: dict[str, str]) -> Path:
    """Create an origin repo with *base_files* committed, clone it, return the clone.

    The clone ("work" worktree) is git's own real remote-tracking setup: after
    `git clone`, HEAD == origin/main (no divergence).  Any file subsequently
    written into the work worktree and left uncommitted or untracked is, by
    construction, absent from the merge-base version of its content and MUST
    be classified newly-added under BO-2400a-3-ii's git-derived partition.
    This mirrors the real fast-lane worktree, which is always a fresh clone
    off origin/main with the batch's tests written but not yet committed.

    Args:
        tmp_root: Parent directory to create "origin" and "work" subdirs in.
        base_files: Mapping of repo-relative path -> file content (dedented)
            to commit into the origin repo before cloning.  When empty, a
            placeholder README is committed so the initial commit is non-empty.

    Returns:
        Path to the cloned "work" worktree (the repo `verify_red_baseline`
        would be pointed at via `test_root=work_dir / "..."`).
    """
    origin_dir = tmp_root / "origin"
    _init_repo(origin_dir)
    if not base_files:
        _write(origin_dir / "README.md", "placeholder\n")
    else:
        for rel_path, content in base_files.items():
            _write(origin_dir / rel_path, content)
    _commit_all(origin_dir, "base")

    work_dir = tmp_root / "work"
    _run_git(["clone", "-q", str(origin_dir), str(work_dir)], cwd=tmp_root)
    _run_git(["config", "user.email", "test-writer@example.com"], cwd=work_dir)
    _run_git(["config", "user.name", "Test Writer"], cwd=work_dir)
    _run_git(["config", "core.autocrlf", "false"], cwd=work_dir)
    return work_dir


def _find_entry(entries: list[dict] | None, func_name: str) -> dict | None:
    """Find the entry in *entries* whose nodeid ends with '::<func_name>'."""
    for entry in entries or []:
        if str(entry.get("nodeid", "")).endswith(f"::{func_name}"):
            return entry
    return None


def _names(entries: list[dict] | None) -> set[str]:
    """Return the set of trailing '::func_name' suffixes present in *entries*."""
    out: set[str] = set()
    for entry in entries or []:
        nodeid = str(entry.get("nodeid", ""))
        if "::" in nodeid:
            out.add(nodeid.rsplit("::", 1)[-1])
    return out


# ---------------------------------------------------------------------------
# BO-2400a-3-v — one red newly-added test is sufficient; greens are surfaced,
# not fatal; no early return on the first green encountered.
# ---------------------------------------------------------------------------


class TestMixedNewlyAddedVerdict(unittest.TestCase):
    """Tests for the amended pass rule: >=1 red newly-added test passes the gate.

    AC scope: BO-2400a-3-v.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac3v_mixed_red_and_green_newly_added_passes_gate(self) -> None:
        # covers: BO-2400a-3-v
        """This is the live TKT-600a-1 shape: 2 red + 2 green, all newly-added.

        To make this green, verify_red_baseline must:
        - Accept base_ref as an optional kwarg (default: git-derived).
        - Classify all 4 tests newly-added (base repo has none of them).
        - Return gate_passed=True because >=1 newly-added test is red.
        - List both green tests individually in green_at_baseline with their
          nodeid and ac_id -- never collapsed into a count.
        """
        ac_id = "BO-FL-V-001"
        work_dir = _make_worktree(self.tmp_root, {})
        test_root = work_dir / "tests"
        _write(
            test_root / "test_green_a.py",
            f"""\
            def test_green_a():
                # covers: {ac_id}
                assert True
            """,
        )
        _write(
            test_root / "test_green_b.py",
            f"""\
            def test_green_b():
                # covers: {ac_id}
                assert True
            """,
        )
        _write(
            test_root / "test_red_a.py",
            f"""\
            def test_red_a():
                # covers: {ac_id}
                assert False, "not yet implemented"
            """,
        )
        _write(
            test_root / "test_red_b.py",
            f"""\
            def test_red_b():
                # covers: {ac_id}
                assert False, "not yet implemented"
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root)

        self.assertTrue(
            verdict.get("gate_passed") is True,
            "gate_passed must be True when >=1 newly-added covering test is red, "
            f"even with 2 newly-added greens present (BO-2400a-3-v); got {verdict!r}.",
        )
        self.assertIsNone(
            verdict.get("reason"),
            "reason must be None when the gate passes.",
        )
        green_entries = verdict.get("green_at_baseline")
        self.assertEqual(
            _names(green_entries),
            {"test_green_a", "test_green_b"},
            "Both newly-added green tests must be reported individually in "
            f"green_at_baseline (test id + AC id); got {green_entries!r}.",
        )
        for entry in green_entries or []:
            self.assertEqual(entry.get("ac_id"), ac_id)
        red_entries = verdict.get("red")
        self.assertEqual(
            _names(red_entries),
            {"test_red_a", "test_red_b"},
            f"Both newly-added red tests must be reported in red; got {red_entries!r}.",
        )

    def test_ac3v_one_red_among_many_green_is_sufficient(self) -> None:
        # covers: BO-2400a-3-v
        """3 green + 1 red newly-added tests must still pass the gate.

        The verdict must be produced by a fold over the whole newly-added set,
        not a short-circuit on the count of reds -- one is enough.
        """
        ac_id = "BO-FL-V-002"
        work_dir = _make_worktree(self.tmp_root, {})
        test_root = work_dir / "tests"
        for name in ("test_green_1", "test_green_2", "test_green_3"):
            _write(
                test_root / f"{name}.py",
                f"""\
                def {name}():
                    # covers: {ac_id}
                    assert True
                """,
            )
        _write(
            test_root / "test_only_red.py",
            f"""\
            def test_only_red():
                # covers: {ac_id}
                assert False, "not yet implemented"
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root)

        self.assertTrue(
            verdict.get("gate_passed") is True,
            "One red newly-added covering test among 3 greens must be sufficient "
            f"to pass the gate (BO-2400a-3-v); got {verdict!r}.",
        )

    def test_ac3v_no_early_return_on_green_before_red_in_scan_order(self) -> None:
        # covers: BO-2400a-3-v
        """A green test scanned BEFORE a red test must not short-circuit the verdict.

        File names are chosen so the green test sorts alphabetically before the
        red test (covers-tag scanning walks sorted(test_root.rglob("*.py"))).
        The pre-amendment implementation returned all_red=False on the FIRST
        PASSED outcome it encountered while iterating linked tags -- this test
        is specifically designed to fail against that early-return shape even
        though the overall mixed-outcome case (test above) already exercises
        the bug in general.
        """
        ac_id = "BO-FL-V-003"
        work_dir = _make_worktree(self.tmp_root, {})
        test_root = work_dir / "tests"
        _write(
            test_root / "test_a_early_green.py",
            f"""\
            def test_a_early_green():
                # covers: {ac_id}
                assert True
            """,
        )
        _write(
            test_root / "test_z_later_red.py",
            f"""\
            def test_z_later_red():
                # covers: {ac_id}
                assert False, "not yet implemented"
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root)

        self.assertTrue(
            verdict.get("gate_passed") is True,
            "A green test appearing before a red test in scan order must not "
            "halt the gate early (no early-return on first PASSED) -- "
            f"BO-2400a-3-v; got {verdict!r}.",
        )


# ---------------------------------------------------------------------------
# BO-2400a-3-iv — pre-existing covering tests are excluded from the verdict
# but still reported.
# ---------------------------------------------------------------------------


class TestPreexistingExcludedFromVerdict(unittest.TestCase):
    """Tests for pre-existing test exclusion from the verdict.

    AC scope: BO-2400a-3-iv.  This is the live BO-2400g-1 shape: a
    pre-existing green covering test must not block a newly-added red one.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac3iv_preexisting_green_test_does_not_block_red_newly_added(self) -> None:
        # covers: BO-2400a-3-iv
        """A pre-existing green test must appear in `preexisting`, not
        `green_at_baseline`, and must not prevent the gate from passing.
        """
        ac_id = "BO-FL-IV-001"
        base_files = {
            "tests/test_preexisting.py": f"""\
                def test_preexisting_passes():
                    # covers: {ac_id}
                    assert True
                """,
        }
        work_dir = _make_worktree(self.tmp_root, base_files)
        test_root = work_dir / "tests"
        _write(
            test_root / "test_new_red.py",
            f"""\
            def test_new_red():
                # covers: {ac_id}
                assert False, "not yet implemented"
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root)

        self.assertTrue(
            verdict.get("gate_passed") is True,
            "A pre-existing green covering test must not block a newly-added "
            f"red one (BO-2400a-3-iv); got {verdict!r}.",
        )
        self.assertNotIn(
            "test_preexisting_passes",
            _names(verdict.get("green_at_baseline")),
            "A pre-existing test must never appear in green_at_baseline -- it "
            "is excluded from the verdict entirely, not merely non-fatal.",
        )
        preexisting_entry = _find_entry(verdict.get("preexisting"), "test_preexisting_passes")
        self.assertIsNotNone(
            preexisting_entry,
            "The pre-existing covering test must still be reported, under "
            f"`preexisting`; got {verdict.get('preexisting')!r}.",
        )
        if preexisting_entry is not None:
            self.assertEqual(preexisting_entry.get("ac_id"), ac_id)
            self.assertEqual(preexisting_entry.get("outcome"), "PASSED")
        self.assertIn(
            "test_new_red",
            _names(verdict.get("red")),
            "The newly-added red test must be reported under `red`.",
        )

    def test_ac3iv_verdict_unchanged_when_preexisting_outcome_varies(self) -> None:
        # covers: BO-2400a-3-iv
        """Flipping a pre-existing test's outcome (pass -> fail) must not
        change the verdict (gate_passed, reason, red, green_at_baseline) --
        only the pre-existing test's OWN reported outcome may differ.
        """
        ac_id = "BO-FL-IV-002"

        def _build(preexisting_body: str) -> dict:
            tmp_root = self.tmp_root / preexisting_body.__hash__().__str__()
            tmp_root.mkdir(parents=True, exist_ok=True)
            base_files = {
                "tests/test_preexisting.py": f"""\
                    def test_preexisting():
                        # covers: {ac_id}
                        {preexisting_body}
                    """,
            }
            work_dir = _make_worktree(tmp_root, base_files)
            test_root = work_dir / "tests"
            _write(
                test_root / "test_new_red.py",
                f"""\
                def test_new_red():
                    # covers: {ac_id}
                    assert False, "not yet implemented"
                """,
            )
            return verify_red_baseline(ac_ids=[ac_id], test_root=test_root)

        verdict_pass = _build("assert True")
        verdict_fail = _build("assert False")

        self.assertEqual(
            verdict_pass.get("gate_passed"),
            verdict_fail.get("gate_passed"),
            "The verdict's gate_passed must be identical regardless of whether "
            "the pre-existing covering test passes or fails (BO-2400a-3-iv); "
            f"pass-variant={verdict_pass!r} fail-variant={verdict_fail!r}.",
        )
        self.assertTrue(verdict_pass.get("gate_passed") is True)
        self.assertEqual(verdict_pass.get("reason"), verdict_fail.get("reason"))
        self.assertEqual(
            _names(verdict_pass.get("red")),
            _names(verdict_fail.get("red")),
            "The newly-added red set must be unaffected by the pre-existing "
            "test's outcome.",
        )
        self.assertEqual(
            _names(verdict_pass.get("green_at_baseline")),
            _names(verdict_fail.get("green_at_baseline")),
        )
        entry_pass = _find_entry(verdict_pass.get("preexisting"), "test_preexisting")
        entry_fail = _find_entry(verdict_fail.get("preexisting"), "test_preexisting")
        self.assertIsNotNone(entry_pass)
        self.assertIsNotNone(entry_fail)
        if entry_pass is not None and entry_fail is not None:
            self.assertEqual(entry_pass.get("outcome"), "PASSED")
            self.assertEqual(entry_fail.get("outcome"), "FAILED")


# ---------------------------------------------------------------------------
# BO-2400a-3-iii — function-level granularity within a modified pre-existing
# file.
# ---------------------------------------------------------------------------


class TestAppendedFunctionGranularity(unittest.TestCase):
    """Tests for BO-2400a-3-iii: appending to a pre-existing file does not
    reclassify that file's older functions.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac3iii_appended_functions_are_new_older_functions_stay_preexisting(self) -> None:
        # covers: BO-2400a-3-iii
        """3 pre-existing passing functions + 2 appended failing functions,
        all in ONE file, all tagged for the same AC.

        To make this green, verify_red_baseline must classify at
        test-function granularity: the appended two are newly-added, the
        original three stay pre-existing, even though the FILE itself was
        modified (git would report the whole file as changed).
        """
        ac_id = "BO-FL-III-001"
        base_files = {
            "tests/test_mixed_file.py": f"""\
                def test_orig_a():
                    # covers: {ac_id}
                    assert True


                def test_orig_b():
                    # covers: {ac_id}
                    assert True


                def test_orig_c():
                    # covers: {ac_id}
                    assert True
                """,
        }
        work_dir = _make_worktree(self.tmp_root, base_files)
        test_root = work_dir / "tests"
        # Modify (not overwrite-as-new-file) the SAME pre-existing file by
        # appending two more functions, left uncommitted.
        _write(
            test_root / "test_mixed_file.py",
            f"""\
            def test_orig_a():
                # covers: {ac_id}
                assert True


            def test_orig_b():
                # covers: {ac_id}
                assert True


            def test_orig_c():
                # covers: {ac_id}
                assert True


            def test_appended_a():
                # covers: {ac_id}
                assert False, "not yet implemented"


            def test_appended_b():
                # covers: {ac_id}
                assert False, "not yet implemented"
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root)

        self.assertTrue(verdict.get("gate_passed") is True)
        self.assertEqual(
            _names(verdict.get("red")),
            {"test_appended_a", "test_appended_b"},
            "Only the two appended functions must be classified newly-added "
            f"(and red); got {verdict.get('red')!r}.",
        )
        preexisting_names = _names(verdict.get("preexisting"))
        self.assertEqual(
            preexisting_names,
            {"test_orig_a", "test_orig_b", "test_orig_c"},
            "The three functions present at the merge-base must stay "
            f"pre-existing despite the file being modified; got {preexisting_names!r}.",
        )
        self.assertEqual(
            _names(verdict.get("green_at_baseline")),
            set(),
            "None of the pre-existing functions may leak into green_at_baseline "
            "-- file-level modification must not promote them to newly-added.",
        )


# ---------------------------------------------------------------------------
# BO-2400a-3-ii — the partition is git-derived; no caller-supplied file list.
# ---------------------------------------------------------------------------


class TestPartitionIsGitDrivenNotCallerSupplied(unittest.TestCase):
    """Tests for BO-2400a-3-ii: classification comes from git state alone."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac3ii_signature_accepts_no_caller_supplied_file_list_param(self) -> None:
        # covers: BO-2400a-3-ii
        """The pinned signature is exactly (*, ac_ids, test_root, base_ref=None).

        No parameter for an agent-reported list of written test files may
        exist -- BO-2400a-3 it_requirements[0] already requires the verdict
        to be derived from process exit codes, not agent judgment; a
        caller-supplied file list would reintroduce exactly that judgment.
        """
        params = signature(verify_red_baseline).parameters
        self.assertEqual(
            set(params.keys()),
            {"ac_ids", "test_root", "base_ref"},
            "verify_red_baseline's signature must be exactly "
            "(*, ac_ids, test_root, base_ref=None) per BO-2400a-3-ii -- no "
            f"caller-supplied written-files parameter is permitted; got {sorted(params.keys())!r}.",
        )
        self.assertIn("base_ref", params)
        self.assertIsNone(
            params["base_ref"].default,
            "base_ref must default to None (git-derived merge-base).",
        )

    def test_ac3ii_extraneous_written_files_argument_is_rejected_and_ignored(self) -> None:
        # covers: BO-2400a-3-ii
        """Supplying an agent-reported written-files list must be rejected
        outright (no such parameter exists), and the ordinary git-derived
        call (with no such argument) must still classify correctly on its own.
        """
        ac_id = "BO-FL-II-002"
        base_files = {
            "tests/test_existing.py": f"""\
                def test_existing_passes():
                    # covers: {ac_id}
                    assert True
                """,
        }
        work_dir = _make_worktree(self.tmp_root, base_files)
        test_root = work_dir / "tests"
        _write(
            test_root / "test_new_red.py",
            f"""\
            def test_new_red():
                # covers: {ac_id}
                assert False, "not yet implemented"
            """,
        )

        with self.assertRaises(
            TypeError,
            msg="verify_red_baseline must not accept a caller-supplied "
            "written-test-files argument (BO-2400a-3-ii) -- classification "
            "is git-derived only.",
        ):
            verify_red_baseline(
                ac_ids=[ac_id],
                test_root=test_root,
                written_test_files=[str(test_root / "test_new_red.py")],
            )

        # The ordinary call, with no such argument, must classify from real
        # git state alone and still pass the gate.
        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root)
        self.assertTrue(
            verdict.get("gate_passed") is True,
            "gate_passed must be True from git-derived classification alone "
            f"(no caller-supplied list involved); got {verdict!r}.",
        )


# ---------------------------------------------------------------------------
# BO-2400a-3-vi — total outcome classification: red / green / inconclusive.
# ---------------------------------------------------------------------------


class TestOutcomeClassificationVocabulary(unittest.TestCase):
    """Tests for BO-2400a-3-vi: classification is total over the pytest
    outcome vocabulary, with XFAIL counted as red (not just FAILED).

    The pytest-outcome layer is mocked here (`_run_pytest_and_parse`) since
    the point is the classifier, not pytest itself -- per the test-writer
    brief.  Git state is still real: an empty-base worktree makes every
    covers-tagged function newly-added, isolating the classification logic.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac3vi_outcome_vocabulary_is_classified_red_green_inconclusive(self) -> None:
        # covers: BO-2400a-3-vi
        """FAILED/XFAIL -> red; PASSED/XPASS -> green; SKIPPED/ERROR/unknown
        -> inconclusive, each reported with its raw outcome token.
        """
        ac_id = "BO-FL-VI-001"
        work_dir = _make_worktree(self.tmp_root, {})
        test_root = work_dir / "tests"
        func_names = [
            "test_failed_case",
            "test_xfail_case",
            "test_passed_case",
            "test_xpass_case",
            "test_skipped_case",
            "test_error_case",
            "test_unknown_outcome_case",
        ]
        body = "\n\n\n".join(
            f"def {name}():\n    # covers: {ac_id}\n    pass" for name in func_names
        )
        test_file = test_root / "test_all_outcomes.py"
        _write(test_file, body + "\n")

        mocked_outcomes = {
            f"{test_file}::test_failed_case": "FAILED",
            f"{test_file}::test_xfail_case": "XFAIL",
            f"{test_file}::test_passed_case": "PASSED",
            f"{test_file}::test_xpass_case": "XPASS",
            f"{test_file}::test_skipped_case": "SKIPPED",
            f"{test_file}::test_error_case": "ERROR",
            f"{test_file}::test_unknown_outcome_case": "WEIRDTOKEN",
        }

        with patch("fast_lane._run_pytest_and_parse", return_value=mocked_outcomes):
            verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root)

        self.assertTrue(verdict.get("gate_passed") is True)
        self.assertEqual(
            _names(verdict.get("red")),
            {"test_failed_case", "test_xfail_case"},
            f"FAILED and XFAIL must both classify red; got {verdict.get('red')!r}.",
        )
        self.assertEqual(
            _names(verdict.get("green_at_baseline")),
            {"test_passed_case", "test_xpass_case"},
            f"PASSED and XPASS must both classify green; got {verdict.get('green_at_baseline')!r}.",
        )
        inconclusive = verdict.get("inconclusive")
        self.assertEqual(
            _names(inconclusive),
            {"test_skipped_case", "test_error_case", "test_unknown_outcome_case"},
            "SKIPPED, ERROR, and an unrecognised outcome token must all "
            f"classify inconclusive (never silently dropped); got {inconclusive!r}.",
        )
        skipped_entry = _find_entry(inconclusive, "test_skipped_case")
        error_entry = _find_entry(inconclusive, "test_error_case")
        unknown_entry = _find_entry(inconclusive, "test_unknown_outcome_case")
        self.assertIsNotNone(skipped_entry)
        self.assertIsNotNone(error_entry)
        self.assertIsNotNone(unknown_entry)
        if skipped_entry is not None:
            self.assertEqual(skipped_entry.get("outcome"), "SKIPPED")
        if error_entry is not None:
            self.assertEqual(error_entry.get("outcome"), "ERROR")
        if unknown_entry is not None:
            self.assertEqual(
                unknown_entry.get("outcome"),
                "WEIRDTOKEN",
                "An unrecognised outcome token must be reported verbatim, not dropped.",
            )

    def test_ac3vi_all_xfail_newly_added_set_passes_gate(self) -> None:
        # covers: BO-2400a-3-vi
        """An all-XFAIL newly-added set must pass the gate.

        Every AC in a fast-lane batch is not-yet-done, so the repository's
        pytest_ac_enforcement plugin converts genuine failures to XFAIL for
        every real run.  A classifier recognising only FAILED as red would
        see zero red tests here and make the gate vacuous in every real
        invocation.
        """
        ac_id = "BO-FL-VI-002"
        work_dir = _make_worktree(self.tmp_root, {})
        test_root = work_dir / "tests"
        test_file = test_root / "test_xfail_only.py"
        _write(
            test_file,
            f"""\
            def test_xfail_only():
                # covers: {ac_id}
                pass
            """,
        )
        mocked_outcomes = {f"{test_file}::test_xfail_only": "XFAIL"}

        with patch("fast_lane._run_pytest_and_parse", return_value=mocked_outcomes):
            verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root)

        self.assertTrue(
            verdict.get("gate_passed") is True,
            f"An all-XFAIL newly-added set must pass the gate; got {verdict!r}.",
        )
        self.assertIsNone(verdict.get("reason"))
        self.assertEqual(_names(verdict.get("red")), {"test_xfail_only"})


# ---------------------------------------------------------------------------
# BO-2400a-3-i — the three halt reasons are distinguishable.
# ---------------------------------------------------------------------------


class TestThreeHaltReasons(unittest.TestCase):
    """Tests for BO-2400a-3-i: a fixed, named halt-reason vocabulary."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac3i_no_new_covering_tests_when_batch_has_no_matching_tags(self) -> None:
        # covers: BO-2400a-3-i
        """An empty newly-added (and pre-existing) set halts with
        no_new_covering_tests.
        """
        ac_id = "BO-FL-I-001"
        work_dir = _make_worktree(self.tmp_root, {})
        test_root = work_dir / "tests"
        test_root.mkdir(parents=True, exist_ok=True)

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root)

        self.assertFalse(verdict.get("gate_passed"))
        self.assertEqual(verdict.get("reason"), "no_new_covering_tests")

    def test_ac3i_all_green_newly_added_halts_with_correct_reason(self) -> None:
        # covers: BO-2400a-3-i
        """An all-green newly-added set halts with all_new_tests_green_at_baseline."""
        ac_id = "BO-FL-I-002"
        work_dir = _make_worktree(self.tmp_root, {})
        test_root = work_dir / "tests"
        test_file = test_root / "test_all_green.py"
        _write(
            test_file,
            f"""\
            def test_green_x():
                # covers: {ac_id}
                pass


            def test_green_y():
                # covers: {ac_id}
                pass
            """,
        )
        mocked_outcomes = {
            f"{test_file}::test_green_x": "PASSED",
            f"{test_file}::test_green_y": "PASSED",
        }

        with patch("fast_lane._run_pytest_and_parse", return_value=mocked_outcomes):
            verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root)

        self.assertFalse(verdict.get("gate_passed"))
        self.assertEqual(verdict.get("reason"), "all_new_tests_green_at_baseline")
        self.assertEqual(
            _names(verdict.get("green_at_baseline")),
            {"test_green_x", "test_green_y"},
        )
        self.assertEqual(_names(verdict.get("red")), set())

    def test_ac3i_green_and_inconclusive_with_no_red_halts_with_correct_reason(self) -> None:
        # covers: BO-2400a-3-i
        """Green + inconclusive newly-added tests (no red at all) halt with
        no_red_outcome_among_new_tests.
        """
        ac_id = "BO-FL-I-003"
        work_dir = _make_worktree(self.tmp_root, {})
        test_root = work_dir / "tests"
        test_file = test_root / "test_green_and_skip.py"
        _write(
            test_file,
            f"""\
            def test_green_only():
                # covers: {ac_id}
                pass


            def test_skipped_only():
                # covers: {ac_id}
                pass
            """,
        )
        mocked_outcomes = {
            f"{test_file}::test_green_only": "PASSED",
            f"{test_file}::test_skipped_only": "SKIPPED",
        }

        with patch("fast_lane._run_pytest_and_parse", return_value=mocked_outcomes):
            verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root)

        self.assertFalse(verdict.get("gate_passed"))
        self.assertEqual(verdict.get("reason"), "no_red_outcome_among_new_tests")
        self.assertEqual(_names(verdict.get("green_at_baseline")), {"test_green_only"})
        self.assertEqual(_names(verdict.get("inconclusive")), {"test_skipped_only"})
        self.assertEqual(_names(verdict.get("red")), set())


# ---------------------------------------------------------------------------
# BO-2400a-3-vii — unavailable git metadata fails closed.
# ---------------------------------------------------------------------------


class TestBaselinePartitionUnavailable(unittest.TestCase):
    """Tests for BO-2400a-3-vii: fail closed when the merge-base cannot be
    resolved -- never fall back to treating everything as newly-added.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac3vii_test_root_outside_any_git_repo_fails_closed(self) -> None:
        # covers: BO-2400a-3-vii
        """test_root that is not inside any git worktree at all must halt
        with baseline_partition_unavailable, never fall back to
        "everything is newly-added".
        """
        precheck = subprocess.run(
            ["git", "-C", str(self.tmp_root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertNotEqual(
            precheck.returncode,
            0,
            "Test fixture assumption violated: the tempdir used for this "
            "scenario must NOT be inside any git repository.",
        )
        ac_id = "BO-FL-VII-001"
        test_root = self.tmp_root / "tests"
        _write(
            test_root / "test_orphan.py",
            f"""\
            def test_orphan():
                # covers: {ac_id}
                assert False
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root)

        self.assertFalse(
            verdict.get("gate_passed"),
            "The gate must fail closed (gate_passed=False) when the "
            f"worktree's git metadata is unavailable; got {verdict!r}.",
        )
        self.assertEqual(verdict.get("reason"), "baseline_partition_unavailable")

    def test_ac3vii_repo_without_origin_remote_fails_closed(self) -> None:
        # covers: BO-2400a-3-vii
        """A real git repo with no `origin` remote at all cannot resolve
        `origin/main`; the gate must halt with baseline_partition_unavailable
        rather than treating every covering test as newly-added.
        """
        repo_dir = self.tmp_root / "lone_repo"
        _init_repo(repo_dir)
        _write(repo_dir / "README.md", "placeholder\n")
        _commit_all(repo_dir, "initial")

        ac_id = "BO-FL-VII-002"
        test_root = repo_dir / "tests"
        _write(
            test_root / "test_no_origin.py",
            f"""\
            def test_no_origin():
                # covers: {ac_id}
                assert False
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root)

        self.assertFalse(verdict.get("gate_passed"))
        self.assertEqual(verdict.get("reason"), "baseline_partition_unavailable")


# ---------------------------------------------------------------------------
# BO-2400a-3-viii — idempotency.
# ---------------------------------------------------------------------------


class TestIdempotency(unittest.TestCase):
    """Tests for BO-2400a-3-viii: two consecutive runs over an unchanged
    worktree produce identical results and leave the worktree unmodified.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac3viii_repeated_calls_return_identical_verdict_and_leave_worktree_clean(
        self,
    ) -> None:
        # covers: BO-2400a-3-viii
        """Re-running the gate on an unchanged tree must reproduce the exact
        same partition, classification, verdict, and ordering -- and must
        write nothing to the worktree (no fetch, no ref update, no index
        write) as a side effect of resolving the merge-base.
        """
        ac_id = "BO-FL-VIII-001"
        base_files = {
            "tests/test_preexisting.py": f"""\
                def test_preexisting_passes():
                    # covers: {ac_id}
                    assert True
                """,
        }
        work_dir = _make_worktree(self.tmp_root, base_files)
        test_root = work_dir / "tests"
        _write(
            test_root / "test_new_green.py",
            f"""\
            def test_new_green():
                # covers: {ac_id}
                assert True
            """,
        )
        _write(
            test_root / "test_new_red.py",
            f"""\
            def test_new_red():
                # covers: {ac_id}
                assert False, "not yet implemented"
            """,
        )

        # Scoped to exactly what BO-2400a-3-viii's it_requirements forbid as a
        # side effect of resolving the merge-base: "no fetch, no ref update,
        # no index write".  We deliberately do NOT diff raw `git status
        # --porcelain` here -- running pytest on the fixture files is itself
        # allowed to leave Python bytecode-cache artifacts (__pycache__)
        # behind, which is irrelevant noise for this AC's git-mutation
        # guarantee and would make the assertion fail for the wrong reason.
        head_before = _run_git(["rev-parse", "HEAD"], cwd=work_dir)
        origin_main_before = _run_git(["rev-parse", "refs/remotes/origin/main"], cwd=work_dir)
        tracked_diff_before = _run_git(["diff", "--stat"], cwd=work_dir)

        verdict_1 = verify_red_baseline(ac_ids=[ac_id], test_root=test_root)

        head_mid = _run_git(["rev-parse", "HEAD"], cwd=work_dir)
        origin_main_mid = _run_git(["rev-parse", "refs/remotes/origin/main"], cwd=work_dir)
        tracked_diff_mid = _run_git(["diff", "--stat"], cwd=work_dir)

        verdict_2 = verify_red_baseline(ac_ids=[ac_id], test_root=test_root)

        head_after = _run_git(["rev-parse", "HEAD"], cwd=work_dir)
        origin_main_after = _run_git(["rev-parse", "refs/remotes/origin/main"], cwd=work_dir)
        tracked_diff_after = _run_git(["diff", "--stat"], cwd=work_dir)

        # Pin the verdict to the amended contract shape first -- a bare
        # equality check alone would pass immediately against the
        # PRE-amendment implementation too (it also returns a stable,
        # self-consistent dict shape for identical inputs), which would make
        # this an under-specified, falsely-green test.  Asserting the pinned
        # keys/semantics here is what actually distinguishes the amended
        # gate from the old one.
        self.assertTrue(
            verdict_1.get("gate_passed") is True,
            f"gate_passed must be True (a red newly-added test is present); got {verdict_1!r}.",
        )
        self.assertIsNone(verdict_1.get("reason"))
        self.assertIn("test_new_red", _names(verdict_1.get("red")))
        self.assertIn("test_new_green", _names(verdict_1.get("green_at_baseline")))
        self.assertIn("test_preexisting_passes", _names(verdict_1.get("preexisting")))

        self.assertEqual(
            verdict_1,
            verdict_2,
            "Two consecutive calls against an unchanged worktree must return "
            f"byte-identical verdict dicts; run1={verdict_1!r} run2={verdict_2!r}.",
        )
        self.assertEqual(
            (head_before, origin_main_before, tracked_diff_before),
            (head_mid, origin_main_mid, tracked_diff_mid),
            "Resolving the merge-base must not advance HEAD, move "
            "refs/remotes/origin/main (no fetch), or write to the index/"
            "tracked files -- state must be identical before and after the "
            "first call (BO-2400a-3-viii).",
        )
        self.assertEqual(
            (head_mid, origin_main_mid, tracked_diff_mid),
            (head_after, origin_main_after, tracked_diff_after),
            "The same must hold across the SECOND call too.",
        )


if __name__ == "__main__":
    unittest.main()
