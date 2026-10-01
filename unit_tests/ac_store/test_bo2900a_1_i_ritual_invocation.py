"""
MODULE: unit_tests/ac_store/test_bo2900a_1_i_ritual_invocation.py
COVERS: BO-2900a-1-i

GOAL: The ritual/honest/direct-import adversarial fixture pair BO-2900a-1-i's
    own test_spec asked for (entry 3,
    ``test_unrelated_extra_invocation_does_not_launder_a_direct_import_proof``)
    but that was never written before the record was flipped to
    ``work_status: done``.
BUSINESS CONTEXT: ``_apply_entry_point_reachability_gate`` (BO-2900a-1, in
    scripts/ac_store/_done_proof_entry_point_gate.py) backs the REQUIRED
    Proof-of-done CI gate. It calls ``_observe_reachability`` with an EMPTY
    ``target_spec`` and then branches on ``entered_entry_point`` alone
    (never ``reached_through``, which is structurally always False on that
    call). Consequence: a proof that calls ``main()`` once for an unrelated
    action and then reaches the code under proof by a completely separate
    direct call is ACCEPTED, while an ordinary direct-import proof of the
    exact same unit is REFUSED -- the exact ritual-invocation trap
    BO-2900a-1-i's own DECISION HISTORY entry (done_proof.py, 2026-09-07)
    names by description.
ARCHITECTURE: Same single-file fixture convention as the sibling
    unit_tests/ac_store/test_bo_2900a_1.py: the implementing function,
    ``main``, and the covers-tagged proof test all live in one real,
    importable ``.py`` fixture file written fresh per test into a
    ``tempfile.TemporaryDirectory()``, and the REAL, unmodified
    ``verify_done_eligible`` (which internally calls the real
    ``_apply_entry_point_reachability_gate``) is invoked against it -- never
    a hand-fed boolean. All three cases share the exact same fixture-unit
    shape (an argparse ``main(argv)`` with a ``report`` action that does NOT
    reach the code under proof and a ``mark-done`` action that DOES), so the
    only variable across the three test methods is how the proof test
    itself calls into that unit. The shared unit body and each per-case
    proof-test block are both flush-left module-level string constants so
    that ``write_fixture_file``'s ``textwrap.dedent`` call (computed over
    the concatenation of the two) is a no-op instead of being defeated by a
    mismatched common-indentation prefix between the two pieces.

    Asserted in one test run (three test methods in one module) so neither
    a reject-everything nor an accept-everything gate implementation can
    pass all three: an accept-everything gate fails RitualCase and
    DirectImportCase; a reject-everything gate fails HonestCase.

=== Red baseline ===

    RitualCase is expected to FAIL against today's
    ``_apply_entry_point_reachability_gate`` -- that is the defect this file
    documents executably. BO-2900a-1-i is ``work_status: todo`` (corrected
    from a false ``done`` in the same change that added this file), so
    ``scripts.ac_store.pytest_ac_enforcement`` downgrades that failure to
    XFAIL rather than a hard CI break. Run with ``AC_ENFORCE_STRICT=1`` to
    see the real (non-masked) assertion failure.
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo_2900a_1_fixtures import write_ac, write_fixture_file  # noqa: E402

from done_proof import verify_done_eligible  # noqa: E402


def _gate_findings(ac_id: str, ac_root: Path, test_root: Path) -> tuple[dict, list[str]]:
    """Run the real gate and return its verdict plus any reachability findings.

    These tests assert on whether the rule FLAGGED the proof, not on
    ``eligible``. The entry-point rule was suspended to report-only on
    2026-09-30 (see _done_proof_entry_point_gate's DECISION HISTORY), so
    eligibility no longer separates the three cases -- every one of them is
    now eligible. Whether a finding was emitted still separates them, and it
    is the same boolean the rule would refuse on once re-armed, so these
    assertions are correct in BOTH states and need no edit when it is.

    Args:
        ac_id: Fixture AC to evaluate.
        ac_root: Fixture AC store root.
        test_root: Fixture test tree root.

    Returns:
        ``(verdict, findings)`` -- findings is the list of report-only
        reachability lines the rule wrote to stderr during the run.
    """
    buffer = io.StringIO()
    with contextlib.redirect_stderr(buffer):
        verdict = verify_done_eligible(ac_id, ac_root=ac_root, test_root=test_root)
    findings = [
        line
        for line in buffer.getvalue().splitlines()
        if "REPORT-ONLY reachability finding" in line
    ]
    return verdict, findings


#: Shared fixture-unit body reused verbatim across all three cases below --
#: a genuine argparse main(argv) with a "report" action that never reaches
#: the code under proof and a "mark-done" action that does. Flush-left
#: (zero indentation) so concatenating it with a per-case test-body constant
#: below leaves textwrap.dedent's common-prefix computation at zero, i.e.
#: a no-op, rather than defeated by mismatched indentation between pieces.
_SHARED_UNIT_BODY = """\
import argparse


def mark_the_criterion_done():
    # The implementing code under proof -- the mark-done handler.
    return "done"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fixture-unit")
    parser.add_argument("action", choices=["report", "mark-done"])
    args = parser.parse_args(argv)
    if args.action == "mark-done":
        return mark_the_criterion_done()
    return "reported"

"""

#: RITUAL proof: calls main() for the unrelated "report" action (whose
#: handler never reaches mark_the_criterion_done), then separately calls
#: the code under proof directly -- entering the way in without reaching
#: the target through it.
_RITUAL_TEST_TEMPLATE = """
# covers: {ac_id}
def test_ritual_invocation_then_separate_direct_call():
    main(["report"])
    result = mark_the_criterion_done()
    assert result == "done"
"""

#: HONEST proof: drives the code under proof THROUGH main() with the real
#: "mark-done" operator action.
_HONEST_TEST_TEMPLATE = """
# covers: {ac_id}
def test_proof_drives_mark_done_through_main():
    result = main(["mark-done"])
    assert result == "done"
"""

#: DIRECT IMPORT proof: only imports and calls the code under proof
#: directly, never touching main() at all.
_DIRECT_IMPORT_TEST_TEMPLATE = """
# covers: {ac_id}
def test_proof_imports_and_calls_directly_only():
    result = mark_the_criterion_done()
    assert result == "done"
"""


class TestRitualInvocationDoesNotLaunderADirectImportProof(unittest.TestCase):
    """RITUAL case: the proof calls ``main(["report"])`` (an action whose
    handler never reaches the code under proof) and then, in a separate,
    unconnected step, calls the code under proof directly. This is
    EXACTLY the ritual-invocation trap BO-2900a-1-i's own notes describe --
    the gate must refuse it. FAILS TODAY: the real gate reads only
    ``entered_entry_point`` (True, because ``main`` was called for
    "report"), never ``reached_through`` (which its own call to
    ``_observe_reachability`` with an empty target_spec can never set), so
    it wrongly accepts."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.fixture_ac_id = "BO-TEST-2900A1I-RITUAL"
        write_ac(self.ac_root, self.fixture_ac_id)
        self.module_name = "test_bo2900a1i_ritual_fixture"
        write_fixture_file(
            self.test_root,
            f"{self.module_name}.py",
            _SHARED_UNIT_BODY
            + _RITUAL_TEST_TEMPLATE.format(ac_id=self.fixture_ac_id),
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # Expected-failure for a DIFFERENT reason than the two suspension-marked files:
    # this one fails on the live defect itself. The gate passes target_spec="" to
    # _observe_reachability, so `reached_through` is structurally always False and the
    # predicate collapses to `entered_entry_point` -- which the ritual proof satisfies.
    # No finding is raised, so once re-armed the rule would ACCEPT the exact shape it
    # exists to refuse. BO-2900a-1-i is `work_status: todo` for this.
    #
    # Repairing the observer (BO-2900a-2-i / a-2-iii) makes this pass, and the marker
    # then turns the file red on the unexpected success -- which is how the repair
    # announces itself. Remove the marker in that change; do not weaken the assertion.
    @unittest.expectedFailure  # gate emits no finding: target_spec="" (BO-2900a-1-i)
    def test_ritual_invocation_does_not_launder_a_direct_import_proof(self) -> None:
        # covers: BO-2900a-1-i
        # angle: criterion
        """A proof that enters ``main`` for an unrelated action and then
        separately calls the code under proof directly must be REFUSED --
        entering the way in is not the same as reaching the target through
        it. This is the case today's gate gets wrong."""
        verdict, findings = _gate_findings(
            self.fixture_ac_id, self.ac_root, self.test_root
        )

        self.assertTrue(
            findings,
            "RITUAL invocation must be FLAGGED — entering main for an unrelated "
            "action then calling the code directly is not reaching it through "
            "the way in. The rule raised no finding at all, so once re-armed it "
            f"would accept this proof. verdict={verdict}",
        )


class TestHonestProofThroughMainIsAccepted(unittest.TestCase):
    """HONEST case: the proof drives the code under proof THROUGH ``main``
    with the real operator action and arguments (``main(["mark-done"])``).
    Same fixture unit as the ritual case above; only the proof's own
    invocation shape differs. The gate must ACCEPT."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.fixture_ac_id = "BO-TEST-2900A1I-HONEST"
        write_ac(self.ac_root, self.fixture_ac_id)
        self.module_name = "test_bo2900a1i_honest_fixture"
        write_fixture_file(
            self.test_root,
            f"{self.module_name}.py",
            _SHARED_UNIT_BODY
            + _HONEST_TEST_TEMPLATE.format(ac_id=self.fixture_ac_id),
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_honest_proof_through_main_is_accepted(self) -> None:
        # covers: BO-2900a-1-i
        # angle: criterion
        """A proof that reaches the code under proof by invoking the real
        ``mark-done`` action on the unit's own way in must be eligible --
        proving the refusal above is about the path taken, not about
        whether ``main`` was entered at all."""
        verdict, findings = _gate_findings(
            self.fixture_ac_id, self.ac_root, self.test_root
        )

        self.assertEqual(
            findings,
            [],
            "HONEST proof through main() must raise NO finding — it drove the "
            f"behaviour through the unit's own way in. Got: {findings}",
        )
        self.assertTrue(
            verdict.get("eligible"),
            f"HONEST proof through main() must be eligible, got: {verdict}",
        )


class TestOrdinaryDirectImportProofIsRefused(unittest.TestCase):
    """DIRECT IMPORT case: the proof only imports and calls the code under
    proof directly, never touching ``main`` at all. Same fixture unit as
    the two cases above. The gate must REFUSE -- the ordinary case
    BO-2900a-1 exists to catch, and the one the sibling analysis shows is
    refused correctly today even while the ritual case above is wrongly
    accepted."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.fixture_ac_id = "BO-TEST-2900A1I-DIRECT"
        write_ac(self.ac_root, self.fixture_ac_id)
        self.module_name = "test_bo2900a1i_direct_fixture"
        write_fixture_file(
            self.test_root,
            f"{self.module_name}.py",
            _SHARED_UNIT_BODY
            + _DIRECT_IMPORT_TEST_TEMPLATE.format(ac_id=self.fixture_ac_id),
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ordinary_direct_import_proof_is_refused(self) -> None:
        # covers: BO-2900a-1-i
        # angle: criterion
        """A proof that never enters the unit's own way in at all must be
        refused, exactly as BO-2900a-1's own core case requires -- asserted
        here again, alongside the ritual and honest cases, so a
        reject-everything implementation cannot pass this suite either."""
        verdict, findings = _gate_findings(
            self.fixture_ac_id, self.ac_root, self.test_root
        )

        self.assertTrue(
            findings,
            "ordinary direct-import proof must be FLAGGED — it never enters the "
            f"unit's way in at all. verdict={verdict}",
        )


if __name__ == "__main__":
    unittest.main()
