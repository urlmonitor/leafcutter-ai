"""
MODULE: tests.kernel.memory.test_learning_loop_e2e
GOAL: The decision store's learning loop, end to end through the real service and graph (scripted
    Jev transport, fake host, real stores and checkpointer): run 1 decides a design question with
    a ranked human choice and stages a record that `decisions publish` files; run 2 asks the SAME
    goal, finds the record, judges it applicable and asks the short reuse question, and the human's
    `reuse` resolves it with far fewer Jev calls and no host operation or research round; run 3
    asks an unrelated goal and the normal flow runs.
BUSINESS CONTEXT: The first real learning loop of the Decision Kernel (ADR-059, ADR-060): approved
    decisions are filed as reviewable records and later runs reuse them as precedent, but a
    precedent never resolves anything without a human, the kernel never writes the repository
    during a run, and a record exists only after a person published it.
ARCHITECTURE: Builds on the round-6 scenario rig (a repository with enough matching files for the
    real research shape). The memory backend is the real FileColonyMemory over the scenario
    repository; publication goes through the real argparse entry point with --repo-root and a
    config override that points the run root at the scenario's, so nothing touches the checkout.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
from pathlib import Path

from kernel.adapters.cli import main
from kernel.contracts import (
    Actor,
    ActorKind,
    HumanQuestion,
    RunStatus,
    TaskInput,
)
from kernel.memory.codec import load_record_file
from kernel.memory.file_store import FileColonyMemory, staged_files
from kernel.memory.port import DecisionQuery
from kernel.providers.fakes import noul_answer
from tests.kernel.grounding.test_round6_end_to_end import GOAL, Round6Case
from tests.kernel.helpers import as_type, make_scope, narrow
from tests.kernel.integration.scenario_support import answer_human
from tests.kernel.memory.support import CHECKOUT, VOCAB_FILES

UNRELATED = "Which logging library should the scheduler use for structured output?"
LOOKALIKE = ("Decide how Leafcutter should file decision records as Markdown files in a wiki so "
             "later kernel runs can find them: fields, folder layout, approval and corrections.")
CONFIRM_START = "Decision dec-"


class LoopCase(Round6Case):
    """The round-6 rig plus a file memory over its repository and a precedent script."""

    applies = 0.95

    def setUp(self) -> None:
        super().setUp()
        for rel in VOCAB_FILES:
            target = self.repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(CHECKOUT / rel, target)
        rules = self.repo / "templates" / "rules"
        rules.mkdir(parents=True, exist_ok=True)
        for rule in (CHECKOUT / "templates" / "rules").glob("*.md"):
            shutil.copyfile(rule, rules / rule.name)
        self.memory = FileColonyMemory(self.repo, self.run_root, "docs/decisions")
        for purpose in ("decision.precedent", "decision.assess"):
            self.scripted.script(purpose, "precedent.*", lambda q, b: noul_answer(self.applies))

    def service(self):  # noqa: ANN201
        service = super().service()
        assert self.env is not None
        self.env.memory = self.memory
        return service

    def cli(self, *argv: str) -> tuple[int, dict]:
        """Run `python -m kernel decisions ...` against the scenario repository and run root."""
        override = self.repo.parent / "override.json"
        override.write_text(json.dumps({"paths": {"run_root": str(self.run_root),
                                                  "registry": "config/capability_registry.json"}}),
                            encoding="utf-8")
        out = io.StringIO()
        args = [argv[0], argv[1], "--repo-root", str(self.repo), "--config", str(override),
                *argv[2:]]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = main(args)
        return code, json.loads(out.getvalue())

    def staged_for(self, run_id: str):  # noqa: ANN201
        return [load_record_file(p) for p in staged_files(self.run_root, run_id)]

    def purposes_since(self, start: int) -> list[str]:
        """Return the purposes of the Jev batches after the first `start` of them."""
        return [b.purpose for b in self.scripted.batches[start:]]

    async def run_one(self):  # noqa: ANN201
        """Run 1: decide the design question; the human picks the kernel's first choice."""
        final = await self.play()
        question = as_type(narrow(final.pending_interaction), HumanQuestion)
        done = await self.service().resume_run(
            final.run_id, answer_human(final, {"choice_id": question.choices[0].id}))
        return final, done

    async def published(self):  # noqa: ANN201
        """Run run 1 and publish its staged record; return (run 1 envelope, record id)."""
        _, done = await self.run_one()
        self.assertEqual(done.status, RunStatus.COMPLETED, done.limitations)
        code, doc = self.cli("decisions", "publish", "--run-id", done.run_id)
        self.assertEqual((code, doc["ok"]), (0, True), doc)
        (record_id,) = doc["published"]
        return done, record_id

    def goal(self, text: str) -> TaskInput:
        return TaskInput(goal=text, caller=Actor(id="user", kind=ActorKind.HUMAN),
                         scope=make_scope(self.repo))


class TestRunOneStagesARecordThatPublishFiles(LoopCase):
    """Run 1: a design decision, a ranked question, the human picks, a record is staged."""

    async def test_a_human_choice_stages_a_record_and_nothing_is_written_to_the_repository(
            self) -> None:
        # covers: DK-600c-1
        # covers: DK-600c-2
        # covers: DK-600c-3
        # covers: DK-600c-4
        # covers: DK-600d-1
        _, done = await self.run_one()
        self.assertEqual(done.status, RunStatus.COMPLETED, done.limitations)
        self.assertFalse((self.repo / "docs" / "decisions").exists())  # the kernel wrote no repo file
        (record,) = self.staged_for(done.run_id)
        note = next(x for x in done.limitations if x.startswith("decision record staged:"))
        self.assertIn(f"python -m kernel decisions publish --run-id {done.run_id}", note)
        self.assertEqual(record.question, GOAL)
        self.assertEqual(record.approval.approved_by, "human:user")
        self.assertEqual(record.provenance.run_id, done.run_id)
        self.assertEqual(record.provenance.langfuse_trace_id, done.trace_refs.trace_id)
        self.assertEqual(record.assessment.basis, "kernel_ranking")
        self.assertGreaterEqual(len(record.assessment.ranking), 3)
        self.assertEqual(record.id, narrow(done.decision_ids)[0])

    def git_status(self) -> str:
        """Return `git status` of the scenario repository, untracked files listed individually."""
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.test",
               "-c", "commit.gpgsign=false"]
        if not (self.repo / ".git").exists():
            for step in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "scenario"]):
                subprocess.run([*git, *step], cwd=self.repo, check=True, capture_output=True)
        out = subprocess.run([*git, "status", "--porcelain", "--untracked-files=all"],
                             cwd=self.repo, check=True, capture_output=True, text=True)
        return out.stdout

    async def test_a_staging_run_leaves_git_status_unchanged(self) -> None:
        # covers: DK-600c-3
        before = self.git_status()
        self.assertEqual(before, "")  # a clean, committed scenario repository
        _, done = await self.run_one()
        self.assertEqual(done.status, RunStatus.COMPLETED, done.limitations)
        (record,) = self.staged_for(done.run_id)  # the run did stage its record ...
        staged = self.run_root / "runs" / done.run_id / "staged" / "decisions" / f"{record.id}.yaml"
        self.assertTrue(staged.is_file())  # ... at the documented path, outside the repository
        self.assertEqual(self.git_status(), before)  # ... and git sees no change in the repository
        self.assertFalse((self.repo / "docs" / "decisions").exists())

    async def test_cancelling_at_the_ranked_question_stages_no_record(self) -> None:
        # covers: DK-600b-2-iii
        final = await self.play()
        question = as_type(narrow(final.pending_interaction), HumanQuestion)
        self.assertGreaterEqual(len(question.choices), 3)  # the ranked-choice question is open
        self.assertEqual(staged_files(self.run_root, final.run_id), [])  # unanswered: no record
        cancelled = await self.service().cancel_run(
            final.run_id, Actor(id="human:user", kind=ActorKind.HUMAN))
        self.assertEqual(cancelled.status, RunStatus.CANCELLED)
        self.assertIsNone(cancelled.output)  # the decision did not resolve
        self.assertEqual(staged_files(self.run_root, final.run_id), [])
        folder = self.run_root / "runs" / final.run_id / "staged" / "decisions"
        self.assertEqual(list(folder.glob("*")) if folder.is_dir() else [], [])
        self.assertFalse((self.repo / "docs" / "decisions").exists())

    async def test_a_record_kept_staged_is_never_found_as_precedent(self) -> None:
        # covers: DK-600d-1-i
        _, done = await self.run_one()  # run 1 stages its record; nobody publishes it
        (record,) = self.staged_for(done.run_id)
        before = len(self.scripted.batches)
        envelope = await self.service().start_run(self.goal(GOAL))  # a later run, same goal
        self.assertNotIn("decision.precedent", self.purposes_since(before))  # nothing to judge
        self.assertNotEqual(envelope.status, RunStatus.WAITING_HUMAN)  # no reuse question
        values = await self.checkpoint_values(envelope.run_id)
        locators = [e.source.locator for e in values["evidence"].values()]
        self.assertFalse([x for x in locators if record.id in x], locators)
        self.assertEqual(self.memory.find_decisions(DecisionQuery(text=GOAL)), [])
        self.assertFalse((self.repo / "docs" / "decisions").exists())

    async def test_publish_files_a_valid_record_and_the_index(self) -> None:
        # covers: DK-600d-3
        done, record_id = await self.published()
        folder = self.repo / "docs" / "decisions"
        self.assertTrue((folder / f"{record_id}.yaml").is_file())
        self.assertTrue((folder / "index.json").is_file())
        code, doc = self.cli("decisions", "validate")
        self.assertEqual((code, doc["ok"], doc["records"]), (0, True, 1), doc)
        again = self.cli("decisions", "publish", "--run-id", done.run_id)
        self.assertEqual(again[1]["already_present"], [record_id])  # idempotent

    async def test_the_report_and_the_envelope_carry_the_round_eight_fixes(self) -> None:
        # covers: DK-600b-3
        done, _ = await self.published()
        payload = narrow(done.output).payload
        self.assertEqual(payload["trace_refs"]["trace_id"], done.trace_refs.trace_id)  # defect b
        text = Path(narrow(done.report_ref)).read_text(encoding="utf-8")
        self.assertIn("## Decision", text)  # defect c
        self.assertIn("Approval: approved by user", text)
        self.assertIn("Key evidence:", text)
        self.assertIn("Precedent used:", text)
        evidence_per_criterion = {a["criterion_id"]: len(a["evidence_ids"])
                                  for a in payload["criterion_assessments"]}
        self.assertTrue(evidence_per_criterion)
        self.assertTrue(all(n <= self.config.memory.criterion_evidence_max
                            for n in evidence_per_criterion.values()))  # defect e


class TestRunTwoReusesThePrecedent(LoopCase):
    """Run 2: the same goal finds the record, asks the short question, and reuse resolves it."""

    async def test_the_same_goal_reuses_the_precedent_with_far_fewer_calls_and_no_host_work(
            self) -> None:
        # covers: DK-600d-4
        first, record_id = await self.published()
        run_one_calls = self.transport.requests
        host_before = first.usage_summary.host_operations
        batches_before = len(self.scripted.batches)

        envelope = await self.service().start_run(self.goal(GOAL))
        self.assertEqual(envelope.status, RunStatus.WAITING_HUMAN)  # never waiting_host
        question = as_type(narrow(envelope.pending_interaction), HumanQuestion)
        self.assertTrue(question.question.startswith(f"Decision {record_id} (approved by "
                                                     "human:user on "))
        self.assertTrue(question.question.endswith(" for a matching question. Reuse it, or "
                                                   "decide anew?"))
        self.assertIn(" chose ", question.question)
        self.assertEqual([c.id for c in question.choices], ["reuse", "decide_anew"])

        done = await self.service().resume_run(
            envelope.run_id, answer_human(envelope, {"choice_id": "reuse"}))
        self.assertEqual(done.status, RunStatus.COMPLETED, done.limitations)

        run_two_calls = self.transport.requests - run_one_calls
        run_two_purposes = self.purposes_since(batches_before)
        print(f"jev calls: run 1 = {run_one_calls}, run 2 = {run_two_calls} {run_two_purposes}")
        self.assertLessEqual(run_two_calls, 4)  # intent, routing, one precedent judgement
        self.assertLess(run_two_calls * 4, run_one_calls)
        self.assertIn("decision.precedent", run_two_purposes)
        for purpose in run_two_purposes:  # no research, no retrieval, no assessment, no options
            self.assertFalse(purpose.startswith(("research.", "retrieval.", "decision.assess")),
                             purpose)
        self.assertEqual(done.usage_summary.host_operations or 0, 0)
        self.assertGreater(host_before or 0, 0)  # run 1 needed host work; run 2 needed none
        values = await self.checkpoint_values(done.run_id)
        self.assertEqual(self.capabilities_used(values).count("research"), 0)
        self.assertEqual(self.capabilities_used(values).count("retrieve.repository"), 0)

        payload = narrow(done.output).payload
        self.assertEqual(payload["status"], "resolved")
        self.assertEqual(payload["approval_status"], "approved")
        decision = next(iter(values["decisions"].values()))
        self.assertEqual(decision.approved_by, "user")  # the CURRENT human, not the precedent's
        self.assertEqual(decision.precedent_ids, [record_id])
        self.assertIn(record_id, narrow(decision.rationale).text)

    async def test_nothing_resolves_until_the_human_answers(self) -> None:
        # covers: DK-600e-3
        _, record_id = await self.published()
        envelope = await self.service().start_run(self.goal(GOAL))
        self.assertEqual(envelope.status, RunStatus.WAITING_HUMAN)
        self.assertIsNone(envelope.output)
        values = await self.checkpoint_values(envelope.run_id)
        self.assertTrue(all(d.selected_option_id is None for d in values["decisions"].values()))
        self.assertEqual(self.staged_for(envelope.run_id), [])
        self.assertEqual(
            [e.source.locator for e in values["evidence"].values()
             if e.source.locator.endswith(f"{record_id}.yaml")],
            [f"docs/decisions/{record_id}.yaml"])

    async def test_reuse_stages_a_new_record_that_cites_the_precedent_and_publishes(self) -> None:
        # covers: DK-600e-4
        _, record_id = await self.published()
        envelope = await self.service().start_run(self.goal(GOAL))
        done = await self.service().resume_run(
            envelope.run_id, answer_human(envelope, {"choice_id": "reuse"}))
        (staged,) = self.staged_for(done.run_id)
        self.assertEqual((staged.related, staged.supersedes), ([record_id], []))
        self.assertEqual([(n.id, n.action) for n in staged.precedents_considered],
                         [(record_id, "reused")])
        self.assertEqual(staged.assessment.basis, "precedent_reuse")
        self.assertEqual(staged.approval.approved_by, "human:user")
        code, doc = self.cli("decisions", "publish", "--run-id", done.run_id)
        self.assertEqual((code, doc["ok"]), (0, True), doc)
        code, doc = self.cli("decisions", "validate")
        self.assertEqual((code, doc["records"]), (0, 2), doc)

    async def test_deciding_anew_keeps_the_precedent_as_evidence_and_runs_the_normal_flow(
            self) -> None:
        _, record_id = await self.published()
        envelope = await self.service().start_run(self.goal(GOAL))
        again = await self.service().resume_run(
            envelope.run_id, answer_human(envelope, {"choice_id": "decide_anew"}))
        self.assertNotEqual(again.status, RunStatus.COMPLETED)  # the normal flow continues
        values = await self.checkpoint_values(again.run_id)
        self.assertIn(f"docs/decisions/{record_id}.yaml",
                      [e.source.locator for e in values["evidence"].values()])
        self.assertEqual(self.staged_for(again.run_id), [])


class TestRunThreeIsUnrelated(LoopCase):
    """Run 3: an unrelated goal runs the normal flow; a look-alike one is judged not applicable."""

    async def test_an_unrelated_goal_finds_no_precedent_and_runs_the_normal_flow(self) -> None:
        await self.published()
        before = len(self.scripted.batches)
        envelope = await self.service().start_run(self.goal(UNRELATED))
        self.assertNotIn("decision.precedent", self.purposes_since(before))
        pending = narrow(envelope.pending_interaction)
        self.assertFalse(getattr(pending, "question", "").startswith(CONFIRM_START))

    async def test_a_lookalike_goal_is_judged_not_applicable_and_the_normal_flow_runs(self) -> None:
        # covers: DK-600e-2-i
        await self.published()
        self.applies = 0.1
        before = len(self.scripted.batches)
        envelope = await self.service().start_run(self.goal(LOOKALIKE))
        self.assertEqual(self.purposes_since(before).count("decision.precedent"), 1)
        pending = narrow(envelope.pending_interaction)
        self.assertFalse(getattr(pending, "question", "").startswith(CONFIRM_START))
        values = await self.checkpoint_values(envelope.run_id)
        self.assertEqual([e for e in values["evidence"].values()
                          if e.source.locator.startswith("docs/decisions/")], [])


if __name__ == "__main__":
    import unittest

    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The offline proof of the learning loop: run 1 stages and publishes a
#   record, run 2 (same goal) reuses it with a handful of Jev calls and no host or research work,
#   run 3 (unrelated, or judged not applicable) runs the normal flow. (#KernelDecisionStore)
# ====================================================================
