"""
MODULE: _usable_stream_parity_rows
GOAL: The 14 declaration rows of the usable-stream parity check (AC INF-500d-4-ix) and
    the cheap install each one is materialised into.
BUSINESS CONTEXT: A rule about "is this declared stream usable" only means something when
    fed every shape a declaration can take: absent, empty, unparseable, no root, a
    relative root, a stream missing / relative / outside / nested, and a valid one with the
    log directory present, missing, or its enduring root vanished (conventional AND flat).
ARCHITECTURE: No build.py is spawned. A row becomes a temp tree: ``project/`` (a REAL
    ``git init`` repository carrying the DEPLOYED sink query, telemetry skill and guard
    hook copied from the layout) beside the enduring directories the row declares. The
    declaration comes from the REAL build helper (``h.declare``) and is then round-tripped
    through ``h.rewrite_declaration`` for the shapes the helper cannot produce.
"""

from __future__ import annotations

import contextlib
import io
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

from unit_tests.feedback import _inf_500d_4_helpers as h
from unit_tests.feedback._usable_stream_parity_core import CopyRunError, run_command

_ROOT_KEY = "operational_log_root"
_STREAM_KEY = "operational_telemetry_stream"
_FLAT = "{e}/logs"
_DECLARE_LOCK = threading.Lock()


@dataclass(frozen=True)
class InstalledRow:
    """One materialised row: the whole temp tree and the paths a copy needs."""

    name: str
    tree: Path
    project: Path
    out_root: Path
    log_root: Path | None
    enduring_root: Path | None
    stream: Path | None


def _absolute(value: object) -> Path | None:
    return Path(value) if isinstance(value, str) and Path(value).is_absolute() else None


def _enduring(log_root: Path | None) -> Path | None:
    if log_root is None:
        return None
    holder = log_root.parent
    return holder.parent if holder.name == "debugging" else holder


def _copy_deployed(layout_dir: Path, out_root: Path) -> None:
    """Carry the DEPLOYED files the inline copies and the sink query live in; absent ones stay absent."""
    deployed = layout_dir / ".leafcutter"
    (out_root / "config").mkdir(parents=True)
    for rel in ("scripts/knowledge", "skills/agent-telemetry"):
        if (deployed / rel).is_dir():
            shutil.copytree(deployed / rel, out_root / rel, ignore=shutil.ignore_patterns("__pycache__"))
    guard = deployed / "hooks" / "inline_work_guard.py"
    if guard.is_file():
        (out_root / "hooks").mkdir()
        shutil.copy2(guard, out_root / "hooks" / guard.name)


@dataclass(frozen=True)
class Row:
    """A declaration recipe: how the declaration looks and which directories exist beside it.

    ``root`` and ``mkdirs`` and the values in ``changes`` are templates over ``{e}`` (the enduring
    directory), ``{x}`` (a directory outside it) and ``{root}`` (the declared log root).
    """

    name: str
    kind: str = "real"  # "absent" | "text" | "real" (written by the real build helper)
    text: str = ""
    root: str = "{e}/debugging/logs"
    mkdirs: tuple[str, ...] = ("{root}",)
    changes: tuple[tuple[str, str | None], ...] = ()

    def materialize(self, base: Path, layout_dir: Path) -> InstalledRow:
        """Build this row's cheap install under *base* (no build.py)."""
        base.mkdir(parents=True)
        project = base / "project"
        project.mkdir()
        init = run_command(["git", "init", "-q", str(project)], base, "materialize")
        if init.returncode != 0:
            reason = f"row {self.name}: git init failed: {init.stderr.strip()}"
            raise CopyRunError("materialize", reason)
        out_root = project / ".leafcutter"
        _copy_deployed(Path(layout_dir), out_root)
        tokens = {"e": str(base / "enduring"), "x": str(base / "elsewhere")}
        tokens["root"] = self.root.format(**tokens)
        for template in self.mkdirs:
            Path(template.format(**tokens)).mkdir(parents=True, exist_ok=True)
        self._write_declaration(out_root, tokens)
        data = h.read_declaration(out_root) if self.kind == "real" else {}
        log_root = _absolute(data.get(_ROOT_KEY))
        return InstalledRow(self.name, base, project, out_root, log_root, _enduring(log_root),
                            _absolute(data.get(_STREAM_KEY)))

    def _write_declaration(self, out_root: Path, tokens: dict[str, str]) -> None:
        path = h.declaration_path(out_root)
        if self.kind == "text":
            path.write_text(self.text, encoding="utf-8")
        elif self.kind == "real":
            # the real build helper narrates what it declares; redirecting stdout is process-wide, so one at a time
            with _DECLARE_LOCK, contextlib.redirect_stdout(io.StringIO()):
                h.declare(out_root, Path(tokens["root"]))
            changes = {key: (value.format(**tokens) if value else value) for key, value in self.changes}
            h.rewrite_declaration(out_root, **changes)


def build_rows() -> list[Row]:
    """The 14 declaration rows, in the order the criteria list them."""
    return [
        Row("no_declaration_file", kind="absent"),
        Row("empty_object", kind="text", text="{}\n"),
        Row("unparseable_json", kind="text", text="{not json"),
        Row("no_operational_log_root", changes=((_ROOT_KEY, None),)),
        Row("relative_operational_log_root", changes=((_ROOT_KEY, "debugging/logs"),)),
        Row("stream_missing", changes=((_STREAM_KEY, None),)),
        Row("stream_relative", changes=((_STREAM_KEY, "agent_telemetry.jsonl"),)),
        Row("stream_outside_root", mkdirs=("{root}", "{x}"),
            changes=((_STREAM_KEY, "{x}/agent_telemetry.jsonl"),)),
        Row("stream_two_levels_under_root", mkdirs=("{root}/sub/deeper",),
            changes=((_STREAM_KEY, "{root}/sub/deeper/agent_telemetry.jsonl"),)),
        Row("valid_log_dir_present"),
        Row("valid_log_dir_missing_conventional", mkdirs=("{e}",)),
        Row("valid_log_dir_missing_flat", root=_FLAT, mkdirs=("{e}",)),
        Row("valid_enduring_root_vanished_conventional", mkdirs=()),
        Row("valid_enduring_root_vanished_flat", root=_FLAT, mkdirs=()),
    ]


# DECISION HISTORY
# ================================================================================
# - 2026-10-14 11:00 [python-coder]: Created the 14-row declaration table and its cheap installs. (#TICKET-INF-500d-4-ix)
