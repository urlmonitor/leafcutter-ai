"""
MODULE: test_acd_1700b_1_i_reachability
GOAL: Reachability proof for ACD-1700b-1-i: the real assignment_quality.py CLI, run
    as a subprocess with two surfaces of different crafts, flags a split.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "ac_store" / "assignment_quality.py"


def test_acd_1700b_1_i_cli_flags_two_craft_deliverable_for_split():
    """ACD-1700b-1-i: assignment_quality CLI (subprocess) flags a py + agent-prompt deliverable."""
    # covers: ACD-1700b-1-i
    # angle: reachability
    cmd = [sys.executable, str(SCRIPT), "--ac-id", "ACD-1700b-1-i",
           "--surface", "scripts/ac_store/helper.py",
           "--surface", "templates/agents/example.md",
           "--assigned-agent", "python-coder"]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, timeout=60)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["split_required"] is True
    crafts = {s["surface"]: s["craft"] for s in out["surfaces"]}
    assert crafts == {"scripts/ac_store/helper.py": "python-coder",
                      "templates/agents/example.md": "llm-expert"}
