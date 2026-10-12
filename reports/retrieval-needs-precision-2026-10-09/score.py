"""Independent frozen interpretation grading; no model/backend calls or answer coaching."""
from __future__ import annotations

import json

from eval_support import BASE, cases, read, save, utc_now, verify_freeze

INCIDENTAL = {"canonical_id", "kind", "title", "source_sha", "source_locator"}


def minimal(fields, required, optional=INCIDENTAL):
    """Require all indispensable fields and reject unrelated extra obligations."""
    actual = set(fields)
    return set(required) <= actual and actual <= set(required) | set(optional)


def linked(selection: dict, content: bool) -> bool:
    """Allow one linked-test representation, with an optional declaration provenance side.

    Args:
        selection: Actual accepted finite labels.
        content: Whether the question requests source text rather than references.

    Returns:
        Whether result kinds, relationship and minimal fields preserve that request.
    """
    entities, documents = set(selection["entity_types"]), set(selection["document_types"])
    if (entities, documents) not in [({"test"}, {"code"}), ({"ac", "test"}, {"ac_yaml", "code"})]:
        return False
    if selection["relationships"] != ["covered_by"]:
        return False
    fields = set(selection["required_fields"])
    allowed = INCIDENTAL | ({"covered_by"} if "ac" in entities else set())
    if content:
        return minimal(fields, {"content"}, allowed)
    return bool(fields & {"canonical_id", "source_locator"}) and fields <= allowed


def reference_plan(selected: dict, output: dict) -> bool:
    """Recognize either complete declaration-list representation frozen before execution.

    Args:
        selected: Actual accepted finite labels.
        output: Actual host output containing requested completeness.

    Returns:
        Whether declaration fields or exhaustive linked references preserve the question.
    """
    direct = (selected["entity_types"] == ["ac"] and selected["document_types"] == ["ac_yaml"]
        and not selected["relationships"] and output["completeness"] == "single_entity"
        and minimal(selected["required_fields"], ["covered_by"]))
    return direct or (linked(selected, content=False) and output["completeness"] == "exhaustive_set")


def execution_gap(expected: dict, output: dict) -> dict:
    """Refuse declarations or status as proof of an actual test execution.

    Args:
        expected: Predeclared finite candidate and investigative-field allowances.
        output: Actual accepted host output.

    Returns:
        Shape checks, retaining the explicit manual explanation-meaning review.
    """
    selected = output["selections"]
    return {"explicit_unavailable_meaning": output["status"] == "needs_resolution"
            and "needs_outside_catalog" in output["unresolved"],
        "no_needless_user_choice": output["scope_resolution"] in {"unknown", "discovery_needed"},
        "offered_candidates_only": set(selected["entity_types"]) <= set(expected["candidate_entity_types"])
            and set(selected["document_types"]) <= set(expected["candidate_document_types"]),
        "no_proxy_execution_result": set(selected["required_fields"]) <= set(expected["investigative_fields_allowed"]),
        "explanation_present": bool(output.get("rationale", "").strip())
            or any(item != "needs_outside_catalog" for item in output["unresolved"])}


def meaning_checks(case: dict, output: dict) -> dict:
    """Check predeclared alternatives without treating model prose as field choices.

    Args:
        case: Frozen evaluator-only meaning expectations.
        output: Actual accepted host interpretation.

    Returns:
        Named independent checks for the requested representation.
    """
    expected, selected = case["expected"], output["selections"]
    kind, fields = expected["kind"], selected["required_fields"]
    if kind == "fields":
        return {"result_kind": selected["entity_types"] == expected["entity_types"],
            "document_kind": selected["document_types"] == expected["document_types"],
            "relationship": selected["relationships"] == expected["relationships"],
            "completeness": output["completeness"] == expected["completeness"],
            "minimal_fields": minimal(fields, expected["minimal_fields"])}
    if kind == "declared_references":
        return {"complete_declared_reference_plan": reference_plan(selected, output)}
    if kind == "one_test_source":
        return {"one_linked_test_source": linked(selected, content=True) and output["completeness"] == "examples"}
    if kind == "full_document":
        return {"single_canonical_document": selected["entity_types"] == ["ac"]
            and selected["document_types"] == ["ac_yaml"] and not selected["relationships"]
            and output["completeness"] == "single_entity", "full_document": output["detail_mode"] == "full_document"}
    return execution_gap(expected, output)


def grade(case: dict, output: dict, request: dict) -> dict:
    """Separate finite interpretation checks from manual explanation review and execution.

    Args:
        case: Frozen question and evaluator-only expected meanings.
        output: Accepted interpretation, without evaluator modifications.
        request: Actual production request presented to the host.

    Returns:
        Named checks and the explicit absence of retrieval proof.
    """
    selection = output["selections"]
    kind = case["expected"]["kind"]
    checks = {"original_question": output["original_question"] == case["question"],
        "trusted_source_scope": output["source_scope"] == request["source_scope"],
        "literal_anchor": selection["target_ids"] == [case["target"]],
        "no_hierarchy_expansion": output["hierarchy_scope"] == "not_applicable" and not output["hierarchy_levels"]}
    if kind != "execution_gap":
        checks.update(decided=output["status"] == "decided", sufficient=output["scope_resolution"] == "sufficient",
            detail_mode=output["detail_mode"] == ("full_document" if kind == "full_document" else "fields"))
    checks.update(meaning_checks(case, output))
    return {"finite_contract_pass": all(checks.values()), "checks": checks,
        "manual_explanation_review_required": kind == "execution_gap",
        "manual_review_rubric": ("Explanation must actually identify the unavailable execution outcome/run/tested-commit evidence; a generic unsupported statement is insufficient." if kind == "execution_gap" else None),
        "execution_fulfillment": "not_executed", "runtime_support_claim": False}


def score():
    """Score accepted immutable outputs against the previously frozen contrast manifest."""
    output = BASE / "stage1"
    verify_freeze(output)
    results = []
    for case in cases():
        directory = output / case["id"]
        if (directory / "failure.json").exists() or not (directory / "result.json").exists():
            results.append({"id": case["id"], "accepted": False, "finite_contract_pass": False})
            continue
        envelope = read(directory / "result.json")
        assert envelope["usage_summary"]["jev_calls"] == 0
        answer = (envelope.get("output") or {}).get("payload")
        if (envelope.get("status") != "completed"
                or (envelope.get("output") or {}).get("schema_id") != "leafcutter.retrieval_needs_output.v1"
                or not answer):
            results.append({"id": case["id"], "accepted": False, "finite_contract_pass": False})
            continue
        result = grade(case, answer, read(directory / "request.json"))
        results.append({"id": case["id"], "accepted": True, "question": case["question"],
                        "actual_output": answer, **result})
    summary = {"scored_at": utc_now(), "accepted": sum(r["accepted"] for r in results),
        "finite_contract_passes": sum(r["finite_contract_pass"] for r in results),
        "semantic_review": "Evaluator must inspect IP11 execution-gap explanation before final semantic signoff.",
        "cases": results, "jev_calls": 0, "graph_calls": 0, "execution_claim": False}
    save(output / "summary.json", summary)
    print(json.dumps({key: value for key, value in summary.items() if key != "cases"}))
