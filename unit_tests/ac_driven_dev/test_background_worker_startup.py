"""Real detached service startup reports readiness and durable early failures."""

import json
from pathlib import Path
import time

import pytest

from scripts.background_worker.locks import exclusive
from scripts.background_worker.startup import start_background, startup_status
from scripts.background_worker.store import Store


@pytest.fixture
def startup_repo(tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()
    state = repo / ".leafcutter" / "background-worker"
    state.mkdir(parents=True)
    with Store(state / "state.sqlite") as store:
        store.update_settings(
            poll_seconds=1, reviewer={"executor": "codex-sdk", "model": "test"}, checks=[["check"]]
        )
    return repo, state


def test_early_child_exit_rolls_back_enablement_and_records_failure(startup_repo):
    # covers: ACD-1300b-2, ACD-1300e-3
    repo, state = startup_repo
    broken = repo / "broken.py"
    broken.write_text("raise SystemExit(7)\n")
    (state / "service-status.json").write_text(json.dumps({"state": "running", "token": "old"}))
    with pytest.raises(OSError, match="before startup"):
        start_background(repo, state, entrypoint=broken)
    with Store(state / "state.sqlite") as store:
        assert not store.get_settings()["enabled"]
    assert startup_status(state)["last_launch"]["state"] == "failed"


def test_missing_readiness_times_out_without_leaving_enabled_worker(startup_repo):
    # covers: ACD-1300b-2, ACD-1300e-3
    repo, state = startup_repo
    stalled = repo / "stalled.py"
    stalled.write_text("import time\ntime.sleep(30)\n")
    with pytest.raises(OSError, match="timed out"):
        start_background(repo, state, entrypoint=stalled, timeout=0.2)
    with Store(state / "state.sqlite") as store:
        assert not store.get_settings()["enabled"]


def test_on_existing_service_is_idempotent_without_launching_child(startup_repo, monkeypatch):
    # covers: ACD-1300b-2
    repo, state = startup_repo
    monkeypatch.setattr(
        "scripts.background_worker.startup.subprocess.Popen",
        lambda *a, **k: pytest.fail("duplicate process"),
    )
    with exclusive(state / "service.lock") as owned:
        assert owned
        assert start_background(repo, state)["state"] == "already_running"
    with Store(state / "state.sqlite") as store:
        assert store.get_settings()["enabled"]


def test_external_supervisor_enablement_respects_startup_recovery_lock(startup_repo, monkeypatch):
    # covers: ACD-1300b-2, ACD-1300e-3
    from scripts.background_worker import cli

    repo, state = startup_repo
    monkeypatch.setattr(cli, "repo_path", lambda value: repo)
    with exclusive(state / "startup.lock") as owned:
        assert owned
        assert cli.main(["--repo", str(repo), "on", "--no-start"]) == 2
    with Store(state / "state.sqlite") as store:
        assert not store.get_settings()["enabled"]


def test_real_detached_service_acknowledges_its_token_and_drains_off(startup_repo):
    # covers: ACD-1300b-2, ACD-1300e-3
    repo, state = startup_repo
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    entry = repo / "entry.py"
    entry.write_text(
        "import sys\nfrom pathlib import Path\nsys.path.insert(0," + repr(str(scripts)) + ")\n"
        "from background_worker.service import run_service\n"
        "run_service(Path(sys.argv[2]), Path(sys.argv[2])/'.leafcutter/background-worker/state.sqlite')\n"
    )
    try:
        result = start_background(repo, state, entrypoint=entry)
        assert result["state"] == "running"
        assert startup_status(state)["last_launch"]["token"] == result["token"]
    finally:
        with Store(state / "state.sqlite") as store:
            store.update_settings(enabled=False)
    deadline = time.monotonic() + 5
    while (
        time.monotonic() < deadline and startup_status(state)["service"].get("state") == "running"
    ):
        time.sleep(0.05)
    assert startup_status(state)["service"]["state"] == "stopped"
