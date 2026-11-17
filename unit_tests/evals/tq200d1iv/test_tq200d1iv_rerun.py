"""
MODULE: unit_tests/evals/tq200d1iv/test_tq200d1iv_rerun
GOAL: RED tests for TQ-200d-1-iv on the re-run probe fixtures and the real CLI gold replay.
Target: scripts/evals/produced_tests_scoring.py, scripts/evals/run_agent_eval.py
"""

from __future__ import annotations

import json

import pytest

import unit_tests.evals._tq200d1_helpers as h
from unit_tests.evals.tq200d1iv import _static as s

CASES = [(s.COUNT, "run1"), (s.COUNT, "run2"), (s.SEED, "run1"), (s.SEED, "run2")]
PRESENCE_VAR = {s.COUNT: "volumes", s.SEED: 'result["AAPL"]'}


def _weaken(kind, recorded, *, bare=False):
    """Drop every assertion line and assert presence only, keeping the file's indent (*bare*: as an ``assert``)."""
    lines = recorded.read_text(encoding="utf-8").splitlines()
    kept = [ln for ln in lines if "assert" not in ln]
    unit = any("unittest" in ln for ln in kept)
    indent = "        " if unit else "    "
    call = f"self.assertIsNotNone({PRESENCE_VAR[kind]})" if unit and not bare else f"assert {PRESENCE_VAR[kind]} is not None"
    recorded.write_text("\n".join(kept) + "\n" + indent + call + "\n", encoding="utf-8")


@pytest.mark.parametrize(("kind", "run"), CASES)
def test_kept_rerun_outputs_pass_and_presence_only_copies_fail(tmp_path, kind, run):
    # covers: TQ-200d-1-iv
    # angle: real_artifact
    kept = s.copy_run(kind, run, tmp_path / "kept")
    got = s.score_dir(kind, kept, tmp_path / "k")
    assert got["passed"] is True, got["detail"]
    out = s.copy_run(kind, run, tmp_path / "out")
    _weaken(kind, out / (s.TEST_FILE[kind] + ".recorded"))
    got = s.score_dir(kind, out, tmp_path)
    assert got["passed"] is False, "presence-only copy passed: false green"
    assert "does not parse" not in got["detail"], got["detail"]
    bare = s.copy_run(kind, run, tmp_path / "bare")
    _weaken(kind, bare / (s.TEST_FILE[kind] + ".recorded"), bare=True)
    got = s.score_dir(kind, bare, tmp_path / "b")
    assert got["passed"] is False, "presence-only copy (as an assert ... is not None) passed: false green"


def test_test_writer_gold_still_passes_with_unittest_reading(tmp_path):
    # covers: TQ-200d-1-iv
    # angle: reachability
    results = tmp_path / "results.json"
    proc = h.run_cli(h.RUN_EVAL, ["--agent", "test-writer", "--score-gold", "--results-file", str(results)])
    assert proc.returncode == 0, f"stdout={proc.stdout[-600:]} stderr={proc.stderr[-600:]}"
    rows = {r["id"]: r for r in json.loads(results.read_text(encoding="utf-8"))["rows"]}
    for row_id in (h.ROW_IDS["empty"], h.ROW_IDS["presence"]):
        assert rows[row_id]["score"]["passed"] is True, rows[row_id]["score"]
