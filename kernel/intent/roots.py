"""
MODULE: kernel.intent.roots
GOAL: Turn a resolved answer kind into the root request the scheduler routes (decision root,
    research root or an options request) and into the plain declines for kinds the read-only
    kernel does not serve (`change`, `out_of_domain`).
BUSINESS CONTEXT: A decline is an honest, deterministic answer, not a capability gap: a write
    request is a permission-type observation (spec 13.3/13.4: a denied native action is never
    reclassified as a missing capability) and an out-of-domain request is recorded without ever
    becoming a build opportunity (spec 14: only true capability gaps are).
ARCHITECTURE: Pure functions over contract models; no scheduler imports. The route node applies
    the results (updates the request and task, blocks the item, records the observation).
"""

from __future__ import annotations

from dataclasses import dataclass

from kernel.contracts import GapType, Request, RequestKind, Task, schema_ids
from kernel.contracts.payloads import OptionsRequestPayload
from kernel.intent.classify import (
    CHANGE,
    IDEAS,
    INTENT_DEFAULT,
    INTENT_EXPLICIT,
    KIND_SCHEMA,
    OUT_OF_DOMAIN,
)

WRITE_PERMISSION = "write_repo"
#: A typed caller input already names its output contract (deterministic, no classification).
PAYLOAD_OUTPUT = {schema_ids.DECISION_REQUEST: schema_ids.DECISION_REPORT,
                  schema_ids.RESEARCH_REQUEST: schema_ids.EVIDENCE_BUNDLE,
                  schema_ids.OPTIONS_REQUEST: schema_ids.OPTIONS}


@dataclass(frozen=True)
class Decline:
    """A plain refusal: limitation code and message, and the gap type it is recorded under."""

    code: str
    message: str
    gap_type: GapType


DECLINES = {
    CHANGE: Decline(
        "out_of_scope_write",
        "The kernel is read-only; implementing or editing is not supported. You can ask it "
        "to decide what to implement or to find relevant evidence.", GapType.PERMISSION),
    OUT_OF_DOMAIN: Decline(
        "out_of_domain",
        "This request is not about software engineering in this repository, so the kernel "
        "cannot help with it. Ask about the code, its design decisions or its documentation.",
        GapType.OUT_OF_DOMAIN),
}


def initial_contract(requested: str | None, payload_schema: str | None) -> tuple[str, str | None]:
    """Return the root's provisional output contract and how it was resolved at intake.

    Args:
        requested: The caller's `requested_output_schema` (None when not chosen).
        payload_schema: The caller's input payload schema (None when no payload was given).

    Returns:
        tuple: (output schema, intent). Intent is `explicit` when the caller chose the contract
            (directly or through a typed payload), `default` for an unknown typed payload, and
            None when the goal must still be classified (the schema is then provisional).
    """
    if requested is not None:
        return requested, INTENT_EXPLICIT
    if payload_schema in PAYLOAD_OUTPUT:
        return PAYLOAD_OUTPUT[payload_schema], INTENT_EXPLICIT
    if payload_schema is not None:
        return schema_ids.DECISION_REPORT, INTENT_DEFAULT
    return schema_ids.DECISION_REPORT, None


def root_contract_bound(task: Task, request: Request, item_id: str) -> bool:
    """Whether the root contract already resolves its answer kind.

    Args:
        task: The current task, including any classified intent and the root identity.
        request: The validated request currently being routed.
        item_id: The work item owning this request; children never inherit this binding.

    Returns:
        bool: Classified root intents or the exact research-to-evidence pair are bound.
            Eligibility and the single-candidate check remain the router's responsibility.
    """
    typed_research = (request.kind is RequestKind.CAPABILITY
                      and request.payload_schema == schema_ids.RESEARCH_REQUEST
                      and request.requested_output_schema == schema_ids.EVIDENCE_BUNDLE)
    return (item_id == task.root_work_item_id
            and (task.intent in KIND_SCHEMA or typed_research))


def decline_for(kind: str) -> Decline | None:
    """Return the decline for a kind the kernel does not serve, or None when it is served."""
    return DECLINES.get(kind)


def decline_limitation(decline: Decline) -> str:
    """Return the `code: message` limitation text of a decline."""
    return f"{decline.code}: {decline.message}"


def write_denial_reason(permissions: list[str]) -> str:
    """Say why a write request cannot run: the permissions forbid it, or no capability exists.

    The check is deterministic and runs before any routing: a write request is never offered to
    a permissive fallback, whichever of the two reasons applies.
    """
    if WRITE_PERMISSION not in permissions:
        return ("the kernel is read-only by design: no capability writes to the repository, "
                "whatever permissions the caller holds")
    return "the kernel is read-only by design: no registered capability writes to the repository"


def shape_root(request: Request, kind: str, goal: str) -> Request:
    """Return the root request resolved for a served answer kind.

    Args:
        request: The provisional root request created at intake.
        kind: `decision`, `evidence` or `ideas`.
        goal: The effective goal (as clarified); the original stays on the task.

    Returns:
        Request: Decision and evidence stay `capability` requests over a goal payload with their
            output contract; ideas become an `options` request (an options_request.v1 payload
            for `host.generate_options`). The dedup key must be recomputed by the caller.
    """
    update: dict = {"goal": goal, "requested_output_schema": KIND_SCHEMA[kind]}
    if kind == IDEAS:
        body = OptionsRequestPayload(problem=goal)
        update.update(kind=RequestKind.OPTIONS, payload_schema=schema_ids.OPTIONS_REQUEST,
                      payload=body.model_dump(mode="json"), question=goal)
    else:
        update.update(kind=RequestKind.CAPABILITY, payload_schema=schema_ids.GOAL_REQUEST,
                      payload={"goal": goal})
    return request.model_copy(update=update)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 23:00 [python-coder]: The write denial says the kernel is read-only by design: it
#   blamed the caller permissions although granting write_repo changes nothing.
#   (#KernelBootstrapV0/GROUND)
# - 2026-10-01 22:00 [python-coder]: `ideas` becomes an `options` root request (a direct root
#   binding to host.generate_options through ordinary eligibility) instead of a thin parent that
#   spawns it: nothing would decide afterwards, and the options stay `proposed` in the report.
#   (#KernelBootstrapV0/INTENT)
# - 2026-10-01 22:00 [python-coder]: A write request is declined with the same text whether the
#   permissions forbid writes or no write capability exists; the reason is recorded in the event
#   detail, never offered as a fallback. (#KernelBootstrapV0/INTENT)
# - 2026-10-02 16:54 [python-coder]: Recognize only the validated research pair at the root;
#   eligibility and semantic alternatives still govern dispatch. (#KM-500a/2)
# ====================================================================
