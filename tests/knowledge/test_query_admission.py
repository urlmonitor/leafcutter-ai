"""Public catalog admission checks; database double is not a Cypher correctness claim."""

import asyncio
import copy
import importlib
import json

import pytest

from tests.knowledge.test_core import Backend, entity


def candidate():
    return {
        "descriptor": {
            "operation": "get_component_tests",
            "version": "1",
            "description": "Tests covering acceptance criteria for the selected components",
            "questions": ["Which tests verify this component's requirements?"],
            "parameters": {"component_ids": {"type": "string_list", "required": True}},
            "recipe": {
                "seed_parameter": "component_ids",
                "seed_kind": "Component",
                "steps": [
                    {
                        "edge_type": "component_membership",
                        "direction": "incoming",
                        "kind": "AcceptanceCriterion",
                    },
                    {"edge_type": "covered_by", "direction": "outgoing", "kind": "Test"},
                ],
            },
        },
        "reviewer": "declared-fixture-author",
        "cases": [
            {
                "name": "known component",
                "arguments": {"component_ids": ["component"]},
                "expected_ids": ["test"],
            },
            {
                "name": "absent component",
                "arguments": {"component_ids": ["missing"]},
                "expected_ids": [],
            },
        ],
    }


class Database(Backend):
    def __init__(self):
        contracts = importlib.import_module("knowledge.contracts")
        super().__init__(contracts, [entity(contracts, "test", "Test")])
        self.statements = []
        self.snapshot.supported_kinds = ["Component", "AcceptanceCriterion", "Test"]

    async def get_revision(self, repo, sha):
        return self.snapshot if repo == "repo" and sha == "a" * 40 else None

    async def _run(self, statement, parameters=None, write=False):
        self.statements.append((statement, parameters, write))
        ids = parameters.get("arg_component_ids", [])
        return [{"payload": self.nodes[0].model_dump_json()}] if ids == ["component"] else []


def admission(tmp_path):
    catalog = importlib.import_module("knowledge.query_catalog").QueryCatalog(tmp_path)
    db = Database()
    port = importlib.import_module("knowledge.query_admission").QueryAdmission(catalog, db, "repo")
    return catalog, port, db


def test_catalog_compiles_novel_two_hop_query_with_bound_values(tmp_path):
    # covers: KM-500b-2
    # angle: criterion
    catalog, port, db = admission(tmp_path)
    receipt = asyncio.run(
        port.verify_and_activate(candidate(), repository_id="repo", source_sha="a" * 40)
    )
    assert receipt["status"] == "activated"
    descriptor = catalog.get("get_component_tests", digest=receipt["digest"])
    assert descriptor.recipe.steps[1].edge_type == "covered_by"
    assert db.statements and all(not call[2] for call in db.statements)
    cypher = db.statements[0][0]
    assert cypher.count("CALL {") == 2 and "generation_key:$scope_key" in cypher
    assert "component_membership" not in cypher and "covered_by" not in cypher
    assert receipt["checks"]["semantic_usefulness_proven"] is False
    assert receipt["checks"]["declared_cases_passed"] == 2


def test_catalog_reopens_and_public_service_consumes_pinned_digest(tmp_path):
    # covers: KM-500b-3
    # angle: criterion
    # angle: reachability
    catalog, port, db = admission(tmp_path)
    receipt = asyncio.run(
        port.verify_and_activate(candidate(), repository_id="repo", source_sha="a" * 40)
    )
    reopened = type(catalog)(tmp_path)
    selected = [d for d in reopened.descriptors() if d["operation"] == "get_component_tests"][0]
    assert selected["digest"] == receipt["digest"] and selected["questions"]
    request = reopened.request(
        {
            "repository_id": "repo",
            "request_id": "new-run",
            "operation": "get_component_tests",
            "mode": "graph",
            "arguments": {"component_ids": ["component"]},
            "revision": "a" * 40,
        }
    )
    service = importlib.import_module("knowledge.service").KnowledgeService(
        db, query_catalog=reopened
    )
    result = asyncio.run(service.retrieve(request))
    assert result.status == "partial" and result.truncated
    assert result.evidence[0].entity.canonical_id == "test"
    assert result.stats["operation_digest"] == receipt["digest"]


def test_false_expectations_never_activate_and_previous_catalog_survives(tmp_path):
    # covers: KM-500b-2
    # covers: KM-500b-3
    # angle: criterion
    catalog, port, _ = admission(tmp_path)
    good = asyncio.run(
        port.verify_and_activate(candidate(), repository_id="repo", source_sha="a" * 40)
    )
    altered = candidate()
    altered["descriptor"]["version"] = "2"
    altered["cases"][0]["expected_ids"] = ["invented"]
    with pytest.raises(ValueError, match="expectation"):
        asyncio.run(port.verify_and_activate(altered, repository_id="repo", source_sha="a" * 40))
    assert catalog.get("get_component_tests").version == "1"
    assert catalog.descriptors()[-1]["digest"] == good["digest"]


@pytest.mark.parametrize("mutation", ["cypher", "edge", "parameter", "depth", "empty_cases"])
def test_unsafe_or_unverified_candidate_is_rejected_before_database_work(tmp_path, mutation):
    # covers: KM-500b-2
    # angle: criterion
    catalog, port, db = admission(tmp_path)
    proposed = candidate()
    if mutation == "cypher":
        proposed["cypher"] = "MATCH (n) DELETE n"
    elif mutation == "edge":
        proposed["descriptor"]["recipe"]["steps"][0]["edge_type"] = "unknown"
    elif mutation == "parameter":
        proposed["descriptor"]["parameters"]["repo"] = {"type": "string"}
    elif mutation == "depth":
        proposed["descriptor"]["recipe"]["steps"] *= 2
    else:
        proposed["cases"] = []
    with pytest.raises(ValueError):
        asyncio.run(port.verify_and_activate(proposed, repository_id="repo", source_sha="a" * 40))
    assert not db.statements
    assert all(d["operation"] != "get_component_tests" for d in catalog.descriptors())


def test_persisted_descriptor_or_verification_tampering_fails_closed(tmp_path):
    # covers: KM-500b-3
    # angle: criterion
    catalog, port, _ = admission(tmp_path)
    asyncio.run(port.verify_and_activate(candidate(), repository_id="repo", source_sha="a" * 40))
    target = tmp_path / "catalog.json"
    saved = json.loads(target.read_text())
    modified = copy.deepcopy(saved)
    entry = next(iter(modified["entries"].values()))
    entry["verification"]["source_sha"] = "b" * 40
    target.write_text(json.dumps(modified))
    with pytest.raises(ValueError, match="integrity"):
        type(catalog)(tmp_path).descriptors()


def test_unknown_operation_still_rejected_without_trusted_catalog_context():
    # covers: KM-500a-2
    # angle: criterion
    contracts = importlib.import_module("knowledge.contracts")
    with pytest.raises(ValueError):
        contracts.KnowledgeRetrievalRequest(
            repository_id="repo",
            request_id="r",
            operation="get_component_tests",
            mode="graph",
            arguments={"component_ids": ["component"]},
        )


def test_same_query_reverified_on_new_source_returns_fresh_receipt(tmp_path):
    # covers: KM-500b-3
    # angle: criterion
    catalog, port, db = admission(tmp_path)
    first = asyncio.run(
        port.verify_and_activate(candidate(), repository_id="repo", source_sha="a" * 40)
    )
    db.snapshot.source_sha = "b" * 40
    db.nodes[0].source.source_sha = "b" * 40

    async def revision(repo, sha):
        return db.snapshot if repo == "repo" and sha == "b" * 40 else None

    db.get_revision = revision
    second = asyncio.run(
        port.verify_and_activate(candidate(), repository_id="repo", source_sha="b" * 40)
    )
    assert second["digest"] == first["digest"]
    assert second["source_sha"] == "b" * 40
    assert second["verification_digest"] != first["verification_digest"]


@pytest.mark.parametrize(
    "data",
    [
        {"entries": [], "active": {}},
        {"entries": {"x": {}}, "active": {}},
        {"entries": {}, "active": []},
    ],
)
def test_malformed_catalog_is_typed_integrity_error(tmp_path, data):
    # covers: KM-500b-3
    # angle: criterion
    catalog = importlib.import_module("knowledge.query_catalog").QueryCatalog(tmp_path)
    (tmp_path / "catalog.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="integrity"):
        catalog.descriptors()


def test_cli_catalog_restart_discovery_and_write_denial(tmp_path):
    # covers: KM-500b-3
    # angle: reachability
    import subprocess
    import sys

    catalog, port, _ = admission(tmp_path)
    receipt = asyncio.run(
        port.verify_and_activate(candidate(), repository_id="repo", source_sha="a" * 40)
    )
    found = subprocess.run(
        [sys.executable, "-m", "knowledge", "catalog-list", "--catalog-root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert any(row["digest"] == receipt["digest"] for row in json.loads(found.stdout)["queries"])
    denied = subprocess.run(
        [
            sys.executable,
            "-m",
            "knowledge",
            "query-register",
            "--catalog-root",
            str(tmp_path),
            "--repository-id",
            "repo",
            "--source-sha",
            "a" * 40,
            "--candidate",
            "not-read.json",
        ],
        capture_output=True,
        text=True,
    )
    assert denied.returncode == 2 and "allow-catalog-write" in denied.stderr


def test_retained_digest_and_failed_atomic_publication_keep_previous_entry(tmp_path, monkeypatch):
    # covers: KM-500b-3
    # angle: criterion
    catalog, port, _ = admission(tmp_path)
    first = asyncio.run(
        port.verify_and_activate(candidate(), repository_id="repo", source_sha="a" * 40)
    )
    revised = candidate()
    revised["descriptor"]["version"] = "2"
    revised["descriptor"]["description"] += " (revised description)"
    import knowledge.query_store as storage

    original = storage.os.replace

    def fail_replace(source, destination):
        raise OSError("simulated interrupted atomic publication")

    monkeypatch.setattr(storage.os, "replace", fail_replace)
    with pytest.raises(ValueError, match="prior snapshot retained"):
        asyncio.run(
            port.verify_and_activate(
                revised,
                repository_id="repo",
                source_sha="a" * 40,
                expected_active_digest=first["digest"],
            )
        )
    assert catalog.get("get_component_tests").version == "1"
    monkeypatch.setattr(storage.os, "replace", original)
    second = asyncio.run(
        port.verify_and_activate(
            revised,
            repository_id="repo",
            source_sha="a" * 40,
            expected_active_digest=first["digest"],
        )
    )
    assert catalog.get("get_component_tests").version == "2"
    assert catalog.get("get_component_tests", digest=first["digest"]).version == "1"
    assert second["digest"] != first["digest"]
    conflict = candidate()
    conflict["descriptor"]["version"] = "3"
    with pytest.raises(ValueError, match="conflict"):
        asyncio.run(
            port.verify_and_activate(
                conflict,
                repository_id="repo",
                source_sha="a" * 40,
                expected_active_digest=first["digest"],
            )
        )
    assert catalog.get("get_component_tests").version == "2"


def test_verification_timeout_and_cancellation_never_activate(tmp_path):
    # covers: KM-500b-2
    # angle: criterion
    catalog, port, db = admission(tmp_path)

    async def timeout(statement, parameters=None, write=False):
        raise TimeoutError

    db._run = timeout
    with pytest.raises(Exception, match="verification deadline") as failure:
        asyncio.run(
            port.verify_and_activate(candidate(), repository_id="repo", source_sha="a" * 40)
        )
    assert failure.value.code == "unavailable"

    async def scenario():
        started = asyncio.Event()

        async def slow(statement, parameters=None, write=False):
            started.set()
            await asyncio.Event().wait()

        db._run = slow
        task = asyncio.create_task(
            port.verify_and_activate(candidate(), repository_id="repo", source_sha="a" * 40)
        )
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert all(row["operation"] != "get_component_tests" for row in catalog.descriptors())


def test_catalog_query_without_compiled_backend_reports_unsupported(tmp_path):
    catalog, port, _ = admission(tmp_path)
    asyncio.run(port.verify_and_activate(candidate(), repository_id="repo", source_sha="a" * 40))
    contracts = importlib.import_module("knowledge.contracts")
    service = importlib.import_module("knowledge.service").KnowledgeService(
        Backend(contracts), query_catalog=catalog
    )
    request = catalog.request(
        {
            "request_id": "unsupported-catalog-backend",
            "repository_id": "repo",
            "operation": "get_component_tests",
            "mode": "graph",
            "arguments": {"component_ids": ["component"]},
        }
    )
    result = asyncio.run(service.retrieve(request))
    assert result.status == "unsupported"
    assert result.evidence == []
    assert result.errors[0]["code"] == "unsupported"
