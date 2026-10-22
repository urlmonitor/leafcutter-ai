"""
MODULE: unit_tests/build_orchestration/test_bo_4300a_1.py
AC: BO-4300a-1 -- "Every route that asks gets the same kind of workspace from
    the same maker."
TICKET: tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/
    01_TICKET-20260927-BO-4300a-1.md

WHAT THIS PROVES: One stdlib-only maker CLI (deployed at
`<install-root>/scripts/worktree.py`, source `templates/scripts/worktree.py`)
answers `ensure --kind K --slug S` identically in shape for every one of the
five routes named in the AC's Given clause (long-running build=kind epic,
quick fix=kind feature, requirements-authoring session=kind ac, an agent
following the workspace skill=kind fastlane, a person at a terminal=kind
scratch), and every resulting workspace is a real independent git clone,
carries the maker's own persisted marker record, has its own real install,
rejects a known-bad commit via a real hook, and lands under the project's one
landing place.

FILE SPLIT (2026-09-28, test-writer, re-dispatch off python-coder's
test_drift handoff): this module originally held BOTH the deployed-build
test class and the no-build seam test in one 539-line file, over the
`check_file_size.py` 400-line ratchet. Per python-coder's own remediation
recipe, the shared build-once `TestBO4300a1DeployedMaker` class (and its
nine `_MANUAL` tests) now live in the sibling module
`unit_tests/build_orchestration/test_bo_4300a_1_deployed.py`; this file keeps
only the `git ls-files` seam test (`TestBO4300a1Seam`, no deployed build
needed) plus this shared module docstring's AC-coverage note. Both files are
discovered independently by `unittest discover` / pytest (each is its own
`test_*.py`); this split changes no test's name, assertions, or `# covers:` /
`# angle:` tags -- see DECISION HISTORY below.

None of this exists yet -- `templates/scripts/worktree.py` and its resolver
module are not present anywhere in this repository (confirmed via
`git ls-files` in test_maker_and_resolver_have_no_tracked_copy_outside_
templates_scripts, which is itself one of the ten required tests, and lives
in THIS file). Every test across both files is expected to be RED until
python-coder builds the maker, its resolver module, and both deploy-manifest
entries.

AC COVERAGE (no `### test-writer` subsection and no `## AC Coverage` table
exist in this ticket body, so this ticket falls to the "global AC list"
branch of the AC Mapping Rule -- recorded here rather than in a
fabricated table):
    AC-1 (a workspace is requested once from each of the five routes):
        structural precondition of every test in test_bo_4300a_1_deployed.py
        via FIVE_ROUTES.
    AC-2 (every workspace carries the maker's own record, agreeing with the
        answer): test_every_route_workspace_carries_marker_agreeing_with_its_answer
        (test_bo_4300a_1_deployed.py)
    AC-3 (independent copy, started from S as read at request time, own
        install, protections fire, one landing place):
        test_every_route_workspace_is_independent_clone_rooted_at_fresh_hub_main,
        test_every_route_workspace_has_own_install_and_rejects_canary,
        test_every_route_workspace_lands_in_the_one_landing_place
        (all in test_bo_4300a_1_deployed.py)
    AC-4 (identical answer shape, stating ready and location):
        test_every_route_receives_answer_of_identical_shape
        (test_bo_4300a_1_deployed.py)
    AC-5 (no route lacks a property another route has):
        test_no_route_lacks_a_property_another_route_has
        (test_bo_4300a_1_deployed.py)

TEST-ANGLE NOTE ON THE SHARED DEPLOYED BUILD: `TestBO4300a1DeployedMaker`
(in the sibling module) builds the package's real deployed layout EXACTLY
ONCE in `setUpClass` (~60s, matching CLAUDE.md's own measured full-build
cost) and every test method in that class re-uses that one build. This is
the one new `scripts/build.py` spawn site this ticket's own Implementation
Notes justify ("A test that must mutate the package and build its own copy
says so and justifies it in its ticket" / "Proof runs the DEPLOYED maker...
resolved through the shared test locator delivered by BO-4300f-4" -- which
does not exist yet; see `_bo_4300a_1_fixtures.py`'s module docstring). Every
test method in that class is suffixed `_MANUAL` (this repo's
`manual_test_suffix` convention) because that shared ~60s setup makes the
file's tests exceed `testing_context.max_test_duration_seconds` (5s) by a
wide margin; test-writer still runs them directly (this phase's own
verification step, independent of automated-suite inclusion) to confirm the
required RED baseline.

`TestBO4300a1Seam` below is kept in a SEPARATE class (and, as of this split,
a separate FILE) specifically so the seam test (a plain `git ls-files`, no
deployed build needed) is not forced to pay that ~60s setup cost.

DECISION HISTORY
====================================================================
- 2026-09-27 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01,
  BO-4300a-1]: Initial single-file implementation (10 tests across two
  classes).
- 2026-09-28 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01,
  BO-4300a-1, re-dispatch off python-coder's test_drift handoff]: Split
  `TestBO4300a1DeployedMaker` out to test_bo_4300a_1_deployed.py (this file
  was 539 lines, over the 400-line ratchet). Also fixed
  `DeployedMakerBuild.maker_path`/`resolver_path` in
  `_bo_4300a_1_fixtures.py` to resolve through `.leafcutter/scripts/<name>`
  (scripts/build.py's own documented `output_root` default) instead of the
  stale `scripts/<name>` assumption -- classification: test_drift, no
  production code touched. Moved `_workspace_location`/`_marker_fields` into
  `_bo_4300a_1_fixtures.py` (as `workspace_location`/`marker_fields`) so
  both test files can share them without importing from each other.
====================================================================
"""
from __future__ import annotations

import unittest

from unit_tests.build_orchestration._bo_4300a_1_fixtures import (
    MAKER_NAME,
    REPO_ROOT,
    RESOLVER_MODULE_NAME,
    run_git,
)


class TestBO4300a1Seam(unittest.TestCase):
    """No deployed build needed -- a plain `git ls-files` against the real
    package repository. Kept in its own class (and its own file) so it never
    pays the shared ~60s setUpClass cost that TestBO4300a1DeployedMaker
    (test_bo_4300a_1_deployed.py) incurs."""

    def test_maker_and_resolver_have_no_tracked_copy_outside_templates_scripts(self):
        # covers: BO-4300a-1
        # angle: seam
        """NO SECOND TRACKED COPY (KI-TQ-004, this ticket's own note): `git
        ls-files` of the package repository must list the maker's and the
        resolver module's file names ONLY under templates/scripts/. Any
        tracked copy under scripts/ or elsewhere fails this test, naming the
        offending path.

        Today (before this AC is implemented) `templates/scripts/worktree.py`
        and `templates/scripts/workspace_root.py` do not exist at all, so
        this test's own presence assertion below is the RED signal -- not
        merely the absence-of-a-stray-copy check, which would trivially
        (and misleadingly) pass on a repo with neither file anywhere.
        """
        proc = run_git(["ls-files"], REPO_ROOT)
        tracked = proc.stdout.splitlines()

        for name in (MAKER_NAME, RESOLVER_MODULE_NAME):
            matches = [p for p in tracked if p.replace("\\", "/").endswith(f"/{name}") or p == name]
            expected = f"templates/scripts/{name}"
            self.assertIn(
                expected,
                matches,
                msg=(
                    f"{name} is not tracked at {expected} yet (found instead: {matches}) -- "
                    "expected RED state until python-coder delivers it there."
                ),
            )
            offenders = [p for p in matches if p != expected]
            self.assertEqual(
                offenders,
                [],
                msg=f"{name} has a second tracked copy outside templates/scripts/: {offenders}",
            )


if __name__ == "__main__":
    unittest.main()
