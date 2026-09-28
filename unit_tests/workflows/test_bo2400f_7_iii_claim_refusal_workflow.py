"""
MODULE: unit_tests/workflows/test_bo2400f_7_iii_claim_refusal_workflow.py
GOAL: RED behavioural (workflow-level) tests for BO-2400f-7-iii — the claim
      phase in fast-lane-ship.js's ONLY correctly-shaped dispatch must be one
      that is ACTUALLY made by a performer permitted to change the store, and
      a role refusal must never be reported as another run's contention.

=== The defect (BO-2400f-7-iii) ===

Observed 2026-09-23 on a fast-lane run aimed at BO-3500. The run passed
Worktree, Verify, Resolve, and Producibility, then reached the claim step:

    const claimResult = await agent(
      `...If the command exits non-zero or target_refused is true, the
      connected set is already in_progress (owned by a concurrent run)...`,
      { agentType: "status-checker", ..., label: "claim-connected", ... }
    );

    if (!claimResult || claimResult.target_refused) {
      return {
        status: "halt",
        message: "connected set already claimed / in progress — a concurrent
          fast-lane run owns these ACs. Wait for that run to complete or
          release stuck claims. Detail: ${JSON.stringify(claimResult)}",
        ...
      };
    }

Two faults, both load-bearing here:

  1. The claim step — a repository-mutating command — is dispatched to
     `status-checker`, whose config/agent_registry.json entry declares
     `permits_shell: false` and whose charter is investigating/reporting
     state, not changing it. Asked to run a command that flips ACs from
     todo to in_progress, it declined — correctly.

  2. The prompt instructs the agent that a non-zero exit OR a
     `target_refused: true` flag means the set is "already in_progress
     (owned by a concurrent run)". A role refusal (no attempt made,
     `claimed: []`, `excluded_claimed: []`) is folded into the exact same
     contention branch as genuine contention (the CLI actually ran and
     found members held elsewhere, named in `excluded_claimed`). The
     2026-09-23 payload carried `claimed: []` and `excluded_claimed: []`
     while the halt asserted "owns these ACs" — nothing was held by anyone.

=== Why this is not a grep test ===

Every assertion below drives fast-lane-ship.js through run_workflow_under_e2(),
which executes the script's REAL top-level control flow in a Node.js
subprocess (see _workflow_engine_harness.py) and records every agent()
dispatch verbatim, plus the script's own terminal return value. Nothing here
inspects the JS source text for a string or an agent name — see
"Gate / Workflow ACs — Verify Behaviorally, Not by Grep" in this repo's
CLAUDE.md. In particular, test 5 below asserts on the `agentType` the harness
recorded for the ACTUAL "claim-connected" dispatch the run made — not on a
constant read from the source — because a constant naming the right performer
proves nothing about which performer the claim step actually passes to (this
file's own history: the release path's executor was corrected in a later
change and the claim path was left on the wrong one, undetected).
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

_WORKFLOW_PATH = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"

_AC_ID = "BO-STUB-1"
_BRANCH = f"fast-lane/{_AC_ID}"

# Language a contention report is allowed to use. If any of these substrings
# appear in a halt produced from an input carrying an EMPTY held/excluded set,
# that halt is asserting ownership no payload actually supports — the exact
# 2026-09-23 shape.
_CONTENTION_MARKERS = (
    "concurrent",
    "owns these",
    "owned by",
    "already claimed",
    "already in_progress",
    "held by another",
)

# Language a "the claim was never attempted" halt must use, distinguishing it
# from a contention halt. The remedy differs (change who attempts it, vs.
# wait/release), so the wording must differ too.
_NOT_ATTEMPTED_MARKERS = (
    "never attempted",
    "not attempted",
    "was not attempted",
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


def _run_lane(
    claim_response: Any, extra_label_responses: dict[str, Any] | None = None
) -> HarnessResult:
    """Drive fast-lane-ship.js from Worktree through the claim step.

    Supplies just enough for the run to reach "claim-connected": an opened
    worktree and a non-empty resolved connected set (Producibility already
    defaults to "producible" via the harness's built-in default for this
    script — see _default_label_responses_for_script). The caller controls
    only the claim step's own reply.
    """
    tmp = tempfile.TemporaryDirectory()
    try:
        worktree_root = Path(tmp.name)
        (worktree_root / "docs" / "acceptance-criteria").mkdir(parents=True)
        label_responses = {
            "fastlane-worktree": _opened_worktree_payload(str(worktree_root)),
            "resolve-connected": {"ac_ids": [_AC_ID], "message": "1 to build"},
            "claim-connected": claim_response,
            **(extra_label_responses or {}),
        }
        return run_workflow_under_e2(
            _WORKFLOW_PATH,
            label_responses=label_responses,
            args={"ac": _AC_ID},
        )
    finally:
        tmp.cleanup()


def _calls_with_label(result: HarnessResult, label: str) -> list:
    return [c for c in result.agent_calls if c.label == label]


def _labels_seen(result: HarnessResult) -> list[str | None]:
    return [c.label for c in result.agent_calls]


class TestPerformerThatDeclinesToAttemptTheClaimHaltsAsNotAttempted(
    unittest.TestCase
):
    """Descriptor 1 (angle: failure).

    The claim step's dispatch returns a refusal-shaped reply — no attempt was
    made, nothing is claimed, nothing is excluded — rather than a genuine
    result. The run must halt saying the claim was never attempted, not that
    the set is held by a concurrent run.
    """

    def test_a_performer_that_declines_to_attempt_the_claim_halts_as_not_attempted(
        self,
    ) -> None:
        # covers: BO-2400f-7-iii
        # angle: failure
        decline_reply = {
            "claimed": [],
            "excluded_claimed": [],
            "target_refused": True,
            "message": (
                "status-checker cannot run commands that mutate the AC "
                "store; declining to run "
                "'python3 fast_lane.py claim --ac-ids BO-STUB-1'."
            ),
        }
        result = _run_lane(decline_reply)

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result or {}
        as_text = str(payload).lower()

        self.assertTrue(
            any(marker in as_text for marker in _NOT_ATTEMPTED_MARKERS),
            f"A performer that declines to attempt the claim must halt "
            f"saying the claim was NEVER ATTEMPTED. Got: {payload}",
        )
        for marker in _CONTENTION_MARKERS:
            self.assertNotIn(
                marker,
                as_text,
                f"A declined attempt must not be reported using contention/"
                f"ownership language ('{marker}' found). Got: {payload}",
            )


class TestHaltDoesNotClaimTheSetIsHeldByAnotherRun(unittest.TestCase):
    """Descriptor 2 (angle: criterion).

    Checks the not-attempted halt specifically for contention language and
    for any assertion of concurrent ownership — neither may be present.
    """

    def test_that_halt_does_not_claim_the_set_is_held_by_another_run(
        self,
    ) -> None:
        # covers: BO-2400f-7-iii
        # angle: criterion
        decline_reply = {
            "claimed": [],
            "excluded_claimed": [],
            "target_refused": True,
            "message": "role declined to run the claim command",
        }
        result = _run_lane(decline_reply)

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result or {}
        as_text = str(payload).lower()

        for marker in _CONTENTION_MARKERS:
            self.assertNotIn(
                marker,
                as_text,
                f"The not-attempted halt must not assert concurrent "
                f"ownership ('{marker}' found). Got: {payload}",
            )
        # No held member may be named either — there is nothing to name; the
        # AC id itself must not appear as though it were a held member (it
        # would legitimately appear in worktree_path/branch/ac_ids fields
        # unrelated to a held-set claim, so this check is scoped to the
        # contention vocabulary above, not to bare AC-id presence).


class TestGenuineContentionStillReportsContentionAndNamesTheMembers(
    unittest.TestCase
):
    """Descriptor 3 (angle: criterion) — the non-regression arm.

    A claim that IS attempted (the CLI ran) and genuinely finds members
    already held must still report contention, naming the held members.
    Fails any fix that turns EVERY claim failure into "not attempted".
    """

    def test_genuine_contention_still_reports_contention_and_names_the_members(
        self,
    ) -> None:
        # covers: BO-2400f-7-iii
        # angle: criterion
        contention_reply = {
            "claimed": [],
            "excluded_claimed": [_AC_ID],
            "target_refused": True,
            "message": f"{_AC_ID} is already in_progress, held by run wf_abc123.",
        }
        result = _run_lane(contention_reply)

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result or {}
        as_text = str(payload)

        self.assertNotEqual(
            payload.get("status"),
            "ok",
            f"Genuine contention must not be reported as a successful run. "
            f"Got: {payload}",
        )
        self.assertIn(
            _AC_ID,
            as_text,
            f"The held member must be named in the halt payload. Got: {payload}",
        )
        as_text_lower = as_text.lower()
        self.assertTrue(
            any(
                marker in as_text_lower
                for marker in (
                    "held",
                    "in_progress",
                    "in progress",
                    "concurrent",
                    "owned by",
                )
            ),
            f"Genuine contention must still be reported as contention "
            f"(not silently relabelled as 'not attempted'). Got: {payload}",
        )


class TestContentionReportNamingNoHeldMemberIsImpossible(unittest.TestCase):
    """Descriptor 4 (angle: boundary) — LOAD-BEARING.

    No input may produce contention/ownership language while excluded_claimed
    is empty. Sweeps several distinct shapes a role-declining or otherwise
    non-attempting performer might plausibly emit, so a fix that merely
    relabels the ONE observed 2026-09-23 message does not accidentally pass.
    """

    def _assert_no_contention_with_empty_held(
        self, claim_reply: Any, case_name: str
    ) -> None:
        result = _run_lane(claim_reply)
        self.assertIsNotNone(result.result, f"[{case_name}] stderr={result.stderr!r}")
        payload = result.result or {}
        as_text = str(payload).lower()
        for marker in _CONTENTION_MARKERS:
            self.assertNotIn(
                marker,
                as_text,
                f"[{case_name}] A payload with an empty held/excluded set "
                f"must never produce contention language ('{marker}' "
                f"found). Got: {payload}",
            )

    def test_a_contention_report_naming_no_held_member_is_impossible(
        self,
    ) -> None:
        # covers: BO-2400f-7-iii
        # angle: boundary
        cases: list[tuple[str, Any]] = [
            (
                "exact-2026-09-23-shape",
                {
                    "claimed": [],
                    "excluded_claimed": [],
                    "target_refused": True,
                    "message": "declining to run a repository-mutating command",
                },
            ),
            (
                "target-refused-with-no-message",
                {"claimed": [], "excluded_claimed": [], "target_refused": True},
            ),
            (
                "null-claim-result",
                None,
            ),
            (
                "refusal-shaped-reply-missing-required-fields",
                {
                    "status": "refused",
                    "reason": "role_forbids_repository_mutation",
                    "message": "status-checker cannot mutate the AC store",
                },
            ),
        ]
        for case_name, claim_reply in cases:
            with self.subTest(case=case_name):
                self._assert_no_contention_with_empty_held(claim_reply, case_name)


class TestTheClaimIsAttemptedByAPerformerPermittedToChangeTheStore(
    unittest.TestCase
):
    """Descriptor 5 (angle: seam) — LOAD-BEARING.

    Asserted on the DISPATCH the run actually makes for the "claim-connected"
    label, not on a constant read from the source. A constant naming the
    right performer proves nothing about which performer the claim step
    passes to — this file's own history is the argument: the release path's
    executor was corrected to a different performer and the claim path was
    left unchanged in the same file, and nothing detected the divergence.
    """

    def test_the_claim_is_attempted_by_a_performer_permitted_to_change_the_store(
        self,
    ) -> None:
        # covers: BO-2400f-7-iii
        # angle: seam
        success_reply = {
            "claimed": [_AC_ID],
            "excluded_claimed": [],
            "target_refused": False,
            "message": "claimed 1 ACs",
        }
        result = _run_lane(success_reply)

        claim_calls = _calls_with_label(result, "claim-connected")
        self.assertTrue(
            claim_calls,
            f"The claim step must actually be dispatched under the "
            f"'claim-connected' label. Labels seen: {_labels_seen(result)}. "
            f"stderr={result.stderr!r}",
        )
        dispatched_agent_type = claim_calls[0].agent_type
        self.assertNotEqual(
            dispatched_agent_type,
            "status-checker",
            f"The claim step is a repository-mutating command. Its declared "
            f"charter (config/agent_registry.json: status-checker declares "
            f"permits_shell: false) forbids changing the store, so it must "
            f"not be the performer dispatched for 'claim-connected'. "
            f"Actual dispatched agentType: {dispatched_agent_type!r}",
        )


if __name__ == "__main__":
    unittest.main()
