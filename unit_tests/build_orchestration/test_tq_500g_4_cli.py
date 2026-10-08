"""
MODULE: unit_tests/build_orchestration/test_tq_500g_4_cli.py
GOAL: TQ-500g-4 / TQ-500g-4-i through the production CLIs -- fast_lane.py
    verify_red_baseline and the done-proof CLI (mark_ac_done.py --test-root),
    each run as a subprocess over real pytest runs (fixtures shared with
    unit_tests/ac_store/_tq500g4_fixtures.py), plus the DEPLOYED copy of the
    red-baseline gate from the shared reference layout (no private build.py).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import unit_tests.ac_store._tq500g4_fixtures as fx

_INCONCLUSIVE_REASON = "no failing test could be identified"


def test_red_baseline_counts_subfailed_test_red(tmp_path):
    # covers: TQ-500g-4
    # angle: reachability
    # Entry point: python scripts/build_orchestration/fast_lane.py verify_red_baseline.
    # Wrong versions caught: SUBFAILED ignored (S1 listed green_at_baseline);
    # downgrade applied in the done-proof path only (same symptom here).
    work, test_root, _ac_root = fx.build_run(tmp_path, "S")
    rc, verdict = fx.run_red_baseline_cli(work, test_root, fx.ALL_ACS)
    assert "test_refresh_gate" in fx.bucket_names(verdict, "red"), verdict
    assert "test_refresh_gate" not in fx.bucket_names(verdict, "green_at_baseline"), verdict
    assert fx.SUBCASE in repr(verdict["red"]), verdict["red"]
    assert rc == 0 and verdict["gate_passed"] is True, (rc, verdict)


def test_contradictory_run_inconclusive_through_production_clis(tmp_path):
    # covers: TQ-500g-4-i
    # angle: reachability
    # Entries: fast_lane.py verify_red_baseline + mark_ac_done.py --test-root.
    # Wrong versions caught: returncode only checked for (0, 1); contradictory
    # run read as all passed (done CLI says "would mark done", baseline green).
    work, test_root, ac_root = fx.build_run(tmp_path, "R1")
    rc, verdict = fx.run_red_baseline_cli(work, test_root, [fx.AC_S1, fx.AC_S2])
    assert fx.bucket_names(verdict, "inconclusive") == {
        "test_refresh_gate", "test_export_gate"}, verdict
    assert verdict["red"] == [] and verdict["green_at_baseline"] == [], verdict
    assert rc == 1 and verdict["gate_passed"] is False, (rc, verdict)
    proc = fx.run_mark_done_cli(work, ac_root, test_root, fx.AC_S1)
    assert proc.returncode == 3, (proc.returncode, proc.stdout, proc.stderr)
    assert _INCONCLUSIVE_REASON in proc.stderr, proc.stderr


_DEPLOY_SNIPPET = """
import sys
from pathlib import Path
sys.path.insert(0, r"{scripts}")
import build_phases as bp
target = Path(r"{target}")
bp.build_ac_store(target, {{}}, False, True)
bp.build_build_orchestration_scripts(target, {{}}, False, True)
bp.build_phases_script_deploy._deploy_fast_lane_release_dependency(target, False, True)     if hasattr(bp, "build_phases_script_deploy") else bp._deploy_fast_lane_release_dependency(target, False, True)
"""


def _deploy_into(target: Path) -> Path:
    """Deploy the AC-store + build-orchestration phases (the REAL build-phase
    functions, as build.py calls them) into *target* in a fresh subprocess.
    No build.py is spawned (CLAUDE.md: tests must not spawn their own build.py)."""
    code = _DEPLOY_SNIPPET.format(scripts=fx.REPO_ROOT / "scripts", target=target)
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, timeout=120, cwd=fx.REPO_ROOT)
    assert proc.returncode == 0, f"deploy phases failed: {proc.stderr[-1500:]}"
    script = target / "scripts" / "build_orchestration" / "fast_lane.py"
    assert script.is_file(), f"deployed layout lacks {script}"
    return script


def test_deployed_gate_reads_subfailed_as_failed(tmp_path):
    # covers: TQ-500g-4
    # angle: deployed
    # Deploys via the real build-phase functions into a temp target (the shared
    # reference layout needs POSIX flock and errors at setup on Windows), then
    # runs the DEPLOYED verify_red_baseline in a fresh subprocess: it must
    # import the new sibling reader and read S1 as red.
    # Wrong version caught: new sibling module missing from AC_STORE_DEPLOY_MAP
    # (deployed gate dies at import -> no JSON verdict -> assertion error).
    script = _deploy_into(tmp_path / "target")
    work, test_root, _ac_root = fx.build_run(tmp_path / "run", "S")
    rc, verdict = fx.run_red_baseline_cli(work, test_root, fx.ALL_ACS, script=script)
    assert "test_refresh_gate" in fx.bucket_names(verdict, "red"), (rc, verdict)
    assert "test_refresh_gate" not in fx.bucket_names(verdict, "green_at_baseline"), verdict
