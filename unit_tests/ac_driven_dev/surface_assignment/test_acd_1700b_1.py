"""
MODULE: test_acd_1700b_1
GOAL: Failing-first tests for ACD-1700b-1 -- the assignment-quality check that
    flags an assigned_agent which mismatches the deliverable surface.

CONTRACT THIS FILE PINS (python-coder must implement):
    scripts/ac_store/assignment_quality.py
        evaluate_assignment(ac_id, surface, assigned_agent, map_path=None) -> dict
            {ac_id, surface, resolved_craft, assigned_agent,
             verdict: 'match'|'mismatch'|'unresolved', held: bool}
        resolve_craft(surface, map_path=None) -> str | None   (first-match-wins)
        CLI: python scripts/ac_store/assignment_quality.py --ac-id ID
             --surface PATH --assigned-agent AGENT [--map FILE]
             prints the verdict dict as JSON on stdout; exit 0 (advisory,
             ADR-026 warn-before-required). held is true only on mismatch.
    config/surface_craft_map.yaml : ordered list of {glob, craft}, first match
        wins, templates/workflows-js/**/*.{js,mjs} -> python-coder ahead of a
        generic web *.js -> frontend-coder. Also added to deploy_map in
        scripts/build_phases.py.
"""
import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "ac_store" / "assignment_quality.py"
MAP = REPO / "config" / "surface_craft_map.yaml"


def _run(surface, agent, map_path=None, ac_id="ACD-1700b-1"):
    cmd = [sys.executable, str(SCRIPT), "--ac-id", ac_id,
           "--surface", surface, "--assigned-agent", agent]
    if map_path:
        cmd += ["--map", str(map_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_js_workflow_body_python_coder_passes():
    # covers: ACD-1700b-1
    # angle: criterion
    for ext in ("js", "mjs"):
        out = _run(f"templates/workflows-js/build-feature/step.{ext}", "python-coder")
        assert out["verdict"] == "match"
        assert out["resolved_craft"] == "python-coder"
        assert out["held"] is False


def test_frontend_deliverable_python_coder_flagged():
    # covers: ACD-1700b-1
    # angle: discrimination
    # Wrong version caught: an extension-blind check that passes everything.
    for ext in ("jsx", "tsx", "vue", "svelte"):
        out = _run(f"web/app/page.{ext}", "python-coder")
        assert out["verdict"] == "mismatch", ext
        assert out["resolved_craft"] == "frontend-coder"
        assert out["held"] is True
    ctrl = _run("web/app/page.tsx", "frontend-coder")
    assert ctrl["verdict"] == "match" and ctrl["held"] is False


def test_sql_deliverable_python_coder_flagged():
    # covers: ACD-1700b-1
    # angle: failure
    out = _run("db/migrations/001_init.sql", "python-coder")
    assert out["verdict"] == "mismatch"
    assert out["resolved_craft"] == "sql-coder"
    assert out["held"] is True
    assert _run("db/migrations/001_init.sql", "sql-coder")["verdict"] == "match"


def test_mismatch_flag_names_surface_craft_and_agent():
    # covers: ACD-1700b-1
    # angle: seam
    out = _run("web/app/page.tsx", "python-coder", ac_id="ACD-9999-1")
    assert out["surface"] == "web/app/page.tsx"
    assert out["resolved_craft"] == "frontend-coder"
    assert out["assigned_agent"] == "python-coder"
    assert out["ac_id"] == "ACD-9999-1"
    assert out["verdict"] == "mismatch"


def test_map_first_match_wins_path_aware():
    # covers: ACD-1700b-1
    # angle: boundary
    assert _run("web/app/main.js", "frontend-coder")["resolved_craft"] == "frontend-coder"
    assert _run("templates/workflows-js/x/main.js", "python-coder")["resolved_craft"] == "python-coder"
    # map is the single source of truth: a changed fixture map changes the verdict
    real = yaml.safe_load(MAP.read_text(encoding="utf-8"))
    entries = real["entries"] if isinstance(real, dict) else real
    assert isinstance(entries, list) and entries[0].keys() >= {"glob", "craft"}


def test_unmatched_surface_is_unresolved_not_pass_or_mismatch(tmp_path):
    # covers: ACD-1700b-1
    # angle: boundary
    out = _run("weird/thing.zzzqq", "python-coder")
    assert out["verdict"] == "unresolved"
    assert out["resolved_craft"] is None
    assert out["held"] is False


def test_changed_fixture_map_changes_verdict(tmp_path):
    # covers: ACD-1700b-1
    # angle: seam
    m = tmp_path / "map.yaml"
    m.write_text(yaml.safe_dump([{"glob": "**/*.zzz", "craft": "sql-coder"}]), encoding="utf-8")
    assert _run("a/b.zzz", "sql-coder", m)["verdict"] == "match"
    assert _run("a/b.zzz", "python-coder", m)["verdict"] == "mismatch"


def test_acd_1700b_1_reachable_from_entry_point():
    # covers: ACD-1700b-1
    # angle: reachability
    # Entry point: CLI script scripts/ac_store/assignment_quality.py via subprocess.
    assert SCRIPT.is_file(), "scripts/ac_store/assignment_quality.py must exist"
    out = _run("db/q.sql", "python-coder")
    assert out["verdict"] == "mismatch" and out["held"] is True
