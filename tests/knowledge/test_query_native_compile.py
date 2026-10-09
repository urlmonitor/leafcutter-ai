"""Native compiler behavior and fresh-admission-only saved catalog contracts."""

import asyncio
import copy
import json

import pytest

from knowledge.adapters.domain_schema import NODE_LABELS, RELATIONSHIPS
from knowledge.native_types.registry import LABELS
from knowledge.query_compile import compile_query, digest_data
from knowledge.query_models import KINDS, QueryDescriptor
from knowledge.query_store import read_catalog
from knowledge.service import KnowledgeService
from tests.knowledge.test_query_admission import admission, candidate


def request_payload(digest=None):
    """Use the same query scope while selecting a retained native admission."""
    payload = {
        "repository_id": "repo",
        "request_id": "native-query-catalog",
        "operation": "get_component_tests",
        "mode": "graph",
        "arguments": {"component_ids": ["component"]},
        "revision": "a" * 40,
    }
    if digest:
        payload["operation_digest"] = digest
    return payload


def test_native_compiler_uses_exact_labels_relationships_and_bounds():
    # covers: KM-400a-3-i
    # covers: KM-500b-2
    descriptor = QueryDescriptor.model_validate(candidate()["descriptor"])
    compiled = compile_query(descriptor)
    statement = compiled["cypher"]
    assert compiled["compiler_version"] == "2"
    assert "(n0:Component {generation_key:$scope_key,canonical_id:seed_id})" in statement
    assert "(n0)<-[r0:COMPONENT_MEMBERSHIP]-(n1:AC {generation_key:$scope_key})" in statement
    assert "(n1)-[r1:COVERED_BY]->(n2:Test {generation_key:$scope_key})" in statement
    assert "KR" not in statement
    assert "n0.kind=$seed_kind" in statement and "n1.kind=$step_0_kind" in statement
    assert statement.count("generation_key=$scope_key") == 2
    assert statement.count("LIMIT $probe_fanout") == 2
    assert "LIMIT $seed_limit" in statement and "found[..$result_limit]" in statement
    assert "size(hits0)>$fanout" in statement and "hits1[..$fanout]" in statement
    assert "clipped0 OR clipped1" in statement
    assert compiled["constants"]["step_0_edge"] == "component_membership"


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_each_constrained_kind_uses_its_trusted_native_label(kind):
    # covers: KM-400a-3-i
    authored = candidate()["descriptor"]
    authored["recipe"].update(seed_kind=kind, steps=[])
    statement = compile_query(QueryDescriptor.model_validate(authored))["cypher"]
    assert f"(n0:{LABELS[kind]} {{generation_key:$scope_key" in statement


@pytest.mark.parametrize("edge", sorted(RELATIONSHIPS))
@pytest.mark.parametrize("direction", ["incoming", "outgoing"])
def test_generic_endpoints_keep_native_union_and_declared_direction(edge, direction):
    # covers: KM-400a-3-i
    authored = candidate()["descriptor"]
    authored["recipe"].update(
        seed_kind=None, steps=[{"edge_type": edge, "direction": direction}]
    )
    statement = compile_query(QueryDescriptor.model_validate(authored))["cypher"]
    assert f"(n0:{NODE_LABELS} {{" in statement
    assert f"(n1:{NODE_LABELS} {{" in statement
    arrow = (
        f"<-[r0:{RELATIONSHIPS[edge]}]-"
        if direction == "incoming"
        else f"-[r0:{RELATIONSHIPS[edge]}]->"
    )
    assert arrow in statement and "KR_LINK" not in statement


def test_filter_values_stay_bound_and_execution_clamps_limits(tmp_path):
    # covers: KM-400a-3-i
    # covers: KM-500b-2
    from knowledge.query_execution import execute_query

    _, _, db = admission(tmp_path)
    authored = candidate()["descriptor"]
    authored["parameters"]["status"] = {"type": "string", "required": False}
    authored["recipe"]["filters"] = {"status": "status"}
    authored["recipe"]["steps"][0]["filters"] = {"status": "status"}
    descriptor = QueryDescriptor.model_validate(authored)
    poison = "done' MATCH (n) DELETE n //"
    asyncio.run(execute_query(db, descriptor, "repo", db.snapshot.generation_id,
                             {"component_ids": ["component"], "status": poison},
                             limit=999, fanout=999))
    statement, params, write = db.statements[-1]
    assert not write and poison not in statement
    assert params["arg_status"] == poison
    assert "($arg_status IS NULL OR n0.status=$arg_status)" in statement
    assert "($arg_status IS NULL OR n1.status=$arg_status)" in statement
    assert params["result_limit"] == 200 and params["fanout"] == 10
    assert params["probe_fanout"] == 11 and params["seed_limit"] == 20


def test_registry_growth_cannot_change_existing_v2_query_digests(monkeypatch):
    # covers: KM-400a-3-i
    # covers: KM-500b-3
    import importlib
    from knowledge import query_compile
    from knowledge.adapters import domain_schema
    from knowledge.native_types import registry

    authored = candidate()["descriptor"]
    authored["recipe"].update(seed_kind=None, steps=[
        {"edge_type": "component_membership", "direction": "incoming"}
    ])
    descriptor = QueryDescriptor.model_validate(authored)
    before = query_compile.compile_query(descriptor)
    monkeypatch.setitem(registry.LABELS, "FutureKind", "FutureKind")
    monkeypatch.setattr(domain_schema, "NODE_LABELS", domain_schema.NODE_LABELS + "|FutureKind")
    monkeypatch.setitem(domain_schema.RELATIONSHIPS, "future_edge", "FUTURE_EDGE")
    assert importlib.reload(query_compile).compile_query(descriptor) == before


@pytest.mark.parametrize("extension", ["kind", "relationship"])
def test_future_model_vocabulary_requires_deliberate_compiler_version(monkeypatch, extension):
    # covers: KM-400a-3-i
    from knowledge import query_models

    authored = candidate()["descriptor"]
    if extension == "kind":
        monkeypatch.setattr(query_models, "KINDS", query_models.KINDS | {"FutureKind"})
        authored["recipe"]["seed_kind"] = "FutureKind"
    else:
        monkeypatch.setattr(query_models, "EDGES", query_models.EDGES | {"future_edge"})
        authored["recipe"]["steps"][0]["edge_type"] = "future_edge"
    descriptor = QueryDescriptor.model_validate(authored)
    with pytest.raises(ValueError, match="requires a newer compiler version"):
        compile_query(descriptor)


def test_current_catalog_descriptor_digest_matches_recorded_admission(tmp_path):
    # covers: KM-400a-3-i
    # covers: KM-500b-3
    catalog, port, _ = admission(tmp_path)
    receipt = asyncio.run(port.verify_and_activate(
        candidate(), repository_id="repo", source_sha="a" * 40
    ))
    descriptor = catalog.get("get_component_tests")
    assert descriptor.digest == receipt["digest"] == compile_query(descriptor)["digest"]


def saved_catalog(tmp_path):
    """Build current and retained versions through real fresh admission checks."""
    catalog, port, db = admission(tmp_path)
    first = asyncio.run(port.verify_and_activate(
        candidate(), repository_id="repo", source_sha="a" * 40
    ))
    proposed = candidate()
    proposed["descriptor"]["version"] = "2"
    active = asyncio.run(port.verify_and_activate(
        proposed, repository_id="repo", source_sha="a" * 40,
        expected_active_digest=first["digest"]
    ))
    return catalog, port, db, first["digest"], active["digest"]


@pytest.mark.parametrize("retained", [True, False])
def test_native_catalog_preserves_active_and_retained_pins(tmp_path, retained):
    # covers: KM-400a-3-i
    # covers: KM-500b-3
    catalog, _, db, first, active = saved_catalog(tmp_path)
    target = tmp_path / "catalog.json"
    before = target.read_bytes()
    request = catalog.request(request_payload(first if retained else None))
    expected = first if retained else active
    assert request.operation_digest == expected
    descriptor = catalog.get(request.operation, request.operation_version, expected)
    assert descriptor.digest == expected == compile_query(descriptor)["digest"]
    result = asyncio.run(KnowledgeService(db, query_catalog=catalog).retrieve(request))
    assert [item.entity.canonical_id for item in result.evidence] == ["test"]
    assert result.stats["operation_digest"] == expected
    assert target.read_bytes() == before
    assert all("KR" not in statement for statement, _, _ in db.statements)


@pytest.mark.parametrize("compiler", ["1", "unsupported", None])
def test_unsupported_catalog_compiler_requires_readmission(tmp_path, compiler):
    # covers: KM-400a-3-i
    # covers: KM-500b-3
    catalog, _, db, first, _ = saved_catalog(tmp_path)
    target = tmp_path / "catalog.json"
    data = json.loads(target.read_text())
    data["entries"][first]["compiled"]["compiler_version"] = compiler
    target.write_text(json.dumps(data))
    before, calls = target.read_bytes(), len(db.statements)
    with pytest.raises(ValueError, match="compiler requires re-admission"):
        catalog.request(request_payload(first))
    assert target.read_bytes() == before and len(db.statements) == calls


@pytest.mark.parametrize("compiler", ["1", "unsupported", None])
def test_stale_or_missing_verification_cannot_be_reused(tmp_path, compiler):
    # covers: KM-400a-3-i
    # covers: KM-500b-3
    catalog, _, db, first, _ = saved_catalog(tmp_path)
    target = tmp_path / "catalog.json"
    data = json.loads(target.read_text())
    entry = data["entries"][first]
    entry["verification"]["checks"]["compiler_version"] = compiler
    entry["verification_digest"] = digest_data(entry["verification"])
    target.write_text(json.dumps(data))
    before, calls = target.read_bytes(), len(db.statements)
    with pytest.raises(ValueError, match="fresh.*admission"):
        catalog.request(request_payload(first))
    assert target.read_bytes() == before and len(db.statements) == calls


@pytest.mark.parametrize("mutation", ["cypher", "proof", "proof_digest"])
def test_native_catalog_tampering_fails_without_rewriting(tmp_path, mutation):
    # covers: KM-400a-3-i
    # covers: KM-500b-3
    catalog, _, db, first, _ = saved_catalog(tmp_path)
    target = tmp_path / "catalog.json"
    data = json.loads(target.read_text())
    entry = data["entries"][first]
    if mutation == "cypher":
        entry["compiled"]["cypher"] += " RETURN 1"
    elif mutation == "proof":
        entry["verification"]["source_sha"] = "b" * 40
    else:
        entry["verification_digest"] = "f" * 64
    target.write_text(json.dumps(data))
    before, calls = target.read_bytes(), len(db.statements)
    with pytest.raises(ValueError, match="integrity"):
        catalog.request(request_payload(first))
    assert target.read_bytes() == before and len(db.statements) == calls


def test_new_native_admission_retains_versions_and_rejects_stale_activation(tmp_path):
    # covers: KM-400a-3-i
    # covers: KM-500b-3
    catalog, port, _, _, active = saved_catalog(tmp_path)
    before = copy.deepcopy(read_catalog(tmp_path))
    proposed = candidate()
    proposed["descriptor"]["version"] = "3"
    receipt = asyncio.run(port.verify_and_activate(
        proposed, repository_id="repo", source_sha="a" * 40, expected_active_digest=active
    ))
    assert receipt["checks"]["compiler_version"] == "2"
    assert receipt["checks"]["declared_cases_passed"] == 2
    after = read_catalog(tmp_path)
    for digest, entry in before["entries"].items():
        assert after["entries"][digest] == entry
        assert catalog.request(request_payload(digest)).operation_digest == digest
    assert catalog.request(request_payload()).operation_digest == receipt["digest"]
    proposed["descriptor"]["version"] = "4"
    with pytest.raises(ValueError, match="activation conflict"):
        asyncio.run(port.verify_and_activate(
            proposed, repository_id="repo", source_sha="a" * 40, expected_active_digest=active
        ))
    assert read_catalog(tmp_path) == after


def test_native_catalog_descriptor_roundtrips_and_edited_copies_rehash(tmp_path):
    # covers: KM-400a-3-i
    # covers: KM-500b-3
    catalog, _, _, first, _ = saved_catalog(tmp_path)
    descriptor = catalog.get("get_component_tests", digest=first)
    authored = descriptor.model_dump()
    assert authored == read_catalog(tmp_path)["entries"][first]["descriptor"]
    assert QueryDescriptor.model_validate(authored).digest == descriptor.digest == first
    changed = descriptor.model_copy(update={"version": "3"})
    assert changed.digest != first
    assert changed.digest == compile_query(changed)["digest"]
    descriptor.description += " (edited after lookup)"
    assert descriptor.digest != first
    assert descriptor.digest == compile_query(descriptor)["digest"]


def test_missing_pinned_digest_never_falls_back_to_active_query(tmp_path):
    # covers: KM-400a-3-i
    # covers: KM-500b-3
    catalog, _, db, _, active = saved_catalog(tmp_path)
    before = len(db.statements)
    with pytest.raises(ValueError, match="unknown registered catalog operation or digest"):
        catalog.request(request_payload("0" * 64))
    assert len(db.statements) == before
    assert catalog.request(request_payload()).operation_digest == active
