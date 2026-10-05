"""Resolve bounded local contracts and validate examples without network or arbitrary imports.

GOAL: Check documented JSON facts against their real schema and optional runtime model.
BUSINESS CONTEXT: Readable handoffs must not silently drift from callable contracts.
ARCHITECTURE: Local JSON Schema plus an explicit, lazy Pydantic model allowlist.
"""
from __future__ import annotations
import copy
import json
import sys
from pathlib import Path
from typing import get_args
import jsonschema

SCHEMA_ROOTS = ("docs/product-truth/schemas/", "kernel/schemas/", "config/")
EXAMPLE_ROOTS = ("reports/", "docs/product-truth/")


def bounded_path(root, relative, allowed):
    """Resolve an allowed repository-relative path, including symlink containment."""
    if not isinstance(relative, str) or "\\" in relative or not relative.startswith(allowed):
        raise ValueError(f"path is outside allowed roots: {relative}")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes repository: {relative}")
    if not any(path.is_relative_to((root / prefix).resolve()) for prefix in allowed):
        raise ValueError(f"path escapes its allowed root: {relative}")
    return path


def pointer(value, path):
    """Read an RFC 6901 pointer; field wildcards are handled separately."""
    if path == "":
        return value
    if not path.startswith("/"):
        raise ValueError(f"invalid JSON pointer: {path}")
    for token in path[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


SCHEMA_MAPS = {"properties", "patternProperties", "$defs", "definitions", "dependentSchemas"}
SCHEMA_SINGLE = {"additionalProperties", "unevaluatedProperties", "propertyNames", "contains", "additionalItems",
                 "unevaluatedItems", "not", "if", "then", "else"}
SCHEMA_ARRAYS = {"allOf", "anyOf", "oneOf", "prefixItems"}


def map_schema(schema, transform):
    """Visit schema locations only: property names and const/default data remain literal."""
    if not isinstance(schema, dict):
        return schema
    result = copy.deepcopy(schema)
    for key, value in schema.items():
        if key in SCHEMA_MAPS and isinstance(value, dict):
            result[key] = {name: map_schema(child, transform) for name, child in value.items()}
        elif key in SCHEMA_SINGLE or key == "items" and isinstance(value, (dict, bool)):
            result[key] = map_schema(value, transform)
        elif key in SCHEMA_ARRAYS or key == "items" and isinstance(value, list):
            result[key] = [map_schema(child, transform) for child in value]
        elif key == "dependencies" and isinstance(value, dict):
            result[key] = {name: map_schema(child, transform) if isinstance(child, (dict, bool)) else child
                           for name, child in value.items()}
    return transform(result)


def safe_schema(schema):
    """Reject every non-fragment reference before a validator can resolve it."""
    def check(node):
        for key in ("$ref", "$dynamicRef", "$recursiveRef"):
            if key in node:
                value = node[key]
                if not isinstance(value, str) or not value.startswith("#"):
                    raise ValueError(f"only local fragment schema references are allowed: {value}")
                if value.startswith("#/"):
                    pointer(schema, value[1:])
        return node
    map_schema(schema, check)


def model_for(name):
    """Import only this package's reviewed model set, never an authored import path."""
    names = {"retrieval_needs_request", "retrieval_needs_output", "task_input", "scope", "actor",
             "host_work_request", "interaction_submission", "submission_record", "capability_invocation",
             "capability_result", "run_envelope", "work_item", "decision", "enriched_context", "human_question",
             "decision_record", "decision_index_entry", "decision_query", "provider_answer", "option", "criterion",
             "option_ranking", "evidence", "knowledge_request", "knowledge_result", "projection_snapshot",
             "answer_requirements", "answer_assessment", "query_descriptor", "query_candidate",
             "jev_batch", "jev_result", "choice_answer", "decision_request", "decision_report",
             "research_request", "evidence_bundle", "options_request", "options", "synthesis_request",
             "findings", "human_answer", "goal_request"}
    if name not in names:
        raise ValueError(f"model is not allowlisted: {name}")
    package = str(Path(__file__).resolve().parents[3])
    if package not in sys.path:
        sys.path.insert(0, package)
    from kernel.contracts.retrieval_needs import RetrievalNeedsRequest, RetrievalNeedsOutput
    from kernel.contracts.task import TaskInput, Scope, Actor
    from kernel.contracts.interaction import HostWorkRequest, InteractionSubmission
    from kernel.contracts.capability import CapabilityResult
    from kernel.contracts.work import CapabilityInvocation, WorkItem
    from kernel.contracts.run import RunEnvelope
    from kernel.persistence.base import SubmissionRecord
    from kernel.contracts.context import EnrichedContext
    from kernel.contracts.interaction import HumanQuestion
    from kernel.contracts.decision import Decision, ProviderAnswer, Option, Criterion, OptionRanking
    from kernel.contracts.evidence import Evidence, EvidenceBundlePayload
    from kernel.contracts.payloads import (DecisionRequestPayload, DecisionReportPayload, ResearchRequestPayload,
        OptionsRequestPayload, OptionsPayload, SynthesisRequestPayload, FindingsPayload, HumanAnswerPayload, GoalRequestPayload)
    from kernel.memory.models import DecisionRecord
    from kernel.memory.index import IndexEntry
    from kernel.memory.port import DecisionQuery
    from knowledge.contracts import KnowledgeRetrievalRequest, KnowledgeRetrievalResult, ProjectionSnapshot
    from knowledge.answer_models import AnswerRequirements, AnswerAssessment
    from knowledge.query_models import QueryDescriptor, QueryCandidate
    from kernel.providers.base import JevBatch, JevResult, ChoiceAnswer
    extra_models = {"decision_request": DecisionRequestPayload, "decision_report": DecisionReportPayload,
                    "research_request": ResearchRequestPayload, "evidence_bundle": EvidenceBundlePayload,
                    "options_request": OptionsRequestPayload, "options": OptionsPayload,
                    "synthesis_request": SynthesisRequestPayload, "findings": FindingsPayload,
                    "human_answer": HumanAnswerPayload, "goal_request": GoalRequestPayload, "query_descriptor": QueryDescriptor, "query_candidate": QueryCandidate,
                    "jev_batch": JevBatch, "jev_result": JevResult, "choice_answer": ChoiceAnswer, "knowledge_request": KnowledgeRetrievalRequest, "knowledge_result": KnowledgeRetrievalResult,
                    "projection_snapshot": ProjectionSnapshot, "answer_requirements": AnswerRequirements,
                    "answer_assessment": AnswerAssessment,"decision": Decision, "enriched_context": EnrichedContext, "human_question": HumanQuestion,
                    "decision_record": DecisionRecord, "decision_index_entry": IndexEntry, "decision_query": DecisionQuery,
                    "provider_answer": ProviderAnswer, "option": Option, "criterion": Criterion,
                    "option_ranking": OptionRanking, "evidence": Evidence}
    if name in extra_models:
        return extra_models[name]
    return dict(zip(("retrieval_needs_request", "retrieval_needs_output", "task_input", "scope", "actor",
                     "host_work_request", "interaction_submission", "submission_record", "capability_invocation",
                     "capability_result", "run_envelope", "work_item"),
                    (RetrievalNeedsRequest, RetrievalNeedsOutput, TaskInput, Scope, Actor,
                     HostWorkRequest, InteractionSubmission, SubmissionRecord, CapabilityInvocation,
                     CapabilityResult, RunEnvelope, WorkItem)))[name]


def factory_defaults(schema, model):
    """Expose deterministic list/dict factories; never execute arbitrary default factories."""
    seen = set()
    def visit(cls, target):
        if cls in seen or not hasattr(cls, "model_fields"):
            return
        seen.add(cls)
        for name, field in cls.model_fields.items():
            prop = target.get("properties", {}).get(name, {})
            if field.default_factory is list:
                prop["default"] = []
            elif field.default_factory is dict:
                prop["default"] = {}
            pending = [field.annotation]
            while pending:
                annotation = pending.pop()
                if hasattr(annotation, "model_fields"):
                    visit(annotation, schema.get("$defs", {}).get(annotation.__name__, {}))
                else:
                    pending.extend(get_args(annotation))
    visit(model, schema)


def load_contract(definition, root):
    """Return schema and optional runtime validator, checking committed-schema parity."""
    model = model_for(definition["model"]) if "model" in definition else None
    generated = model.model_json_schema() if model else None
    if "schema" in definition:
        schema = json.loads(bounded_path(root, definition["schema"], SCHEMA_ROOTS).read_text(encoding="utf-8"))
        if generated is not None:
            plain = {k: v for k, v in schema.items() if k not in ("$id", "$schema")}
            if plain != generated:
                raise ValueError("committed JSON Schema differs from the runtime model")
    else:
        schema = generated
    if not isinstance(schema, dict):
        raise ValueError("contract needs a JSON Schema or allowlisted model")
    safe_schema(schema)
    jsonschema.validators.validator_for(schema).check_schema(schema)
    schema = copy.deepcopy(schema)
    if model:
        factory_defaults(schema, model)
    return schema, model


def dereference(schema, fragment):
    """Resolve a fragment in the current document without external resolution."""
    seen = set()
    while "$ref" in fragment:
        ref = fragment["$ref"]
        if ref in seen:
            raise ValueError("recursive reference cannot be traversed as a field")
        seen.add(ref)
        fragment = {**pointer(schema, ref[1:]), **{k: v for k, v in fragment.items() if k != "$ref"}}
    return fragment


def variants(schema, fragment):
    fragment = dereference(schema, fragment)
    choices = fragment.get("anyOf", fragment.get("oneOf"))
    return [v for c in choices for v in variants(schema, c)] if choices else [fragment]


def json_types(schema, fragment):
    result = set()
    for value in variants(schema, fragment):
        types = value.get("type", "object" if "properties" in value else None)
        if types is not None:
            result.update(types if isinstance(types, list) else [types])
        elif "const" in value or "enum" in value:
            for item in value.get("enum", [value.get("const")]):
                result.add("null" if item is None else "boolean" if isinstance(item, bool) else
                           "integer" if isinstance(item, int) else "number" if isinstance(item, float) else "string")
    return sorted(result)


def field_facts(schema, path):
    """Return field schema and immediate-container requiredness; '*' selects array/map values."""
    current, required = schema, True
    if path == "":
        return current, required
    if not path.startswith("/"):
        raise ValueError(f"invalid field pointer: {path}")
    for token in path[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        found = []
        for choice in variants(schema, current):
            if token in choice.get("properties", {}):
                found.append((choice["properties"][token], token in choice.get("required", [])))
            elif token == "*" and isinstance(choice.get("items"), dict):
                found.append((choice["items"], True))
            elif token == "*" and isinstance(choice.get("additionalProperties"), dict):
                found.append((choice["additionalProperties"], True))
        if not found:
            raise ValueError(f"unknown field path: {path}")
        required = all(item[1] for item in found)
        current = found[0][0] if len(found) == 1 else {"anyOf": [item[0] for item in found]}
    return dereference(schema, current), required


def relaxed(schema):
    """Projection validation removes only required keywords at schema locations."""
    return map_schema(schema, lambda node: {key: value for key, value in node.items() if key != "required"})


def validate_value(value, contract, projection=False):
    schema, model = contract
    checked = relaxed(schema) if projection else schema
    jsonschema.validators.validator_for(checked)(checked).validate(value)
    if model and not projection:
        model.model_validate(value)


def is_projection(part, whole):
    if isinstance(part, dict):
        return isinstance(whole, dict) and all(k in whole and is_projection(v, whole[k]) for k, v in part.items())
    if isinstance(part, list):
        return isinstance(whole, list) and len(part) == len(whole) and all(is_projection(a, b) for a, b in zip(part, whole))
    return type(part) is type(whole) and part == whole
