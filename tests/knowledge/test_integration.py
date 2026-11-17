"""The integration maps transport evidence into the existing canonical kernel model."""

import importlib
import subprocess
import sys
from pathlib import Path


def test_disabled_cli_is_reachable_without_kernel_bootstrap():
    # covers: KM-400e-1
    # angle: reachability
    result = subprocess.run(
        [sys.executable, "-m", "knowledge", "capabilities"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "disabled" in result.stdout


def test_exact_mode_choice_skips_jev_and_evidence_mapping_preserves_sha():
    # covers: KM-400e-2
    # covers: KM-400e-3
    # angle: seam
    c = importlib.import_module("knowledge.contracts")
    adapter = importlib.import_module("integrations.knowledge_capability")
    decision = importlib.import_module("integrations.retrieval_decision")
    choice = decision.choose_retrieval_mode(
        known_ids=["KM-400a-1"],
        intent="explain",
        capabilities={"graph": True},
        evidence_sufficient=False,
    )
    assert choice.mode == "exact" and choice.operation == "get_entities"
    entity = c.Entity(
        canonical_id="KM-400a-1",
        kind="AcceptanceCriterion",
        title="Rule",
        source=c.SourceReference(
            repository_id="repo", source_sha="a" * 40, path="docs/ac.yaml", locator="/criteria"
        ),
    )
    evidence = c.KnowledgeEvidence(entity=entity, content="  approved text\n", disclosure_level=3)
    mapped = adapter.to_kernel_evidence(evidence, retrieval_id="retrieval-1")
    from kernel.contracts.evidence import Evidence

    assert isinstance(mapped, Evidence)
    assert mapped.source.source_version.commit == "a" * 40
    assert mapped.excerpt == "  approved text\n"
    assert "KM-400a-1" in mapped.source.locator


def test_sufficient_evidence_mode_choice_stops_retrieval():
    # covers: KM-400e-2
    # angle: boundary
    decision = importlib.import_module("integrations.retrieval_decision")
    choice = decision.choose_retrieval_mode(
        known_ids=[], intent="enough", capabilities={"graph": True}, evidence_sufficient=True
    )
    assert not choice.retrieve and choice.reason
