"""Large checkout preparation has its own bounded Git timeout."""
from contextlib import nullcontext
import copy
import subprocess
from unittest.mock import Mock, patch

from scripts.background_worker.git_ops import GitOps
from scripts.background_worker.store import Store


def test_only_worktree_creation_uses_ten_minutes_without_consuming_ac_budget(tmp_path):
    # covers: ACD-1300b-4 ACD-1300c-1
    calls = []

    def invoke(argv, **options):
        calls.append((argv, options["timeout"]))
        return subprocess.CompletedProcess(argv, 0, "", "")

    settings = {"target_ref": "main"}
    original = copy.deepcopy(settings)
    coordinator = GitOps(tmp_path, settings, invoke=invoke)
    boundary = Mock()
    boundary.invocation.side_effect = lambda cwd: nullcontext(["-c", "core.hooksPath=/owned-hooks"])
    with Store(tmp_path / "worker.sqlite") as store:
        store.update_settings(enabled=True)
        run = store.claim_feature({"feature_id": "TEST-100a", "ac_ids": ["TEST-100a-1"]})
        budget = run["budgets"]
        with patch.object(coordinator, "_assert_hooks_safe"), patch.object(coordinator, "target_head", return_value="base"):
            with patch.object(coordinator, "hook_boundary", return_value=boundary):
                coordinator.prepare(run)
                coordinator.hooked_git(tmp_path, tmp_path, "push", "origin", "owned-branch")
        coordinator.git(tmp_path, "rev-parse", "HEAD")
        assert store.get_run(run["id"])["budgets"] == budget
    assert next(timeout for argv, timeout in calls if "worktree" in argv) == 600
    assert all(timeout == 120 for argv, timeout in calls if "worktree" not in argv)
    assert settings == original


def test_baseline_hook_gets_full_coordinator_budget(tmp_path):
    # covers: ACD-1300b-4
    coordinator = GitOps(tmp_path, {})
    with patch.object(coordinator, "_assert_hooks_safe"), patch.object(coordinator, "target_head", return_value="base"), patch.object(coordinator, "hooked_git") as hooked, patch("scripts.background_worker.bootstrap.provision_runtime", return_value=True):
        coordinator.prepare({"id": "probe"})
    assert hooked.call_args.kwargs["timeout"] == 660
    assert hooked.call_args.args[-1] == "pre-commit"


def test_commit_subprocesses_share_remaining_ac_deadline(tmp_path):
    # covers: ACD-1300c-1
    elapsed = [0]
    calls = []

    def invoke(argv, **options):
        calls.append((argv, options["timeout"]))
        elapsed[0] += 5
        output = " M file" if "--untracked-files=all" in argv else ""
        return subprocess.CompletedProcess(argv, 0, output, "")

    coordinator = GitOps(tmp_path, {}, invoke=invoke)
    boundary = Mock()
    boundary.invocation.side_effect = lambda cwd: nullcontext([])
    with patch("scripts.background_worker.git_deadline.time.monotonic", side_effect=lambda: elapsed[0]), patch.object(coordinator, "assert_workspace", return_value=tmp_path), patch.object(coordinator, "_assert_hooks_safe"), patch.object(coordinator, "hook_boundary", return_value=boundary), patch("scripts.background_worker.git_extensions.assert_no_executable_filters"):
        coordinator.commit({}, "AC-1", timeout=40)
    assert next(timeout for argv, timeout in calls if "commit" in argv) == 25
    assert all(timeout <= 40 - i * 5 for i, (_, timeout) in enumerate(calls))
    assert coordinator.invoke is invoke


def test_exhausted_commit_preparation_cannot_launch_hook(tmp_path):
    # covers: ACD-1300c-1
    import pytest
    from scripts.background_worker.executors import ExecutorError

    coordinator = GitOps(tmp_path, {}, invoke=Mock())
    original = coordinator.invoke
    with patch("scripts.background_worker.git_deadline.time.monotonic", side_effect=[0, 11]), patch.object(coordinator, "assert_workspace", return_value=tmp_path), patch("scripts.background_worker.git_extensions.assert_no_executable_filters"):
        with pytest.raises(ExecutorError, match="time budget exhausted"):
            coordinator.commit({}, "AC-1", timeout=10)
    original.assert_not_called()
    assert coordinator.invoke is original


def test_commit_hook_budget_is_bounded_but_reads_keep_normal_timeout(tmp_path):
    # covers: ACD-1300c-1
    calls = []

    def invoke(argv, **options):
        calls.append((argv, options["timeout"]))
        output = " M file" if "--untracked-files=all" in argv else ""
        return subprocess.CompletedProcess(argv, 0, output, "")

    coordinator = GitOps(tmp_path, {}, invoke=invoke)
    boundary = Mock()
    boundary.invocation.side_effect = lambda cwd: nullcontext([])
    with patch("scripts.background_worker.git_deadline.time.monotonic", return_value=0), patch.object(coordinator, "assert_workspace", return_value=tmp_path), patch.object(coordinator, "_assert_hooks_safe"), patch.object(coordinator, "hook_boundary", return_value=boundary), patch("scripts.background_worker.git_extensions.assert_no_executable_filters"):
        coordinator.commit({}, "AC-1", timeout=3600)
    assert next(timeout for argv, timeout in calls if "commit" in argv) == 660
    assert all(timeout == 120 for argv, timeout in calls if "commit" not in argv)
