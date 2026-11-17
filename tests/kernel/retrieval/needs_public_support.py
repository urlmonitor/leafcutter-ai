"""Cooperating host responses for public graph-flow compatibility tests."""

from kernel.contracts import RunStatus
from tests.knowledge.public_retrieval_needs_support import (
    controlled_needs, host_submission, packet_request,
)


async def resume_graph_needs(service_factory, pending, *, target, entity_type, document_type,
                             relationship=None, completeness="single_entity"):
    """Answer the actual durable needs packet without selecting an operation."""
    assert pending.status is RunStatus.WAITING_HOST, pending.model_dump_json()
    assert pending.pending_interaction.operation == "interpret_retrieval_needs"
    request = packet_request(pending)
    response = controlled_needs(request, target, ("content",), completeness=completeness)
    response["selections"].update(entity_types=[entity_type], document_types=[document_type],
                                  relationships=[relationship] if relationship else [])
    return await service_factory().resume_run(pending.run_id, host_submission(pending, response))
