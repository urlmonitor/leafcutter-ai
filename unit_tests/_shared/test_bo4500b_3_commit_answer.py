"""
MODULE: unit_tests/_shared/test_bo4500b_3_commit_answer.py
GOAL: BO-4500b-3 -- the COMMIT-ANSWER block turns every commit reply into exactly one decision,
    proven on the block's own installed text (node, no engine, no route).
RED TODAY: templates/workflows-js/_shared/commit-answer.js does not exist, so the installed marker
    pair is empty and every decision is ``null`` with an error -- an assertion red.
"""

from __future__ import annotations

import re

import _bo4500b3_support as S


def _block(tmp_path, monkeypatch):
    return S.render_block(tmp_path, monkeypatch).text


def test_committed_reply_decides_continue(tmp_path, monkeypatch):
    # covers: BO-4500b-3
    # angle: criterion
    """AC (a): committed on a first attempt, ceiling 3, decides continue."""
    d = S.decide(_block(tmp_path, monkeypatch), S.envelope(S.commit_answer("committed")), S.fresh_history())
    assert d.get("decision") == "continue", d


def test_policy_refusal_decides_stop_without_further_attempt(tmp_path, monkeypatch):
    # covers: BO-4500b-3
    # angle: criterion
    """AC (b): refused/policy_protected_branch decides stop; no retry, engage or re-offer."""
    ca = S.commit_answer("refused", "policy_protected_branch", reason="on main")
    d = S.decide(_block(tmp_path, monkeypatch), S.envelope(ca), S.fresh_history())
    assert d.get("decision") == "stop", d
    assert d.get("specialist") in (None, ""), d
    assert not d.get("paths"), d


def test_step_refusal_decides_retry_with_identical_paths_and_message_file(tmp_path, monkeypatch):
    # covers: BO-4500b-3
    # angle: criterion
    """AC (c): refused/step_index_locked decides retry re-offering the first attempt's list."""
    ca = S.commit_answer("refused", "step_index_locked", reason="index.lock")
    d = S.decide(_block(tmp_path, monkeypatch), S.envelope(ca), S.fresh_history())
    assert d.get("decision") == "retry", d
    assert d.get("paths") == S.FIRST_PATHS, d
    assert d.get("message_file") == S.FIRST_MESSAGE_FILE, d


def test_hook_failed_with_handoff_decides_engage_then_reoffers_identical(tmp_path, monkeypatch):
    # covers: BO-4500b-3
    # angle: criterion
    """AC (d): handoff naming the specialist decides engage verbatim, then re-offers the first list."""
    text = _block(tmp_path, monkeypatch)
    d1 = S.decide(text, S.envelope(S.hook_failed_with_handoff()), S.fresh_history())
    assert d1.get("decision") == "engage", d1
    assert d1.get("specialist") == S.SPECIALIST, d1
    hist = dict(d1.get("history") or {}, specialist_reply={"status": "ok", "changed_files": ["scripts/x.py"]})
    d2 = S.decide(text, None, hist)
    assert d2.get("decision") == "retry", d2
    assert d2.get("paths") == S.FIRST_PATHS, d2
    assert d2.get("message_file") == S.FIRST_MESSAGE_FILE, d2


def test_check_failed_and_nothing_to_commit_decide_report(tmp_path, monkeypatch):
    # covers: BO-4500b-3
    # angle: criterion
    """AC (e),(f): hook_failed without handoff and nothing_to_commit each decide report."""
    text = _block(tmp_path, monkeypatch)
    e = S.commit_answer("hook_failed", "check_failed", reason="lint", hook_name="ruff", failing_files=["a.py"])
    f = S.commit_answer("nothing_to_commit", "nothing_changed", reason="clean tree")
    for ca in (e, f):
        d = S.decide(text, S.envelope(ca), S.fresh_history())
        assert d.get("decision") == "report", (ca["status"], d)


def test_stop_and_report_carry_reply_fields_unchanged(tmp_path, monkeypatch):
    # covers: BO-4500b-3
    # angle: criterion
    """AC: every stop and report decision carries status, reason_code, reason, hook_name,
    failing_files exactly as the reply gave them."""
    text = _block(tmp_path, monkeypatch)
    cases = [
        (S.commit_answer("refused", "policy_protected_branch", reason="on main branch 'main'"), "stop"),
        (S.commit_answer("hook_failed", "check_failed", reason="r-e", hook_name="check-x",
                         failing_files=["p/q.py", "r/s.py"]), "report"),
        (S.commit_answer("nothing_to_commit", "nothing_changed", reason="nothing", hook_name=None,
                         failing_files=[]), "report"),
    ]
    for ca, want in cases:
        d = S.decide(text, S.envelope(ca), S.fresh_history())
        assert d.get("decision") == want, (ca["status"], d)
        for key in ("status", "reason_code", "reason", "hook_name", "failing_files"):
            assert d.get(key) == ca[key], (key, ca["status"], d.get(key), ca[key])


def test_regression_of_each_moved_known_issue_runs_against_block_decision(tmp_path, monkeypatch):
    # covers: BO-4500b-3
    # angle: criterion
    """AC: the known-issue regressions of the copies the block was taken from run on the block.

    Moved regressions: (1) fast-lane halt-on-non-ok reading -- prose that says 'committed' must
    not continue; (2) /commit engage loop -- a repeated handoff must not loop; (3) /commit
    re-offer -- the list is never re-derived. The source also names the copies and KIs it came
    from (provenance), so the regressions are traceable.
    """
    text = _block(tmp_path, monkeypatch)
    prose = S.decide(text, "Committed successfully, all good.", S.fresh_history())
    assert prose.get("decision") == "report", prose

    d1 = S.decide(text, S.envelope(S.hook_failed_with_handoff()), S.fresh_history())
    assert d1.get("decision") == "engage", d1
    hist = dict(d1.get("history") or {}, specialist_reply={"status": "ok", "changed_files": ["scripts/x_helpers.py"]})
    d2 = S.decide(text, None, hist)
    assert d2.get("paths") == S.FIRST_PATHS, d2
    d3 = S.decide(text, S.envelope(S.hook_failed_with_handoff()), d2.get("history") or hist)
    assert d3.get("decision") == "report", d3

    assert S.BLOCK_SOURCE.is_file(), "block source missing"
    src = S.BLOCK_SOURCE.read_text(encoding="utf-8")
    assert "commit.js" in src and "fast-lane-ship.js" in src, "provenance must name both source copies"
    cited = set(re.findall(r"KI-BO-[0-9A-Za-z-]+", src))
    expected = {"KI-BO-007", "KI-BO-20260914-autofix-re-dispatch-is-specified-at-a-depth-that-cannot-execute"}
    assert expected <= cited, (expected - cited, cited)
    # The release-path KIs are about the fast lane's release step, not commit-reply reading.
    assert not ({"KI-BO-020", "KI-BO-20260928-release-decline-reported-as-partial-success"} & cited), cited
    kdir = S.REPO_ROOT / "docs" / "known-issues" / "build-orchestration"
    for ki in expected:
        assert list(kdir.glob(f"*{ki.lower()}*.md")), f"cited known issue {ki} has no register file"


def test_hook_failed_handoff_not_engageable_decides_report_without_engage(tmp_path, monkeypatch):
    # covers: BO-4500b-3
    # angle: criterion
    """commit.js:77 guard ported: a handoff whose disposition is not engage-specialist is reported."""
    text = _block(tmp_path, monkeypatch)
    ca = S.hook_failed_with_handoff(disposition="author-clears")
    d = S.decide(text, S.envelope(ca), S.fresh_history())
    assert d.get("decision") == "report", d
    assert d.get("specialist") in (None, ""), d
    assert (d.get("history") or {}).get("specialist_engaged") is False, d
    for key in ("status", "reason_code", "reason", "hook_name", "failing_files"):
        assert d.get(key) == ca[key], (key, d.get(key))


def test_hook_failed_handoff_without_usable_demand_decides_report(tmp_path, monkeypatch):
    # covers: BO-4500b-3
    # angle: criterion
    """commit.js:77 guard ported: engage-specialist with a null or empty demand is reported."""
    text = _block(tmp_path, monkeypatch)
    for demand in (None, []):
        ca = S.hook_failed_with_handoff(demand=demand)
        d = S.decide(text, S.envelope(ca), S.fresh_history())
        assert d.get("decision") == "report", (demand, d)
        assert (d.get("history") or {}).get("specialist_engaged") is False, (demand, d)


def test_absent_specialist_reply_after_engage_reports_naming_the_specialist(tmp_path, monkeypatch):
    # covers: BO-4500b-3
    # angle: criterion
    """A null specialist reply after an engage is reported, names the specialist, never re-offers."""
    text = _block(tmp_path, monkeypatch)
    d1 = S.decide(text, S.envelope(S.hook_failed_with_handoff()), S.fresh_history())
    assert d1.get("decision") == "engage", d1
    hist = dict(d1.get("history") or {})
    for gone in (None, {"status": "blocker"}):
        d2 = S.decide(text, None, dict(hist, specialist_reply=gone))
        assert d2.get("decision") == "report", d2
        assert S.SPECIALIST in (d2.get("message") or ""), d2
        assert d2.get("specialist") == S.SPECIALIST, d2


def test_commit_answer_block_is_reachable_through_the_install(tmp_path, monkeypatch):
    # covers: BO-4500b-3
    # angle: reachability
    """Run the real build_workflow_scripts install with the SHIPPED config/commit_step.json values;
    the installed block text decides continue for a committed reply, and the install result is
    what was evaluated (not the source file)."""
    inst = S.render_block(tmp_path, monkeypatch)
    assert inst.error is None, inst.error
    assert inst.text is not None and S.START in inst.text
    assert "{{config" not in inst.text, "unresolved placeholder shipped in the installed block"
    d = S.decide(inst.text, S.envelope(S.commit_answer("committed")), S.fresh_history())
    assert d.get("decision") == "continue", d
    stop = S.decide(inst.text, S.envelope(S.commit_answer("refused", "policy_protected_branch")), S.fresh_history())
    assert stop.get("decision") == "stop", stop
