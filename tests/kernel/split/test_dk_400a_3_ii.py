"""
MODULE: tests.kernel.split.test_dk_400a_3_ii
GOAL: Prove a caller-supplied decision request (leafcutter.decision_request.v1) is never checked
    for bundling, even when its question bundles several: no bundle question in any Jev batch, no
    split record, no split interaction, and the decision capability gets the caller's question,
    options and criteria unchanged (AC DK-400a-3-ii).
BUSINESS CONTEXT: The caller already named the one decision (its own options and criteria), so
    offering a split would override the caller. The exemption is an exact check on the payload
    schema id (ADR-053), never on goal wording.
ARCHITECTURE: Real KernelService through the scenario rig and the shipped CLI main(); only Jev is
    scripted. Every test enables splitting through a config override and scripts a bundle answer
    of 0.99 so an unexempted request would split. The documentation tests read the ADR and the
    reviewed flow from disk.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
from pathlib import Path
from typing import Any

from kernel.adapters.cli import main
from kernel.contracts import Actor, ActorKind, Criterion, Option, RunStatus, TaskInput, schema_ids
from kernel.contracts.payloads import DecisionRequestPayload
from tests.kernel.helpers import make_scope
from tests.kernel.split.test_dk_400a_3 import SingleCase, _bundle_questions

ROOT = Path(__file__).resolve().parents[3]
FLOW = ROOT / "docs/product-truth/flows/leafcutter/decision-forming.flow.json"
ADR = ROOT / "docs/architecture/adrs/ADR-053-intelligence-selection-deterministic-jev-llm-human.md"
QUESTION = ("Decide which fields a decision record needs, which folder layout the records use and "
            "how record files are named")
OPTIONS = [("yaml", "One YAML record per decision under docs/decisions"),
           ("json", "One JSON record per decision under docs/decisions")]
CRITERIA = [("git", "Git-reviewable"), ("find", "findable by later runs"),
            ("human", "keeps the human approval")]


def _payload() -> dict[str, Any]:
    """Return the AC's decision_request.v1 payload via the real model serializer."""
    return DecisionRequestPayload(
        question=QUESTION, options=[Option(id=i, title=t) for i, t in OPTIONS],
        criteria=[Criterion(id=i, question=q) for i, q in CRITERIA]).model_dump(mode="json")


def _flow_node(node_id: str) -> dict[str, Any]:
    """Return the node of the reviewed flow with the id, read verbatim from disk."""
    stack: list[Any] = [json.loads(FLOW.read_text(encoding="utf-8"))]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if item.get("id") == node_id and "implements" in item:
                return item
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    raise AssertionError(node_id)


class TypedCase(SingleCase):
    """A scenario that starts with the AC's caller-supplied decision request."""

    def goal_task(self) -> TaskInput:
        """Return the bundled-looking question as a typed decision request."""
        return TaskInput(goal=QUESTION, caller=Actor(id="tester", kind=ActorKind.HOST),
                         scope=make_scope(self.repo),
                         input_payload_schema=schema_ids.DECISION_REQUEST,
                         input_payload=_payload())

    def arrange_bundled(self) -> None:
        """Splitting on, bundle probability 0.99: a non-exempt request would split."""
        self.arrange(enabled=True, bundle=0.99)


class TestTypedRequest(TypedCase):
    """The typed request is exempt from the bundling check."""

    async def test_typed_decision_request_never_checked_for_bundling(self) -> None:
        # covers: DK-400a-3-ii
        # angle: criterion
        """No bundle question, no split record, no split interaction; one decision runs."""
        self.arrange_bundled()
        service = self.service()
        seen, final = await self.drive(service)
        values = await self.checkpoint_values(final.run_id)
        self.assertEqual(_bundle_questions(self), [])
        self.assertEqual(self.splits_of(values), [])
        self.assertNotIn("decompose_goal", [op for _, op in seen if op])
        self.assertIn("decision", self.capabilities_used(values))
        self.assertTrue(all(i.split_checked is False for i in values["work_items"].values()))

    async def test_untyped_goal_with_same_wording_is_asked_about(self) -> None:
        # covers: DK-400a-3-ii
        # angle: discrimination
        """Control: the same question as a plain goal is asked about, so the typed request
        passes because of its payload schema and not because splitting is off.

        Wrong version caught: an exemption keyed on goal wording, or splitting never on.
        """
        self.arrange_bundled()
        self.route_choice = "__NONE__"
        task = TaskInput(goal=QUESTION, caller=Actor(id="tester", kind=ActorKind.HOST),
                         scope=make_scope(self.repo))
        envelope = await self.service().start_run(task)
        self.assertEqual(len(_bundle_questions(self)), 1)
        self.assertEqual(envelope.status, RunStatus.WAITING_HOST)

    async def test_typed_decision_request_payload_reaches_decision_unchanged(self) -> None:
        # covers: DK-400a-3-ii
        # angle: seam
        """The decision invocation's request holds the caller's question, options, criteria."""
        self.arrange_bundled()
        _, final = await self.drive(self.service())
        values = await self.checkpoint_values(final.run_id)
        sent = _payload()
        roots = [values["requests"][i.request_id] for i in values["work_items"].values()
                 if i.depth == 0]
        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].payload_schema, schema_ids.DECISION_REQUEST)
        found = [roots[0].payload]
        self.assertTrue(any(p.get("question") == sent["question"]
                            and p.get("options") == sent["options"]
                            and p.get("criteria") == sent["criteria"] for p in found), found)


class TestEntryPoint(TypedCase):
    """The shipped CLI main() with real argv reaches the behaviour."""

    async def test_dk_400a_3_ii_reachable_from_entry_point(self) -> None:
        # covers: DK-400a-3-ii
        # angle: reachability
        """`kernel run --input-file` via cli.main: typed request, no bundle question, no split."""
        self.arrange_bundled()
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
        self.assertGreater(self.jev.call_count, 0)  # the run really reached Jev elsewhere
        self.assertEqual(_bundle_questions(self), [])
        values = await self.checkpoint_values(document["run_id"])
        self.assertEqual(self.splits_of(values), [])


class TestDocumentation(TypedCase):
    """The ADR and the reviewed flow state the exemption (the ticket's deliverables)."""

    def test_adr_053_states_exact_check_before_any_jev_question(self) -> None:
        # covers: DK-400a-3-ii
        # angle: real_artifact
        """ADR-053 names DK-400a-3-ii, the payload schema id and that the check is exact."""
        text = " ".join(ADR.read_text(encoding="utf-8").split())
        self.assertIn("DK-400a-3-ii", text)
        self.assertIn(schema_ids.DECISION_REQUEST, text)
        self.assertRegex(text, r"(?i)exact check[^.]*before any (Jev|bundle)")

    def test_flow_node_split_typed_request_is_no_longer_not_started(self) -> None:
        # covers: DK-400a-3-ii
        # angle: real_artifact
        """The reviewed flow node reflects the built exemption and still implements the AC."""
        node = _flow_node("split-typed-request")
        self.assertIn("DK-400a-3-ii", node["implements"])
        self.assertIn(node["impl_status"], ("in_progress", "done"))
        self.assertGreaterEqual(node["impl_asof"], "2026-10-09")
