"""Configuration, source validation and recovery regressions for the public CLI."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess

import pytest

# Shared subprocess fixtures keep consumer setup identical across CLI modules.
from . import test_background_worker_cli as shared_cli
from .test_background_worker_cli import (
    config_file,
    error,
    invoke,
    ok,
)

consumer = shared_cli.consumer
blocked_request = shared_cli.blocked_request

# covers: ACD-1300b-1-i
@pytest.mark.parametrize(
    "role,change",
    [
        ("implementation", {"model": 42}),
        ("reviewer", {"model": ["chosen"]}),
        ("reviewer", {"model": "   "}),
        ("implementation", {"provider": "hosted-service"}),
        ("reviewer", {"provider": "anthropic"}),
        ("reviewer", {"provider": "unknown-provider"}),
        ("implementation", {"executable": "untrusted-command"}),
        ("reviewer", {"executable": "silently-ignored-command"}),
    ],
)
def test_background_worker_rejects_unusable_or_ignored_executor_settings(consumer, role, change):
    path = Path(config_file(consumer))
    config = json.loads(path.read_text(encoding="utf-8"))
    config[role].update(change)
    path.write_text(json.dumps(config), encoding="utf-8")
    error(invoke(consumer, "configure", "--config", str(path)))
    status = ok(invoke(consumer, "status"))
    assert status["settings"]["enabled"] is False
    assert status["runs"] == []


# covers: ACD-1300b-1-i
def test_background_worker_nonfinite_poll_interval_cannot_be_persisted(consumer):
    path = config_file(consumer, poll_seconds=float("nan"))
    assert "poll" in error(invoke(consumer, "configure", "--config", path))
    assert ok(invoke(consumer, "status"))["settings"]["poll_seconds"] == 15


# covers: ACD-1300e-1
def test_background_worker_concurrent_answers_have_one_durable_winner(consumer, blocked_request):
    db, run, item = blocked_request
    answers = ["Use option A", "Use option B"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                invoke,
                consumer,
                "answer",
                run["id"],
                "--request-id",
                item["id"],
                "--answer",
                answer,
            )
            for answer in answers
        ]
        results = [future.result() for future in futures]
    assert sorted(result.returncode for result in results) == [0, 2]
    winner = next(answer for answer, result in zip(answers, results) if result.returncode == 0)
    from background_worker.store import Store

    with Store(db) as store:
        assert store.get_inbox(item["id"])["answer"] == winner
    status = ok(invoke(consumer, "status"))
    assert status["settings"]["enabled"] is False
    assert len(status["runs"]) == 1


# covers: ACD-1300f-3
def test_background_worker_malformed_ac_returns_structured_error(consumer):
    (consumer / "docs/acceptance-criteria/broken.yaml").write_text(
        "id: [unterminated", encoding="utf-8"
    )
    ok(invoke(consumer, "configure", "--config", config_file(consumer)))
    ok(invoke(consumer, "on", "--no-start"))
    message = error(invoke(consumer, "run", "--once"))
    assert any(word in message for word in ("yaml", "parse", "invalid"))
    status = ok(invoke(consumer, "status"))
    assert status["runs"] == []
    assert status["settings"]["enabled"] is False
    assert status["queue"]["error"]
    assert "yaml" in status["queue"]["error"].lower()


# covers: ACD-1300a-2-i, ACD-1300d-1
def test_background_worker_queue_exclusion_survives_reopened_status(consumer):
    import yaml

    # Plumbing constructs an empty target baseline without changing or committing
    # the source repository and without invoking any project commit hooks.
    def git(*args, input_text=None):
        try:
            result = subprocess.run(
                ["git", "-C", str(consumer), *args],
                input=input_text,
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            raise
        return result.stdout.strip()

    tree = git("hash-object", "-t", "tree", "-w", "--stdin", input_text="")
    commit = git(
        "-c",
        "user.name=Worker Test",
        "-c",
        "user.email=worker@example.invalid",
        "commit-tree",
        tree,
        "-m",
        "Empty test target",
    )
    git("update-ref", "refs/heads/test-target", commit)
    records = [
        {"id": "TEST-100", "level": "L0"},
        {"id": "TEST-100a", "level": "L1", "parent": "TEST-100", "depends_on": ["TEST-100"]},
        {
            "id": "TEST-100a-1",
            "level": "L2",
            "parent": "TEST-100a",
            "depends_on": ["TEST-100a"],
            "estimated_complexity": "L",
        },
    ]
    for record in records:
        record.update(
            status="active",
            readiness="approved",
            req_status="approved",
            work_status="todo",
            priority="low",
            criteria="Given input When run Then checked",
        )
        (consumer / "docs/acceptance-criteria" / (record["id"] + ".yaml")).write_text(
            yaml.safe_dump(record), encoding="utf-8"
        )
    ok(invoke(consumer, "configure", "--config", config_file(consumer, target_ref="test-target")))
    ok(invoke(consumer, "on", "--no-start"))
    run = ok(invoke(consumer, "run", "--once"))
    assert run["state"] == "waiting"
    assert run["excluded"]
    status = ok(invoke(consumer, "status"))
    assert status["runs"] == []
    assert status["queue"]["excluded"] == run["excluded"]
    assert status["queue"]["ready"] == []
    assert "TEST-100a" in json.dumps(status["queue"]["excluded"])
