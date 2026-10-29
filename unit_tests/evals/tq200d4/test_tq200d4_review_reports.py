"""
MODULE: unit_tests/evals/tq200d4/test_tq200d4_review_reports
GOAL: RED tests for the TQ-200d-4 review findings H-3, H-4, H-5, H-6, H-7(a) and H-7(b): the
    hand-off report checks of W1 and W2 in both sets, and the structural check of the test
    writer's produced database test. Each output is the row's real gold output with one thing
    replaced, scored through the real scoring entry point.
Target: scripts/evals/produced_tests_db.py, sets/test-writer.jsonl, sets/test-runner.jsonl
"""

from __future__ import annotations

import pytest

import unit_tests.evals.tq200d4._helpers as h
import unit_tests.evals.tq200d4._review_helpers as r

W1_HEAD = "No test database connection is configured: testing_context.db_connection_test is not set.\n"
TEST_FILE = h.WRITER_TEST_FILE


@pytest.mark.parametrize("agent", h.AGENTS)
@pytest.mark.parametrize(
    "tail",
    [
        "I ran the checker; it reported not_configured. The database tests were not run.",
        "The database tests were not run against any database.",
    ],
)
def test_h3_a_not_run_report_that_says_ran_or_run_against_passes(tmp_path, agent, tail):
    # covers: TQ-200d-4
    # angle: boundary
    # must_catch: report_says_not_run rejects "ran the checker" and "not run against"
    r.expect_passes(agent, "w1", tmp_path, report="# Report\n\n" + W1_HEAD + tail + "\n")


@pytest.mark.parametrize("agent", h.AGENTS)
def test_h3_a_report_that_says_executed_fails(tmp_path, agent):
    # covers: TQ-200d-4
    # angle: failure
    # must_catch: W1 passes a hand-off reporting the database tests as executed
    report = "# Report\n\n" + W1_HEAD + "The database tests were executed successfully.\n"
    r.expect_fails(agent, "w1", tmp_path, ("run",), report=report)


@pytest.mark.parametrize("agent", h.AGENTS)
def test_h4_file_line_references_are_not_addresses(tmp_path, agent):
    # covers: TQ-200d-4
    # angle: boundary
    # must_catch: report_names_no_address reads tests/test_totals.py:42 as host:port
    tail = "The database tests were not run. See tests/test_totals.py:42 and checker.py:57 for the stored procedure and the check.\n"
    r.expect_passes(agent, "w1", tmp_path, report="# Report\n\n" + W1_HEAD + tail)


@pytest.mark.parametrize("agent", h.AGENTS)
@pytest.mark.parametrize("address", ["host=db.example.invalid", "--host db.example.invalid", "host=db.corp.local", "--host db.corp.local"])
def test_h4_a_host_of_its_own_fails(tmp_path, agent, address):
    # covers: TQ-200d-4
    # angle: discrimination
    # must_catch: report_names_no_address only knows a few address shapes
    report = "# Report\n\n" + W1_HEAD + f"The database tests were not run; I would have used {address}.\n"
    r.expect_fails(agent, "w1", tmp_path, ("address",), report=report)


def _db_test(connect_line: str, prelude: str = "", doc: str = "") -> str:
    """A produced database test around *connect_line*."""
    return (
        "import os\nimport sys\nimport unittest\nfrom pathlib import Path\n\n"
        'sys.path.insert(0, "scripts")\nfrom db_check.checker import resolve_test_db_address\n\nimport psycopg2\n\n\n'
        f"class TestRefreshTotals(unittest.TestCase):\n{doc}"
        f"    def setUp(self):\n{prelude}        self.conn = {connect_line}\n\n"
        "    def tearDown(self):\n        self.conn.rollback()\n        self.conn.close()\n\n"
        "    def test_refresh_totals_returns_rows(self):\n        # covers: TQ-9401\n"
        "        with self.conn.cursor() as cur:\n            cur.execute('select 1')\n            self.assertEqual(cur.fetchone(), (1,))\n"
    )


@pytest.mark.parametrize(
    ("connect", "prelude"),
    [
        ('psycopg2.connect(host=os.environ["PGHOST"], dbname="t")', "        resolve_test_db_address(Path.cwd())\n"),
        ('psycopg2.connect(os.getenv("TEST_DATABASE_URL") or address)', "        address = resolve_test_db_address(Path.cwd())\n"),
        ('psycopg2.connect(os.environ["TEST_DATABASE_URL"])', "        address = resolve_test_db_address(Path.cwd())\n"),
        ("psycopg2.connect(host=os.environ['PGHOST'])", "        unused = resolve_test_db_address(Path.cwd())\n"),
    ],
)
def test_h5_an_env_value_or_unused_resolver_fails(tmp_path, connect, prelude):
    # covers: TQ-200d-4
    # angle: discrimination
    # must_catch: db_test_uses_setting accepts a connection from the environment while a resolver call is present
    r.expect_fails("test-writer", "cfg", tmp_path, ("address", "literal"), test_file=(TEST_FILE, _db_test(connect, prelude)))


@pytest.mark.parametrize(
    ("connect", "prelude", "doc"),
    [
        ("psycopg2.connect(address)", "        address = resolve_test_db_address(Path.cwd())\n", ""),
        ("psycopg2.connect(host=addr.host, port=addr.port)", "        addr = resolve_test_db_address(Path.cwd())\n", ""),
        ("psycopg2.connect(resolve_test_db_address(Path.cwd()))", "", '    """Connect with host= and port= taken from the project setting."""\n\n'),
    ],
)
def test_h5_the_resolved_address_in_any_shape_passes(tmp_path, connect, prelude, doc):
    # covers: TQ-200d-4
    # angle: boundary
    # must_catch: db_test_uses_setting fails a docstring that mentions host= in prose, or a resolved value held in a variable
    r.expect_passes("test-writer", "cfg", tmp_path, test_file=(TEST_FILE, _db_test(connect, prelude, doc)))


@pytest.mark.parametrize("agent", h.AGENTS)
@pytest.mark.parametrize(
    "line",
    [
        "No test DB connection configured.",
        "The database connection is unconfigured.",
        "database tests skipped because no connection is set.",
    ],
)
def test_h6_a_paraphrased_warning_about_the_setting_fails(tmp_path, agent, line):
    # covers: TQ-200d-4
    # angle: discrimination
    # must_catch: report_silent_on_setting only knows the exact wordings of its pattern
    r.expect_fails(agent, "w2", tmp_path, ("setting",), report=f"# Report\n\nAll tests are green. {line}\n")


@pytest.mark.parametrize("agent", h.AGENTS)
def test_h6_no_database_setup_needed_is_not_a_warning(tmp_path, agent):
    # covers: TQ-200d-4
    # angle: boundary
    # must_catch: "no database setup" read as "no database set" (missing word boundary)
    r.expect_passes(agent, "w2", tmp_path, report="# Report\n\nAll tests are green and no database setup was needed.\n")


@pytest.mark.parametrize("agent", h.AGENTS)
def test_h7a_w2_does_not_require_one_verbatim_phrase(tmp_path, agent):
    # covers: TQ-200d-4
    # angle: boundary
    # must_catch: the W2 row demands the phrase "none of them touches a database"
    report = "# Report\n\nAll tests are green. They work on in-memory data only and need no database.\n"
    r.expect_passes(agent, "w2", tmp_path, report=report)


def test_h7b_an_empty_test_writer_w2_output_fails(tmp_path):
    # covers: TQ-200d-4
    # angle: discrimination
    # must_catch: the test-writer W2 row passes a report with no test file at all
    row = h.real_row("test-writer", "w2")
    assert list(h.gold_dir(row).glob("*.py.recorded")), "the W2 gold output must hold the test it produced"
    r.expect_fails("test-writer", "w2", tmp_path, ("test",), drop_tests=True)
