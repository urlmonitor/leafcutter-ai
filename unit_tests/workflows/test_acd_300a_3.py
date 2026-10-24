"""
MODULE: unit_tests/workflows/test_acd_300a_3.py
COVERS: ACD-300a-3
GOAL: Red-first specification of the covered route of /plan-feature: the triage reply "covered" pauses at
    covered-route-gate before any authoring, the paused question lists every covering AC id with its title
    and carries the exact message of the AC, cancel authors nothing, amend runs the technical route on the
    covering records, force (answer or --force argument) runs the full strategic pipeline, and an unreadable
    answer is never read as cancel.
ARCHITECTURE: The REAL plan-feature.js under run_workflow_under_e2 (_acd_300a_support.py). The workflow body
    has no file access, so the titles reach it through ONE shell-agent dispatch labelled
    `read-covering-ac-titles` whose reply is {output: JSON object of id to title, exit_code}; the design
    fixes that label for the implementer. The question the person is shown is the terminal question.prompt
    and the prompt of the persisted pause record (the headless gate never calls its live closure).
RED STATE: the covered gate's paused question is the generic "requires a human decision" text (no ids, no
    titles, no message); amend does not tell the planner which records to amend; an unreadable answer falls
    to force; --force keeps route covered. Cancel, force-answer and the pause itself are green-today guards.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_300a_support import (  # noqa: E402
    COVERED_GATE, COVERING, TITLES, author_calls, authoring_labels, covered_pause_record, covered_resume,
    fresh_table, full_table, names, pause_records, run, terminal, triage,
)

THIRD = "ACD-9103"
IDS3 = [*COVERING, THIRD]
MESSAGE = (
    "These existing ACs already cover your request. Would you like to proceed anyway (force new), "
    "amend an existing AC, or cancel?"
)
TITLE_LABEL = "read-covering-ac-titles"


def _titles_reply(titles: dict | None = None, exit_code: int = 0) -> dict:
    return {"output": json.dumps(TITLES if titles is None else titles) if exit_code == 0 else "", "exit_code": exit_code}


def _covered_run(existing=COVERING, titles=None, **overrides):
    table = fresh_table(triage("covered", existing), **{TITLE_LABEL: titles or _titles_reply()}, **overrides)
    return run(table)


def _resumed_table(record: dict, **extra) -> dict:
    """A covered triage with a durable covered-route-gate pause record, the title read scripted."""
    return fresh_table(triage("covered", COVERING), **{TITLE_LABEL: _titles_reply(), "peek-pause-record": record, "read-pause-record": record, **extra})


def _shown(result) -> list[str]:
    """The question text the person is shown: the terminal question prompt and the persisted record's."""
    asked = str((terminal(result).get("question") or {}).get("prompt", ""))
    persisted = str((covered_pause_record(result).get("question") or {}).get("prompt", ""))
    return [asked, persisted]


def _owner_of(text: str, title: str, ids: list[str]) -> str:
    """The id whose occurrence in `text` lies nearest to the title's occurrence."""
    at = text.index(title)
    spots = [(abs(text.index(i) - at), i) for i in ids if i in text]
    return min(spots)[1]


def _no_authoring(result) -> None:
    assert authoring_labels(result) == [], f"authoring was dispatched: {names(result)}"


def test_acd_300a_3_covered_triage_pauses_at_covered_gate_before_any_authoring():
    # covers: ACD-300a-3
    # angle: reachability
    """Fresh run, triage covered with two ids: the run pauses at covered-route-gate, a pause-persist record
    names that gate, and no pt-classify, pt author, stage author or test-design dispatch happens."""
    result = _covered_run()

    outcome = terminal(result)
    assert (outcome.get("status"), outcome.get("gate_id")) == ("paused_awaiting_input", COVERED_GATE), outcome
    assert covered_pause_record(result)["gate_id"] == COVERED_GATE
    _no_authoring(result)


def test_acd_300a_3_gate_question_lists_each_covering_id_with_its_title():
    # covers: ACD-300a-3
    # angle: discrimination
    """Three covering ids; read-covering-ac-titles knows two of them. The paused question shows ACD-9101 next
    to its own title and ACD-9102 next to its own title, and still lists ACD-9103 by id.

    Wrong versions caught: only the ids are shown, as today; an id with no readable title is dropped; each
    title is shown next to the wrong id.
    """
    result = _covered_run(IDS3)

    for text in _shown(result):
        for cid in IDS3:
            assert cid in text, f"{cid} is not listed: {text[:600]!r}"
        for cid in COVERING:
            assert TITLES[cid] in text, f"the title of {cid} is not shown: {text[:600]!r}"
            assert _owner_of(text, TITLES[cid], IDS3) == cid, f"title of {cid} sits next to another id: {text[:600]!r}"


def test_acd_300a_3_failed_title_read_still_lists_every_id():
    # covers: ACD-300a-3
    # angle: boundary
    """read-covering-ac-titles replies exit_code 1 with empty output: the run still pauses at
    covered-route-gate and the paused question lists ACD-9101, ACD-9102 and ACD-9103 by id."""
    result = _covered_run(IDS3, titles=_titles_reply(exit_code=1))

    assert terminal(result).get("gate_id") == COVERED_GATE, terminal(result)
    for text in _shown(result):
        assert [cid for cid in IDS3 if cid not in text] == [], f"ids missing from: {text[:600]!r}"


def test_acd_300a_3_gate_question_shows_exact_message():
    # covers: ACD-300a-3
    # angle: discrimination
    """The paused question contains the AC's sentence character for character (terminal and persisted
    record), and the options stay cancel, amend and force.

    Wrong versions caught: the paused question is still the generic "Interactive gate ... requires a human
    decision" text; the sentence is put only into the live gate instructions, which resolveGate never
    dispatches.
    """
    result = _covered_run()

    for text in _shown(result):
        assert MESSAGE in text, text[:600]
    assert terminal(result)["question"]["options"] == ["cancel", "amend", "force"], terminal(result)
    assert covered_pause_record(result)["question"]["options"] == ["cancel", "amend", "force"]


def test_acd_300a_3_cancel_invokes_no_authoring_agent():
    # covers: ACD-300a-3
    # angle: criterion
    """Resume of covered-route-gate with a person's cancel: status ok with covered_by both ids, and no
    pt-classify, pt author, stage author, design-prepass or test-design dispatch happens."""
    record, args = covered_resume("cancel")
    result = run(_resumed_table(record), args)

    outcome = terminal(result)
    assert outcome.get("status") == "ok" and outcome.get("covered_by") == COVERING, outcome
    _no_authoring(result)


def test_acd_300a_3_unreadable_answer_is_not_read_as_cancel():
    # covers: ACD-300a-3
    # angle: discrimination
    """Resume with an action that is none of cancel, amend or force: the run stays paused at
    covered-route-gate, never returns status ok with covered_by, and dispatches no authoring agent.

    Wrong version caught: a missing or unreadable answer falls back to cancel (or to force).
    """
    record, unknown = covered_resume("maybe-later")
    _, missing = covered_resume("cancel")
    del missing["resume_answer"]["action"]
    for args in (unknown, missing):
        result = run(_resumed_table(record), args)

        outcome = terminal(result)
        assert (outcome.get("status"), outcome.get("gate_id")) == ("paused_awaiting_input", COVERED_GATE), outcome
        assert "covered_by" not in outcome, outcome
        _no_authoring(result)


def test_acd_300a_3_amend_runs_technical_pipeline_on_covering_acs(tmp_path):
    # covers: ACD-300a-3
    # angle: discrimination
    """Resume with amend: the stage authors are stage-itpo-author then stage-test-design-author, the run
    pauses at final-gate, no PO or BA author runs, and the it-po instructions name ACD-9101 and ACD-9102 as
    the records to amend.

    Wrong versions caught: the it-po stage is not told which records to amend, as today; amend dispatches
    the product-owner or business-analyst stage.
    """
    record, args = covered_resume("amend")
    table = full_table(tmp_path, triage("covered", COVERING), **{TITLE_LABEL: _titles_reply(), "peek-pause-record": record, "read-pause-record": record})
    result = run(table, args)

    labels = [c.label for c in author_calls(result)]
    assert labels == ["stage-itpo-author", "stage-test-design-author"], names(result)
    assert terminal(result).get("gate_id") == "final-gate", terminal(result)
    prompt = author_calls(result)[0].prompt
    assert [cid for cid in COVERING if cid not in prompt] == [], prompt[-500:]


def test_acd_300a_3_force_answer_runs_full_pipeline():
    # covers: ACD-300a-3
    # angle: criterion
    """Resume with force: the first stage author is stage-po-author with route "strategic" in its
    instructions, and the run pauses at gate-po (the order beyond that gate is proven by ACD-300a-1)."""
    record, args = covered_resume("force")
    result = run(_resumed_table(record), args)

    authors = author_calls(result)
    assert [c.label for c in authors][:1] == ["stage-po-author"], names(result)
    assert 'route: "strategic"' in authors[0].prompt, authors[0].prompt[-400:]
    assert terminal(result).get("gate_id") == "gate-po", terminal(result)


def test_acd_300a_3_force_argument_routes_covered_request_as_strategic():
    # covers: ACD-300a-3
    # angle: discrimination
    """Fresh run with --force ending args.userInput and triage covered: no pause names covered-route-gate,
    the first stage author is stage-po-author with route "strategic", and no stage-itpo-author runs before it.

    Wrong version caught: with --force a covered request keeps route covered and runs only stage-itpo-author,
    as today.
    """
    table = fresh_table(triage("covered", COVERING), **{TITLE_LABEL: _titles_reply()})
    result = run(table, user_input="build the widget export --force")

    assert [r for r in pause_records(result) if r.get("gate_id") == COVERED_GATE] == [], names(result)
    authors = author_calls(result)
    assert authors and authors[0].label == "stage-po-author", names(result)
    assert 'route: "strategic"' in authors[0].prompt, authors[0].prompt[-400:]
