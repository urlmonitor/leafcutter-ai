"""
MODULE: test_ge_120e_4_i
AC: GE-120e-4-i — "Reworking a merge after the operation record is gone still
    attributes only the author's part"

GOAL: TDD red-baseline tests for the one fixture in this L1 where the
    operation record (MERGE_HEAD) has already expired and the parent states
    have not: a merge commit that has already been made (so no operation
    record remains) is then REVISED (``git commit --amend``) — restaging the
    same merged content plus one edit of the author's own.

BUSINESS CONTEXT: Ticket 36 of EPIC-TrustThatAGreenCheckActuallyChecked.
    Source AC: GE-120e-4-i. The AC store's own ``test_spec`` (authoritative
    over the ticket body's derived Gherkin) supplies the three named tests
    below; the fourth (reachability) is the mandatory floor test this
    ticket's own Test Requirements table appends because the AC authored no
    ``test_spec`` entry naming a production entry point.

    GE-120e-4-i sits at the bottom of a three-AC chain, none of which have
    landed as of this file's authoring:
      GE-120e-1 (ticket 28, todo) — the shared "authored-change" derivation
        every self-deriving check is meant to consult, combining the states
        a commit is built on with any operation record.
      GE-120e-4 (ticket 35, todo) — extends that derivation to consult
        REVERT_HEAD / CHERRY_PICK_HEAD, not just MERGE_HEAD.
      GE-120e-4-i (this ticket) — the edge case within GE-120e-4's own scope
        where the operation record has already EXPIRED (the merge already
        committed) but the commit under revision's parents are still
        discoverable from the commit itself.

WHY THIS CANNOT BE A NAIVE BEHAVIOURAL TEST AGAINST TODAY'S CODE (important —
    read before "fixing" this file to remove the gate below): today's
    ``check_contract_shrinking.py`` has NO shared derivation at all — it
    scopes only on ``MERGE_HEAD`` (see ``_merge_scoped_paths()``) and, when
    that probe is absent, falls back to the FULL unscoped ``git diff
    --cached``. For the exact fixture this AC describes (amend a just-made
    merge commit, i.e. ``HEAD`` already IS the merge and already contains
    every bit of the carried-in content), that accidental fallback already
    produces the "correct" narrow diff — because ``git diff --cached``
    against ``HEAD`` trivially excludes everything ``HEAD`` already contains,
    with no awareness of "states this commit is built on" or "operation
    record" whatsoever. Empirically verified before writing this file (two
    scratch fixtures — one with a violation planted in the author's own edit,
    one with the violation only in the merged-in content — both against
    today's ``check_contract_shrinking.py``): both already produce the
    AC-correct exit code. A test that merely re-confirms that coincidence
    would be GREEN before any of GE-120e-1/GE-120e-4/GE-120e-4-i exist —
    exactly the under-specified-test trap CLAUDE.md's "TDD Order" section and
    the test-writer skill's red-baseline rule both name explicitly.

    What this AC actually protects against is a FUTURE regression: once
    GE-120e-1's derivation exists and GE-120e-4 teaches it to consult
    REVERT_HEAD/CHERRY_PICK_HEAD, the natural implementation shape is
    "read the operation record first, and if none is found, decide there is
    nothing to narrow" — see the it_requirements' named anti-pattern, "if
    there is no operation record, treat this as an ordinary commit and use
    the whole staged tree". That anti-pattern would specifically DESTROY
    today's accidental correctness on this exact fixture (a real derivation
    that starts asking "what states is this built on" and then gives up when
    the marker is gone has replaced a harmless no-op fallback with an active
    wrong answer). This file's tests are written against that future
    derivation, not today's marker-only code, and are gated on it existing.

CONTRACT THIS TEST FILE ESTABLISHES for whoever implements GE-120e-1
    (record this choice for that ticket's implementer, per its own
    instruction to "shape it like ``_resolve_root.py``" — one shared module
    in ``templates/scripts/commit_guardian/``, imported by the checks):

        templates/scripts/commit_guardian/_authored_change.py
            get_authored_change(cwd: Path | None = None) -> AuthoredChange
                Derives the change set from the states the commit under
                revision is built on (its parent(s), discovered from the
                commit itself — NOT from an operation-record marker) refined
                by whichever operation record (MERGE_HEAD / REVERT_HEAD /
                CHERRY_PICK_HEAD) is present. Absence of a marker must NOT
                collapse the derivation to "the whole staged tree" — with no
                marker and a single parent it is the ordinary-commit case
                (equivalent to plain ``git diff --cached``); with no marker
                and a commit whose HEAD has two parents (the amend-of-merge
                case this AC is about) it must still narrow against BOTH of
                HEAD's parents.

            class AuthoredChange:
                diff_text: str          — full text diff shape (contract-shrinking)
                name_status: list[tuple[str, str]]  — name-status shape (doc-frontmatter)
                paths: list[str]        — repo-relative paths in the change set
                states: list[str]       — commit-ish(es) the change set was derived
                                           against, for provenance in objection text
                could_not_check: bool   — True when the derivation itself failed
                error: str | None

    Neither this module nor ``check_contract_shrinking.py`` consulting it
    exists yet anywhere in this repository (confirmed: no
    ``_authored_change.py`` under ``templates/scripts/commit_guardian/``, and
    ``check_contract_shrinking.py`` still keys purely on ``MERGE_HEAD``).
    Importing it raises ``ImportError``. THIS IS THE VALID RED STATE.

    Until it exists, every test below fails via an explicit ``self.fail()``
    naming the missing dependency — matching the established convention in
    this same epic (``test_ge_120e_2_i.py``, ``test_ge120c1i_setup_failure_reporting.py``)
    rather than a bare crash, and rather than silently passing on a
    coincidence.

====================================================================
DECISION HISTORY
====================================================================
- 2026-08-25 [EPIC-TrustThatAGreenCheckActuallyChecked/36]: Initial TDD
  red-baseline, written before GE-120e-1's shared derivation
  (``_authored_change.py``) or GE-120e-4's operation-record extension exist
  (both are separate, still-``todo`` tickets in this epic; this ticket's own
  ``depends_on:`` frontmatter is empty even though the AC store correctly
  records ``depends_on: [GE-120e-4]`` — the same ticket-authoring gap flagged
  in ``test_ge_120e_2_i.py``'s Comments, not fixed here). Verified, by
  actually running today's ``check_contract_shrinking.py`` against real
  scratch fixtures, that a naive behavioural test targeting only observable
  process output would be green today by coincidence (see rationale above) —
  so this file gates on the proposed shared-derivation contract instead. The
  module path and field names above are this ticket's proposed contract;
  GE-120e-1's and GE-120e-4's implementers should honour them or update this
  file to match whatever they actually ship.
====================================================================
"""
# @ac-tag: GE-120e-4-i

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — make templates/scripts/commit_guardian importable regardless
# of cwd, and locate the real repository root + the real check + run_hook.py
# entry points this file executes as subprocesses.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CHECK_PATH = _COMMIT_GUARDIAN_DIR / "check_contract_shrinking.py"
_RUN_HOOK_PATH = _COMMIT_GUARDIAN_DIR / "run_hook.py"

if str(_COMMIT_GUARDIAN_DIR) not in sys.path:
    sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))

# ---------------------------------------------------------------------------
# GE-120e-1's expected shared authored-change derivation. Does not exist yet
# — see module docstring, "CONTRACT THIS TEST FILE ESTABLISHES".
# ---------------------------------------------------------------------------
try:
    import _authored_change  # type: ignore[import]  # noqa: E402
    _AUTHORED_CHANGE_OK = hasattr(_authored_change, "get_authored_change")
except ImportError:
    _authored_change = None  # type: ignore[assignment]
    _AUTHORED_CHANGE_OK = False

_MISSING_DEPENDENCY_MSG = (
    "templates/scripts/commit_guardian/_authored_change.py does not exist "
    "yet (or does not define get_authored_change()). This is GE-120e-1's "
    "shared authored-change derivation, extended by GE-120e-4 to consult "
    "REVERT_HEAD/CHERRY_PICK_HEAD — neither has landed. Today's "
    "check_contract_shrinking.py handles this ticket's exact fixture "
    "correctly only by coincidence (a marker-only MERGE_HEAD probe that "
    "falls back to the full unscoped `git diff --cached`, which happens to "
    "already exclude a completed merge's content because HEAD already "
    "contains it) — that accidental correctness is exactly what the "
    "GE-120e-1/GE-120e-4 refactor risks breaking if it reads the operation "
    "record first and treats its absence as license to use the whole "
    "staged tree. This test cannot verify the REAL contract until the "
    "shared derivation exists. See the module docstring for the full "
    "proposed contract."
)

_GIT_TIMEOUT = 30


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


def _init_repo(repo: Path) -> None:
    _run_git(["init", "-q"], repo)
    _run_git(["config", "user.email", "ge120e4i@test.local"], repo)
    _run_git(["config", "user.name", "GE-120e-4-i Test"], repo)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_merge_repo(repo: Path) -> str:
    """Build a real repository with a completed, clean, disjoint-file merge.

    Recorded (merged-in) content lives on ``mainline``: a production edit to
    ``prod/module.py`` concurrent with dropping ``test_two`` from
    ``unit_tests/test_module.py`` — the exact contract-shrinking shape.
    ``feature`` (the branch we work on) merges ``mainline`` in cleanly (no
    conflicts, disjoint files), producing a real merge commit. By the time
    this function returns, the merge is fully COMMITTED — MERGE_HEAD is
    gone, matching the AC's "operation record is gone" precondition.

    Returns:
        The merge commit's SHA (the "commit under revision").
    """
    _init_repo(repo)
    _write(repo / "prod" / "module.py", "def helper():\n    return 1\n")
    _write(
        repo / "unit_tests" / "test_module.py",
        "def test_one():\n    assert True\n\n\ndef test_two():\n    assert True\n",
    )
    _write(repo / "unit_tests" / "test_other.py", "def test_alpha():\n    assert True\n")
    _run_git(["add", "-A"], repo)
    _run_git(["commit", "-q", "-m", "base"], repo)
    _run_git(["branch", "mainline"], repo)
    _run_git(["checkout", "-q", "-b", "feature"], repo)
    _write(repo / "prod" / "other_feature.py", "# feature marker\n")
    _run_git(["add", "-A"], repo)
    _run_git(["commit", "-q", "-m", "feature work"], repo)

    _run_git(["checkout", "-q", "mainline"], repo)
    _write(repo / "unit_tests" / "test_module.py", "def test_one():\n    assert True\n")
    _write(repo / "prod" / "module.py", "def helper():\n    return 2\n")
    _run_git(["add", "-A"], repo)
    _run_git(["commit", "-q", "-m", "mainline: refactor + drop test_two"], repo)

    _run_git(["checkout", "-q", "feature"], repo)
    _run_git(["merge", "--no-edit", "-q", "mainline"], repo)

    # Sanity-check the fixture itself: the operation record must genuinely
    # be gone, or this test is not exercising the precondition it claims to.
    probe = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"],
        cwd=str(repo), capture_output=True, text=True, timeout=_GIT_TIMEOUT,
        check=False,
    )
    if probe.returncode == 0:
        raise AssertionError(
            "Test fixture invalid: MERGE_HEAD still present immediately "
            "after a clean, conflict-free `git merge --no-edit`. The "
            "operation-record-is-gone precondition this AC exercises is "
            "not actually present."
        )
    parents = _run_git(["log", "-1", "--pretty=%P"], repo).stdout.split()
    if len(parents) != 2:
        raise AssertionError(
            f"Test fixture invalid: expected the merge commit to have 2 "
            f"parents, found {len(parents)}: {parents!r}"
        )
    return _run_git(["rev-parse", "HEAD"], repo).stdout.strip()


def _run_check(repo: Path) -> subprocess.CompletedProcess:
    """Run check_contract_shrinking.py as a real subprocess against *repo*.

    Deliberately invokes the script directly (not via import) so it reads
    real git state (``git diff --cached``, ``MERGE_HEAD``, HEAD's parents)
    from *repo* — the "execute the check as a process" requirement.
    """
    return subprocess.run(
        [sys.executable, str(_CHECK_PATH)],
        cwd=str(repo), capture_output=True, text=True, timeout=_GIT_TIMEOUT,
        check=False,
    )


def _run_check_via_entry_point(repo: Path) -> subprocess.CompletedProcess:
    """Run the check via the REAL deployed dispatch path (run_hook.py).

    This is the entry the commit_guardian manifest actually registers for
    check-contract-shrinking (``entry: "python .../run_hook.py
    .../check_contract_shrinking.py"``) — used for the reachability test so
    that test exercises the dispatch path, not a hand-picked shortcut.
    """
    return subprocess.run(
        [sys.executable, str(_RUN_HOOK_PATH), str(_CHECK_PATH)],
        cwd=str(repo), capture_output=True, text=True, timeout=_GIT_TIMEOUT,
        check=False,
    )


class TestRevisedMergeChangeSetHoldsOnlyTheAuthorsEdit(unittest.TestCase):
    """AC-1: the change set the check inspects holds the author's edit and
    not the merged-in work."""

    def test_ge120e4i_revised_merge_change_set_holds_only_the_authors_edit(
        self,
    ) -> None:
        # covers: GE-120e-4-i
        """RED until GE-120e-1's shared derivation (extended by GE-120e-4)
        exists.

        Once it lands: build a real merge whose merged-in content carries a
        contract-shrinking violation (mainline drops ``test_two`` concurrent
        with a production edit — already recorded, not authored by the
        reviser), commit it (operation record now gone), then stage ONE
        edit of the reviser's own that is ITSELF a distinct contract-
        shrinking violation, in different files than the merged-in one. Run
        the check as a process. It must BLOCK (the author's own violation is
        real) and its output must name the author's file/violation while
        never naming the merged-in file/violation — proving the inspected
        change set held the edit and not the merged-in work.
        """
        if not _AUTHORED_CHANGE_OK:
            self.fail(_MISSING_DEPENDENCY_MSG)

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            _build_merge_repo(repo)

            # The reviser's own edit: a DISTINCT contract-shrinking violation,
            # in files the merge never touched.
            other_feature = repo / "prod" / "other_feature.py"
            other_feature.write_text(
                other_feature.read_text(encoding="utf-8") + "# author followup edit\n",
                encoding="utf-8",
            )
            test_other = repo / "unit_tests" / "test_other.py"
            test_other.write_text(
                test_other.read_text(encoding="utf-8")
                + "\n\ndef test_beta():\n    pytest.skip('flaky')\n",
                encoding="utf-8",
            )
            _run_git(["add", "-A"], repo)

            result = _run_check(repo)
            combined = result.stdout + result.stderr

            self.assertNotEqual(
                0, result.returncode,
                "The author's own contract-shrinking violation must still "
                f"block the revision. Output:\n{combined}",
            )
            self.assertIn(
                "other_feature.py", combined,
                "The author's own modified file must be named in the "
                f"objection. Output:\n{combined}",
            )
            self.assertIn(
                "test_other.py", combined,
                "The author's own weakened test file must be named. "
                f"Output:\n{combined}",
            )
            self.assertNotIn(
                "test_module.py", combined,
                "The merged-in file (never touched by the author's edit) "
                f"must NOT be attributed to the reviser. Output:\n{combined}",
            )
            self.assertNotIn(
                "test_two", combined,
                "The merged-in test deletion must NOT appear in the "
                f"objection. Output:\n{combined}",
            )


class TestAbsentOperationRecordDoesNotWidenToWholeStagedTree(unittest.TestCase):
    """AC-2: the absence of an operation record does not cause the whole
    staged tree to be attributed to the author — the expired-marker trap."""

    def test_ge120e4i_absent_operation_record_does_not_widen_to_the_whole_staged_tree(
        self,
    ) -> None:
        # covers: GE-120e-4-i
        """RED until GE-120e-1's shared derivation (extended by GE-120e-4)
        exists.

        Same merge fixture as above (merged-in violation present), but this
        time the reviser's own edit is BENIGN — no violation of their own.
        The check must NOT block: if the derivation, on finding no
        operation record, fell back to "the whole staged tree" (the named
        anti-pattern), it would rediscover the merged-in violation and block
        a commit the author did nothing wrong in.
        """
        if not _AUTHORED_CHANGE_OK:
            self.fail(_MISSING_DEPENDENCY_MSG)

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            _build_merge_repo(repo)

            other_feature = repo / "prod" / "other_feature.py"
            other_feature.write_text(
                other_feature.read_text(encoding="utf-8") + "# author benign followup edit\n",
                encoding="utf-8",
            )
            _run_git(["add", "-A"], repo)

            result = _run_check(repo)
            combined = result.stdout + result.stderr

            self.assertEqual(
                0, result.returncode,
                "VACUOUS-WIDENING DETECTED: the reviser made no weakening "
                "edit of their own, but the check blocked anyway — the "
                "absent operation record must not cause the merged-in "
                f"content to be attributed to them. Output:\n{combined}",
            )
            self.assertNotIn(
                "test_two", combined,
                f"The merged-in violation must not surface at all. Output:\n{combined}",
            )


class TestVerdictMatchesOrdinaryFollowupCommitArm(unittest.TestCase):
    """AC-3: the verdict on (revised merge + edit) is identical to the
    verdict on (original merge + that same edit as an ordinary follow-up
    commit) — both arms in one case, asserted as an equality of two real
    runs, not inferred."""

    def test_ge120e4i_verdict_matches_the_ordinary_followup_commit_arm(self) -> None:
        # covers: GE-120e-4-i
        """RED until GE-120e-1's shared derivation (extended by GE-120e-4)
        exists.

        Arm A (revision): merge is committed, then the author's violating
        edit is staged on top — the pre-commit-hook state for `git commit
        --amend`. Run the check; capture status+output. Then actually
        perform the amend (a real repository operation) and confirm the
        resulting commit still has 2 parents (it is still, structurally,
        the same merge, revised).

        Arm B (ordinary follow-up): an independently-built copy of the SAME
        merge, committed the same way, then the SAME edit staged as an
        ordinary (non-amend) follow-up commit's pre-commit-hook state. Run
        the check; capture status+output. Then actually commit it as a real
        ordinary commit and confirm the result has exactly 1 parent (the
        merge commit itself) — a different commit topology from Arm A even
        though the verdict must be identical.
        """
        if not _AUTHORED_CHANGE_OK:
            self.fail(_MISSING_DEPENDENCY_MSG)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo_a = tmp_path / "repo_amend"
            repo_b = tmp_path / "repo_followup"

            merge_sha_a = _build_merge_repo(repo_a)
            merge_sha_b = _build_merge_repo(repo_b)

            def _stage_the_edit(repo: Path) -> None:
                other_feature = repo / "prod" / "other_feature.py"
                other_feature.write_text(
                    other_feature.read_text(encoding="utf-8") + "# author followup edit\n",
                    encoding="utf-8",
                )
                test_other = repo / "unit_tests" / "test_other.py"
                test_other.write_text(
                    test_other.read_text(encoding="utf-8")
                    + "\n\ndef test_beta():\n    pytest.skip('flaky')\n",
                    encoding="utf-8",
                )
                _run_git(["add", "-A"], repo)

            # --- Arm A: revision of the merge (amend) ---
            _stage_the_edit(repo_a)
            result_a = _run_check(repo_a)
            _run_git(["commit", "-q", "--amend", "--no-edit"], repo_a)
            parents_a = _run_git(["log", "-1", "--pretty=%P"], repo_a).stdout.split()

            # --- Arm B: the same edit as an ordinary follow-up commit ---
            _stage_the_edit(repo_b)
            result_b = _run_check(repo_b)
            _run_git(["commit", "-q", "-m", "author followup"], repo_b)
            parents_b = _run_git(["log", "-1", "--pretty=%P"], repo_b).stdout.split()

            combined_a = result_a.stdout + result_a.stderr
            combined_b = result_b.stdout + result_b.stderr

            self.assertEqual(
                result_a.returncode, result_b.returncode,
                "Both arms must produce the SAME result status.\n"
                f"Arm A (amend) output:\n{combined_a}\n"
                f"Arm B (follow-up) output:\n{combined_b}",
            )
            # Same objected-to content in both arms (same author files/violations).
            for needle in ("other_feature.py", "test_other.py"):
                self.assertIn(needle, combined_a, f"Arm A output missing {needle!r}")
                self.assertIn(needle, combined_b, f"Arm B output missing {needle!r}")
            self.assertNotIn("test_two", combined_a)
            self.assertNotIn("test_two", combined_b)

            # Structural check: both operations were REAL and produced the
            # documented, DIFFERENT commit topology despite the equal verdict.
            self.assertEqual(
                2, len(parents_a),
                "Arm A (amend) must still be a 2-parent merge commit after "
                f"the revision: {parents_a!r}",
            )
            self.assertEqual(
                1, len(parents_b),
                "Arm B (ordinary follow-up) must be a single-parent commit "
                f"on top of the merge: {parents_b!r}",
            )
            self.assertEqual(
                merge_sha_b, parents_b[0],
                "Arm B's follow-up commit must be a child of the original "
                "merge commit.",
            )
            self.assertNotEqual(
                merge_sha_a, "",
                "Sanity: Arm A's original merge sha must have been captured.",
            )


class TestReachableFromEntryPoint(unittest.TestCase):
    """Mandatory floor test: invoke the production entry point (the real
    commit_guardian dispatch path, run_hook.py -> check_contract_shrinking.py)
    as a subprocess and assert the new behaviour actually occurs. Importing
    the check's functions directly would NOT satisfy this."""

    def test_ge_120e_4_i_reachable_from_entry_point(self) -> None:
        # covers: GE-120e-4-i
        """RED until GE-120e-1's shared derivation (extended by GE-120e-4)
        exists.

        Re-runs the AC-1 scenario (merged-in violation + a distinct
        author-authored violation) but dispatches through
        ``run_hook.py check_contract_shrinking.py`` — the exact command the
        real commit_guardian manifest registers for check-contract-shrinking
        (see ``templates/scripts/commit_guardian/commit_guardian.json``) —
        rather than invoking the check script directly, proving the
        behaviour is reachable via the real deployed dispatch path.
        """
        if not _AUTHORED_CHANGE_OK:
            self.fail(_MISSING_DEPENDENCY_MSG)

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            _build_merge_repo(repo)

            other_feature = repo / "prod" / "other_feature.py"
            other_feature.write_text(
                other_feature.read_text(encoding="utf-8") + "# author followup edit\n",
                encoding="utf-8",
            )
            test_other = repo / "unit_tests" / "test_other.py"
            test_other.write_text(
                test_other.read_text(encoding="utf-8")
                + "\n\ndef test_beta():\n    pytest.skip('flaky')\n",
                encoding="utf-8",
            )
            _run_git(["add", "-A"], repo)

            result = _run_check_via_entry_point(repo)
            combined = result.stdout + result.stderr

            self.assertNotEqual(
                0, result.returncode,
                "Dispatching via the real run_hook.py entry point must "
                f"still block on the author's own violation. Output:\n{combined}",
            )
            self.assertIn("other_feature.py", combined)
            self.assertNotIn("test_two", combined)


if __name__ == "__main__":
    unittest.main()
