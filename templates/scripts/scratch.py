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
    ``sweep()`` (CLI ``sweep``) removes exactly what classify() calls expired,
    over the scratch root's items and the declared third-party leftovers
    (pre-commit's stash patch files, BO-4400f-1-ii); an active owner keeps its
    item however old it is (BO-4400f-1-i). The route workflows create their
    item through ``new-item ... --owner-pid $PPID`` so the label names the
    long-lived process that runs the drive, not the short-lived command.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
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

# Third-party leftovers (BO-4400f-1-ii), declared beside the durable-path list:
# where a tool the project does not own leaves throwaway FILES, and the exact
# top-level file names that are its leftovers. They carry no run owner, so the
# owner-unknown branch of classify() applies (age by mtime alone).
THIRD_PARTY_LEFTOVERS = (
    {
        "tool": "pre-commit",
        "home_env": "PRE_COMMIT_HOME",
        "cache_subdir": "pre-commit",
        "file_pattern": r"patch\d+(?:-\d+)?",
    },
)


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


def _user_cache_dir() -> str:
    return os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")


def scratch_root() -> str:
    """Return the absolute path of the one scratch location."""
    configured = str(_cleanup_config().get("scratch_root") or "").strip()
    if configured:
        return os.path.abspath(os.path.expanduser(configured))
    return os.path.abspath(os.path.join(_user_cache_dir(), "leafcutter", "scratch"))


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


def new_item(owner_run_id: str, route: str, owner_pid: int | None = None) -> str:
    """Create a fresh labelled item folder in the scratch root; return its path.

    ``owner_pid`` is the process whose liveness decides whether the owning run
    is still going; it defaults to the calling process. A workflow's shell step
    passes the long-lived process that runs the drive, since the short-lived
    command that creates the item exits at once.
    """
    root = scratch_root()
    os.makedirs(root, exist_ok=True)
    item = tempfile.mkdtemp(prefix=f"{_slug(route)}-{_slug(owner_run_id)}-", dir=root)
    label = {
        "owner_run_id": owner_run_id,
        "route": route,
        "pid": os.getpid() if owner_pid is None else int(owner_pid),
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
    """Return the item's label, or None when missing/unreadable/malformed.

    A plain file (a third-party leftover, a stray file in the root) carries no
    label by construction, so it is owner-unknown without a warning.
    """
    if not os.path.isdir(item):
        return None
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


def leftover_candidates() -> list[str]:
    """Return the declared third-party leftover FILES that exist right now.

    Only top-level regular files whose whole name matches the declared pattern
    are candidates; directories (a tool's installed environments), symlinks and
    every other entry in that folder never are.
    """
    found: list[str] = []
    for spec in THIRD_PARTY_LEFTOVERS:
        folder = os.environ.get(spec["home_env"]) or os.path.join(
            _user_cache_dir(), spec["cache_subdir"]
        )
        pattern = re.compile(spec["file_pattern"])
        try:
            entries = list(os.scandir(folder))
        except FileNotFoundError:
            continue
        except OSError as exc:
            logger.warning("scratch: cannot list %s leftovers in %s: %s", spec["tool"], folder, exc)
            continue
        found.extend(
            entry.path for entry in entries
            if pattern.fullmatch(entry.name) and entry.is_file(follow_symlinks=False)
        )
    return sorted(found)


def _scratch_items() -> list[str]:
    """Return every entry in the scratch root (symlinks are never followed)."""
    root = scratch_root()
    try:
        entries = list(os.scandir(root))
    except FileNotFoundError:
        return []
    except OSError as exc:
        logger.warning("scratch: cannot list scratch root %s: %s", root, exc)
        return []
    return sorted(entry.path for entry in entries if not entry.is_symlink())


def _remove(path: str) -> None:
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def sweep(now: datetime | None = None, age_limit_hours: float | None = None) -> dict:
    """Remove exactly what ``classify()`` calls expired; return the report.

    Candidates are the scratch root's items and the declared third-party
    leftovers. There is no age-only path here: every decision is classify()'s,
    so an item whose owner is still running is kept however old it is.
    Removals are counted under the ``scratch`` kind.
    """
    now = now or datetime.now(timezone.utc)
    limit = scratch_max_age_hours() if age_limit_hours is None else age_limit_hours
    removed: list[str] = []
    errors: list[dict] = []
    kept = 0
    for path in _scratch_items() + leftover_candidates():
        try:
            expired = classify(path, now, limit)["expired"]
            if expired:
                _remove(path)
        except OSError as exc:
            logger.warning("scratch: cannot sweep %s: %s", path, exc)
            errors.append({"path": path, "error": str(exc)})
            continue
        if expired:
            removed.append(path)
        else:
            kept += 1
    return {"removed": {"scratch": len(removed)}, "removed_paths": removed, "kept": kept, "errors": errors}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="scratch.py")
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("new-item", help="create a labelled scratch item")
    make.add_argument("owner_run_id")
    make.add_argument("route")
    make.add_argument("--owner-pid", type=int, default=None,
                      help="the run's long-lived process (default: this process)")
    commands.add_parser("sweep", help="remove expired scratch and declared leftovers")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI used by workflow shell steps and the sweep.

    ``new-item <owner_run_id> <route> [--owner-pid PID]`` prints one JSON line
    ``{"item": "<abs path>"}``. ``sweep`` prints the sweep report as one JSON
    line and exits 1 when any expired entry could not be removed.
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.command == "new-item":
        print(json.dumps({"item": new_item(args.owner_run_id, args.route, args.owner_pid)}))
        return 0
    report = sweep()
    print(json.dumps(report))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
