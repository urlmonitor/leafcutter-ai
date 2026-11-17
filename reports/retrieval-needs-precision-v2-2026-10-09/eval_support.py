"""Offline source-bound preparation for the isolated interpretation evaluation."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from kernel.capabilities.base import ExecutionContext
    from kernel.config import KernelConfig
    from kernel.contracts.retrieval_needs import RetrievalNeedsRequest
    from kernel.contracts.task import Scope

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "reports/retrieval-aura-2026-10-09"))
from proof_support import read, save as save, sha256, utc_now as utc_now, runtime_fingerprint


@dataclasses.dataclass
class PreparationContext:
    """Only pure catalogue-preparation inputs; contains no graph/model/read ports."""
    config: KernelConfig
    scope: Scope
    clarifications: list[str]
    entity_context: object = None
    context_enrichment: object = None


def cases():
    """Read the separately frozen evaluator-only manifest."""
    return read(BASE / "cases.json")["cases"]


def request_for(case: dict) -> tuple[RetrievalNeedsRequest, Scope]:
    """Use the actual repository interpreter to offer current production meanings.

    Args:
        case: Frozen question, literal candidate and optional original context.

    Returns:
        Production-prepared host request and its immutable source scope.
    """
    from integrations.research_needs import RepositoryNeedsInterpreter
    from kernel.capabilities.research.state import Plan
    from kernel.config import SourceConfig, load_kernel_config
    from kernel.contracts.task import Scope, RevisionInfo

    plan = read(BASE / "plan.json")
    config = load_kernel_config(default_path=ROOT / "config/kernel_config.default.json", env={})
    config = config.model_copy(update={
        "knowledge": config.knowledge.model_copy(update={"repository_id": "leafcutter"}),
        "sources": [SourceConfig(id="knowledge.graph", kind="graph_query", categories=["task_context"])],
    })
    scope = Scope(workspace_id="needs-precision-proof", repository_root=str(ROOT),
        revision=RevisionInfo(commit=plan["stage2"]["source_sha"]),
        read_roots=["docs"], source_ids=["knowledge.graph"])
    context = PreparationContext(config, scope, case["context"])
    research = Plan(question=case["question"], expected_coverage="", mandated=[], source_restrictions=[])
    request = RepositoryNeedsInterpreter().prepare(cast("ExecutionContext", context), research)
    assert request is not None
    assert request.original_question == case["question"] and request.context == case["context"]
    assert list(request.catalog["target_ids"]) == [case["target"]]
    return request, scope


def fingerprint():
    """Pin runtime bytes and new evaluator code independently of the source revision."""
    value = runtime_fingerprint()
    value["files_sha256"].update({path.relative_to(ROOT).as_posix(): sha256(path)
                                for path in BASE.glob("*.py")})
    value["aggregate_sha256"] = hashlib.sha256(
        json.dumps(value["files_sha256"], sort_keys=True).encode()).hexdigest()
    return value


def verify_plan():
    """Refuse changed gold or baseline closure before any fresh packet or submission."""
    plan = read(BASE / "plan.json")
    assert sha256(BASE / "cases.json") == plan["case_manifest_sha256"]
    assert sha256(BASE / "source-oracles.json") == plan["source_oracles_sha256"]
    baseline = ROOT / plan["baseline_preservation"]["path"]
    assert sha256(baseline / "closure-integrity.json") == plan["baseline_preservation"]["closure_integrity_sha256"]
    prior = plan["prior_stage1_preservation"]
    assert sha256(ROOT / prior["path"] / "closure-integrity.json") == prior["closure_integrity_sha256"]
    assert sha256(ROOT / prior["cases_path"]) == prior["cases_sha256"]
    assert sha256(BASE / "original-cases.json") == prior["cases_sha256"]
    assert cases()[:12] == read(BASE / "original-cases.json")["cases"]
    assert sha256(BASE / "holdouts.json") == plan["holdouts_sha256"]
    assert cases()[12:] == read(BASE / "holdouts.json")["cases"]
    assert sha256(ROOT / plan["maintained_helpers"]["receipt"]) == plan["maintained_helpers"]["sha256"]
    assert len(cases()) == 16


def verify_freeze(output: Path) -> None:
    """Refuse modified code, expectations or requests after dispatch.

    Args:
        output: Batch directory containing the pre-dispatch fingerprint.
    """
    verify_plan()
    freeze = read(output / "freeze.json")
    assert freeze["runtime"] == fingerprint(), "Runtime/evaluator code changed after freeze"
    assert freeze["plan_sha256"] == sha256(BASE / "plan.json")
    for name, expected in freeze["requests_sha256"].items():
        assert sha256(output / name / "request.json") == expected


def isolated_service(directory):
    """Compose the established zero-Jev, no-source-port real host/ledger experiment."""
    from integrations.retrieval_needs_llm import make_experiment_service
    return make_experiment_service(ROOT, directory / "runtime")
