"""
MODULE: leafcutter/scripts/feedback/feedback_reader.py
GOAL: Give every feedback reader the same three answers: which file to read
      (the declared ``feedback_sink`` / ``operational_telemetry_stream``, or a
      refusal), what it read ("read N records from <path>"), and how to
      rewrite the sink without losing a concurrent append.
BUSINESS CONTEXT: AC INF-500d-4-v (ADR-069). Writers file into one durable
      location; a reader that computes its own root from where it stands
      reports a quiet, wrong zero (KI-FC-001). A rewrite that replaces the
      file loses a report a parallel drive appended meanwhile.
ARCHITECTURE: Sibling of ``submit_feedback.py`` and ``feedback_sink.py`` (the
      build deploys ``templates/scripts/feedback/`` whole, so no deploy-map
      entry is needed). The declaration is read through
      ``feedback_sink.read_declared`` -- never a second parser. Resolving and
      announcing create nothing. Rewrites keep the inode (truncate and write
      through the locked descriptor) so an appender waiting on the lock
      appends to the same file afterwards; a dated copy of the original is
      kept beside the sink for the duration of the rewrite so a failed write
      loses nothing.
"""

from __future__ import annotations

import json
import shutil
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl as _fcntl  # POSIX only; not available on Windows
except ImportError:
    _fcntl = None

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import feedback_sink  # noqa: E402

_REBUILD = "python scripts/build.py --target-dir <project-root>"


def resolve(output_root: Path, label: str, **explicit: str | None) -> dict[str, Path] | None:
    """Map each declaration key to the path to read: the explicit argument, else the declared value.

    *explicit* maps a declaration key (``feedback_sink``, ...) to the caller's
    path argument or ``None``. The declaration is consulted only for keys with
    no explicit path. When it cannot supply them one stderr line names the
    expected declaration and the failed condition, and ``None`` comes back --
    never a working-directory or script-relative guess.
    """
    wanted = tuple(key for key, value in explicit.items() if not value)
    declared: dict[str, str] = {}
    if wanted:
        values, condition = feedback_sink.read_declared(output_root, wanted)
        if values is None:
            print(
                f"[{label}] ERROR: no usable build-time declaration "
                f"{feedback_sink.declaration_path(output_root)} ({condition}). Refusing to guess a "
                f"location from the working directory or the script location. Rebuild ({_REBUILD}) "
                "to declare it, or pass the path explicitly.",
                file=sys.stderr,
            )
            return None
        declared = values
    return {key: Path(value or declared[key]) for key, value in explicit.items()}


def _populated_records(path: Path) -> int:
    """Return the number of non-blank lines in *path*, or 0 when it is absent or unreadable."""
    if not path.is_file():
        return 0
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except (OSError, UnicodeDecodeError) as exc:
        print(f"WARNING: could not inspect {path}: {exc}", file=sys.stderr)
        return 0


def _legacy_note(output_root: Path, sink: Path) -> str:
    """Name each populated pre-declaration feedback.jsonl that differs from *sink*, or return ''."""
    named = []
    for candidate in (output_root / "debugging" / "logs", output_root.parent / "debugging" / "logs"):
        legacy = candidate / "feedback.jsonl"
        records = _populated_records(legacy)
        if records and legacy.resolve() != sink:
            named.append(f"{legacy} ({records} records)")
    if not named:
        return ""
    return (
        f"; NOTE: {', '.join(named)} predate the declaration and differ from this sink -- "
        "not read, merged, moved or deleted"
    )


def report(label: str, sink: Path, count: int, legacy_root: Path | None) -> None:
    """Print the one stderr line naming the absolute *sink* read and the *count* of records found.

    With a *legacy_root* (the output root, for a feedback sink read by default)
    a populated pre-declaration sink is named on the same line, once. ``None``
    skips that check: an explicit path is honoured as given, and a telemetry
    stream has no legacy feedback file.
    """
    absolute = sink.resolve()
    note = "" if legacy_root is None else _legacy_note(legacy_root, absolute)
    print(f"[{label}] read {count} records from {absolute}{note}", file=sys.stderr)


@contextmanager
def exclusive_sink(path: Path):
    """Open *path* for a read-modify-write under the exclusive lock ``submit_feedback.py`` takes.

    Exits 2 (like the former readers) when the file cannot be opened. The
    descriptor stays valid for :func:`load_entries` and :func:`replace_entries`.
    """
    try:
        fh = open(path, "r+", encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: Cannot read {path}: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    with fh:
        if _fcntl is not None:
            _fcntl.flock(fh, _fcntl.LOCK_EX)
        try:
            yield fh
        finally:
            if _fcntl is not None:
                _fcntl.flock(fh, _fcntl.LOCK_UN)


def load_entries(fh, path: Path) -> list[dict]:
    """Parse every non-blank line of the locked *fh*; exit 2 on an unreadable file or a malformed line."""
    try:
        lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        print(f"ERROR: Cannot read {path}: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    entries: list[dict] = []
    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError as exc:
            print(f"ERROR: Malformed JSON on line {lineno} of {path}: {exc}", file=sys.stderr)
            raise SystemExit(2) from exc
    return entries


def replace_entries(fh, path: Path, entries: list[dict]) -> None:
    """Rewrite the locked *fh* in place with *entries*, one JSON object per line; exit 2 on a write error.

    The inode is kept, so the truncate-and-write cannot be atomic. A copy of the original is therefore
    made beside the sink first (``<sink>.bak-<UTC timestamp>``) and removed once the rewrite succeeded;
    when the rewrite fails the error names that copy, so the records stay recoverable. If the copy cannot
    be made the sink is left untouched.
    """
    backup = path.with_name(f"{path.name}.bak-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    try:
        shutil.copyfile(path, backup)
    except OSError as exc:
        print(f"ERROR: Cannot write {path}: could not make a safety copy at {backup} first ({exc}); "
              "the sink was left untouched", file=sys.stderr)
        backup.unlink(missing_ok=True)
        raise SystemExit(2) from exc
    try:
        fh.seek(0)
        fh.truncate()
        for entry in entries:
            fh.write(json.dumps(entry, separators=(",", ":")) + "\n")
        fh.flush()
    except OSError as exc:
        print(f"ERROR: Cannot write {path}: {exc}; the original records are kept at {backup}", file=sys.stderr)
        raise SystemExit(2) from exc
    backup.unlink(missing_ok=True)
