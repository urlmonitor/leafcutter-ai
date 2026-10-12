"""Controlled host responses for public answer-obligation lifecycle regressions.

The real scheduler, interaction ledger and child-process checkpoint are exercised.
These responses assert wiring, not model interpretation quality or query answers.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace

from kernel.config import KernelConfig
from kernel.contracts import RunStatus, TaskInput, schema_ids
from kernel.contracts.run import RunEnvelope
from kernel.providers.fakes import choice_answer
from knowledge.query_catalog import QueryCatalog
from tests.kernel.integration.scenario_support import answer_human
from tests.knowledge.public_retrieval_needs_support import (
    controlled_needs, host_submission, packet_request,
)

CLARIFICATION = "Use root_excluded: exclude only TQ-500f itself, retaining all L2 and L3 descendants and their work statuses."


def configure_count_task(case, *, inclusion="clarify", fields=True, legacy=False):
    """Configure controlled external boundaries; only legacy callers supply an answer contract."""
    case.requirements["original_question"] = (
        "How many TQ-500f test-writing ACs are there and what work statuses do they have, excluding parent requirements?"
        if inclusion == "clarify" else
        "Count every L2 and L3 descendant of TQ-500f, exclude only TQ-500f itself, and show work statuses.")
    case.catalog = SimpleNamespace(descriptors=lambda: []) if legacy else QueryCatalog(case.run_root / "query-catalog")

    async def pin(repository_id, source_sha="latest"):
        return {"repository_id": repository_id, "source_sha": "a" * 40,
            "generation_id": "controlled-generation", "supported_kinds": ["AcceptanceCriterion"],
            "supported_fields": {"AcceptanceCriterion": ["canonical_id", "level"]
                + ([] if getattr(case, "mapping_gap", False) else ["work_status"])},
            "supported_relationships": ["parent", "depends_on"]}

    case.admission = SimpleNamespace(pin=pin)
    case.jev.script("knowledge.query_readiness", "readiness", choice_answer("ready"))
    case.jev.script("knowledge.query_target", "kind", choice_answer("AcceptanceCriterion"))
    case.jev.script("knowledge.query_select", "query", choice_answer("build"))
    case.operation = "query_catalog" if legacy else "get_ac_descendants"
    if legacy:
        case.requirements.update(required_fields=["work_status"] if fields else [], scope={
            "population": "ac_descendants", "root_id": "TQ-500f", "levels": ["L2", "L3"],
            "inclusion": inclusion})
    raw = case.research_task().model_dump(mode="json")
    if not legacy:
        raw["input_payload"].pop("answer_requirements")
    return TaskInput.model_validate(raw)


def count_response(request, *, inclusion="clarify", fields=True):
    """Return an explicit controlled interpretation of all dimensions in one host response."""
    needs = ["work_status"] if fields else []
    explicit_levels = any("L2" in text and "L3" in text
        for text in [request["original_question"], *request["context"]])
    unresolved = ([] if fields else ["Which required field or fact should the answer contain?"])
    if inclusion == "clarify":
        unresolved.append("Does excluding parents mean root_excluded (only TQ-500f) or terminal_leaves (every parent)?")
    selections = {"entity_types": ["ac"], "target_ids": ["TQ-500f"],
        "required_fields": needs, "document_types": ["ac_yaml"], "relationships": ["all_descendants"]}
    return controlled_needs(request, "TQ-500f", fields=needs, selections=selections,
        completeness="exhaustive_count", hierarchy_scope="unknown" if inclusion == "clarify" else "exclude_root",
        hierarchy_levels=["L2", "L3"] if explicit_levels else [], unresolved=unresolved,
        scope_resolution="user_choice_missing" if unresolved else "sufficient",
        status="needs_resolution" if unresolved else "decided")


async def accept_count(case, pending, *, inclusion="clarify", fields=True):
    """Submit to the actual durable interaction with measured controlled usage."""
    assert pending.status is RunStatus.WAITING_HOST, pending.model_dump_json()
    assert pending.pending_interaction.operation == "interpret_retrieval_needs"
    request = packet_request(pending)
    raw = host_submission(pending, count_response(request, inclusion=inclusion, fields=fields))
    raw["usage"] = [{"provider": "host", "calls": 1, "input_tokens": 11, "output_tokens": 7}]
    final = await case.service().resume_run(pending.run_id, raw)
    assert final.run_id == pending.run_id
    return final, request


async def interpret_count(case, task, *, inclusion="clarify", fields=True):
    """Start at question-only public intake, then answer the actual host interpretation wait."""
    assert "answer_requirements" not in task.input_payload
    pending = await case.service().start_run(task)
    assert not case.calls
    return await accept_count(case, pending, inclusion=inclusion, fields=fields)


def accepted_needs(values):
    """Read the real accepted typed child outputs from the persisted scheduler state."""
    outputs = [item.output_payload for item in values["results"].values()
        if item.output_schema_id == schema_ids.RETRIEVAL_NEEDS_OUTPUT]
    assert outputs and all(outputs)
    return outputs


async def _resume_child(case, raw):
    """Continue a human choice, then a fresh bound host wait, in the new OS process."""
    pending = RunEnvelope.model_validate(raw["pending"])
    response = answer_human(pending, {"free_text": CLARIFICATION})
    reinterpreting = await case.service().resume_run(pending.run_id, response)
    assert reinterpreting.status is RunStatus.WAITING_HOST
    assert reinterpreting.pending_interaction.operation == "interpret_retrieval_needs"
    request = packet_request(reinterpreting)
    assert request["original_question"] == raw["question"]
    assert request["source_scope"] == raw["source_scope"]
    assert CLARIFICATION in request["context"]
    assert not case.calls
    result, _ = await accept_count(case, reinterpreting, inclusion="root_excluded")
    values = await case.checkpoint_values(result.run_id)
    requests = [item for item in values["requests"].values()
        if item.payload_schema == schema_ids.RETRIEVAL_REQUEST]
    assert requests and case.calls
    requirements = requests[-1].payload["answer_requirements"]
    assert all(item.payload["answer_requirements"] == requirements for item in requests)
    assert all(item.payload["retrieval_needs"]["source_scope"] == raw["source_scope"] for item in requests)
    host_usage = [entry for entry in result.usage_summary.usage if entry.provider == "host"]
    return {"run_id": result.run_id, "status": result.status.value,
        "pending_operation": getattr(result.pending_interaction, "operation", None),
        "original_question": requirements["original_question"], "required_fields": requirements["required_fields"],
        "scope": requirements["scope"], "source_scope": request["source_scope"], "pid": os.getpid(),
        "interpretation_count": len(accepted_needs(values)), "host_operations": result.usage_summary.host_operations,
        "host_input_tokens": sum(entry.input_tokens or 0 for entry in host_usage),
        "host_output_tokens": sum(entry.output_tokens or 0 for entry in host_usage),
        "jev_calls": result.usage_summary.jev_calls, "operation": case.calls[0].operation}


def resume_count_in_child(case_type, path):
    """Reconstruct fixture collaborators while reopening the original on-disk run state."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    case = case_type()
    case.setUp()
    try:
        case.repo, case.run_root = Path(raw["repo"]), Path(raw["run_root"])
        case.config = KernelConfig.model_validate(raw["config"])
        case.natural_task()
        print(json.dumps(asyncio.run(_resume_child(case, raw))))
    finally:
        case.doCleanups()


# DECISION HISTORY
# - 2026-10-09 [test-writer]: Preserve host and human lifecycle across actual process restart. (#KM-500e-1-i)
