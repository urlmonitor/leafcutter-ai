"""
MODULE: test_acd_2500a_1_deploy_declaration
GOAL: Failing-first proof that the requirement rule check ships to consumer projects:
    its 11 modules are in the build's own deploy declaration, they import only what is
    deployed, and the deployed copy of plan-feature.js and the script work from the
    deployed layout. No test here spawns build.py (CLAUDE.md: tests must not spawn
    their own build.py); the deployed layout is the sanctioned shared one.
ARCHITECTURE (architect note, section 5):
    1. Each of the 11 sources is a single entry of build_phases_ac_store.AC_STORE_DEPLOY_MAP.
    2. The in-process closure check the real build guard runs
       (build_referential_integrity.compute_intra_package_closure) finds every import
       of the entry script inside the deploy map.
    3. Parity from the deployed layout: `shared_reference_layout` (reader-declared)
       holds .leafcutter/workflows/plan-feature.js equal to the template with only
       `{{config.output_root}}` substituted, and the deployed script runs `--help`
       from its flat layout.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPTS = REPO / "scripts"
ENTRY = "scripts/ac_store/requirement_rule_check.py"
MODULES = (
    "requirement_rule_check", "_rc_report", "_rc_records", "_rc_record_schema", "_rc_edit",
    "_rc_backlinks", "_rc_components", "_rc_contracts", "_rc_readiness", "_rc_doc_triggers",
    "_rc_declared",
)
_PLACEHOLDER = "{{config.output_root}}"


def _deploy_sources() -> list[str]:
    sys.path.insert(0, str(SCRIPTS))
    import build_phases_ac_store as phase

    return [src for src, _dest in phase.AC_STORE_DEPLOY_MAP]


def test_rule_check_modules_in_ac_store_deploy_map():
    # covers: ACD-2500a-1
    # angle: deployed
    """All 11 modules appear exactly once in AC_STORE_DEPLOY_MAP, and each source exists."""
    sources = _deploy_sources()

    assert "scripts/ac_store/scan_ac_store.py" in sources  # control: the map was read correctly
    for module in MODULES:
        relative = f"scripts/ac_store/{module}.py"
        assert sources.count(relative) == 1, f"{relative} must be declared exactly once"
        assert (REPO / relative).is_file(), f"declared source missing: {relative}"


def test_rule_check_import_closure_is_inside_the_deploy_map():
    # covers: ACD-2500a-1
    # angle: deployed
    """Every python module reachable from the entry script is itself deployed (the derived
    check the real build guard runs), computed in-process with no build."""
    sys.path.insert(0, str(SCRIPTS))
    import build_referential_integrity as bri

    sources = set(_deploy_sources())
    assert (REPO / ENTRY).is_file(), f"{ENTRY} does not exist yet"

    closure = bri.compute_intra_package_closure(REPO / ENTRY, REPO)

    # The closure also lists data reads (config/, docs/); those deploy through other
    # phases. The deploy-map contract is about the python modules of this package.
    modules = {item for item in closure if item.startswith("scripts/ac_store/") and item.endswith(".py")}
    assert "scripts/ac_store/validate_ac_schema.py" in modules, (
        "the check must CALL the store's existing record check (control: closure is non-trivial)"
    )
    assert modules <= sources, sorted(modules - sources)


@pytest.mark.shared_layout_reader
def test_deployed_plan_feature_and_script_match_canonical_sources(shared_reference_layout):
    # covers: ACD-2500a-1
    # angle: deployed
    """From the deployed layout: plan-feature.js equals the template (only
    `{{config.output_root}}` substituted, and it carries the rule-check dispatch), and
    the deployed requirement_rule_check.py runs from the flat layout."""
    layout = Path(shared_reference_layout)
    deployed_workflow = (layout / ".leafcutter" / "workflows" / "plan-feature.js").read_text(
        encoding="utf-8"
    )
    template = (REPO / "templates" / "workflows-js" / "plan-feature.js").read_text(encoding="utf-8")
    pattern = "(?s)^" + "(?:.*?)".join(re.escape(part) for part in template.split(_PLACEHOLDER)) + "$"
    assert re.match(pattern, deployed_workflow), "deployed plan-feature.js drifted from the template"
    assert "rule-check-" in deployed_workflow  # the dispatch the template must now carry

    deployed_script = layout / ".leafcutter" / "scripts" / "ac_store" / "requirement_rule_check.py"
    assert deployed_script.is_file(), f"not deployed: {deployed_script}"
    proc = subprocess.run(
        [sys.executable, str(deployed_script), "--help"],
        capture_output=True, text=True, timeout=60, cwd=str(layout),
    )
    assert proc.returncode == 0, proc.stderr
    assert "--location" in proc.stdout
