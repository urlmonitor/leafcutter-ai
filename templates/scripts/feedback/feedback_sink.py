"""
MODULE: leafcutter/scripts/feedback/feedback_sink.py
GOAL: Decide where ``submit_feedback.py`` writes when no ``--jsonl`` is given:
      the ``feedback_sink`` the install's build-time declaration records, or a
      one-line refusal that names the declaration and the failed condition.
BUSINESS CONTEXT: AC INF-500d-4-i / INF-500d-4-iv (ADR-069). A per-drive
      worktree is deleted when the drive ends, so a sink derived from where the
      script or the caller happens to stand loses the report with it
      (KI-FC-001). The only enduring answer is the absolute location the build
      recorded, and when that cannot be read the writer must say so rather than
      write somewhere disposable.
ARCHITECTURE: Sibling of ``submit_feedback.py`` (the build deploys
      ``templates/scripts/feedback/`` whole, so no deploy-map entry is needed).
      It reads the declaration through ``scripts/knowledge/sink_resolution.py``
      (``read_absolute_values``) rather than parsing the file a second time. It
      only inspects the filesystem; creating the log directory is the
      caller's job (only under a live enduring root), so a refusal creates
      nothing. "Is the enduring root gone?" is answered by
      ``sink_resolution.enduring_root_exists``, the harvester's own rule. No git, no working-directory
      lookup, no walk for ``.claude/``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_STREAM_KEYS = ("feedback_sink", "operational_telemetry_stream")
_REBUILD = "python scripts/build.py --target-dir <project-root>"


def declaration_path(output_root: Path) -> Path:
    """Return the build-time declaration file this install must carry."""
    return output_root / "config" / "knowledge_sink.json"


def _load_sink_resolution(output_root: Path):
    """Load the shared declaration reader that lives beside this package, or None."""
    module_path = output_root / "scripts" / "knowledge" / "sink_resolution.py"
    spec = importlib.util.spec_from_file_location("sink_resolution", module_path)
    if spec is None or spec.loader is None or not module_path.is_file():
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read(reader, output_root: Path, keys: tuple[str, ...]) -> tuple[dict[str, str] | None, str | None]:
    """Read *keys* through *reader*; a stream key must satisfy ``read_usable_stream`` (ADR-069 section 4)."""
    values: dict[str, str] = {}
    for key in keys:
        if key in _STREAM_KEYS:
            stream, why = reader.read_usable_stream(output_root, key)
            if stream is None:
                return None, why
            values[key] = str(stream)
            continue
        found, condition = reader.read_absolute_values(output_root, (key,))
        if found is None:
            return None, condition
        values.update(found)
    return values, None


def read_declared(output_root: Path, keys: tuple[str, ...]) -> tuple[dict[str, str] | None, str | None]:
    """Return ``({key: absolute path}, None)`` or ``(None, condition)`` for *keys* of the declaration.

    ``feedback_sink`` and ``operational_telemetry_stream`` are streams and are
    returned only when the declaration also records an absolute
    ``operational_log_root`` with the stream directly under it -- the one
    usable-stream rule, shared with ``sink_resolution.read_usable_stream``.
    """
    reader = _load_sink_resolution(output_root)
    if reader is None:
        return None, "unreadable: the shared declaration reader scripts/knowledge/sink_resolution.py is not deployed"
    return _read(reader, output_root, keys)


def _failure(output_root: Path) -> tuple[Path | None, str | None]:
    """Return ``(sink, None)`` for a usable declaration, else ``(None, condition)``.

    "Is the enduring root gone?" is asked of ``sink_resolution.enduring_root_exists`` itself, so the
    harvester and this writer agree on every layout. A log directory (or ``debugging``) that was
    simply never created under a live project is a first write, not staleness.
    """
    reader = _load_sink_resolution(output_root)
    if reader is None:
        return None, "unreadable: the shared declaration reader scripts/knowledge/sink_resolution.py is not deployed"
    values, condition = _read(reader, output_root, ("feedback_sink",))
    if values is None:
        return None, condition
    sink = Path(values["feedback_sink"])
    if not reader.enduring_root_exists(output_root):
        return None, (
            f"stale: {reader.enduring_holder(sink.parent)} (the enduring root that should hold {sink.parent}) "
            "no longer exists, so the project was moved or deleted after the build recorded it"
        )
    return sink, None


def resolve_feedback_sink(output_root: Path) -> tuple[Path | None, str | None]:
    """Resolve the declared sink, or the one-line refusal to print instead.

    Returns ``(sink, None)`` when the declaration is usable, else ``(None,
    message)`` where *message* is a single line naming the expected declaration
    and the condition that failed (absent, unreadable, unparseable, missing,
    not absolute, stale). The refusal is the "destination could not be written"
    reason of INF-500d-3: nothing was written, so it must never read as a
    written-but-uncited record. Creates nothing.
    """
    sink, condition = _failure(output_root)
    if sink is not None:
        return sink, None
    message = (
        "[submit_feedback] ERROR: destination could not be written: the durable feedback "
        f"location cannot be determined from the build-time declaration {declaration_path(output_root)} "
        f"({condition}). Refusing to fall back to the working directory or the script location; "
        f"nothing was recorded. Rebuild ({_REBUILD}) to re-declare it at this install's current location."
    )
    return None, " ".join(message.split())
