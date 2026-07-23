"""
MODULE: pause_store
GOAL: Durable persistence helpers for the BO-2300 pause/resume mechanism.
    Provides write and read CLI subcommands for storing pending-question records
    on disk so the JS workflow engine (which has no filesystem access) can
    delegate persistence to a dispatched Python agent.
BUSINESS CONTEXT: When the workflow engine encounters a gate that requires a
    human answer before proceeding, it records a "paused run" entry so the
    session can resume later without losing state. The agent dispatched by the
    JS engine runs this CLI to write or read those records safely and
    idempotently. Idempotency prevents duplicate records when the same gate is
    replayed; TTL-based staleness detection prevents resume attempts on records
    that are too old to be acted upon.
ARCHITECTURE: Core functions write_record() and read_record() operate on
    explicit Path arguments (pure I/O, directly testable). The CLI is a thin
    argparse wrapper that resolves the store directory from --store-dir or a
    git-derived default, then delegates to the core functions. Both write and
    read print exactly one JSON object to stdout; all diagnostic messages go to
    stderr via a module-level logger. File format: one pretty-printed JSON file
    per run_id at <store>/<run_id>.json. write is idempotent when the same
    run_id+gate_id are seen again; read supports explicit --now override for
    deterministic TTL tests.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Default TTL: 24 hours in seconds
_DEFAULT_TTL_SECONDS = 86400

# Sub-dir under project root where paused-run records are stored by default
_DEFAULT_STORE_SUBDIR = ".leafcutter/paused_runs"


# ---------------------------------------------------------------------------
# Store-dir resolution
# ---------------------------------------------------------------------------


def _resolve_project_root() -> Path:
    """Detect the project root via git rev-parse, falling back to cwd.

    Returns:
        Absolute Path to the project root. Falls back to cwd with a WARNING
        when not inside a git repository or when git is unavailable.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).resolve()
        logger.warning("Not inside a git repository; using cwd as project root")
    except OSError as exc:
        logger.warning("git not available: %s — falling back to cwd", exc)
    return Path.cwd().resolve()


def _resolve_store_dir(store_dir: str | None) -> Path:
    """Resolve the store directory from an explicit path or a git-derived default.

    Args:
        store_dir: Caller-supplied directory path string, or None to derive
            from the project root via git rev-parse.

    Returns:
        Absolute Path to the store directory (not yet created).
    """
    if store_dir is not None:
        return Path(store_dir).resolve()
    project_root = _resolve_project_root()
    return project_root / _DEFAULT_STORE_SUBDIR


# ---------------------------------------------------------------------------
# Core: write
# ---------------------------------------------------------------------------


def write_record(store_path: Path, run_id: str, record: dict) -> dict:
    """Write a pending-question record to disk under store_path.

    If the record does not contain a ``created_at`` key, the current epoch
    seconds (int) is added before anything is written or checked. If a file for
    ``run_id`` already exists and its ``gate_id`` matches the incoming record,
    the write is skipped (idempotent — ``created_at`` is never mutated).
    Otherwise the file is written (or overwritten) with pretty-printed JSON.

    Args:
        store_path: Absolute directory where records are stored. Created if
            absent (including parent directories).
        run_id: Unique run identifier; used as the filename stem.
        record: Dict containing the pending-question payload. Should include
            ``gate_id``; will gain ``created_at`` if absent.

    Returns:
        On success: ``{"ok": True, "idempotent": <bool>, "path": "<abs path>"}``.
        On failure: ``{"ok": False, "error": "<message>"}``.
    """
    record_path = store_path / f"{run_id}.json"

    # Stamp created_at before the idempotency check so the original timestamp
    # is preserved on an idempotent replay (the check reads it from disk).
    if "created_at" not in record:
        record = {**record, "created_at": int(time.time())}

    # Idempotency: if the file already exists with the same gate_id, skip write
    if record_path.exists():
        try:
            existing = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Cannot read existing record %s: %s — will overwrite", record_path, exc)
            existing = {}
        if existing.get("gate_id") == record.get("gate_id"):
            return {"ok": True, "idempotent": True, "path": str(record_path)}

    # Ensure the store directory exists
    try:
        store_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("Cannot create store directory %s: %s", store_path, exc)
        return {"ok": False, "error": str(exc)}

    # Write the record as pretty-printed JSON
    try:
        record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot write record %s: %s", record_path, exc)
        return {"ok": False, "error": str(exc)}

    return {"ok": True, "idempotent": False, "path": str(record_path)}


# ---------------------------------------------------------------------------
# Core: read
# ---------------------------------------------------------------------------


def _is_stale(record: dict, ttl_seconds: int, now: int) -> bool:
    """Determine whether a record is stale.

    A record is stale when any of the following is true:
    - The ``stale`` key is explicitly set to ``True``; OR
    - ``ttl_seconds`` is positive AND the record has a ``created_at`` field
      AND ``(now - created_at) > ttl_seconds``.

    Args:
        record: The parsed record dict.
        ttl_seconds: Configured TTL in seconds. Zero or negative disables
            TTL-based staleness.
        now: Current epoch seconds used for the TTL comparison.

    Returns:
        True when the record is considered stale, False otherwise.
    """
    if record.get("stale") is True:
        return True
    if ttl_seconds > 0 and "created_at" in record:
        age = now - int(record["created_at"])
        if age > ttl_seconds:
            return True
    return False


def read_record(
    store_path: Path,
    run_id: str,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    now: int | None = None,
) -> dict:
    """Read a pending-question record from disk.

    A missing file or a file that cannot be parsed as JSON is reported as
    ``exists=False`` (exit 0 — absence is normal during polling). A parse
    error is logged at WARNING level so callers can distinguish a corrupt
    record from a plain absence.

    Args:
        store_path: Absolute directory where records are stored.
        run_id: Unique run identifier; used as the filename stem.
        ttl_seconds: Seconds after which a record is considered stale.
            Zero or negative disables TTL-based staleness. Default: 86400.
        now: Current epoch seconds for TTL comparison. Defaults to
            ``int(time.time())`` when None (override for deterministic tests).

    Returns:
        ``{"exists": <bool>, "stale": <bool>, "record": <dict|null>}``.
    """
    record_path = store_path / f"{run_id}.json"
    _now = int(time.time()) if now is None else now

    if not record_path.exists():
        return {"exists": False, "stale": False, "record": None}

    try:
        raw = record_path.read_text(encoding="utf-8")
        record = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Cannot parse record %s: %s", record_path, exc)
        return {"exists": False, "stale": False, "record": None}

    stale = _is_stale(record, ttl_seconds, _now)
    return {"exists": True, "stale": stale, "record": record}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the argument parser with write and read subcommands.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="pause_store.py",
        description=(
            "Durable persistence for the BO-2300 pause/resume mechanism. "
            "Stores pending-question records as JSON files under a configurable "
            "store directory."
        ),
    )
    parser.add_argument(
        "--store-dir",
        default=None,
        metavar="DIR",
        help=(
            "Directory in which records are stored. "
            "Defaults to <project_root>/.leafcutter/paused_runs/ "
            "(project_root detected via 'git rev-parse --show-toplevel'; "
            "falls back to cwd when not in a git repo, with a WARNING)."
        ),
    )

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # --- write subcommand ---
    write_p = subparsers.add_parser("write", help="Write a pending-question record to disk.")
    write_p.add_argument(
        "--run-id",
        required=True,
        metavar="ID",
        help="Unique run identifier used as the filename stem.",
    )
    write_p.add_argument(
        "--record",
        required=True,
        metavar="JSON_STRING",
        help=(
            "JSON string containing the pending-question payload. "
            "Expected keys: run_id, gate_id, question, context, status. "
            "'created_at' (epoch int) is added automatically if absent."
        ),
    )

    # --- read subcommand ---
    read_p = subparsers.add_parser("read", help="Read a pending-question record from disk.")
    read_p.add_argument(
        "--run-id",
        required=True,
        metavar="ID",
        help="Unique run identifier used as the filename stem.",
    )
    read_p.add_argument(
        "--ttl-seconds",
        type=int,
        default=_DEFAULT_TTL_SECONDS,
        metavar="N",
        help=f"Seconds after which a record is stale (default: {_DEFAULT_TTL_SECONDS}).",
    )
    read_p.add_argument(
        "--now",
        type=int,
        default=None,
        metavar="EPOCH",
        help="Override the current epoch seconds for deterministic TTL tests.",
    )

    return parser


def _cmd_write(args: argparse.Namespace) -> int:
    """Execute the write subcommand.

    Args:
        args: Parsed CLI arguments containing run_id, record, and store_dir.

    Returns:
        0 on success; 1 on invalid JSON input or write failure.
    """
    try:
        record = json.loads(args.record)
    except json.JSONDecodeError as exc:
        result: dict = {"ok": False, "error": f"Invalid JSON for --record: {exc}"}
        print(json.dumps(result))
        return 1

    store_path = _resolve_store_dir(args.store_dir)
    result = write_record(store_path, args.run_id, record)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


def _cmd_read(args: argparse.Namespace) -> int:
    """Execute the read subcommand.

    Always exits 0 — a missing or unparseable record is reported as
    ``exists=false`` in the JSON output, not as a non-zero exit code.

    Args:
        args: Parsed CLI arguments containing run_id, ttl_seconds, now,
            and store_dir.

    Returns:
        Always 0.
    """
    store_path = _resolve_store_dir(args.store_dir)
    result = read_record(store_path, args.run_id, args.ttl_seconds, args.now)
    print(json.dumps(result))
    return 0


def main() -> int:
    """Entry point for pause_store.py.

    Configures root logging to WARNING, parses CLI arguments, and dispatches
    to the appropriate subcommand handler.

    Returns:
        0 on success; non-zero on write failure or invalid input.
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    parser = _build_arg_parser()
    args = parser.parse_args()

    if args.subcommand == "write":
        return _cmd_write(args)
    return _cmd_read(args)


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-07-21 [python-coder/BO-2300-pause-resume]: Created as the CLI
  persistence helper for the BO-2300 pause/resume mechanism. The JS engine
  has no filesystem access; a dispatched agent runs this CLI instead.
  Core functions write_record() / read_record() accept explicit Path args so
  unit tests can drive them without subprocess. Idempotency: same
  run_id+gate_id writes are no-ops and never mutate created_at. TTL staleness
  and the explicit "stale": true flag are both honoured by _is_stale().
  Store dir defaults to <git-root>/.leafcutter/paused_runs/ with a WARNING
  fallback to cwd when not in a git repo. The --now override in the read
  subcommand exists solely for deterministic test assertions.
====================================================================
"""
