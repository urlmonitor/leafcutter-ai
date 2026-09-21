"""
MODULE: test_uxp_700b_3
GOAL: Pin UXP-700b-3 -- a check phrased as a universal rule ("every X must satisfy P")
    that is run against zero records of that kind must report that it was NOT
    exercised, naming the kind of record it needed, and that report must never be
    confused with a real "the rule holds" verdict.
BUSINESS CONTEXT: A universal rule over an empty set is vacuously true (there is no
    record to violate it), so a naive checker that only asks "did I find a
    violation?" would report success having examined nothing -- the exact failure
    mode UXP-514's four "errors if ANY X differs" clauses are vulnerable to on an
    empty product-truth store. UXP-700b-3 is the general rule those four checks (and
    every future universal-rule check) must be held to; UXP-700b-3-i is the paired
    negative control proving a checker cannot satisfy this AC by refusing to ever
    report anything else.
ARCHITECTURE: Targets docs/product-truth/scripts/universal_rule_check.py, added to
    sys.path the same way unit_tests/test_generate_product_truth_idempotency.py
    reaches into docs/product-truth/scripts for generate_product_truth, and the same
    way test_uxp_700b_3_i.py already reaches it for the paired population-of-one
    boundary. Both the library entry point (check_universal_rule) and the module's
    own CLI entry point (main(argv), guarded by `if __name__ == "__main__":`) are
    exercised here; the CLI is the resolved reachability surface (there is no
    pre-commit hook, slash command, or workflow step yet -- UXP-700b/700b-1/700b-2
    are still work_status: todo in this repo, so nothing else calls this module).

AC-4 SCOPE NOTE (contract-aware mode, "global AC list" mapping):
    AC-4 -- "the run's overall outcome is not the outcome for a record that was
    checked and found sound while any such check reports it was not exercised" --
    is partly out of THIS ticket's scope: wiring RuleCheckResult into the
    multi-check ADR-042 aggregate outcome in
    docs/product-truth/scripts/product_truth_outcome.py (e.g. "checked-and-sound"
    vs "checked-with-unexecuted-checks"/"nothing-examined") is explicitly deferred
    to a later ticket (architect-review sign-off on this ticket, 2026-09-16: "the
    module is deliberately a pure, standalone helper ... not yet wired into
    validate_product_truth.py or product_truth_outcome.py -- that wiring ... is
    correctly left to a later ticket"). That multi-check aggregation is NOT tested
    here.

    RESOLUTION (2026-09-16, decided with the user, superseding the original
    exit-code framing below): AC-4 is about the run's overall OUTCOME, not about
    its exit code. This module's own exit-code contract is independently pinned
    by TWO already-fixed points that jointly leave no free exit-code value for
    AC-4 to claim: this ticket's own reachability test requires a not_exercised
    run to exit 0 ("an empty population is not a violation"), and the done
    sibling UXP-700b-3-i's reachability test requires a holds run to exit 0 (a
    single satisfying record is not a violation either) -- see
    test_uxp_700b_3_i.py::TestReachability::test_uxp_700b_3_i_reachable_from_entry_point.
    Both are correct and neither is renegotiated here. AC-4's actual text --
    "the run's overall outcome is not the outcome for a record that was checked
    and found sound while any such check reports it was not exercised" -- names
    OUTCOME, and this module's `outcome` field (in {not_exercised, holds,
    violated}, per ADR-042's vocabulary this module participates in) already
    is the non-colliding signal: `not_exercised` and `holds` are two distinct
    members of that closed vocabulary and are asserted to differ, on both the
    library result (RuleCheckResult.outcome) and the CLI's JSON payload
    (payload["outcome"]), by every test in this file. TestAc4RunOutcomeDiffers
    below is rewritten accordingly to assert AC-4 against `outcome`, not exit
    code -- the exit-code framing in the paragraph below is retained only as
    historical context for why that signal was rejected.

    (Superseded framing, kept for context.) AC-4's clause still applies,
    narrowly, to the one "run" this ticket's own contract DOES build: a single
    CLI invocation of universal_rule_check.py, whose own docstring states its
    "exit code... makes the verdict consumable in control flow, not just in
    printed output." A caller that only consumes the exit code cannot currently
    distinguish a not-exercised run from a checked-and-found-sound ("holds")
    run -- main() maps both to exit 0, only "violated" gets a non-zero exit.
    That signal is already fully allocated by the two fixed points above, so
    AC-4 is now read against `outcome` instead (resolved above).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# The scripts directory is not on the default path; add it so we can import,
# mirroring unit_tests/test_generate_product_truth_idempotency.py's convention for
# this same docs/product-truth/scripts location, and test_uxp_700b_3_i.py's own
# convention for this exact module.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "docs" / "product-truth" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_CLI_PATH = _SCRIPTS_DIR / "universal_rule_check.py"


class TestEmptyPopulationReportsNotExercised(unittest.TestCase):
    """Zero records of the checked kind must yield a not-exercised verdict that names
    the kind -- never a silent pass produced by vacuous truth."""

    def test_universal_rule_on_empty_input_reports_not_exercised(self):
        # covers: UXP-700b-3
        # angle: boundary
        # AC-1: a project record in which no record of that kind exists
        # AC-2: it reports that it was not exercised, naming the kind of record it needed
        #
        # A population of exactly zero records must yield outcome == "not_exercised",
        # examined == 0, and the result must NAME the kind of record it needed (AC-2)
        # -- a bare boolean or an unnamed sentinel would not satisfy "naming the kind".
        import universal_rule_check as urc  # noqa: E402  (import must fail until implemented)

        result = urc.check_universal_rule(
            [],
            predicate=lambda r: r["value"] > 0,
            kind="widget",
        )

        self.assertEqual(result.outcome, "not_exercised")
        self.assertEqual(result.examined, 0)
        # AC-2's "naming the kind of record it needed" -- the verdict must carry the
        # actual kind string, not merely a fixed/blank placeholder.
        self.assertEqual(
            result.kind,
            "widget",
            "the not-exercised verdict must name the kind of record it needed (AC-2)",
        )
        self.assertNotEqual(
            result.kind,
            "",
            "an empty kind string does not name anything -- AC-2 requires the actual kind",
        )
        self.assertEqual(result.violations, [])

        # A second, differently-named kind must be echoed back distinctly -- proves the
        # module actually threads the caller's kind through rather than returning a
        # constant that happens to match a single fixture value.
        other = urc.check_universal_rule([], predicate=lambda r: True, kind="gadget")
        self.assertEqual(other.kind, "gadget")
        self.assertEqual(other.outcome, "not_exercised")


class TestEmptyPopulationDoesNotReportHolds(unittest.TestCase):
    """The not-exercised report must be distinct from -- and must never accompany --
    a statement that the rule holds (AC-3)."""

    def test_universal_rule_on_empty_input_does_not_report_the_rule_holds(self):
        # covers: UXP-700b-3
        # angle: criterion
        # AC-3: it does not report that the rule holds
        import universal_rule_check as urc  # noqa: E402  (import must fail until implemented)

        result = urc.check_universal_rule(
            [],
            predicate=lambda r: r["value"] > 0,
            kind="widget",
        )

        self.assertNotEqual(
            result.outcome,
            "holds",
            "an empty population must never be reported as the rule holding -- that is "
            "the exact vacuous-truth trap this AC exists to close",
        )
        # The outcome vocabulary is a closed set of exactly three values; asserting the
        # positive membership (not just inequality to "holds") rules out a checker that
        # invents a fourth, ambiguous label to dodge the assertion above.
        self.assertIn(result.outcome, {"not_exercised", "holds", "violated"})
        self.assertEqual(result.outcome, "not_exercised")
        # The presence of a real verdict at all (outcome is a non-empty string distinct
        # from "holds") plus zero violations proves this is a genuine not-exercised
        # report, not a violated report dressed up to avoid "holds".
        self.assertEqual(result.violations, [])


class TestReachability(unittest.TestCase):
    """Reachability: the not-exercised verdict on an empty population must be provable
    through the module's real CLI entry point, not merely through a direct import of
    check_universal_rule().

    completion_manifest.reachability_entry_point_answer:
      result: resolved
      entry_point: "python docs/product-truth/scripts/universal_rule_check.py \
        --records <file> --rule positive --kind widget (CLI via subprocess, main()
        guarded by if __name__ == '__main__':)"
    This mirrors test_uxp_700b_3_i.py's own resolution for this same module: UXP-700b/
    700b-1/700b-2/700b-3 (this AC's own prerequisites) are all still work_status: todo
    in this repo, so there is no pre-commit hook, slash command, or workflow step to
    attach to yet. Category 1 of the resolution order (a CLI script with a main()
    guarded by `if __name__ == "__main__":`) is the entry point this ticket's own
    contract requires python-coder to build, so the CLI is what is pinned here -- not
    an inner helper reached by import.
    """

    def _run_cli(self, records: list, kind: str = "widget") -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            records_path = Path(tmp) / "records.json"
            records_path.write_text(json.dumps(records), encoding="utf-8")
            return subprocess.run(
                [
                    sys.executable,
                    str(_CLI_PATH),
                    "--records",
                    str(records_path),
                    "--rule",
                    "positive",
                    "--kind",
                    kind,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

    def test_uxp_700b_3_reachable_from_entry_point(self):
        # covers: UXP-700b-3
        # angle: reachability
        # AC-1, AC-2, AC-3: exercised through the real production entry point (the
        # module's own CLI), not through a direct import of check_universal_rule().
        # REQUIRED: invoke the production entry point as a subprocess and assert the
        # outcome is consumed -- read back from the process's own stdout -- not
        # merely printed and ignored.
        result = self._run_cli([], kind="widget")

        self.assertEqual(
            result.returncode,
            0,
            f"an empty population is not a violation; the CLI must not exit non-zero "
            f"for not-exercised; stderr={result.stderr!r}",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["outcome"], "not_exercised")
        self.assertEqual(payload["examined"], 0)
        self.assertEqual(
            payload["kind"],
            "widget",
            "the CLI's own JSON verdict must name the kind of record it needed (AC-2)",
        )
        self.assertNotEqual(
            payload["outcome"],
            "holds",
            "the CLI must not report the rule holds for an empty population (AC-3)",
        )
        self.assertEqual(payload["violations"], [])


class TestAc4RunOutcomeDiffers(unittest.TestCase):
    """AC-4, narrowed to this ticket's own entry point (see the AC-4 SCOPE NOTE in this
    file's module docstring, RESOLUTION paragraph): the run's overall OUTCOME for a
    not-exercised run must not be the outcome for a run that was checked and found
    sound (a "holds" run). AC-4's text names outcome, not exit code -- the CLI's exit
    code is a scalar already fully allocated by two independent, already-pinned fixed
    points (this ticket's own not_exercised-exits-0 reachability test, and the done
    sibling UXP-700b-3-i's holds-exits-0 reachability test), leaving no free exit-code
    value for AC-4 to claim without contradicting one of them. `outcome` is the
    non-colliding signal: it is a member of a closed three-value vocabulary
    ({not_exercised, holds, violated}) and `not_exercised` / `holds` are two distinct
    members of it."""

    def _run_cli(self, records: list) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            records_path = Path(tmp) / "records.json"
            records_path.write_text(json.dumps(records), encoding="utf-8")
            return subprocess.run(
                [
                    sys.executable,
                    str(_CLI_PATH),
                    "--records",
                    str(records_path),
                    "--rule",
                    "positive",
                    "--kind",
                    "widget",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

    def test_ac4_not_exercised_outcome_differs_from_holds_outcome(self):
        # covers: UXP-700b-3
        # angle: criterion
        # AC-4: the run's overall outcome is not the outcome for a record that was
        # checked and found sound while any such check reports it was not exercised.
        # Narrowed here to this ticket's own CLI entry point (see module docstring
        # AC-4 SCOPE NOTE) -- the multi-check ADR-042 aggregation is out of scope.
        # Asserted against the run's OUTCOME (payload["outcome"]), per the RESOLUTION
        # in this file's module docstring -- not against exit code, which both a
        # not-exercised run (this ticket's own reachability test) and a holds run
        # (the done sibling UXP-700b-3-i's reachability test) already, correctly,
        # pin to 0, leaving no free exit-code value for AC-4 to claim.
        not_exercised_run = self._run_cli([])
        holds_run = self._run_cli([{"id": "widget-1", "value": 5}])

        # Both runs exit 0 -- this is the pre-existing, correct, already-pinned
        # contract (not_exercised is not a violation; a single satisfying record
        # is not a violation either) and is unaffected by AC-4's requirement.
        self.assertEqual(not_exercised_run.returncode, 0)
        self.assertEqual(holds_run.returncode, 0)

        not_exercised_payload = json.loads(not_exercised_run.stdout)
        holds_payload = json.loads(holds_run.stdout)
        self.assertEqual(not_exercised_payload["outcome"], "not_exercised")
        self.assertEqual(holds_payload["outcome"], "holds")

        self.assertNotEqual(
            not_exercised_payload["outcome"],
            holds_payload["outcome"],
            "a not-exercised run and a checked-and-found-sound (holds) run must not "
            "report the same overall outcome -- otherwise a caller that reads "
            "outcome cannot tell them apart, which is exactly the ambiguity AC-4 "
            f"forbids (both reported {not_exercised_payload['outcome']!r})",
        )


if __name__ == "__main__":
    unittest.main()
