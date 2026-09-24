"""Real Git evidence and durable notification failure tests."""

import json
from pathlib import Path
import subprocess
import sys
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from background_worker.sources import load_records, target_completed
from background_worker.store import Store
from background_worker import notifications


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )


# covers: ACD-1300f-2
def test_uncommitted_done_flag_cannot_satisfy_external_dependency(tmp_path):
    git(tmp_path, "init")
    folder = tmp_path / "docs/acceptance-criteria/demo"
    folder.mkdir(parents=True)
    ac = {"id": "DEM-100a-1", "work_status": "todo", "implemented_by": []}
    path = folder / "DEM-100a-1.yaml"
    path.write_text(yaml.safe_dump(ac))
    git(tmp_path, "add", ".")
    git(
        tmp_path,
        "-c",
        "user.name=Worker Test",
        "-c",
        "user.email=worker@example.invalid",
        "commit",
        "-m",
        "baseline",
    )
    ac.update(work_status="done", implemented_by=["scripts/example.py"])
    path.write_text(yaml.safe_dump(ac))
    assert load_records(tmp_path)[ac["id"]]["work_status"] == "done"
    assert ac["id"] not in target_completed(tmp_path, "HEAD")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/example.py").write_text("# completed implementation evidence\n")
    git(tmp_path, "add", ".")
    git(
        tmp_path,
        "-c",
        "user.name=Worker Test",
        "-c",
        "user.email=worker@example.invalid",
        "commit",
        "-m",
        "completed declaration",
    )
    assert ac["id"] in target_completed(tmp_path, "HEAD")


# covers: ACD-1300d-2, ACD-1300d-2-i
def test_notification_failure_preserves_request_and_does_not_repeat(tmp_path, monkeypatch):
    db = tmp_path / "state.sqlite"
    with Store(db) as store:
        store.update_settings(enabled=True)
        run = store.claim_feature({"feature_id": "DEM-100a", "ac_ids": ["DEM-100a-1"]})
        store.block_run(run["id"], "Needs answer", {"evidence": "retained"})
        calls = []

        def unavailable(message):
            calls.append(message)
            raise FileNotFoundError("No desktop notifier")

        monkeypatch.setattr(notifications, "_send", unavailable)
        notifications.notify_outcomes(db, store)
        notifications.notify_outcomes(db, store)
        assert len(calls) == 1
        assert store.list_inbox()[0]["details"]["evidence"] == "retained"
        assert store.get_run(run["id"])["state"] == "blocked"
    assert notifications.notification_status(db)[0]["state"] == "failed"


# covers: ACD-1300f-3
def test_duplicate_source_identity_is_not_silently_overwritten(tmp_path):
    import pytest

    root = tmp_path / "docs/acceptance-criteria"
    root.mkdir(parents=True)
    for name in ("one.yaml", "two.yaml"):
        (root / name).write_text("id: DEM-100a-1\n")
    with pytest.raises(ValueError, match="Duplicate AC"):
        load_records(tmp_path)


# covers: ACD-1300e-1, ACD-1300c-2
def test_resumed_context_binds_answers_to_original_questions(tmp_path):
    from scripts.background_worker.store import Store
    from scripts.background_worker.engine import WorkerEngine

    with Store(tmp_path / "state.sqlite") as store:
        store.update_settings(enabled=True)
        run = store.claim_feature(
            {
                "feature_id": "ACD-1300e",
                "ac_ids": ["ACD-1300e-1"],
                "execution_order": ["ACD-1300e-1"],
                "scope_digest": "scope",
                "source_context": {},
            }
        )
        request = store.block_run(
            run["id"],
            "Implementation needs user input",
            {"questions": ["Use the existing public interface?"]},
        )
        store.answer_request(run["id"], request["id"], "Yes")
        context = json.loads(
            WorkerEngine.implementation_context(
                run["plan"], "ACD-1300e-1", store.get_run(run["id"])["payload"]
            )
        )
        bound = context["answered_requests"][request["id"]]
        assert bound["answer"] == "Yes"
        assert bound["details"]["questions"] == ["Use the existing public interface?"]
