"""
MODULE: _uxp_700c_2_fixtures
GOAL: Pure fixture builders shared by test_uxp_700c_2.py's freshness-check
    test classes -- extracted so that file stays inside the 400-content-line
    file-size ratchet (check-file-size).
BUSINESS CONTEXT: No test logic or assertions live here -- only flow/AC-record
    construction helpers, so this module carries zero coverage of its own and
    is not itself a test module (leading underscore keeps pytest from
    collecting it).
ARCHITECTURE: Imported by unit_tests/product_truth/test_uxp_700c_2.py. Mirrors
    unit_tests/product_truth/test_uxp_700c_1.py's own _base_flow / _write_flow
    convention for the same product-truth store shape.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PT_SRC = _REPO_ROOT / "docs" / "product-truth"


def step(step_id: str, implements: list, order: int) -> dict:
    """One flow step fixture, `implements` naming the AC ids it cites."""
    return {
        "id": step_id,
        "label": step_id,
        "human": f"the actor performs {step_id}",
        "order": order,
        "implements": implements,
    }


def base_flow(flow_id: str, steps: list, confirmed: dict | None = None) -> dict:
    """A minimal, schema-shaped flow fixture; `confirmed` is attached only
    when the caller supplies one (never-confirmed journeys omit the key)."""
    component = flow_id.split("/", 1)[0]
    flow = {
        "id": flow_id,
        "component": component,
        "name": flow_id,
        "summary": "fixture flow for UXP-700c-2 freshness tests",
        "kind": "user",
        "source": "mock",
        "status": "active",
        "readiness": "draft",
        "version": 1,
        "entities": [],
        "steps": steps,
        "branches": [],
    }
    if confirmed is not None:
        flow["confirmed"] = confirmed
    return flow


def write_flow(flows_dir: Path, flow: dict) -> Path:
    """Serialise `flow` under flows_dir/<component>/<name>.flow.json."""
    component_dir = flows_dir / flow["component"]
    component_dir.mkdir(parents=True, exist_ok=True)
    name = flow["id"].split("/", 1)[1]
    path = component_dir / f"{name}.flow.json"
    path.write_text(json.dumps(flow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def ac_record(work_status: str = "todo", product_truth=None, implemented_by=None, covered_by=None) -> dict:
    """A hand-built ac_records[ac_id] entry, matching load_ac_records()'s own
    shape ({path, work_status, product_truth, implemented_by, covered_by}) --
    minus `path`, which every direct-call test omits since
    _ac_content_signature is documented to exclude it."""
    return {
        "work_status": work_status,
        "product_truth": product_truth,
        "implemented_by": implemented_by,
        "covered_by": covered_by,
    }


def build_freshness_cli_store(tmp: Path, ac_work_status: str, confirmed_signature: str) -> Path:
    """Build a complete, schema-valid (once `confirmed` is registered),
    self-consistent product-truth store inside tmp -- real scripts + real
    schemas copied verbatim, one small flow authored with a `confirmed`
    record naming AC-REAL-1's `confirmed_signature`, and a derived
    index.json that already agrees with a fresh rebuild (so ONLY the new
    freshness check is exercised by the CLI run, mirroring
    test_uxp_700c_1.py's own _build_minimal_cli_store convention).
    Returns the path to the copied validate_product_truth.py CLI entry
    point."""
    import shutil

    pt_root = tmp / "docs" / "product-truth"
    shutil.copytree(_PT_SRC / "scripts", pt_root / "scripts")
    shutil.copytree(_PT_SRC / "schemas", pt_root / "schemas")
    (pt_root / "flows").mkdir(parents=True)
    (pt_root / "mock-data").mkdir(parents=True)
    (pt_root / "mockups").mkdir(parents=True)
    classifier_dir = pt_root / "classifier"
    classifier_dir.mkdir(parents=True)
    (classifier_dir / "eval.jsonl").write_text("", encoding="utf-8")

    ac_dir = tmp / "docs" / "acceptance-criteria" / "fixture-product"
    ac_dir.mkdir(parents=True)
    ac_record_data = {
        "id": "AC-REAL-1",
        "work_status": ac_work_status,
        "product_truth": [
            {
                "flow": "fixture-product/cli-journey",
                "node": "browse",
                "node_kind": "step",
                "flow_kind": "user",
                "screen": None,
                "mock_data": None,
                "entities": [],
                "source": "mock",
                "asof": "2026-01-01",
            }
        ],
    }
    (ac_dir / "AC-REAL-1.yaml").write_text(
        yaml.safe_dump(ac_record_data, sort_keys=False), encoding="utf-8"
    )

    flow = base_flow(
        "fixture-product/cli-journey",
        steps=[step("browse", ["AC-REAL-1"], 1)],
        confirmed={"against": "commit-abc123", "state": {"AC-REAL-1": confirmed_signature}},
    )
    flow["impl_summary"] = {"done": 0, "in_progress": 0, "not_started": 1, "total": 1, "asof": "2026-01-01"}
    for flow_step in flow["steps"]:
        flow_step["impl_status"] = "not_started"
    write_flow(pt_root / "flows", flow)

    common_entry_fields = {
        "flow_kind": "user",
        "screen": None,
        "mock_data": None,
        "entities": [],
        "source": "mock",
        "asof": "2026-01-01",
    }
    index = {
        "artifacts": [],
        "entity_registry": [],
        "by_component": {},
        "by_entity": {},
        "by_flow": {
            "fixture-product/cli-journey": {
                "component": "fixture-product",
                "level": None,
                "entities": [],
                "path": "flows/fixture-product/cli-journey.flow.json",
                "impl_status": "not_started",
                "impl_summary": {"done": 0, "in_progress": 0, "not_started": 1, "total": 1, "asof": "2026-01-01"},
                "expands": [],
                "parents": [],
            }
        },
        "by_ac": {
            "AC-REAL-1": [
                {"flow": "fixture-product/cli-journey", "node": "browse", "node_kind": "step", **common_entry_fields}
            ],
        },
    }
    (pt_root / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return pt_root / "scripts" / "validate_product_truth.py"


def expected_ac_signature(work_status: str) -> str:
    """Pre-computes the signature _ac_content_signature is documented to
    produce, so a caller can predict it before that function exists. MUST
    mirror the recipe pinned in test_uxp_700c_2.py's module docstring
    byte-for-byte: {work_status, product_truth, implemented_by, covered_by}
    (no `path`), sha256 of json.dumps(..., sort_keys=True, default=str)."""
    record = {
        "work_status": work_status,
        "product_truth": [
            {
                "flow": "fixture-product/cli-journey",
                "node": "browse",
                "node_kind": "step",
                "flow_kind": "user",
                "screen": None,
                "mock_data": None,
                "entities": [],
                "source": "mock",
                "asof": "2026-01-01",
            }
        ],
        "implemented_by": None,
        "covered_by": None,
    }
    payload = json.dumps(record, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# DECISION HISTORY
# ================================================================================
# - 2026-09-16 [python-coder]: Created by hand from the halted /build-feature
#   run wf_3d2879c1-2ae's backup, at the user's direction, splitting the pure
#   fixture builders out of test_uxp_700c_2.py to keep that file inside the
#   check-file-size 400-content-line limit after adding the vanished-AC-id
#   regression test. No test logic or assertions moved -- fixtures only.
#   (#EPIC-TruthfulProjectRecord/21)
