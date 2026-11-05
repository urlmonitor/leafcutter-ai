"""
MODULE: unit_tests/_shared/test_bo4500b_3_i_hostile_replies.py
GOAL: BO-4500b-3-i -- a reply the block cannot read, or whose envelope disagrees with its
    commit answer, is reported and never continued.
"""

from __future__ import annotations

import json

import _bo4500b3_support as S


def _hostile_cases():
    committed = S.commit_answer("committed")
    hook_failed = S.commit_answer("hook_failed", "check_failed", hook_name="ruff", failing_files=["a.py"])
    return {
        "a_prose": "Committed successfully, all good.",
        "b_no_commit_answer": {"status": "ok"},
        "c_string_commit_answer": {"status": "ok", "commit_answer": "committed", "earlier_answers": []},
        "d_empty": "",
        "e_ok_envelope_hook_failed": {"status": "ok", "commit_answer": hook_failed, "earlier_answers": []},
        "f_blocker_envelope_committed": {"status": "blocker", "commit_answer": committed, "earlier_answers": []},
    }


def test_unreadable_or_contradicting_replies_are_all_report(tmp_path, monkeypatch):
    # covers: BO-4500b-3-i
    # angle: discrimination
    """Six hostile replies each decide report; none continue/retry/engage; nothing raises.

    Wrong versions caught: read prose containing 'committed' as ok; trust commit_answer alone
    (case f is continue); trust the envelope status alone (case e is continue).
    """
    text = S.render_block(tmp_path, monkeypatch).text
    seen = {}
    for name, reply in _hostile_cases().items():
        d = S.decide(text, reply, S.fresh_history())
        seen[name] = d.get("decision")
    assert seen == {name: "report" for name in _hostile_cases()}, seen


def test_report_quotes_received_bounded_to_2kb(tmp_path, monkeypatch):
    # covers: BO-4500b-3-i
    # angle: criterion
    """Report carries received == reply text; over 2048 bytes it is cut to <= 2048 and marked."""
    text = S.render_block(tmp_path, monkeypatch).text
    short = "Committed successfully, all good."
    d = S.decide(text, short, S.fresh_history())
    assert d.get("decision") == "report", d
    assert d.get("received") == short, d
    assert d.get("truncated") is False, d
    big = "x" * 5000
    d = S.decide(text, big, S.fresh_history())
    assert d.get("decision") == "report", d
    received = d.get("received")
    assert isinstance(received, str) and 0 < len(received.encode("utf-8")) <= 2048, d
    assert d.get("truncated") is True, d


def test_envelope_disagreement_report_names_both_statuses(tmp_path, monkeypatch):
    # covers: BO-4500b-3-i
    # angle: criterion
    """(e) and (f): the report names the envelope status and the commit_answer status."""
    text = S.render_block(tmp_path, monkeypatch).text
    cases = _hostile_cases()
    for key, env_status, ans_status in (("e_ok_envelope_hook_failed", "ok", "hook_failed"),
                                        ("f_blocker_envelope_committed", "blocker", "committed")):
        d = S.decide(text, cases[key], S.fresh_history())
        assert d.get("decision") == "report", (key, d)
        assert d.get("envelope_status") == env_status, (key, d)
        assert d.get("answer_status") == ans_status, (key, d)
        blob = json.dumps(d)
        assert env_status in blob and ans_status in blob, (key, d)


def test_hostile_reply_handling_is_reachable_through_the_install(tmp_path, monkeypatch):
    # covers: BO-4500b-3-i
    # angle: reachability
    """Real install, installed text, empty reply: decides report."""
    inst = S.render_block(tmp_path, monkeypatch)
    assert inst.error is None, inst.error
    assert inst.text is not None and S.START in inst.text
    d = S.decide(inst.text, "", S.fresh_history())
    assert d.get("decision") == "report", d
