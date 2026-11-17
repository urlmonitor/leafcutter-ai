"""Public natural-language needs integration proof; provider answers are scripted.

The client sends no operation, selected fields or final answer. These tests prove
actual host/resume/retrieval wiring; separate live evaluations measure semantics.
"""

import asyncio
import subprocess

import pytest
import yaml

from kernel.contracts import RunStatus, schema_ids
from kernel.interaction import SubmissionRejected
from tests.kernel.integration.scenario_support import answer_human
from tests.knowledge.public_retrieval_needs_support import (
    ROOT, PublicNeedsHarness, controlled_needs, host_submission, packet_request, source_snapshot,
    interpret_public_question as _interpret, answer_assessments as _answers,
)


@pytest.fixture
def harness(request):
    value = PublicNeedsHarness().configure(catalog_enabled=request.param)
    yield value
    value.doCleanups()


@pytest.mark.parametrize("harness", [False, True], indirect=True)
def test_public_question_reaches_host_before_source_read(harness):
    # covers: KM-500e-1-i
    # angle: criterion
    # angle: reachability
    # angle: seam
    """Enabling catalog/admission cannot bypass the same needs interpretation boundary."""
    async def check():
        question = "For KM-500c-2, what must tests demonstrate?"
        result = await harness.service().start_run(harness.question(question))
        assert result.status is RunStatus.WAITING_HOST, result.model_dump_json()
        assert result.pending_interaction.operation == "interpret_retrieval_needs"
        assert result.pending_interaction.output_schema_id == schema_ids.RETRIEVAL_NEEDS_OUTPUT
        body = packet_request(result)
        assert body["original_question"] == question
        assert "criteria" in body["catalog"]["required_fields"]
        assert "KM-500c-2" in body["catalog"]["target_ids"]
        assert harness.storage.calls == [], "Retrieval executed before interpretation"
        values = await harness.checkpoint_values(result.run_id)
        assert "host.retrieval_needs" in harness.capabilities_used(values)
    asyncio.run(check())


@pytest.mark.parametrize("harness", [False, True], indirect=True)
@pytest.mark.parametrize("identifier", ["KM-500c-2", "KM-500c-1"])
def test_host_needs_drives_exact_criteria_through_public_entry(harness, identifier):
    # covers: KM-500e-1-i
    # covers: KM-500e-2
    # angle: seam
    # angle: real_artifact
    # angle: discrimination
    """A changed literal ID changes real source evidence; no canned answer can satisfy both."""
    async def check():
        question = f"For {identifier}, what must tests demonstrate?"
        final, values = await _interpret(harness, question, identifier)
        assert final.status is RunStatus.COMPLETED, final.model_dump_json()
        assert final.evidence_ids
        assert len([name for name in harness.capabilities_used(values) if name == "host.retrieval_needs"]) == 1
        requests = [item for item in values["requests"].values() if item.payload_schema == schema_ids.RETRIEVAL_REQUEST]
        assert requests and all(item.payload["answer_requirements"]["required_fields"] == ["criteria"] for item in requests)
        assert all(item.payload["retrieval_needs"]["original_question"] == question for item in requests)
        answers = _answers(values)
        assert answers and all(answer["status"] == "fulfilled" for answer in answers)
        selected = next(node for node in source_snapshot().nodes if node.canonical_id == identifier)
        raw = subprocess.check_output(["git", "show", f"{selected.source.source_sha}:{selected.source.path}"], cwd=ROOT)
        criteria = yaml.safe_load(raw)["criteria"]
        evidence = [item for item in values["evidence"].values() if identifier in item.source.locator]
        assert evidence and any(item.excerpt == criteria for item in evidence)
        assert all(item.source.source_version.commit == selected.source.source_sha for item in evidence)
        assert all(item[2] == "get_entities" and item[3]["entity_ids"] == [identifier] for item in harness.storage.calls)
        assert "host.query_build" not in harness.capabilities_used(values)
        if harness.catalog:
            assert harness.catalog.descriptors() == harness.catalog_before
            assert not harness.catalog.root.exists(), "Read-only retrieval persisted a catalog artifact"
    asyncio.run(check())


@pytest.mark.parametrize("harness", [False, True], indirect=True)
def test_public_population_preserves_levels_root_and_work_status(harness):
    # covers: KM-500e-1-i
    # covers: KM-500e-2
    # angle: seam
    # angle: discrimination
    """A fitting four-child subtree retains source-derived statuses and exact population."""
    async def check():
        harness.operation = "get_ac_descendants"
        harness.config = harness.config.model_copy(update={"retrieval": harness.config.retrieval.model_copy(update={"top_k": 6})})
        question = "Count every L2 and L3 AC under TQ-500f-3, excluding only TQ-500f-3 itself, grouped by work status."
        selections = {"entity_types": ["ac"], "target_ids": ["TQ-500f-3"],
            "required_fields": ["work_status", "level"], "document_types": ["ac_yaml"], "relationships": ["all_descendants"]}
        final, values = await _interpret(harness, question, "TQ-500f-3", selections=selections,
            completeness="exhaustive_count", hierarchy_scope="exclude_root", hierarchy_levels=["L2", "L3"])
        assert final.status is RunStatus.COMPLETED, final.model_dump_json()
        answers = _answers(values)
        assert answers and all(answer["status"] == "fulfilled" for answer in answers), answers
        answer = answers[-1]
        expected = [node for node in source_snapshot().nodes if node.canonical_id.startswith("TQ-500f-3-")
                    and node.properties["level"] in {"L2", "L3"}]
        counts = {}
        for node in expected:
            status = node.properties["work_status"]
            counts[status] = counts.get(status, 0) + 1
        assert answer["completeness"]["exact_total"] == len(expected)
        assert answer["work_status_counts"] == counts
        assert answer["scope"]["levels"] == ["L2", "L3"]
        assert answer["scope"]["inclusion"] == "root_excluded"
        assert "status" not in answer["required_fields"]
    asyncio.run(check())


@pytest.mark.parametrize("harness", [False, True], indirect=True)
def test_public_ambiguous_needs_clarifies_and_resumes_original_question(harness):
    # covers: KM-500e-1-i
    # angle: reachability
    # angle: boundary
    """A human-introduced root becomes a bounded candidate without rewriting the question."""
    async def check():
        question = "How many ACs concern test writing? Exclude parent requirements."
        harness.config = harness.config.model_copy(update={"retrieval": harness.config.retrieval.model_copy(update={"top_k": 6})})
        pending = await harness.service().start_run(harness.question(question))
        response = controlled_needs(packet_request(pending), None, (), status="needs_resolution",
            completeness="exhaustive_count", hierarchy_scope="exclude_parents", scope_resolution="user_choice_missing",
            unresolved=["Which canonical family and levels define test-writing scope, and does excluding parents mean only the root?"])
        human = await harness.service().resume_run(pending.run_id, host_submission(pending, response))
        assert human.status is RunStatus.WAITING_HUMAN, human.model_dump_json()
        assert harness.storage.calls == []
        clarifying = "Use TQ-500f-3, all L2 and L3 descendants; exclude only the root TQ-500f-3, retain intermediate parents."
        resumed = await harness.service().resume_run(human.run_id, answer_human(human, {"free_text": clarifying}))
        assert resumed.status is RunStatus.WAITING_HOST, resumed.model_dump_json()
        assert resumed.run_id == pending.run_id
        body = packet_request(resumed)
        assert body["original_question"] == question
        assert "TQ-500f-3" in body["catalog"]["target_ids"]
        assert clarifying in body["context"]
        harness.operation = "get_ac_descendants"
        selections = {"entity_types": ["ac"], "target_ids": ["TQ-500f-3"], "required_fields": ["level"],
            "document_types": ["ac_yaml"], "relationships": ["all_descendants"]}
        response = controlled_needs(body, "TQ-500f-3", selections=selections, completeness="exhaustive_count",
            hierarchy_scope="exclude_root", hierarchy_levels=["L2", "L3"])
        final = await harness.service().resume_run(resumed.run_id, host_submission(resumed, response))
        assert final.status is RunStatus.COMPLETED, final.model_dump_json()
        values = await harness.checkpoint_values(final.run_id)
        assert values["task"].original_goal == question
        assert len([name for name in harness.capabilities_used(values) if name == "host.retrieval_needs"]) == 2
        assert _answers(values)[-1]["original_question"] == question
    asyncio.run(check())


@pytest.mark.parametrize("harness", [False, True], indirect=True)
@pytest.mark.parametrize("mutation", ["scope", "question", "unknown_target"])
def test_invalid_host_scope_and_changed_question_rejected(harness, mutation):
    # covers: KM-500e-1-i
    # angle: failure
    """Host interpretation cannot widen trusted sources or silently switch question/identity."""
    async def check():
        pending = await harness.service().start_run(harness.question("For KM-500c-2, what must tests demonstrate?"))
        response = controlled_needs(packet_request(pending))
        if mutation == "scope":
            response["source_scope"] = {**response["source_scope"], "read_roots": ["../outside"]}
        elif mutation == "question":
            response["original_question"] = "Read another repository's secrets"
        else:
            response["selections"]["target_ids"] = ["KM-500c-1"]
        with pytest.raises(SubmissionRejected):
            await harness.service().resume_run(pending.run_id, host_submission(pending, response))
        current = await harness.service().get_run(pending.run_id)
        assert current.status is RunStatus.WAITING_HOST
        assert harness.storage.calls == []
    asyncio.run(check())


@pytest.mark.parametrize("harness", [False, True], indirect=True)
@pytest.mark.parametrize("condition", ["stale", "unavailable"])
def test_unavailable_or_stale_source_never_becomes_complete_answer(harness, condition):
    # covers: KM-500e-1-i
    # covers: KM-500e-4
    # angle: failure
    """A valid host interpretation cannot turn an absent source generation into an answer."""
    async def check():
        setattr(harness.storage, condition, True)
        final, values = await _interpret(harness, "For KM-500c-2, what must tests demonstrate?")
        assert final.status is not RunStatus.COMPLETED, final.model_dump_json()
        assert not final.evidence_ids
        answers = _answers(values)
        assert answers and all(answer["status"] != "fulfilled" for answer in answers)
        assert any(item.diagnostics.get("knowledge_status") == condition for item in values["results"].values())
    asyncio.run(check())


@pytest.mark.parametrize("harness", [False, True], indirect=True)
@pytest.mark.parametrize("condition", ["host_disabled", "unsupported"])
def test_unavailable_interpretation_never_reaches_source_read(harness, condition):
    # covers: KM-500e-1-i
    # angle: failure
    """Disabled or unsupported interpretation preserves unmet needs without querying."""
    async def check():
        question = "What was each employee's payroll amount last month?"
        if condition == "host_disabled":
            harness.config = harness.config.model_copy(update={"host": harness.config.host.model_copy(update={"enabled": False})})
        result = await harness.service().start_run(harness.question(question))
        if condition == "unsupported":
            request = packet_request(result)
            response = controlled_needs(request, None, (), status="needs_resolution",
                detail_mode="unknown", completeness="unknown", scope_resolution="unknown",
                selections={name: [] for name in request["catalog"]}, unresolved=["needs_outside_catalog"])
            result = await harness.service().resume_run(result.run_id, host_submission(result, response))
        assert result.status is RunStatus.PARTIAL
        assert harness.storage.calls == []
        assert not result.evidence_ids
        assert result.output.payload["assessments"]["retrieval_needs"]["status"] == "unresolved"
    asyncio.run(check())


@pytest.mark.parametrize("harness", [False, True], indirect=True)
def test_count_beyond_result_budget_cannot_be_reported_complete(harness):
    # covers: KM-500e-1-i
    # covers: KM-500e-2
    # angle: boundary
    # angle: discrimination
    """Default six-result budget cannot silently become an exhaustive fifteen-AC answer."""
    async def check():
        harness.operation = "get_ac_descendants"
        harness.config = harness.config.model_copy(update={"retrieval": harness.config.retrieval.model_copy(update={"top_k": 6})})
        question = "Count all L2 and L3 descendants of TQ-500f, excluding only the root, by work status."
        selected = {"entity_types": ["ac"], "target_ids": ["TQ-500f"], "required_fields": ["work_status", "level"],
                    "document_types": ["ac_yaml"], "relationships": ["all_descendants"]}
        final, values = await _interpret(harness, question, "TQ-500f", selections=selected,
            completeness="exhaustive_count", hierarchy_scope="exclude_root", hierarchy_levels=["L2", "L3"])
        assert final.status is not RunStatus.COMPLETED
        answers = _answers(values)
        assert answers and all(answer["status"] != "fulfilled" for answer in answers)
        assert all(answer["completeness"]["exact_total"] is None for answer in answers)
        assert all(answer["work_status_counts"] is None for answer in answers)
    asyncio.run(check())


@pytest.mark.parametrize("harness", [False, True], indirect=True)
def test_partial_source_cannot_be_upgraded_by_sufficient_jev(harness):
    # covers: KM-500e-1-i
    # covers: KM-500e-2
    # angle: discrimination
    """Removing the actual requested field defeats a high-confidence sufficiency judgment."""
    async def check():
        harness.storage.omit_field = "work_status"
        final, values = await _interpret(harness, "What is the work status of KM-500c-2?", fields=("work_status",))
        assert final.status is not RunStatus.COMPLETED, final.model_dump_json()
        answers = _answers(values)
        assert answers and all(answer["status"] != "fulfilled" for answer in answers)
        assert any(item["field"] == "work_status" for answer in answers for item in answer["missing_fields"])
    asyncio.run(check())


@pytest.mark.parametrize("harness", [False, True], indirect=True)
@pytest.mark.parametrize("shape", ["full_document", "relationship", "multiple_types"])
def test_unsupported_valid_needs_remain_explicitly_unresolved(harness, shape):
    # covers: KM-500e-1-i
    # angle: discrimination
    # angle: failure
    """Accepted finite catalog values must not imply unsupported execution is implemented."""
    async def check():
        overrides = {}
        if shape == "full_document":
            overrides["detail_mode"] = "full_document"
        else:
            selection = {"entity_types": ["ac"], "target_ids": ["KM-500c-2"],
                "required_fields": ["criteria"], "document_types": ["ac_yaml"], "relationships": []}
            if shape == "relationship":
                selection["relationships"] = ["covered_by"]
            else:
                selection["entity_types"] = ["ac", "adr"]
                selection["document_types"] = ["ac_yaml", "adr"]
            overrides["selections"] = selection
        final, values = await _interpret(harness, "For KM-500c-2, what must tests demonstrate?", **overrides)
        assert final.status is RunStatus.PARTIAL, final.model_dump_json()
        assert harness.storage.calls == []
        assert not final.evidence_ids
        assert final.output.payload["assessments"]["retrieval_needs"]["status"] == "unresolved"
    asyncio.run(check())


@pytest.mark.parametrize("harness", [False, True], indirect=True)
def test_missing_final_jev_judgment_cannot_complete_fulfilled_source_answer(harness):
    # covers: KM-500e-1-i
    # angle: failure
    # angle: seam
    """Real criteria retrieval is insufficient when the required final assessor fails."""
    async def check():
        harness.jev._rules = [rule for rule in harness.jev._rules
            if not (rule.purpose == "research.assess" and rule.question_glob == "answers.*")]
        final, values = await _interpret(harness, "For KM-500c-2, what must tests demonstrate?")
        assert final.status is not RunStatus.COMPLETED, final.model_dump_json()
        assert final.evidence_ids
        assert any(answer["status"] == "fulfilled" for answer in _answers(values))
        assert harness.jev.questions_asked("research.assess")
    asyncio.run(check())


@pytest.mark.parametrize("harness", [True], indirect=True)
def test_previously_admitted_saved_query_keeps_digest_and_public_obligations(harness, monkeypatch):
    # covers: KM-500e-1-i
    # covers: KM-500b-3
    # angle: seam
    # angle: real_artifact
    """An existing saved AC query is selectable without granting write authority to research."""
    async def check():
        from knowledge.adapters.neo4j_backend import scope_key
        from tests.knowledge.public_retrieval_needs_support import REPOSITORY

        from knowledge.service import KnowledgeService

        requests = []
        original_retrieve = KnowledgeService.retrieve
        async def observed_retrieve(service, request):
            requests.append(request)
            return await original_retrieve(service, request)
        monkeypatch.setattr(KnowledgeService, "retrieve", observed_retrieve)
        calls = []
        async def compiled_read(statement, parameters=None, write=False):
            calls.append((statement, parameters, write))
            snapshot = source_snapshot()
            selected = [node for node in snapshot.nodes
                if node.canonical_id in parameters["arg_ac_ids"]]
            if parameters["scope_key"] != scope_key(REPOSITORY, snapshot.generation_id):
                selected = []
            return [{"payloads": [node.model_dump_json() for node in selected], "expansion_truncated": False}]

        harness.storage._run = compiled_read
        operation = "get_saved_ac_obligations"
        candidate = {"descriptor": {"operation": operation, "version": "1",
            "description": "Retrieve the exact selected acceptance criteria and their authoritative obligations",
            "questions": ["What must tests demonstrate for this AC?"],
            "parameters": {"ac_ids": {"type": "string_list", "required": True}},
            "recipe": {"seed_parameter": "ac_ids", "seed_kind": "AcceptanceCriterion", "steps": []}},
            "reviewer": "explicit controlled fixture setup",
            "cases": [{"name": "actual AC", "arguments": {"ac_ids": ["KM-500c-2"]}, "expected_ids": ["KM-500c-2"]},
                {"name": "missing", "arguments": {"ac_ids": ["ABSENT-1"]}, "expected_ids": []}]}
        admitted = await harness.admission.verify_and_activate(candidate,
            repository_id=REPOSITORY, source_sha=source_snapshot().source_sha)
        original_catalog = (harness.catalog.root / "catalog.json").read_bytes()
        calls.clear()
        harness.operation = operation
        final, values = await _interpret(harness, "For KM-500c-2, what must tests demonstrate?")
        assert final.status is RunStatus.COMPLETED, final.model_dump_json()
        assert _answers(values)[-1]["required_fields"] == ["criteria"]
        assert _answers(values)[-1]["status"] == "fulfilled"
        assert calls and all(not call[2] for call in calls)
        assert all(call[1]["arg_ac_ids"] == ["KM-500c-2"] for call in calls)
        assert (harness.catalog.root / "catalog.json").read_bytes() == original_catalog
        assert requests and requests[0].operation == operation
        assert requests[0].operation_digest == admitted["digest"]
        assert requests[0].arguments == {"ac_ids": ["KM-500c-2"]}
        assert all(request.answer_requirements.required_fields == ["criteria"] for request in requests)
        assert all(request.operation == "get_entities" and request.arguments == {"entity_ids": ["KM-500c-2"]}
                   for request in requests[1:])
        assert "host.query_build" not in harness.capabilities_used(values)
    asyncio.run(check())


@pytest.mark.parametrize("harness", [False, True], indirect=True)
@pytest.mark.parametrize("control", ["complete", "outside_read_root", "tiny_excerpt"])
def test_authored_criteria_and_test_spec_survive_public_disclosure(harness, control):
    # covers: KM-500e-1-i
    # covers: KM-500e-2
    # angle: real_artifact
    # angle: discrimination
    # angle: boundary
    """An authored test spec must reach evidence with its locator, or remain explicitly incomplete."""
    async def check():
        question = "For KM-500c-2, what must tests demonstrate?"
        task = harness.question(question)
        if control == "outside_read_root":
            task = task.model_copy(update={"scope": task.scope.model_copy(update={"read_roots": ["tests"]})})
        elif control == "tiny_excerpt":
            harness.config = harness.config.model_copy(update={"retrieval":
                harness.config.retrieval.model_copy(update={"max_excerpt_chars": 100})})
        pending = await harness.service().start_run(task)
        response = controlled_needs(packet_request(pending), fields=("criteria", "test_spec"))
        final = await harness.service().resume_run(pending.run_id, host_submission(pending, response))
        values = await harness.checkpoint_values(final.run_id)
        selected = next(node for node in source_snapshot().nodes if node.canonical_id == "KM-500c-2")
        raw = subprocess.check_output(["git", "show", f"{selected.source.source_sha}:{selected.source.path}"], cwd=ROOT)
        source = yaml.safe_load(raw)
        assert source["test_spec"], "This regression requires a real authored test spec"
        if control != "complete":
            assert final.status is not RunStatus.COMPLETED, final.model_dump_json()
            if control == "outside_read_root":
                assert not final.evidence_ids
            return
        assert final.status is RunStatus.COMPLETED, final.model_dump_json()
        assert _answers(values)[-1]["required_fields"] == ["criteria", "test_spec"]
        assert _answers(values)[-1]["missing_fields"] == []
        evidence = list(values["evidence"].values())
        disclosed = "\n".join(item.excerpt or "" for item in evidence)
        assert source["criteria"].strip() in disclosed
        assert source["test_spec"][0]["name"] in disclosed
        test_specs = [item for item in evidence if item.source.section_locator == "/test_spec"]
        assert test_specs and all("test_spec" in item.source.locator for item in test_specs)
        assert any(yaml.safe_load(item.excerpt) == source["test_spec"] for item in test_specs)
    asyncio.run(check())
