"""Exercise the public worker CLI in fresh processes without inference."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts" / "background_worker_cli.py"


@pytest.fixture
def consumer(tmp_path):
    repo = tmp_path / "consumer project"
    repo.mkdir()
    try:
        subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        raise
    (repo / "docs" / "acceptance-criteria").mkdir(parents=True)
    return repo


def invoke(repo, *args):
    # No real model executable is available to these subprocesses. The absolute
    # Python entry point also proves invocation is independent of caller cwd.
    env = os.environ.copy()
    git = shutil.which("git")
    assert git, "Git is required for the temporary consumer fixture"
    env["PATH"] = str(Path(git).parent)
    env.pop("PYTHONPATH", None)
    try:
        return subprocess.run(
            [sys.executable, str(CLI), "--repo", str(repo), *args],
            cwd=repo.parent,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise


def ok(result):
    assert result.returncode == 0, (result.stdout, result.stderr)
    return json.loads(result.stdout)


def error(result):
    assert result.returncode == 2, (result.stdout, result.stderr)
    payload = json.loads(result.stderr)
    assert payload["error"]
    return str(payload["error"]).lower()


def config_file(repo, **overrides):
    config = {
        "max_agent_calls": 1,
        "implementation": {
            "executor": "codex-cli",
            "provider": "ollama",
            "model": "qwen3.5:9b-q4_K_M",
            "endpoint": "http://localhost:11434",
        },
        "reviewer": {"executor": "codex-sdk", "model": "chosen-review-model"},
        "checks": [[sys.executable, "-c", "print('checked')"]],
    }
    config.update(overrides)
    path = repo / "worker-config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return str(path)


# covers: ACD-1300b-1
def test_background_worker_fresh_consumer_is_disabled_and_reachable(consumer):
    result = ok(invoke(consumer, "status"))
    assert result["settings"]["enabled"] is False
    assert result["settings"]["max_agent_calls"] == 1
    assert result["runs"] == []
    assert ok(invoke(consumer, "inbox"))["items"] == []


# covers: ACD-1300b-1, ACD-1300b-3
@pytest.mark.parametrize("reviewer", ["codex-sdk", "claude-agent-sdk"])
def test_background_worker_enable_persists_distinct_executor_models(consumer, reviewer):
    path = config_file(
        consumer,
        max_agent_calls=2,
        reviewer={"executor": reviewer, "model": "user-chosen-review-model"},
    )
    configured = ok(invoke(consumer, "configure", "--config", path))
    assert configured["settings"]["enabled"] is False
    ok(invoke(consumer, "on", "--no-start"))
    status = ok(invoke(consumer, "status"))
    assert status["settings"]["enabled"] is True
    assert status["settings"]["max_agent_calls"] == 2
    assert status["settings"]["implementation"]["model"] == "qwen3.5:9b-q4_K_M"
    assert status["settings"]["reviewer"]["executor"] == reviewer
    assert status["settings"]["reviewer"]["model"] == "user-chosen-review-model"
    assert status["runs"] == []
    ok(invoke(consumer, "off"))
    stopped = ok(invoke(consumer, "status"))
    assert stopped["settings"]["enabled"] is False
    assert stopped["settings"]["reviewer"]["model"] == "user-chosen-review-model"


# covers: ACD-1300b-1-i
@pytest.mark.parametrize("capacity", [0, -1, 1.5, True, "2"])
def test_background_worker_invalid_capacity_is_rejected_without_enabling(consumer, capacity):
    path = config_file(consumer, max_agent_calls=capacity)
    assert "max_agent_calls" in error(invoke(consumer, "configure", "--config", path))
    status = ok(invoke(consumer, "status"))
    assert status["settings"]["enabled"] is False
    assert status["runs"] == []


# covers: ACD-1300b-1-i
@pytest.mark.parametrize("checks", [[], ["pytest"], [[]], [[""]]])
def test_background_worker_missing_or_invalid_checks_are_rejected(consumer, checks):
    path = config_file(consumer, checks=checks)
    assert "check" in error(invoke(consumer, "configure", "--config", path))
    assert ok(invoke(consumer, "status"))["settings"]["enabled"] is False


# covers: ACD-1300b-1-i
def test_background_worker_unconfigured_enable_reports_required_correction(consumer):
    message = error(invoke(consumer, "on", "--no-start"))
    assert any(word in message for word in ("config", "reviewer", "check", "model"))
    assert ok(invoke(consumer, "status"))["runs"] == []


# covers: ACD-1300b-1-i
@pytest.mark.parametrize(
    "reviewer",
    [
        {"executor": "unregistered-harness", "model": "chosen"},
        {"executor": "codex-sdk", "model": ""},
    ],
)
def test_background_worker_invalid_reviewer_is_not_silently_replaced(consumer, reviewer):
    path = config_file(consumer, reviewer=reviewer)
    message = error(invoke(consumer, "configure", "--config", path))
    assert any(word in message for word in ("reviewer", "executor", "model"))
    assert ok(invoke(consumer, "status"))["runs"] == []


# covers: ACD-1300a-2-i, ACD-1300b-1
def test_background_worker_empty_queue_waits_without_model_executables(consumer):
    ok(invoke(consumer, "configure", "--config", config_file(consumer)))
    ok(invoke(consumer, "on", "--no-start"))
    result = ok(invoke(consumer, "run", "--once"))
    assert result["state"] == "waiting"
    assert ok(invoke(consumer, "status"))["runs"] == []


# covers: ACD-1300b-3
def test_background_worker_disabled_run_starts_no_feature(consumer):
    result = invoke(consumer, "run", "--once")
    if result.returncode == 0:
        assert ok(result)["state"] in ("disabled", "paused")
    else:
        assert "disabled" in error(result)
    assert ok(invoke(consumer, "status"))["runs"] == []


# covers: ACD-1300b-1
def test_background_worker_raw_credentials_are_never_persisted_or_echoed(consumer):
    sentinel = "test-secret-do-not-store-123"
    path = config_file(
        consumer,
        reviewer={"executor": "codex-sdk", "model": "chosen", "api_key": sentinel},
    )
    result = invoke(consumer, "configure", "--config", path)
    error(result)
    assert sentinel not in result.stdout + result.stderr
    assert sentinel not in invoke(consumer, "status").stdout
    state_dir = consumer / ".leafcutter" / "background-worker"
    for file in state_dir.rglob("*"):
        if file.is_file():
            assert sentinel.encode() not in file.read_bytes()


# covers: ACD-1300e-1
def test_background_worker_answer_unknown_request_does_not_invent_run(consumer):
    result = invoke(
        consumer, "answer", "missing-run", "--request-id", "missing-request", "--answer", "yes"
    )
    message = error(result)
    assert any(word in message for word in ("unknown", "missing", "not found"))
    assert ok(invoke(consumer, "status"))["runs"] == []
    assert ok(invoke(consumer, "inbox"))["items"] == []


@pytest.fixture
def blocked_request(consumer, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    from background_worker.store import Store

    db = consumer / ".leafcutter" / "background-worker" / "state.sqlite"
    with Store(db) as store:
        store.update_settings(enabled=True)
        run = store.claim_feature(
            {
                "feature_id": "TEST-100a",
                "ac_ids": ["TEST-100a-1"],
                "scope_digest": "source-revision",
            }
        )
        item = store.block_run(
            run["id"],
            "Choose the supported interface",
            {
                "ac_id": "TEST-100a-1",
                "evidence_refs": ["checks/failed.txt"],
            },
        )
        store.update_settings(enabled=False)
    return db, run, item


# covers: ACD-1300e-1, ACD-1300d-1
def test_background_worker_answer_while_disabled_persists_without_dispatch(
    consumer, blocked_request
):
    db, run, item = blocked_request
    before = ok(invoke(consumer, "inbox"))["items"]
    assert before[0]["id"] == item["id"]
    result = ok(
        invoke(
            consumer,
            "answer",
            run["id"],
            "--request-id",
            item["id"],
            "--answer",
            "Use the existing stable API",
        )
    )
    assert result["run_id"] == run["id"]
    status = ok(invoke(consumer, "status"))
    assert status["settings"]["enabled"] is False
    assert len(status["runs"]) == 1
    assert status["runs"][0]["state"] in ("blocked", "paused", "answered")
    from background_worker.store import Store

    with Store(db) as store:
        resolved = store.get_inbox(item["id"])
        assert resolved["answer"] == "Use the existing stable API"
        assert resolved["status"] == "resolved"
    assert "resolved" in error(
        invoke(
            consumer,
            "answer",
            run["id"],
            "--request-id",
            item["id"],
            "--answer",
            "Replace that answer",
        )
    )


# covers: ACD-1300e-1
def test_background_worker_other_run_cannot_answer_request(consumer, blocked_request):
    db, _, item = blocked_request
    error(
        invoke(consumer, "answer", "different-run", "--request-id", item["id"], "--answer", "yes")
    )
    from background_worker.store import Store

    with Store(db) as store:
        pending = store.get_inbox(item["id"])
        assert pending["status"] == "pending"
        assert pending["answer"] is None


# covers: ACD-1300d-2-i, ACD-1300d-1
def test_background_worker_notification_failure_keeps_durable_inbox(
    consumer, blocked_request, monkeypatch
):
    db, run, item = blocked_request
    from background_worker import notifications
    from background_worker.store import Store

    def unavailable(_message):
        raise OSError("No desktop session")

    monkeypatch.setattr(notifications, "_send", unavailable)
    with Store(db) as store:
        notifications.notify_outcomes(db, store)
    status = ok(invoke(consumer, "status"))
    assert status["runs"][0]["id"] == run["id"]
    assert status["runs"][0]["state"] == "blocked"
    assert status["notifications"][0]["state"] == "failed"
    inbox = ok(invoke(consumer, "inbox"))["items"]
    assert inbox[0]["id"] == item["id"]
    assert inbox[0]["details"]["evidence_refs"] == ["checks/failed.txt"]
    assert inbox[0]["status"] == "pending"
