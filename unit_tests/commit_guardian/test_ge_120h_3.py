"""
MODULE: unit_tests/commit_guardian/test_ge_120h_3.py
COVERS: GE-120h-3 -- "Five checks the package has always presented as
    protecting you begin to run on an ordinary commit, and none of them
    refuses work the same repository accepted the day before"

SCOPE OF THIS FILE. Arms 1, 2 and 5 of GE-120h-3 landed in 5d0792d1 (PR
    #808): all five checks are registered in hooks_manifest.hooks, the
    folder-density ratchet already reports pre-existing state as a warning
    rather than a violation, and the inventory baseline
    (test_hook_registration_inventory.py's UNREGISTERED_BASELINE) no longer
    names any of the five. This file covers ONLY arm 3 -- the nothing-to-
    -inspect clause -- plus the ticket's mandatory reachability floor test.
    Arm 4 (the anti-theatre refusal clause) is covered separately in
    test_ge_120h_3_refusals.py, per files_touched and the 400-counted-line
    file-size ratchet.

ARM 3, PRECISELY. Two of the five checks have nothing to bite on in an
    ordinary commit that stages no .sql file and nothing under
    debugging/scripts/: check_sql_complexity.py and check_debug_scripts.py.
    Today both exit 0 SILENTLY in that case -- indistinguishable, to a
    caller reading only the exit code or only the absence of output, from a
    check that ran and found everything clean. GE-120a-1's shared vocabulary
    module (check_outcome.py, OUTCOME_NOTHING_TO_INSPECT ->
    "RESULT: nothing_to_inspect") exists precisely to make that distinction
    machine-readable, and check_contract_shrinking.py / check_doc_frontmatter.py
    already use it for the identical shape (an empty derived change set is a
    PASS, not a skip, but must ANNOUNCE the emptiness). check_folder_density.py
    is deliberately OUT of this arm's scope: this repository holds real
    over-density directories, so its subject is never absent here.

    Neither check imports check_outcome today, so both tests below are RED:
    empirically verified via a real subprocess run through run_hook.py
    against the TEMPLATE (source-tree) script, in a scratch git repository,
    BEFORE this test file was written -- see the sign-off comment on
    TICKET-20260930-GE-120h-3.md for the exact probe transcripts.

REACHABILITY FLOOR. GE-120h-3's own test_spec carries no entry with
    angle: reachability (its seven entries are angle: deployed / criterion /
    real_artifact / criterion / failure / seam / seam), so the ticket's own
    Test Requirements table adds one as the mandatory floor -- see this
    module's own docstring section below on
    ``TestReachabilityFloor`` for the entry-point resolution.
"""

from __future__ import annotations

import sys
import shutil
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_120h_3_fixture as fx  # noqa: E402

_NOTHING_TO_INSPECT_LINE = "RESULT: nothing_to_inspect"


# ---------------------------------------------------------------------------
# Arm 3 -- "it says that it had nothing to examine, rather than reporting
# that it examined something and found it clean"
# ---------------------------------------------------------------------------


class TestCheckSqlComplexityAnnouncesNothingToInspect(unittest.TestCase):
    def setUp(self) -> None:
        self.root = fx.fresh_repo_dir("ge120h3_sql_nti_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        fx.init_repo(self.root)

    def test_ge120h3_check_sql_complexity_reports_nothing_to_inspect_when_no_sql_staged(self):
        # covers: GE-120h-3
        # angle: criterion
        """A commit staging content with no .sql file gives
        check_sql_complexity.py nothing of its subject to examine. It must
        say so via check_outcome's shared vocabulary, not exit 0 silently
        the same way a genuine clean pass would.

        RED TODAY: check_sql_complexity.py's main() returns 0 with no
        output at all when no staged file ends in .sql (verified: `if not
        failed_files: ...; if passed_files_count > 0: print(...)` -- with
        passed_files_count staying 0, nothing prints).
        """
        (self.root / "unrelated.txt").write_text("nothing sql here\n", encoding="utf-8")
        fx.stage_all(self.root)

        result = fx.run_via_hook(fx.SQL_COMPLEXITY, self.root)
        combined = result.stdout + result.stderr

        self.assertEqual(
            0,
            result.returncode,
            msg=f"A nothing-to-inspect outcome must not itself block the commit. Got: {combined!r}",
        )
        self.assertIn(
            _NOTHING_TO_INSPECT_LINE,
            combined,
            msg=(
                "check_sql_complexity.py must announce "
                f"{_NOTHING_TO_INSPECT_LINE!r} when no .sql file is staged, "
                f"per GE-120a-1's shared vocabulary. Got: {combined!r}"
            ),
        )


class TestCheckDebugScriptsAnnouncesNothingToInspect(unittest.TestCase):
    def setUp(self) -> None:
        self.root = fx.fresh_repo_dir("ge120h3_debug_nti_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        fx.init_repo(self.root)

    def test_ge120h3_check_debug_scripts_reports_nothing_to_inspect_when_none_staged(self):
        # covers: GE-120h-3
        # angle: criterion
        """A commit staging content with nothing under debugging/scripts/
        gives check_debug_scripts.py nothing of its subject to examine. It
        must say so via check_outcome's shared vocabulary, not exit 0
        silently.

        RED TODAY: check_debug_scripts.py's main() returns 0 with no output
        at all when get_staged_debug_scripts() resolves empty (verified:
        `if not files_to_check: return 0`, no print reached).
        """
        (self.root / "unrelated.py").write_text("print('hi')\n", encoding="utf-8")
        fx.stage_all(self.root)

        result = fx.run_via_hook(fx.DEBUG_SCRIPTS, self.root)
        combined = result.stdout + result.stderr

        self.assertEqual(
            0,
            result.returncode,
            msg=f"A nothing-to-inspect outcome must not itself block the commit. Got: {combined!r}",
        )
        self.assertIn(
            _NOTHING_TO_INSPECT_LINE,
            combined,
            msg=(
                "check_debug_scripts.py must announce "
                f"{_NOTHING_TO_INSPECT_LINE!r} when nothing is staged under "
                f"debugging/scripts/, per GE-120a-1's shared vocabulary. Got: {combined!r}"
            ),
        )


# ---------------------------------------------------------------------------
# Reachability floor -- production entry point, per the Reachability
# Entry-Point Resolution procedure: check_debug_scripts.py is a CLI-style
# script with no argv of its own, dispatched through run_hook.py -- the
# wrapper every registered pre-commit hooks_manifest entry among the five
# delegates through (Step 1, bullet 1: "CLI script"; run_hook.py IS that
# entry point, not an internal helper import). Resolution answer recorded in
# this ticket's sign-off completion_manifest as reachability_entry_point_answer.
# ---------------------------------------------------------------------------


class TestReachabilityFloor(unittest.TestCase):
    def setUp(self) -> None:
        self.root = fx.fresh_repo_dir("ge120h3_reach_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        fx.init_repo(self.root)

    def test_ge_120h_3_reachable_from_entry_point(self):
        # covers: GE-120h-3
        # angle: reachability
        """Drives check_debug_scripts.py through the REAL production entry
        point (run_hook.py, a real subprocess against a real staged git
        repo -- never an import-and-call of validate_debug_script()) and
        asserts the result is CONSUMED in control flow: a non-zero exit and
        the named objection in the wrapper's own output stream, not merely
        a value some internal function happened to return.

        This is not RED for lack of a code path -- check_debug_scripts.py's
        validation logic already correctly refuses an untagged script, and
        arm 1 (5d0792d1 / PR #808) already registered it in
        hooks_manifest.hooks. It is included because GE-120h-3's own
        test_spec carries no angle: reachability entry, and the ticket's
        Test Requirements table adds this as a mandatory floor: importing
        validate_debug_script() and calling it directly would NOT prove
        anything about the registered commit path, which is exactly the
        anti-theatre question this whole AC exists to answer.
        """
        scripts_dir = self.root / "debugging" / "scripts" / "misc"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "untagged.py").write_text(
            fx.make_untagged_debug_script(), encoding="utf-8"
        )
        fx.stage_all(self.root)

        result = fx.run_via_hook(fx.DEBUG_SCRIPTS, self.root)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "The registered entry point must actually refuse an untagged "
                f"debug script, consumed as a non-zero exit. Got: {combined!r}"
            ),
        )
        self.assertIn(
            "untagged.py",
            combined,
            msg=f"The refusal must name the file it objected to. Got: {combined!r}",
        )


if __name__ == "__main__":
    unittest.main()
