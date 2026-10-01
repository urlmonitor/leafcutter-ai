"""
MODULE: tests.kernel.grounding.test_round5
GOAL: Tests of the fifth round: the knowledge-map bridge never executes code from the scope
    repository, kernel git calls cannot write to the scope, the default sources include the
    design docs, options named in the goal are taken as caller-supplied after a deterministic
    check, and a human approval can add options.
BUSINESS CONTEXT: Scoping a run to an untrusted repository must not run that repository's Python
    (Rev 3 section 13.3); a goal that names its options ("files, Postgres or Neo4j") must be
    decided between exactly those, not between regenerated ones, and the human must be able to
    add an option at approval (ADR-053: extraction is generative work, verification is code).
ARCHITECTURE: Real bridge, versioning and host conversion; the decision flow through the real
    DecisionExecutor, and the approval end to end through the real service (ScenarioCase).
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from kernel.capabilities.decision.loading import load_working
from kernel.capabilities.host import host_operation
from kernel.capabilities.research.planning import _native_available
from kernel.capabilities.retrieval import knowledge_map as km
from kernel.capabilities.retrieval import versioning
from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.config import SourceConfig, load_kernel_config, repo_root
from kernel.contracts import ApprovalStatus, ProposalStatus, RunStatus, schema_ids
from kernel.contracts.enums import EvidenceCategory
from kernel.contracts.enums import RequestKind as RK
from kernel.contracts.payloads import HumanAnswerPayload, OptionsPayload
from kernel.contracts.schema_catalog import SemanticContext, semantic_violations
from kernel.contracts.task import Scope
from tests.kernel.capabilities.host_support import conversion, criterion, option
from tests.kernel.capabilities.support import child, invocation
from tests.kernel.capabilities.test_decision_graph import DECISION, DecisionTestCase
from tests.kernel.helpers import make_context
from tests.kernel.integration.scenario_support import (
    FakeHostResponder,
    ScenarioCase,
    answer_human,
    options_response,
)

SOURCE = SourceConfig(id="knowledge.decisions", kind="knowledge_map",
                      categories=[EvidenceCategory.PRIOR_DECISIONS], surfaces=["adrs"])
EV = "ev-aaaaaaaaaaaaaaaa"
GOAL = ("Decide how decisions are stored: reviewable decision files in the repository, a "
        "Postgres store, or a Neo4j graph.")


def _policy(root: Path) -> ReadPolicy:
    cfg = load_kernel_config().retrieval
    return ReadPolicy(root=root.resolve(), read_roots=(), deny_globs=tuple(cfg.deny_globs),
                      max_file_bytes=cfg.max_file_bytes)


class TestKnowledgeMapNeverRunsScopeCode(unittest.TestCase):
    """S1: the bridge script comes from the kernel installation, never from the scope."""

    def setUp(self) -> None:
        km.clear_caches()
        self.addCleanup(km.clear_caches)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.scope = Path(tmp.name).resolve() / "untrusted"
        (self.scope / "scripts").mkdir(parents=True)
        (self.scope / "config").mkdir()
        self.marker = Path(tmp.name).resolve() / "executed.marker"
        (self.scope / "scripts" / "knowledge_query.py").write_text(
            f"from pathlib import Path\nPath({str(self.marker)!r}).write_text('ran')\n"
            "raise RuntimeError('untrusted code ran')\n", encoding="utf-8")
        (self.scope / "config" / "paths.json").write_text("{}", encoding="utf-8")

    def search(self):
        return km.search_knowledge_map(_policy(self.scope), SOURCE, ["decision"],
                                       load_kernel_config().retrieval)

    def test_a_script_in_the_scope_repository_is_not_executed(self) -> None:
        self.search()
        self.assertFalse(self.marker.exists(), "the scope repository's script was executed")

    def test_the_loaded_bridge_is_the_kernels_own_script(self) -> None:
        self.search()
        files = {Path(m.__file__).resolve() for m in km._MODULES.values()}
        self.assertEqual(files, {(repo_root() / km.SCRIPT).resolve()})

    def test_without_a_trusted_script_the_source_is_unavailable_with_a_reason(self) -> None:
        with mock.patch.object(km, "trusted_root", return_value=self.scope / "nowhere"):
            report = self.search()
        self.assertIn("trusted", report.unavailable_reason)
        self.assertEqual(report.candidates, [])

    def test_planning_checks_the_trusted_script_not_the_scope(self) -> None:
        ctx = make_context(self.scope)
        self.assertIsNone(_native_available(ctx, SOURCE))  # the scope has no script that counts
        (self.scope / "scripts" / "knowledge_query.py").unlink()
        self.assertIsNone(_native_available(ctx, SOURCE))

    def test_no_other_kernel_module_imports_or_executes_code_dynamically(self) -> None:
        allowed = {"knowledge_map.py", "versioning.py"}
        banned = ("spec_from_file_location", "import_module", "exec(", "eval(", "__import__(",
                  "runpy", "os.system(", "shell=True")
        offenders = []
        for path in (repo_root() / "kernel").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            code = "\n".join(line for line in text.splitlines()
                             if not line.lstrip().startswith(("#", '"', "'")))
            if path.name not in allowed and any(b in code for b in banned):
                offenders.append(path.name)
        self.assertEqual(offenders, [])


class TestGitIsReadOnly(unittest.TestCase):
    """S2: kernel git calls cannot refresh or write the scope's index."""

    def test_every_git_call_disables_optional_locks_and_uses_no_shell(self) -> None:
        calls = []

        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0, stdout="abc123\n", stderr="")

        versioning._CACHE.clear()
        self.addCleanup(versioning._CACHE.clear)
        scope = Scope(workspace_id="ws", repository_root=str(repo_root()))
        with mock.patch.object(versioning.subprocess, "run", fake_run):
            versioning.resolve_source_version("run-0000000000000042", scope)
        self.assertTrue(calls)
        for argv, kwargs in calls:
            self.assertEqual(argv[0], "git")
            self.assertIn(argv[1], {"rev-parse", "status"})  # read-only commands only
            self.assertEqual(kwargs["env"]["GIT_OPTIONAL_LOCKS"], "0")
            self.assertFalse(kwargs.get("shell", False))


class TestDesignDocsAreSources(unittest.TestCase):
    """C1: the kernel can see its own design docs."""

    def test_analysis_and_components_are_default_sources(self) -> None:
        sources = load_kernel_config().sources
        wanted = {"docs/analysis": EvidenceCategory.PRIOR_DECISIONS,
                  "docs/architecture/components": EvidenceCategory.EXISTING_PATTERNS}
        for root, category in wanted.items():
            with self.subTest(root=root):
                found = [s for s in sources if root in s.roots]
                self.assertTrue(found)
                self.assertIn(category, found[0].categories)
                self.assertIn(EvidenceCategory.TASK_CONTEXT, found[0].categories)


class TestNamedOptions(unittest.TestCase):
    """C2: options the goal names are caller-supplied once the kernel verifies them."""

    def convert(self, options: list[dict], **request: object):
        body = {"problem": GOAL, "max_options": 5, "propose_criteria": True,
                "evidence_ids": [EV], "require_grounding": True, **request}
        ctx = conversion("host.generate_options", body, {"options": options})
        result = host_operation("host.generate_options").convert(ctx)
        return result, OptionsPayload.model_validate(result.output_payload)

    def test_a_named_option_found_in_the_goal_is_supplied_and_needs_no_grounding(self) -> None:
        result, payload = self.convert([option("neo", title="a Neo4j graph", named_in_goal=True)])
        (named,) = payload.named_options
        self.assertEqual(named.title, "a Neo4j graph")
        self.assertEqual(named.proposal_status, ProposalStatus.SUPPLIED)
        self.assertEqual(named.approval_status, ApprovalStatus.NOT_REQUIRED)
        self.assertEqual(payload.options, [])  # not refused, not a proposal
        self.assertFalse(any("refused" in t for t in result.limitations))

    def test_a_named_claim_not_in_the_goal_stays_an_ungrounded_proposal(self) -> None:
        result, payload = self.convert([option("rd", title="Redis cache", named_in_goal=True)])
        self.assertEqual(payload.named_options, [])
        self.assertEqual(payload.options, [])  # refused as an ungrounded proposal
        self.assertTrue(any("not found in the goal" in t for t in result.limitations))

    def test_generated_extras_are_still_proposals_and_must_be_grounded(self) -> None:
        _, payload = self.convert([option("neo", title="Neo4j graph", named_in_goal=True),
                                   option("x", title="Flat files", source_refs=[EV]),
                                   option("y", title="Invented")])
        self.assertEqual([o.id for o in payload.named_options], ["neo"])
        self.assertEqual([o.id for o in payload.options], ["x"])

    def test_the_verified_title_is_the_callers_wording_without_host_embellishment(self) -> None:
        _, payload = self.convert([option("pg", title="Postgres store", named_in_goal=True,
                                          description="Fastest by far; use it.")])
        self.assertEqual(payload.named_options[0].description, "")

    def test_a_host_cannot_supply_named_options_directly(self) -> None:
        payload = OptionsPayload.model_validate({"named_options": [
            {"id": "n", "title": "Neo4j graph"}]})
        violations = semantic_violations(schema_ids.OPTIONS, payload, SemanticContext())
        self.assertTrue(any("named_options" in v for v in violations))


class TestNamedOptionsInTheDecision(DecisionTestCase):
    """The decision uses named options as supplied options."""

    def test_named_options_are_usable_without_approval(self) -> None:
        ctx = self.ctx()
        body = self.first(options=False)[0].input_payload
        named = option("neo", title="Neo4j graph")
        named.update(proposal_status="supplied", approval_status="not_required",
                     proposed_by="caller_goal", named_in_goal=True)
        out = child(ctx, RK.OPTIONS, schema_ids.OPTIONS, {
            "named_options": [named], "proposed_criteria": [criterion("c1")]})
        inv = invocation(DECISION, schema_ids.DECISION_REQUEST, body, outcomes=[out])
        work = load_working(inv, ctx)
        self.assertEqual([o.id for o in work.usable_options], ["neo"])


class TestApprovalCanAddOptions(unittest.TestCase):
    """C3: added_options in a structured answer become human-supplied approved options."""

    def test_the_answer_model_accepts_added_options_as_a_structured_answer(self) -> None:
        answer = HumanAnswerPayload.model_validate(
            {"added_options": [{"title": "Use ADR files", "description": "One per decision"}]})
        self.assertTrue(answer.is_structured)


class TestAddedOptionsEndToEnd(ScenarioCase):
    """The approval question offers it, and an added option reaches the assessment."""

    domains = ("primary",)

    async def test_a_human_adds_an_option_at_approval(self) -> None:
        self.params["satisfies"] = {("c1", "A"): 0.95, ("c2", "A"): 0.9}
        responder = FakeHostResponder({schema_ids.OPTIONS: options_response("primary")})
        paused = await self.service().start_run(self.task("primary", request=False))
        approval = await self.service().resume_run(paused.run_id, responder.answer(paused))
        self.assertEqual(approval.status, RunStatus.WAITING_HUMAN)
        self.assertIn("added_options", approval.pending_interaction.question)
        answer = {"approved_option_ids": ["A", "B"],
                  "approved_criterion_ids": ["c1", "c2"],
                  "added_options": [{"title": "Hybrid of both", "description": "Mix them"}]}
        final = await self.service().resume_run(paused.run_id,
                                                answer_human(approval, answer))
        self.assertEqual(final.status, RunStatus.COMPLETED)
        batch = next(b for b in self.jev.batches if b.purpose == "decision.assess")
        self.assertIn("Hybrid of both. Mix them", batch.state["options"].values())


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: Tests for S1, S2, C1, C2 and C3 written first and seen failing.
#   (#KernelBootstrapV0/GROUND)
# ====================================================================
