"""
MODULE: unit_tests/evals/tq200d3/test_tq200d3_registration
GOAL: RED tests for TQ-200d-3 that drive the REAL eval CLIs (run_agent_eval.py, eval_selector.py) as
    subprocesses: the test-designer registration, row pickup, the local-run marker, and the shape of the
    fixture stores. No model: --score-gold only.
Target: scripts/evals/agent_eval_config.json, scripts/evals/sets/test-designer.jsonl,
    run_agent_eval.py, eval_selector.py
"""

from __future__ import annotations

import json
import re

import yaml

import unit_tests.evals.tq200d3._helpers as h


def _assert_registered_config(cfg: dict) -> None:
    """The agent's config entry: template, set, mode, model, tools and the scripts its sandbox needs."""
    assert cfg["template"] == "templates/agents/test-designer.md"
    assert (h.REPO_ROOT / cfg["template"]).is_file()
    assert cfg["eval_set"] == "scripts/evals/sets/test-designer.jsonl"
    assert cfg["scoring_mode"] == "produced_tests"
    assert cfg["model"] == "sonnet"
    # Per the template's frontmatter: Bash, Read, Write, Edit. No sub-agents, no skills, no search tools.
    assert sorted(cfg["tools"].split(",")) == ["Bash", "Edit", "Read", "Write"], cfg["tools"]
    # The pre-pass the input is built from, and the schema validator the scorer runs, live under scripts/ac_store.
    assert "scripts/ac_store" in cfg["support_scripts"]


def _assert_every_row_scored(proc, payload) -> None:
    """No --row was passed: the three rows are picked up from the set, no more and no fewer, and each is scored."""
    assert payload is not None, f"stdout={proc.stdout[-500:]} stderr={proc.stderr[-500:]}"
    assert sorted(r["id"] for r in payload["rows"]) == sorted(h.ROW_IDS.values()), [r.get("id") for r in payload["rows"]]
    assert proc.returncode == 0, f"stdout={proc.stdout[-600:]} stderr={proc.stderr[-600:]}"
    assert [r["id"] for r in payload["rows"] if not r["score"]["passed"]] == []
    for row in payload["rows"]:
        assert isinstance(row["score"]["passed"], bool), row
        assert row["score"]["assertions"], f"row {row['id']} carries no scored assertion"
        assert not row.get("error"), row
    assert payload["aggregate"]["rows"] == 3 and payload["aggregate"]["passed"] == 3
    # A score is reported for each row on the printed report too.
    for row_id in h.ROW_IDS.values():
        assert re.search(rf"\[PASS\] {re.escape(row_id)}\b", proc.stdout), proc.stdout[:800]


def _assert_row_shape(key: str, kinds: set[str]) -> None:
    """One row: its kinds, input, fixture and gold paths, and its record."""
    row = h.real_row(key)
    row_kinds = {a["kind"] for a in row["expected"]["assertions"]}
    assert kinds <= row_kinds, f"{h.ROW_IDS[key]} lacks {sorted(kinds - row_kinds)}"
    assert row["input"].strip(), "a row's input is the request text the agent is asked"
    assert row["expected"]["fixture"] == f"scripts/evals/sets/test-designer/projects/{row['id']}"
    assert row["expected"]["gold_output"] == f"scripts/evals/sets/test-designer/recorded/{row['id']}"
    assert row["expected"]["records"] == [h.AC_IDS[key]]
    for a in row["expected"]["assertions"]:
        assert a.get("record") == h.AC_IDS[key] and a.get("store") == row["expected"]["store"], a


def _assert_scored_literals() -> None:
    """The bug-fix and gate specs carry the literals the scorer compares."""
    specs = {k: {a["kind"]: a for a in h.real_row(k)["expected"]["assertions"]}[h.K_WRONG] for k in ("bug", "gate")}
    assert specs["bug"]["exact"] == [h.REVERT] and specs["bug"]["tokens"] == ["retry_due"], specs["bug"]
    assert specs["gate"]["exact"] == [h.ALWAYS] and specs["gate"]["tokens"] == ["window open", "position limit"], specs["gate"]
    # OQ-15 as amended 2026-10-25: the fixed word-sequence variants of each condition ride in the row spec (`variants`).
    assert specs["bug"]["variants"] == h.VARIANTS["bug"] and specs["gate"]["variants"] == h.VARIANTS["gate"], specs


def test_test_designer_set_registered_and_every_row_scored(tmp_path):
    # covers: TQ-200d-3
    # covers: TQ-200d
    # angle: reachability
    # must_catch: test-designer entry missing from agent_eval_config.json
    _assert_registered_config(h.agent_config())
    proc, payload = h.score_gold_cli(tmp_path)
    _assert_every_row_scored(proc, payload)

    # One set per agent, one file: the rows live in test-designer.jsonl and nowhere else.
    rows = h.load_rows()
    assert sorted(r["id"] for r in rows) == sorted(h.ROW_IDS.values())
    negatives = {r["id"]: r["expected"]["negative"] for r in rows}
    assert negatives == {h.ROW_IDS["bug"]: False, h.ROW_IDS["gate"]: False, h.ROW_IDS["new"]: True}
    for key, kinds in h.ROW_KINDS.items():
        _assert_row_shape(key, kinds)
    _assert_scored_literals()


def test_test_designer_local_result_never_presented_as_ci(tmp_path):
    # covers: TQ-200d-3
    # angle: failure
    # must_catch: eval_selector lists test-designer as affected
    cfg = h.agent_config()
    assert cfg["local_only"] is True
    assert "templates/agents/test-designer.md" in cfg["triggers"], "exclusion must come from local_only, not absent triggers"
    assert "scripts/evals/designer_eval/**" in cfg["triggers"]
    proc, payload = h.score_gold_cli(tmp_path)
    assert payload is not None and proc.returncode == 0, proc.stderr[-500:]
    assert payload["run_context"] == "local"
    marker = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith("LOCAL RUN:")]
    assert marker and "CI eval gate has not run" in marker[0], proc.stdout[:600]
    assert not re.search(r"checked by ci|ci[- ]verified", proc.stdout, re.IGNORECASE)

    changed = ["--changed-files", "templates/agents/test-designer.md"]
    sel = h.run_cli(h.d4.d1.SELECTOR, changed)
    assert sel.returncode == 0, sel.stderr[-400:]
    out = json.loads(sel.stdout)
    assert "test-designer" not in out["affected"]
    assert "test-designer" in out["local_only"], out
    empty = tmp_path / "no_results"
    empty.mkdir()
    chk = h.run_cli(h.d4.d1.SELECTOR, [*changed, "--check", "--results-dir", str(empty)])
    assert chk.returncode == 0, f"--check demanded a result for a local-only agent: {chk.stdout[-500:]}"
    assert "test-designer" not in json.loads(chk.stdout)["status"]

    # Control: without the flag the very same change DOES affect test-designer (so the flag is what excludes it).
    full = json.loads(h.CONFIG.read_text(encoding="utf-8"))
    del full["agents"]["test-designer"]["local_only"]
    ctrl_cfg = tmp_path / "no_flag.json"
    ctrl_cfg.write_text(json.dumps(full), encoding="utf-8")
    ctrl = h.run_cli(h.d4.d1.SELECTOR, [*changed, "--config", str(ctrl_cfg)])
    assert "test-designer" in json.loads(ctrl.stdout)["affected"]


def test_designer_fixture_stores_hold_pending_records_outside_the_real_store():
    # covers: TQ-200d-3
    # angle: real_artifact
    # The designer's evidence is the requirement record it edits, so each row's sandbox holds a store of its own:
    # one leaf record with test_intent written and the design pending, outside docs/acceptance-criteria/, under an
    # id prefix the real store does not use.
    real_ids = {p.stem for p in (h.REPO_ROOT / "docs" / "acceptance-criteria").rglob("*.yaml")}
    assert not [i for i in real_ids if i.startswith("TDE-")], "the fixture id prefix must not exist in the real store"
    for key, ac_id in h.AC_IDS.items():
        expected = h.real_row(key)["expected"]
        store = expected["store"]
        assert not store.startswith(("docs/", "/")) and ".." not in store.split("/"), store
        fixture = h.REPO_ROOT / expected["fixture"]
        pending_file = fixture / store / f"{ac_id}.yaml"
        assert pending_file.is_file(), f"{pending_file} (the pending record, named <id>.yaml so the pre-pass finds it)"
        pending = yaml.safe_load(pending_file.read_text(encoding="utf-8"))
        assert pending["id"] == ac_id and ac_id not in real_ids
        assert pending["level"] in ("L2", "L3")
        assert isinstance(pending["test_intent"], list) and any(c["needs_test"] is True for c in pending["test_intent"])
        assert "test_spec" not in pending, "the test design is pending: the designer writes the test_spec"
        assert pending["declared_files"], "the pre-pass reports the declared files"
        # The recorded gold record is that record with ONLY the design fields added: nothing the designer must not touch moved.
        gold = h.gold_record(key)
        for field in ("criteria", "test_intent", "declared_files", "assigned_agent", "title", "id", "level"):
            assert gold.get(field) == pending.get(field), f"{ac_id}: the gold record changed {field}"
        assert gold.get("test_design_authorship", {}).get("step") == "test-designer"
        assert gold.get("test_design_opened_files")
        assert not (set(gold) - set(pending)) - {"test_spec", "test_design_authorship", "test_design_opened_files"}
        # The code the record declares is in the fixture project, so the designer can open it.
        for declared in pending["declared_files"]:
            if declared["state"] == "existing":
                assert (fixture / declared["path"]).is_file(), declared
