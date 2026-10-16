"""Host-visible isolation assertions without inference or an installed sandbox."""

import builtins
import io
import json
import subprocess
from types import SimpleNamespace

import pytest

from scripts.background_worker import execution_boundary, executors


@pytest.fixture
def local_executor(monkeypatch):
    monkeypatch.setattr(executors.shutil, "which", lambda _: "codex")
    requests = []

    def metadata(request, **kwargs):
        requests.append(request)
        payload = {"capabilities": ["tools"]} if len(requests) == 2 else {
            "models": [{"name": "fixture-model"}]
        }
        return io.StringIO(json.dumps(payload))

    monkeypatch.setattr(executors, "urlopen", metadata)
    executor = executors.LocalCodexExecutor(
        {"model": "fixture-model"},
        invoke=lambda argv, **kwargs: subprocess.CompletedProcess(
            argv, 0, "--oss --strict-config", ""
        ),
    )
    return executor, requests


@pytest.mark.parametrize("escape", ["overwrite-sentinel", "new-outside-file", "delete-sentinel"])
def test_preflight_rejects_host_visible_writes_before_model_lookup(local_executor, escape):
    # covers: ACD-1300g-1-i, ACD-1300b-1-i
    executor, requests = local_executor

    def check(workspace, argv, **kwargs):
        (workspace / "inside").write_text("allowed", encoding="utf-8")
        if escape == "delete-sentinel":
            (workspace.parent / "outside").unlink()
        else:
            target = "outside" if escape == "overwrite-sentinel" else "escaped"
            (workspace.parent / target).write_text("forbidden", encoding="utf-8")

    executor.check = check
    with pytest.raises(executors.ExecutorError, match="cannot prove scoped"):
        executor.preflight()
    assert requests == []


@pytest.mark.parametrize("inside", [None, "wrong-content"])
def test_preflight_requires_persisted_workspace_write(local_executor, inside):
    # covers: ACD-1300g-1-i
    executor, requests = local_executor

    def check(workspace, argv, **kwargs):
        if inside is not None:
            (workspace / "inside").write_text(inside, encoding="utf-8")

    executor.check = check
    with pytest.raises(executors.ExecutorError, match="cannot prove scoped"):
        executor.preflight()
    assert requests == []


def test_preflight_accepts_hidden_host_paths_and_private_namespace_writes(
    local_executor, tmp_path
):
    # covers: ACD-1300g-1
    executor, requests = local_executor
    private_parent = tmp_path / "private-namespace"
    private_parent.mkdir()

    def check(workspace, argv, **kwargs):
        # Execute the actual probe against a modeled mount view: the workspace
        # persists, while its apparent parent is private. This is not a real
        # kernel sandbox test; the opt-in Linux acceptance suite provides that.
        class WorkspaceView:
            parent = private_parent

            def __truediv__(self, name):
                return workspace / name

        def import_module(name, *args, **kwargs):
            if name == "pathlib":
                return SimpleNamespace(Path=SimpleNamespace(cwd=lambda: WorkspaceView()))
            return builtins.__import__(name, *args, **kwargs)

        assert not (private_parent / "outside").exists()
        exec(argv[-1], {"__builtins__": {**vars(builtins), "__import__": import_module}})
        assert (workspace.parent / "outside").read_text() == "boundary-sentinel"
        assert not (workspace.parent / "escaped").exists()

    executor.check = check
    executor.preflight()
    assert len(requests) == 2
    assert (private_parent / "outside").read_text() == "forbidden"
    assert (private_parent / "escaped").read_text() == "forbidden"


@pytest.mark.parametrize("readonly", [False, True])
def test_virtualenv_runtime_is_readonly_without_widening_host_access(monkeypatch, tmp_path, readonly):
    # covers: ACD-1300b-1, ACD-1300g-1
    import tomllib

    runtime = tmp_path / "coordinator-venv"
    monkeypatch.setattr(execution_boundary.sys, "prefix", str(runtime))
    monkeypatch.setattr(execution_boundary.sys, "base_prefix", str(tmp_path / "base"))
    config = tomllib.loads("\n".join(execution_boundary.permission_overrides(readonly=readonly)))
    profile = config["permissions"]["leafcutter-worker"]
    fs = profile["filesystem"]
    assert fs[str(runtime.resolve())] == "read"
    assert fs[":root"] == "deny"
    assert fs[":workspace_roots"]["."] == ("read" if readonly else "write")
    assert fs[":workspace_roots"]["**/*.env"] == "deny"
    assert profile["network"]["enabled"] is False


def test_system_python_adds_no_extra_host_path_grant(monkeypatch, tmp_path):
    # covers: ACD-1300b-1-i
    import tomllib

    monkeypatch.setattr(execution_boundary.sys, "prefix", str(tmp_path))
    monkeypatch.setattr(execution_boundary.sys, "base_prefix", str(tmp_path))
    config = tomllib.loads("\n".join(execution_boundary.permission_overrides()))
    filesystem = config["permissions"]["leafcutter-worker"]["filesystem"]
    assert filesystem["glob_scan_max_depth"] == 32
    assert set(filesystem) == {
        ":root", ":minimal", ":workspace_roots", "glob_scan_max_depth"
    }


def test_preflight_rejects_model_unsupported_reasoning_before_implementation(local_executor):
    # covers: ACD-1300g-1-i
    executor, requests = local_executor
    executor.settings["reasoning_effort"] = "high"
    executor.check = lambda workspace, argv, **kwargs: (workspace / "inside").write_text("allowed")
    with pytest.raises(executors.ExecutorError, match="unsupported by the local model"):
        executor.preflight()
    assert len(requests) == 2
    assert executor.metadata == {}


def test_preflight_keeps_verified_metadata_on_actual_executor(local_executor, monkeypatch):
    # covers: ACD-1300g-1
    executor, _ = local_executor
    metadata = {"capabilities": ["tools"], "thinking": {"values": [True]},
                "model_info": {"fixture.context_length": 32768}}
    payloads = iter([{"models": [{"name": "fixture-model"}]}, metadata])
    monkeypatch.setattr(executors, "urlopen", lambda *args, **kwargs: io.StringIO(json.dumps(next(payloads))))
    executor.check = lambda workspace, argv, **kwargs: (workspace / "inside").write_text("allowed")
    executor.preflight()
    assert executor.metadata == metadata


def test_preflight_accepts_cli_without_generation_schema_support(local_executor):
    # covers: ACD-1300g-1-i
    # angle: seam
    executor, requests = local_executor
    executor.check = lambda workspace, argv, **kwargs: (workspace / "inside").write_text("allowed")
    executor.preflight()
    assert len(requests) == 2 and executor.metadata["capabilities"] == ["tools"]
