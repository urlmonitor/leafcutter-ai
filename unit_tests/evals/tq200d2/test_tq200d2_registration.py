"""
MODULE: unit_tests/evals/tq200d2/test_tq200d2_registration
GOAL: RED tests for TQ-200d-2 that drive the REAL eval CLIs (run_agent_eval.py, eval_selector.py,
    check_shipped_addresses.py) as subprocesses: the sql-test-writer registration, row pickup, the
    local-run marker, and the placeholder-address scan. No model: --score-gold only.
Target: scripts/evals/agent_eval_config.json, scripts/evals/sets/sql-test-writer.jsonl,
    run_agent_eval.py, eval_selector.py
"""

from __future__ import annotations

import json
import re

import unit_tests.evals.tq200d2._helpers as h


def test_sql_test_writer_set_registered_and_every_row_scored(tmp_path):
    # covers: TQ-200d-2
    # angle: reachability
    # must_catch: sql-test-writer entry missing from agent_eval_config.json
    cfg = h.agent_config()
    assert cfg["template"] == "templates/agents/sql-test-writer.md"
    assert (h.REPO_ROOT / cfg["template"]).is_file()
    assert cfg["eval_set"] == "scripts/evals/sets/sql-test-writer.jsonl"
    assert cfg["scoring_mode"] == "produced_tests"
    assert cfg["model"] == "sonnet"
    # User decision 2026-10-23: Bash, Read, Edit, Write only; the sandbox has no sub-agents or skills.
    assert sorted(cfg["tools"].split(",")) == ["Bash", "Edit", "Read", "Write"], cfg["tools"]
    # The template runs the checker and the wrong-version runner (which reads the AC store) inside the sandbox.
    assert {"scripts/db_check", "scripts/build_orchestration", "scripts/ac_store"} <= set(cfg["support_scripts"])

    proc, payload = h.score_gold_cli(tmp_path)
    assert payload is not None, f"stdout={proc.stdout[-500:]} stderr={proc.stderr[-500:]}"
    # No --row was passed: the three rows are picked up from the set, no more and no fewer.
    assert sorted(r["id"] for r in payload["rows"]) == sorted(h.ROW_IDS.values()), [r.get("id") for r in payload["rows"]]
    assert proc.returncode == 0, f"stdout={proc.stdout[-600:]} stderr={proc.stderr[-600:]}"
    assert [r["id"] for r in payload["rows"] if not r["score"]["passed"]] == []
    for row in payload["rows"]:
        assert isinstance(row["score"]["passed"], bool), row
        assert row["score"]["assertions"], f"row {row['id']} carries no scored assertion"
    assert payload["aggregate"]["rows"] == 3 and payload["aggregate"]["passed"] == 3

    # One set per agent, one file: the rows live in sql-test-writer.jsonl and nowhere else.
    assert sorted(r["id"] for r in h.load_rows()) == sorted(h.ROW_IDS.values())
    negatives = {r["id"]: r["expected"]["negative"] for r in h.load_rows()}
    assert negatives == {h.ROW_IDS["reg"]: False, h.ROW_IDS["empty"]: False, h.ROW_IDS["trap"]: True}
    # Each row carries the assertion kinds that can fail it (superset: the build may add more).
    for key, kinds in h.ROW_KINDS.items():
        row_kinds = {a["kind"] for a in h.real_row(key)["expected"]["assertions"]}
        assert kinds <= row_kinds, f"{h.ROW_IDS[key]} lacks {sorted(kinds - row_kinds)}"


def test_sql_test_writer_local_result_never_presented_as_ci(tmp_path):
    # covers: TQ-200d-2
    # angle: failure
    # must_catch: report omits the local marker
    # must_catch: eval_selector lists sql-test-writer as affected
    cfg = h.agent_config()
    assert cfg["local_only"] is True
    assert "templates/agents/sql-test-writer.md" in cfg["triggers"], "exclusion must come from local_only, not absent triggers"
    proc, payload = h.score_gold_cli(tmp_path)
    assert payload is not None and proc.returncode == 0, proc.stderr[-500:]
    assert payload["run_context"] == "local"
    marker = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith("LOCAL RUN:")]
    assert marker and "CI eval gate has not run" in marker[0], proc.stdout[:600]
    assert not re.search(r"checked by ci|ci[- ]verified", proc.stdout, re.IGNORECASE)

    changed = ["--changed-files", "templates/agents/sql-test-writer.md"]
    sel = h.run_cli(h.d4.d1.SELECTOR, changed)
    assert sel.returncode == 0, sel.stderr[-400:]
    out = json.loads(sel.stdout)
    assert "sql-test-writer" not in out["affected"]
    assert "sql-test-writer" in out["local_only"], out
    empty = tmp_path / "no_results"
    empty.mkdir()
    chk = h.run_cli(h.d4.d1.SELECTOR, [*changed, "--check", "--results-dir", str(empty)])
    assert chk.returncode == 0, f"--check demanded a result for a local-only agent: {chk.stdout[-500:]}"
    assert "sql-test-writer" not in json.loads(chk.stdout)["status"]

    # Control: without the flag the very same change DOES affect sql-test-writer (so the flag is what excludes it).
    full = json.loads(h.CONFIG.read_text(encoding="utf-8"))
    del full["agents"]["sql-test-writer"]["local_only"]
    ctrl_cfg = tmp_path / "no_flag.json"
    ctrl_cfg.write_text(json.dumps(full), encoding="utf-8")
    ctrl = h.run_cli(h.d4.d1.SELECTOR, [*changed, "--config", str(ctrl_cfg)])
    assert "sql-test-writer" in json.loads(ctrl.stdout)["affected"]


def test_sql_test_writer_set_carries_only_placeholder_addresses():
    # covers: TQ-200d-2
    # angle: real_artifact
    # must_catch: a real-looking address left in a row, fixture or recorded output of the set
    assert h.SET_PATH.is_file() and h.SET_PATH.stat().st_size > 0
    set_dir = h.SETS_DIR / h.AGENT
    assert list(set_dir.rglob("report.md")), "no recorded sql-test-writer report under sets/sql-test-writer/"
    assert list(set_dir.rglob("*.py.recorded")), "no recorded sql-test-writer test under sets/sql-test-writer/"
    assert list(set_dir.rglob(h.TO_RUN_LATER.rsplit("/", 1)[-1])), "no recorded to-run-later file"
    # The two database rows carry the placeholder as their setting; the trap's sandbox leaves it unset.
    for key in ("reg", "empty"):
        config = h.REPO_ROOT / h.real_row(key)["expected"]["fixture"] / ".claude" / "skills_config.json"
        setting = json.loads(config.read_text(encoding="utf-8"))["testing_context"]["db_connection_test"]
        assert setting == h.PLACEHOLDER, f"{h.ROW_IDS[key]}: {setting!r}"
    trap = h.REPO_ROOT / h.real_row("trap")["expected"]["fixture"] / ".claude" / "skills_config.json"
    assert not json.loads(trap.read_text(encoding="utf-8")).get("testing_context", {}).get("db_connection_test")
    scanner = h.REPO_ROOT / "scripts" / "portability" / "check_shipped_addresses.py"
    for root in (h.SETS_DIR, h.FIXTURES):
        proc = h.run_cli(scanner, ["--build-root", str(root)])
        assert proc.returncode == 0, f"{root}: {proc.stdout[-600:]}{proc.stderr[-300:]}"
