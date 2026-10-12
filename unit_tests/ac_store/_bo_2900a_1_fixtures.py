"""
MODULE: unit_tests/ac_store/_bo_2900a_1_fixtures.py
GOAL: Shared fixture construction for the BO-2900a-1 test family
    (test_bo_2900a_1.py, test_bo_2900a_1_ii.py) -- the AC YAML writer, the
    real-importable Python fixture-file writer, and the git-fixture-project
    initialiser, plus the sys.path setup every sibling module needs to
    import ``done_proof`` directly.
BUSINESS CONTEXT: test_bo_2900a_1.py originally held all fixtures and tests
    in one file and exceeded check_file_size.py's 400-content-line new-file
    limit (426 lines) once the cross-file fixture (Test 5) was added on
    rework. Extracted here, mirroring the precedent of
    unit_tests/ac_store/_tkt_500f_fixtures.py, so neither sibling test file
    has to duplicate this logic or re-grow past the limit.
COVERS: (support module -- no test functions live here)
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts" / "ac_store"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

#: Real, deployed CLI entry point for the reachability tests -- resolved via
#: Step 1 of the Reachability Entry-Point Resolution procedure: this is a
#: registered pre-commit hook (commit_guardian.json id "check-done-proof")
#: AND the required CI done-proof job (.github/workflows/ci.yml).
CHECK_DONE_PROOF_SCRIPT = REPO_ROOT / "scripts" / "commit_guardian" / "check_done_proof.py"


def write_ac(ac_root: Path, ac_id: str, *, work_status: str = "todo") -> Path:
    """Write a minimal active AC YAML using yaml.safe_dump (mandate-compliant)."""
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic BO-2900a-1 fixture AC {ac_id}",
        "component": "build-orchestration",
        "components": ["build_orchestration"],
        "level": "L3",
        "status": "active",
        "work_status": work_status,
        "readiness": "draft",
        "priority": "medium",
        "depends_on": [],
        "amended_by": [],
        "covered_by": [],
        "implemented_by": [],
        "superseded_by": None,
        "criteria": (
            "Given a fixture unit with a genuine argparse main(argv)\n"
            "When verify_done_eligible evaluates its covers-tagged proof\n"
            "Then a direct-import proof is refused and an entry-point-driven "
            "proof is eligible\n"
        ),
    }
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def write_fixture_file(test_root: Path, filename: str, content: str) -> Path:
    """Write a real, importable Python fixture file to test_root."""
    test_root.mkdir(parents=True, exist_ok=True)
    path = test_root / filename
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def init_git_fixture_project(root: Path) -> None:
    """Git-initialise *root* so find_project_root() resolves it correctly
    when check_done_proof.py's real CLI runs with cwd=root."""
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True, capture_output=True)
    (root / "docs" / "acceptance-criteria").mkdir(parents=True, exist_ok=True)
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
