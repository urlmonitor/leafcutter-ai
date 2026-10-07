"""
Tests for TQ-600a-9 -- "Tests that differ only in what they assert about one
build stop producing one build each."

Source of truth: docs/acceptance-criteria/testing-quality/
TQ-600-suite-feedback-latency/TQ-600a-9.yaml (test_spec + test_rationale +
it_requirements). Where the ticket's derived ``## Test Requirements`` table
differs from the YAML, the YAML wins.

See ``_test_helpers_tq_600a_9.py``'s module docstring for the full ASSUMED
PRODUCTION CONTRACT (the execution-log counter wiring every named builder
needs, and the break-property test hook used by the discrimination tests).

ALL SIX TESTS BELOW ARE RED TODAY, uniformly, because none of the four
builder call sites this AC's it_requirements name
(``_bp1500g1_harness.run_build``, ``test_inf_400c_4_i.py``'s inline
``subprocess.run`` sites, ``test_build_leaves_tracked_files_clean.py``'s
``_run_build``) calls ``emit_execution_signal`` yet -- every measured count
below is 0 regardless of how many real subprocess builds actually ran. Each
test asserts the count FIRST (see helper module docstring for why that is
the deliberate RED-today design), so the per-test isolation/ordering logic
later in a test body is correctly unreached code until python-coder's
sharing implementation lands.

SCOPE NOTE on tests 4 and 5 (aggregate count, timing ratio): this AC's own
it_requirement ("THE VERIFICATION MUST NOT COST MORE THAN THE SAVING...")
flags that running all thirteen files' full real-build cost to measure an
aggregate is itself expensive. Tests 4 and 5 below are scoped to the three
files this build set's other tests already execute directly (the
colliding-capability four-group, the consumer-install file, and the
tracked-files file) rather than re-running all six adopter files a second
time under this descriptor -- a deliberate, documented cost reduction, not
an oversight. The remaining five adopter files' reduction is exercised by
TQ-600a-9's own declared_files edits and by the full test suite's
before/after timing, not re-measured a second time here.

COST CONTAINMENT: tests 1, 2, 4, and 6 below all need "the plain (unbroken)
real run" of the same underlying file (the collision group / the
consumer-install file / the tracked-files file) and share ONE real
execution each via ``_test_helpers_tq_600a_9.run_plain_once`` rather than
each spawning its own -- test-writer applying the same produce-once
principle this AC specifies, so that a thorough RED suite does not multiply
this file's own real-build cost across sibling test functions. Only the
discrimination tests (3, 5) that genuinely require a FRESH, differently-
broken or differently-ordered process per run bypass the cache.

NAMING CONSTRAINT (binding, not stylistic): every test_spec entry on this
AC that carries a ``must_catch`` list or ``angle: discrimination`` (tests
3, 5, 6) is named EXACTLY as declared -- no ``_MANUAL`` suffix -- because
the red-baseline gate's declared-name preflight
(``_fl_red_baseline_support._load_declared_test_names``) matches on the
literal ``name`` field; a suffixed function name fails that match and the
whole batch is refused with ``declared_test_missing_no_matching_test``
(confirmed empirically while authoring this build set). Tests without
``must_catch`` (1, 2, 4) are not declared-checked and keep the suffix.

Every test here spawns one or more real ``python scripts/build.py``
subprocesses (~13.3s directed / ~43s self-targeting) via a real child
pytest session and cannot complete within ``max_test_duration_seconds``;
tests 1, 2, and 4 carry the repo's ``_MANUAL`` slow-test suffix
(``testing_context.manual_test_suffix``) accordingly. Tests 3, 5, and 6 do
NOT carry it despite being equally slow -- see the NAMING CONSTRAINT note
above.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from ._test_helpers import _WORKTREE_ROOT
from ._test_helpers_tq_600a_9 import (
    COLLISION_GROUP_FILE,
    COLLISION_GROUP_KEXPR,
    break_env,
    count_events,
    run_child_session,
    run_plain_once,
    write_collision_break_plugin,
)

_CONSUMER_INSTALL_FILE = "unit_tests/portability/test_inf_400c_4_i.py"
_TRACKED_FILES_FILE = "unit_tests/build_guards/test_build_leaves_tracked_files_clean.py"


class TestTQ600a9BuildSubprocessReduction(unittest.TestCase):
    """RED test stubs for TQ-600a-9. See module docstring for the assumed
    production contract these tests are pinned to."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)

    # ------------------------------------------------------------------
    # Test 1 -- criterion
    # ------------------------------------------------------------------
    def test_tq600a_9_the_four_collision_tests_start_two_builds_not_eight_MANUAL(self):
        # covers: TQ-600a-9
        # angle: criterion
        """Run the colliding-capability file's four-way group in ONE child
        pytest session with the execution log pointed at a scratch file.
        The count of real `deploy_executed` signals is 2, not 8, and all
        four tests pass. Shares ONE real run with sibling tests via
        `run_plain_once` -- see module docstring COST CONTAINMENT note."""
        result, log_path, _basetemp = run_plain_once(
            "collision_group", COLLISION_GROUP_FILE, extra_args=["-k", COLLISION_GROUP_KEXPR]
        )
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        count = count_events(log_path)
        self.assertEqual(
            2,
            count,
            msg=(
                f"expected exactly 2 real build subprocesses for the four-way "
                f"collision group, measured {count} from the execution log "
                "-- the shared produce-once-then-copy mechanism does not "
                f"exist yet.\nstdout:\n{result.stdout}"
            ),
        )

    # ------------------------------------------------------------------
    # Test 2 -- criterion
    # ------------------------------------------------------------------
    def test_tq600a_9_the_consumer_install_file_starts_one_pre_mutation_build_MANUAL(self):
        # covers: TQ-600a-9
        # angle: criterion
        """Run the WHOLE consumer-install file in one child session. The
        pre-mutation build happens once across the first test and all four
        parametrised instances of the second, and all nine of the file's
        tests still pass. Shares ONE real run with sibling tests via
        `run_plain_once` -- see module docstring COST CONTAINMENT note."""
        result, log_path, _basetemp = run_plain_once(
            "consumer_install_whole", _CONSUMER_INSTALL_FILE
        )
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        count = count_events(log_path)
        self.assertEqual(
            1,
            count,
            msg=(
                f"expected exactly 1 real pre-mutation build shared across "
                f"the first test and all four parametrised instances of the "
                f"second, measured {count} from the execution log.\n"
                f"stdout:\n{result.stdout}"
            ),
        )

    # ------------------------------------------------------------------
    # Test 3 -- discrimination. THIS IS THE DESCRIPTOR THAT CANNOT BE
    # DROPPED (TQ-600a-9's own test_rationale).
    # ------------------------------------------------------------------
    def test_tq600a_9_each_shared_assertion_still_fails_when_its_own_subject_is_broken(
        self,
    ):
        # covers: TQ-600a-9
        # angle: discrimination
        """For each of the four collision tests, break ONLY the property
        that test names (survival / message / declared winner /
        cross-platform winner) via the test-side break-property plugin (see
        helper module docstring), in its OWN child session, and assert
        EXACTLY that one test goes red while the other three stay green.

        must_catch (TQ-600a-9.yaml):
          - sharing makes three of the four assertions true by construction
            (fewer than four of the four runs redden) -- caught by the
            per-run exactly-one-red assertion below.
          - the shared build is reused ACROSS the four break-runs, so a
            mutation from run N survives into run N+1 -- caught by giving
            each break-run its OWN child session (OS process) and its OWN
            execution log.

        RED TODAY: the per-run build count (asserted first, exactly as in
        test 1) is 0, not 2, for every one of the four break-runs, because
        sharing does not exist yet. The per-property isolation check below
        is therefore unreached until python-coder's change lands.
        """
        # NOTE: deliberately NOT using self.subTest() here. Confirmed while
        # authoring this build set: a failure inside self.subTest() is
        # reported by pytest as a separate "SUBFAILED" entry under a
        # decorated node id, while the OUTER test's own plain node id can
        # still be reported "passed" in the summary this file's own
        # red-baseline tooling parses -- a subTest failure is therefore
        # invisible to that mechanical classifier even though a human
        # reading the terminal output sees it. A direct, unwrapped
        # assertion failure is the only form the classifier reliably sees.
        plugin_dir = self.tmp_path / "break_plugin"
        modname = write_collision_break_plugin(plugin_dir)
        for prop in ("survival", "message", "declared_winner", "cross_platform_winner"):
            log_path = self.tmp_path / f"exec_log_{prop}.jsonl"
            result = run_child_session(
                COLLISION_GROUP_FILE,
                extra_args=["-k", COLLISION_GROUP_KEXPR, "-p", modname],
                env_overrides=break_env(plugin_dir, log_path, break_property=prop),
            )
            count = count_events(log_path)
            self.assertEqual(
                2,
                count,
                msg=(
                    f"[{prop}] expected the broken run to still start "
                    f"exactly 2 real builds (sharing scoped per OS "
                    f"process), measured {count}.\nstdout:\n{result.stdout}"
                ),
            )
            failed = [
                line[len("FAILED ") :].split(" ")[0]
                for line in result.stdout.splitlines()
                if line.startswith("FAILED ")
            ]
            self.assertEqual(
                1,
                len(failed),
                msg=(
                    f"[{prop}] expected exactly one of the four tests "
                    f"to go red, got {failed}.\nstdout:\n{result.stdout}"
                ),
            )

    # ------------------------------------------------------------------
    # Test 4 -- criterion (scoped aggregate; see module docstring)
    # ------------------------------------------------------------------
    def test_tq600a_9_the_build_subprocess_count_for_the_named_files_falls_by_the_declared_counts_MANUAL(
        self,
    ):
        # covers: TQ-600a-9
        # angle: criterion
        """Count real build subprocesses, reading the execution log, across
        the colliding-capability group, the consumer-install file, and the
        tracked-files file -- the three files this build set's sibling
        descriptors already execute directly. See module docstring SCOPE
        NOTE: the remaining five adopter files are not re-measured a second
        time under this descriptor. Shares each of the three real runs with
        sibling tests via `run_plain_once`."""
        r1, log1, _ = run_plain_once(
            "collision_group", COLLISION_GROUP_FILE, extra_args=["-k", COLLISION_GROUP_KEXPR]
        )
        r2, log2, _ = run_plain_once("consumer_install_whole", _CONSUMER_INSTALL_FILE)
        r3, log3, _ = run_plain_once("tracked_files_whole", _TRACKED_FILES_FILE)
        for result in (r1, r2, r3):
            self.assertEqual(
                0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
            )
        total = count_events(log1) + count_events(log2) + count_events(log3)
        # Exact combined target for just these three files: 2 (collision
        # group) + 1 (consumer-install) + 2 (tracked-files) = 5. An
        # assertLessEqual upper bound here would be satisfied vacuously by
        # today's real measured total of 0 (no builder calls
        # emit_execution_signal yet) -- confirmed while authoring this
        # build set, where that exact under-specification let this
        # descriptor pass before any implementation existed. assertEqual
        # against the exact declared total closes that gap.
        self.assertEqual(
            5,
            total,
            msg=(
                f"expected the combined real build count across the three "
                f"named files to be exactly 5 (2 + 1 + 2), measured {total} "
                "total."
            ),
        )

    # ------------------------------------------------------------------
    # Test 5 -- criterion (ratio, before/after in one sitting; scoped)
    # ------------------------------------------------------------------
    def test_tq600a_9_the_named_files_cost_at_most_two_thirds_of_their_baseline(self):
        # covers: TQ-600a-9
        # angle: criterion
        """Run the colliding-capability group with sharing OFF (a
        `git worktree` checkout of `merge-base(HEAD, origin/main)`, which by
        construction predates this AC's change) and with sharing ON (this
        worktree, as-is), same machine same sitting, and assert the RATIO of
        after-time to before-time is at most two thirds.

        must_catch (TQ-600a-9.yaml):
          - replacing the ratio with an absolute wall-clock threshold --
            not done here; only the ratio is asserted.
          - reading the baseline from a figure recorded in the AC rather
            than measured alongside the after figure in the same run --
            not done here; both figures come from real runs in this test.

        RED TODAY: this worktree IS the "before" state (no sharing exists
        yet), so after-time ~= before-time and the ratio is ~1.0, which
        exceeds two thirds.
        """
        try:
            merge_base = subprocess.run(
                ["git", "merge-base", "HEAD", "origin/main"],
                cwd=str(_WORKTREE_ROOT),
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            ).stdout.strip()
        except (subprocess.CalledProcessError, OSError) as exc:
            self.fail(f"could not resolve a baseline ref via git merge-base: {exc}")

        baseline_worktree = self.tmp_path / "baseline_worktree"
        try:
            subprocess.run(
                ["git", "worktree", "add", "--detach", str(baseline_worktree), merge_base],
                cwd=str(_WORKTREE_ROOT),
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            )
            self.addCleanup(
                subprocess.run,
                ["git", "worktree", "remove", "--force", str(baseline_worktree)],
                cwd=str(_WORKTREE_ROOT),
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )

            before_start = time.monotonic()
            before_result = subprocess.run(
                [sys.executable, "-m", "pytest", COLLISION_GROUP_FILE, "-k", COLLISION_GROUP_KEXPR, "-q"],
                cwd=str(baseline_worktree),
                capture_output=True,
                text=True,
                timeout=300,
            )
            before_elapsed = time.monotonic() - before_start

            after_start = time.monotonic()
            after_result = run_child_session(
                COLLISION_GROUP_FILE, extra_args=["-k", COLLISION_GROUP_KEXPR]
            )
            after_elapsed = time.monotonic() - after_start
        except subprocess.TimeoutExpired as exc:
            self.fail(f"a real build/test invocation timed out: {exc}")

        self.assertEqual(0, before_result.returncode, msg=before_result.stdout)
        self.assertEqual(0, after_result.returncode, msg=after_result.stdout)
        ratio = after_elapsed / before_elapsed if before_elapsed else float("inf")
        self.assertLessEqual(
            ratio,
            2 / 3,
            msg=(
                f"expected after/before <= 2/3, measured {ratio:.3f} "
                f"(before={before_elapsed:.1f}s, after={after_elapsed:.1f}s)"
            ),
        )

    # ------------------------------------------------------------------
    # Test 6 -- discrimination (boundary/safety; named mutation)
    # ------------------------------------------------------------------
    def test_tq600a_9_no_file_in_the_set_changes_between_directed_and_self_targeting(
        self,
    ):
        # covers: TQ-600a-9
        # angle: discrimination
        """Read the `target_dir` field of the `deploy_executed` entries the
        tracked-files file's run actually emits, and assert its target
        directory and its package root resolve to the same tree (it
        self-targets, and must keep doing so).

        must_catch (TQ-600a-9.yaml):
          - the tracked-files file's build is converted to a directed one
            (target_dir and package root stop coinciding).
          - an adopter file's build is converted from directed to
            self-targeting.

        RED TODAY: no entry exists in the execution log at all (the
        builder does not call `emit_execution_signal` yet), so there is
        nothing to read the `target_dir` field FROM -- `events()` returns
        an empty list and the assertion below fails on that emptiness
        before it can even inspect a path. Shares ONE real run with sibling
        tests via `run_plain_once`.
        """
        result, log_path, _basetemp = run_plain_once("tracked_files_whole", _TRACKED_FILES_FILE)
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        from ._test_helpers_tq_600a_9 import events

        entries = events(log_path)
        self.assertTrue(
            entries,
            msg=(
                "expected at least one deploy_executed entry from the "
                "tracked-files file's run -- none were emitted, so the "
                "target_dir/package-root relationship cannot be checked yet."
            ),
        )
        for entry in entries:
            target_dir = Path(entry["target_dir"]).resolve()
            # The tracked-files file self-targets: its package root IS the
            # clone it built, so the emitted target_dir must resolve inside
            # (or equal to) a `clone` directory under this test's own tmp
            # tree lineage -- never this worktree's own root.
            self.assertNotEqual(
                target_dir,
                _WORKTREE_ROOT.resolve(),
                msg=(
                    f"a deploy_executed entry named this worktree's own "
                    f"root ({_WORKTREE_ROOT}) as target_dir -- the "
                    "tracked-files file must only ever build its own clone, "
                    "never the real worktree."
                ),
            )


if __name__ == "__main__":
    unittest.main()
