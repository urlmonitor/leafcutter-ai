"""Explicit Windows launcher for a separately installed Linux worker runtime."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sqlite3
import sys

RUNTIME_FILE = Path(".leafcutter/background-worker/runtime.json")
DEFAULT_PYTHON = "/opt/leafcutter-worker/venv/bin/python"


def _option(argv, name):
    for index, value in enumerate(argv):
        if value == name:
            if index + 1 >= len(argv):
                raise ValueError(f"{name} requires a value")
            return argv[index + 1]
        if value.startswith(name + "="):
            return value.split("=", 1)[1]
    return None


def _replace(argv, name, value):
    result = list(argv)
    for index, item in enumerate(result):
        if item == name:
            result[index + 1] = value
            return result
        if item.startswith(name + "="):
            result[index] = name + "=" + value
            return result
    return result


def _wsl(config, *arguments):
    return ["wsl.exe", "--distribution", config["distribution"], "--exec", *arguments]


def _environment():
    # WSLENV explicitly propagates selected Windows environment variables.
    # Runtime credentials must be configured inside Linux, never forwarded here.
    return dict(os.environ, WSLENV="")


def _run_capture(argv):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30, env=_environment())
    except (OSError, subprocess.SubprocessError):
        raise
    if result.returncode:
        raise ValueError("WSL runtime probe failed: " + result.stderr.strip()[-2000:])
    return result.stdout.strip()


def _linux_path(config, path):
    return _run_capture(_wsl(config, "wslpath", "-a", "-u", str(Path(path).resolve())))


def _validate(config):
    if not isinstance(config, dict) or set(config) != {"kind", "distribution", "python"}:
        raise ValueError("Runtime configuration requires only kind, distribution and python")
    if config["kind"] != "wsl":
        raise ValueError("Unsupported runtime kind; expected wsl")
    for key in ("distribution", "python"):
        value = config[key]
        if (
            not isinstance(value, str)
            or not value
            or value.startswith("-")
            or any(c in value for c in "\r\n\x00")
        ):
            raise ValueError(f"Invalid runtime {key}")
    if not config["python"].startswith("/"):
        raise ValueError("WSL Python must be an absolute Linux path")
    return config


def _configure(argv, repo):
    parser = argparse.ArgumentParser(
        description="Configure a preinstalled WSL worker; does not enable it"
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("runtime", choices=["runtime"])
    parser.add_argument("operation", choices=["configure-wsl"])
    parser.add_argument("--distribution", default="leafcutter-worker")
    parser.add_argument("--python", default=DEFAULT_PYTHON)
    args = parser.parse_args(argv)
    config = _validate({"kind": "wsl", "distribution": args.distribution, "python": args.python})
    state = repo / ".leafcutter/background-worker/state.sqlite"
    if state.exists():
        connection = sqlite3.connect(state.as_uri() + "?mode=ro", uri=True)
        try:
            settings = connection.execute("SELECT body FROM settings WHERE id=1").fetchone()
            leases = connection.execute(
                "SELECT COUNT(*) FROM leases WHERE released_at IS NULL"
            ).fetchone()[0]
            if settings and json.loads(settings[0]).get("enabled") or leases:
                raise ValueError(
                    "Turn the current worker off and drain all active calls before changing runtime"
                )
        finally:
            connection.close()
    linux_repo = _linux_path(config, repo)
    # Check runtime dependencies and Linux Git visibility before storing the route.
    _run_capture(
        _wsl(
            config,
            config["python"],
            "-c",
            "import langgraph,sqlite3,subprocess,sys; subprocess.run(['git','-C',sys.argv[1],'rev-parse','--show-toplevel'],check=True)",
            linux_repo,
        )
    )
    target = repo / RUNTIME_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    print(json.dumps({"runtime": config, "repo": str(repo), "enabled_changed": False}))
    return 0


def dispatch(argv=None, *, entrypoint=None):
    """Return child exit status, or None when the native CLI should handle argv."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if os.name != "nt":
        return None
    repo_value = _option(argv, "--repo")
    if repo_value is None:
        return None
    repo = Path(repo_value).resolve()
    globals_parser = argparse.ArgumentParser(add_help=False)
    globals_parser.add_argument("--repo")
    globals_parser.add_argument("--json", action="store_true")
    _, remaining = globals_parser.parse_known_args(argv)
    if remaining and remaining[0] == "runtime":
        return _configure(argv, repo)
    target = repo / RUNTIME_FILE
    if not target.exists():
        return None
    config = _validate(json.loads(target.read_text(encoding="utf-8")))
    forwarded = _replace(argv, "--repo", _linux_path(config, repo))
    config_file = _option(argv, "--config")
    if config_file is not None:
        settings = json.loads(Path(config_file).read_text(encoding="utf-8"))
        from .settings import validate

        validate(settings)
        for check in settings.get("checks", []):
            if any(
                isinstance(arg, str) and (len(arg) > 1 and arg[1] == ":" or "\\" in arg)
                for arg in check
            ):
                raise ValueError(
                    "WSL checks must use Linux commands and paths; Windows check paths are unsupported"
                )
        forwarded = _replace(forwarded, "--config", _linux_path(config, config_file))
    script = _linux_path(
        config, entrypoint or Path(__file__).resolve().parents[1] / "background_worker_cli.py"
    )
    # WSL does not inherit host credentials. The Linux worker detaches its service
    # with start_new_session and redirects output before this launcher exits.
    try:
        result = subprocess.run(_wsl(config, config["python"], script, *forwarded), env=_environment())
    except (OSError, subprocess.SubprocessError):
        raise
    return result.returncode


def main(argv=None):
    try:
        status = dispatch(argv)
        if status is not None:
            return status
        from .cli import main as native_main

        return native_main(argv)
    except (ValueError, OSError, sqlite3.Error, subprocess.SubprocessError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
