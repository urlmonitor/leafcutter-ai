"""
MODULE: unit_tests/_shared/test_bo4500b_3_iv_contract_violations.py
GOAL: BO-4500b-3-iv -- a reason code outside its family, unknown to the published list, or an
    unknown answer version is reported as a contract violation and never retried.
"""

from __future__ import annotations

import json

import _bo4500b3_support as S


def _cases():
    return {
        "a_refused_check_failed": S.commit_answer("refused", "check_failed", reason="x"),
        "b_refused_null": S.commit_answer("refused", None, reason="x"),
        "c_step_disk_full": S.commit_answer("refused", "step_disk_full", reason="x"),
        "d_policy_made_up": S.commit_answer("refused", "policy_made_up", reason="x"),
        "e_committed_version_2": dict(S.commit_answer("committed"), answer_version=2),
    }


def test_out_of_family_and_unknown_codes_and_versions_are_all_report(tmp_path, monkeypatch):
    # covers: BO-4500b-3-iv
    # angle: discrimination
    """Five contract-breaking replies each decide report.

    Wrong versions caught: decide family by prefix (c retried, d stopped); accept any
    answer_version on committed (e continued).
    """
    text = S.render_block(tmp_path, monkeypatch).text
    got = {k: S.decide(text, S.envelope(ca), S.fresh_history()).get("decision") for k, ca in _cases().items()}
    assert got == {k: "report" for k in _cases()}, got


def test_contract_break_report_names_the_offending_value(tmp_path, monkeypatch):
    # covers: BO-4500b-3-iv
    # angle: criterion
    """Each report says the reply breaks the commit answer contract and names field and value."""
    text = S.render_block(tmp_path, monkeypatch).text
    expect = {
        "c_step_disk_full": ("reason_code", "step_disk_full"),
        "d_policy_made_up": ("reason_code", "policy_made_up"),
        "e_committed_version_2": ("answer_version", 2),
    }
    cases = _cases()
    for key, (field, value) in expect.items():
        d = S.decide(text, S.envelope(cases[key]), S.fresh_history())
        assert d.get("decision") == "report", (key, d)
        assert d.get("contract_violation") is True, (key, d)
        assert d.get("offending_field") == field and d.get("offending_value") == value, (key, d)
        assert "contract" in json.dumps(d).lower(), (key, d)


def test_code_added_to_config_family_changes_decision_without_block_edit(tmp_path, monkeypatch):
    # covers: BO-4500b-3-iv
    # angle: discrimination
    """Fixture config adds step_disk_full to the step family; same block source decides retry.

    Wrong version caught: a reason-code list typed into the block source.
    """
    def mutate(cfg):
        cfg["reason_codes"]["step"].append("step_disk_full")
    text = S.render_block(tmp_path, monkeypatch, mutate).text
    d = S.decide(text, S.envelope(_cases()["c_step_disk_full"]), S.fresh_history())
    assert d.get("decision") == "retry", d
    other = S.decide(text, S.envelope(_cases()["d_policy_made_up"]), S.fresh_history())
    assert other.get("decision") == "report", other


def test_contract_violation_is_reachable_through_the_install(tmp_path, monkeypatch):
    # covers: BO-4500b-3-iv
    # angle: reachability
    """Real install with the shipped config, installed text, reply (c): report."""
    inst = S.render_block(tmp_path, monkeypatch)
    assert inst.error is None, inst.error
    d = S.decide(inst.text, S.envelope(_cases()["c_step_disk_full"]), S.fresh_history())
    assert d.get("decision") == "report" and d.get("contract_violation") is True, d
