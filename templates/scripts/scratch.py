"""
MODULE: scratch.py
GOAL: Provide the one designated scratch location for throwaway files, label
    every item in it with its owner and creation time, and decide when an item
    has expired.
BUSINESS CONTEXT: Gap G7 (BO-4400f). Build routes, the quick fix and the test
    runner each left throwaway folders in the project root, in durable log
    folders (test-logs/ reached 3.4 GB) and in the system temp folder. One
    location with an owner label and one expiry rule lets every route clean up
    after itself and lets the sweep remove only what is safe to remove.
ARCHITECTURE: Pure stdlib. ``scratch_root()`` resolves the location from the
    ``worktree_cleanup`` section of skills_config.json (defaulting to
    ``<user cache dir>/leafcutter/scratch``). ``new_item()`` creates a fresh
    item folder holding ``label.json``. ``classify()`` is the single definition
    of the expiry rule; the sweep, route-end removal and the pytest plugin only
    consume it. Owner liveness is process liveness of the pid in the label.
"""

from __future__ import annotations

import json
import logging
import os
import re
import socket
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

LABEL_NAME = "label.json"
DEFAULT_AGE_LIMIT_HOURS = 24
DEFAULT_DURABLE_PATHS = ["debugging/logs", "test-logs"]
_CONFIG_RELATIVE = (".claude/skills_config.json",)


def _find_cleanup_config(start: Path) -> dict:
    """Return the ``worktree_cleanup`` section found walking up from ``start``."""
    for folder in (start, *start.parents):
        for relative in _CONFIG_RELATIVE:
            candidate = folder / relative
            if not candidate.is_file():
                continue
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                logger.warning("scratch: cannot read config %s: %s", candidate, exc)
                continue
            section = data.get("worktree_cleanup") if isinstance(data, dict) else None
            return section if isinstance(section, dict) else {}
    return {}


def _cleanup_config() -> dict:
    return _find_cleanup_config(Path.cwd())


def scratch_root() -> str:
    """Return the absolute path of the one scratch location."""
    configured = str(_cleanup_config().get("scratch_root") or "").strip()
    if configured:
        return os.path.abspath(os.path.expanduser(configured))
    cache = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.abspath(os.path.join(cache, "leafcutter", "scratch"))


def scratch_max_age_hours() -> float:
    """Return the configured age limit in hours (default 24)."""
    value = _cleanup_config().get("scratch_max_age_hours", DEFAULT_AGE_LIMIT_HOURS)
    return float(value)


def durable_paths() -> list[str]:
    """Return the declared durable folders (never treated as scratch)."""
    declared = _cleanup_config().get("durable_paths")
    if isinstance(declared, list) and declared:
        return [str(entry) for entry in declared]
    return list(DEFAULT_DURABLE_PATHS)


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-")[:40] or "x"


def new_item(owner_run_id: str, route: str) -> str:
    """Create a fresh labelled item folder in the scratch root; return its path."""
    root = scratch_root()
    os.makedirs(root, exist_ok=True)
    item = tempfile.mkdtemp(prefix=f"{_slug(route)}-{_slug(owner_run_id)}-", dir=root)
    label = {
        "owner_run_id": owner_run_id,
        "route": route,
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with open(os.path.join(item, LABEL_NAME), "w", encoding="utf-8") as handle:
            json.dump(label, handle)
    except OSError as exc:
        logger.warning("scratch: cannot write label in %s: %s", item, exc)
        raise
    return item


def _read_label(item: str) -> dict | None:
    """Return the item's label, or None when missing/unreadable/malformed."""
    try:
        with open(os.path.join(item, LABEL_NAME), encoding="utf-8") as handle:
            label = json.load(handle)
        int(label["pid"])
        datetime.fromisoformat(label["created_at"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.warning("scratch: unreadable label in %s: %s", item, exc)
        return None
    return label if isinstance(label, dict) else None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        logger.warning("scratch: cannot probe pid %s: %s", pid, exc)
        return False
    return True


def _under_durable(item: str) -> bool:
    target = os.path.abspath(item).replace(os.sep, "/")
    for declared in durable_paths():
        marker = "/" + declared.strip("/").replace(os.sep, "/") + "/"
        if marker in target + "/":
            return True
    return False


def classify(item: str, now: datetime, age_limit_hours: float) -> dict:
    """Decide whether ``item`` is expired.

    Expired iff (owner ended AND older than the limit) OR (owner unknown AND
    older than the limit). An active owner never expires; anything under a
    durable folder is never scratch.
    """
    if _under_durable(item):
        return {"expired": False, "reason": "durable_path"}
    label = _read_label(item)
    if label is None:
        created = datetime.fromtimestamp(os.stat(item).st_mtime, tz=timezone.utc)
        owner_state = "unknown"
    else:
        created = datetime.fromisoformat(label["created_at"])
        same_host = label.get("host") == socket.gethostname()
        if same_host:
            owner_state = "active" if _pid_alive(int(label["pid"])) else "ended"
        else:
            owner_state = "unknown"
    if owner_state == "active":
        return {"expired": False, "reason": "owner_active"}
    if now - created <= timedelta(hours=age_limit_hours):
        return {"expired": False, "reason": "within_age"}
    return {"expired": True, "reason": f"owner_{owner_state}_and_old"}


def main(argv: list[str] | None = None) -> int:
    """CLI used by workflow shell steps: ``new-item <owner_run_id> <route>``.

    Prints one JSON line ``{"item": "<abs path>"}`` for the fresh item.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 3 or args[0] != "new-item":
        print("usage: scratch.py new-item <owner_run_id> <route>", file=sys.stderr)
        return 2
    print(json.dumps({"item": new_item(args[1], args[2])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
