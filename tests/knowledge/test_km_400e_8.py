"""KM-400e-8: an unset required backend setting fails loudly instead of being guessed.

Every test RUNS the synchronization job in a fresh subprocess (real argv, real ``main``) against a
backend double that records connection attempts. None of them reads the job definition for text.
Implementation target: the writer path (``knowledge.cli_sync.writer_backend``) and the merge workflow
must declare, never substitute, the database name and the writer username, and must name each unset
one, individually, before any connection is attempted.
"""

import json

from tests.knowledge import _km_400e_8_support as support
from tests.knowledge._km_400e_8_support import (
    DATABASE_SETTING,
    INSTANCE_DB,
    INSTANCE_USER,
    PASSWORD,
    USERNAME_SETTING,
    connections,
    declared,
    output_of,
    run_sync,
    run_workflow_job,
)


def test_unset_required_settings_fail_before_connecting_and_name_themselves(tmp_path):
    # covers: KM-400e-8
    # angle: criterion
    """Neither the database name nor the username declared: no connection, both named."""
    result = run_sync(tmp_path, declared(database=None, username=None))
    text = output_of(result)
    assert result.returncode != 0
    assert connections(tmp_path) == [], "a connection was attempted with an unset required setting"
    assert DATABASE_SETTING in text
    assert USERNAME_SETTING in text
    assert support.STOP_MARKER not in text, "the job proceeded past configuration"


def test_only_the_unset_setting_is_named(tmp_path):
    # covers: KM-400e-8
    # angle: boundary
    """Exactly one required setting unset: only that one is named; the control row mirrors it."""
    (tmp_path / "a").mkdir()
    only_database = run_sync(tmp_path / "a", declared(database=None))
    text = output_of(only_database)
    assert only_database.returncode != 0
    assert connections(tmp_path / "a") == [], "connected using a conventional database name"
    assert DATABASE_SETTING in text
    assert USERNAME_SETTING not in text

    (tmp_path / "b").mkdir()
    only_username = run_sync(tmp_path / "b", declared(username=None))
    text = output_of(only_username)
    assert only_username.returncode != 0
    assert connections(tmp_path / "b") == []
    assert USERNAME_SETTING in text
    assert DATABASE_SETTING not in text


def test_rejected_database_name_reports_the_name_and_its_source(tmp_path):
    # covers: KM-400e-8
    # angle: failure
    """A rejected database is reported with the requested name and its source, never as success."""
    requested = "declared-but-missing-db"
    result = run_sync(tmp_path, declared(database=requested), mode="reject_database")
    text = output_of(result)
    assert len(connections(tmp_path)) == 1
    assert result.returncode != 0, "a rejected database must not look like a successful run"
    assert requested in text, "the requested database name is not reported"
    assert DATABASE_SETTING in text, "the configuration source is not reported"
    for line in result.stdout.splitlines():
        if line.strip().startswith("{"):
            assert json.loads(line).get("status") not in {"ok", "empty"}


def test_declared_settings_are_used_verbatim_without_credentials_in_output(tmp_path):
    # covers: KM-400e-8
    # angle: criterion
    """Instance-specific declared values reach the connection unchanged; the password never appears."""
    result = run_sync(tmp_path, declared())
    attempts = connections(tmp_path)
    assert len(attempts) == 1
    assert attempts[0]["database"] == INSTANCE_DB
    assert attempts[0]["username"] == INSTANCE_USER
    assert attempts[0]["password"] == PASSWORD
    assert attempts[0]["uri"] == support.HOSTED_URI
    assert support.STOP_MARKER in output_of(result), "the job did not reach the backend"
    assert PASSWORD not in output_of(result)


def test_synchronization_job_runs_end_to_end_with_unset_and_declared_settings(tmp_path):
    # covers: KM-400e-8
    # angle: deployed
    """Run the merge workflow's own steps and env: unset database fails first, declared connects."""
    secrets = {
        "LEAFCUTTER_NEO4J_URI": support.HOSTED_URI,
        "LEAFCUTTER_NEO4J_WRITER_USERNAME": INSTANCE_USER,
        "LEAFCUTTER_NEO4J_WRITER_PASSWORD": PASSWORD,
    }
    unset_dir = tmp_path / "unset"
    unset_dir.mkdir()
    code, text = run_workflow_job(unset_dir, secrets, {"KNOWLEDGE_SYNC_ENABLED": "true"})
    assert code != 0
    assert connections(unset_dir) == [], "the job substituted a database name and connected"
    assert DATABASE_SETTING in text

    declared_dir = tmp_path / "declared"
    declared_dir.mkdir()
    code, text = run_workflow_job(
        declared_dir, secrets,
        {"KNOWLEDGE_SYNC_ENABLED": "true", DATABASE_SETTING: INSTANCE_DB},
    )
    attempts = connections(declared_dir)
    assert len(attempts) == 1
    assert attempts[0]["database"] == INSTANCE_DB
    assert attempts[0]["username"] == INSTANCE_USER
    assert support.STOP_MARKER in text
    assert PASSWORD not in text


def test_km400_e_5_behavior(tmp_path):
    # covers: KM-400e-5
    # angle: criterion
    """The job ends with a failure naming an unset required backend setting; declared ones sync on."""
    result = run_sync(tmp_path, declared(database=None))
    assert result.returncode != 0
    assert connections(tmp_path) == []
    assert DATABASE_SETTING in output_of(result)

    (tmp_path / "ok").mkdir()
    bound = ("--retention-max-generations", "3", "--retention-min-age-seconds", "7200")
    proceeded = run_sync(tmp_path / "ok", declared(), extra_args=bound)
    assert len(connections(tmp_path / "ok")) == 1
    assert support.STOP_MARKER in output_of(proceeded)


def test_km400_e_5_public_reachability(tmp_path):
    # covers: KM-400e-5
    # angle: reachability
    """Through the merge workflow's real steps, the unset setting's failure is consumed as the job exit."""
    secrets = {
        "LEAFCUTTER_NEO4J_URI": support.HOSTED_URI,
        "LEAFCUTTER_NEO4J_WRITER_USERNAME": INSTANCE_USER,
        "LEAFCUTTER_NEO4J_WRITER_PASSWORD": PASSWORD,
    }
    code, text = run_workflow_job(tmp_path, secrets, {"KNOWLEDGE_SYNC_ENABLED": "true"})
    assert code != 0
    assert connections(tmp_path) == []
    assert DATABASE_SETTING in text
