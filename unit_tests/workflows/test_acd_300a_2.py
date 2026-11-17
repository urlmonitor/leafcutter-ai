"""
MODULE: unit_tests/workflows/test_acd_300a_2.py
COVERS: ACD-300a-2
GOAL: Red-first specification that the Haiku triage classifies a request that adds scenarios to an existing
    L1 feature as "behavioral" with that L1 as parent, and that the behavioral route skips the product owner:
    business analyst, technical planner, test designer, with the parent L1 id handed to the business analyst.
ARCHITECTURE: Template tests read the real templates/agents/ac-triage.md. Workflow tests drive the REAL
    plan-feature.js through run_workflow_under_e2 (_acd_300a_support.py; crash-resume uses the label table
    of file_findings/_handback_support.py).
RED STATE: the behavioral rule mentions neither edge cases nor the not-a-new-capability signal. The four
    workflow and ordering tests are green-today guards.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_300a_support import (  # noqa: E402
    PARENT_L1, author_calls, authoring_labels, committed_stages, fresh_table, full_table, names, position_of, run,
    section, template_parts, terminal, triage,
)


def _fresh_behavioral():
    return run(fresh_table(triage("behavioral", parent=PARENT_L1)))


def test_acd_300a_2_triage_template_routes_l1_match_to_behavioral():
    # covers: ACD-300a-2
    # angle: criterion
    """The L1 match check comes after the covered check and before the technical and default checks,
    classifies a matching L1 as route behavioral, and sets parent_l1_id to the matched L1 id."""
    _, body = template_parts()

    marks = [body.index(m) for m in ("**Covered check**", "**L1 match check**", "**Technical constraint check**", "**Default**")]
    assert marks == sorted(marks), f"decision steps are out of order: {marks}"
    step = section(body, "**L1 match check**", "**Technical constraint check**")
    assert re.search(r"route:\s*`behavioral`", step), step
    assert re.search(r"`parent_l1_id`[^.]*matched L1", step), step


def test_acd_300a_2_behavioral_rule_names_both_signals():
    # covers: ACD-300a-2
    # angle: criterion
    """The behavioral rule names a matching L1 parent in the AC store and a request that adds scenarios or
    edge cases to existing behaviour rather than a new capability. Red today: neither edge cases nor the
    not-a-new-capability signal is named."""
    _, body = template_parts()
    row = next(line for line in body.splitlines() if line.startswith("| `behavioral`"))
    rule = (row + "\n" + section(body, "**L1 match check**", "**Technical constraint check**")).lower()

    assert "matching l1" in rule, rule
    assert re.search(r"edge[- ]cases?", rule), rule
    assert re.search(r"(rather than|not) (a )?new capabilit", rule), rule


def test_acd_300a_2_behavioral_route_starts_with_business_analyst():
    # covers: ACD-300a-2
    # angle: reachability
    """Fresh run, triage behavioral with parent_l1_id ACD-9100: the first stage author is stage-ba-author, no
    stage-po-author is dispatched, and the run pauses at gate-ba."""
    result = _fresh_behavioral()

    labels = [c.label for c in author_calls(result)]
    assert labels == ["stage-ba-author"], names(result)
    outcome = terminal(result)
    assert (outcome.get("status"), outcome.get("gate_id")) == ("paused_awaiting_input", "gate-ba"), outcome


def test_acd_300a_2_behavioral_route_runs_itpo_then_test_designer(tmp_path):
    # covers: ACD-300a-2
    # angle: criterion
    """Crash-resume on a behavioral route with the BA commit present: exactly one resume-log dispatch
    precedes stage-itpo-author, stage-test-design-author follows it, no stage-po-author is dispatched, and
    the run pauses at final-gate."""
    table = full_table(tmp_path, triage("behavioral", parent=PARENT_L1), **committed_stages("BA"))
    result = run(table)

    itpo = position_of(result, "stage-itpo-author")
    assert names(result)[:itpo].count("resume-log") == 1, names(result)
    assert position_of(result, "stage-test-design-author") > itpo, names(result)
    assert "stage-po-author" not in authoring_labels(result), names(result)
    outcome = terminal(result)
    assert (outcome.get("status"), outcome.get("gate_id")) == ("paused_awaiting_input", "final-gate"), outcome


def test_acd_300a_2_parent_l1_id_reaches_business_analyst():
    # covers: ACD-300a-2
    # angle: criterion
    """The stage-ba-author instructions carry the line parent_l1_id: "ACD-9100" exactly as the triage reply
    gave it, never null."""
    result = _fresh_behavioral()

    prompt = author_calls(result)[0].prompt
    assert f'parent_l1_id: "{PARENT_L1}"' in prompt, prompt[-400:]
    assert "parent_l1_id: null" not in prompt, prompt[-400:]
