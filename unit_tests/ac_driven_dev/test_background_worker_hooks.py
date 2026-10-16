"""Real Git hooks execute inside the coordinator's Linux namespace boundary."""

import os
import shutil
import subprocess
import sys

import pytest

from scripts.background_worker.git_hooks import GitHookSandbox
from scripts.background_worker.execution_boundary import ExecutorError

requires_bubblewrap = pytest.mark.skipif(
    os.name != "posix" or not shutil.which("bwrap"),
    reason="Real hook isolation requires Linux bubblewrap",
)


def git(cwd, *args):
    try:
        return subprocess.run(
            ["git", *args], cwd=cwd, check=True, text=True, capture_output=True
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        raise


@pytest.fixture
def hook_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "--initial-branch=main")
    git(repo, "config", "user.name", "Worker test")
    git(repo, "config", "user.email", "worker@example.test")
    (repo / "file.txt").write_text("base\n")
    git(repo, "add", "file.txt")
    git(repo, "commit", "-m", "base")
    workspace = tmp_path / "owned"
    git(repo, "worktree", "add", "-b", "codex/test", str(workspace))
    hook = repo / ".git" / "hooks" / "pre-commit"

    def install(body):
        hook.write_text("#!/bin/sh\nset -eu\n" + body + "\n")
        hook.chmod(0o700)

    (workspace / "file.txt").write_text("changed\n")
    git(workspace, "add", "file.txt")
    return repo, workspace, install


def commit_with_hooks(repo, workspace):
    sandbox = GitHookSandbox(repo, workspace)
    with sandbox.invocation(workspace) as overrides:
        return git(workspace, *overrides, "commit", "-m", "implementation")


@requires_bubblewrap
def test_real_hook_reads_index_runs_check_and_writes_owned_workspace(hook_repo):
    # covers: ACD-1300g-1, ACD-1300g-2
    repo, workspace, install = hook_repo
    install(
        "git diff --cached --name-only | grep -qx file.txt\n"
        "git write-tree >/dev/null\nprintf checked > hook-evidence.txt"
    )
    original = git(repo, "rev-parse", "main")
    commit_with_hooks(repo, workspace)
    assert (workspace / "hook-evidence.txt").read_text() == "checked"
    assert git(workspace, "log", "-1", "--format=%s") == "implementation"
    assert git(repo, "rev-parse", "main") == original


@pytest.mark.parametrize("attack", ["outside", "protected_ref", "git_config"])
@requires_bubblewrap
def test_real_hook_cannot_write_outside_or_modify_protected_git_metadata(hook_repo, attack):
    # covers: ACD-1300g-1, ACD-1300g-1-i
    repo, workspace, install = hook_repo
    outside = repo.parent / "private.txt"
    outside.write_text("untouched")
    original = git(repo, "rev-parse", "main")
    command = {
        "outside": f"printf escaped > '{outside}'",
        "protected_ref": "git update-ref refs/heads/main HEAD~0",
        "git_config": "git config worker.escape true",
    }[attack]
    if attack == "protected_ref":
        command = "git update-ref -d refs/heads/main"
    install(command)
    if attack == "outside":
        # Mount ancestors can be private writable placeholders. Verify actual
        # host isolation, not whether creating a same-named private file fails.
        install(f"if test -e '{outside}'; then printf exposed > visibility.txt; exit 1; fi\n"
                "printf hidden > visibility.txt\n" + command)
        try:
            commit_with_hooks(repo, workspace)
        except (ExecutorError, subprocess.CalledProcessError):
            pass  # A read-only namespace ancestor may also deny creation.
        assert (workspace / "visibility.txt").read_text() == "hidden"
    else:
        with pytest.raises((ExecutorError, subprocess.CalledProcessError)):
            commit_with_hooks(repo, workspace)
        assert git(workspace, "rev-parse", "HEAD") == original
    assert outside.read_text() == "untouched"
    assert git(repo, "rev-parse", "main") == original
    assert "worker.escape" not in git(repo, "config", "--list")



@requires_bubblewrap
def test_hook_index_mutation_requires_revalidation(hook_repo):
    # covers: ACD-1300g-1, ACD-1300g-2
    repo, workspace, install = hook_repo
    install("printf formatted > file.txt\ngit add file.txt")
    before = git(workspace, "rev-parse", "HEAD")
    with pytest.raises((ExecutorError, subprocess.CalledProcessError)):
        commit_with_hooks(repo, workspace)
    assert git(workspace, "rev-parse", "HEAD") == before
    assert (workspace / "file.txt").read_text() == "formatted"


@requires_bubblewrap
def test_commit_message_hook_preserves_normal_argument_semantics(hook_repo):
    # covers: ACD-1300g-1
    repo, workspace, install = hook_repo
    hook = repo / ".git" / "hooks" / "commit-msg"
    hook.write_text('#!/bin/sh\nprintf "checked message\\n" > "$1"\n')
    hook.chmod(0o700)
    commit_with_hooks(repo, workspace)
    assert git(workspace, "log", "-1", "--format=%s") == "checked message"


@requires_bubblewrap
def test_unstaged_hook_formatting_cannot_create_a_stale_checked_commit(hook_repo):
    # covers: ACD-1300g-1, ACD-1300g-2
    repo, workspace, install = hook_repo
    install("printf formatted > file.txt")
    before = git(workspace, "rev-parse", "HEAD")
    with pytest.raises(ExecutorError, match="revalidation"):
        commit_with_hooks(repo, workspace)
    assert git(workspace, "rev-parse", "HEAD") == before


@requires_bubblewrap
def test_post_commit_failure_is_not_hidden_by_successful_git_exit(hook_repo):
    # covers: ACD-1300g-1, ACD-1300g-2
    repo, workspace, install = hook_repo
    hook = repo / ".git" / "hooks" / "post-commit"
    hook.write_text("#!/bin/sh\nexit 7\n")
    hook.chmod(0o700)
    with pytest.raises(ExecutorError) as result:
        commit_with_hooks(repo, workspace)
    assert result.value.requires_reconciliation is True
    assert git(workspace, "log", "-1", "--format=%s") == "implementation"


@requires_bubblewrap
def test_real_pre_commit_runs_local_check_with_private_copy_of_prepared_cache(hook_repo):
    # covers: ACD-1300g-1, ACD-1300g-2
    repo, workspace, install = hook_repo
    cache = repo.parent / "prepared-cache"
    cache.mkdir()
    (cache / "seed").write_text("prepared")
    config = workspace / ".pre-commit-config.yaml"
    config.write_text(
        "repos:\n- repo: local\n  hooks:\n  - id: real-check\n"
        "    name: real check\n    language: system\n"
        "    entry: sh -c 'test -f \"$PRE_COMMIT_HOME/seed\" && printf checked > hook-evidence.txt'\n"
        "    pass_filenames: false\n    always_run: true\n"
    )
    git(workspace, "add", ".pre-commit-config.yaml")
    install(f"'{sys.executable}' -m pre_commit run --all-files")
    boundary = GitHookSandbox(repo, workspace, pre_commit_cache=cache)
    with boundary.invocation(workspace) as overrides:
        git(workspace, *overrides, "commit", "-m", "checked by pre-commit")
    assert (workspace / "hook-evidence.txt").read_text() == "checked"
    assert sorted(path.name for path in cache.iterdir()) == ["seed"]


@pytest.mark.parametrize(
    "config",
    [
        {"read_paths": ["/"]},
        {"read_paths": ["relative"]},
        {"pre_commit_cache": "/opt/../home"},
        {"read_paths": "bad"},
    ],
)
def test_hook_runtime_configuration_rejects_broad_or_ambiguous_paths(config):
    # covers: ACD-1300b-2
    from scripts.background_worker.settings import validate

    with pytest.raises(ValueError):
        validate({"hook_runtime": config})


@requires_bubblewrap
def test_real_git_coordinator_prepares_and_commits_with_repository_hook(hook_repo):
    # covers: ACD-1300e-2, ACD-1300g-1
    from scripts.background_worker.git_ops import GitOps

    repo, _, install = hook_repo
    install("git diff --cached --name-only | grep -qx file.txt")
    coordinator = GitOps(repo, {"target_ref": "main"})
    run = {"id": "integration", "payload": {}}
    prepared = coordinator.prepare(run)
    run.update(workspace=prepared["workspace"], payload=prepared)
    from pathlib import Path

    (Path(run["workspace"]) / "file.txt").write_text("implemented\n")
    sha = coordinator.commit(run, "ACD-1300g-1")
    assert sha != prepared["base_sha"]
    assert git(repo, "rev-parse", "main") == prepared["base_sha"]
    assert git(run["workspace"], "status", "--porcelain") == ""


@requires_bubblewrap
def test_committed_reference_hook_failure_requires_reconciliation(hook_repo):
    # covers: ACD-1300e-3, ACD-1300g-1
    repo, workspace, _ = hook_repo
    hook = repo / ".git" / "hooks" / "reference-transaction"
    hook.write_text('#!/bin/sh\nif [ "$1" = committed ]; then exit 7; fi\n')
    hook.chmod(0o700)
    before = git(workspace, "rev-parse", "HEAD")
    with pytest.raises(ExecutorError) as result:
        commit_with_hooks(repo, workspace)
    assert result.value.requires_reconciliation is True
    assert git(workspace, "rev-parse", "HEAD") != before


@pytest.mark.parametrize("attack", ["source_checkout", "protected_ref"])
@requires_bubblewrap
def test_fetch_reference_hook_cannot_write_checkout_or_protected_ref(hook_repo, attack):
    # covers: ACD-1300f-2, ACD-1300g-1
    from scripts.background_worker.sources import refresh_target

    repo, _, _ = hook_repo
    remote = repo.parent / "upstream"
    git(repo.parent, "clone", str(repo), str(remote))
    git(remote, "config", "user.name", "Worker test")
    git(remote, "config", "user.email", "worker@example.test")
    git(repo, "remote", "add", "origin", str(remote))
    refresh_target(repo, "origin/main")
    before = git(repo, "rev-parse", "origin/main")
    (remote / "file.txt").write_text("upstream update\n")
    git(remote, "commit", "-am", "advance upstream")
    hook = repo / ".git" / "hooks" / "reference-transaction"
    command = (
        "printf escaped > file.txt"
        if attack == "source_checkout"
        else "git update-ref -d refs/heads/main"
    )
    hook.write_text('#!/bin/sh\nset -eu\nif [ "$1" = prepared ]; then ' + command + "; fi\n")
    hook.chmod(0o700)
    with pytest.raises(ValueError, match="safely"):
        refresh_target(repo, "origin/main")
    assert (repo / "file.txt").read_text() == "base\n"
    assert git(repo, "rev-parse", "main") == before
    assert git(repo, "rev-parse", "origin/main") == before


@pytest.mark.parametrize(
    "target,expected",
    [
        ("upstream/main", "main"),
        ("refs/remotes/origin/main", "main"),
        ("refs/heads/main", "main"),
        ("upstream/release/v1", "release/v1"),
    ],
)
@requires_bubblewrap
def test_publication_base_normalizes_real_local_and_remote_refs(hook_repo, target, expected):
    # covers: ACD-1300g-4
    from scripts.background_worker.git_ops import GitOps

    repo, workspace, _ = hook_repo
    git(repo, "remote", "add", "origin", str(repo))
    git(repo, "remote", "add", "upstream", str(repo))
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(repo, "update-ref", "refs/remotes/upstream/main", "HEAD")
    git(repo, "update-ref", "refs/remotes/upstream/release/v1", "HEAD")
    assert git(repo, "rev-parse", "--verify", target)
    assert GitOps(repo, {"target_ref": target}).publication_base(workspace) == expected


@requires_bubblewrap
def test_active_clean_filter_is_rejected_before_status_or_staging(hook_repo):
    # covers: ACD-1300g-1
    from scripts.background_worker.git_ops import GitOps

    repo, workspace, _ = hook_repo
    marker = repo.parent / "filter-executed"
    git(repo, "config", "filter.dangerous.clean", f"sh -c 'printf bad > {marker}; cat'")
    (workspace / ".gitattributes").write_text("*.txt filter=dangerous\n")
    coordinator = GitOps(repo, {})
    with pytest.raises(ExecutorError, match="required filter will not be bypassed"):
        coordinator.git(workspace, "status", "--porcelain")
    assert not marker.exists()


@requires_bubblewrap
def test_unused_global_filter_does_not_block_ordinary_repository(hook_repo):
    # covers: ACD-1300g-1
    from scripts.background_worker.git_ops import GitOps

    repo, workspace, _ = hook_repo
    git(repo, "config", "filter.unused.clean", "command-that-does-not-exist")
    GitOps(repo, {})._assert_hooks_safe(workspace)


@requires_bubblewrap
def test_status_never_executes_configured_fsmonitor(hook_repo):
    # covers: ACD-1300g-1
    from scripts.background_worker.git_ops import GitOps

    repo, workspace, _ = hook_repo
    marker = repo.parent / "fsmonitor-executed"
    helper = repo.parent / "fsmonitor.sh"
    helper.write_text(f"#!/bin/sh\nprintf bad > '{marker}'\n")
    helper.chmod(0o700)
    git(repo, "config", "core.fsmonitor", str(helper))
    assert GitOps(repo, {}).git(workspace, "status", "--porcelain")
    assert not marker.exists()


@requires_bubblewrap
def test_review_package_diff_never_executes_textconv_or_external_diff(hook_repo):
    # covers: ACD-1300g-1, ACD-1300g-3
    from scripts.background_worker.git_ops import GitOps

    repo, workspace, _ = hook_repo
    before = git(workspace, "rev-parse", "HEAD")
    (workspace / ".gitattributes").write_text("*.txt diff=dangerous\n")
    git(workspace, "add", ".gitattributes")
    git(workspace, "commit", "-m", "implementation")
    marker = repo.parent / "diff-executed"
    command = f"sh -c 'printf bad > {marker}; cat'"
    git(repo, "config", "diff.dangerous.textconv", command)
    git(repo, "config", "diff.dangerous.command", command)
    coordinator = GitOps(repo, {})
    coordinator.assert_workspace = lambda run: workspace
    package = coordinator.package(
        {"payload": {"base_sha": before}, "plan": {"ac_ids": [], "source_context": {}}}, {}
    )
    assert "+changed" in package["diff"]
    assert not marker.exists()


@pytest.mark.parametrize("generated", [True, False])
@pytest.mark.parametrize("ending", ["\n", "\r\n"])
@requires_bubblewrap
def test_windows_generated_bash_hook_preserves_body_and_arbitrary_sh(hook_repo, generated, ending):
    # covers: ACD-1300g-1, ACD-1300g-2
    repo, workspace, _ = hook_repo
    hook = repo / ".git/hooks/pre-commit"
    header = "#!/bin/sh\n#!/usr/bin/env bash\n"
    header += "# File generated by pre-commit: https://pre-commit.com\n" if generated else "# custom shell hook\n"
    body = header + 'VALUES=(checked)\nprintf "%s" "${VALUES[0]}" > hook-evidence.txt\n'
    body += 'printf "%s" "$0" > hook-path.txt\n'
    hook.write_bytes(body.replace("\n", ending).encode())
    hook.chmod(0o700)
    if generated:
        commit_with_hooks(repo, workspace)
        assert (workspace / "hook-evidence.txt").read_text() == "checked"
        assert (workspace / "hook-path.txt").read_text() == str(hook)
        assert hook.read_bytes() == body.replace("\n", ending).encode()
    else:
        with pytest.raises(ExecutorError, match="Hook"):
            commit_with_hooks(repo, workspace)
        assert not (workspace / "hook-evidence.txt").exists()
