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

import json
import re
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


def _declared_required_fields_for_claim_dispatch() -> list[str]:
    """Extract the claim dispatch's OWN declared `required` list from the source.

    Used to build the input for descriptor 3, never to assert on. The window is
    anchored on the `label: "claim-connected"` line and walks backwards to the
    nearest preceding `required: [...]`, which is the schema attached to that
    dispatch.
    """
    source = _WORKFLOW_PATH.read_text(encoding="utf-8")
    label_at = source.index('label: "claim-connected"')
    preceding = source[:label_at]
    matches = list(re.finditer(r"required:\s*(\[[^\]]*\])", preceding))
    if not matches:
        raise AssertionError(
            "Could not locate a `required: [...]` schema preceding the "
            "claim-connected dispatch in fast-lane-ship.js. If the dispatch "
            "shape changed, update this extractor — do not delete the test."
        )
    raw = matches[-1].group(1).replace("'", '"')
    return json.loads(raw)


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
        successful_reply = {
            "claimed": [_AC_ID],
            "target_refused": False,
            "message": "",
        }
        self.assertNotIn(
            "excluded_claimed",
            successful_reply,
            "This test's whole point is the ABSENT optional key.",
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
        for reply in (
            {"claimed": [_AC_ID], "target_refused": False, "message": ""},
            {
                "claimed": [_AC_ID],
                "excluded_claimed": [],
                "target_refused": False,
            },
            {"claimed": [_AC_ID], "target_refused": False},
        ):
            with self.subTest(reply=reply):
                result = _run_lane(reply)
                self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
                as_text = str(result.result or {}).lower()
                for marker in _NOT_ATTEMPTED_MARKERS:
                    self.assertNotIn(
                        marker,
                        as_text,
                        f"A claim reporting {len(reply['claimed'])} claimed "
                        f"id(s) was described as never attempted "
                        f"('{marker}'). Reply: {reply}",
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
        required = _declared_required_fields_for_claim_dispatch()
        self.assertIn(
            "claimed",
            required,
            "The claim dispatch must at minimum require `claimed`; the "
            "extractor found a different schema.",
        )

        # A minimal reply: exactly the declared required fields, nothing more.
        # Values are chosen to describe a fully successful claim.
        minimal: dict[str, Any] = {}
        for field in required:
            if field == "claimed":
                minimal[field] = [_AC_ID]
            elif field == "excluded_claimed":
                minimal[field] = []
            elif field == "target_refused":
                minimal[field] = False
            else:
                minimal[field] = ""

        result = _run_lane(minimal)

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        self.assertIn(
            _LABEL_AFTER_CLAIM,
            _labels_seen(result),
            f"A reply carrying exactly the dispatch's OWN declared required "
            f"fields {required} was judged unusable. The gate demands more "
            f"than the contract it declared. Result: {result.result}",
        )


class TestDeclineStillHaltsAsNotAttempted(unittest.TestCase):
    """Descriptor 4 (angle: criterion) — non-regression over BO-2400f-7-iii.

    The opposed arm. A fix that simply stops checking the reply passes
    descriptors 1-3 and fails here.
    """

    def test_a_performer_that_declines_still_halts_as_not_attempted(self) -> None:
        # covers: BO-2400f-7-iv
        # angle: criterion
        decline_reply = {
            "claimed": [],
            "excluded_claimed": [],
            "target_refused": True,
            "message": "declining to run a store-mutating command",
        }
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
