"""Accepted explicit identities remain obligations across public query selection."""

import asyncio
import subprocess

import pytest
import yaml

from kernel.contracts import RunStatus, schema_ids
from kernel.providers.fakes import choice_answer
from tests.knowledge.public_retrieval_needs_support import (
    ROOT, PublicNeedsHarness, answer_assessments, interpret_public_question, source_snapshot,
)


@pytest.fixture
def harness(request):
    value = PublicNeedsHarness().configure(catalog_enabled=request.param)
    yield value
    value.doCleanups()


def _assert_original_targets(values, identifiers):
    requests = [item for item in values["requests"].values()
        if item.payload_schema == schema_ids.RETRIEVAL_REQUEST]
    assert requests
    assert all(item.payload["answer_requirements"]["scope"]["entity_ids"] == identifiers
               for item in requests)
    answers = answer_assessments(values)
    assert answers
    assert all(answer["scope"]["entity_ids"] == identifiers for answer in answers)
    return answers


def _assert_exact_criteria(values, identifiers):
    for identifier in identifiers:
        node = next(node for node in source_snapshot().nodes if node.canonical_id == identifier)
        raw = subprocess.check_output(
            ["git", "show", f"{node.source.source_sha}:{node.source.path}"], cwd=ROOT)
        criteria = yaml.safe_load(raw)["criteria"]
        evidence = [item for item in values["evidence"].values()
            if identifier in item.source.locator]
        assert any(item.excerpt == criteria for item in evidence), identifier
        assert all(item.source.source_version.commit == node.source.source_sha for item in evidence)


@pytest.mark.parametrize("harness", [False, True], indirect=True)
def test_selected_entities_cannot_complete_after_selector_narrows_original_targets(harness):
    # covers: KM-500e-1-i
    # covers: KM-500e-2
    # angle: seam
    # angle: discrimination
    """A confident one-ID choice cannot erase the other explicit requested criterion."""
    async def check():
        identifiers = ["KM-500c-1", "KM-500c-2"]
        harness.jev.script("knowledge.target_select", "target", choice_answer(identifiers[0]))
        selections = {"entity_types": ["ac"], "target_ids": identifiers,
            "required_fields": ["criteria"], "document_types": ["ac_yaml"], "relationships": []}
        final, values = await interpret_public_question(harness,
            "Compare the acceptance criteria of KM-500c-1 and KM-500c-2.",
            selections=selections, completeness="selected_entities")
        retrieved = {identity for call in harness.storage.calls for identity in call[3]["entity_ids"]}
        assert final.status is not RunStatus.COMPLETED or set(identifiers) <= retrieved, (
            "Completed a two-criterion question after retrieving only " + repr(retrieved))
        answers = _assert_original_targets(values, identifiers)
        if final.status is RunStatus.COMPLETED:
            _assert_exact_criteria(values, identifiers)
            assert all(answer["status"] == "fulfilled" for answer in answers)
        else:
            assert all(answer["status"] != "fulfilled" for answer in answers)
            assert all(answer["completeness"]["exact_total"] is None for answer in answers)
    asyncio.run(check())


@pytest.mark.parametrize("harness", [False, True], indirect=True)
def test_selected_entities_complete_control_returns_both_canonical_criteria(harness):
    # covers: KM-500e-1-i
    # covers: KM-500e-2
    # angle: real_artifact
    # angle: discrimination
    """Retaining obligations still permits a complete answer when both sources are present."""
    async def check():
        identifiers = ["KM-500c-1", "KM-500c-2"]
        harness.jev.script("knowledge.target_select", "target", choice_answer("all"))
        selections = {"entity_types": ["ac"], "target_ids": identifiers,
            "required_fields": ["criteria"], "document_types": ["ac_yaml"], "relationships": []}
        final, values = await interpret_public_question(harness,
            "Compare the acceptance criteria of KM-500c-1 and KM-500c-2.",
            selections=selections, completeness="selected_entities")
        assert final.status is RunStatus.COMPLETED, final.model_dump_json()
        _assert_exact_criteria(values, identifiers)
        answers = _assert_original_targets(values, identifiers)
        assert all(answer["status"] == "fulfilled" for answer in answers)
        assert all(answer["completeness"]["exact_total"] == 2 for answer in answers)
    asyncio.run(check())


@pytest.mark.parametrize("harness", [False, True], indirect=True)
def test_missing_selected_entity_stays_unmet_after_disclosure_of_present_entity(harness):
    # covers: KM-500e-1-i
    # covers: KM-500e-2
    # angle: failure
    # angle: boundary
    """Disclosure of one real result cannot replace an absent original target with itself."""
    async def check():
        identifiers = ["KM-500c-1", "KM-500c-999"]
        harness.jev.script("knowledge.target_select", "target", choice_answer("all"))
        selections = {"entity_types": ["ac"], "target_ids": identifiers,
            "required_fields": ["criteria"], "document_types": ["ac_yaml"], "relationships": []}
        final, values = await interpret_public_question(harness,
            "Compare the acceptance criteria of KM-500c-1 and KM-500c-999.",
            selections=selections, completeness="selected_entities")
        assert final.status is not RunStatus.COMPLETED, final.model_dump_json()
        _assert_exact_criteria(values, identifiers[:1])
        answers = _assert_original_targets(values, identifiers)
        assert all(answer["status"] != "fulfilled" for answer in answers)
        assert all(answer["completeness"]["exact_total"] is None for answer in answers)
        assert any("requested identities are missing" in limit
            for answer in answers for limit in answer["limitations"])
    asyncio.run(check())


@pytest.mark.parametrize("omit_second", [False, True])
def test_saved_query_assesses_original_ids_independently_of_custom_argument_name(tmp_path, omit_second):
    # covers: KM-500e-1-i
    # covers: KM-500e-2
    # covers: KM-500b-3
    # angle: seam
    # angle: discrimination
    """An admitted custom query cannot hide a missing obligation behind a different seed key."""
    from knowledge.query_admission import QueryAdmission
    from knowledge.query_catalog import QueryCatalog
    from knowledge.service import KnowledgeService
    from tests.knowledge.public_retrieval_needs_support import REPOSITORY, SnapshotStorage

    async def check():
        storage = SnapshotStorage()
        missing = False
        calls = []

        async def compiled_read(statement, parameters=None, write=False):
            calls.append((parameters, write))
            nodes = [node for node in source_snapshot().nodes
                if node.canonical_id in parameters["arg_selected_acs"]
                and not (missing and node.canonical_id == "KM-500c-2")]
            return [{"payloads": [node.model_dump_json() for node in nodes], "expansion_truncated": False}]

        storage._run = compiled_read
        catalog = QueryCatalog(tmp_path / "catalog")
        operation = "get_saved_comparison_acs"
        candidate = {"descriptor": {"operation": operation, "version": "1",
            "description": "Read exact selected acceptance criteria for comparison",
            "questions": ["Compare the specified acceptance criteria"],
            "parameters": {"selected_acs": {"type": "string_list", "required": True}},
            "recipe": {"seed_parameter": "selected_acs", "seed_kind": "AcceptanceCriterion", "steps": []}},
            "reviewer": "controlled fixture admission, not semantic review",
            "cases": [{"name": "actual", "arguments": {"selected_acs": ["KM-500c-1"]},
                       "expected_ids": ["KM-500c-1"]},
                {"name": "absent", "arguments": {"selected_acs": ["MISSING-1"]}, "expected_ids": []}]}
        admitted = await QueryAdmission(catalog, storage, REPOSITORY).verify_and_activate(candidate,
            repository_id=REPOSITORY, source_sha=source_snapshot().source_sha)
        original_catalog = (catalog.root / "catalog.json").read_bytes()
        missing = omit_second
        calls.clear()
        identifiers = ["KM-500c-1", "KM-500c-2"]
        request = catalog.request({"request_id": "saved-comparison", "repository_id": REPOSITORY,
            "revision": source_snapshot().source_sha, "mode": "graph", "operation": operation,
            "operation_digest": admitted["digest"], "arguments": {"selected_acs": identifiers},
            "answer_requirements": {"original_question": "Compare KM-500c-1 and KM-500c-2",
                "required_fields": ["canonical_id"], "scope": {"entity_ids": identifiers},
                "require_complete": True}})
        result = await KnowledgeService(storage, query_catalog=catalog).retrieve(request)
        assert calls and all(not write for _, write in calls)
        assert (catalog.root / "catalog.json").read_bytes() == original_catalog
        assert result.answer.scope.entity_ids == identifiers
        if omit_second:
            assert [item.entity.canonical_id for item in result.evidence] == identifiers[:1]
            assert result.answer.status == "partial"
            assert result.answer.completeness.exact_total is None
            assert "requested identities are missing from returned evidence" in result.answer.limitations
        else:
            assert {item.entity.canonical_id for item in result.evidence} == set(identifiers)
            assert result.answer.status == "fulfilled"
            assert result.answer.completeness.exact_total == 2
    asyncio.run(check())


def test_incompatible_single_seed_offer_retains_paid_selector_usage(tmp_path):
    # covers: KM-500e-1-i
    # covers: DK-300d-4-i
    # angle: failure
    # angle: seam
    """Refusing an offer that cannot bind both identities still records its paid decision."""
    from tests.kernel.entity_context.graph_selection_support import SelectionRig

    selection = SelectionRig(tmp_path / "repository")
    identifiers = ["decision_kernel", "knowledge_management"]
    question = "Compare the two specified components."
    ctx = selection.context(question, components=identifiers)
    selection.choice = "get_component_context"
    result, _, _ = selection.run(question, context=ctx, answer_requirements={
        "original_question": question, "required_fields": ["canonical_id"],
        "scope": {"entity_ids": identifiers}, "require_complete": True})
    assert len(selection.operation_batches()) == 1
    assert not selection.port.calls
    assert result.status.value != "completed"
    assert not result.evidence
    assert sum(item.calls for item in result.usage) == 1
    assert sum(item.input_tokens or 0 for item in result.usage) == 17
    assert sum(item.output_tokens or 0 for item in result.usage) == 3


@pytest.mark.parametrize("label,prefix", [("ticket", "Ticket"), ("flow", "Flow"), ("decision", "Decision")])
def test_prefixed_canonical_targets_match_original_scope_and_query_seeds(label, prefix):
    # covers: KM-500e-1-i
    # angle: boundary
    # angle: discrimination
    """Native and already-prefixed literals use the same IDs in obligations and query seeds."""
    from integrations.graph_offers import canonical_target_ids
    from integrations.research_needs import RepositoryNeedsInterpreter
    from kernel.capabilities.research.state import Plan
    from kernel.contracts.retrieval_needs import RetrievalNeedsOutput
    from tests.knowledge.public_retrieval_needs_support import controlled_needs

    question = f"Compare {label} one and {prefix}:two."
    output = RetrievalNeedsOutput.model_validate(controlled_needs(
        {"original_question": question, "source_scope": {}}, completeness="selected_entities",
        selections={"entity_types": [label], "target_ids": ["one", f"{prefix}:two"],
            "required_fields": ["title"], "document_types": [label], "relationships": []}))
    plan = Plan(question=question, expected_coverage="", mandated=[], source_restrictions=[])
    interpreted = RepositoryNeedsInterpreter().apply(plan, output)
    expected = [f"{prefix}:one", f"{prefix}:two"]
    assert interpreted.answer_requirements["scope"]["entity_ids"] == expected
    assert list(canonical_target_ids(output, prefix)) == expected


@pytest.mark.parametrize("invalid", ["original_question", "scope_shape"])
def test_malformed_explicit_requirements_are_rejected_before_selector_spending(tmp_path, invalid):
    # covers: KM-500e-1-i
    # covers: DK-300d-4-i
    # angle: failure
    # angle: boundary
    """The public binding validates supplied requirements before making a paid choice."""
    from tests.kernel.entity_context.graph_selection_support import AC_ID, SelectionRig

    selection = SelectionRig(tmp_path / "repository")
    question = f"Explain {AC_ID}."
    requirements = {"original_question": question, "required_fields": ["canonical_id"],
        "scope": {"entity_ids": [AC_ID]}, "require_complete": True}
    if invalid == "original_question":
        requirements["original_question"] = ""
    else:
        requirements["scope"] = {"entity_ids": "not-a-list"}
    result, _, _ = selection.run(question, answer_requirements=requirements)
    assert result.status.value == "failed"
    assert result.error and result.error.code == "knowledge_invalid_request"
    assert not selection.port.calls
    assert not result.evidence
    assert selection.jev.call_count == 0, "Invalid caller requirements spent a model call"
    assert result.usage == []
