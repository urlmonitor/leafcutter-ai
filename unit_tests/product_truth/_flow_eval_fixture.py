"""Real product-truth scripts and reviewed model sources in a bounded eval fixture."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from unit_tests.product_truth._flow_io_fixture import ROOT, make_store, assert_success, write_json

FLOW_REL = "flows/fixture/query.flow.json"
RECEIPT_REL = "reports/contract-eval/receipt.json"
GAP_REL = "docs/analysis/contract-eval-proposal.md"


def make_eval_source(root: Path, *, runtime: bool = False) -> Path:
    """Use the real serializer, generator and schema; never a validation double."""
    store = make_store(root)
    flow_path = store / FLOW_REL
    flow = json.loads(flow_path.read_text(encoding="utf-8"))
    io = flow["steps"][0]["io_contracts"]
    if runtime:
        for package in ("kernel", "knowledge"):
            for source in (ROOT / package).rglob("*.py"):
                if "__pycache__" in source.parts:
                    continue
                destination = root / source.relative_to(ROOT)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        for relative in ("integrations/__init__.py", "integrations/knowledge_config.py"):
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        flow["contract_definitions"]["request"] = {"model": "scope"}
        # A second declared schema proves closure is driven by declarations,
        # not just the first model-bound contract.
        flow["contract_definitions"]["reference"] = {"schema": "config/request.schema.json"}
        io["consumes"][0]["fields"] = [
            {"path": "/workspace_id", "types": ["string"], "required": True},
            {"path": "/repository_root", "types": ["string"], "required": True},
            {"path": "/read_roots", "types": ["array"], "required": False, "default": []},
        ]
        io["examples"][0]["value"] = {"workspace_id": "eval-fixture", "repository_root": str(root.resolve()), "read_roots": []}
    example = io["examples"][0]
    example.update(origin="observed", source={"path": RECEIPT_REL, "pointer": "/request"})
    write_json(root / RECEIPT_REL, {"request": example["value"]})
    gap = root / GAP_REL
    gap.parent.mkdir(parents=True, exist_ok=True)
    gap.write_text("Proposed extra context has no agreed payload yet.\n", encoding="utf-8")
    io["missing_bindings"] = [{"name": "extra_context", "direction": "produces", "reason": "The extra context payload is not designed.", "source": GAP_REL}]
    write_json(flow_path, flow)
    for relative in (".env", "config/unrelated-private.json", "reports/unrelated-private.json", "kernel/.env", "knowledge/cache/private.txt"):
        sentinel = root / relative
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text("fixture-private-sentinel", encoding="utf-8")
    return store


def regenerate(ev, root: Path) -> None:
    """Require a completed actual generator run, not just a tolerated failure."""
    result = ev._run_pt_script(root, ev._GENERATE_REL, ["--quiet"], 30)
    assert_success(result)


def target_score(ev, sandbox: Path, new_errors: set[str], flow_relative: str = FLOW_REL):
    store = ev._store_dir(sandbox)
    schema = json.loads((store / "schemas/flow.schema.json").read_text(encoding="utf-8"))
    target = {"target_rel": flow_relative, "matching_added": [], "matching_modified": [flow_relative]}
    context = ev.build_artifact_context(store, "flow", schema, target, new_errors)
    return ev.score_artifact_context(context, {"assertions": [{"kind": "schema_valid"}, {"kind": "validator_clean"}]}, "unused", 10, "unused")
