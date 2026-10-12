"""
MODULE: test_acd_1700b_1_i
GOAL: Failing-first tests for ACD-1700b-1-i -- split detection: an AC whose
    deliverable spans surfaces that resolve to two distinct crafts is flagged for a
    per-surface split; one assigned_agent is never accepted as covering both.

CONTRACT THIS FILE PINS (python-coder must implement; extends the
ACD-1700b-1 machinery in scripts/ac_store/assignment_quality.py):
    CLI: python scripts/ac_store/assignment_quality.py --ac-id ID
         --surface PATH --surface PATH [...] --assigned-agent AGENT [--map FILE]
         `--surface` is repeatable. With two or more surfaces the stdout JSON is
         {ac_id, assigned_agent,
          surfaces: [{surface, craft}, ...]   # input order, one per surface
          split_required: bool,               # True iff >1 DISTINCT crafts resolve
          held: bool}                         # == split_required
         exit 0 (advisory, ADR-026). Derived ONLY from the distinct crafts the map
         resolves -- no hard-coded surface pair.
"""
import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "ac_store" / "assignment_quality.py"


def _run(surfaces, agent, map_path=None, ac_id="ACD-1700b-1-i"):
    cmd = [sys.executable, str(SCRIPT), "--ac-id", ac_id]
    for s in surfaces:
        cmd += ["--surface", s]
    cmd += ["--assigned-agent", agent]
    if map_path:
        cmd += ["--map", str(map_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _map(tmp_path, entries):
    m = tmp_path / "map.yaml"
    m.write_text(yaml.safe_dump(entries), encoding="utf-8")  # real serializer
    return m


def test_two_surface_deliverable_flagged_for_split(tmp_path):
    # covers: ACD-1700b-1-i
    # angle: criterion
    """Real map: a Python helper plus agent-template prose resolve to two crafts."""
    out = _run(["scripts/ac_store/helper.py", "templates/agents/some-agent.md"], "python-coder")
    assert out["split_required"] is True
    assert out["held"] is True
    crafts = {s["craft"] for s in out["surfaces"]}
    assert len(crafts) == 2 and None not in crafts
    assert "python-coder" in crafts
    # the single assigned_agent cannot cover both: whoever it is, still flagged
    other = next(c for c in crafts if c != "python-coder")
    assert _run(["scripts/ac_store/helper.py", "templates/agents/some-agent.md"], other)["split_required"] is True


def test_split_flag_enumerates_each_surface_and_craft(tmp_path):
    # covers: ACD-1700b-1-i
    # angle: seam
    """Fixture map (map is the only source): payload lists every surface with its craft."""
    m = _map(tmp_path, [{"glob": "**/*.aaa", "craft": "craft-a"}, {"glob": "**/*.bbb", "craft": "craft-b"},
                        {"glob": "**/*.ccc", "craft": "craft-c"}])
    out = _run(["x/one.aaa", "y/two.bbb", "z/three.ccc"], "craft-a", m)
    assert out["surfaces"] == [
        {"surface": "x/one.aaa", "craft": "craft-a"},
        {"surface": "y/two.bbb", "craft": "craft-b"},
        {"surface": "z/three.ccc", "craft": "craft-c"},
    ]
    assert out["split_required"] is True and out["ac_id"] == "ACD-1700b-1-i"
    assert out["assigned_agent"] == "craft-a"


def test_single_surface_not_flagged_for_split(tmp_path):
    # covers: ACD-1700b-1-i
    # angle: discrimination
    # Wrong version caught: flagging on surface COUNT (or distinct extensions)
    # instead of distinct resolved crafts.
    m = _map(tmp_path, [{"glob": "**/*.aaa", "craft": "craft-a"}, {"glob": "**/*.bbb", "craft": "craft-a"},
                        {"glob": "**/*.ccc", "craft": "craft-b"}])
    same = _run(["x/one.aaa", "y/two.bbb"], "craft-a", m)  # two surfaces, ONE craft
    assert same["split_required"] is False and same["held"] is False
    assert [s["craft"] for s in same["surfaces"]] == ["craft-a", "craft-a"]
    # control: the same machinery does flag when a second craft appears
    assert _run(["x/one.aaa", "z/three.ccc"], "craft-a", m)["split_required"] is True
