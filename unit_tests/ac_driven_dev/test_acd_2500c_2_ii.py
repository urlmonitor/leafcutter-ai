"""
MODULE: unit_tests/ac_driven_dev/test_acd_2500c_2_ii.py
COVERS: ACD-2500c-2-ii
GOAL: Red-first specification of ticket 09: the shared support module of the test-design stage
    tests (unit_tests/ac_driven_dev/test_design_stage/_design_stage_support.py) passes the type
    checker with no finding, and the label table it builds keeps its entries.
DESIGN: the type checker is run as the CI typecheck job runs it (mypy --ignore-missing-imports
    --explicit-package-bases --no-error-summary), from the repo root, with a tmp cache dir. This
    file lives in unit_tests/ac_driven_dev/, NOT in test_design_stage/, so it does not change
    that suite's collected count, which the ticket records before and after.
HONEST LIMIT: the label-table test guards the value the annotation types; the unchanged suite
    run and the recorded collected counts are the rest of the proof.
RED STATE: the type checker test fails on its assertion (line 101: Need type annotation for
    "table" [var-annotated]); the label-table test pins today's table and is green at baseline
    by design.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SUPPORT_REL = "unit_tests/ac_driven_dev/test_design_stage/_design_stage_support.py"
SUPPORT_DIR = REPO / "unit_tests" / "ac_driven_dev" / "test_design_stage"
TECHNICAL_ROUTE_LABELS = {
    "stage-0-triage", "stage-itpo-author", "branch-check", "commit-stage-output",
    "peek-pause-record", "read-pause-record", "pause-persist-verify",
    "clear-pause-record", "clear-pause-record-verify",
    "design-prepass", "stage-test-design-author", "rule-check-test-design", "approval-holds",
}


def test_design_stage_support_has_no_type_checker_finding(tmp_path):
    # covers: ACD-2500c-2-ii
    # angle: reachability
    """Entry point: the type checker CLI, run as the CI typecheck job runs it, over the support
    file. It exits 0 and no output line names the file (in particular no [var-annotated] line).
    Red today: line 101 reports Need type annotation for "table" [var-annotated]."""
    pytest.importorskip("mypy")
    proc = subprocess.run(
        [sys.executable, "-m", "mypy", "--ignore-missing-imports", "--explicit-package-bases",
         "--no-error-summary", "--cache-dir", str(tmp_path / "mypy-cache"), SUPPORT_REL],
        capture_output=True, text=True, encoding="utf-8", timeout=300, cwd=str(REPO),
    )
    output = (proc.stdout + proc.stderr).replace("\\", "/")
    assert "[var-annotated]" not in output, output
    assert [line for line in output.splitlines() if "_design_stage_support.py" in line] == [], output
    assert proc.returncode == 0, output


def test_design_stage_label_table_keeps_its_entries():
    # covers: ACD-2500c-2-ii
    # angle: criterion
    """labels(prepass, holds) with sentinel objects returns a dict with exactly the 13 labels the
    technical route dispatches; design-prepass and approval-holds are the passed objects;
    stage-test-design-author equals designer_reply() and rule-check-test-design equals
    check_reply() when none are given; given designer and check replies are used as passed; a
    keyword override replaces an existing label and adds a new one. Imports only (no workflow
    run). Wrong versions this catches: an annotation written by changing the value (a dropped,
    renamed or defaulted label, or a copy instead of the passed object)."""
    if str(SUPPORT_DIR) not in sys.path:
        sys.path.insert(0, str(SUPPORT_DIR))
    import _design_stage_support as support

    prepass, holds = object(), object()
    table = support.labels(prepass, holds)
    assert isinstance(table, dict)
    assert set(table) == TECHNICAL_ROUTE_LABELS and len(table) == 13, sorted(table)
    assert table["design-prepass"] is prepass and table["approval-holds"] is holds
    assert table["stage-test-design-author"] == support.designer_reply()
    assert table["rule-check-test-design"] == support.check_reply()

    designer, check = object(), object()
    given = support.labels(prepass, holds, designer=designer, check=check)
    assert given["stage-test-design-author"] is designer and given["rule-check-test-design"] is check

    marker = object()
    overridden = support.labels(prepass, holds, **{"branch-check": marker, "extra-label": marker})
    assert overridden["branch-check"] is marker and overridden["extra-label"] is marker
    assert len(overridden) == 14
