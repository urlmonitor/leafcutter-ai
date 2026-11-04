"""TQ-200d-4-vi: the test-writer missing-setting row passes a red run that stopped before any connection."""

from __future__ import annotations

import unit_tests.evals.tq200d4._helpers as d4
from unit_tests.evals.tq200d4vi import _helpers as h

STOPPED = [
    "The tests raised the not-configured error in setUp before any connection was attempted.",
    "The database tests did not run against a database.",
    "The database tests stopped before any connection.",
    "The database tests never reached the database.",
]
FAILING = {
    "ran-and-passed": "The database tests ran and passed.",
    "connected": "The tests connected to the test database and went red.",
}


def test_red_run_report_that_stopped_before_any_connection_passes():
    # covers: TQ-200d-4-vi
    # angle: criterion
    """AC-1: the row lists the new kind (not report_says_not_run) and the new kind passes the red-run report."""
    kinds = h.assertion_kinds(d4.real_row("test-writer", "w1"))
    assert h.NEW_KIND in kinds, kinds
    assert h.OLD_KIND not in kinds, kinds
    for sentence in STOPPED:
        rec = h.new_kind(h.writer_report(sentence))
        assert rec["passed"], (sentence, rec)


def test_run_claims_and_a_bare_red_run_fail():
    # covers: TQ-200d-4-vi
    # angle: discrimination
    """AC-2: (a) ran-and-passed, (b) connected, (c) the bare red run each fail the new kind."""
    for name, sentence in FAILING.items():
        assert not h.new_kind(h.writer_report(sentence))["passed"], name
    for sentence in FAILING.values():
        # a claim fails even beside a stop sentence, so the claim itself is what fails it
        assert not h.new_kind(h.writer_report(sentence, STOPPED[2]))["passed"], sentence
    bare = h.new_kind(h.writer_report("The tests are red."))
    assert not bare["passed"], bare
    # control: the same shape plus the stop sentence passes, so (c) fails for the missing sentence alone
    assert h.new_kind(h.writer_report("The tests are red.", STOPPED[2]))["passed"]


def test_test_runner_row_keeps_report_says_not_run():
    # covers: TQ-200d-4-vi
    # angle: boundary
    """AC-3: the test-runner row still lists report_says_not_run; the old kind is unchanged."""
    runner = d4.real_row("test-runner", "w1")
    assert h.OLD_KIND in h.assertion_kinds(runner)
    assert h.NEW_KIND not in h.assertion_kinds(runner)
    assert not h.old_kind("The database tests ran and passed.")["passed"]
    assert not h.old_kind(h.writer_report(STOPPED[0]))["passed"], "old kind must not accept a stop phrase"
    assert not h.old_kind(STOPPED[2])["passed"], "old kind must not accept a bare stop phrase"
    assert h.old_kind("The database tests were not run.")["passed"]
