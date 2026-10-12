"""
MODULE: unit_tests/workflows/test_bo2400f_7_iv_claim_reply_contract_workflow.py
GOAL: RED behavioural (workflow-level) tests for BO-2400f-7-iv — a claim that
      was made and SUCCEEDED must never be reported as a claim that was never
      attempted, and the run's usability test for the reply must not demand
      more than the dispatch contract the run itself declared.

=== The defect (BO-2400f-7-iv) ===

Observed 2026-09-23 on the first fast-lane run made after BO-2400f-7-iii
shipped. The run reached the claim step, claimed all 25 members of the
connected set, and then halted with:

    "The claim was never attempted: the dispatched performer either declined
     to run the repository-mutating claim command or returned no usable
     result, so no AC was flipped to in_progress"

...while the same payload carried all 25 ids in `claimed` and
`target_refused: false`. The claim had in fact succeeded completely.

The cause sits in two places a few lines apart in fast-lane-ship.js. The
dispatch declares its contract:

    required: ["claimed", "target_refused"]          # excluded_claimed optional

and the gate that judges the reply demanded more than that contract does:

    const claimUsable = !!claimResult
      && Array.isArray(claimResult.claimed)
      && Array.isArray(claimResult.excluded_claimed);   # <-- not required

A performer that claims everything and excludes nothing has no reason to send
an empty optional array, and did not. So a reply that satisfied the declared
contract was judged unusable and routed to the halt whose entire purpose is to
describe a claim that never happened.

This is BO-2400f-7-iii's defect inverted. That record existed because a
DECLINE was reported as CONTENTION; this one is an ATTEMPT THAT SUCCEEDED
reported as AN ATTEMPT NEVER MADE. Both are a consumer reading a reply
differently from the contract it asked for, and both send the operator after
a cause that does not exist.

The two BO-2400f-7-iii behaviours must survive: descriptors 4 and 5 below are
non-regression arms over that record, because the naive fix here — stop
checking the reply — would satisfy descriptors 1-3 while destroying it.

=== Why this is not a grep test ===

Every assertion drives fast-lane-ship.js through run_workflow_under_e2(),
which executes the script's REAL top-level control flow in a Node.js
subprocess and records every agent() dispatch plus the script's terminal
return value. "The run proceeded" is asserted as "the dispatch that FOLLOWS
the claim step was actually made", not as the absence of a string.

Descriptor 3 does read the workflow source, but only to BUILD ITS INPUT — it
extracts the dispatch's own declared `required` list and constructs a reply
carrying exactly those fields and nothing else. The assertion remains
behavioural. That inversion is the point: the test is written against
whatever contract the file declares, so it keeps failing for the next
optional field someone demands in the gate but not in the contract.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402

import workflows._fast_lane_claim_fixtures as _claim_fx  # noqa: E402

_WORKFLOW_PATH = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"

_AC_ID = "BO-STUB-1"
_BRANCH = f"fast-lane/{_AC_ID}"

# The label of the dispatch that immediately FOLLOWS the claim step. Its
# presence in the recorded call list is the behavioural proof that the run got
# past the claim, rather than halting there.
_LABEL_AFTER_CLAIM = "fastlane-context-bundle"

_NOT_ATTEMPTED_MARKERS = (
    "never attempted",
    "not attempted",
    "was not attempted",
)

_CONTENTION_MARKERS = (
    "concurrent",
    "owns these",
    "owned by",
    "already claimed",
    "already in_progress",
    "held by another",
)


def _opened_worktree_payload(worktree_path: str) -> dict[str, Any]:
    return {
        "outcome": "opened",
        "worktree_path": worktree_path,
        "branch": _BRANCH,
        "created": True,
        "base_commit": "a" * 40,
        "base_matches_origin_main": True,
    }


def _run_lane(claim_response: Any) -> HarnessResult:
    """Drive fast-lane-ship.js from Worktree through the claim step.

    Mirrors the sibling BO-2400f-7-iii helper: supplies just enough for the run
    to reach "claim-connected", and lets the caller control only that step's
    reply.
    """
    tmp = tempfile.TemporaryDirectory()
    try:
        worktree_root = Path(tmp.name)
        (worktree_root / "docs" / "acceptance-criteria").mkdir(parents=True)
        label_responses = {
            "fastlane-worktree": _opened_worktree_payload(str(worktree_root)),
            "resolve-connected": {"ac_ids": [_AC_ID], "message": "1 to build"},
            "claim-connected": claim_response,
        }
        return run_workflow_under_e2(
            _WORKFLOW_PATH,
            label_responses=label_responses,
            args={"ac": _AC_ID},
        )
    finally:
        tmp.cleanup()


def _labels_seen(result: HarnessResult) -> list[str | None]:
    return [c.label for c in result.agent_calls]


_CLAIM_SCHEMA_ANCHOR = "const CLAIM_RUNNER_SCHEMA = {"


def _claim_dispatch_schema_source() -> str:
    """Return the source of the schema object the claim dispatch declares.

    Anchored on the schema's own named const, and bounded by the
    `claim-connected` label that consumes it.

    The previous version of this helper anchored only on the label and walked
    BACKWARDS to the nearest preceding `required: [...]`. That worked for as
    long as the claim dispatch happened to be the nearest thing with a
    required list. When the dispatch was rewired to `command-step-runner` on
    2026-09-30 and stopped declaring one, the backwards walk did not fail — it
    kept going and found an unrelated dispatch's schema (`["producible"]`),
    then reported it as the claim's declared contract. Its own guard could not
    fire, because a match WAS found; it was simply the wrong one.

    So this raises when the anchor is missing rather than falling back to
    whatever is nearby. A test that silently measures a different dispatch is
    worse than a test that stops and says it cannot find the one it wants.
    """
    source = _WORKFLOW_PATH.read_text(encoding="utf-8")
    schema_at = source.find(_CLAIM_SCHEMA_ANCHOR)
    if schema_at == -1:
        raise AssertionError(
            f"Could not locate {_CLAIM_SCHEMA_ANCHOR!r} in fast-lane-ship.js. "
            f"If the claim dispatch's schema was renamed or inlined, update "
            f"this anchor — do not loosen it into a search for the nearest "
            f"schema-shaped thing, which is the defect this helper carries a "
            f"docstring about."
        )
    label_at = source.index('label: "claim-connected"')
    if schema_at >= label_at:
        raise AssertionError(
            "CLAIM_RUNNER_SCHEMA is declared AFTER the claim-connected "
            "dispatch that uses it, so the two are no longer the pair this "
            "test assumes. Re-read the dispatch before trusting this file."
        )
    return source[schema_at:label_at]


class TestSuccessfulClaimOmittingOptionalExcludedFieldProceeds(unittest.TestCase):
    """Descriptor 1 (angle: failure).

    The exact 2026-09-23 payload shape: a populated `claimed` list,
    `target_refused: false`, and NO `excluded_claimed` key at all. The run must
    get past the claim step.
    """

    def test_a_successful_claim_omitting_the_optional_excluded_field_proceeds(
        self,
    ) -> None:
        # covers: BO-2400f-7-iv
        # angle: failure
        successful_reply = _claim_fx.claim_ran(
            [_AC_ID], message="", include_excluded_key=False
        )
        self.assertNotIn(
            "excluded_claimed",
            successful_reply["stdout"],
            "This test's whole point is the ABSENT optional key. It is now "
            "absent from the gate payload carried in stdout, which is where "
            "the lane reads it from.",
        )
        result = _run_lane(successful_reply)

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        self.assertIn(
            _LABEL_AFTER_CLAIM,
            _labels_seen(result),
            f"A claim that SUCCEEDED (all ids in `claimed`, target_refused "
            f"false) must let the run proceed past the claim step. The "
            f"dispatch that follows it was never made, so the run halted "
            f"there. Result: {result.result}",
        )


class TestSucceededClaimIsNeverReportedAsNeverAttempted(unittest.TestCase):
    """Descriptor 2 (angle: criterion).

    Asserted over the claim outcome rather than over one wording: no reply
    carrying a non-empty `claimed` list may produce the not-attempted halt.
    """

    def test_a_claim_that_succeeded_is_never_reported_as_never_attempted(
        self,
    ) -> None:
        # covers: BO-2400f-7-iv
        # angle: criterion
        replies: tuple[tuple[str, dict[str, Any]], ...] = (
            (
                "empty-message-no-excluded-key",
                _claim_fx.claim_ran([_AC_ID], message="", include_excluded_key=False),
            ),
            (
                "explicit-empty-excluded",
                _claim_fx.claim_ran([_AC_ID]),
            ),
            (
                "bare-minimum-payload",
                _claim_fx.claim_ran([_AC_ID], include_excluded_key=False),
            ),
        )
        for case_name, reply in replies:
            with self.subTest(case=case_name):
                result = _run_lane(reply)
                self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
                as_text = str(result.result or {}).lower()
                for marker in _NOT_ATTEMPTED_MARKERS:
                    self.assertNotIn(
                        marker,
                        as_text,
                        f"[{case_name}] A claim reporting 1 claimed id was "
                        f"described as never attempted ('{marker}'). "
                        f"Reply: {reply}",
                    )


class TestUsabilityTestRequiresNoMoreThanTheDeclaredContract(unittest.TestCase):
    """Descriptor 3 (angle: seam).

    A reply carrying exactly the dispatch's declared required fields and
    nothing else must be usable. This catches the CLASS of defect rather than
    the instance: it fails for any future field the gate demands but the
    contract leaves optional.
    """

    def test_the_usability_test_requires_no_more_than_the_declared_contract(
        self,
    ) -> None:
        # covers: BO-2400f-7-iv
        # angle: seam
        schema_source = _claim_dispatch_schema_source()

        # The dispatch must declare NO required fields, and that absence is a
        # decision rather than an oversight: command-step-runner answers with
        # either a result (carrying `exit_status`) or a decline (carrying
        # `declined` and no `exit_status`), and those two shapes share no
        # mandatory key. Requiring either one would reject the other at the
        # schema layer — converting a decline, which the lane must report as
        # "never attempted", into a validation failure it cannot describe.
        #
        # This is the same trap as the original BO-2400f-7-iv defect seen from
        # the other side. That one demanded a field the producer left
        # optional; this would demand a field one of the two legal shapes
        # never carries. Both turn a valid reply into a halt.
        self.assertNotIn(
            "required",
            schema_source,
            "The claim dispatch declares a `required` list. Under the "
            "command-step-runner contract it must not: a result and a "
            "decline share no mandatory key, so requiring anything rejects "
            "one of the two legal replies outright.",
        )

        # The contract that DOES have mandatory content is the gate's, and it
        # travels as JSON inside stdout. The minimum it ever emits on a run
        # that claimed something is a `claimed` array — so a reply carrying
        # exactly that, and nothing else, must be usable.
        minimal = _claim_fx.claim_ran([_AC_ID], include_excluded_key=False)

        result = _run_lane(minimal)

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        self.assertIn(
            _LABEL_AFTER_CLAIM,
            _labels_seen(result),
            f"A runner reply whose stdout carries exactly the gate's "
            f"mandatory `claimed` field, and nothing else, was judged "
            f"unusable. The lane demands more than either contract states. "
            f"Result: {result.result}",
        )


class TestDeclineStillHaltsAsNotAttempted(unittest.TestCase):
    """Descriptor 4 (angle: criterion) — non-regression over BO-2400f-7-iii.

    The opposed arm. A fix that simply stops checking the reply passes
    descriptors 1-3 and fails here.
    """

    def test_a_performer_that_declines_still_halts_as_not_attempted(self) -> None:
        # covers: BO-2400f-7-iv
        # angle: criterion
        decline_reply = _claim_fx.claim_declined(
            "declining to run a store-mutating command"
        )
        result = _run_lane(decline_reply)

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        as_text = str(result.result or {}).lower()

        self.assertTrue(
            any(marker in as_text for marker in _NOT_ATTEMPTED_MARKERS),
            f"A decline must still halt as NOT ATTEMPTED. Got: {result.result}",
        )
        self.assertNotIn(
            _LABEL_AFTER_CLAIM,
            _labels_seen(result),
            f"A decline must stop the run at the claim step. The following "
            f"dispatch was made anyway. Result: {result.result}",
        )


class TestGenuineContentionStillReportedWithMembers(unittest.TestCase):
    """Descriptor 5 (angle: criterion) — second non-regression arm."""

    def test_genuine_contention_is_still_reported_with_its_members(self) -> None:
        # covers: BO-2400f-7-iv
        # angle: criterion
        held = ["BO-STUB-1", "BO-STUB-2"]
        contention_reply = {
            "claimed": [],
            "excluded_claimed": held,
            "target_refused": True,
            "message": "members already in_progress",
        }
        result = _run_lane(contention_reply)

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result or {}
        as_text = str(payload).lower()

        self.assertTrue(
            any(marker in as_text for marker in _CONTENTION_MARKERS),
            f"Genuine contention must still be reported as contention. "
            f"Got: {payload}",
        )
        for ac_id in held:
            self.assertIn(
                ac_id,
                str(payload),
                f"A contention report must name the held member {ac_id}. "
                f"Got: {payload}",
            )
        self.assertNotIn(
            _LABEL_AFTER_CLAIM,
            _labels_seen(result),
            f"Contention must stop the run at the claim step. Result: {payload}",
        )


if __name__ == "__main__":
    unittest.main()
