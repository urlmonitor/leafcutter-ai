"""Windows launcher routing without dispatching implementation or production work."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from background_worker import wsl_runtime as runtime


@pytest.fixture
def route(tmp_path, monkeypatch):
    repo = tmp_path / "project with spaces"
    repo.mkdir()
    config = {"kind": "wsl", "distribution": "leafcutter-worker", "python": runtime.DEFAULT_PYTHON}
    target = repo / runtime.RUNTIME_FILE
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(config))
    monkeypatch.setattr(
        runtime,
        "os",
        SimpleNamespace(name="nt", environ={"WSLENV": "SECRET/u", "SECRET": "host-only"}),
    )
    return repo, config


def test_dispatch_preserves_arguments_translates_paths_and_blocks_env_forwarding(
    route, monkeypatch
):
    repo, config = route
    file = repo / "settings with spaces.json"
    file.write_text(json.dumps({"checks": [["python", "-m", "pytest"]]}))
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        if "wslpath" in argv:
            return SimpleNamespace(returncode=0, stdout="/linux/" + Path(argv[-1]).name, stderr="")
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr(runtime.subprocess, "run", run)
    assert (
        runtime.dispatch(
            ["--repo", str(repo), "configure", "--config=" + str(file)],
            entrypoint=repo / "worker cli.py",
        )
        == 7
    )
    command, kwargs = calls[-1]
    assert command == [
        "wsl.exe",
        "--distribution",
        config["distribution"],
        "--exec",
        config["python"],
        "/linux/worker cli.py",
        "--repo",
        "/linux/project with spaces",
        "configure",
        "--config=/linux/settings with spaces.json",
    ]
    assert all(options["env"]["WSLENV"] == "" for _, options in calls)


def test_runtime_configure_checks_linux_git_and_does_not_enable(route, monkeypatch):
    repo, _ = route
    calls = []
    monkeypatch.setattr(runtime, "_run_capture", lambda argv: calls.append(argv) or "/mnt/project")
    assert runtime.dispatch(["--repo", str(repo), "runtime", "configure-wsl"]) == 0
    assert len(calls) == 2
    assert "langgraph" in calls[1][-2] and "rev-parse" in calls[1][-2]
    assert not (repo / ".leafcutter/background-worker/state.sqlite").exists()


def test_bad_windows_check_rejected_before_child_execution(route, monkeypatch):
    repo, _ = route
    file = repo / "config.json"
    file.write_text(json.dumps({"checks": [["C:\\Python\\python.exe", "-m", "pytest"]]}))
    monkeypatch.setattr(runtime, "_linux_path", lambda *args: "/mnt/repo")
    with pytest.raises(ValueError, match="Linux commands"):
        runtime.dispatch(["--repo", str(repo), "configure", "--config", str(file)])


def test_answer_text_runtime_is_not_bootstrap_command(route, monkeypatch):
    repo, _ = route
    monkeypatch.setattr(runtime, "_linux_path", lambda *args: "/mnt/repo")
    monkeypatch.setattr(runtime.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0))
    assert (
        runtime.dispatch(
            [
                "--repo",
                str(repo),
                "answer",
                "run-id",
                "--request-id",
                "request-id",
                "--answer",
                "runtime",
            ]
        )
        == 0
    )


def test_native_linux_never_redispatches(route, monkeypatch):
    repo, _ = route
    monkeypatch.setattr(runtime, "os", SimpleNamespace(name="posix"))
    assert runtime.dispatch(["--repo", str(repo), "status"]) is None


def test_failed_probe_preserves_old_runtime_config(route, monkeypatch):
    repo, _ = route
    target = repo / runtime.RUNTIME_FILE
    original = target.read_bytes()

    def fail(*args):
        raise ValueError("WSL unavailable")

    monkeypatch.setattr(runtime, "_run_capture", fail)
    with pytest.raises(ValueError, match="unavailable"):
        runtime.dispatch(["--repo", str(repo), "runtime", "configure-wsl"])
    assert target.read_bytes() == original


def test_runtime_change_refuses_enabled_worker(route):
    from background_worker.store import Store

    repo, _ = route
    with Store(repo / ".leafcutter/background-worker/state.sqlite") as store:
        store.update_settings(enabled=True)
    with pytest.raises(ValueError, match="Turn the current worker off"):
        runtime.dispatch(["--repo", str(repo), "runtime", "configure-wsl"])
