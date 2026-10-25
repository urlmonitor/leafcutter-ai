"""
MODULE: unit_tests/evals/tq200d4/test_tq200d4_addresses
GOAL: RED tests for TQ-200d-4 on the configured-database rows: the test writer is scored on its
    produced file (structure), the test runner on the commands of a recorded stream-json
    transcript, and the real checker proves each row's sandbox setting is what the row says.
Target: scripts/evals/produced_tests_scoring.py, produced_tests_mode.py, the two set files
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

import unit_tests.evals.tq200d4._helpers as h

BAD = h.FIXTURES / "bad"
TRANSCRIPTS = h.FIXTURES / "transcripts"


@pytest.mark.parametrize(
    "bad",
    ["cfg_resolve_plus_literal_host_port.py.recorded", "cfg_literal_dsn_only.py.recorded", "cfg_resolve_with_literal_fallback.py.recorded"],
)
def test_configured_row_fails_a_literal_address(tmp_path, bad):
    # covers: TQ-200d-4
    # angle: criterion
    # must_catch: configured-database row passes a hard-coded address
    # must_catch: a resolve_test_db_address call excuses a remaining literal address
    row = h.real_row("test-writer", "cfg")
    gold_text = (h.gold_dir(row) / h.WRITER_TEST_FILE).read_text(encoding="utf-8")
    assert "resolve_test_db_address" in gold_text and "postgresql://" not in gold_text
    good = h.score("test-writer", row, h.gold_dir(row), tmp_path / "good")
    assert good["score"]["passed"] is True, h.failed(good)
    out = h.swapped_output(row, tmp_path, {h.WRITER_TEST_FILE: BAD / bad})
    record = h.score("test-writer", row, out, tmp_path / "bad")
    assert record["score"]["passed"] is False, record["score"]
    assert any("address" in a["detail"].lower() or "literal" in a["detail"].lower() for a in h.failed(record)), h.failed(record)
    assert h.passed(record), "control: the report check still passes, only the test file fails"


@pytest.mark.parametrize(
    ("transcript", "word", "kind"),
    [
        ("positional_database.jsonl", "the positional database", "commands_no_db_address"),
        ("literal_only.jsonl", "a postgresql:// literal", "commands_no_db_address"),
        ("host_port_flags.jsonl", "a host/port/database flag", "commands_no_db_address"),
        ("checker_not_run.jsonl", "checker", "commands_run_checker"),
    ],
)
def test_test_runner_configured_row_read_from_its_commands(tmp_path, transcript, word, kind):
    # covers: TQ-200d-4
    # angle: discrimination
    # must_catch: test-runner row scored from its final report only
    # must_catch: a command carrying a postgresql:// literal accepted
    row = h.real_row("test-runner", "cfg")
    gold = h.gold_dir(row)
    report = (gold / "report.md").read_text(encoding="utf-8")
    assert "invalid" in report.lower(), "the recorded report relays the checker's invalid status"
    good = h.score("test-runner", row, gold, tmp_path / "good")
    assert good["score"]["passed"] is True, h.failed(good)
    out = h.swapped_output(row, tmp_path, {h.TRANSCRIPT: TRANSCRIPTS / transcript})
    record = h.score("test-runner", row, out, tmp_path / "bad")
    # The report is the gold report, byte for byte: only the commands can fail the row.
    assert record["score"]["passed"] is False, record["score"]
    # Only the intended check fails, and it fails with its own wording (so no other rule can stand in for it).
    assert [a["kind"] for a in h.failed(record)] == [kind], h.failed(record)
    assert word in h.failed(record)[0]["detail"].lower(), h.failed(record)
    assert h.passed(record), "control: the report check passes, the commands fail"


def _checker_status(agent: str, key: str, tmp_path) -> str:
    """Build the row's scoring sandbox exactly as the mode does, run the REAL checker CLI in it."""
    runs = h.module("produced_tests_runs")
    mode = h.module("produced_tests_mode")
    row = h.real_row(agent, key)
    expected = row["expected"]
    sandbox = tmp_path / agent / key / "sandbox"
    runs.build_sandbox(
        h.REPO_ROOT / expected["fixture"], sandbox, runs.hold_back_dirs(expected.get("assertions", [])),
        mode.support_for(h.agent_config(agent), h.REPO_ROOT),
    )
    try:
        checker = sandbox / "scripts" / "db_check" / "checker.py"
        assert checker.is_file(), "the sandbox must hold the deployed copy of scripts/db_check"
        done = subprocess.run(
            [sys.executable, str(checker), "--target-dir", str(sandbox)],
            capture_output=True, text=True, timeout=60, check=False, cwd=sandbox,
        )
        return json.loads(done.stdout)["status"]
    finally:
        runs.remove_tree(sandbox)


@pytest.mark.parametrize("agent", h.AGENTS)
def test_db_rows_sandbox_setting_matches_the_row(tmp_path, agent):
    # covers: TQ-200d-4
    # angle: seam
    # must_catch: W1/W2 sandbox inherits a configured setting
    assert _checker_status(agent, "cfg", tmp_path) == "invalid"
    assert _checker_status(agent, "w1", tmp_path) == "not_configured"
    assert _checker_status(agent, "w2", tmp_path) == "not_configured"
