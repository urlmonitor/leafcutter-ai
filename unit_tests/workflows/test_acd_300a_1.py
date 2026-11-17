"""
MODULE: unit_tests/workflows/test_acd_300a_1.py
COVERS: ACD-300a-1
GOAL: Red-first specification that the Haiku triage classifies a request that matches no L1 as "strategic"
    for the three signals the AC names, and that a strategic route runs the full pipeline: product owner,
    business analyst, technical planner, test designer.
ARCHITECTURE: Template tests read the real templates/agents/ac-triage.md. Workflow tests drive the REAL
    plan-feature.js through run_workflow_under_e2 (_acd_300a_support.py; crash-resume uses the label table
    of file_findings/_handback_support.py).
RED STATE: the strategic rule names only the missing L1 parent; the rationale rule does not say to name the
    deciding signal. The two workflow tests are green-today guards of the dispatch order.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_300a_support import (  # noqa: E402
    author_calls, authoring_labels, calls, committed_stages, fresh_table, full_table, names, position_of,
    run, section, template_parts, terminal, triage,
)


def _strategic_rule(body: str) -> str:
    row = next(line for line in body.splitlines() if line.startswith("| `strategic`"))
    return row + "\n" + section(body, "**Default**")


def test_acd_300a_1_triage_template_defaults_unmatched_request_to_strategic():
    # covers: ACD-300a-1
    # angle: criterion
    """The real ac-triage.md pins model haiku, tools Read and Bash only, an empty spawn_allowlist, and checks
    covered, then the L1 match, then the technical constraint, and only then defaults to route strategic."""
    front, body = template_parts()

    assert front["model"] == "haiku", front["model"]
    assert [t.strip() for t in str(front["tools"]).split(",")] == ["Read", "Bash"], front["tools"]
    assert front["spawn_allowlist"] == [], front["spawn_allowlist"]
    marks = [body.index(m) for m in ("**Covered check**", "**L1 match check**", "**Technical constraint check**", "**Default**")]
    assert marks == sorted(marks), f"decision steps are out of order: {marks}"
    default = section(body, "**Default**")
    assert re.search(r"route:\s*`strategic`", default), default[:300]


def test_acd_300a_1_strategic_rule_names_all_three_signals():
    # covers: ACD-300a-1
    # angle: criterion
    """The strategic rule names (1) no matching L1 parent, (2) a user-observable outcome or new system
    capability, (3) no reference to a specific existing component or AC; the rationale field rule tells the
    agent to name the signal that decided the route. Red today: only the missing L1 parent is named."""
    _, body = template_parts()
    rule = _strategic_rule(body).lower()

    assert re.search(r"no matching l1", rule), rule
    assert re.search(r"user[- ]observable", rule) and re.search(r"new (system )?capabilit", rule), rule
    assert re.search(r"specific (existing )?(component|ac)\b", rule), rule
    rationale = next(line for line in body.splitlines() if line.startswith("- `rationale`"))
    assert "signal" in rationale.lower(), rationale


def test_acd_300a_1_strategic_route_dispatches_product_owner_first():
    # covers: ACD-300a-1
    # angle: reachability
    """Fresh run, triage strategic, pt-classify outcome none: the first stage author is stage-po-author with
    route "strategic" in its instructions, no other stage author runs, and the run pauses at gate-po."""
    result = run(fresh_table(triage("strategic")))

    authors = author_calls(result)
    assert [c.label for c in authors] == ["stage-po-author"], names(result)
    assert 'route: "strategic"' in authors[0].prompt, authors[0].prompt[-400:]
    outcome = terminal(result)
    assert (outcome.get("status"), outcome.get("gate_id")) == ("paused_awaiting_input", "gate-po"), outcome


def test_acd_300a_1_strategic_route_runs_ba_itpo_then_test_designer(tmp_path):
    # covers: ACD-300a-1
    # angle: criterion
    """Crash-resume on a strategic route with the PO and BA commits present: exactly two resume-log
    dispatches precede stage-itpo-author, stage-test-design-author follows it, no PO or BA author runs, and
    the run pauses at final-gate. With the test above this shows the order PO, BA, planner, test designer."""
    table = full_table(tmp_path, triage("strategic"), **committed_stages("PO", "BA"))
    result = run(table)

    itpo = position_of(result, "stage-itpo-author")
    assert names(result)[:itpo].count("resume-log") == 2, names(result)
    assert position_of(result, "stage-test-design-author") > itpo, names(result)
    assert [c for c in authoring_labels(result) if c in ("stage-po-author", "stage-ba-author")] == [], names(result)
    assert calls(result, "stage-itpo-author"), names(result)
    outcome = terminal(result)
    assert (outcome.get("status"), outcome.get("gate_id")) == ("paused_awaiting_input", "final-gate"), outcome
