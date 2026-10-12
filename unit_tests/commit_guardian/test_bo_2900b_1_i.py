"""
MODULE: unit_tests/commit_guardian/test_bo_2900b_1_i.py
COVERS: BO-2900b-1-i

GOAL: Behavioral tests for "A capability introduced together with its caller
passes; one introduced alone is refused with both ways forward named" -- the
adoption-trap AC layered on top of BO-2900b-1's forward reachability guard.

AC MAPPING (ticket's global AC-1..AC-4 checklist -- this ticket's
`## Agent Contracts` section carries no `### test-writer` subsection, so the
global list is the authoritative mapping per the contract-aware mode rule):
  - AC-1 ("`verify` is not reported and the change is not refused") ->
    TestSameChangeAdoptionPasses::test_capability_and_caller_added_in_the_same_change_pass
  - AC-2 ("`verify` is reported and the change is refused") ->
    TestCapabilityIntroducedAloneIsRefusedAndNamesBothWaysForward::
    test_capability_added_alone_is_refused_and_names_both_ways_forward
  - AC-3 ("the report names both ways forward") -> same test as AC-2 (the
    Gherkin's second Then-clause is one compound assertion; the fixture and
    assertions cannot be usefully separated across two tests) and echoed in
    TestReachableFromEntryPoint (real subprocess evidence of the same
    ways-forward text)
  - AC-4 ("the report does not suggest disabling the check") ->
    TestRefusalNeverOffersDisablingTheCheck::
    test_refusal_text_never_offers_disabling_the_check

CURRENT STATE (2026-09-25, test-writer): scripts/commit_guardian/
check_reachability.py already exists in this worktree and already carries
the exact `_WAYS_FORWARD` tuple this AC's config_schema_fragment pins
("add the automation invocation in this change" /
"record an exemption for the capability with a stated reason") -- confirmed
directly by reading the file before writing these tests, and consistent with
architect-review's own SMALL classification on this ticket ("no new code
path... constrains content and asserts the already-implemented passing
case"). These tests SHOULD therefore already be green against the deployed
check_reachability.py; they exist to pin that behaviour down as this AC's own
contract (in case scripts/commit_guardian/commit_guardian.json or the
canonical templates/ source drift from it) rather than to drive brand-new
production code. If any of these fail, do not weaken the assertion to match
a drifted implementation without re-reading this AC's constraints first
(Source-of-Truth Discipline Rule 1: classify the failure before touching
anything).

ENTRY POINT: tests 1-3 call check_reachability.main([...]) directly, per this
AC's own test_spec verbatim ("Runs check_reachability.main() over a fixture
tree..."). Test 4 is the REQUIRED reachability test and invokes the SAME CLI
as a genuine subprocess, mirroring test_bo_2900b_1.py's own required
reachability test and check_done_proof.py's CI registration precedent.

FIXTURES: every scenario targets a FIXTURE command surface (a real, on-disk,
importable .py file, built via a real `build_parser()` callable -- never a
hand-typed in-memory literal) registering `claim` and `verify`. See
_bo_2900b_1_i_fixtures.py's module docstring for the full fixture shape and
the adoption-trap pairing (same surface, two automation fixtures: one calls
both claim and verify -- the same-change adoption case -- the other calls
only claim, leaving verify uncalled -- the refusing case).

WHY THE POSITIVE SCENARIO IS FIRST (per this AC's own test_rationale): an
implementation that refuses both cases still satisfies a negative-only test
suite. Test 1 below is the passing case, asserted first.

CROSS-LAYER SEAM (test-writer skill Rule 3, BP-1100g-5): the unit under test
sits at the same script -> hook boundary BO-2900b-1's own tests already
established. This AC adds no new seam of its own (no new refusal cause, no
second code path); test 1 and test 4 below still pipe a REAL, unmocked
fixture surface's REAL built parser into the REAL consumer, no mocking on
either side.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo_2900b_1_fixtures import (  # noqa: E402
    fixture_tmp_dir,
    run_check_reachability,
)
from _bo_2900b_1_i_fixtures import (  # noqa: E402
    write_fixture_automation_calls_claim_and_verify,
    write_fixture_automation_calls_claim_only,
    write_fixture_surface_with_verify,
)

try:
    import scripts.commit_guardian.check_reachability as check_reachability  # type: ignore[import]
    _IMPORT_OK = True
except (ImportError, ModuleNotFoundError):
    check_reachability = None  # type: ignore[assignment]
    _IMPORT_OK = False


def _call_main(argv: list[str]) -> tuple[int, str, str]:
    """Call check_reachability.main(argv) directly, capturing stdout/stderr.

    Args:
        argv: Argument list, exactly as a real CLI invocation would receive.

    Returns:
        (return_code, stdout_text, stderr_text).
    """
    import contextlib
    import io

    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = check_reachability.main(argv)
    return rc, out.getvalue(), err.getvalue()


class TestSameChangeAdoptionPasses(unittest.TestCase):
    """The positive Gherkin scenario: `verify` registered AND invoked by
    automation in the same working-tree state must be silent and passing."""

    def test_capability_and_caller_added_in_the_same_change_pass(self) -> None:
        # covers: BO-2900b-1-i
        # angle: criterion
        """A fixture surface registering claim and verify, with a fixture
        automation script invoking BOTH in the same working-tree state, must
        produce zero findings and a zero exit code -- the same-change
        adoption path must genuinely pass (this AC's own constraint: the
        check evaluates WORKING-TREE state, not committed state)."""
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import "
                "scripts.commit_guardian.check_reachability. This module is "
                "expected to already exist per BO-2900b-1; if it is missing "
                "here, python-coder must (re)implement "
                "scripts/commit_guardian/check_reachability.py with a "
                "main(argv) entry point."
            )
        with fixture_tmp_dir() as tmp:
            src_dir = tmp / "src"
            automation_dir = tmp / "automation"
            surface_path = write_fixture_surface_with_verify(src_dir)
            automation_path = write_fixture_automation_calls_claim_and_verify(
                automation_dir
            )

            rc, out, err = _call_main(
                [
                    "--mode",
                    "precommit",
                    "--surface",
                    f"{surface_path}:build_parser",
                    "--automation",
                    str(automation_path),
                ]
            )
            combined = out + err

        self.assertEqual(
            rc,
            0,
            msg=(
                "a capability introduced together with its caller in the "
                f"same change must NOT be refused. Got rc={rc}\ncombined "
                f"output:\n{combined}"
            ),
        )
        self.assertNotIn(
            "uncalled_capability",
            combined,
            msg=(
                "no uncalled_capability finding may be emitted when both "
                f"claim and verify are invoked by automation:\n{combined}"
            ),
        )


class TestCapabilityIntroducedAloneIsRefusedAndNamesBothWaysForward(
    unittest.TestCase
):
    """The negative Gherkin scenario: `verify` registered with no automation
    invocation must be refused, and the refusal must name both ways
    forward."""

    def test_capability_added_alone_is_refused_and_names_both_ways_forward(
        self,
    ) -> None:
        # covers: BO-2900b-1-i
        # angle: failure
        """Same fixture surface (claim, verify), but the automation fixture
        invokes only claim -- verify lands with no caller. The run must
        refuse (non-zero exit), name the uncalled capability, and name BOTH
        ways forward from this AC's own config_schema_fragment: adding the
        automation invocation in this change, and recording an exemption
        with a stated reason. No third way forward may appear."""
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import "
                "scripts.commit_guardian.check_reachability. This module is "
                "expected to already exist per BO-2900b-1; if it is missing "
                "here, python-coder must (re)implement "
                "scripts/commit_guardian/check_reachability.py first."
            )
        with fixture_tmp_dir() as tmp:
            src_dir = tmp / "src"
            automation_dir = tmp / "automation"
            surface_path = write_fixture_surface_with_verify(src_dir)
            automation_path = write_fixture_automation_calls_claim_only(
                automation_dir
            )

            rc, out, err = _call_main(
                [
                    "--mode",
                    "precommit",
                    "--surface",
                    f"{surface_path}:build_parser",
                    "--automation",
                    str(automation_path),
                ]
            )
            combined = out + err

        self.assertNotEqual(
            rc,
            0,
            msg=(
                "a capability introduced alone, with no automation "
                f"invocation, must refuse the change. Got rc={rc}\ncombined "
                f"output:\n{combined}"
            ),
        )
        self.assertIn(
            "verify",
            combined,
            msg=f"the refusal must name the uncalled capability ('verify'):\n{combined}",
        )
        self.assertIn(
            "add the automation invocation in this change",
            combined,
            msg=(
                "the refusal must name the first way forward verbatim (this "
                f"AC's own config_schema_fragment):\n{combined}"
            ),
        )
        self.assertIn(
            "record an exemption",
            combined,
            msg=(
                "the refusal must name the second way forward (recording an "
                f"exemption with a stated reason):\n{combined}"
            ),
        )
        self.assertIn(
            "stated reason",
            combined,
            msg=(
                "the exemption way-forward must mention a STATED reason, "
                f"not a bare 'record an exemption':\n{combined}"
            ),
        )


class TestRefusalNeverOffersDisablingTheCheck(unittest.TestCase):
    """The blocking gate must never document its own off switch, even while
    naming the two sanctioned ways forward."""

    def test_refusal_text_never_offers_disabling_the_check(self) -> None:
        # covers: BO-2900b-1-i
        # angle: failure
        """The text emitted on a refusing run for the alone-introduced
        `verify` capability must contain no 'SKIP=', no '--no-verify', and
        no environment-variable bypass assignment (e.g. 'ENV_VAR=1'/'=true')
        -- printing the bypass at the moment of maximum frustration converts
        a blocking gate into an advisory one (this AC's own constraint)."""
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import "
                "scripts.commit_guardian.check_reachability. This module is "
                "expected to already exist per BO-2900b-1; if it is missing "
                "here, python-coder must (re)implement "
                "scripts/commit_guardian/check_reachability.py first."
            )
        with fixture_tmp_dir() as tmp:
            src_dir = tmp / "src"
            automation_dir = tmp / "automation"
            surface_path = write_fixture_surface_with_verify(src_dir)
            automation_path = write_fixture_automation_calls_claim_only(
                automation_dir
            )

            rc, out, err = _call_main(
                [
                    "--mode",
                    "precommit",
                    "--surface",
                    f"{surface_path}:build_parser",
                    "--automation",
                    str(automation_path),
                ]
            )
            combined = out + err

        self.assertNotEqual(
            rc,
            0,
            msg=f"expected a refusing run to assert against. Got rc={rc}\n{combined}",
        )
        self.assertNotIn(
            "SKIP=",
            combined,
            msg=f"the refusal must never name its own skip mechanism:\n{combined}",
        )
        self.assertNotIn(
            "--no-verify",
            combined,
            msg=f"the refusal must never name its own bypass flag:\n{combined}",
        )
        env_var_bypass = re.search(r"\b[A-Z][A-Z0-9_]{2,}=(1|true|True)\b", combined)
        self.assertIsNone(
            env_var_bypass,
            msg=(
                "the refusal must never name an environment-variable bypass "
                f"assignment, found {env_var_bypass and env_var_bypass.group(0)!r} "
                f"in:\n{combined}"
            ),
        )


class TestReachableFromEntryPoint(unittest.TestCase):
    """REQUIRED reachability test: the real deployed CLI, invoked as a
    genuine subprocess (never main() imported and called directly), must
    exhibit the same adoption-trap refusal behaviour end to end."""

    def test_bo_2900b_1_i_reachable_from_entry_point(self) -> None:
        # covers: BO-2900b-1-i
        # angle: reachability
        """Invokes the REAL deployed
        scripts/commit_guardian/check_reachability.py CLI via subprocess
        (mirroring test_bo_2900b_1.py's own required reachability test and
        check_done_proof.py's CI registration precedent) over the
        alone-introduced-verify fixture, and asserts the refusal actually
        occurs through the real entry point -- not merely that main()
        behaves correctly when imported and called directly."""
        with fixture_tmp_dir() as tmp:
            src_dir = tmp / "src"
            automation_dir = tmp / "automation"
            surface_path = write_fixture_surface_with_verify(src_dir)
            automation_path = write_fixture_automation_calls_claim_only(
                automation_dir
            )

            result = run_check_reachability(
                mode="precommit",
                surfaces=[f"{surface_path}:build_parser"],
                automation_scripts=[str(automation_path)],
            )
            combined = result.stdout + result.stderr

        self.assertNotEqual(
            result.returncode,
            0,
            msg=(
                "the real deployed CLI, invoked as a genuine subprocess, "
                "must refuse (non-zero exit) when 'verify' is introduced "
                f"with no automation caller. Got "
                f"returncode={result.returncode}\nstdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            ),
        )
        self.assertIn(
            "verify",
            combined,
            msg=(
                "the subprocess-invoked CLI's refusal must name the "
                f"uncalled capability ('verify'):\n{combined}"
            ),
        )
        self.assertIn(
            "add the automation invocation in this change",
            combined,
            msg=(
                "the subprocess-invoked CLI's refusal must name the first "
                f"way forward:\n{combined}"
            ),
        )
        self.assertIn(
            "record an exemption",
            combined,
            msg=(
                "the subprocess-invoked CLI's refusal must name the second "
                f"way forward:\n{combined}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
