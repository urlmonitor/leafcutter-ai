"""
MODULE: test_acd_2500d_5_i_deploy_declaration
GOAL: Failing-first proof that the deterministic design pre-pass ships to consumer projects: its source
    is declared exactly once in the build's own deploy declaration, it imports only what is deployed,
    and the DEPLOYED copy (read from the shared deployed layout, no build spawned here) runs from the
    flat layout and gives byte-for-byte the same report as the canonical script.
BUSINESS CONTEXT: ACD-2500d-5-i it_requirement "ships to consumer projects ... verified from the deployed
    layout after a rebuild" (ADR-001, ADR-013); the plan-feature workflow reads
    `.leafcutter/scripts/ac_store/design_prepass.py`. Model: test_acd_2500a_1_deploy_declaration.py.
ARCHITECTURE (G4 architect note, section 3 "Deploy"): the module name is one more entry of
    build_phases_ac_store_rc.RULE_CHECK_DEPLOY_MAP (never a line in build_phases_ac_store.py); the closure
    check is the one the real build guard runs (build_referential_integrity.compute_intra_package_closure).
    No test here spawns build.py: the deployed layout is the sanctioned shared one.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPTS = REPO / "scripts"
ENTRY = "scripts/ac_store/design_prepass.py"
sys.path.insert(0, str(REPO / "unit_tests" / "ac_store"))


def _deploy_sources() -> list[str]:
    sys.path.insert(0, str(SCRIPTS))
    import build_phases_ac_store as phase

    return [src for src, _dest in phase.AC_STORE_DEPLOY_MAP]


def test_design_prepass_declared_once_in_the_rule_check_deploy_map():
    # covers: ACD-2500d-5-i
    # angle: deployed
    """The pre-pass is one entry of RULE_CHECK_DEPLOY_MAP, which AC_STORE_DEPLOY_MAP splices in; its source
    exists; the control (the G2 entry script) is declared the same way."""
    sys.path.insert(0, str(SCRIPTS))
    import build_phases_ac_store_rc as rc_map

    declared = [src for src, _dest in rc_map.RULE_CHECK_DEPLOY_MAP]
    assert "scripts/ac_store/requirement_rule_check.py" in declared  # control: the map was read correctly
    assert declared.count(ENTRY) == 1, f"{ENTRY} must be declared exactly once in RULE_CHECK_DEPLOY_MAP"
    assert (REPO / ENTRY).is_file(), f"declared source missing: {ENTRY}"
    assert _deploy_sources().count(ENTRY) == 1, "the build's AC_STORE_DEPLOY_MAP must carry it exactly once"


def test_design_prepass_import_closure_is_inside_the_deploy_map():
    # covers: ACD-2500d-5-i
    # angle: deployed
    """Every scripts/ac_store python module reachable from the pre-pass is itself deployed (the derived
    check the real build guard runs), computed in-process with no build; the closure must include the
    declared-files seam (the one place declared files are read)."""
    sys.path.insert(0, str(SCRIPTS))
    import build_referential_integrity as bri

    assert (REPO / ENTRY).is_file(), f"{ENTRY} does not exist yet"
    closure = bri.compute_intra_package_closure(REPO / ENTRY, REPO)
    modules = {item for item in closure if item.startswith("scripts/ac_store/") and item.endswith(".py")}

    assert "scripts/ac_store/declared_files.py" in modules, "declared files must be read through the seam"
    assert modules <= set(_deploy_sources()), sorted(modules - set(_deploy_sources()))


@pytest.mark.shared_layout_reader
def test_deployed_design_prepass_runs_from_the_deployed_layout(shared_reference_layout, tmp_path):
    # covers: ACD-2500d-5-i
    # angle: deployed
    """From the deployed layout: .leafcutter/scripts/ac_store/design_prepass.py exists, shows --ids in --help,
    and on the AC's R1/R2/R3 batch prints exactly the bytes the canonical script prints."""
    from _acd_2500d_5_i_fixtures import BATCH_IDS, PREPASS_SCRIPT, batch_store, run_prepass

    layout = Path(shared_reference_layout)
    deployed = layout / ".leafcutter" / "scripts" / "ac_store" / "design_prepass.py"
    assert deployed.is_file(), f"not deployed: {deployed}"
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    helped = subprocess.run(
        [sys.executable, str(deployed), "--help"], capture_output=True, text=True, timeout=60, cwd=str(layout), env=env
    )
    assert helped.returncode == 0, helped.stderr
    assert "--ids" in helped.stdout

    store = batch_store(tmp_path)
    canonical = run_prepass(store, BATCH_IDS)
    argv = [
        sys.executable, str(deployed), "--ids", ",".join(BATCH_IDS),
        "--store-root", str(store.repo_root / "docs" / "acceptance-criteria"), "--repo-root", str(store.repo_root),
    ]
    from_deployed = subprocess.run(argv, capture_output=True, timeout=60, cwd=str(layout), env=env)

    assert PREPASS_SCRIPT.is_file() and canonical.exit_code == 0, canonical.stderr
    assert from_deployed.returncode == 0, from_deployed.stderr.decode("utf-8", "replace")
    assert from_deployed.stdout == canonical.stdout, "deployed copy drifted from the canonical script"
