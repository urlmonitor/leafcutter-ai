"""TQ-200d-4-vi: the real runner CLI replays the gold outputs of both sets after the new kind."""

from __future__ import annotations

import json

import pytest

import unit_tests.evals.tq200d4._helpers as d4


@pytest.mark.parametrize("agent", ["test-writer", "test-runner"])
def test_test_writer_and_test_runner_gold_still_pass_after_the_new_kind(agent, tmp_path):
    # covers: TQ-200d-4-vi
    # angle: reachability
    """run_agent_eval.py --agent <agent> --score-gold passes every row; the writer's row runs the new kind."""
    proc, payload = d4.score_gold_cli(agent, tmp_path)
    assert proc.returncode == 0, (proc.stdout or "")[-500:] + (proc.stderr or "")[-500:]
    assert payload is not None
    text = json.dumps(payload)
    if agent == "test-writer":
        assert "report_says_stopped_before_database" in text, "the writer row never ran the new kind"
    assert '"passed": false' not in text.lower()
