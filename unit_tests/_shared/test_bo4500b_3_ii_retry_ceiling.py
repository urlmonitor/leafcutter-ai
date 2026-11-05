"""
MODULE: unit_tests/_shared/test_bo4500b_3_ii_retry_ceiling.py
GOAL: BO-4500b-3-ii -- transient failures are retried up to the configured ceiling and then
    reported; the ceiling comes from configuration alone (fixture config, never the real file).
"""

from __future__ import annotations

import _bo4500b3_support as S

LOCKED = lambda: S.commit_answer("refused", "step_index_locked", reason="index.lock")  # noqa: E731


def _ceiling(n):
    def mutate(cfg):
        cfg["max_transient_retries"] = n
    return mutate


def test_ceiling_3_gives_retry_retry_retry_report(tmp_path, monkeypatch):
    # covers: BO-4500b-3-ii
    # angle: criterion
    """Ceiling 3, four step_index_locked replies: retry, retry, retry, report."""
    text = S.render_block(tmp_path, monkeypatch, _ceiling(3)).text
    decisions, _ = S.run_sequence(text, [LOCKED() for _ in range(4)])
    assert S.names(decisions) == ["retry", "retry", "retry", "report"], decisions


def test_every_retry_reoffers_first_attempt_paths_and_message_file(tmp_path, monkeypatch):
    # covers: BO-4500b-3-ii
    # angle: criterion
    """Each of the three retries carries the first attempt's paths and message file."""
    text = S.render_block(tmp_path, monkeypatch, _ceiling(3)).text
    decisions, _ = S.run_sequence(text, [LOCKED() for _ in range(4)])
    retries = [d for d in decisions if d.get("decision") == "retry"]
    assert len(retries) == 3, decisions
    for d in retries:
        assert d.get("paths") == S.FIRST_PATHS and d.get("message_file") == S.FIRST_MESSAGE_FILE, d


def test_report_after_ceiling_names_all_four_answers_in_order(tmp_path, monkeypatch):
    # covers: BO-4500b-3-ii
    # angle: criterion
    """The final report's answers hold all four commit_answers in arrival order."""
    text = S.render_block(tmp_path, monkeypatch, _ceiling(3)).text
    answers = [S.commit_answer("refused", "step_index_locked", reason=f"attempt {i}") for i in range(4)]
    decisions, _ = S.run_sequence(text, answers)
    final = decisions[-1]
    assert final.get("decision") == "report", decisions
    assert [a.get("reason") for a in final.get("answers") or []] == [f"attempt {i}" for i in range(4)], final


def test_success_after_transient_failures_continues(tmp_path, monkeypatch):
    # covers: BO-4500b-3-ii
    # angle: criterion
    """step_vcs_error twice then committed: retry, retry, continue."""
    text = S.render_block(tmp_path, monkeypatch, _ceiling(3)).text
    answers = [S.commit_answer("refused", "step_vcs_error"), S.commit_answer("refused", "step_vcs_error"),
               S.commit_answer("committed")]
    decisions, _ = S.run_sequence(text, answers)
    assert S.names(decisions) == ["retry", "retry", "continue"], decisions


def test_ceiling_comes_from_configuration_alone(tmp_path, monkeypatch):
    # covers: BO-4500b-3-ii
    # angle: discrimination
    """Same block source, fixture ceilings 1 and 2: the sequences follow the configured value.

    Wrong versions caught: a 3 typed into the block source (ceiling 1 would give retry, retry);
    a built-in default used when configuration differs.
    """
    one = S.render_block(tmp_path / "one", monkeypatch, _ceiling(1)).text
    d1, _ = S.run_sequence(one, [LOCKED(), LOCKED()])
    assert S.names(d1) == ["retry", "report"], d1
    two = S.render_block(tmp_path / "two", monkeypatch, _ceiling(2)).text
    d2, _ = S.run_sequence(two, [LOCKED(), LOCKED(), LOCKED()])
    assert S.names(d2) == ["retry", "retry", "report"], d2
    zero = S.render_block(tmp_path / "zero", monkeypatch, _ceiling(0)).text
    d0, _ = S.run_sequence(zero, [LOCKED()])
    assert S.names(d0) == ["report"], d0
