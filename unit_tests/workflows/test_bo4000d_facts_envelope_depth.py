"""
MODULE: unit_tests/workflows/test_bo4000d_facts_envelope_depth.py
GOAL: Behavioral tests for BO-4000d — a repository-facts reply that comes
    back wrapped in a SECOND reply envelope (the status-checker agent puts a
    complete {"output": "<raw stdout>", "exit_code": 0} envelope into the
    outer envelope's own `output` field, instead of the raw stdout) must
    still be read, so a fact the helper reported correctly never counts as
    unavailable.
BUSINESS CONTEXT: FIELD EVIDENCE — every /build-feature epic run aborted in
    Phase 0 with abort_reason 'worktree-base-unavailable' and built nothing,
    although scripts/worktree_repo_facts.py returned correct JSON. Reproduced
    twice on 2026-09-25 (runs wf_6d6f8dda-97e and wf_f898fd1a-412) against
    EPIC-TruthfulProjectRecord: both the worktree-facts-resolved and
    worktree-base steps succeeded, but the workflow read no fields from them.
    See docs/acceptance-criteria/build-orchestration/BO-4000d.yaml.
ARCHITECTURE: Every test drives templates/workflows-js/build-feature.js's
    own top-level body through unit_tests/_workflow_engine_harness.py,
    asserting on which agents were dispatched, the terminal abort payload,
    and the paths in phase prompts — never on source text (BO-4000d's own
    test_rationale: a test of worktree_repo_facts.py or of an extracted
    parse helper proves nothing here; the defect lives only in how
    build-feature's own body reads the relayed reply).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests._workflow_engine_harness import run_workflow_under_e2  # noqa: E402
from unit_tests.workflows import _bo4000_fixtures as bfx  # noqa: E402

_BUILD_FEATURE_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"

TICKET = "tickets/00_inbox/epics/EPIC-TruthfulProjectRecord/07_TICKET-x.md"


def _run(label_responses):
    return run_workflow_under_e2(
        _BUILD_FEATURE_JS, label_responses=label_responses, args={"target": bfx.EPIC_NAME}
    )


def _worktree_setup_calls(result):
    return [c for c in result.agent_calls if c.label == "worktree-setup"]


def _ticket_planner_calls(result):
    return [c for c in result.agent_calls if c.label == "ticket-planner"]


def _abort_reason(result):
    payload = result.result or {}
    return payload.get("abort_reason") if isinstance(payload, dict) else None


class TestDoubleWrappedFactsEnvelopeStillYieldsTheFactsObject(unittest.TestCase):
    def test_double_wrapped_facts_envelope_still_yields_the_facts_object(self) -> None:
        # covers: BO-4000d
        # angle: criterion
        """Incident replay: the status-checker stub answers BOTH the
        worktree-facts-resolved read and the worktree-base read one level
        too deep — the value it puts in the envelope's `output` field is
        itself a complete {"output": ..., "exit_code": 0} envelope rather
        than the helper's raw stdout. The workflow must still obtain
        worktree_base (and the resolved-worktree facts) and proceed past
        the worktree step, instead of aborting with
        abort_reason 'worktree-base-unavailable' as the incident recorded.
        """
        base_payload = {
            "main_checkout": bfx.MAIN_CHECKOUT,
            "worktree_base": bfx.WORKTREE_BASE,
            "layout": "dev",
        }
        resolved_facts_payload = bfx.facts(
            is_git_toplevel=False, is_linked_worktree=False,
        )  # not reusable -> falls through to scenario 2 (worktree-base read)

        responses = bfx.success_label_responses(
            ticket_paths=[TICKET],
            resolved_worktree_path=bfx.UXP_WORKTREE,
        )
        # Double-wrap: outer envelope's `output` is itself a full envelope.
        responses["worktree-facts-resolved"] = bfx.envelope(bfx.envelope(resolved_facts_payload))
        responses["worktree-base"] = bfx.envelope(bfx.envelope(base_payload))

        result = _run(responses)

        self.assertNotEqual(
            _abort_reason(result), "worktree-base-unavailable",
            f"aborted with worktree-base-unavailable despite a correctly-reported "
            f"(if double-wrapped) base; result={result.result!r} stderr={result.stderr!r}",
        )
        dispatched = _worktree_setup_calls(result) or _ticket_planner_calls(result)
        self.assertTrue(
            dispatched,
            f"no phase agent dispatched after the worktree step; "
            f"result={result.result!r} stderr={result.stderr!r}",
        )


class TestPlainFactsEnvelopeIsParsedOnceAndReturnedUnchanged(unittest.TestCase):
    def test_plain_facts_envelope_is_parsed_once_and_returned_unchanged(self) -> None:
        # covers: BO-4000d
        # angle: boundary
        """Paired negative control: with the status-checker stub answering
        at the EXPECTED depth (the envelope's `output` field holds the raw
        stdout directly, not a nested envelope), the run proceeds normally.
        This must stay true after the fix — it is the case a naive
        always-parse-twice fix (M2) would break by stripping a facts object
        that legitimately carries its own `output`/`exit_code`-shaped
        fields.
        """
        result = _run(bfx.success_label_responses(ticket_paths=[TICKET]))
        self.assertNotEqual(_abort_reason(result), "worktree-base-unavailable")
        setup_calls = _worktree_setup_calls(result)
        self.assertTrue(
            setup_calls,
            f"no worktree-setup call on the plain (single-wrapped) envelope path; "
            f"result={result.result!r} stderr={result.stderr!r}",
        )
        self.assertIn(bfx.NAMED_LOCATION, setup_calls[0].prompt or "")


class TestUnparseableOrFailedFactsReadStillRefusesWithoutGuessing(unittest.TestCase):
    def test_unparseable_or_failed_facts_read_still_refuses_without_guessing(self) -> None:
        # covers: BO-4000d
        # angle: failure
        """Non-JSON output, a non-zero exit_code, and no reply at all must
        each still leave the run refusing with the existing
        worktree-undetermined abort rather than guessing a worktree base —
        the guard a naive unwrap-and-default fix (M3) would erode.
        """
        cases = {
            "not-json": {"output": "not valid json {{{", "exit_code": 0},
            "nonzero-exit": bfx.envelope({"main_checkout": bfx.MAIN_CHECKOUT, "worktree_base": bfx.WORKTREE_BASE, "layout": "dev"}) | {"exit_code": 1},
            "no-reply": None,
        }
        for case_name, bad_response in cases.items():
            with self.subTest(case=case_name):
                responses = bfx.success_label_responses(ticket_paths=[TICKET])
                if bad_response is None:
                    responses.pop("worktree-base", None)
                else:
                    responses["worktree-base"] = bad_response
                result = _run(responses)
                payload = result.result or {}
                self.assertTrue(
                    isinstance(payload, dict) and payload.get("worktree_undetermined") is True,
                    f"case={case_name}: expected worktree_undetermined abort; "
                    f"result={result.result!r} stderr={result.stderr!r}",
                )
                self.assertEqual(_worktree_setup_calls(result), [])
                self.assertEqual(_ticket_planner_calls(result), [])


class TestUnwrapIsWiredIntoTheWorkflow(unittest.TestCase):
    def test_facts_envelope_unwrapping_is_reachable_from_the_workflow_top_level_body(self) -> None:
        # covers: BO-4000d
        # angle: reachability
        """All three scenarios (double-wrapped, plain, unparseable) are
        driven through build-feature.js's OWN top-level body via
        _workflow_engine_harness.py — never against an extracted copy of
        repoFactsCall — so a fix wired into the real caller (and not into a
        disconnected helper) is what makes this suite green.
        """
        base_payload = {
            "main_checkout": bfx.MAIN_CHECKOUT,
            "worktree_base": bfx.WORKTREE_BASE,
            "layout": "dev",
        }

        double_wrapped = _run(bfx.success_label_responses(ticket_paths=[TICKET]) | {
            "worktree-base": bfx.envelope(bfx.envelope(base_payload)),
        })
        self.assertNotEqual(_abort_reason(double_wrapped), "worktree-base-unavailable")

        plain = _run(bfx.success_label_responses(ticket_paths=[TICKET]))
        self.assertTrue(_worktree_setup_calls(plain))

        responses = bfx.success_label_responses(ticket_paths=[TICKET])
        responses.pop("worktree-base", None)
        unparseable = _run(responses)
        payload = unparseable.result or {}
        self.assertTrue(isinstance(payload, dict) and payload.get("worktree_undetermined") is True)


if __name__ == "__main__":
    unittest.main()
