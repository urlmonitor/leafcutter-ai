"""
MODULE: unit_tests/workflows/test_bo2400a_1_iv_test_writer_ask.py
GOAL: RED behavioural (workflow-level) tests for BO-2400a-1-iv — the fast lane must
      ask its test-writer for the proof obligations the criterion declares, not for
      one minimal test per AC.

=== The defect (BO-2400a-1-iv) ===

Measured on the 2026-09-28 BO-3500 run, the first lane run to complete the full arc.
Every AC in that batch declares 5-10 ``test_spec`` descriptors; every generated test
file contained exactly ONE test. Direct counts: BO-3500a-1 declared 5 and got 1,
BO-3500b-1 declared 6 and got 1, BO-3500c-1 declared 10 and got 1.

The cause is the request, not the performer. ``fast-lane-ship.js`` asked, verbatim:

    For each AC id above, read its YAML from ${acStoreRoot} and write a minimal
    failing test that asserts the AC behavior.

"a minimal failing test" — singular — and no mention of ``test_spec`` or of angles at
all. ``test-writer``'s own template has carried the full taught angle vocabulary since
BP-1100g-1; the lane simply never asked it to use any of it.

=== Why one test per AC BUYS a phantom implementation ===

This is not merely thin coverage. Per docs/testing/test-angles.md, under this repo's
TDD order the coder's contract is literally "make the red baseline green", so the
cheapest green is exactly the shape of the test that was written. A lone criterion-angle
test therefore does not merely fail to catch an unwired module — it positively permits
one. The same BO-3500 run's review refused four new modules whose only callers were
their own unit tests, which is that prediction coming true. The same document records
the identical shape in PR #422, where the BO-2400f-7..10 lifecycle functions shipped
unit-tested but unreachable.

Hence the floor these tests assert is criterion PLUS reachability, not "more tests".

=== Why these assert on the recorded dispatch ===

A prompt's only observable surface is the dispatch actually made. Every assertion here
drives fast-lane-ship.js through run_workflow_under_e2(), which executes the script's
REAL control flow in a Node subprocess and records each agent() call verbatim, then
reads the prompt the run passed. That is the same vehicle and the same argument as
BO-2400f-7-iii's performer assertion: a test that greps the workflow file for a phrase
would pass on an unreachable string constant, whereas the recorded dispatch proves the
run actually asked for it.
"""
from __future__ import annotations

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
_TEST_WRITER_LABEL = "test-writer-connected"

# The singular ask that produced the defect. Matched loosely enough to catch a reworded
# singular ("a single minimal test", "one minimal failing test") rather than only the
# exact 2026-09-28 wording.
_SINGULAR_ASK = re.compile(
    r"\b(a|one|a single)\s+minimal\s+(failing\s+)?test\b", re.IGNORECASE
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


def _run_lane_to_test_writer() -> HarnessResult:
    """Drive fast-lane-ship.js far enough to make the test-writer dispatch."""
    tmp = tempfile.TemporaryDirectory()
    try:
        worktree_root = Path(tmp.name)
        (worktree_root / "docs" / "acceptance-criteria").mkdir(parents=True)
        label_responses = {
            "fastlane-worktree": _opened_worktree_payload(str(worktree_root)),
            "resolve-connected": {"ac_ids": [_AC_ID], "message": "1 to build"},
            "claim-connected": {
                "claimed": [_AC_ID],
                "excluded_claimed": [],
                "target_refused": False,
            },
        }
        return run_workflow_under_e2(
            _WORKFLOW_PATH,
            label_responses=label_responses,
            args={"ac": _AC_ID},
        )
    finally:
        tmp.cleanup()


def _test_writer_prompts(result: HarnessResult) -> list[str]:
    return [
        (c.prompt or "")
        for c in result.agent_calls
        if c.label == _TEST_WRITER_LABEL
    ]


def _one_test_writer_prompt(case: unittest.TestCase, result: HarnessResult) -> str:
    prompts = _test_writer_prompts(result)
    case.assertEqual(
        len(prompts),
        1,
        f"Expected exactly one {_TEST_WRITER_LABEL} dispatch; got {len(prompts)}. "
        f"Labels seen: {[c.label for c in result.agent_calls]}",
    )
    return prompts[0]


class TestRequestMakesDeclaredObligationsTheDeliverable(unittest.TestCase):
    """Descriptor 1 (angle: criterion).

    The dispatch must direct the performer at the criterion's own declared descriptors
    as what it owes — not merely mention that the store exists.
    """

    def test_the_request_makes_the_declared_proof_obligations_the_deliverable(
        self,
    ) -> None:
        # covers: BO-2400a-1-iv
        # angle: criterion
        result = _run_lane_to_test_writer()
        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        prompt = _one_test_writer_prompt(self, result)

        self.assertIn(
            "test_spec",
            prompt,
            "The test-writer request must name test_spec — the field the criterion "
            "declares its proof obligations in. Without it the performer has no way "
            "to know the declared set is the deliverable.",
        )
        self.assertRegex(
            prompt,
            r"(?i)\bone test (per|for each)\b|\bevery declared\b|\beach declared\b",
            "The request must make the DECLARED SET the deliverable (one test per "
            "declared descriptor). Mentioning test_spec without saying the whole set "
            "is owed leaves the singular ask intact in effect.",
        )


class TestRequestDoesNotAskForASingleMinimalTest(unittest.TestCase):
    """Descriptor 2 (angle: failure).

    The opposed arm: the pre-fix singular wording must be gone. A fix that appends a
    sentence about declared descriptors but leaves 'a minimal failing test' in place
    fails here.
    """

    def test_the_request_does_not_ask_for_a_single_minimal_test(self) -> None:
        # covers: BO-2400a-1-iv
        # angle: failure
        result = _run_lane_to_test_writer()
        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        prompt = _one_test_writer_prompt(self, result)

        match = _SINGULAR_ASK.search(prompt)
        if match is not None:
            self.fail(
                f"The request still asks for a singular minimal test "
                f"({match.group(0)!r} found). That wording is what produced one "
                f"test against criteria declaring five to ten."
            )


class TestRequestAsksForTheReachabilityFloor(unittest.TestCase):
    """Descriptor 3 (angle: criterion).

    80% of coder-assigned ACs carry no test_spec at all (docs/testing/test-angles.md),
    so honouring declared descriptors alone would change nothing for four criteria in
    five. The floor is what covers them — and reachability is the half that prevents
    the phantom implementation.
    """

    def test_the_request_asks_for_the_reachability_floor(self) -> None:
        # covers: BO-2400a-1-iv
        # angle: criterion
        result = _run_lane_to_test_writer()
        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        prompt = _one_test_writer_prompt(self, result)

        self.assertIn(
            "reachability",
            prompt.lower(),
            "The request must name reachability as owed. Without it a criterion "
            "carrying no test_spec still gets only a happy path, and the cheapest "
            "green for that is an unwired module.",
        )
        self.assertRegex(
            prompt,
            r"(?i)entry point",
            "Reachability must be stated in terms of the production entry point — "
            "naming the angle without saying what it means is satisfiable by a "
            "renamed criterion test.",
        )
        self.assertRegex(
            prompt,
            r"(?i)no test_spec|without a test_spec|declares none|carries none",
            "The floor must be stated as applying when the criterion declares "
            "nothing, which is the common case rather than the edge case.",
        )


class TestExactlyOneTestWriterDispatch(unittest.TestCase):
    """Descriptor 4 (angle: boundary) — non-regression over the parent BO-2400a-1.

    Widening WHAT is asked for must not become asking more than once.
    """

    def test_the_test_writer_dispatch_is_still_exactly_one_per_run(self) -> None:
        # covers: BO-2400a-1-iv
        # angle: boundary
        result = _run_lane_to_test_writer()
        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        self.assertEqual(
            len(_test_writer_prompts(result)),
            1,
            "BO-2400a-1 fixes exactly one test-writer dispatch per batch; this "
            "record must not have multiplied it.",
        )


if __name__ == "__main__":
    unittest.main()
