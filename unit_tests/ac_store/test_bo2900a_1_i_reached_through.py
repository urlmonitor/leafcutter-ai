"""
MODULE: unit_tests/ac_store/test_bo2900a_1_i_reached_through.py
GOAL: RED test stubs for BO-2900a-1-i -- "entering the way in without reaching
    the code under proof does not make a criterion done".

=== AC under test ===

    id: BO-2900a-1-i (L3, build-orchestration)
    Given an acceptance criterion whose implementing code is the handler for
    the action named `mark-done` on a unit's command surface, and the proof
    test invokes that command surface and passes, and the action the test
    invokes is `report` (whose handler never calls the `mark-done` handler),
    then the criterion is rejected as not eligible, and the rejection states
    that the way in was entered but the code under proof was not reached, and
    a proof invoking the same surface with the `mark-done` action makes the
    criterion eligible.

=== Interface contract under test (to be implemented by python-coder) ===

  Location: scripts/ac_store/done_proof.py

    verify_done_eligible(
        ac_id: str,
        *,
        ac_root: Path,
        test_root: Path,
        reachability_spec: dict | None = None,   # <-- NEW, this ticket
    ) -> dict

  NEW optional keyword argument this ticket introduces:

    reachability_spec = {
        "target": "<module>:<callable>",       # the code under proof
        "entry_point": "<module>:<callable>",  # the unit's real way in
    }

  Both "<module>" values are resolved the same way the pytest subprocess
  that ``_run_pytest_and_parse`` launches resolves them -- i.e. the fixture
  test file's own module name (pytest's "prepend" import-mode inserts the
  test file's directory onto sys.path when there is no ``__init__.py``), so
  ``reachability_spec["target"]`` and ``["entry_point"]`` in the tests below
  name functions defined IN the same file as the covers-tagged proof test.

  When *reachability_spec* is supplied and the AC's covers-linked test would
  otherwise be eligible under the existing pass/fail gate (BO-2500a), the
  eligibility decision must ALSO incorporate reachability for that same
  pytest run, per BO-2900a-2's execution-derived observation contract
  (one ``reach_record`` per (test, target): ``{test_nodeid, target,
  entry_point, entered_entry_point, reached_through, observation_ok}``,
  produced by watching the run -- never by reading the test file's source
  text) and BO-2900a-1's rule (a proof that only ever imports the code under
  proof directly does not make the criterion done when the unit exposes a
  real way in).

  THE TRAP THIS TICKET (BO-2900a-1-i) ISOLATES: the eligibility condition
  must read the run's own ``reached_through`` fact -- "target entered while
  an entry_point frame was an ancestor on the SAME call stack" -- and must
  NEVER be reproduced as the conjunction of two independently recorded
  booleans (``entered_entry_point and target_was_called``). That naive
  conjunction is satisfiable by a proof that invokes the entry point once
  (with ANY action, including an unrelated one) and separately calls the
  target directly -- exactly what
  ``test_unrelated_extra_invocation_does_not_launder_a_direct_import_proof``
  below exercises.

  Returned dict gains one new key (additive only -- the existing
  ``eligible``/``reason``/``passing_tests``/``failing_tests``/``dangling_tags``
  keys are UNCHANGED, per the BO-2500b*/check_done_proof consumer note on
  this AC):

      "refusal_cause"  str | None
          One of the four BO-2900e-1 causes when not eligible; ``None`` when
          eligible. This ticket's distinguishing case uses
          ``"proof_not_through_entry_point"`` -- the SAME cause family
          BO-2900a-1's own direct-import refusal uses, but with a DIFFERENT
          ``reason`` string:

              "the way in was entered but the code under proof was not
               reached"                                   (THIS ticket)
          vs.
              "reached the code by direct import"          (BO-2900a-1)

          per BO-2900a-1-i.yaml's it_requirements.constraints.

=== Fixture authenticity mandate (matches the BO-2500a dogfood convention) ===

  All AC YAML fixtures are written with ``yaml.safe_dump`` (never a
  hand-typed YAML literal). All fixture "command surface" modules are real,
  importable .py files with a genuine ``main(argv)`` dispatcher and genuine
  handler functions -- reachability is exercised by ACTUALLY calling
  ``main()`` (or the target directly), never asserted from a hand-fed
  boolean or a mocked call graph.

=== Red baseline ===

  All three tests below are RED today: ``verify_done_eligible`` does not yet
  accept a ``reachability_spec`` keyword argument at all, so every call in
  this file raises ``TypeError: verify_done_eligible() got an unexpected
  keyword argument 'reachability_spec'`` -- a valid, unambiguous red state
  for all three tests, independent of what the fixture's own proof test
  invokes.

  To go green, python-coder must:
    1. Add the ``reachability_spec`` keyword to ``verify_done_eligible``.
    2. Wire in an execution-derived, ancestor-based reachability check
       (BO-2900a-2's observer, or an equivalent call-stack-ancestry check)
       -- never a source-text scan of the fixture file.
    3. Add the ``refusal_cause`` key and the "entered but not reached" reason
       text this ticket names, distinguishable from BO-2900a-1's own
       direct-import reason string.
"""
from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

# This import succeeds today -- verify_done_eligible already exists. The red
# state for every test in this file comes from calling it with the NEW
# reachability_spec= keyword argument (TypeError), not from this import.
from done_proof import verify_done_eligible  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixture helpers (mirrors unit_tests/ac_store/test_bo2500a_done_proof.py)
# ---------------------------------------------------------------------------


def _write_ac(ac_root: Path, ac_id: str) -> Path:
    """Write a minimal active-leaf AC YAML using yaml.safe_dump (mandate-compliant).

    Args:
        ac_root: Root directory of the synthetic AC store.
        ac_id: Identifier for the fixture AC (e.g. "BO-TEST-REACHTHROUGH-1").

    Returns:
        Path to the written YAML file.
    """
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic reachability fixture AC {ac_id}",
        "component": "build-orchestration",
        "level": "L3",
        "status": "active",
        "work_status": "todo",
        "readiness": "draft",
        "priority": "medium",
        "depends_on": [],
        "amended_by": [],
        "covered_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    # Mandate: yaml.safe_dump, not a hand-typed YAML literal.
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _write_fixture_file(test_root: Path, filename: str, content: str) -> Path:
    """Write a real, importable Python fixture file to test_root.

    Args:
        test_root: Directory to place the fixture file.
        filename: Filename (e.g. "test_proof_via_report_action.py"); its stem
            (minus ".py") is also the module name used in reachability_spec
            "<module>:<callable>" strings in these tests, since pytest's
            prepend import-mode puts test_root on sys.path when it holds no
            __init__.py.
        content: Python source; leading whitespace is dedented automatically.

    Returns:
        Path to the written fixture file.
    """
    test_root.mkdir(parents=True, exist_ok=True)
    path = test_root / filename
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Test 1 -- entering a DIFFERENT action (`report`) never reaches `mark-done`
# ---------------------------------------------------------------------------


class TestEnteringDifferentActionDoesNotLaunder(unittest.TestCase):
    """BO-2900a-1-i core case: `report` proof never reaches the `mark-done` code."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.fixture_ac_id = "BO-TEST-REACHTHROUGH-1"
        _write_ac(self.ac_root, self.fixture_ac_id)
        self.module_name = "test_proof_via_report_action"
        _write_fixture_file(
            self.test_root,
            f"{self.module_name}.py",
            f"""\
            def _mark_done_handler():
                \"\"\"The code under proof -- must NOT be reached by this test.\"\"\"
                return True

            def _report_handler():
                return True

            def main(argv):
                action = argv[0] if argv else "--help"
                if action == "mark-done":
                    return _mark_done_handler()
                return _report_handler()

            # covers: {self.fixture_ac_id}
            def test_proof_invokes_report_action():
                result = main(["report"])
                assert result is True
            """,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_entering_a_different_action_does_not_make_the_criterion_eligible(
        self,
    ) -> None:
        # covers: BO-2900a-1-i
        # angle: criterion
        """AC BO-2900a-1-i: `report` entered, `mark-done` code never reached => ineligible.

        The fixture proof test invokes ``main(["report"])`` and passes under
        pytest, but the ``report`` branch never calls ``_mark_done_handler``
        (the code under proof). verify_done_eligible must therefore refuse
        eligibility, and the reason must state that the way in was entered
        but the code under proof was not reached -- distinguishing this case
        from the pre-existing "no linked test found" / "linked test failed"
        messages the BO-2500a pass/fail gate already produces for other
        refusal reasons.
        """
        verdict = verify_done_eligible(
            self.fixture_ac_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
            reachability_spec={
                "target": f"{self.module_name}:_mark_done_handler",
                "entry_point": f"{self.module_name}:main",
            },
        )

        self.assertFalse(
            verdict["eligible"],
            f"expected ineligible (entered but not reached), got: {verdict}",
        )
        reason = verdict.get("reason", "").lower()
        self.assertIn("entered", reason)
        self.assertIn("not reached", reason)
        self.assertEqual(
            verdict.get("refusal_cause"),
            "proof_not_through_entry_point",
            f"expected the BO-2900e-1 'proof_not_through_entry_point' cause, got: {verdict}",
        )


# ---------------------------------------------------------------------------
# Test 2 -- invoking the ACTUAL action under proof (`mark-done`) is eligible
# ---------------------------------------------------------------------------


class TestInvokingActionUnderProofIsEligible(unittest.TestCase):
    """Same fixture surface; the proof now takes the `mark-done` path."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.fixture_ac_id = "BO-TEST-REACHTHROUGH-2"
        _write_ac(self.ac_root, self.fixture_ac_id)
        self.module_name = "test_proof_via_markdone_action"
        _write_fixture_file(
            self.test_root,
            f"{self.module_name}.py",
            f"""\
            def _mark_done_handler():
                \"\"\"The code under proof -- IS reached by this test.\"\"\"
                return True

            def _report_handler():
                return True

            def main(argv):
                action = argv[0] if argv else "--help"
                if action == "mark-done":
                    return _mark_done_handler()
                return _report_handler()

            # covers: {self.fixture_ac_id}
            def test_proof_invokes_markdone_action():
                result = main(["mark-done"])
                assert result is True
            """,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_invoking_the_action_under_proof_makes_the_criterion_eligible(
        self,
    ) -> None:
        # covers: BO-2900a-1-i
        # angle: criterion
        """AC BO-2900a-1-i: invoking `mark-done` through the way in is eligible.

        Proves the refusal in the sibling test above is about the PATH
        taken during the run, not about the command surface merely being
        entered: the only difference between the two fixtures is which
        action the proof test passes to ``main()``, and only the
        `mark-done` action reaches the code under proof through the entry
        point on the same call stack.
        """
        verdict = verify_done_eligible(
            self.fixture_ac_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
            reachability_spec={
                "target": f"{self.module_name}:_mark_done_handler",
                "entry_point": f"{self.module_name}:main",
            },
        )

        self.assertTrue(
            verdict["eligible"],
            f"expected eligible (reached through the entry point), got: {verdict}",
        )
        self.assertEqual(verdict.get("reason", ""), "")
        self.assertIsNone(verdict.get("refusal_cause"))


# ---------------------------------------------------------------------------
# Test 3 -- an unrelated extra invocation must not launder a direct-import proof
# ---------------------------------------------------------------------------


class TestUnrelatedInvocationDoesNotLaunderDirectImport(unittest.TestCase):
    """A direct-import proof plus a decoy `--help` call must STILL be ineligible."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.fixture_ac_id = "BO-TEST-REACHTHROUGH-3"
        _write_ac(self.ac_root, self.fixture_ac_id)
        self.module_name = "test_direct_import_plus_help_decoy"
        _write_fixture_file(
            self.test_root,
            f"{self.module_name}.py",
            f"""\
            def _mark_done_handler():
                \"\"\"The code under proof -- called DIRECTLY, not through main().\"\"\"
                return True

            def _report_handler():
                return True

            def main(argv):
                action = argv[0] if argv else "--help"
                if action == "mark-done":
                    return _mark_done_handler()
                return _report_handler()

            # covers: {self.fixture_ac_id}
            def test_direct_import_proof_with_unrelated_help_call():
                # Decoy: an unrelated invocation of the SAME command surface,
                # entered separately from (never as an ancestor frame of) the
                # direct call below. A naive
                # "entered_entry_point AND target_was_called" implementation
                # would wrongly treat this as reached-through; the correct
                # ancestor-based check must not.
                main(["--help"])
                # Direct-import proof: calls the code under proof directly,
                # bypassing the entry point entirely for THIS invocation.
                result = _mark_done_handler()
                assert result is True
            """,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_unrelated_extra_invocation_does_not_launder_a_direct_import_proof(
        self,
    ) -> None:
        # covers: BO-2900a-1-i
        # angle: criterion
        """AC BO-2900a-1-i: adding one unrelated entry-point call must not launder eligibility.

        This is the ritual-invocation workaround the AC's notes name
        explicitly: "any proof can then be made eligible by adding one
        unrelated invocation of the command surface (a --help call, a
        status call, a call to a different action entirely)". Because
        ``main(["--help"])`` and ``_mark_done_handler()`` are called as two
        SEPARATE, unconnected statements (not one nested inside the other),
        the entry point is never an ancestor frame at the moment the target
        runs -- so this must be refused with the SAME
        "entered but not reached" cause as
        test_entering_a_different_action_does_not_make_the_criterion_eligible
        above, not silently accepted because both things happened to occur
        somewhere in the same test.
        """
        verdict = verify_done_eligible(
            self.fixture_ac_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
            reachability_spec={
                "target": f"{self.module_name}:_mark_done_handler",
                "entry_point": f"{self.module_name}:main",
            },
        )

        self.assertFalse(
            verdict["eligible"],
            f"expected ineligible (decoy call must not launder a direct-import "
            f"proof), got: {verdict}",
        )
        reason = verdict.get("reason", "").lower()
        self.assertIn("entered", reason)
        self.assertIn("not reached", reason)
        self.assertEqual(
            verdict.get("refusal_cause"),
            "proof_not_through_entry_point",
            f"expected the BO-2900e-1 'proof_not_through_entry_point' cause, got: {verdict}",
        )


if __name__ == "__main__":
    unittest.main()
