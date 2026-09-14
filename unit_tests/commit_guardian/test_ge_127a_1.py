"""
MODULE: unit_tests/commit_guardian/test_ge_127a_1.py
COVERS: GE-127a-1 -- "The change that takes a file past its permitted length
    is refused at the moment it is committed"

GOAL: Close GE-127a-1's own recorded "OPEN COVERAGE GAP, RECORDED 2026-09-08":
    every descriptor below drives a REAL, ORDINARY `git commit` -- no extra
    command, no extra flag, and nothing invoked by hand -- through a real
    `pre-commit install`, against a `.pre-commit-config.yaml` that wires
    `check-file-size` ALONE (via `_ge_127a_1_ordinary_commit_fixture.py`,
    built on the same shape `test_ge_120g_1.py` already uses for a sibling
    AC). The prior version of this file invoked `pre-commit run
    check-file-size` by hand, which proves the hook behaves correctly once
    reached but never proves an ordinary commit reaches it at all -- exactly
    the clause GE-127a-1's own notes say is unexercised. See that AC's YAML
    for the full gap analysis.

WHY A MINIMAL-HOOK FIXTURE RATHER THAN THE REAL REPO. A full commit
    round-trip against this repo's own, real `.pre-commit-config.yaml` in a
    nested build target trips an unrelated `check-build-drift` failure that
    would hold every descriptor here permanently red for a cause that has
    nothing to do with file size (GE-127a-1's own notes name this exact
    obstacle and its fix). The fixture module copies the REAL
    `check_file_size.py` and every module it transitively needs (verified by
    running the hook, not by reading the import graph -- see that module's
    own docstring) into an isolated temp repo whose `.pre-commit-config.yaml`
    carries `check-file-size` and nothing else, so an ordinary commit there
    exercises this gate and only this gate.

NAMED MUTATIONS, EXECUTED. Two of the three behavioural descriptors below
    assert an ABSENCE (nothing reported for a compliant file; only the
    offender named) and both would be green on arrival against ANY
    implementation that reports nothing at all. Per GE-127a-1's test_spec and
    notes, each carries the BA's named injection, applied to the fixture's
    own on-disk copy of check_file_size.py and RUN -- not merely described --
    inside the same test method, asserting the descriptor goes RED under the
    injection and returns to GREEN on revert.

DECISION HISTORY
- 2026-09-07 [GE-127a-1/test-writer]: Initial authoring, all five descriptors
    invoking `pre-commit run check-file-size` by hand. Recorded as an open
    coverage gap in GE-127a-1's own notes on 2026-09-08.
- 2026-09-14 [GE-127a-1/test-writer]: Rewrote all five descriptors to drive a
    real ordinary `git commit` through a minimal single-hook fixture,
    executing (rather than merely describing) the BA's two named mutations.
    Fixture helpers factored into the sibling module
    `_ge_127a_1_ordinary_commit_fixture.py` to keep this file, and that one,
    each well under the 400-counted-line limit `check-file-size` itself now
    enforces on an ordinary commit.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127a_1_ordinary_commit_fixture as fx  # noqa: E402

_LINE_LIMIT = 5


class _MinimalFixtureTestCase(unittest.TestCase):
    """Shared scaffolding: a fresh, minimal, single-hook fixture repo."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        fx.build_minimal_fixture_repo(self.root, _LINE_LIMIT)
        fx.install_precommit(self.root)
        self.limit = fx.configured_limit(self.root)


class TestCrossingFileRefusesCommitNamingBothLengths(_MinimalFixtureTestCase):
    def test_ge_127a_1_a_change_taking_a_file_over_its_limit_refuses_the_commit_naming_both_lengths(self):
        # covers: GE-127a-1
        # covers: GE-127a
        # angle: criterion
        """A covered file below its permitted length, committed to HEAD, then
        staged so it now exceeds its permitted length, must be refused at a
        REAL ORDINARY `git commit` -- and the outcome must name the file, the
        length the standard measured it at, and the length permitted for its
        kind. All three are read from the real process output, never
        compared against a re-typed literal.
        """
        probe = self.root / "oversized_probe.py"
        probe.write_text(fx.content_lines(self.limit - 2), encoding="utf-8")
        fx.stage(self.root, ["oversized_probe.py"])
        baseline = fx.commit(self.root, "establish under-limit file")
        self.assertEqual(0, baseline.returncode, msg=f"baseline commit failed: {baseline.stdout}{baseline.stderr}")

        after = self.limit + 3
        probe.write_text(fx.content_lines(after), encoding="utf-8")
        fx.stage(self.root, ["oversized_probe.py"])

        result = fx.commit(self.root, "grow past the limit")
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "An ordinary commit that takes a covered file from under to "
                f"over its limit must be refused. Output: {combined!r}"
            ),
        )
        self.assertIn("oversized_probe.py", combined, msg=f"Outcome must name the file. Got: {combined!r}")
        self.assertIn(
            str(after),
            combined,
            msg=f"Outcome must state the length the standard measured ({after}). Got: {combined!r}",
        )
        self.assertIn(
            str(self.limit),
            combined,
            msg=f"Outcome must state the permitted length ({self.limit}). Got: {combined!r}",
        )


class TestUnderLimitFileProducesNoLengthOutput(_MinimalFixtureTestCase):
    def test_ge_127a_1_a_file_left_under_its_limit_produces_no_output_about_its_length(self):
        # covers: GE-127a-1
        # angle: criterion
        """A staged change leaving a covered file still below its permitted
        length must commit cleanly, through a REAL ordinary `git commit`, and
        produce no warning, no note, and no line naming that file.

        NAMED MUTATION (BA's injection 1), EXECUTED: after establishing the
        real, correct green result, the fixture's own on-disk copy of
        check_file_size.py is patched so a file AT OR BELOW its permitted
        length is refused alongside one above it. A second, still-under
        -limit growth is then attempted -- this MUST go red (a non-zero exit
        naming the file), because the injection can only turn the descriptor
        red if the gate genuinely runs at every ordinary commit. The mutation
        is then reverted and the same growth attempt MUST return to green.
        """
        probe = self.root / "small_probe.py"
        probe.write_text(fx.content_lines(self.limit - 3), encoding="utf-8")
        fx.stage(self.root, ["small_probe.py"])
        baseline = fx.commit(self.root, "establish under-limit file")
        self.assertEqual(0, baseline.returncode, msg=f"baseline commit failed: {baseline.stdout}{baseline.stderr}")

        probe.write_text(fx.content_lines(self.limit - 2), encoding="utf-8")
        fx.stage(self.root, ["small_probe.py"])
        result = fx.commit(self.root, "grow, still under limit")
        combined = result.stdout + result.stderr

        self.assertEqual(
            0,
            result.returncode,
            msg=f"A commit leaving a covered file under its limit must complete cleanly. Output: {combined!r}",
        )
        self.assertNotIn(
            "small_probe.py",
            combined,
            msg=f"An under-limit file must not be named anywhere in the output. Got: {combined!r}",
        )

        # --- NAMED MUTATION (BA's injection 1), executed and reverted ---
        original = fx.apply_mutation_refuse_regardless_of_length(self.root)
        probe.write_text(fx.content_lines(self.limit - 1), encoding="utf-8")
        fx.stage(self.root, ["small_probe.py"])
        mutated_result = fx.commit(self.root, "grow again, still under limit, under mutation")
        mutated_combined = mutated_result.stdout + mutated_result.stderr

        self.assertNotEqual(
            0,
            mutated_result.returncode,
            msg=(
                "Under the injection, a still-under-limit commit must now be "
                f"refused -- this descriptor is under-specified if it is not. "
                f"Output: {mutated_combined!r}"
            ),
        )
        self.assertIn(
            "small_probe.py",
            mutated_combined,
            msg=f"Under the injection, the file must be named. Got: {mutated_combined!r}",
        )

        fx.restore_check_file_size(self.root, original)
        reverted_result = fx.commit(self.root, "grow again, still under limit, after revert")
        reverted_combined = reverted_result.stdout + reverted_result.stderr

        self.assertEqual(
            0,
            reverted_result.returncode,
            msg=f"After reverting the injection, the commit must complete cleanly again. Output: {reverted_combined!r}",
        )
        self.assertNotIn(
            "small_probe.py",
            reverted_combined,
            msg=f"After revert, the file must not be named. Got: {reverted_combined!r}",
        )


class TestOnlyOverLimitFileIsNamedAlongsideCompliantFile(_MinimalFixtureTestCase):
    def test_ge_127a_1_only_the_over_limit_file_is_named_when_a_compliant_file_is_in_the_same_commit(self):
        # covers: GE-127a-1
        # angle: seam
        """A REAL ordinary commit staging one over-limit covered file and one
        comfortably compliant covered file must be refused, and the reported
        offender must be the first file only -- the compliant file's
        presence neither excuses the offender nor is itself reported.

        NAMED MUTATION (BA's injection 2), EXECUTED: after establishing the
        real, correct refusal-names-only-the-offender result, the fixture's
        own on-disk copy of check_file_size.py is patched to include EVERY
        staged covered file in the reported set regardless of its measured
        length. Naming the compliant file too MUST now happen -- this MUST
        go red -- and revert MUST return the descriptor to green.
        """
        offender = self.root / "big_probe.py"
        compliant = self.root / "small_probe.py"
        offender.write_text(fx.content_lines(self.limit - 2), encoding="utf-8")
        compliant.write_text(fx.content_lines(self.limit - 2), encoding="utf-8")
        fx.stage(self.root, ["big_probe.py", "small_probe.py"])
        baseline = fx.commit(self.root, "establish two under-limit files")
        self.assertEqual(0, baseline.returncode, msg=f"baseline commit failed: {baseline.stdout}{baseline.stderr}")

        offender.write_text(fx.content_lines(self.limit + 3), encoding="utf-8")
        compliant.write_text(fx.content_lines(self.limit - 1), encoding="utf-8")
        fx.stage(self.root, ["big_probe.py", "small_probe.py"])

        result = fx.commit(self.root, "one offender, one compliant")
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=f"A commit with one over-limit covered file must be refused. Output: {combined!r}",
        )
        self.assertIn("big_probe.py", combined, msg=f"The offender must be named. Got: {combined!r}")
        # A passing commit prints nothing (verified separately in the
        # silence-arm descriptor); a REFUSED commit's own PASSED section is
        # informational, not a reported problem -- so only the portion
        # BEFORE it is checked for the compliant file's name.
        failure_section = combined.split("PASSED", 1)[0] if "PASSED" in combined else combined
        self.assertNotIn(
            "small_probe.py",
            failure_section,
            msg=f"The compliant file must not be reported as a problem. Got: {combined!r}",
        )

        # --- NAMED MUTATION (BA's injection 2), executed and reverted ---
        original = fx.apply_mutation_report_all_staged_as_offenders(self.root)
        offender.write_text(fx.content_lines(self.limit + 4), encoding="utf-8")
        compliant.write_text(fx.content_lines(self.limit - 3), encoding="utf-8")
        fx.stage(self.root, ["big_probe.py", "small_probe.py"])
        mutated_result = fx.commit(self.root, "one offender, one compliant, under mutation")
        mutated_combined = mutated_result.stdout + mutated_result.stderr

        self.assertIn(
            "small_probe.py",
            mutated_combined,
            msg=(
                "Under the injection, the compliant file must now ALSO be "
                f"named -- this descriptor is under-specified if it is not. "
                f"Output: {mutated_combined!r}"
            ),
        )

        fx.restore_check_file_size(self.root, original)
        offender.write_text(fx.content_lines(self.limit + 5), encoding="utf-8")
        compliant.write_text(fx.content_lines(self.limit - 1), encoding="utf-8")
        fx.stage(self.root, ["big_probe.py", "small_probe.py"])
        reverted_result = fx.commit(self.root, "one offender, one compliant, after revert")
        reverted_combined = reverted_result.stdout + reverted_result.stderr

        self.assertIn("big_probe.py", reverted_combined, msg=f"After revert, the offender must still be named. Got: {reverted_combined!r}")
        reverted_failure_section = (
            reverted_combined.split("PASSED", 1)[0] if "PASSED" in reverted_combined else reverted_combined
        )
        self.assertNotIn(
            "small_probe.py",
            reverted_failure_section,
            msg=f"After revert, the compliant file must again not be reported as a problem. Got: {reverted_combined!r}",
        )


class TestRefusalReachesRegisteredHookEntryPoint(_MinimalFixtureTestCase):
    def test_ge_127a_1_the_refusal_is_emitted_through_the_registered_hook_entry_point(self):
        # covers: GE-127a-1
        # angle: reachability
        """PRODUCTION ENTRY POINT, PROVED BY CONTRAST. The same crossing
        scenario is run two ways: (a) invoking the fixture's copy of
        check_file_size.py DIRECTLY, bypassing run_hook.py and pre-commit
        entirely, and (b) through a REAL ordinary `git commit`, which
        dispatches via the installed pre-commit hook -> run_hook.py ->
        check_file_size.py. A verdict only (a) can produce is inert at an
        ordinary commit -- the defect this whole record exists to close --
        so (b) is the descriptor's primary assertion; (a) is fixture sanity
        only.
        """
        probe = self.root / "oversized_probe.py"
        probe.write_text(fx.content_lines(self.limit - 2), encoding="utf-8")
        fx.stage(self.root, ["oversized_probe.py"])
        baseline = fx.commit(self.root, "establish under-limit file")
        self.assertEqual(0, baseline.returncode, msg=f"baseline commit failed: {baseline.stdout}{baseline.stderr}")

        after = self.limit + 3
        probe.write_text(fx.content_lines(after), encoding="utf-8")
        fx.stage(self.root, ["oversized_probe.py"])

        direct = fx.run([fx.PYTHON, str(fx.check_file_size_path(self.root))], self.root)
        self.assertNotEqual(
            0,
            direct.returncode,
            msg=(
                "Fixture sanity: the direct invocation must already refuse "
                f"this crossing case. Got: stdout={direct.stdout!r} stderr={direct.stderr!r}"
            ),
        )

        result = fx.commit(self.root, "grow past the limit")
        combined = result.stdout + result.stderr
        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "The SAME crossing case must ALSO be refused by a REAL "
                f"ordinary commit through the registered hook path. Output: {combined!r}"
            ),
        )
        self.assertIn(
            "oversized_probe.py",
            combined,
            msg=f"The registered hook path's own output must name the file. Got: {combined!r}",
        )


class TestDeployedCopyRefusesCrossingCommitInColdProcess(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        fx.build_deployed_fixture_repo(self.root)
        fx.install_precommit(self.root)
        self.limit = fx.configured_limit(self.root)

    def test_ge_127a_1_the_deployed_copy_refuses_the_crossing_commit_in_a_cold_process(self):
        # covers: GE-127a-1
        # angle: deployed
        """After a REAL `build.py` deploy into a fresh temp dir, in a cold
        process, a REAL ordinary `git commit` against the DEPLOYED copy of
        the gate (and every module it imports) must refuse a crossing
        commit. A helper placed outside templates/scripts/commit_guardian/
        without a scripts/build_phases.py deploy-map entry would surface here
        as ModuleNotFoundError rather than passing -- source-tree greenness
        cannot substitute.
        """
        deployed_check = fx.check_file_size_path(self.root)
        self.assertTrue(deployed_check.exists(), msg=f"{deployed_check} was not deployed by build.py.")

        probe = self.root / "oversized_probe.py"
        probe.write_text(fx.content_lines(self.limit - 50), encoding="utf-8")
        fx.stage(self.root, ["oversized_probe.py"])
        baseline = fx.commit(self.root, "establish under-limit file")
        self.assertEqual(0, baseline.returncode, msg=f"baseline commit failed: {baseline.stdout}{baseline.stderr}")

        after = self.limit + 50
        probe.write_text(fx.content_lines(after), encoding="utf-8")
        fx.stage(self.root, ["oversized_probe.py"])

        result = fx.commit(self.root, "grow past the limit, deployed copy")
        combined = result.stdout + result.stderr

        self.assertNotIn(
            "ModuleNotFoundError",
            combined,
            msg=f"Deployed check-file-size crashed importing a dependency. Got: {combined!r}",
        )
        self.assertNotEqual(
            0,
            result.returncode,
            msg=f"The deployed, cold-process copy must refuse a crossing commit. Output: {combined!r}",
        )
        self.assertIn("oversized_probe.py", combined, msg=f"Outcome must name the file. Got: {combined!r}")


if __name__ == "__main__":
    unittest.main()
