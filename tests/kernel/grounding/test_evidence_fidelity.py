"""
MODULE: tests.kernel.grounding.test_evidence_fidelity
GOAL: Tests that evidence excerpts stay verbatim (indentation included) so a host hash over the
    verbatim excerpt matches the kernel's, and that the host.research output schema does not
    require the ids and hashes its own instructions forbid inventing.
BUSINESS CONTEXT: A live host submission carried indented excerpts; the kernel stripped them,
    re-hashed, changed the evidence ids and reported the host hash as replaced (G5), while the
    schema demanded the very ids and hashes the instructions said not to invent (G6).
ARCHITECTURE: Real contract models and the real host conversion; the schema check reads the
    packet schema the interaction package builds, and the submission check uses the real
    payload validator.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from pathlib import Path

from kernel.capabilities.host import host_operation
from kernel.capabilities.retrieval.candidates import Candidate
from kernel.capabilities.retrieval.evidence_build import build_evidence
from kernel.capabilities.retrieval.rerank import Ranked
from kernel.contracts import schema_ids
from kernel.contracts.base import content_hash, evidence_id
from kernel.contracts.enums import EvidenceCategory, SourceKind
from kernel.contracts.evidence import Evidence, EvidenceInput, EvidenceNeed
from kernel.contracts.payloads import RetrievalRequestPayload
from kernel.contracts.schema_catalog import validate_payload
from kernel.interaction.packets import tightened_schema
from tests.kernel.capabilities.host_support import conversion, evidence_json

INDENTED = "    def run(self):\n        return 1\n  \n"
LOCATOR = "kernel/service.py#L10-L12"


def _evidence(excerpt: str) -> Evidence:
    digest = content_hash(excerpt)
    return Evidence(id=evidence_id(LOCATOR, digest), category="task_context",
                    semantic_type="repository_fact", excerpt=excerpt, content_hash=digest,
                    source={"id": "s", "kind": "repository_file", "locator": LOCATOR},
                    provenance={"producer": "test"})


class TestVerbatimExcerpts(unittest.TestCase):
    """The excerpt is the source text, byte for byte."""

    def test_evidence_keeps_leading_indentation_and_trailing_whitespace(self) -> None:
        self.assertEqual(_evidence(INDENTED).excerpt, INDENTED)

    def test_a_host_hash_over_the_verbatim_excerpt_is_accepted_unchanged(self) -> None:
        item = evidence_json(LOCATOR, INDENTED)
        ctx = conversion("host.research", {"need": {"id": "need-1", "category": "task_context",
                                                    "question": "q"}},
                         {"evidence_ids": [item["id"]], "evidence": [item],
                          "coverage": {"need-1": "satisfied"}})
        result = host_operation("host.research").convert(ctx)
        kept = result.evidence[0]
        self.assertEqual(kept.excerpt, INDENTED)
        self.assertEqual(kept.content_hash, content_hash(INDENTED))
        self.assertEqual(kept.id, item["id"])
        self.assertFalse([t for t in result.limitations if "replaced" in t])

    def test_native_evidence_hash_covers_the_stored_excerpt(self) -> None:
        cand = Candidate(source_id="repo.patterns", kind=SourceKind.REPOSITORY_FILE,
                         strategy="repo_text", path="a.py", title="a.py", locator=LOCATOR,
                         excerpt=INDENTED, hits=2, terms=("run",))
        need = EvidenceNeed(id="n", category=EvidenceCategory.EXISTING_PATTERNS, question="q")
        built = build_evidence(Ranked(cand, 0.9, 0), RetrievalRequestPayload(need=need),
                               EvidenceCategory.EXISTING_PATTERNS, None, "inv-0",
                               datetime.now(UTC), None, ["run"])
        self.assertEqual(built.excerpt, INDENTED)
        self.assertEqual(built.content_hash, content_hash(built.excerpt))

    def test_a_caller_supplied_excerpt_keeps_its_indentation(self) -> None:
        item = EvidenceInput(title="t", excerpt=INDENTED)
        self.assertEqual(item.excerpt, INDENTED)


class TestHostSchemaConsistency(unittest.TestCase):
    """What the schema requires must not contradict what the instructions forbid."""

    def _evidence_required(self) -> set[str]:
        schema = tightened_schema(schema_ids.EVIDENCE_BUNDLE,
                                  _bundle_schema())
        return set(schema["$defs"]["Evidence"]["required"])

    def test_the_host_schema_does_not_require_id_or_content_hash(self) -> None:
        required = self._evidence_required()
        self.assertNotIn("id", required)
        self.assertNotIn("content_hash", required)

    def test_the_kernel_schema_file_still_requires_them(self) -> None:
        # The tightening applies to the host packet only; kernel-built bundles stay strict.
        self.assertIn("id", _bundle_schema()["$defs"]["Evidence"]["required"])

    def test_a_host_item_without_id_or_hash_validates_and_converts(self) -> None:
        item = evidence_json(LOCATOR, INDENTED)
        item.pop("id")
        item.pop("content_hash")
        response = {"evidence": [item], "coverage": {"need-1": "satisfied"}}
        validate_payload(schema_ids.EVIDENCE_BUNDLE, response)
        ctx = conversion("host.research", {"need": {"id": "need-1", "category": "task_context",
                                                    "question": "q"}}, response)
        kept = host_operation("host.research").convert(ctx).evidence[0]
        self.assertEqual(kept.content_hash, content_hash(INDENTED))
        self.assertEqual(kept.id, evidence_id(LOCATOR, kept.content_hash))

    def test_the_instructions_still_forbid_inventing_ids_and_hashes(self) -> None:
        op = host_operation("host.research")
        text = " ".join(op.requirements(None))
        self.assertIn("Do not invent content hashes, ids", text)


def _bundle_schema() -> dict:
    """Return the committed kernel schema file of the evidence bundle."""
    import json
    path = Path(__file__).parents[3] / "kernel" / "schemas" / (
        "leafcutter.evidence_bundle.v1.schema.json")
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 23:00 [python-coder]: Tests for G5 and G6 written first and seen failing.
#   (#KernelBootstrapV0/GROUND)
# ====================================================================
