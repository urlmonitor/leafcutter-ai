"""
MODULE: test_acd_1700b_1_deploy_declaration
GOAL: Failing-first proof that ACD-1700b-1's two new artifacts are in the build's own
    deploy declaration, without spawning a build (CLAUDE.md: tests must not spawn their
    own build.py).
ARCHITECTURE: (1) scripts/ac_store/assignment_quality.py must be a source entry in
    build_phases_ac_store.AC_STORE_DEPLOY_MAP (imported, as the existing deploy-map
    tests do). (2) config/surface_craft_map.yaml must appear in the core-config tuple
    that build_ac_store() iterates to deploy config/ files (read via ast from the
    phase's own source, since the tuple is function-local), and in build.py's
    deploy manifest tuples (same ast read).
"""
import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPTS = REPO / "scripts"
MAP_NAME = "surface_craft_map.yaml"


def _config_tuples(path: Path, func_name: str | None = None):
    """Yield each tuple/list of >=3 string constants that includes 'ac_store_schema.json'."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Tuple, ast.List)):
            vals = [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if "ac_store_schema.json" in vals and "agent_registry.json" in vals:
                yield vals


def test_assignment_quality_script_in_ac_store_deploy_map():
    # covers: ACD-1700b-1
    # angle: deployed
    sys.path.insert(0, str(SCRIPTS))
    import build_phases_ac_store as phase

    sources = [src for src, _dest in phase.AC_STORE_DEPLOY_MAP]
    assert "scripts/ac_store/scan_ac_store.py" in sources  # control: map read correctly
    assert sources.count("scripts/ac_store/assignment_quality.py") == 1


def test_surface_craft_map_in_config_deploy_phase_declaration():
    # covers: ACD-1700b-1
    # angle: deployed
    tuples = list(_config_tuples(SCRIPTS / "build_phases_ac_store.py"))
    assert tuples, "core-config tuple not found in build_phases_ac_store.py (control)"
    assert all(MAP_NAME in t for t in tuples), f"{MAP_NAME} not in the config deploy tuple"


def test_surface_craft_map_in_build_manifest():
    # covers: ACD-1700b-1
    # angle: deployed
    tuples = list(_config_tuples(SCRIPTS / "build.py"))
    assert tuples, "build.py config manifest tuples not found (control)"
    assert all(MAP_NAME in t for t in tuples), f"{MAP_NAME} not in build.py's deploy manifest"
