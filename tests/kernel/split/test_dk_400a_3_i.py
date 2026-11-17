"""
MODULE: tests.kernel.split.test_dk_400a_3_i
GOAL: Prove a question that lists alternatives ("or") and constraints ("and") is one question: no
    split starts, the run goes on as one decision, the bundle question states those boundary
    cases literally, and a checked-in labelled eval set measures false positives (DK-400a-3-i).
BUSINESS CONTEXT: "Should this new capability be an atomic node or an encapsulated subgraph, given
    that it must be resumable and traced?" is the likeliest false positive for a split. Jev's real
    answer cannot be asserted offline, so these tests prove the kernel acts only on the answer and
    that the question Jev receives carries the boundary cases.
ARCHITECTURE: Real KernelService through the scenario rig and the shipped CLI main(); only Jev is
    scripted. Every test enables splitting through a config override. The eval set is a checked-in
    JSON file (tests/kernel/fixtures/eval/split_bundle.json) read by
    tests/kernel/split/eval_runner.py, which exposes EVAL_SET, load_cases() and
    score(cases, probabilities, threshold) -> {"false_positives": n, "false_negatives": n}.
    These tests are RED until the bundle template states the boundary cases and the eval set and
    harness are checked in.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import re
from typing import Any

from kernel.adapters.cli import main
from kernel.contracts import RunStatus
from kernel.split.detect import BUNDLE_TEMPLATE_ID, bundle_question
from tests.kernel.split.support_400c import MOCK
from tests.kernel.split.test_dk_400a_3 import SingleCase

GOAL = ("Should this new capability be an atomic node or an encapsulated subgraph, given that "
        "it must be resumable and traced?")
OR_RULE = re.compile(r"alternatives joined by ['\"]or['\"]", re.I)
AND_RULE = re.compile(r"(constraints|conditions)( or (constraints|conditions))? joined by "
                      r"['\"]and['\"]", re.I)
TREE_IDS = {"retention-period", "node-or-subgraph", "reusable-criteria", "decision-records",
            "trace-analyzers", "reuse-threshold-research"}


def _bundle_instructions(case: Any) -> list[str]:
    """Return the instructions of every bundle question any recorded Jev batch held."""
    return [str(q.instructions) for b in case.jev.batches for q in b.questions if "bundl" in q.id]


def _mock_subject(record_id: str) -> str:
    """Return the subject_text of a reviewed mock record, verbatim from disk."""
    data = json.loads(MOCK.read_text(encoding="utf-8"))
    stack: list[Any] = [data]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("id") == record_id:
                return node["subject_text"]
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    raise AssertionError(record_id)


class NodeOrSubgraph(SingleCase):
    """The node-or-subgraph question with its constraint clause."""

    def goal_task(self) -> Any:
        """Return the AC's goal as a task."""
        return super().goal_task().model_copy(update={"goal": GOAL})


class TestOneQuestion(NodeOrSubgraph):
    """Below the threshold the question goes on as one decision."""

    async def test_alternatives_and_constraints_question_not_split(self) -> None:
        # covers: DK-400a-3-i
        # angle: criterion
        """Bundle 0.2 (below 0.8), splitting on: precedent step, no split, boundary text sent."""
        self.arrange(enabled=True, bundle=0.2)
        service = self.service()
        seen, final = await self.drive(service)
        values = await self.checkpoint_values(final.run_id)
        self.assertEqual(self.splits_of(values), [])
        self.assertIn("decision", self.capabilities_used(values))
        self.assertNotIn("decompose_goal", [op for _, op in seen if op])
        # The question really was asked, and carried the boundary cases to Jev.
        sent = _bundle_instructions(self)
        self.assertEqual(len(sent), 1)
        self.assertRegex(sent[0], OR_RULE)
        self.assertRegex(sent[0], AND_RULE)

    async def test_at_threshold_the_same_question_would_split(self) -> None:
        # covers: DK-400a-3-i
        # angle: discrimination
        """Control: bundle 0.9 starts a split, so the 0.2 case passes because of the answer only.

        Wrong version caught: a keyword rule that never splits a goal containing 'or'/'and'.
        """
        self.arrange(enabled=True, bundle=0.9)
        envelope = await self.service().start_run(self.goal_task())
        self.assertEqual(envelope.status, RunStatus.WAITING_HOST)
        values = await self.checkpoint_values(envelope.run_id)
        self.assertEqual(len(self.splits_of(values)), 1)


class TestTemplate(NodeOrSubgraph):
    """The compiled bundle question states the boundary cases literally."""

    def test_bundle_question_template_carries_boundary_cases(self) -> None:
        # covers: DK-400a-3-i
        # angle: criterion
        """Template id and version are set; 'or' alternatives and 'and' constraints are one question."""
        question = bundle_question("wi-1", "state.root_goal")
        self.assertEqual(question.template_id, BUNDLE_TEMPLATE_ID)
        self.assertTrue(question.template_version)
        text = str(question.instructions)
        self.assertRegex(text, OR_RULE)
        self.assertRegex(text, AND_RULE)
        self.assertIn("one question", text.lower())
        self.assertEqual(question.kind, "noul")  # still one literal judgement


class TestEvalSet(NodeOrSubgraph):
    """The checked-in eval set loads in the eval harness and labels every tree example."""

    def test_bundle_eval_set_covers_tree_examples(self) -> None:
        # covers: DK-400a-3-i
        # angle: real_artifact
        """Every tree example is labelled single or bundled; mock-derived goals match the mock."""
        from tests.kernel.split import eval_runner  # absent until the coder adds the harness

        self.assertTrue(eval_runner.EVAL_SET.is_file())
        cases = eval_runner.load_cases()
        by_id = {c["id"]: c for c in cases}
        self.assertEqual(len(by_id), len(cases))  # ids are unique
        self.assertTrue(TREE_IDS <= set(by_id), TREE_IDS - set(by_id))
        for case in cases:
            self.assertIn(case["label"], ("single", "bundled"))
            self.assertTrue(case["goal"].strip())
        self.assertEqual(by_id["node-or-subgraph"]["goal"], GOAL)
        self.assertEqual(by_id["node-or-subgraph"]["label"], "single")
        self.assertEqual(by_id["retention-period"]["label"], "single")
        self.assertEqual(by_id["reusable-criteria"]["label"], "bundled")
        self.assertEqual(by_id["decision-records"]["label"], "bundled")
        # Goals of the reviewed mock records are taken verbatim from the artifact on disk.
        self.assertEqual(by_id["reusable-criteria"]["goal"],
                         _mock_subject("dcp-reusable-criteria-by-hand"))
        self.assertEqual(by_id["decision-records"]["goal"],
                         _mock_subject("dcp-decision-records-bundled"))
        self.assertEqual(by_id["reuse-threshold-research"]["goal"],
                         _mock_subject("dcp-reuse-threshold-research"))
        self.assertEqual(by_id["trace-analyzers"]["goal"],
                         _mock_subject("dcp-trace-analyzers-rejected"))

    def test_eval_score_counts_false_positives_and_negatives(self) -> None:
        # covers: DK-400a-3-i
        # angle: boundary
        """score() reports exact counts at the inclusive threshold: 1 false positive, 1 negative."""
        from tests.kernel.split import eval_runner  # absent until the coder adds the harness

        cases = eval_runner.load_cases()
        singles = [c["id"] for c in cases if c["label"] == "single"]
        bundled = [c["id"] for c in cases if c["label"] == "bundled"]
        self.assertTrue(singles and bundled)
        perfect = {**{i: 0.1 for i in singles}, **{i: 0.95 for i in bundled}}
        self.assertEqual(eval_runner.score(cases, perfect, 0.8),
                         {"false_positives": 0, "false_negatives": 0})
        wrong = {**perfect, singles[0]: 0.8, bundled[0]: 0.79}  # at threshold counts as bundled
        self.assertEqual(eval_runner.score(cases, wrong, 0.8),
                         {"false_positives": 1, "false_negatives": 1})


class TestEntryPoint(NodeOrSubgraph):
    """The shipped CLI main() with real argv reaches the behaviour."""

    async def test_dk_400a_3_i_reachable_from_entry_point(self) -> None:
        # covers: DK-400a-3-i
        # angle: reachability
        """`kernel run --input-file` via cli.main: one decision, no split, boundary text asked."""
        self.arrange(enabled=True, bundle=0.2)
        path = self.run_root.parent / "task.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.goal_task().model_dump_json(), encoding="utf-8")

        def factory(**_: Any) -> Any:
            self.service()
            return self.env

        out = io.StringIO()

        def run_cli() -> int:
            with contextlib.redirect_stdout(out):
                return main(["run", "--input-file", str(path), "--json"], environment=factory)

        code = await asyncio.to_thread(run_cli)  # main() owns its own event loop
        self.assertEqual(code, 0)
        document = json.loads([ln for ln in out.getvalue().splitlines() if ln.strip()][-1])
        sent = _bundle_instructions(self)
        self.assertEqual(len(sent), 1)
        self.assertRegex(sent[0], OR_RULE)
        values = await self.checkpoint_values(document["run_id"])
        self.assertEqual(self.splits_of(values), [])
        self.assertIn("decision", self.capabilities_used(values))
