"""MODULE: synthetic_demo
GOAL: Reproduce registered-query and hybrid mechanics on real Neo4j.
BUSINESS CONTEXT: Synthetic evidence demonstrates mechanics, never semantic usefulness.
ARCHITECTURE: Explicit demonstration entry point; no production memory source is created.

DECISION HISTORY
========================================
- 2026-10-01 12:00 [python-coder]: Record real-server metrics with labeled deterministic fixtures. (#TICKET-KM-400c-5)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
from importlib.metadata import version
from uuid import uuid4

from knowledge.contracts import Entity, ProjectionSnapshot, Relation, SourceReference
from knowledge.adapters.neo4j_backend import Neo4jBackend
from knowledge.embedding_jobs import embed_snapshot
from knowledge.evaluation import evaluate
from knowledge.errors import NotReady
from knowledge.service import KnowledgeService


class FixtureEmbeddings:
    """Deterministic two-dimensional vectors, explicitly not a language model."""

    model = "synthetic-fixture-v1"
    dimensions = 2

    async def embed(self, texts):
        """Return fixed nonzero vectors to test storage and expansion mechanics."""
        return [[1.0, 0.0] for _ in texts]


def fixture(repository_id: str) -> ProjectionSnapshot:
    """Create the visibly synthetic, versioned demonstration source records.

    Args:
        repository_id: Trusted repository namespace that isolates all reads and writes.

    Returns:
        Validated source generation with immutable provenance.
    """
    specs = {
        "C": "Component",
        "AC": "AcceptanceCriterion",
        "T": "Test",
        "ADR": "ADR",
        "D-old": "Decision",
        "D-new": "Decision",
        "L": "Lesson",
        "E": "SourceFile",
    }
    sha = hashlib.sha1(b"leafcutter synthetic knowledge fixture v1").hexdigest()
    nodes = []
    for identifier, kind in specs.items():
        properties = {"synthetic": True}
        if kind == "Decision":
            properties.update(
                status="corrected" if identifier == "D-old" else "current",
                decision_type="architecture",
            )
        nodes.append(
            Entity(
                canonical_id=identifier,
                kind=kind,
                title=identifier,
                summary="Explicit synthetic fixture",
                source=SourceReference(
                    repository_id=repository_id,
                    source_sha=sha,
                    path="synthetic/" + identifier + ".txt",
                    content_hash=hashlib.sha256(identifier.encode()).hexdigest(),
                ),
                properties=properties,
            )
        )
    links = [
        ("AC", "C", "component_membership"),
        ("ADR", "C", "component_membership"),
        ("AC", "T", "covered_by"),
        ("D-old", "C", "ABOUT"),
        ("D-new", "C", "ABOUT"),
        ("D-old", "D-new", "CORRECTED_BY"),
        ("D-old", "L", "TAUGHT"),
        ("D-old", "E", "USED_EVIDENCE"),
    ]
    edges = [Relation(source_id=a, target_id=b, edge_type=kind) for a, b, kind in links]
    return ProjectionSnapshot(
        repository_id=repository_id,
        source_sha=sha,
        generation_id="synthetic-v1",
        nodes=nodes,
        edges=edges,
        supported_kinds=sorted(set(specs.values())),
        diagnostics=["synthetic_fixture:no_real_historical_memory"],
    )


def catalog_cases() -> list[tuple[str, dict, set[str]]]:
    """Define expected canonical identities for every implemented graph template.

    Returns:
        Operation names, bound arguments and expected canonical ID sets for the fixture.
    """
    return [
        ("get_entities", {"entity_ids": ["AC"]}, {"AC"}),
        ("get_component_context", {"component_id": "C"}, {"C", "AC", "ADR"}),
        ("get_acceptance_criteria", {"component_id": "C"}, {"AC"}),
        ("get_related_tests", {"entity_ids": ["AC"]}, {"T"}),
        ("get_relevant_adrs", {"component_id": "C"}, {"ADR"}),
        (
            "get_previous_decisions",
            {"component_id": "C", "status": "corrected", "decision_type": "architecture"},
            {"D-old"},
        ),
        ("get_corrected_decisions", {"entity_ids": ["D-old"]}, {"D-new"}),
        ("get_related_lessons", {"entity_ids": ["D-old"]}, {"L"}),
        ("get_decision_evidence", {"entity_ids": ["D-old"]}, {"E"}),
    ]


def evaluation_cases(repository_id: str) -> list[dict]:
    """Provide reviewed deterministic judgments with explicit synthetic attribution.

    Args:
        repository_id: Trusted repository namespace that isolates all reads and writes.

    Returns:
        Synthetic retrieval requests and their reviewed expected entity judgments.
    """
    cases = []
    selections = [
        catalog_cases()[0],
        catalog_cases()[3],
        catalog_cases()[4],
        catalog_cases()[6],
        ("get_entities", {"entity_ids": ["absent"]}, set()),
        ("find_similar_lessons", {"query_text": "lesson"}, {"L"}),
        ("find_similar_decisions", {"query_text": "precedent"}, {"D-old", "D-new", "L", "E"}),
    ]
    for index, (operation, arguments, expected) in enumerate(selections):
        mode = "exact" if operation == "get_entities" else "graph"
        if operation == "find_similar_lessons":
            mode = "semantic"
        if operation == "find_similar_decisions":
            mode = "hybrid"
        cases.append(
            {
                "id": str(index),
                "reviewed_by": "BA KM-400 deterministic acceptance judgments",
                "synthetic": True,
                "relevant_ids": sorted(expected),
                "correction_ids": ["D-new"] if mode == "hybrid" else [],
                "request": {
                    "repository_id": repository_id,
                    "request_id": "evaluation-" + str(index),
                    "operation": operation,
                    "arguments": arguments,
                    "mode": mode,
                    "disclosure_level": 1 if mode == "hybrid" else 0,
                },
            }
        )
    return cases


async def run_demo() -> dict:
    """Publish isolated synthetic evidence, check templates, and measure service results.

    Returns:
        Measured query checks, retrieval metrics and explicit synthetic-corpus attribution.
    """
    repository_id = "synthetic-demo-" + uuid4().hex
    db = Neo4jBackend(
        os.environ.get("LEAFCUTTER_NEO4J_URI", "bolt://127.0.0.1:17687"),
        os.environ.get("LEAFCUTTER_NEO4J_WRITER_USERNAME", "neo4j"),
        os.environ.get("LEAFCUTTER_NEO4J_WRITER_PASSWORD", "leafcutter-local-tests"),
    )
    try:
        await db.setup()
        snapshot = fixture(repository_id)
        await db.publish(snapshot)
        provider = FixtureEmbeddings()
        embedding = await embed_snapshot(db, snapshot, provider)
        catalog = []
        for operation, arguments, expected in catalog_cases():
            nodes = await db.query(repository_id, snapshot.generation_id, operation, arguments, 20)
            actual = {node.canonical_id for node in nodes}
            catalog.append(
                {
                    "operation": operation,
                    "expected": sorted(expected),
                    "actual": sorted(actual),
                    "passed": actual == expected,
                }
            )
        try:
            await db.query(
                repository_id,
                snapshot.generation_id,
                "get_related_policies",
                {"component_id": "C"},
                20,
            )
        except NotReady:
            unsupported_policy = True
        else:
            unsupported_policy = False
        results = await evaluate(
            KnowledgeService(db, embedding_provider=provider), evaluation_cases(repository_id)
        )
        versions = await db._run("CALL dbms.components() YIELD name,versions RETURN name,versions")
        return {
            "synthetic": True,
            "source_provenance_note": "synthetic source identities; no real-history or source-excerpt claim",
            "backend": versions,
            "driver_version": version("neo4j"),
            "python_version": platform.python_version(),
            "embedding": embedding,
            "node_count": len(snapshot.nodes),
            "edge_count": len(snapshot.edges),
            "catalog": catalog,
            "all_catalog_checks_passed": all(row["passed"] for row in catalog),
            "unsupported_policy": unsupported_policy,
            "evaluation": results,
            "real_model_evaluation": "not run: no production embedding model configured",
        }
    finally:
        await db.close()


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_demo()), indent=2))
