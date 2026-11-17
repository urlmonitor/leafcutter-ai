"""
MODULE: scripts/build_orchestration/gate_verdict_records.py
GOAL: The markers and gate-verdict records of /build-epic: where they live, how they are written
    (atomically), how they are read back, and the digest of the code a wrong-version verdict covers.
BUSINESS CONTEXT: TQ-500g-1-viii. A ticket driven through /build-epic must not be committed until the
    red-baseline reader and the wrong-version runner have each left their own verdict for it. The CLIs
    write the records, build-epic.js opens and closes a marker around each ticket, and the pre-commit hook
    check_build_epic_gate_verdicts.py reads them. Nothing here reads a ticket comment or the supervisor's
    account of a gate.
ARCHITECTURE: Public module (no leading underscore) because the hook in commit_guardian/ imports it, and
    because the gate CLIs (fast_lane.py heavy_lane_gate, wrong_version_runner.py, wrong_version_gate.py)
    import its writer. Records live in ``<git-dir>/leafcutter/gate-verdicts/<ticket-key>/`` (git-dir is
    ``git rev-parse --absolute-git-dir`` in the worktree, the root _wvr_gate uses), outside the working tree,
    so they are private to the worktree, survive a crash and are never committed. Files: ``open.json`` (the
    marker), ``red_baseline.json`` and ``wrong_version.json``. The ticket key is one plain path segment.
    CLI: ``open --worktree W --ticket-key K --ticket-path P`` and ``close --worktree W (--ticket-key K | --all)``,
    each printing one JSON object and exiting 0 only on success.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import posixpath
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_LOG = logging.getLogger("gate_verdict_records")
_KEY_RE = re.compile(r"^[A-Za-z0-9._-]+$")
EXCLUDED_PREFIXES = ("tickets/", "docs/acceptance-criteria/", "changelogs/")
_GIT_TIMEOUT_SECONDS = 60
GATES = ("red_baseline", "wrong_version")


def valid_key(key: object) -> bool:
    """Say whether *key* is one plain path segment matching ``^[A-Za-z0-9._-]+$`` (never ``.`` or ``..``).

    Args:
        key: The candidate ticket key.

    Returns:
        True when the key may be used as a folder name.
    """
    return isinstance(key, str) and _KEY_RE.fullmatch(key) is not None and key not in {".", ".."}


def _git(cwd: Path, *args: str) -> str:
    """Run one git command in *cwd* and return its stdout.

    Raises:
        subprocess.SubprocessError: git failed or timed out.
        OSError: git could not be started.
    """
    try:
        proc = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=_GIT_TIMEOUT_SECONDS, check=True, encoding="utf-8"
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _LOG.warning("git %s failed in %s: %s", args[0], cwd, exc)
        raise
    return proc.stdout


def verdicts_root(worktree: Path) -> Path:
    """Return ``<git-dir>/leafcutter/gate-verdicts`` for *worktree* (not created)."""
    return Path(_git(Path(worktree), "rev-parse", "--absolute-git-dir").strip()) / "leafcutter" / "gate-verdicts"


def now_utc() -> str:
    """Return the current time as ISO-8601 UTC, to the second."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def atomic_write(path: Path, text: str) -> None:
    """Write *text* to *path* through a temporary file in the same folder, then replace.

    A cut-short write never leaves a truncated file at *path*.

    Raises:
        OSError: The folder or file could not be written; nothing is left at *path* by this call.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def is_excluded(rel: str) -> bool:
    """Say whether *rel* (worktree-relative, POSIX) is outside the code a digest covers."""
    return rel.startswith(EXCLUDED_PREFIXES)


def code_paths(worktree: Path, base_ref: str) -> dict[str, str | None]:
    """Map every path changed against *base_ref* (tracked and untracked, non-ignored) to its sha256.

    The ticket files, the AC store and the changelogs are left out. A deleted path maps to None.

    Raises:
        subprocess.SubprocessError: git failed.
        OSError: A changed file could not be read.
    """
    root = Path(worktree)
    changed = set(_git(root, "diff", "--name-only", "-z", "--no-renames", base_ref, "--").split("\0"))
    changed |= set(_git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0"))
    out: dict[str, str | None] = {}
    for rel in sorted(p for p in changed if p and not is_excluded(p)):
        target = root / rel
        out[rel] = hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else None
    return out


def digest(paths: dict[str, str | None]) -> str:
    """Return the sha256 over the sorted *paths* map."""
    return hashlib.sha256(json.dumps(paths, sort_keys=True).encode("utf-8")).hexdigest()


def write_record(worktree: Path, key: str, gate: str, ids: list[str], verdict: dict, base_ref: str | None = None) -> str | None:
    """Write ``<gate>.json`` for *key* atomically; return None, or the text naming why it failed.

    Args:
        worktree: The worktree whose git dir holds the records.
        key: The ticket key (one plain path segment).
        gate: ``red_baseline`` or ``wrong_version``.
        ids: The AC ids the gate ran for.
        verdict: The gate's own JSON verdict, stored verbatim.
        base_ref: The wrong-version base ref (the code paths are taken against it).

    Returns:
        None on success, else a message the caller turns into ``gate_passed: false``.
    """
    if not valid_key(key) or gate not in GATES:
        return f"ticket key {key!r} is not one plain path segment"
    body: dict = {"gate": gate, "ticket_key": key, "ids": list(ids), "written_at": now_utc(), "verdict": verdict}
    try:
        if gate == "wrong_version":
            paths = code_paths(Path(worktree), base_ref or "HEAD")
            body.update(base_ref=base_ref or "HEAD", paths=paths, code_digest=digest(paths))
        atomic_write(verdicts_root(Path(worktree)) / key / f"{gate}.json", json.dumps(body))
    except (OSError, subprocess.SubprocessError, TypeError, ValueError) as exc:
        _LOG.warning("record %s for %s not written: %s", gate, key, exc)
        return f"record write failed for {gate} of {key}: {exc}"
    return None


def remove_record(worktree: Path, key: str, gate: str) -> str | None:
    """Delete ``<gate>.json`` for *key* when present; return None, or the text naming why it failed."""
    try:
        (verdicts_root(Path(worktree)) / key / f"{gate}.json").unlink(missing_ok=True)
    except (OSError, subprocess.SubprocessError) as exc:
        _LOG.warning("record %s for %s not removed: %s", gate, key, exc)
        return f"record {gate} of {key} could not be removed: {exc}"
    return None


def read_record(folder: Path, gate: str) -> tuple[dict | None, str | None]:
    """Read ``<gate>.json`` in *folder*; return ``(record, None)`` or ``(None, "missing" | "unreadable")``.

    A record is unreadable when it does not parse (a cut-off write), is not an object of the
    pinned shape, or names a different gate.
    """
    path = folder / f"{gate}.json"
    if not path.is_file():
        return None, "missing"
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, "unreadable"
    ok = isinstance(rec, dict) and rec.get("gate") == gate and isinstance(rec.get("verdict"), dict)
    ok = ok and isinstance(rec.get("ticket_key"), str) and isinstance(rec.get("ids"), list)
    if ok and gate == "wrong_version":
        paths = rec.get("paths")
        ok = isinstance(paths, dict) and all(v is None or isinstance(v, str) for v in paths.values())
    return (rec, None) if ok else (None, "unreadable")


def rel_posix(path: str) -> str:
    """Normalise a repo-relative path: backslashes to ``/``, a leading ``./`` and ``a/../`` folded away."""
    return posixpath.normpath(path.replace("\\", "/"))


def read_source_ac(ticket_file: Path) -> list[str]:
    """Return the ``source_ac`` ids of a ticket file's YAML frontmatter (``[]`` when the field is absent).

    Raises:
        OSError: The file could not be read.
        ValueError: The frontmatter is missing, is not valid YAML, is not a mapping, or ``source_ac``
            is neither a string nor a list of strings.
    """
    import yaml

    text = ticket_file.read_text(encoding="utf-8")
    parts = text.split("---", 2) if text.startswith("---") else []
    if len(parts) < 3:
        msg = f"{ticket_file.name} has no YAML frontmatter"
        raise ValueError(msg)
    try:
        front = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        msg = f"{ticket_file.name} frontmatter is not valid YAML: {exc}"
        raise ValueError(msg) from exc
    if not isinstance(front, dict):
        msg = f"{ticket_file.name} frontmatter is not a mapping"
        raise ValueError(msg)
    value = front.get("source_ac")
    ids = [] if value is None else [value] if isinstance(value, str) else value
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        msg = f"{ticket_file.name} source_ac is not a list of strings"
        raise ValueError(msg)
    return ids


def _relative_ticket_path(worktree: Path, ticket_path: str) -> str | None:
    """Return *ticket_path* as a worktree-relative POSIX path, or None when it lies outside the worktree."""
    raw = Path(ticket_path)
    if not raw.is_absolute():
        return rel_posix(ticket_path)
    try:
        rel = os.path.relpath(raw.resolve(), worktree.resolve()).replace("\\", "/")
    except ValueError:
        return None
    return None if rel.startswith("..") else rel_posix(rel)


def _open(args: argparse.Namespace) -> dict:
    """Open the marker for one ticket."""
    if not valid_key(args.ticket_key):
        return {"opened": False, "reason": f"ticket key {args.ticket_key!r} is not one plain path segment"}
    worktree = Path(args.worktree)
    rel = _relative_ticket_path(worktree, args.ticket_path)
    if rel is None:
        return {"opened": False, "reason": f"ticket path {args.ticket_path!r} is outside the worktree"}
    ticket_file = worktree / rel
    try:
        # A ticket file not on disk yet has nothing to read; an existing one that cannot be read fails closed.
        source_ac = read_source_ac(ticket_file) if ticket_file.is_file() else []
    except (OSError, ValueError) as exc:
        _LOG.warning("marker not opened for %s: %s", args.ticket_key, exc)
        return {"opened": False, "reason": f"ticket frontmatter source_ac cannot be read: {exc}"}
    marker = {"ticket_key": args.ticket_key, "ticket_path": rel, "source_ac": source_ac, "opened_at": now_utc()}
    atomic_write(verdicts_root(worktree) / args.ticket_key / "open.json", json.dumps(marker))
    return {"opened": True, "ticket_key": args.ticket_key}


def _close(args: argparse.Namespace) -> dict:
    """Close one marker, or every marker with ``--all`` (the records stay)."""
    root = verdicts_root(Path(args.worktree))
    if args.all:
        keys = sorted(d.name for d in root.iterdir() if d.is_dir()) if root.is_dir() else []
    elif valid_key(args.ticket_key):
        keys = [args.ticket_key]
    else:
        return {"closed": [], "ok": False, "reason": f"ticket key {args.ticket_key!r} is not one plain path segment"}
    for key in keys:
        (root / key / "open.json").unlink(missing_ok=True)
    return {"closed": keys, "ok": True}


def _parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description="Gate-verdict markers for /build-epic (TQ-500g-1-viii)")
    sub = parser.add_subparsers(dest="command", required=True)
    opn = sub.add_parser("open", help="Open the marker for one ticket")
    opn.add_argument("--worktree", required=True)
    opn.add_argument("--ticket-key", required=True)
    opn.add_argument("--ticket-path", required=True)
    cls = sub.add_parser("close", help="Close one marker, or all of them")
    cls.add_argument("--worktree", required=True)
    cls.add_argument("--ticket-key", default="")
    cls.add_argument("--all", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI; print one JSON object and return 0 only on success."""
    args = _parser().parse_args(argv)
    try:
        out = _open(args) if args.command == "open" else _close(args)
    except (OSError, subprocess.SubprocessError) as exc:
        _LOG.warning("%s failed: %s", args.command, exc)
        out = {"opened" if args.command == "open" else "ok": False, "reason": f"{args.command} failed: {exc}"}
    print(json.dumps(out))
    return 0 if out.get("opened") is True or out.get("ok") is True else 1


if __name__ == "__main__":
    sys.exit(main())
