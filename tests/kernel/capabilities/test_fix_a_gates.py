"""
MODULE: tests.kernel.capabilities.test_fix_a_gates
GOAL: Regression tests for the pre-PR review findings R2-1..R2-4: the resolved-gate with no
    required criterion, approval bound to the approved option, read_roots enforced on every read
    and case-insensitive deny globs.
BUSINESS CONTEXT: A decision may only resolve on evidence the human could see and a scope may
    only restrict what retrieval reads (Rev 3 sections 9.4 and 10.3, ADR-053).
ARCHITECTURE: The decision cases run through DecisionExecutor with ScriptedJev; the retrieval
    cases use ReadPolicy and the knowledge-map candidate builder directly on a temp repository.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from kernel.capabilities.retrieval import knowledge_map as km
from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.capabilities.retrieval.candidates import SearchReport
from kernel.config import SourceConfig, load_kernel_config
from kernel.contracts import Priority, schema_ids
from kernel.contracts.decision import Criterion, Option
from kernel.contracts.enums import (
    DecisionStatus,
    EvidenceCategory,
    RequestKind,
    ResultStatus,
)
from kernel.contracts.payloads import DecisionReportPayload, DecisionRequestPayload
from tests.kernel.capabilities.support import child, resume
from tests.kernel.capabilities.test_decision_graph import DecisionTestCase
from tests.kernel.capabilities.test_retrieval_repository import _make_link


def _only_supporting_payload() -> dict:
    """A decision request whose only criterion is supporting, with one option."""
    return DecisionRequestPayload(
        question="Where should run state live?", options=[Option(id="A", title="Use sqlite")],
        criteria=[Criterion(id="s1", question="Is it simple?", priority=Priority("supporting"))],
    ).model_dump(mode="json")


class TestNoRequiredCriterion(DecisionTestCase):
    """R2-1: with no usable required criterion the gate must not open."""

    def test_supporting_only_criteria_never_resolve(self) -> None:
        self.params["satisfies"] = {}  # Jev says option A fails every criterion
        _, _, result = self.first(payload=_only_supporting_payload())
        self.assertNotEqual(result.status, ResultStatus.COMPLETED)
        self.assertEqual(result.requests[0].kind, RequestKind.OPTIONS)
        self.assertEqual(result.decisions[0].status, DecisionStatus.NEEDS_OPTIONS)
        self.assertIsNone(result.decisions[0].selected_option_id)


class TestApprovalBoundToOption(DecisionTestCase):
    """R2-2: an approval covers only the option the human saw."""

    def test_changed_winner_asks_the_human_again(self) -> None:
        self.params["satisfies"] = {("c1", "A"): 0.95}
        inv, ctx, waiting = self.first(approval_required=True)
        self.assertEqual(waiting.decisions[0].status, DecisionStatus.NEEDS_HUMAN)
        answer = child(ctx, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER, {"choice_id": "approve"})
        self.params["satisfies"] = {("c1", "B"): 0.95}  # Jev now prefers B only
        done = self.run_decision(resume(inv, waiting, [answer]), ctx)
        self.assertNotEqual(done.status, ResultStatus.COMPLETED)
        self.assertEqual(done.requests[0].kind, RequestKind.HUMAN)
        self.assertEqual(done.continuation_state["candidate_option_id"], "B")

    def test_unchanged_winner_still_resolves_after_approval(self) -> None:
        self.params["satisfies"] = {("c1", "A"): 0.95}
        inv, ctx, waiting = self.first(approval_required=True)
        answer = child(ctx, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER, {"choice_id": "approve"})
        done = self.run_decision(resume(inv, waiting, [answer]), ctx)
        report = DecisionReportPayload.model_validate(done.output_payload)
        self.assertEqual(report.selected_option_id, "A")

    def test_new_evidence_after_approval_invalidates_it(self) -> None:
        self.params["satisfies"] = {("c1", "A"): 0.95}
        inv, ctx, waiting = self.first(approval_required=True)
        answer = child(ctx, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER, {"choice_id": "approve"})
        state = dict(waiting.continuation_state)
        state["human_inputs"] = [*state["human_inputs"], "A new constraint appeared."]
        stale = resume(inv, waiting.model_copy(update={"continuation_state": state}), [answer])
        done = self.run_decision(stale, ctx)
        self.assertNotEqual(done.status, ResultStatus.COMPLETED)
        self.assertEqual(done.requests[0].kind, RequestKind.HUMAN)


class _RepoCase(unittest.TestCase):
    """Base: a temp repo with docs/ and agents/ trees and a scope restricted to docs/."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / "repo"
        for name in ("docs", "agents"):
            (self.root / name).mkdir(parents=True)
            (self.root / name / "a.md").write_text("sqlite notes", encoding="utf-8")
        cfg = load_kernel_config().retrieval
        self.cfg = cfg
        self.policy = ReadPolicy(root=self.root, read_roots=("docs",),
                                 deny_globs=tuple(cfg.deny_globs),
                                 max_file_bytes=cfg.max_file_bytes)


class TestReadRootsEnforcedOnRead(_RepoCase):
    """R2-3: read_roots bind reads, symlinks and knowledge-map nodes, not only root resolution."""

    def test_file_outside_read_roots_is_not_read(self) -> None:
        self.assertEqual(self.policy.read_text(self.root / "agents" / "a.md").reason,
                         "outside_root")
        self.assertEqual(self.policy.read_text(self.root / "docs" / "a.md").text, "sqlite notes")

    def test_link_inside_root_pointing_elsewhere_in_repo_is_not_read(self) -> None:
        if not _make_link(self.root / "docs" / "sneak", self.root / "agents"):
            self.skipTest("cannot create a directory link here")
        outcome = self.policy.read_text(self.root / "docs" / "sneak" / "a.md")
        self.assertIsNone(outcome.text)
        self.assertEqual(outcome.reason, "outside_root")

    def test_knowledge_map_node_outside_read_roots_is_skipped(self) -> None:
        source = SourceConfig(id="km", kind="knowledge_map",
                              categories=[EvidenceCategory.PRIOR_DECISIONS], surfaces=["adrs"])
        node = SimpleNamespace(id="n1", title="sqlite", description="sqlite choice",
                               path=self.root / "agents" / "a.md", missing=False)
        report = SearchReport(source_id="km")
        self.assertIsNone(km._node_candidate(self.policy, source, node, ["sqlite"], report))
        self.assertEqual(report.skipped, {"outside_root": 1})


class TestDenyGlobsCaseInsensitive(_RepoCase):
    """R2-4: deny globs match regardless of letter case."""

    def test_mixed_case_secret_names_are_denied(self) -> None:
        for rel in (".ENV", ".Env.local", "config/server.PEM", "keys/ID.Key", ".GIT/config"):
            self.assertTrue(self.policy.is_denied(rel), rel)

    def test_ordinary_names_are_not_denied(self) -> None:
        self.assertFalse(self.policy.is_denied("docs/a.md"))


if __name__ == "__main__":
    unittest.main()
