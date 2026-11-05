"""
MODULE: unit_tests/evals/tq200d4/test_tq200d4_review3
GOAL: RED tests for the TQ-200d-4 review round 3 findings R3-1 (a crashed checker whose exit code
    is masked by a pipe or a trailing command) and R3-2 (name collisions in the resolved-address
    tracking of db_test_uses_setting), scored through the real scoring entry point on the real
    rows, each output being a row's gold output with one thing replaced. No model, no network.
Target: scripts/evals/produced_tests_commands.py, produced_tests_db.py
"""

from __future__ import annotations

import pytest

import unit_tests.evals.tq200d4._helpers as h
import unit_tests.evals.tq200d4._review2_helpers as r2
import unit_tests.evals.tq200d4._review_helpers as r

TRACEBACK = 'Traceback (most recent call last):\n  File "checker.py", line 3, in <module>\nImportError: no module named x'
NOISE = "warning: stderr line one\nwarning: stderr line two\n"


@pytest.mark.parametrize(
    "command",
    [
        "python scripts/db_check/checker.py --target-dir . 2>&1 | tail -5",
        "python scripts/db_check/checker.py --target-dir /nonexistent; echo done",
    ],
)
def test_r3_1_a_crashed_checker_with_a_masked_exit_code_is_not_a_run(tmp_path, command):
    # covers: TQ-200d-4
    # angle: discrimination
    # must_catch: a traceback in the result counts as a run because the pipe or echo hid the exit code
    r.expect_fails("test-runner", "cfg", tmp_path, ("checker",), transcript=r2.stream_calls([(command, TRACEBACK, False)]))


@pytest.mark.parametrize(
    ("command", "content"),
    [
        ("python scripts/db_check/checker.py --target-dir . 2>&1 | tail -5", NOISE + r2.INVALID_JSON),
        ("python scripts/db_check/checker.py --target-dir .", r2.INVALID_JSON),
    ],
)
def test_r3_1_a_piped_or_plain_run_holding_the_json_report_is_a_run(tmp_path, command, content):
    # covers: TQ-200d-4
    # angle: boundary
    # must_catch: a pipe or stderr noise before the report makes a real run fail
    r.expect_passes("test-runner", "cfg", tmp_path, transcript=r2.stream_calls([(command, content, False)]))


def _source(parts: str) -> str:
    """A produced database test module around *parts* (module-level definitions and one test)."""
    return (
        "import os\nimport sys\nfrom pathlib import Path\n\nimport pytest\n\n"
        'sys.path.insert(0, "scripts")\nfrom db_check.checker import resolve_test_db_address\n\nimport psycopg2\n\n'
        f"ROOT = Path.cwd()\n\n\n{parts}"
    )


def _test(connect: str, arg: str = "") -> str:
    return f"def test_a({arg}):\n    # covers: TQ-9401\n    {connect}\n"


COLLISIONS = {
    "fixture_vs_method": (
        '@pytest.fixture\ndef dsn():\n    return os.environ["X_URL"]\n\n\n'
        "class Helper:\n    @staticmethod\n    def dsn():\n        return resolve_test_db_address(ROOT)\n\n\n"
        + _test("psycopg2.connect(dsn)", "dsn")),
    "env_get_vs_function": (
        "def get():\n    return resolve_test_db_address(ROOT)\n\n\n" + _test('psycopg2.connect(os.environ.get("FOO"))')),
    "dict_get_vs_function": (
        "def get():\n    return resolve_test_db_address(ROOT)\n\n\n" + _test('psycopg2.connect({"a": "x"}.get("a"))')),
}


@pytest.mark.parametrize("name", sorted(COLLISIONS))
def test_r3_2_a_same_named_helper_does_not_make_a_foreign_value_the_setting(tmp_path, name):
    # covers: TQ-200d-4
    # angle: discrimination
    # must_catch: the resolved-address tracking goes by bare name, so a method or .get() of the same name taints a literal or env value
    r.expect_fails("test-writer", "cfg", tmp_path, ("address", "literal", "resolve"),
                   test_file=(h.WRITER_TEST_FILE, _source(COLLISIONS[name])))


def test_r3_2_the_plain_fixture_shape_still_passes(tmp_path):
    # covers: TQ-200d-4
    # angle: boundary
    # must_catch: tightening the name tracking rejects the round 2 fixture shape
    parts = "@pytest.fixture\ndef dsn():\n    return resolve_test_db_address(ROOT)\n\n\n" + _test("psycopg2.connect(dsn)", "dsn")
    r.expect_passes("test-writer", "cfg", tmp_path, test_file=(h.WRITER_TEST_FILE, _source(parts)))
