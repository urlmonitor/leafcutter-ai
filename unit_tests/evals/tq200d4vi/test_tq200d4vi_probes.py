"""TQ-200d-4-vi: the kept test-writer re-run reports pass; copies without their stop sentence fail."""

from __future__ import annotations

import pytest

import unit_tests.evals.tq200d4._helpers as d4
from unit_tests.evals.tq200d4vi import _helpers as h


@pytest.mark.parametrize("run", ["run1", "run2"])
def test_kept_test_writer_reports_pass_and_weakened_copies_fail(run, tmp_path):
    # covers: TQ-200d-4-vi
    # angle: real_artifact
    """AC-4: the kept report passes all four checks; without its stop sentence the new kind fails (no false green)."""
    kept = h.score_report_dir(h.probe(run, tmp_path), tmp_path)
    assert len(kept["score"]["assertions"]) == 4
    assert d4.failed(kept) == [], d4.failed(kept)
    weak = h.score_report_dir(h.probe(run, tmp_path, drop_stop_sentence=True), tmp_path)
    assert [a["kind"] for a in d4.failed(weak)] == [h.NEW_KIND], d4.failed(weak)
