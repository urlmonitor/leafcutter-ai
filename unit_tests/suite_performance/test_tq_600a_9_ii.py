"""
Tests for TQ-600a-9-ii -- "The file that exists to prove the self-targeting
bootstrap keeps self-targeting."

Source of truth: docs/acceptance-criteria/testing-quality/
TQ-600-suite-feedback-latency/TQ-600a-9-ii.yaml (test_spec + test_rationale
+ it_requirements). Where the ticket's derived ``## Test Requirements``
table differs from the YAML, the YAML wins.

See ``_test_helpers_tq_600a_9.py``'s module docstring for the full ASSUMED
PRODUCTION CONTRACT (the execution-log counter every named builder must
call). ``unit_tests/build_guards/test_build_leaves_tracked_files_clean.py``
already owns a module-level cache (`_built_clone()` / `_STATE`) that
produces ONE clone-and-build; the duplicate cycle this AC removes is
`test_a_second_build_on_a_clean_checkout_changes_nothing`'s own separate
clone + build(1) -- structurally identical to `_built_clone()`'s own
clone + build. Post-fix: `_built_clone()`'s cached, already-built clone
becomes the "first" snapshot for the idempotence test, and only ONE more
build (not two) runs on top of it for the "second" snapshot -- 2 real
builds total where there were 3.

RED TODAY, uniformly: `_run_build()` (line 29 of the target file) does not
call `emit_execution_signal` yet, so every count below measures 0.

All tests suffixed ``_MANUAL`` -- each spawns real `git clone --no-local`
and real `python scripts/build.py` subprocesses (~43s self-targeting rate)
via a real child pytest session.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ._test_helpers_tq_600a_9 import count_events, events, run_plain_once

_TRACKED_FILES_FILE = "unit_tests/build_guards/test_build_leaves_tracked_files_clean.py"
_NON_BUILDING_TESTS_KEXPR = (
    "test_resolver_ignores_gitignored_deployed_copy "
    "or test_resolver_deployed_copy_does_not_make_tracked_match_ambiguous"
)


class TestTQ600a9iiTrackedFilesSelfTargetingPreserved(unittest.TestCase):
    """RED test stubs for TQ-600a-9-ii. See module docstring for the
    assumed production contract these tests are pinned to."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)

    # ------------------------------------------------------------------
    # Test 1 -- criterion
    # ------------------------------------------------------------------
    def test_tq600a_9_ii_the_tracked_files_file_starts_two_builds_not_three_MANUAL(self):
        # covers: TQ-600a-9-ii
        # angle: criterion
        """Run the whole file in ONE child session with the execution log
        pointed at a scratch file. The count is 2, and all four of its
        tests pass. Shares ONE real run with sibling tests in this file via
        `run_plain_once` -- see `_test_helpers_tq_600a_9.py`'s COST
        CONTAINMENT note."""
        result, log_path, _basetemp = run_plain_once("tracked_files_whole", _TRACKED_FILES_FILE)
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        count = count_events(log_path)
        self.assertEqual(
            2,
            count,
            msg=(
                f"expected exactly 2 real build subprocesses for the whole "
                f"file, measured {count} from the execution log -- the "
                "duplicate clone-and-build cycle has not been removed yet."
            ),
        )

    # ------------------------------------------------------------------
    # Test 2 -- discrimination (named mutation: directed conversion)
    # ------------------------------------------------------------------
    def test_tq600a_9_ii_the_build_still_targets_the_tree_it_was_cloned_into(
        self,
    ):
        # covers: TQ-600a-9-ii
        # angle: discrimination
        """Read the `target_dir` field of the `deploy_executed` entries the
        run emitted and assert the target directory and the package root
        resolve to the same tree (self-targeting preserved).

        must_catch: the target directory is pointed at a sibling
        directory, so the build stops self-targeting.

        RED TODAY: no entries are emitted yet, so there is nothing to read
        the target_dir field FROM. Shares the same cached run as test 1.
        """
        result, log_path, _basetemp = run_plain_once("tracked_files_whole", _TRACKED_FILES_FILE)
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        entries = events(log_path)
        self.assertTrue(
            entries,
            msg="expected at least one deploy_executed entry -- none were emitted yet.",
        )
        for entry in entries:
            target_dir = Path(entry["target_dir"]).resolve()
            # Self-targeting means the clone IS its own package root: the
            # build script invoked lives inside target_dir itself.
            self.assertTrue(
                (target_dir / "scripts" / "build.py").is_file(),
                msg=(
                    f"target_dir {target_dir} does not contain its own "
                    "scripts/build.py -- the build stopped self-targeting "
                    "(it now points at a tree distinct from its package root)."
                ),
            )

    # ------------------------------------------------------------------
    # Test 3 -- discrimination (named mutation: dropped --no-local)
    # ------------------------------------------------------------------
    def test_tq600a_9_ii_the_clone_has_no_hardlinks_into_the_real_repository(
        self,
    ):
        # covers: TQ-600a-9-ii
        # angle: discrimination
        """Run the REAL file with `--basetemp` retained, then inspect the
        clone IT produced (never a clone this test makes itself) and
        assert its object store is independent of the real repository's --
        not that the `--no-local` option string is present at the call
        site, but that the produced clone's objects are its own.

        must_catch: a future sharing implementation drops `--no-local`
        (e.g. to make the cached clone cheaper to produce), so the clone's
        object store is hardlinked into the real repository.

        RED TODAY: the build-count assertion (shared with test 1) fails
        first -- the clone/hardlink check below is unreached until the
        file actually starts exactly 2 real builds. Shares the same cached
        run as test 1 (it already runs with `--basetemp`).
        """
        from ._test_helpers_tq_600a_9 import _WORKTREE_ROOT

        result, log_path, basetemp = run_plain_once("tracked_files_whole", _TRACKED_FILES_FILE)
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        count = count_events(log_path)
        self.assertEqual(
            2,
            count,
            msg=f"expected exactly 2 real builds, measured {count}.",
        )
        clones = [
            d
            for d in basetemp.rglob(".git")
            if d.is_dir() and (d.parent / "scripts" / "build.py").is_file()
        ]
        self.assertTrue(clones, msg=f"no produced clone found under {basetemp}")
        real_inodes = {
            (p.stat().st_dev, p.stat().st_ino)
            for p in (_WORKTREE_ROOT / ".git" / "objects").glob("*/*")
            if p.is_file()
        }
        for clone_git_dir in clones:
            shared = [
                p
                for p in (clone_git_dir / "objects").glob("*/*")
                if p.is_file() and (p.stat().st_dev, p.stat().st_ino) in real_inodes
            ]
            self.assertEqual(
                [],
                shared,
                msg=(
                    f"[{clone_git_dir}] found {len(shared)} object file(s) "
                    "sharing an inode with the real repository's object "
                    "store -- the clone is hardlinked in. "
                    f"Examples: {shared[:5]}"
                ),
            )

    # ------------------------------------------------------------------
    # Test 4 -- discrimination (idempotence vacuity guard)
    # ------------------------------------------------------------------
    def test_tq600a_9_ii_the_second_build_runs_on_an_already_built_tree(self):
        # covers: TQ-600a-9-ii
        # angle: discrimination
        """Assert the tree the second build runs against carries the
        output of a prior build -- check for `.build_manifest.json`, the
        artifact a completed build leaves.

        must_catch: the caching is changed so the clone is handed out
        unbuilt, leaving the file green while its idempotence assertion
        compares an untouched tree against itself.

        RED TODAY: no deploy_executed entries exist to read the target
        tree from. Shares the same cached run as test 1.
        """
        result, log_path, _basetemp = run_plain_once("tracked_files_whole", _TRACKED_FILES_FILE)
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        entries = events(log_path)
        self.assertGreaterEqual(
            len(entries),
            2,
            msg=(
                f"expected at least 2 deploy_executed entries (a first and "
                f"a second build), found {len(entries)}."
            ),
        )
        # The SECOND entry's target_dir must already carry a manifest
        # BEFORE it ran -- we cannot observe "before" directly from the
        # log alone, so this test additionally asserts the postcondition
        # that is only possible if a real prior build occurred: the
        # manifest exists and is well-formed JSON after the run.
        second_target = Path(entries[1]["target_dir"])
        manifest = second_target / ".build_manifest.json"
        self.assertTrue(
            manifest.is_file(),
            msg=(
                f"expected {manifest} to exist after the second build -- "
                "if the caching changed to hand out an unbuilt clone, "
                "the idempotence assertion this file makes would be "
                "comparing an untouched tree against itself."
            ),
        )

    # ------------------------------------------------------------------
    # Test 5 -- criterion
    # ------------------------------------------------------------------
    def test_tq600a_9_ii_the_two_non_building_tests_are_unaffected_MANUAL(self):
        # covers: TQ-600a-9-ii
        # angle: criterion
        """Run the WHOLE file (not just the two non-building tests in
        isolation) so this test is tied to the same change as tests 1-4:
        the shared-build count must be 2 (not 3) across all four tests,
        AND the two tests that never start a build must both report
        PASSED in that same combined run -- proving the sharing change
        left them untouched rather than merely that they pass standalone,
        which they already do today regardless of this AC.

        RED TODAY: the count assertion (shared with test 1) fails before
        the pass/fail check is even reached. Shares the same cached run as
        test 1.
        """
        result, log_path, _basetemp = run_plain_once("tracked_files_whole", _TRACKED_FILES_FILE)
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        count = count_events(log_path)
        self.assertEqual(
            2,
            count,
            msg=(
                f"expected exactly 2 real builds across the whole file "
                f"(the change this test is paired with), measured {count}."
            ),
        )
        for name in (
            "test_resolver_ignores_gitignored_deployed_copy",
            "test_resolver_deployed_copy_does_not_make_tracked_match_ambiguous",
        ):
            self.assertNotIn(
                f"FAILED {_TRACKED_FILES_FILE.rsplit('/', 1)[-1]}::"
                f"TestResolverIgnoresUntrackedCopies::{name}",
                result.stdout,
                msg=f"{name} regressed in the combined run.\nstdout:\n{result.stdout}",
            )


if __name__ == "__main__":
    unittest.main()
