"""Public synthetic evaluation exercises every advertised Neo4j query recipe."""

import asyncio
import importlib


def test_all_registered_templates_and_measured_synthetic_evaluation():
    # angle: reachability
    # covers: KM-400a-3
    # covers: KM-400c-1
    # covers: KM-400c-5
    # angle: criterion
    demo = importlib.import_module("knowledge.examples.synthetic_demo")
    report = asyncio.run(demo.run_demo())
    assert report["synthetic"] is True
    assert report["all_catalog_checks_passed"] is True
    assert len(report["catalog"]) == 9
    assert len(report["evaluation"]["cases"]) >= 5
    assert all(
        case["precision_at_k"] == 1 and case["recall_at_k"] == 1
        for case in report["evaluation"]["cases"]
    )
    assert report["evaluation"]["semantic_usefulness_proven"] is False
