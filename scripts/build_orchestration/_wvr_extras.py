"""
MODULE: scripts/build_orchestration/_wvr_extras.py
GOAL: The ONE reader of the extra wrong versions a test writer left "to run later":
    it finds the files, checks them and attaches each extra to the in-scope test it
    names, so the writer's ``list`` step and the runner see exactly the same set.
BUSINESS CONTEXT: TQ-500g-2-ii (user decisions Q2 2026-09-28 and OQ-1 (A) 2026-10-22).
    A database test writer's hand-off names wrong versions its tests should catch
    (TQ-500f-4). They are run and reported, but a survivor among them never stops the
    work. A name spelled like a version the test's own entry names, or like "the fix
    undone", is not an extra: it stays the blocking named version.
ARCHITECTURE: Files are ``<git-dir>/leafcutter/to-run-later/<ac-id>.json``, found by
    requirement id, shaped ``{ac_id, to_run_later: [{test, wrong_version, reason}]}``
    with ``test`` = ``<repo-relative POSIX test file>::<test function>``. An absent file
    means none. Called from ``_wvr_scope.resolve_scope`` (so ``_wvw_list`` and the runner
    both get it). No import of ``_wvr_scope`` (it imports this module): the matching-key
    function is passed in. An unreadable or malformed file, and an extra whose test is
    not a resolved in-scope test, each give one note ``(subject, detail)`` the runner
    reports as a non-blocking row; nothing is dropped silently and nothing stops the work.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_LOG = logging.getLogger("wrong_version_runner")
_PLAIN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
NOTE_RESULT = "not_in_scope"


@dataclass
class Extra:
    """One extra wrong version and the test it is for."""

    test: str
    wrong_version: str


@dataclass
class ExtrasRead:
    """What the to-run-later files of a run hold: the extras and the notes about what was unusable."""

    items: list[Extra] = field(default_factory=list)
    notes: list[tuple[str, str]] = field(default_factory=list)


def _locations(test_root: Path) -> tuple[Path, Path] | None:
    """Return ``(git dir, work tree root)`` for *test_root*, or ``None`` when git cannot say."""
    try:
        proc = subprocess.run(["git", "rev-parse", "--absolute-git-dir", "--show-toplevel"], cwd=test_root,
                              capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        _LOG.warning("to-run-later: git could not run: %s", exc)
        return None
    lines = proc.stdout.splitlines()
    if proc.returncode != 0 or len(lines) < 2:
        _LOG.warning("to-run-later: %s is not inside a git working tree", test_root)
        return None
    return Path(lines[0].strip()), Path(lines[1].strip())


def _entry(raw: Any) -> Extra | None:
    """Return the :class:`Extra` of one file entry, or ``None`` when it is malformed."""
    if not isinstance(raw, dict):
        return None
    test, version = raw.get("test"), raw.get("wrong_version")
    if not (isinstance(test, str) and isinstance(version, str)) or not test.strip() or not version.strip():
        return None
    return Extra(test.strip(), version.strip())


def _read_file(path: Path) -> tuple[list[Extra], list[tuple[str, str]]]:
    """Read one to-run-later file; return its extras and the notes about what was unusable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [], [(path.name, f"to-run-later file {path.name} is unreadable: {exc}")]
    listed = data.get("to_run_later") if isinstance(data, dict) else None
    if not isinstance(listed, list):
        return [], [(path.name, f"to-run-later file {path.name} is malformed: no to_run_later list")]
    items: list[Extra] = []
    notes: list[tuple[str, str]] = []
    for index, raw in enumerate(listed):
        extra = _entry(raw)
        if extra is None:
            notes.append((path.name, f"to-run-later file {path.name} entry {index} is malformed: needs test and wrong_version"))
        else:
            items.append(extra)
    return items, notes


def read_extras(test_root: Path, ac_ids: Sequence[str]) -> tuple[ExtrasRead, Path | None]:
    """Read the to-run-later files of *ac_ids*; return the reading and the work tree root.

    Args:
        test_root: A directory inside the work tree (its git dir holds the files).
        ac_ids: The requirement ids of the run; each one names at most one file.

    Returns:
        ``(reading, work tree root)``; the root is ``None`` when git cannot say where the files are.
    """
    places = _locations(test_root)
    if places is None:
        return ExtrasRead(), None
    folder = places[0] / "leafcutter" / "to-run-later"
    reading = ExtrasRead()
    for ac_id in dict.fromkeys(ac_ids):
        if not _PLAIN_ID.match(ac_id):
            reading.notes.append((ac_id, f"to-run-later: requirement id {ac_id!r} is not a plain id, so its file was not looked for"))
            continue
        path = folder / f"{ac_id}.json"
        if path.exists():
            items, notes = _read_file(path)
            reading.items += items
            reading.notes += notes
    return reading, places[1]


def attach_extras(tests: list[Any], test_root: Path, ac_ids: Sequence[str], key_of: Callable[[str], str],
                  undone_key: str) -> ExtrasRead:
    """Attach each extra to the in-scope test it names (``test.extras``); return what was read.

    The returned reading holds every extra read and the notes (including those of an extra whose
    test is not in scope), so the caller can tell that the run had to-run-later files at all.

    An extra whose key (``key_of``) is one of the test's own versions, or the fix undone, is not
    attached: the named version stays blocking. A test is matched by its function name and its
    file; only tests with a resolved node are in scope for an extra.
    """
    reading, root = read_extras(test_root, ac_ids)
    if not reading.items or root is None:
        return reading
    for extra in reading.items:
        path, _sep, rest = extra.test.partition("::")
        function = rest.rsplit("::", 1)[-1]
        target = (root / path).resolve()
        matched = [t for t in tests if t.node is not None and t.function == function and Path(t.node.file).resolve() == target]
        if not matched:
            reading.notes.append((extra.test, f'to-run-later extra "{extra.wrong_version}" is for {extra.test}, which is not a resolved in-scope test'))
            continue
        key = key_of(extra.wrong_version)
        for test in matched:
            # An extra spelled like a named version or "the fix undone" is intentionally NOT attached:
            # it stays that blocking version (see the module docstring).
            if key != undone_key and key not in test.versions:
                test.extras.setdefault(key, extra.wrong_version)
    return reading


def extra_rows(notes: list[tuple[str, str]]) -> list[dict]:
    """The one non-blocking row of each note (``not_in_scope`` never stops the work)."""
    return [{"test": subject, "wrong_version": "", "result": NOTE_RESULT, "blocking": False, "detail": detail}
            for subject, detail in notes]


def demote(rows: list[dict], labels: set[str]) -> list[dict]:
    """Return *rows* with ``blocking`` false on every row of a test in *labels* (an extra's rows)."""
    return [{**r, "blocking": False} if r["test"] in labels else r for r in rows]
