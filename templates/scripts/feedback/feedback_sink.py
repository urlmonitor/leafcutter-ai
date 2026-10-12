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
      only inspects the filesystem; creating the final log directory is the
      caller's job, so a refusal creates nothing. No git, no working-directory
      lookup, no walk for ``.claude/``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_KEYS = ("operational_log_root", "feedback_sink")
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


def _failure(output_root: Path) -> tuple[Path | None, str | None]:
    """Return ``(sink, None)`` for a usable declaration, else ``(None, condition)``."""
    reader = _load_sink_resolution(output_root)
    if reader is None:
        return None, "unreadable: the shared declaration reader scripts/knowledge/sink_resolution.py is not deployed"
    values, condition = reader.read_absolute_values(output_root, _KEYS)
    if values is None:
        return None, condition
    sink = Path(values["feedback_sink"])
    if not sink.parent.exists() and not sink.parent.parent.exists():
        return None, (
            f"stale: {sink.parent.parent} (the enduring root that should hold {sink.parent}) "
            "no longer exists"
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
        f"nothing was recorded. Rebuild ({_REBUILD}) to declare it."
    )
    return None, " ".join(message.split())
