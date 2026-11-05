"""
MODULE: unit_tests/_shared/test_bo4500b_3_iii_engage_once.py
GOAL: BO-4500b-3-iii -- a specialist is engaged at most once per commit, and the re-offer carries
    the identical path list and message file.
"""

from __future__ import annotations

import json

import _bo4500b3_support as S

EXTRA = "scripts/x_helpers.py"


def _after_specialist(text, report):
    d1 = S.decide(text, S.envelope(S.hook_failed_with_handoff()), S.fresh_history())
    assert d1.get("decision") == "engage", d1
    hist = dict(d1.get("history") or {}, specialist_reply=report)
    return d1, hist


def test_handoff_decides_engage_named_specialist(tmp_path, monkeypatch):
    # covers: BO-4500b-3-iii
    # angle: criterion
    """hook_failed carrying a handoff naming the specialist decides engage with that name."""
    text = S.render_block(tmp_path, monkeypatch).text
    for target in (S.SPECIALIST, "some-other-specialist"):
        d = S.decide(text, S.envelope(S.hook_failed_with_handoff(target)), S.fresh_history())
        assert d.get("decision") == "engage" and d.get("specialist") == target, d
        assert (d.get("history") or {}).get("specialist_engaged") is True, d


def test_reoffer_excludes_specialist_reported_extra_file(tmp_path, monkeypatch):
    # covers: BO-4500b-3-iii
    # angle: discrimination
    """Specialist reports it also changed x_helpers.py; the re-offer is exactly the first list.

    Wrong versions caught: re-derive the list from what changed; add the reported file.
    """
    text = S.render_block(tmp_path, monkeypatch).text
    _, hist = _after_specialist(text, {"status": "ok", "changed_files": [EXTRA]})
    d = S.decide(text, None, hist)
    assert d.get("decision") == "retry", d
    assert d.get("paths") == S.FIRST_PATHS and EXTRA not in (d.get("paths") or []), d
    assert d.get("message_file") == S.FIRST_MESSAGE_FILE, d


def test_repeated_handoff_reports_both_answers_in_order(tmp_path, monkeypatch):
    # covers: BO-4500b-3-iii
    # angle: criterion
    """Second hook_failed handoff after the re-offer: report naming both answers in order."""
    text = S.render_block(tmp_path, monkeypatch).text
    first = S.hook_failed_with_handoff()
    first["reason"] = "first failure"
    second = S.hook_failed_with_handoff()
    second["reason"] = "second failure"
    d1 = S.decide(text, S.envelope(first), S.fresh_history())
    hist = dict(d1.get("history") or {}, specialist_reply={"status": "ok", "changed_files": []})
    d2 = S.decide(text, None, hist)
    d3 = S.decide(text, S.envelope(second), d2.get("history") or hist)
    assert d3.get("decision") == "report", d3
    assert [a.get("reason") for a in d3.get("answers") or []] == ["first failure", "second failure"], d3


def test_specialist_is_never_engaged_twice_per_commit(tmp_path, monkeypatch):
    # covers: BO-4500b-3-iii
    # angle: discrimination
    """With specialist_engaged true no decision is engage, whatever the name or ceiling.

    Wrong versions caught: loop on repeated handoffs; engage a different specialist the 2nd time.
    """
    for ceiling in (0, 3, 9):
        def mutate(cfg, n=ceiling):
            cfg["max_transient_retries"] = n
        text = S.render_block(tmp_path / f"c{ceiling}", monkeypatch, mutate).text
        for target in (S.SPECIALIST, "a-different-specialist"):
            hist = dict(S.fresh_history(), specialist_engaged=True, specialist=S.SPECIALIST)
            d = S.decide(text, S.envelope(S.hook_failed_with_handoff(target)), hist)
            assert d.get("decision") == "report", (ceiling, target, d)


def test_declining_or_unreadable_specialist_reply_is_reported_with_quote(tmp_path, monkeypatch):
    # covers: BO-4500b-3-iii
    # angle: criterion
    """A declining and an unreadable specialist reply each report, naming it and quoting <= 2 KB."""
    text = S.render_block(tmp_path, monkeypatch).text
    declined = {"status": "blocker", "message": "I decline to refactor this"}
    unreadable = "p" * 5000
    for report in (declined, unreadable):
        _, hist = _after_specialist(text, report)
        d = S.decide(text, None, hist)
        assert d.get("decision") == "report", d
        assert d.get("specialist") == S.SPECIALIST, d
        received = d.get("received")
        assert isinstance(received, str) and 0 < len(received.encode("utf-8")) <= 2048, d
        if isinstance(report, dict):
            assert "decline" in received, d
        else:
            assert d.get("truncated") is True, d
        assert S.SPECIALIST in json.dumps(d)


def test_no_reoffer_after_specialist_declined(tmp_path, monkeypatch):
    # covers: BO-4500b-3-iii
    # angle: criterion
    """The declined-case report carries no paths/message_file and is not retry or engage."""
    text = S.render_block(tmp_path, monkeypatch).text
    _, hist = _after_specialist(text, {"status": "blocker", "message": "declined"})
    d = S.decide(text, None, hist)
    assert d.get("decision") == "report", d
    assert not d.get("paths") and not d.get("message_file"), d


def test_transient_after_reoffer_retries_against_same_ceiling_without_engagement(tmp_path, monkeypatch):
    # covers: BO-4500b-3-iii
    # angle: criterion
    """step_index_locked after the re-offer: retry, identical list, shared counter, no engage.

    Ceiling 1: a fresh counter would let two retries through; the shared counter reports the
    second transient answer.
    """
    def mutate(cfg):
        cfg["max_transient_retries"] = 1
    text = S.render_block(tmp_path, monkeypatch, mutate).text
    _, hist = _after_specialist(text, {"status": "ok", "changed_files": [EXTRA]})
    reoffer = S.decide(text, None, hist)
    assert reoffer.get("decision") == "retry", reoffer
    locked = S.envelope(S.commit_answer("refused", "step_index_locked"))
    d1 = S.decide(text, locked, reoffer.get("history") or hist)
    assert d1.get("decision") == "retry", d1
    assert d1.get("paths") == S.FIRST_PATHS and d1.get("message_file") == S.FIRST_MESSAGE_FILE, d1
    assert (d1.get("history") or {}).get("transient_retries_used") == 1, d1
    d2 = S.decide(text, locked, d1.get("history") or hist)
    assert d2.get("decision") == "report", d2


def test_engage_reoffer_loop_is_reachable_through_the_install(tmp_path, monkeypatch):
    # covers: BO-4500b-3-iii
    # angle: reachability
    """Real install, installed text, hook_failed handoff reply: decides engage."""
    inst = S.render_block(tmp_path, monkeypatch)
    assert inst.error is None, inst.error
    d = S.decide(inst.text, S.envelope(S.hook_failed_with_handoff()), S.fresh_history())
    assert d.get("decision") == "engage" and d.get("specialist") == S.SPECIALIST, d
