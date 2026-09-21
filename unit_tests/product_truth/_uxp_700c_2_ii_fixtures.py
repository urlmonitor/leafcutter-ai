"""
MODULE: _uxp_700c_2_ii_fixtures
GOAL: Pure fixture builders and the two-process CLI installer shared by
    test_uxp_700c_2_ii.py's `behind`-mark test classes -- extracted so that
    file stays inside the 400-content-line file-size ratchet (check-file-size).
BUSINESS CONTEXT: No test logic or assertions live here -- only flow
    construction and the real generate/validate CLI installer, so this module
    carries zero coverage of its own and is not itself a test module (leading
    underscore keeps pytest from collecting it).
ARCHITECTURE: Imported by unit_tests/product_truth/test_uxp_700c_2_ii.py.
    Mirrors unit_tests/product_truth/test_uxp_700c_1.py's own _base_flow /
    _write_flow convention and test_uxp_700c_1_i.py's _install_and_check
    convention for the same product-truth store shape.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "docs" / "product-truth" / "scripts"
_PT_SRC = _REPO_ROOT / "docs" / "product-truth"


def base_flow(flow_id: str, behind: dict | None = None, confirmed: dict | None = None) -> dict:
    """A minimal, schema-shaped flow fixture; `behind` / `confirmed` are
    attached only when the caller supplies them."""
    component = flow_id.split("/", 1)[0]
    flow = {
        "id": flow_id,
        "component": component,
        "name": flow_id,
        "summary": "fixture flow for UXP-700c-2-ii behind-mark tests",
        "kind": "user",
        "source": "mock",
        "status": "active",
        "readiness": "draft",
        "version": 1,
        "entities": [],
        "steps": [
            {
                "id": "browse",
                "label": "browse",
                "human": "the actor performs browse",
                "order": 1,
                "implements": ["AC-REAL-1"],
            }
        ],
        "branches": [],
    }
    if behind is not None:
        flow["behind"] = behind
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


def read_behind_in_subprocess(path: Path) -> dict | None:
    """Re-read `path`'s `behind` key from disk in a genuinely separate Python
    process -- proves persistence, not an in-memory result (real_artifact
    angle, ADR-043 Operational section)."""
    code = (
        "import json, sys; "
        "d = json.load(open(sys.argv[1], encoding='utf-8')); "
        "print(json.dumps(d.get('behind')))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(path)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"re-read subprocess failed: {result.stderr!r}"
    return json.loads(result.stdout.strip())


def install_and_check(
    tmp: Path, behind: dict | None, confirmed: dict | None = None, ac_work_status: str = "todo"
) -> subprocess.CompletedProcess:
    """Author one journey (optionally already carrying a `behind` and/or
    `confirmed` record) and one AC, derive index.json with the REAL generator
    CLI, then run the REAL checker CLI -- the two-process path an installed
    project's pre-commit chain takes (mirrors test_uxp_700c_1_i.py's
    _install_and_check). The journey always lands at
    tmp/docs/product-truth/flows/fixture-product/cli-journey.flow.json."""
    pt = tmp / "docs" / "product-truth"
    shutil.copytree(_SCRIPTS_DIR, pt / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(_PT_SRC / "schemas", pt / "schemas")
    for place in ("mock-data", "mockups"):
        (pt / place).mkdir(parents=True)
    (pt / "classifier").mkdir(parents=True)
    (pt / "classifier" / "eval.jsonl").write_text("", encoding="utf-8")

    ac_dir = tmp / "docs" / "acceptance-criteria" / "fixture-product"
    ac_dir.mkdir(parents=True)
    (ac_dir / "AC-REAL-1.yaml").write_text(
        yaml.safe_dump({"id": "AC-REAL-1", "work_status": ac_work_status}), encoding="utf-8"
    )

    flow = base_flow("fixture-product/cli-journey", behind=behind, confirmed=confirmed)
    flow_path = pt / "flows" / "fixture-product" / "cli-journey.flow.json"
    flow_path.parent.mkdir(parents=True)
    flow_path.write_text(json.dumps(flow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    (pt / "index.json").write_text(
        json.dumps(
            {
                "artifacts": [
                    {
                        "id": flow["id"],
                        "type": "flow",
                        "component": "fixture-product",
                        "path": "flows/fixture-product/cli-journey.flow.json",
                        "status": "active",
                        "readiness": "draft",
                        "version": 1,
                    }
                ],
                "entity_registry": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    subprocess.run(
        [sys.executable, str(pt / "scripts" / "generate_product_truth.py")],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return subprocess.run(
        [sys.executable, str(pt / "scripts" / "validate_product_truth.py")],
        capture_output=True,
        text=True,
        timeout=60,
    )


# DECISION HISTORY
# ================================================================================
# - 2026-09-16 [python-coder]: Created by hand from the halted /build-feature
#   run wf_3d2879c1-2ae's backup, at the user's direction, splitting the pure
#   fixture builders and the two-process CLI installer out of
#   test_uxp_700c_2_ii.py to keep that file inside the check-file-size
#   400-content-line limit after adding the main()-wiring reachability tests
#   that resolve UXP-700c-2-ii's blocker. No test logic or assertions moved --
#   fixtures only. (#EPIC-TruthfulProjectRecord/23)
