"""
MODULE: _bounds_harness
GOAL: A throwaway product-truth store for the size-bound tests (UXP-700e-1,
    UXP-700e-1-ii): real scripts and schemas copied into a tempdir, journeys
    written to disk, and the REAL generator and checker CLIs run over them.
BUSINESS CONTEXT: A bound is only proven when the checker a project actually
    runs applies it, so the seam and reachability tests drive the CLIs rather
    than call the bound functions. Shared by two test files, so it lives here
    rather than being copied into both.
ARCHITECTURE: Not a test module (leading underscore, no TestCase). The whole
    scripts/ directory is copied, as build.py deploys it, because the checker
    imports its sibling modules.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PT_SRC = REPO_ROOT / "docs" / "product-truth"
SCRIPTS_DIR = PT_SRC / "scripts"


def journey(flow_id: str, summary_length: int = 60, steps: int = 1, shape_version: int | None = None) -> dict:
    """Return a schema-valid journey with a summary and step count of the given size."""
    flow = {
        "id": flow_id, "component": "ux-prototyping", "name": flow_id, "summary": "x" * summary_length,
        "kind": "user", "source": "mock", "status": "active", "readiness": "draft", "version": 1,
        "tags": [], "entities": [],
        "steps": [{"id": f"s{n}", "label": f"s{n}", "human": "the actor acts", "order": n} for n in range(1, steps + 1)],
        "branches": [],
    }
    if shape_version is not None:
        flow["shape_version"] = shape_version
    return flow


def make_store(root: Path) -> Path:
    """Build an empty store under *root* and return its docs/product-truth directory."""
    pt = root / "docs" / "product-truth"
    shutil.copytree(SCRIPTS_DIR, pt / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(PT_SRC / "schemas", pt / "schemas")
    for place in ("flows", "mock-data", "mockups", "classifier"):
        (pt / place).mkdir(parents=True)
    (pt / "classifier" / "eval.jsonl").write_text("", encoding="utf-8")
    (root / "docs" / "acceptance-criteria").mkdir(parents=True)
    return pt


def put_journeys(pt: Path, journeys: list[dict]) -> None:
    """Replace the store's journeys with *journeys* and register them in the index."""
    shutil.rmtree(pt / "flows")
    for j in journeys:
        product, name = j["id"].split("/", 1)
        path = pt / "flows" / product / f"{name}.flow.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(j, indent=2) + "\n", encoding="utf-8")
    (pt / "flows").mkdir(exist_ok=True)
    (pt / "index.json").write_text(json.dumps({
        "artifacts": [{"id": j["id"], "type": "flow", "component": j["component"],
                       "path": "flows/{}/{}.flow.json".format(*j["id"].split("/", 1)), "status": "active",
                       "readiness": j["readiness"], "version": j["version"]} for j in journeys],
        "entity_registry": [],
    }, indent=2) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(pt / "scripts" / "generate_product_truth.py")],
                   capture_output=True, text=True, timeout=120, check=True)


def run_checker(pt: Path, *args: str) -> subprocess.CompletedProcess:
    """Run the real checker CLI over the store."""
    return subprocess.run([sys.executable, str(pt / "scripts" / "validate_product_truth.py"), *args],
                          capture_output=True, text=True, timeout=120)


def contract(result: subprocess.CompletedProcess) -> dict:
    """Return the checker's machine-readable outcome line."""
    return json.loads(result.stdout.strip().splitlines()[-1])
