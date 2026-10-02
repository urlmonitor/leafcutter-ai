"""Conditional readiness comparison with explicit policy clauses.
MODULE: knowledge.assessment_readiness
GOAL: Separate canonical candidate facts from policy-driven recommendations.
BUSINESS CONTEXT: Completed work does not imply deployment or satisfied dependencies.
ARCHITECTURE: Pure supplied-policy interpretation; actual retrieval overrides candidate packets.
"""

from __future__ import annotations
from .assessment_evidence import structured
from .assessment_proof import verification


def readiness(payload: dict, evidence: list[dict], retrieval: object | None) -> dict:
    """Evaluate explicit equality clauses without inventing priority or readiness policy.

    Args:
        payload: Scoped assessment packet.
        evidence: Scoped supplied candidate, policy and report content.
        retrieval: Actual research result, when invoked through retrieval.

    Returns:
        Per-candidate clause interpretation and unresolved deployment/dependency limits.
    """
    policies = [(item, structured(item)) for item in evidence if item.get("kind") == "policy"]
    policies = [(item, value) for item, value in policies if _valid_policy(value)]
    if len(policies) != 1:
        return {
            "kind": "readiness",
            "status": "unresolved",
            "policy_id": None,
            "recommendations": [],
            "limitations": ["one attributable explicit supported policy is required"],
        }
    policy_item, policy = policies[0]
    candidates = _candidates(evidence, retrieval)
    proof = verification(payload, evidence, [])
    recommendations = [
        _recommend(candidate, policy, policy_item, proof) for candidate in candidates
    ]
    return {
        "kind": "readiness",
        "status": "partial" if recommendations else "unresolved",
        "policy_id": policy["id"],
        "policy_source": policy_item["source"],
        "recommendations": recommendations,
        "limitations": [
            "conditional policy interpretation; no canonical mutation or invented ranking",
            "deployment and dependency evidence remain separately required",
        ],
    }


def _valid_policy(value: dict | None) -> bool:
    """Support only a declared nonempty set of exact field-equality clauses.

    Args:
        value: Decoded explicit supplied policy.

    Returns:
        Whether the policy belongs to the supported comparison vocabulary.
    """
    return bool(
        value
        and value.get("id")
        and isinstance(value.get("clauses"), list)
        and value["clauses"]
        and all(
            isinstance(clause, dict)
            and clause.get("id")
            and clause.get("field")
            and "equals" in clause
            for clause in value["clauses"]
        )
    )


def _candidates(evidence: list[dict], retrieval: object | None) -> list[dict]:
    """Prefer actual canonical retrieval facts; never copy packet facts over them.

    Args:
        evidence: Scoped supplied candidate and policy content.
        retrieval: Actual final research response, if available.

    Returns:
        Candidate facts labeled canonical only when obtained from actual retrieval.
    """
    if retrieval is not None:
        return [
            {
                "canonical_id": item.entity.canonical_id,
                "facts": item.entity.properties,
                "canonical": True,
                "source": item.entity.source.model_dump(),
                "evidence_id": item.evidence_id,
            }
            for item in retrieval.evidence
            if item.entity.kind == "AcceptanceCriterion"
        ]
    candidates = []
    for item in evidence:
        if item.get("kind") != "candidate":
            continue
        value = structured(item)
        if value and value.get("canonical_id"):
            candidates.append(
                {
                    "canonical_id": value["canonical_id"],
                    "facts": value,
                    "canonical": False,
                    "source": item["source"],
                    "evidence_id": item["evidence_id"],
                }
            )
    return candidates


def _recommend(candidate: dict, policy: dict, policy_item: dict, proof: dict) -> dict:
    """Keep recorded status, clause interpretation and deployment reports separate.

    Args:
        candidate: Attributed candidate facts without mutation.
        policy: Explicit supported policy clauses.
        policy_item: Policy source and evidence identity.
        proof: Separate conditional verification assessment.

    Returns:
        Clause outcomes and inferred readiness distinct from canonical state.
    """
    facts = candidate["facts"]
    clauses = []
    for clause in policy["clauses"]:
        value = facts.get(clause["field"])
        state = "unknown" if value is None else ("met" if value == clause["equals"] else "unmet")
        clauses.append(
            {
                "id": clause["id"],
                "field": clause["field"],
                "expected": clause["equals"],
                "actual": value,
                "state": state,
            }
        )
    deployment = _deployment(candidate, policy, proof)
    states = {clause["state"] for clause in clauses}
    if policy.get("deployment_required") and deployment != "reported":
        states.add("unknown")
    if facts.get("depends_on"):
        states.add("unknown")
    readiness_state = (
        "not_ready" if "unmet" in states else ("unresolved" if "unknown" in states else "eligible")
    )
    return {
        "canonical_id": candidate["canonical_id"],
        "canonical_facts": facts if candidate["canonical"] else {},
        "supplied_facts": facts if not candidate["canonical"] else {},
        "source": candidate["source"],
        "evidence_ids": [candidate["evidence_id"], policy_item["evidence_id"]],
        "clauses": clauses,
        "readiness": readiness_state,
        "deployment": deployment,
        "interpretation": True,
        "dependency_evidence": "unresolved" if facts.get("depends_on") else "none declared",
    }


def _deployment(candidate: dict, policy: dict, proof: dict) -> str:
    """Match supplied deployment reports to candidate, tested revision and environment.

    Args:
        candidate: Candidate identity and source revision.
        policy: Explicit environment and deployment policy.
        proof: Supplied execution report assessment.

    Returns:
        Reported only for an applicable supplied deployment report, otherwise unverified.
    """
    environment = policy.get("environment")
    for receipt in proof["receipts"]:
        if (
            environment
            and receipt.get("environment") == environment
            and receipt.get("tested_sha") == candidate["source"]["source_sha"]
            and receipt.get("deployment") is True
            and receipt.get("execution_status") == "passed"
            and candidate["canonical_id"] in receipt.get("test_ids", [])
        ):
            return "reported"
    return "unverified"


# DECISION HISTORY
# - 2026-10-01 [python-coder]: Require explicit policy and preserve canonical statuses unchanged. (#EPIC-RepositoryResearchAnswers/TICKET-20261001-KM-500f-3)
