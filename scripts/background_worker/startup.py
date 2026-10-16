"""Token-bound startup acknowledgement and durable local service lifecycle."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

from .locks import exclusive
from .store import Store

TOKEN_ENV = "LEAFCUTTER_WORKER_LAUNCH_TOKEN"


def _write(path, payload):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        temporary.replace(path)
    except OSError as exc:
        raise OSError("Cannot persist worker startup status") from exc


def _read(path):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError) as exc:
        raise OSError("Cannot read worker startup status") from exc


def startup_status(state_dir):
    directory = Path(state_dir)
    latest = _read(directory / "last-launch.json")
    token = latest.get("token", "")
    launch = (
        _read(directory / "startup" / (token + ".json"))
        if re.fullmatch(r"[a-f0-9]{32}", token)
        else {}
    )
    return {"service": _read(directory / "service-status.json"), "last_launch": launch}


@contextmanager
def service_lifecycle(state_dir):
    """Acknowledge only after the service lock is held; never before admission."""
    directory = Path(state_dir)
    token = os.environ.get(TOKEN_ENV) or uuid.uuid4().hex
    if not re.fullmatch(r"[a-f0-9]{32}", token):
        raise ValueError("Invalid worker launch token")
    owned = False

    def record(state, error=None):
        nonlocal owned
        owned = owned or state == "running"
        payload = {"token": token, "state": state, "pid": os.getpid(), "updated_at": time.time()}
        if error:
            payload["error"] = error
        _write(directory / "startup" / (token + ".json"), payload)
        if owned:
            _write(directory / "service-status.json", payload)

    try:
        yield record
    except BaseException as exc:
        record("failed", type(exc).__name__)
        raise
    else:
        if owned:
            record("stopped")


def start_background(repo, state_dir, *, timeout=10, entrypoint=None):
    """Enable and launch once, or acknowledge the existing lock-owning service."""
    directory = Path(state_dir)
    with exclusive(directory / "startup.lock") as owner:
        if not owner:
            raise OSError("Another worker startup is in progress; retry status/on")
        with Store(directory / "state.sqlite") as store:
            with exclusive(directory / "service.lock") as available:
                if not available:
                    store.update_settings(enabled=True)
                    return {"state": "already_running", "log": str(directory / "worker.log")}
            token = uuid.uuid4().hex
            path = directory / "startup" / (token + ".json")
            _write(directory / "last-launch.json", {"token": token})
            _write(path, {"token": token, "state": "starting", "updated_at": time.time()})
            entry = entrypoint or Path(__file__).resolve().parents[1] / "background_worker_cli.py"
            argv = [sys.executable, str(entry), "--repo", str(repo), "run"]
            options = {
                "cwd": str(repo),
                "stdin": subprocess.DEVNULL,
                "env": dict(os.environ, **{TOKEN_ENV: token}),
            }
            if os.name == "nt":
                options["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
            else:
                options["start_new_session"] = True
            child = None
            store.update_settings(enabled=True)
            try:
                with (directory / "worker.log").open("ab") as output:
                    child = subprocess.Popen(argv, stdout=output, stderr=output, **options)
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    status = _read(path)
                    exited = child.poll()
                    if status.get("token") == token and status.get("state") == "already_running":
                        return {
                            "state": "already_running",
                            "token": token,
                            "log": str(directory / "worker.log"),
                        }
                    if exited is not None:
                        raise OSError(
                            "Worker exited before startup acknowledgement; inspect worker.log"
                        )
                    if status.get("token") == token and status.get("state") == "running":
                        return {
                            "state": "running",
                            "pid": child.pid,
                            "token": token,
                            "log": str(directory / "worker.log"),
                        }
                    time.sleep(0.05)
                raise OSError("Worker startup acknowledgement timed out; inspect worker.log")
            except (OSError, subprocess.SubprocessError) as exc:
                if child is not None and child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)
                # Another foreground service may have acquired the lock while
                # this launch failed. Never disable that verified live service.
                with exclusive(directory / "service.lock") as available:
                    if not available:
                        return {"state": "already_running", "log": str(directory / "worker.log")}
                    store.update_settings(enabled=False)
                _write(
                    path,
                    {
                        "token": token,
                        "state": "failed",
                        "error": str(exc),
                        "updated_at": time.time(),
                    },
                )
                raise OSError(str(exc)) from exc
