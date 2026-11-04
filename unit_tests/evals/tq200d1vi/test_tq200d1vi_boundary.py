"""
MODULE: unit_tests/evals/tq200d1vi/test_tq200d1vi_boundary.py
COVERS: TQ-200d-1-vi
GOAL: RED tests: every other report_mentions row keeps its one term, and the real CLI replays both gold sets
    (the widened rows scored on re-run wordings) with every row passing.
Target: scripts/evals/sets/test-writer.jsonl, scripts/evals/sets/test-runner.jsonl, scripts/evals/run_agent_eval.py
"""

from __future__ import annotations

import json
import shutil

import unit_tests.evals._tq200d1_helpers as h
from unit_tests.evals.tq200d1vi import _helpers as s

WIDENED = {s.EMPTY, s.PRESENCE}
CONFIG = h.EVALS_DIR / "agent_eval_config.json"


def test_other_report_mentions_rows_keep_their_one_term(tmp_path):
    # covers: TQ-200d-1-vi
    # angle: boundary
    # must_catch: also_accepts added to another row; the widening applied to every report_mentions row
    """Only the two widened rows carry also_accepts; any other row fails a report holding only an equivalent wording."""
    seen = []
    for path in (h.SET_PATH, s.RUNNER_SET):
        for row_id, spec in s.mention_specs(path):
            seen.append((path.name, row_id))
            if row_id in WIDENED and path == h.SET_PATH:
                assert spec.get("also_accepts"), f"{row_id} must list also_accepts"
                continue
            assert "also_accepts" not in spec, f"{path.name} row {row_id} must keep its one term"
            report = "non-None non-NULL known value expected value seeded value"
            got = s.score_report(report, tmp_path / f"{path.stem}-{row_id}", row_id, path)
            assert got["passed"] is False, f"{row_id}: equivalent wordings of another row must not pass"
            assert got["detail"] == f"report does not name '{spec['contains']}'", got["detail"]
    assert len(seen) == 8, f"expected 6 test-writer and 2 test-runner report_mentions rows, got {seen}"


def test_widened_row_detail_names_the_term_found_or_lists_every_term(tmp_path):
    # covers: TQ-200d-1-vi
    # angle: boundary
    # must_catch: detail text unchanged for a widened row
    """The widened rows' detail names the term found, or lists every term when none is found."""
    spec = dict(s.mention_specs(h.SET_PATH))[s.EMPTY]
    hit = s.score_report("the exact non-None count", tmp_path / "hit", s.EMPTY)["detail"]
    assert "non-None" in hit
    miss = s.score_report("counts the values", tmp_path / "miss", s.EMPTY)["detail"]
    for term in (spec["contains"], *spec.get("also_accepts", [])):
        assert term in miss, f"the failing detail must list {term!r}: {miss}"
    assert spec.get("also_accepts"), "the empty-window row must list also_accepts"


def _copy_with_rerun_reports(tmp_path):
    """A copy of the test-writer set whose two widened rows have gold outputs reporting the re-run wordings."""
    rows = h.load_set()
    for row in rows:
        if row["id"] in WIDENED:
            wording = s.EMPTY_RERUNS[1] if row["id"] == s.EMPTY else s.PRESENCE_RERUNS[0]
            gold = tmp_path / "gold" / row["id"]
            shutil.copytree(h.gold_dir(row), gold)
            (gold / "report.md").write_text("# Completion report\n\n" + wording + "\n", encoding="utf-8")
            row["expected"]["gold_output"] = str(gold)
    set_copy = tmp_path / "test-writer-rerun.jsonl"
    set_copy.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["agents"]["test-writer"]["eval_set"] = str(set_copy)
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(config), encoding="utf-8")
    return cfg


def test_test_writer_and_test_runner_gold_still_pass(tmp_path):
    # covers: TQ-200d-1-vi
    # angle: reachability
    # surface_invoked: python scripts/evals/run_agent_eval.py --agent test-writer --score-gold --results-file <tmp>
    """The real CLI scores both sets: the test-writer rows (widened rows on re-run wordings) and the test-runner rows pass."""
    cfg = _copy_with_rerun_reports(tmp_path)
    results = tmp_path / "tw.json"
    proc = h.run_cli(h.RUN_EVAL, ["--agent", "test-writer", "--score-gold", "--results-file", str(results), "--config", str(cfg)])
    assert results.is_file(), f"stdout={proc.stdout[-500:]} stderr={proc.stderr[-500:]}"
    rows = json.loads(results.read_text(encoding="utf-8"))["rows"]
    failed = {r["id"]: [a["detail"] for a in r["score"]["assertions"] if not a["passed"]] for r in rows if not r["score"]["passed"]}
    assert len(rows) == 8 and not failed, f"every test-writer row must pass: {failed}"
    assert proc.returncode == 0, proc.stderr[-500:]

    runner = tmp_path / "tr.json"
    proc = h.run_cli(h.RUN_EVAL, ["--agent", "test-runner", "--score-gold", "--results-file", str(runner)])
    assert runner.is_file(), f"stdout={proc.stdout[-500:]} stderr={proc.stderr[-500:]}"
    runner_rows = json.loads(runner.read_text(encoding="utf-8"))["rows"]
    assert runner_rows and all(r["score"]["passed"] for r in runner_rows), [r["id"] for r in runner_rows if not r["score"]["passed"]]
    assert proc.returncode == 0, proc.stderr[-500:]
