"""Construct typed child requests through the ordinary kernel scheduler."""
from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from kernel.contracts import RequestProposal
from kernel.contracts import schema_ids, RequestKind, RequestProposal
from kernel.contracts.query import QueryActivationRequest

QUERY_BUILD_REQUEST = schema_ids.QUERY_BUILD_REQUEST
QUERY_CANDIDATE = schema_ids.QUERY_CANDIDATE

def activation_request(*, candidate: dict, repository_id: str, source_sha: str, component_ids: list[str] | None = None) -> RequestProposal:
    """Request independent, permissioned admission of one host candidate.

    Returns:
        RequestProposal: Native activation child with a typed receipt contract.
    """
    payload = QueryActivationRequest(candidate=candidate, repository_id=repository_id,
                                     source_sha=source_sha,component_ids=component_ids or [])
    return RequestProposal(kind=RequestKind.CAPABILITY, question="Verify and activate bounded query",
        operation="activate_query", payload_schema=schema_ids.QUERY_ACTIVATION_REQUEST,
        payload=payload.model_dump(mode="json"),
        requested_output_schema=schema_ids.QUERY_ACTIVATION_RECEIPT)
