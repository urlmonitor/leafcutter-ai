"""
MODULE: test_acd_2500d_3_i_deploy_declaration
GOAL: Failing-first proof that the two new ticket 39 modules ship to consumer projects: each is declared
    exactly once in the build's own deploy declaration (RULE_CHECK_DEPLOY_MAP), the import closure of
    the new family stays inside the declared set, and the DEPLOYED copies (read from the shared deployed
    layout, no build spawned here) import cold, in a fresh subprocess, from the flat layout.
BUSINESS CONTEXT: The G4 note, section 3 "Deploy" and section 4: `_file_findings.py` (constants and
    `undecided_findings`) and `_rc_file_findings.py` (the family) are deployed beside the rule check;
    the workflow's hold report (`approval_hold_report.py`, ticket 31) imports `_approval_holds.py`,
    which imports `_file_findings.py`, so a missing declaration would break the gate in a consumer
    project while every source-tree test stays green. Model: test_acd_2500d_5_i_deploy_declaration.py.
ARCHITECTURE: No test here spawns build.py: the deployed layout is the sanctioned shared one. The cold
    import runs in a genuinely fresh interpreter (not importlib.reload, which masks cold-import errors).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPTS = REPO / "scripts"
NEW_MODULES = ("_file_findings", "_rc_file_findings")
FAMILY = "file findings consistency"


def _declared() -> list[str]:
    sys.path.insert(0, str(SCRIPTS))
    import build_phases_ac_store_rc as rc_map  # noqa: PLC0415

    return [src for src, _dest in rc_map.RULE_CHECK_DEPLOY_MAP]


def test_new_modules_declared_once_in_the_rule_check_deploy_map():
    # covers: ACD-2500d-3-i
    # angle: deployed
    """Each new module is exactly one entry of RULE_CHECK_DEPLOY_MAP and its source exists.

    Control: the rule-check entry script is declared the same way (the map was read correctly), and
    `build_phases_ac_store.py` splices the same entries in exactly once (never a second line there).
    """
    declared = _declared()
    assert "scripts/ac_store/requirement_rule_check.py" in declared
    counts = {name: declared.count(f"scripts/ac_store/{name}.py") for name in NEW_MODULES}
    assert counts == {name: 1 for name in NEW_MODULES}, counts
    missing = [name for name in NEW_MODULES if not (REPO / "scripts" / "ac_store" / f"{name}.py").is_file()]
    assert missing == [], f"declared sources missing: {missing}"

    import build_phases_ac_store as phase  # noqa: PLC0415

    spliced = [src for src, _dest in phase.AC_STORE_DEPLOY_MAP]
    assert [spliced.count(f"scripts/ac_store/{name}.py") for name in NEW_MODULES] == [1, 1]


def test_family_import_closure_is_inside_the_deploy_map():
    # covers: ACD-2500d-3-i
    # angle: deployed
    """Every scripts/ac_store module the family imports is deployed; the approval hold reaches the predicate.

    The derived check the real build guard runs (compute_intra_package_closure), computed in process
    with no build. `_approval_holds.py` must now reach `_file_findings.py` (one shared predicate).
    """
    sys.path.insert(0, str(SCRIPTS))
    import build_referential_integrity as bri  # noqa: PLC0415

    entry = REPO / "scripts" / "ac_store" / "_rc_file_findings.py"
    assert entry.is_file(), f"{entry} does not exist yet"
    import build_phases_ac_store as phase  # noqa: PLC0415

    # the whole deploy map: the rule-check map is spliced into it, and seams such as
    # declared_files.py are deployed through it already
    deployed = {src for src, _dest in phase.AC_STORE_DEPLOY_MAP}
    holds = bri.compute_intra_package_closure(REPO / "scripts" / "ac_store" / "_approval_holds.py", REPO)
    family = bri.compute_intra_package_closure(entry, REPO)
    modules = {m for m in family if m.startswith("scripts/ac_store/") and m.endswith(".py")}

    assert "scripts/ac_store/_file_findings.py" in holds, "the approval hold must read the shared predicate"
    assert modules <= deployed, sorted(modules - deployed)


@pytest.mark.shared_layout_reader
def test_deployed_modules_import_cold_from_the_deployed_layout(shared_reference_layout):
    # covers: ACD-2500d-3-i
    # angle: real_artifact
    """From the deployed layout, in a fresh interpreter: both modules import and the family name matches.

    `.leafcutter/scripts/ac_store/` holds `_file_findings.py` and `_rc_file_findings.py`; a cold
    subprocess with that directory first on sys.path imports them, `NAME` equals the family the rule check
    reports, and `undecided_findings` returns the one undecided finding of a two-finding record.
    """
    layout = Path(shared_reference_layout)
    flat = layout / ".leafcutter" / "scripts" / "ac_store"
    absent = [name for name in NEW_MODULES if not (flat / f"{name}.py").is_file()]
    assert absent == [], f"not deployed: {absent}"

    code = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "import _rc_file_findings as fam, _file_findings as ff;"
        "decided = {'choice': 'reassign', 'reason': 'r', 'by': 'it-po'};"
        "mk = lambda d: {'file': 'a.py', 'verdict': 'describes, does not implement', 'reason': 'r', 'decision': d};"
        "rec = {ff.FINDINGS_KEY: [mk(None), mk(decided)]};"
        "print(fam.NAME + '|' + str(len(list(ff.undecided_findings(rec)))))"
    )
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    done = subprocess.run(
        [sys.executable, "-c", code, str(flat)], capture_output=True, text=True, timeout=60, cwd=str(layout), env=env
    )
    assert done.returncode == 0, done.stderr[-600:]
    assert done.stdout.strip() == f"{FAMILY}|1", done.stdout
