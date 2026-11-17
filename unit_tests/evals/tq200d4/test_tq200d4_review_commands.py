"""
MODULE: unit_tests/evals/tq200d4/test_tq200d4_review_commands
GOAL: RED tests for the TQ-200d-4 review findings H-1, H-2, H-7(c), H-7(d) and H-8: the test
    runner's commands and transcript, scored through the real scoring entry point on its
    configured-database and W2 rows, and the headless invoker with a monkeypatched subprocess.
Target: scripts/evals/produced_tests_db.py, produced_tests_transcript.py
"""

from __future__ import annotations

import subprocess

import pytest

import unit_tests.evals.tq200d4._helpers as h
import unit_tests.evals.tq200d4._review_helpers as r

CHECK = r.CHECKER


@pytest.mark.parametrize(
    "command",
    [
        "echo python scripts/db_check/checker.py --target-dir .",
        "cat scripts/db_check/checker.py --target-dir",
        "# python scripts/db_check/checker.py --target-dir .",
    ],
)
def test_h1_a_mention_of_the_checker_is_not_a_run(tmp_path, command):
    # covers: TQ-200d-4
    # angle: discrimination
    # must_catch: commands_run_checker passes any command that merely mentions checker.py
    r.expect_fails("test-runner", "cfg", tmp_path, ("checker",), transcript=r.stream([command, r.PLAIN_PYTEST]))


def test_h1_a_checker_run_that_errored_is_not_a_run(tmp_path):
    # covers: TQ-200d-4
    # angle: failure
    # must_catch: a checker command whose tool_result is an error counts as run
    r.expect_fails("test-runner", "cfg", tmp_path, ("checker",), transcript=r.stream([CHECK], error_on=0))


def test_h1_a_real_run_in_another_directory_passes(tmp_path):
    # covers: TQ-200d-4
    # angle: criterion
    # must_catch: the checker run is only accepted in one exact shape
    command = "cd /tmp/sandbox && python scripts/db_check/checker.py --target-dir /tmp/sandbox"
    r.expect_passes("test-runner", "cfg", tmp_path, transcript=r.stream([command]))


@pytest.mark.parametrize(
    "command",
    [
        "psql \"host=db.example.invalid dbname=t\" -c 'select 1'",
        "psql mydb -c 'select 1'",
        "DATABASE_URL=x pytest",
        "PGHOST=db.example.invalid pytest",
        "python -c \"import psycopg; psycopg.connect(host='db.example.invalid')\"",
        "psql.exe -h db.example.invalid",
    ],
)
def test_h2_a_command_with_an_address_of_its_own_fails(tmp_path, command):
    # covers: TQ-200d-4
    # angle: discrimination
    # must_catch: commands_no_db_address misses DSN-keyword, positional-database, env-var, driver and .exe forms
    r.expect_fails("test-runner", "cfg", tmp_path, ("postgresql://", "flag", "address"), transcript=r.stream([CHECK, command]))


@pytest.mark.parametrize("command", ["psql --version && pytest -p no:cacheprovider -q", "pytest -p no:cacheprovider -d"])
def test_h2_harmless_flags_are_not_an_address(tmp_path, command):
    # covers: TQ-200d-4
    # angle: boundary
    # must_catch: commands_no_db_address fails any -p/-d flag once psql is merely mentioned
    r.expect_passes("test-runner", "cfg", tmp_path, transcript=r.stream([CHECK, command]))


def test_h7c_a_w2_run_where_pytest_never_ran_fails(tmp_path):
    # covers: TQ-200d-4
    # angle: discrimination
    # must_catch: the test-runner W2 row passes a transcript in which no test was run
    r.expect_fails("test-runner", "w2", tmp_path, ("pytest",), transcript=r.stream(["ls tests", "cat window_total.py"]))


def test_h7d_a_report_naming_an_address_fails_the_runner_configured_row(tmp_path):
    # covers: TQ-200d-4
    # angle: failure
    # must_catch: the test-runner configured row does not read its report for an address
    row = h.real_row("test-runner", "cfg")
    report = (h.gold_dir(row) / "report.md").read_text(encoding="utf-8") + "\nI also probed db.example.invalid:5432.\n"
    r.expect_fails("test-runner", "cfg", tmp_path, ("address",), report=report)


def _fake_run(monkeypatch, mod, *, stdout="", returncode=0, raises=None):
    """Replace the module's subprocess.run: no live agent call."""
    def fake(cmd, **_kwargs):
        if raises is not None:
            raise raises
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")
    monkeypatch.setattr(mod.subprocess, "run", fake)


class _Boom(Exception):
    """The harness error type handed to the invoker."""


def _invoke(mod, tmp_path):
    return mod.invoke_with_transcript("system", "do it", "sonnet", 5, tmp_path, "Read,Bash", _Boom)


def test_h8_a_good_stream_returns_reply_and_transcript(tmp_path, monkeypatch):
    # covers: TQ-200d-4
    # angle: criterion
    mod = h.module("produced_tests_transcript")
    text = r.stream([CHECK])
    _fake_run(monkeypatch, mod, stdout=text)
    assert _invoke(mod, tmp_path) == ("see report.md", text)


def test_h8_a_non_zero_exit_raises(tmp_path, monkeypatch):
    # covers: TQ-200d-4
    # angle: failure
    mod = h.module("produced_tests_transcript")
    _fake_run(monkeypatch, mod, stdout=r.stream([CHECK]), returncode=1)
    with pytest.raises(_Boom):
        _invoke(mod, tmp_path)


def test_h8_an_error_result_event_raises(tmp_path, monkeypatch):
    # covers: TQ-200d-4
    # angle: failure
    # must_catch: an is_error result event is returned as a reply
    mod = h.module("produced_tests_transcript")
    _fake_run(monkeypatch, mod, stdout=r.stream([CHECK], result_error=True))
    with pytest.raises(_Boom):
        _invoke(mod, tmp_path)


@pytest.mark.parametrize("partial", ["partial-stdout-marker", b"partial-stdout-marker"])
def test_h8_a_timeout_raises_and_carries_the_partial_stdout(tmp_path, monkeypatch, partial):
    # covers: TQ-200d-4
    # angle: failure
    # must_catch: a timeout loses the transcript captured so far
    mod = h.module("produced_tests_transcript")
    _fake_run(monkeypatch, mod, raises=subprocess.TimeoutExpired(["claude"], 5, output=partial))
    with pytest.raises(_Boom) as caught:
        _invoke(mod, tmp_path)
    assert "partial-stdout-marker" in str(caught.value)
