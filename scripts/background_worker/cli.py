"""Installed CLI for the opt-in local background worker (ACD-1300b/d/e)."""

from __future__ import annotations
import argparse
import json
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
    from .startup import start_background as launch

    return launch(repo, state_dir)


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
    c = sub.add_parser("reconcile")
    c.add_argument("run_id")
    c.add_argument("--confirm-processes-stopped", action="store_true", required=True)
    c.add_argument("--note", required=True)
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
                "hook_runtime",
            }
            if set(requested) - allowed:
                raise ValueError("Unknown configuration fields")
            combined = {**store.get_settings(), **requested}
            validate(combined, executable=True)
            store.update_settings(**requested)
            emit({"settings": store.get_settings()})
        elif args.command == "status":
            from .notifications import notification_status
            from .startup import startup_status
            from .status_views import capacity_status, attention_items

            emit(
                {
                    "settings": store.get_settings(),
                    "runs": store.list_runs(),
                    "notifications": notification_status(db),
                    "queue": store.get_queue_status(),
                    "startup": startup_status(state_dir),
                    "capacity": capacity_status(store),
                    "attention_items": attention_items(store),
                }
            )
        elif args.command == "inbox":
            from .status_views import attention_items

            emit({"items": attention_items(store)})
        elif args.command == "off":
            store.update_settings(enabled=False)
            emit({"settings": store.get_settings(), "state": "draining"})
        elif args.command == "on":
            settings = store.get_settings()
            validate(settings, executable=True)
            if not args.no_start:
                from .executors import preflight

                preflight(settings)
            if args.no_start:
                from .locks import exclusive

                with exclusive(state_dir / "startup.lock") as admitted:
                    if not admitted:
                        raise OSError("Worker startup or recovery is in progress")
                    store.update_settings(enabled=True)
                process = {}
            else:
                process = start_background(repo, state_dir)
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
        elif args.command == "reconcile":
            from .recovery import reconcile

            emit(
                reconcile(
                    repo,
                    store,
                    args.run_id,
                    confirm_processes_stopped=args.confirm_processes_stopped,
                    note=args.note,
                )
            )
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
