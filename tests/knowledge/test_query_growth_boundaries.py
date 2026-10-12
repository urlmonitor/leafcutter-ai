"""Independent failure-boundary checks for authored graph query growth."""
import asyncio

import pytest

from knowledge.errors import BackendUnavailable, KnowledgeError
from knowledge.query_execution import execute_query
from knowledge.query_models import QueryDescriptor
from tests.knowledge.test_query_admission import admission, candidate


def test_unmapped_memory_relation_cannot_masquerade_as_empty(tmp_path):
    # covers: KM-500a-3
    # angle: failure
    _, _, backend = admission(tmp_path)
    descriptor = candidate()["descriptor"]
    descriptor["operation"] = "get_authored_evidence"
    descriptor["recipe"] = {
        "seed_parameter": "component_ids",
        "steps": [{"edge_type": "USED_EVIDENCE", "direction": "outgoing"}],
    }
    with pytest.raises(KnowledgeError) as failure:
        asyncio.run(execute_query(backend, QueryDescriptor.model_validate(descriptor),
                                  "repo", backend.snapshot.generation_id,
                                  {"component_ids": ["missing"]}))
    assert failure.value.code == "unsupported"
    assert backend.statements == []


def test_backend_outage_cannot_activate_or_replace_catalog(tmp_path):
    # covers: KM-500a-3
    # covers: KM-500b-3
    # angle: failure
    catalog, port, backend = admission(tmp_path)
    receipt = asyncio.run(port.verify_and_activate(candidate(), repository_id="repo",
                                                   source_sha="a" * 40))
    before = (tmp_path / "catalog.json").read_bytes()
    changed = candidate()
    changed["descriptor"]["version"] = "2"

    async def unavailable(*args, **kwargs):
        raise BackendUnavailable()

    backend._run = unavailable
    with pytest.raises(BackendUnavailable):
        asyncio.run(port.verify_and_activate(changed, repository_id="repo",
            source_sha="a" * 40, expected_active_digest=receipt["digest"]))
    assert (tmp_path / "catalog.json").read_bytes() == before
    assert catalog.get("get_component_tests").version == "1"
