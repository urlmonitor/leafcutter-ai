"""Installed CLI for the opt-in local background worker (ACD-1300b/d/e)."""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import sqlite3
import logging

LOGGER = logging.getLogger(__name__)
from .settings import validate
from .store import Store


def emit(data):
    print(json.dumps(data, default=str))


def repo_path(value):
    path = Path(value).resolve()
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        LOGGER.warning("Cannot identify Git repository: %s", type(exc).__name__)
        raise
    if result.returncode:
        raise ValueError("--repo must identify a Git repository")
    return Path(result.stdout.strip()).resolve()


def start_background(repo, state_dir):
    entry = Path(__file__).resolve().parents[1] / "background_worker_cli.py"
    argv = [sys.executable, str(entry), "--repo", str(repo), "run"]
    kwargs = {"cwd": str(repo), "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    try:
        with open(state_dir / "worker.log", "ab") as output:
            child = subprocess.Popen(argv, stdout=output, stderr=output, **kwargs)
    except OSError as exc:
        LOGGER.warning("Cannot start background worker: %s", type(exc).__name__)
        raise
    return {"pid": child.pid, "log": str(state_dir / "worker.log")}


def parser():
    p = argparse.ArgumentParser(description="Opt-in local background AC worker")
    p.add_argument("--repo", required=True, help="Explicit project repository")
    p.add_argument("--json", action="store_true", help="Output is always JSON")
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("configure")
    c.add_argument("--config", required=True)
    c = sub.add_parser("on")
    c.add_argument(
        "--no-start",
        action="store_true",
        help="Persist enablement for an external supervisor; no process is started",
    )
    sub.add_parser("off")
    sub.add_parser("status")
    sub.add_parser("inbox")
    c = sub.add_parser("run")
    c.add_argument("--once", action="store_true")
    c = sub.add_parser("answer")
    c.add_argument("run_id")
    c.add_argument("--request-id", required=True)
    c.add_argument("--answer", required=True)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    store = None
    try:
        repo = repo_path(args.repo)
        state_dir = repo / ".leafcutter" / "background-worker"
        state_dir.mkdir(parents=True, exist_ok=True)
        db = state_dir / "state.sqlite"
        store = Store(db)
        if args.command == "configure":
            requested = json.loads(Path(args.config).read_text(encoding="utf-8"))
            if not isinstance(requested, dict):
                raise ValueError("Configuration must be an object")
            if "enabled" in requested:
                raise ValueError("Use on/off to change enabled state")
            allowed = {
                "max_agent_calls",
                "implementation",
                "reviewer",
                "checks",
                "target_ref",
                "poll_seconds",
            }
            if set(requested) - allowed:
                raise ValueError("Unknown configuration fields")
            combined = {**store.get_settings(), **requested}
            validate(combined, executable=True)
            store.update_settings(**requested)
            emit({"settings": store.get_settings()})
        elif args.command == "status":
            from .notifications import notification_status

            emit(
                {
                    "settings": store.get_settings(),
                    "runs": store.list_runs(),
                    "notifications": notification_status(db),
                    "queue": store.get_queue_status(),
                }
            )
        elif args.command == "inbox":
            emit({"items": store.list_inbox()})
        elif args.command == "off":
            store.update_settings(enabled=False)
            emit({"settings": store.get_settings(), "state": "draining"})
        elif args.command == "on":
            settings = store.get_settings()
            validate(settings, executable=True)
            if not args.no_start:
                from .executors import preflight

                preflight(settings)
            store.update_settings(enabled=True)
            try:
                process = {} if args.no_start else start_background(repo, state_dir)
            except OSError:
                store.update_settings(enabled=False)
                raise
            emit({"settings": store.get_settings(), "worker": process})
        elif args.command == "answer":
            items = store.list_inbox()
            item = next(
                (i for i in items if i.get("id", i.get("item_id")) == args.request_id), None
            )
            if item is None or item.get("run_id") != args.run_id:
                raise ValueError("Unknown request for this run")
            if item.get("answer") is not None or item.get("status") in {"resolved", "answered"}:
                raise ValueError("Request already resolved")
            result = store.answer_request(args.run_id, args.request_id, args.answer)
            if result is None:
                raise ValueError("Request already resolved or unknown for this run")
            emit(result)
        elif args.command == "run":
            from .service import run_service

            emit(run_service(repo, db, once=args.once))
        return 0
    except (
        ValueError,
        KeyError,
        OSError,
        RuntimeError,
        ImportError,
        sqlite3.Error,
        subprocess.SubprocessError,
    ) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
