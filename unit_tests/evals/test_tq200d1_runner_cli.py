"""
MODULE: unit_tests/evals/test_tq200d1_runner_cli
GOAL: RED tests for TQ-200d-1 that drive the REAL eval CLIs (run_agent_eval.py, eval_selector.py,
    check_shipped_addresses.py) as subprocesses: row pickup, completeness, the local-only marker
    and the placeholder-address scan. No model, no network: --score-gold uses recorded outputs.
Target: scripts/evals/run_agent_eval.py, produced_tests_mode.py, eval_selector.py, agent_eval_config.json
"""

from __future__ import annotations

import json
import re

import unit_tests.evals._tq200d1_helpers as h

CONFIG = h.EVALS_DIR / "agent_eval_config.json"


def _score_gold(tmp_path, *extra, config=None):
    results = tmp_path / "results.json"
    args = ["--agent", "test-writer", "--score-gold", "--results-file", str(results), *extra]
    if config:
        args += ["--config", str(config)]
    return h.run_cli(h.RUN_EVAL, args), results


def test_test_writer_set_registers_all_eight_rows_and_scores_each(tmp_path):
    # covers: TQ-200d-1
    # angle: reachability
    # Catches: produced-tests mode not dispatched by main(); rows without gold_target skipped.
    proc, results = _score_gold(tmp_path)
    assert proc.returncode == 0, f"stdout={proc.stdout[-600:]} stderr={proc.stderr[-600:]}"
    payload = json.loads(results.read_text(encoding="utf-8"))
    rows = payload["rows"]
    assert sorted(r["id"] for r in rows) == sorted(h.ROW_IDS.values()), [r.get("id") for r in rows]
    for r in rows:
        assert isinstance(r["score"]["passed"], bool), r
        assert r["score"]["assertions"], f"row {r['id']} carries no scored assertion"
    # The recorded gold output of every row is, by definition, a passing output.
    assert [r["id"] for r in rows if not r["score"]["passed"]] == []


def test_row_without_gold_target_is_scored_and_fails_among_eight_rows(tmp_path):
    # covers: TQ-200d-1
    # angle: boundary
    # Catches: rows without gold_target skipped in score-gold mode.
    rows = h.load_set()
    victim = h.ROW_IDS["refresh"]
    for r in rows:
        if r["id"] == victim:
            del r["expected"]["gold_output"]
    set_copy = tmp_path / "test-writer-no-gold.jsonl"
    set_copy.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["agents"]["test-writer"]["eval_set"] = str(set_copy)
    cfg = tmp_path / "no_gold.json"
    cfg.write_text(json.dumps(config), encoding="utf-8")
    proc, results = _score_gold(tmp_path / "run", config=cfg)
    assert results.is_file(), f"stdout={proc.stdout[-500:]} stderr={proc.stderr[-500:]}"
    scored = {r["id"]: r for r in json.loads(results.read_text(encoding="utf-8"))["rows"]}
    assert sorted(scored) == sorted(h.ROW_IDS.values()), "a row without a gold target must still be scored (as a failure), not dropped"
    assert scored[victim]["score"]["passed"] is False and scored[victim].get("error"), scored[victim]
    others = [r for i, r in scored.items() if i != victim]
    assert len(others) == 4 and all(r["score"]["passed"] for r in others), "control: every row with a gold target still passes"
    assert proc.returncode != 0, "a failed row must not leave the run green"


def test_set_without_negative_row_is_incomplete(tmp_path):
    # covers: TQ-200d-1
    # angle: failure
    # Catches: completeness check (TQ-200a-4) skipped in the produced-tests mode.
    rows = h.load_set()
    assert sum(1 for r in rows if r["expected"].get("negative")) >= 1, "the real set has no negative row"
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    set_copy = tmp_path / "test-writer-control.jsonl"
    set_copy.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    config["agents"]["test-writer"]["eval_set"] = str(set_copy)
    control_cfg = tmp_path / "control.json"
    control_cfg.write_text(json.dumps(config), encoding="utf-8")
    control, _ = _score_gold(tmp_path / "control", config=control_cfg)
    assert control.returncode == 0, f"the unmodified copy must score: {control.stderr[-500:]}"

    for r in rows:
        r["expected"]["negative"] = False
    no_neg = tmp_path / "test-writer-no-negative.jsonl"
    no_neg.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    config["agents"]["test-writer"]["eval_set"] = str(no_neg)
    bad_cfg = tmp_path / "bad.json"
    bad_cfg.write_text(json.dumps(config), encoding="utf-8")
    proc, results = _score_gold(tmp_path / "bad", config=bad_cfg)
    assert proc.returncode == 2, f"expected INCOMPLETE exit 2, got {proc.returncode}: {proc.stderr[-500:]}"
    assert "INCOMPLETE" in proc.stderr + proc.stdout
    assert not results.exists(), "no row may be scored from an incomplete set"


def test_local_result_never_presented_as_ci(tmp_path):
    # covers: TQ-200d-1
    # angle: failure
    # Catches: report omits the local marker; payload omits it; selector lists test-writer as affected.
    agent_cfg = json.loads(CONFIG.read_text(encoding="utf-8"))["agents"]["test-writer"]
    assert agent_cfg["local_only"] is True
    assert "templates/agents/test-writer.md" in agent_cfg["triggers"], "exclusion must come from local_only, not absent triggers"
    proc, results = _score_gold(tmp_path)
    assert proc.returncode == 0, proc.stderr[-500:]
    assert json.loads(results.read_text(encoding="utf-8"))["run_context"] == "local"
    assert re.search(r"local run", proc.stdout, re.IGNORECASE), proc.stdout[-800:]
    marker = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith("LOCAL RUN:")]
    assert marker and "CI eval gate has not run" in marker[0], f"the report must carry its own local marker line: {proc.stdout[:600]}"
    assert not re.search(r"checked by ci|ci[- ]verified", proc.stdout, re.IGNORECASE)

    changed = ["--changed-files", "templates/agents/test-writer.md"]
    sel = h.run_cli(h.SELECTOR, changed)
    assert sel.returncode == 0, sel.stderr[-400:]
    assert "test-writer" not in json.loads(sel.stdout)["affected"]
    empty = tmp_path / "no_results"
    empty.mkdir()
    chk = h.run_cli(h.SELECTOR, [*changed, "--check", "--results-dir", str(empty)])
    assert chk.returncode == 0, f"--check demanded a result for a local-only agent: {chk.stdout[-500:]}"
    assert "test-writer" not in json.loads(chk.stdout)["status"]

    # Control: without the flag the very same change DOES affect test-writer (so the flag is what excludes it).
    full = json.loads(CONFIG.read_text(encoding="utf-8"))
    del full["agents"]["test-writer"]["local_only"]
    ctrl_cfg = tmp_path / "no_flag.json"
    ctrl_cfg.write_text(json.dumps(full), encoding="utf-8")
    ctrl = h.run_cli(h.SELECTOR, [*changed, "--config", str(ctrl_cfg)])
    assert "test-writer" in json.loads(ctrl.stdout)["affected"]


def test_test_writer_set_carries_only_placeholder_addresses():
    # covers: TQ-200d-1
    # angle: real_artifact
    # Catches: a real-looking address left in a row, fixture or recorded output.
    sets_dir = h.EVALS_DIR / "sets"
    assert h.SET_PATH.is_file() and h.SET_PATH.stat().st_size > 0
    recorded = list((sets_dir / "test-writer").rglob("*.py.recorded"))
    assert recorded, "no recorded test output under sets/test-writer/"
    scanner = h.REPO_ROOT / "scripts" / "portability" / "check_shipped_addresses.py"
    proc = h.run_cli(scanner, ["--build-root", str(sets_dir)])
    assert proc.returncode == 0, f"{proc.stdout[-600:]}{proc.stderr[-300:]}"
