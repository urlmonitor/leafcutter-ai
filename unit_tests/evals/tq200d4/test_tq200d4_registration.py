"""
MODULE: unit_tests/evals/tq200d4/test_tq200d4_registration
GOAL: RED tests for TQ-200d-4 that drive the REAL eval CLIs (run_agent_eval.py, eval_selector.py,
    check_shipped_addresses.py) as subprocesses: the test-runner registration, row pickup in both
    sets, the local-run marker, and the placeholder-address scan. No model: --score-gold only.
Target: scripts/evals/agent_eval_config.json, sets/test-writer.jsonl, sets/test-runner.jsonl,
    run_agent_eval.py, eval_selector.py
"""

from __future__ import annotations

import json
import re

import unit_tests.evals.tq200d4._helpers as h


def test_test_runner_set_registered_and_every_row_scored(tmp_path):
    # covers: TQ-200d-4
    # angle: reachability
    # must_catch: test-runner entry missing from agent_eval_config.json
    # must_catch: database-setting rows placed in a second test-writer set
    runner = h.agent_config("test-runner")
    assert runner["eval_set"] == "scripts/evals/sets/test-runner.jsonl"
    assert runner["scoring_mode"] == "produced_tests"
    assert runner["template"] == "templates/agents/test-runner.md"

    proc, payload = h.score_gold_cli("test-runner", tmp_path)
    assert payload is not None, f"stdout={proc.stdout[-500:]} stderr={proc.stderr[-500:]}"
    assert sorted(r["id"] for r in payload["rows"]) == sorted(h.ROW_IDS.values())
    assert proc.returncode == 0, f"stdout={proc.stdout[-600:]} stderr={proc.stderr[-600:]}"
    assert [r["id"] for r in payload["rows"] if not r["score"]["passed"]] == []
    assert all(r["score"]["assertions"] for r in payload["rows"]), "every row carries a scored assertion"

    proc, payload = h.score_gold_cli("test-writer", tmp_path)
    assert payload is not None, f"stdout={proc.stdout[-500:]} stderr={proc.stderr[-500:]}"
    assert sorted(r["id"] for r in payload["rows"]) == sorted([*h.D1_ROW_IDS, *h.ROW_IDS.values()])
    assert proc.returncode == 0, proc.stdout[-600:]

    # One set per agent: the new test-writer rows live in the TQ-200d-1 set, in no second file.
    assert h.agent_config("test-writer")["eval_set"] == "scripts/evals/sets/test-writer.jsonl"
    assert sorted(p.name for p in h.SETS_DIR.glob("*.jsonl")) == ["restructuring-specialist.jsonl", "sql-test-writer.jsonl", "test-runner.jsonl", "test-writer.jsonl"]
    assert [r["id"] for r in h.load_rows("test-runner")].count(h.ROW_IDS["cfg"]) == 1


def test_test_runner_local_result_never_presented_as_ci(tmp_path):
    # covers: TQ-200d-4
    # angle: failure
    # must_catch: eval_selector lists test-runner as affected
    cfg = h.agent_config("test-runner")
    assert cfg["local_only"] is True
    assert "templates/agents/test-runner.md" in cfg["triggers"], "exclusion must come from local_only, not absent triggers"
    proc, payload = h.score_gold_cli("test-runner", tmp_path)
    assert payload is not None and proc.returncode == 0, proc.stderr[-500:]
    assert payload["run_context"] == "local"
    marker = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith("LOCAL RUN:")]
    assert marker and "CI eval gate has not run" in marker[0], proc.stdout[:600]
    assert not re.search(r"checked by ci|ci[- ]verified", proc.stdout, re.IGNORECASE)

    changed = ["--changed-files", "templates/agents/test-runner.md"]
    sel = h.run_cli(h.d1.SELECTOR, changed)
    assert sel.returncode == 0, sel.stderr[-400:]
    out = json.loads(sel.stdout)
    assert "test-runner" not in out["affected"]
    assert "test-runner" in out["local_only"], out
    empty = tmp_path / "no_results"
    empty.mkdir()
    chk = h.run_cli(h.d1.SELECTOR, [*changed, "--check", "--results-dir", str(empty)])
    assert chk.returncode == 0, f"--check demanded a result for a local-only agent: {chk.stdout[-500:]}"
    assert "test-runner" not in json.loads(chk.stdout)["status"]

    # Control: without the flag the very same change DOES affect test-runner.
    full = json.loads(h.CONFIG.read_text(encoding="utf-8"))
    del full["agents"]["test-runner"]["local_only"]
    ctrl_cfg = tmp_path / "no_flag.json"
    ctrl_cfg.write_text(json.dumps(full), encoding="utf-8")
    ctrl = h.run_cli(h.d1.SELECTOR, [*changed, "--config", str(ctrl_cfg)])
    assert "test-runner" in json.loads(ctrl.stdout)["affected"]


def test_db_setting_rows_carry_only_placeholder_addresses():
    # covers: TQ-200d-4
    # angle: real_artifact
    assert h.set_path("test-runner").is_file() and h.set_path("test-runner").stat().st_size > 0
    runner_dir = h.SETS_DIR / "test-runner"
    assert list(runner_dir.rglob("report.md")), "no recorded test-runner output under sets/test-runner/"
    assert list(runner_dir.rglob(h.TRANSCRIPT)), "no recorded test-runner command transcript"
    assert list(h.SETS_DIR.glob("test-writer/**/" + h.WRITER_TEST_FILE)), "no recorded configured-database test"
    configs = [p for p in h.SETS_DIR.rglob("skills_config.json") if h.PLACEHOLDER in p.read_text(encoding="utf-8")]
    assert len(configs) >= 2, f"the configured-database rows of both sets must hold the placeholder: {configs}"
    scanner = h.REPO_ROOT / "scripts" / "portability" / "check_shipped_addresses.py"
    proc = h.run_cli(scanner, ["--build-root", str(h.SETS_DIR)])
    assert proc.returncode == 0, f"{proc.stdout[-600:]}{proc.stderr[-300:]}"
