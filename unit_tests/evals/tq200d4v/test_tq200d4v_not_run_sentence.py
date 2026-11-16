"""
MODULE: unit_tests/evals/tq200d4v/test_tq200d4v_not_run_sentence.py
COVERS: TQ-200d-4-v
GOAL: Prove that the test-runner's fixed "Database Not Configured" block, relayed word for word,
    passes every check of the row ``missing-setting-database-work`` only because of the sentence
    "The database tests were not run." (the scorer is not widened), that a run claim beside the
    sentence still fails the not-run check, and that the kept live reports and the gold output of
    the test-runner set still pass.
Target: templates/agents/test-runner.md, scripts/evals/produced_tests_reports.py (report_says_not_run)
RED STATE: the template block holds no not-run sentence, so the verbatim block fails report_says_not_run.
"""

from __future__ import annotations

import unit_tests.evals.tq200d4._helpers as d4
import unit_tests.evals.tq200d4v._helpers as h

SIX = {"report_mentions", "report_says_unconfigured", "report_says_not_run",
       "report_names_no_address", "commands_run_checker", "commands_no_db_address"}


def test_verbatim_block_alone_passes_all_six_checks(tmp_path):
    # covers: TQ-200d-4-v
    # angle: criterion
    # must_catch: the template block without its not-run sentence
    """The block extracted from the template, with the run1 transcript, passes all six assertions."""
    block = h.template_block()
    record = h.score_report(tmp_path, block)
    kinds = [a["kind"] for a in record["score"]["assertions"]]
    assert set(kinds) == SIX and len(kinds) == 6, f"the row must score exactly the six checks, got {kinds}"
    detail = {a["kind"]: a["detail"] for a in d4.failed(record)}
    assert record["score"]["passed"] is True and not detail, \
        f"the verbatim block alone must pass all six checks; failed: {detail}"
    assert len(d4.passed(record)) == 6


def test_block_without_the_sentence_still_fails_not_run(tmp_path):
    # covers: TQ-200d-4-v
    # angle: discrimination
    # must_catch: report_says_not_run widened to accept 'before running database tests'
    """The same block with the sentence removed fails report_says_not_run, and only that check."""
    block = h.template_block()
    assert h.SENTENCE in block, f"control: the template block must hold {h.SENTENCE!r} before it can be removed"
    with_sentence = h.score_report(tmp_path / "with", block)
    assert h.failed_kinds(with_sentence) == [], "control: the block with the sentence passes every check"
    stripped = "\n".join(line for line in block.splitlines() if h.SENTENCE not in line) + "\n"
    assert stripped != block
    record = h.score_report(tmp_path / "without", stripped)
    assert h.failed_kinds(record) == [h.NOT_RUN], \
        f"without the sentence only report_says_not_run may fail, got {h.failed_kinds(record)}"


def test_block_plus_a_run_claim_fails_not_run(tmp_path):
    # covers: TQ-200d-4-v
    # angle: discrimination
    # must_catch: a run claim accepted when the not-run sentence is present
    """The block plus 'The database tests ran and passed.' fails report_says_not_run, and only that check."""
    block = h.template_block()
    assert h.SENTENCE in block, f"control: the template block must hold {h.SENTENCE!r}"
    claimed = block + h.RUN_CLAIM + "\n"
    record = h.score_report(tmp_path, claimed)
    assert h.failed_kinds(record) == [h.NOT_RUN], \
        f"a run claim must fail report_says_not_run alone, got {h.failed_kinds(record)}"


def test_kept_test_runner_reports_still_pass(tmp_path):
    # covers: TQ-200d-4-v
    # angle: real_artifact
    """The recorded re-run 1 and re-run 2 probes pass all six assertions of the row."""
    for run in ("run1", "run2"):
        record = h.score_probe(tmp_path, run)
        assert len(record["score"]["assertions"]) == 6
        assert h.failed_kinds(record) == [], f"{run} must still pass: {h.failed_kinds(record)}"
        assert record["score"]["passed"] is True


def test_test_runner_gold_still_passes_with_the_new_sentence(tmp_path):
    # covers: TQ-200d-4-v
    # angle: reachability
    """The real CLI replays the test-runner gold outputs and all four rows pass."""
    proc, payload = d4.score_gold_cli("test-runner", tmp_path)
    assert payload is not None and proc.returncode == 0, proc.stderr[-500:]
    rows = payload["rows"]
    assert len(rows) == 4, f"the test-runner set has four rows, got {[r['id'] for r in rows]}"
    assert [r["id"] for r in rows if not r["score"]["passed"]] == []
