"""
MODULE: unit_tests/evals/tq200d2iii/test_tq200d2iii_reach_docs
GOAL: RED tests for TQ-200d-2-iii: the real runner CLI scores the kept re-run 1 output of the row (and
    a predicate-less copy) through the set, the gold run stays green, and the reference entry, the known
    issue, the register and the changelog say what was fixed.
Target: scripts/evals/run_agent_eval.py (unchanged), docs/reference/produced-tests-eval-assertion-kinds-sql-test-writer.md,
    docs/known-issues/testing-quality*, changelogs/
"""

from __future__ import annotations

import json
import shutil

import unit_tests.evals.tq200d2._helpers as h
import unit_tests.evals.tq200d2._probes as p
import unit_tests.evals.tq200d2iii._helpers as t


def _cli_with_empty_gold(tmp_path, name: str, gold):
    """Run the real CLI --score-gold over a config whose set has the empty-window row's gold output at *gold*."""
    rows = h.load_rows()
    for row in rows:
        if row["id"] == h.ROW_IDS["empty"]:
            row["expected"]["gold_output"] = str(gold)
    set_file = tmp_path / f"{name}.jsonl"
    set_file.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    cfg = json.loads(h.CONFIG.read_text(encoding="utf-8"))
    cfg["agents"][h.AGENT]["eval_set"] = str(set_file)
    config = tmp_path / f"{name}_config.json"
    config.write_text(json.dumps(cfg), encoding="utf-8")
    results = tmp_path / f"{name}_results.json"
    proc = h.run_cli(h.d4.d1.RUN_EVAL, ["--agent", h.AGENT, "--score-gold", "--config", str(config), "--results-file", str(results)])
    return proc, json.loads(results.read_text(encoding="utf-8")) if results.is_file() else None


def test_sql_test_writer_gold_still_passes_with_filtered_counts(tmp_path):
    # covers: TQ-200d-2-iii
    # angle: reachability
    proc, payload = h.score_gold_cli(tmp_path)
    assert payload is not None and proc.returncode == 0, f"stdout={proc.stdout[-500:]} stderr={proc.stderr[-500:]}"
    assert [r["id"] for r in payload["rows"] if not r["score"]["passed"]] == []
    # The kept output goes through the real CLI and its verdict decides the exit code (consumed in control flow).
    proc, payload = _cli_with_empty_gold(tmp_path, "kept", t.RERUN)
    assert payload is not None, f"stdout={proc.stdout[-500:]} stderr={proc.stderr[-500:]}"
    rows = {r["id"]: r for r in payload["rows"]}
    assert rows[h.ROW_IDS["empty"]]["score"]["passed"] is True, rows[h.ROW_IDS["empty"]]["score"]
    assert proc.returncode == 0, proc.stdout[-500:]
    bare = tmp_path / "bare"
    shutil.copytree(t.RERUN, bare)
    probe = bare / h.EMPTY_TEST_FILE
    probe.write_text(probe.read_text(encoding="utf-8").replace(" AND buy_volume IS NOT NULL", ""), encoding="utf-8")
    proc, payload = _cli_with_empty_gold(tmp_path, "bare", bare)
    assert payload is not None
    failing = [r["id"] for r in payload["rows"] if not r["score"]["passed"]]
    assert failing == [h.ROW_IDS["empty"]] and proc.returncode != 0, (failing, proc.returncode)


def test_count_entry_lists_the_filtered_form(tmp_path):
    # covers: TQ-200d-2-iii
    # angle: real_artifact
    # must_catch: entry still lists only three non-NULL forms
    entry = p.entry_of(h.K_COUNTS)
    passes_when, fails_when = p.part(entry, "Passes when").lower(), p.part(entry, "Fails when").lower()
    for phrase in ("count(*)", "count(1)", "is not null", "alias", "equality", "processed-row count"):
        assert phrase in passes_when, f"Passes when must name {phrase!r}: {passes_when}"
    for phrase in ("different statement", "is null", "another column", ">= 0", "at least one row"):
        assert phrase in fails_when, f"Fails when must name {phrase!r}: {fails_when}"
    passing = p.probe_files(entry, "Passing example")
    assert any("tq200d-rerun" in f and f.endswith("test_buy_volume_window.py.recorded") for f in passing), passing
    row = h.real_row("empty")
    for n, named in enumerate(passing):
        out = h.output_with(row, tmp_path / f"p{n}", {h.EMPTY_TEST_FILE: p.REPO_ROOT / named})
        assert p.assertion(h.score(row, out, tmp_path / f"p{n}" / "w"), h.K_COUNTS)["passed"] is True, named
    template = (p.REPO_ROOT / "templates/agents/sql-test-writer.md").read_text(encoding="utf-8")
    assert "assert an exact count of processed rows plus a non-NULL count" in " ".join(template.split())
    p.ki_resolved(t.KI_STEM, "TQ-200d-2-iii")
    ki = (p.KI_DIR / "resolved" / f"resolved-low-{t.KI_STEM}.md").read_text(encoding="utf-8")
    assert "unit_tests/evals/tq200d2iii/" in ki, "the Status names the proving tests"
    notes = [f for f in (p.REPO_ROOT / "changelogs").glob("*.md") if "TQ-200d-2-iii" in f.read_text(encoding="utf-8")]
    assert len(notes) == 1 and "KI-TQ-20261102-sql-non-null-count-misses-count-star-where-not-null" in notes[0].read_text(encoding="utf-8"), notes
