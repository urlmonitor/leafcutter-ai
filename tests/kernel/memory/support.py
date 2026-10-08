"""
MODULE: tests.kernel.memory.support
GOAL: Shared builders for the decision-store tests: a valid record from the JSON fixture, a store
    folder in a temporary directory, the real vocabulary and schema, and a resolved human-approved
    kernel Decision with its options, criteria and evidence.
BUSINESS CONTEXT: Every store test needs a record that is valid by the real schema and the real
    vocabularies, and a repository layout (config/, docs/) it can validate against, without
    writing into the checkout.
ARCHITECTURE: Builders return real models (no mocks). `StoreCase` makes a temp repository root
    holding the committed schema and the vocabulary sources copied from the checkout, so
    validation runs the same code as `python -m kernel decisions validate`.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from kernel.contracts.base import content_hash, evidence_id, utc_now
from kernel.contracts.decision import Criterion, Decision, Option, OptionRanking, Rationale
from kernel.contracts.enums import (
    ApprovalStatus,
    DecisionStatus,
    EvidenceCategory,
    ProposalStatus,
)
from kernel.contracts.evidence import Evidence
from kernel.memory.codec import dump_record
from kernel.memory.models import DecisionRecord
from kernel.memory.validate import SCHEMA_NAME, load_schema
from kernel.memory.vocab import Vocabulary, load_vocabulary
from tests.kernel.helpers import load_json

CHECKOUT = Path(__file__).resolve().parents[3]
VOCAB_FILES = ("docs/components.json", "docs/roadmap.json", "config/ac_store_schema.json",
               f"config/{SCHEMA_NAME}")
HUMAN = "human:tester"
DEC_ID = "dec-0123456789abcdef"


def record_data(**overrides: Any) -> dict[str, Any]:
    """Return the fixture record as a dict with top-level overrides applied."""
    return {**load_json("memory/record_basic.json"), **overrides}


def make_record(**overrides: Any) -> DecisionRecord:
    """Return a valid DecisionRecord (fixture plus overrides)."""
    return DecisionRecord.model_validate(record_data(**overrides))


def vocabulary() -> Vocabulary:
    """Return the real vocabularies of the checkout."""
    return load_vocabulary(CHECKOUT)


def schema() -> dict[str, Any]:
    """Return the committed record schema."""
    return load_schema(CHECKOUT / "config" / SCHEMA_NAME)


def human_decision(*, decision_id: str = DEC_ID, selected: str = "opt.a", approved_by: str | None
                   = HUMAN, approval: ApprovalStatus = ApprovalStatus.APPROVED,
                   status: DecisionStatus = DecisionStatus.RESOLVED) -> Decision:
    """Return a kernel Decision a human settled (overridable to build refusals)."""
    return Decision(
        id=decision_id, question="Which option should the kernel use?",
        option_ids=["opt.a", "opt.b"], criterion_ids=["crit.one"],
        selected_option_id=selected if status is DecisionStatus.RESOLVED else None,
        status=status, approval_status=approval, evidence_ids=[evidence_item().id],
        rationale=Rationale(text="Settled by a human.", origin="template"),
        approved_by=approved_by, approved_at=utc_now(), design_reason="design_judgement")


def options() -> list[Option]:
    """Return two human-approved options."""
    return [Option(id=i, title=t, proposal_status=ProposalStatus.PROPOSED,
                   approval_status=ApprovalStatus.APPROVED, proposed_by="host.generate_options",
                   approved_by=HUMAN, assumptions=[f"{i} assumption"])
            for i, t in (("opt.a", "Option A"), ("opt.b", "Option B"))]


def criteria() -> list[Criterion]:
    """Return one required criterion."""
    return [Criterion(id="crit.one", question="Is it simple?")]


def evidence_item(locator: str = "docs/a.md#L1-L5", excerpt: str = "Use YAML.") -> Evidence:
    """Return a content-addressed prior_decisions evidence item."""
    digest = content_hash(excerpt)
    return Evidence.model_validate({
        "id": evidence_id(locator, digest), "category": EvidenceCategory.PRIOR_DECISIONS,
        "semantic_type": "repository_fact", "excerpt": excerpt, "content_hash": digest,
        "source": {"id": "repo.decisions", "kind": "repository_file", "locator": locator,
                   "source_version": {"commit": "abc1234567", "dirty": False}},
        "provenance": {"producer": "test", "relevance": 0.8}})


def ranking() -> list[OptionRanking]:
    """Return a two-row kernel ranking."""
    return [OptionRanking(option_id="opt.a", rank=1, required_passed=1, required_total=1,
                          required_mean=0.9, scores={"crit.one": 0.9}),
            OptionRanking(option_id="opt.b", rank=2, required_passed=0, required_total=1,
                          required_mean=0.3, scores={"crit.one": 0.3})]


class StoreCase(unittest.TestCase):
    """A temporary repository root with the vocabulary sources, schema and an empty store."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        for rel in VOCAB_FILES:
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(CHECKOUT / rel, target)
        rules = self.root / "templates" / "rules"
        rules.mkdir(parents=True, exist_ok=True)
        for rule in (CHECKOUT / "templates" / "rules").glob("*.md"):
            shutil.copyfile(rule, rules / rule.name)
        self.folder = self.root / "docs" / "decisions"
        self.run_root = self.root / "kernel-run"

    def write_record(self, record: DecisionRecord) -> Path:
        """Write the record into the store folder and return the path."""
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / f"{record.id}.yaml"
        path.write_text(dump_record(record), encoding="utf-8", newline="\n")
        return path
