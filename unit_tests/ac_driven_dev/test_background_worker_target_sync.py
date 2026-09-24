"""Target completion must observe remote merges without any hosted service."""

import subprocess

import pytest
import yaml

from scripts.background_worker.sources import refresh_target, target_completed


def git(repo, *args):
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        raise
    return result.stdout.strip()


def initialize(path, *, bare=False):
    path.mkdir()
    git(path, "init", *(["--bare"] if bare else []))
    git(path, "symbolic-ref", "HEAD", "refs/heads/main")
    return path


def save_target(repo, *, done, parent=None):
    store = repo / "docs/acceptance-criteria/test"
    store.mkdir(parents=True, exist_ok=True)
    evidence = repo / "tests/evidence.txt"
    evidence.parent.mkdir(exist_ok=True)
    evidence.write_text("Executed target-branch check evidence", encoding="utf-8")
    record = {
        "id": "TEST-200a-1",
        "level": "L2",
        "status": "active",
        "work_status": "done" if done else "todo",
        "implemented_by": ["tests/evidence.txt"],
    }
    (store / "TEST-200a-1.yaml").write_text(yaml.safe_dump(record), encoding="utf-8")
    git(repo, "add", "--all")
    tree = git(repo, "write-tree")
    # Construct fixture history with Git plumbing; no project hook or source
    # repository commit is involved.
    parents = ["-p", parent] if parent else []
    sha = git(
        repo,
        "-c",
        "user.name=Worker Test",
        "-c",
        "user.email=worker@example.invalid",
        "commit-tree",
        tree,
        *parents,
        "-m",
        "Target evidence fixture",
    )
    git(repo, "update-ref", "refs/heads/main", sha)
    return sha


# covers: ACD-1300f-2, ACD-1300a-2-i
def test_background_worker_fetch_observes_new_remote_completion(tmp_path):
    remote = initialize(tmp_path / "origin.git", bare=True)
    author = initialize(tmp_path / "author")
    initial = save_target(author, done=False)
    git(author, "remote", "add", "origin", str(remote))
    git(author, "push", "origin", "main")
    consumer = initialize(tmp_path / "consumer")
    git(consumer, "remote", "add", "origin", str(remote))
    refresh_target(consumer, "origin/main")
    assert "TEST-200a-1" not in target_completed(consumer, "origin/main")

    merged = save_target(author, done=True, parent=initial)
    git(author, "push", "origin", "main")
    assert git(consumer, "rev-parse", "origin/main") == initial
    assert "TEST-200a-1" not in target_completed(consumer, "origin/main")
    refresh_target(consumer, "origin/main")
    assert git(consumer, "rev-parse", "origin/main") == merged
    assert target_completed(consumer, "origin/main") == {"TEST-200a-1"}


# covers: ACD-1300f-2
def test_background_worker_local_target_needs_no_remote(tmp_path):
    repo = initialize(tmp_path / "offline")
    initial = save_target(repo, done=True)
    assert git(repo, "remote") == ""
    refresh_target(repo, "main")
    assert git(repo, "rev-parse", "main") == initial
    assert target_completed(repo, "main") == {"TEST-200a-1"}


# covers: ACD-1300f-2
def test_background_worker_unknown_tracking_remote_does_not_use_stale_evidence(tmp_path):
    repo = initialize(tmp_path / "missing-remote")
    save_target(repo, done=True)
    with pytest.raises(ValueError, match="(?i)(remote|target)"):
        refresh_target(repo, "missing/main")


# covers: ACD-1300f-2, ACD-1300e-3
def test_target_evidence_is_pinned_when_ref_moves_during_read(tmp_path, monkeypatch):
    from scripts.background_worker import sources

    repo = initialize(tmp_path / "moving")
    original = save_target(repo, done=False)
    latest = save_target(repo, done=True, parent=original)
    git(repo, "update-ref", "refs/heads/main", original)
    invoke = sources._run_git

    def advance_before_archive(argv, **kwargs):
        if "archive" in argv:
            git(repo, "update-ref", "refs/heads/main", latest)
        return invoke(argv, **kwargs)

    monkeypatch.setattr(sources, "_run_git", advance_before_archive)
    assert sources.target_completed(repo, "main") == set()
    assert git(repo, "rev-parse", "main") == latest
