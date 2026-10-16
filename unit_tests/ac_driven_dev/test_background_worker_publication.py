"""Controlled publication requires one explicit Git and GitHub destination."""

import json
from pathlib import Path
import subprocess

import pytest

from scripts.background_worker.executors import ExecutorError


@pytest.fixture
def publisher(tmp_path, monkeypatch):
    from scripts.background_worker.git_ops import GitOps

    state = {"entries": [], "creates": 0, "pushes": 0, "body": "", "lose_create_response": False}
    state.update(
        remote_urls={"origin": "https://example.test/owner/repo"},
        push_urls={},
        gh_calls=[],
        git_calls=[],
        tracking={},
    )
    state.update(base_sha="base", refreshes=[])
    monkeypatch.setattr(
        "scripts.background_worker.sources.refresh_target",
        lambda repo, target, **kwargs: state["refreshes"].append(target),
    )
    run = {
        "id": "run",
        "feature_id": "ACD-1300g",
        "workspace": str(tmp_path),
        "plan": {
            "ac_ids": ["ACD-1300g-4"],
            "source_context": {"obligations": {"ACD-1300g-4": {}}, "source_revision": "revision"},
        },
        "payload": {
            "branch": "codex/test",
            "base_sha": "base",
            "validated_sha": "head",
            "review": {"disposition": "approved"},
        },
    }
    source = tmp_path / "docs" / "acceptance-criteria" / "ACD-1300g-4.yaml"
    source.parent.mkdir(parents=True)
    source.write_text("id: ACD-1300g-4")

    def invoke(argv, **kwargs):
        state["gh_calls"].append(argv)
        if argv[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(argv, 0, json.dumps(state["entries"]), "")
        if argv[:3] == ["gh", "repo", "view"]:
            return subprocess.CompletedProcess(argv, 0, json.dumps({"url": argv[3]}), "")
        assert argv[:3] == ["gh", "pr", "create"]
        state["creates"] += 1
        state["body"] = Path(argv[argv.index("--body-file") + 1]).read_text()
        state["entries"] = [
            {
                "url": "https://example.test/pr/1",
                "headRefOid": "head",
                "isDraft": True,
                "state": "OPEN",
                "baseRefName": "main",
            }
        ]
        if state["lose_create_response"]:
            raise ExecutorError("Transport interrupted after publication")
        return subprocess.CompletedProcess(argv, 0, "created", "")

    coordinator = GitOps(tmp_path, {"target_ref": "origin/main"}, invoke=invoke)
    coordinator.assert_workspace = lambda run: tmp_path
    coordinator.head = lambda workspace: "head"
    coordinator._assert_hooks_safe = lambda workspace: None

    def git(workspace, *args):
        state["git_calls"].append(args)
        if args[0] == "remote":
            if len(args) == 1:
                return "\n".join(state["remote_urls"])
            if "--push" in args:
                return state["push_urls"].get(args[-1], state["remote_urls"][args[-1]])
            return state["remote_urls"][args[-1]]
        if args[0] == "config":
            return state["tracking"].get(args[-1], "")
        if args[0] == "rev-parse":
            return state["base_sha"]
        if args[0] == "push":
            state["pushes"] += 1
        return ""

    coordinator.git = git
    coordinator.hooked_git = lambda workspace, owned, *args: git(workspace, *args)
    return coordinator, run, state


def test_publisher_requires_exact_head_before_push(publisher):
    # covers: ACD-1300g-4, ACD-1300g-4-i
    coordinator, run, state = publisher
    with pytest.raises(ExecutorError, match="Head changed"):
        coordinator.publish(run, "other")
    assert state["creates"] == state["pushes"] == 0


@pytest.mark.parametrize("target", ["upstream/main", "refs/remotes/upstream/main"])
def test_non_origin_target_binds_push_and_every_github_operation(publisher, target):
    # covers: ACD-1300g-4, ACD-1300g-4-i
    coordinator, run, state = publisher
    coordinator.settings["target_ref"] = target
    state["remote_urls"]["upstream"] = "git@example.test:team/canonical.git"
    coordinator.publish(run, "head")
    pushes = [args for args in state["git_calls"] if args[0] == "push"]
    assert pushes == [
        ("push", "--set-upstream", "upstream", "refs/heads/codex/test:refs/heads/codex/test")
    ]
    for argv in state["gh_calls"]:
        if argv[:3] == ["gh", "repo", "view"]:
            assert argv[3] == "https://example.test/team/canonical"
        else:
            assert argv[argv.index("--repo") + 1] == "https://example.test/team/canonical"
    assert "/team/canonical/blob/head/" in state["body"]


@pytest.mark.parametrize(
    "target,tracking,expected",
    [
        ("main", {}, "origin"),
        (
            "refs/heads/main",
            {"branch.main.remote": "upstream", "branch.main.merge": "refs/heads/main"},
            "upstream",
        ),
    ],
)
def test_local_branch_uses_tracking_remote_or_documented_origin_fallback(
    publisher, target, tracking, expected
):
    # covers: ACD-1300g-4
    coordinator, run, state = publisher
    coordinator.settings["target_ref"] = target
    state["remote_urls"]["upstream"] = "https://example.test/team/canonical.git"
    state["tracking"] = tracking
    coordinator.publish(run, "head")
    assert next(args for args in state["git_calls"] if args[0] == "push")[2] == expected


@pytest.mark.parametrize(
    "push_url",
    [
        "https://example.test/different/repo.git",
        "https://example.test/owner/repo\nhttps://example.test/other/repo",
    ],
)
def test_ambiguous_or_different_push_repository_refuses_all_publication(publisher, push_url):
    # covers: ACD-1300g-4-i
    coordinator, run, state = publisher
    state["push_urls"]["origin"] = push_url
    with pytest.raises(ExecutorError):
        coordinator.publish(run, "head")
    assert not state["gh_calls"] and state["pushes"] == 0


def test_local_only_tracking_does_not_fall_back_to_another_remote(publisher):
    # covers: ACD-1300g-4-i
    coordinator, run, state = publisher
    coordinator.settings["target_ref"] = "main"
    state["tracking"] = {"branch.main.remote": ".", "branch.main.merge": "refs/heads/main"}
    with pytest.raises(ExecutorError, match="tracking remote"):
        coordinator.publish(run, "head")
    assert state["pushes"] == 0 and not state["gh_calls"]


def test_local_target_cannot_publish_against_different_remote_base(publisher):
    # covers: ACD-1300g-4-i
    coordinator, run, state = publisher
    coordinator.settings["target_ref"] = "main"
    state["base_sha"] = "remote-advanced"
    with pytest.raises(ExecutorError, match="remote base differs"):
        coordinator.publish(run, "head")
    assert state["refreshes"] == ["origin/main"]
    assert state["pushes"] == 0 and not state["gh_calls"]


def test_real_remote_refresh_refuses_unpublished_local_base_commits(tmp_path):
    # covers: ACD-1300g-4-i
    from scripts.background_worker.git_ops import GitOps

    repo, remote = tmp_path / "repo", tmp_path / "origin.git"
    repo.mkdir()
    remote.mkdir()

    def git(directory, *argv):
        try:
            return subprocess.run(
                ["git", "-C", str(directory), *argv], check=True, capture_output=True, text=True
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            raise

    git(remote, "init", "--bare")
    git(repo, "init", "--initial-branch=main")
    git(repo, "config", "user.name", "Publication test")
    git(repo, "config", "user.email", "publication@example.test")
    git(repo, "commit", "--allow-empty", "-m", "published base")
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "origin", "main")
    git(repo, "commit", "--allow-empty", "-m", "unpublished local base")
    local_base = git(repo, "rev-parse", "HEAD")
    coordinator = GitOps(repo, {"target_ref": "main"})
    with pytest.raises(ExecutorError, match="remote base differs"):
        coordinator.verify_publication_base(repo, {"remote": "origin", "base": "main"}, local_base)


@pytest.mark.parametrize("target", ["upstream/main", "refs/remotes/upstream/main", "main"])
def test_destination_resolves_actual_git_remote_configuration(tmp_path, target):
    # covers: ACD-1300g-4
    from scripts.background_worker.git_ops import GitOps

    def git(*argv):
        try:
            subprocess.run(["git", "-C", str(tmp_path), *argv], check=True, capture_output=True)
        except (OSError, subprocess.SubprocessError):
            raise

    git("init")
    git("remote", "add", "origin", "https://github.com/fork/project.git")
    git("remote", "add", "upstream", "git@github.com:canonical/project.git")
    git("remote", "set-url", "--push", "upstream", "https://github.com/canonical/project.git")
    git("config", "branch.main.remote", "upstream")
    git("config", "branch.main.merge", "refs/heads/main")
    assert GitOps(tmp_path, {"target_ref": target}).publication_destination(tmp_path) == {
        "remote": "upstream",
        "base": "main",
        "repository": "https://github.com/canonical/project",
    }


def test_nul_delimited_git_output_preserves_leading_filename_whitespace(tmp_path):
    # covers: ACD-1300g-1, ACD-1300g-2
    from scripts.background_worker.git_ops import GitOps

    name = "  leading filename.txt"
    (tmp_path / name).write_text("content")
    try:
        subprocess.run(["git", "-C", str(tmp_path), "init"], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(tmp_path), "add", "--", name], check=True, capture_output=True
        )
    except (OSError, subprocess.SubprocessError):
        raise
    assert GitOps(tmp_path, {}).git(tmp_path, "ls-files", "-z") == name + "\0"


def test_uncertain_publication_reconciles_without_duplicate_pr(publisher):
    # covers: ACD-1300g-4, ACD-1300g-4-i
    coordinator, run, state = publisher
    state["lose_create_response"] = True
    with pytest.raises(ExecutorError):
        coordinator.publish(run, "head")
    assert coordinator.publish(run, "head") == "https://example.test/pr/1"
    assert state["creates"] == state["pushes"] == 1
    assert (
        "[ACD-1300g-4](https://example.test/owner/repo/blob/head/docs/acceptance-criteria/ACD-1300g-4.yaml)"
        in state["body"]
    )
    assert '"validated_sha": "head"' in state["body"]


@pytest.mark.parametrize(
    "field,value",
    [("isDraft", False), ("state", "CLOSED"), ("baseRefName", "other"), ("headRefOid", "stale")],
)
def test_existing_unexpected_pr_is_never_reused(publisher, field, value):
    # covers: ACD-1300g-4-i
    coordinator, run, state = publisher
    state["entries"] = [
        {
            "url": "https://example.test/pr/1",
            "headRefOid": "head",
            "isDraft": True,
            "state": "OPEN",
            "baseRefName": "main",
            field: value,
        }
    ]
    with pytest.raises(ExecutorError, match="Existing PR"):
        coordinator.publish(run, "head")
    assert state["creates"] == state["pushes"] == 0
