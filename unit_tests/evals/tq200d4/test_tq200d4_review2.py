"""
MODULE: unit_tests/evals/tq200d4/test_tq200d4_review2
GOAL: RED tests for the TQ-200d-4 review round 2 findings R2-1 .. R2-5, R2-L1 and R2-L8, scored
    through the real scoring entry point on the real rows, each output being a row's gold output
    with one thing replaced. No model, no network.
Target: scripts/evals/produced_tests_commands.py, produced_tests_reports.py, produced_tests_db.py,
    produced_tests_transcript.py, agent_eval_config.json, the recorded test-runner transcripts
"""

from __future__ import annotations

import json
import re
import subprocess

import pytest

import unit_tests.evals.tq200d4._helpers as h
import unit_tests.evals.tq200d4._review2_helpers as r2
import unit_tests.evals.tq200d4._review_helpers as r

CHECK = r2.CHECK


def test_r2_1_a_checker_run_that_exited_non_zero_with_its_report_is_a_run(tmp_path):
    # covers: TQ-200d-4
    # angle: boundary
    # must_catch: commands_run_checker fails every correct live run (the checker exits 1 unless reachable)
    content = "Exit code 1\n" + r2.INVALID_JSON
    r.expect_passes("test-runner", "cfg", tmp_path, transcript=r2.stream_calls([(CHECK, content, True)]))


@pytest.mark.parametrize(
    "content",
    [
        'Exit code 1\nTraceback (most recent call last):\n  File "checker.py", line 3\nImportError: no module named x',
        "Exit code 2\nusage: checker.py [-h] --target-dir TARGET_DIR\nchecker.py: error: unrecognized arguments: --bogus",
    ],
)
def test_r2_1_a_crashed_or_misused_checker_is_not_a_run(tmp_path, content):
    # covers: TQ-200d-4
    # angle: discrimination
    # must_catch: any is_error result counts as a run, or none does
    r.expect_fails("test-runner", "cfg", tmp_path, ("checker",), transcript=r2.stream_calls([(CHECK, content, True)]))


@pytest.mark.parametrize("key", ["cfg", "w1"])
def test_r2_1_the_gold_transcripts_have_the_real_result_shape(key):
    # covers: TQ-200d-4
    # angle: real_artifact
    # must_catch: the recorded gold transcript says "ok" for a checker run that really exits non-zero
    row = h.real_row("test-runner", key)
    events = [json.loads(ln) for ln in (h.gold_dir(row) / h.TRANSCRIPT).read_text(encoding="utf-8").splitlines()]
    uses = [b for e in events if e.get("type") == "assistant" for b in e["message"]["content"] if "checker.py" in b["input"]["command"]]
    assert uses, "the gold transcript runs the checker"
    results = {b["tool_use_id"]: b for e in events if e.get("type") == "user" for b in e["message"]["content"]}
    body = results[uses[0]["id"]]
    text = body["content"]
    match = re.search(r"\{.*\}", text, re.DOTALL)
    assert match, f"the result content must hold the checker's JSON report: {text!r}"
    status = json.loads(match.group(0))["status"]
    assert status == {"cfg": "invalid", "w1": "not_configured"}[key]
    assert body.get("is_error", False) is (status != "reachable"), "is_error must match the checker's exit code"


@pytest.mark.parametrize(
    "command",
    ["bash -c \"psql -h db.example.invalid -c 'select 1'\"", "sh -c 'psql mydb'", 'cmd /c "psql -h db.example.invalid"'],
)
def test_r2_2_a_wrapped_client_command_with_an_address_is_flagged(tmp_path, command):
    # covers: TQ-200d-4
    # angle: discrimination
    # must_catch: commands_no_db_address does not look inside bash -c / sh -c / cmd /c
    r.expect_fails("test-runner", "cfg", tmp_path, ("flag", "address", "postgresql://"), transcript=r.stream([CHECK, command]))


@pytest.mark.parametrize(
    "command",
    [
        "python scripts/db_check/checker.py --target-dir=/p",
        "env X=1 python scripts/db_check/checker.py --target-dir .",
        "timeout 60 python scripts/db_check/checker.py --target-dir .",
        "uv run python scripts/db_check/checker.py --target-dir .",
        "python -X utf8 scripts/db_check/checker.py --target-dir .",
        "python3 scripts\\db_check\\checker.py --target-dir .",
    ],
)
def test_r2_2_real_checker_run_shapes_count(tmp_path, command):
    # covers: TQ-200d-4
    # angle: boundary
    # must_catch: commands_run_checker accepts one exact command shape only
    r.expect_passes("test-runner", "cfg", tmp_path, transcript=r2.ok(command))


def test_r2_2_help_is_not_a_checker_run(tmp_path):
    # covers: TQ-200d-4
    # angle: discrimination
    # must_catch: --help beside --target-dir counts as a run
    r.expect_fails("test-runner", "cfg", tmp_path, ("checker",),
                   transcript=r2.ok("python scripts/db_check/checker.py --help --target-dir ."))


@pytest.mark.parametrize("command", ["poetry run pytest", "python -Im pytest", 'bash -c "pytest -q"', "uv run pytest"])
def test_r2_2_real_pytest_run_shapes_count(tmp_path, command):
    # covers: TQ-200d-4
    # angle: boundary
    # must_catch: commands_ran_pytest accepts python -m pytest only
    r.expect_passes("test-runner", "w2", tmp_path, transcript=r2.ok(command))


@pytest.mark.parametrize("agent", h.AGENTS)
@pytest.mark.parametrize(
    "tail",
    ["No database tests were run.", "The database tests weren't run.", "I didn't run the database tests.", "Database tests were skipped."],
)
def test_r2_3_natural_not_run_wordings_pass(tmp_path, agent, tail):
    # covers: TQ-200d-4
    # angle: boundary
    # must_catch: report_says_not_run knows only a few phrasings
    r.expect_passes(agent, "w1", tmp_path, report=r2.W1_HEAD + tail + "\n")


def test_r2_4_a_report_quoting_the_placeholder_names_no_address(tmp_path):
    # covers: TQ-200d-4
    # angle: boundary
    # must_catch: report_names_no_address fails the placeholder the setting holds
    row = h.real_row("test-runner", "cfg")
    report = (h.gold_dir(row) / "report.md").read_text(encoding="utf-8") + f"\nThe setting holds {h.PLACEHOLDER}.\n"
    r.expect_passes("test-runner", "cfg", tmp_path, report=report)


@pytest.mark.parametrize("agent", h.AGENTS)
@pytest.mark.parametrize("line", ["All tests pass.", "3 tests, 0 failures.", "tests failed: 1"])
def test_r2_4_any_outcome_wording_states_an_outcome(tmp_path, agent, line):
    # covers: TQ-200d-4
    # angle: boundary
    # must_catch: report_states_outcome needs one of a few words
    r.expect_passes(agent, "w2", tmp_path, report=f"# Report\n\n{line}\n")


@pytest.mark.parametrize("agent", h.AGENTS)
@pytest.mark.parametrize(
    "line",
    [
        "testing_context.db_connection_test was not set.",
        "testing_context.db_connection_test is unset.",
        "testing_context.db_connection_test isn't set.",
        "testing_context.db_connection_test is missing.",
    ],
)
def test_r2_4_any_unconfigured_wording_is_accepted(tmp_path, agent, line):
    # covers: TQ-200d-4
    # angle: boundary
    # must_catch: report_says_unconfigured needs "not configured" or "is not set" exactly
    r.expect_passes(agent, "w1", tmp_path, report=f"# Report\n\n{line}\nThe database tests were not run.\n")


HEAD = "class TestTotals(unittest.TestCase):\n"
RESOLVER_SHAPES = {
    "instance": (
        HEAD + "    def setUp(self):\n        self.dsn = resolve_test_db_address(ROOT)\n",
        "psycopg2.connect(self.dsn)", 'psycopg2.connect(os.environ["TEST_URL"])'),
    "fixture": (
        "import pytest\n\n\n@pytest.fixture\ndef dsn():\n    return resolve_test_db_address(ROOT)\n\n\nclass TestTotals:\n"
        "    @pytest.fixture(autouse=True)\n    def _conn(self, dsn):\n        self.dsn = dsn\n",
        "psycopg2.connect(self.dsn)", 'psycopg2.connect(os.getenv("TEST_URL"))'),
    "annotated": (
        HEAD + "    def setUp(self):\n        dsn: str = resolve_test_db_address(ROOT)\n        self.dsn = dsn\n",
        "psycopg2.connect(self.dsn)", 'psycopg2.connect(os.environ["TEST_URL"])'),
    "alias": (
        "from db_check.checker import resolve_test_db_address as resolve\n\n\n"
        + HEAD + "    def setUp(self):\n        self.dsn = resolve(ROOT)\n",
        "psycopg2.connect(self.dsn)", 'psycopg2.connect(os.environ["TEST_URL"])'),
    "kwargs": (
        HEAD + '    def setUp(self):\n        self.kw = {"dsn": resolve_test_db_address(ROOT)}\n',
        "psycopg2.connect(**self.kw)", 'psycopg2.connect(**{"dsn": os.environ["TEST_URL"]})'),
}


@pytest.mark.parametrize("name", sorted(RESOLVER_SHAPES))
def test_r2_5_every_shape_that_uses_the_resolved_address_passes(tmp_path, name):
    # covers: TQ-200d-4
    # angle: boundary
    # must_catch: db_test_uses_setting only follows a variable assigned and passed straight to connect
    shape, good, _bad = RESOLVER_SHAPES[name]
    r.expect_passes("test-writer", "cfg", tmp_path, test_file=(h.WRITER_TEST_FILE, r2.db_test(shape, good)))


@pytest.mark.parametrize("name", sorted(RESOLVER_SHAPES))
def test_r2_5_the_same_shape_connecting_with_an_env_value_still_fails(tmp_path, name):
    # covers: TQ-200d-4
    # angle: discrimination
    # must_catch: a looser check that accepts any resolver call beside a connect
    shape, _good, bad = RESOLVER_SHAPES[name]
    r.expect_fails("test-writer", "cfg", tmp_path, ("address", "literal", "resolve"), test_file=(h.WRITER_TEST_FILE, r2.db_test(shape, bad)))


def test_r2_l1_the_invoker_decodes_utf8_and_replaces_bad_bytes(tmp_path, monkeypatch):
    # covers: TQ-200d-4
    # angle: failure
    # must_catch: subprocess.run text mode uses the platform codec and can crash on agent output
    mod = h.module("produced_tests_transcript")
    seen: dict = {}

    def fake(cmd, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0, stdout=r.stream([CHECK]), stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake)
    mod.invoke_with_transcript("system", "do it", "sonnet", 5, tmp_path, "Read,Bash", RuntimeError)
    assert seen.get("encoding") == "utf-8" and seen.get("errors") == "replace", seen
    assert seen.get("capture_output") is True and seen.get("timeout") == 5, "control: the other kwargs are kept"


def test_r2_l8_the_test_runner_is_triggered_by_the_run_module():
    # covers: TQ-200d-4
    # angle: criterion
    # must_catch: a change to produced_tests_runs.py leaves the test-runner eval unmarked
    triggers = h.agent_config("test-runner")["triggers"]
    assert "scripts/evals/produced_tests_runs.py" in triggers
    assert "scripts/evals/produced_tests_scoring.py" in triggers, "control: the other scorer modules stay"
