"""
MODULE: unit_tests/build_guards/test_inf_700a_5_deploy_and_wiring.py
GOAL: Prove the INF-700a-5 durability step is REACHABLE in a deployed install,
    and that the completion-path wiring declaration matches what the paths do.

    1. The deployed layout (the ONE shared reference build -- this test only
       reads it) carries completion_routing.py and every sibling it loads,
       and the deployed CLI actually runs from there against a temp sink.
       The source-tree tests cannot see a missing deploy entry; this can.
    2. build-epic.js is EXCLUDED from knowledge_routing_wiring (BrainCandy,
       2026-10-08, ADR-040 section 3): no commit follows its routing step, so
       its writes could never be published. The exclusion is checked against
       the real guard over the real config, and the path itself is driven
       through the engine harness to show it no longer dispatches a routing
       step that would write unpublishable files.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT, _REPO_ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from build_phases_knowledge import (  # noqa: E402
    _manifest_knowledge_scripts,
    check_knowledge_routing_wiring,
)
from unit_tests._workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_MODULES = (
    "completion_routing.py",
    "completion_routing_state.py",
    "completion_routing_git.py",
    "completion_routing_cli.py",
)


@pytest.mark.shared_layout_reader
def test_the_deployed_layout_carries_the_durability_modules_and_the_cli_runs(
    shared_reference_layout, tmp_path
):
    # covers: INF-700a-5
    # angle: reachability
    knowledge = Path(shared_reference_layout) / ".leafcutter" / "scripts" / "knowledge"
    missing = [m for m in _MODULES if not (knowledge / m).is_file()]
    assert not missing, f"not deployed to {knowledge}: {missing}"

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    sink = tmp_path / "logs" / "knowledge_emissions.jsonl"
    proc = subprocess.run(
        [sys.executable, str(knowledge / "completion_routing_cli.py"), "stage",
         "--working-dir", str(repo), "--sink", str(sink)],
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    reply = json.loads(proc.stdout.splitlines()[-1])
    assert reply["case"] == "completed", reply
    assert reply["manifest"] == [], reply


def test_the_build_manifest_names_every_durability_module():
    # covers: INF-700a-5
    # angle: seam
    names = _manifest_knowledge_scripts(_REPO_ROOT)
    for module in _MODULES:
        assert any(n.endswith(module) for n in names), f"{module} missing from {sorted(names)}"


def test_build_epic_is_excluded_with_its_reason_and_the_guard_still_passes():
    # covers: INF-700a-5
    # angle: boundary
    config = yaml.safe_load((_REPO_ROOT / "config" / "guardrail_gates.yaml").read_text())
    section = config["knowledge_routing_wiring"]
    assert "build-epic.js" not in section["wired"]
    excluded = {e["path"]: e["reason"] for e in section["excluded"]}
    assert "no commit follows the step" in excluded.get("build-epic.js", "").lower(), excluded
    result = check_knowledge_routing_wiring(_REPO_ROOT / "templates" / "workflows-js", config)
    assert result["unwired"] == [], result


def test_build_epic_no_longer_dispatches_an_unpublishable_routing_step():
    # covers: INF-700a-5
    # angle: reachability
    ticket = "01_ticket.md"
    result = run_workflow_under_e2(
        _REPO_ROOT / "templates" / "workflows-js" / "build-epic.js",
        label_responses={
            "epic-planner": {
                "epic_path": "tickets/00_inbox/epics/EPIC-X",
                "title": "EPIC-X",
                "batches": [{"batch_number": 1, "tickets": [{"path": ticket, "status": "todo"}]}],
            },
            f"ticket:{ticket}": {"status": "ok"},
        },
        args={"epic_path": "tickets/00_inbox/epics/EPIC-X", "worktree_path": "/tmp/wt"},
    )
    assert result.error == "", result.error
    assert (result.result or {}).get("status") == "ok", result.result
    labels = [c.label for c in result.agent_calls]
    assert "knowledge-routing-step" not in labels, labels
