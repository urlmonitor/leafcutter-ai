"""
MODULE: scripts/build_orchestration/_cs_edits.py
GOAL: The edit comparison of the sweep check (TQ-500g-3-i): which existing tests and fixtures the
    work changed, and which of those edits a recorded sweep entry still names.
BUSINESS CONTEXT: Only the test writer's list excuses an edit to an existing test, and only while
    the entry's fingerprint equals the test's current source. The decision comes from git (the
    code at the base ref against the working tree) and the list -- never from a writer's claim
    that its list is complete. Status ``unaffected`` and a stale fingerprint excuse nothing.
ARCHITECTURE: Pure helpers plus two reads (the base blob through ``git show`` and the working tree,
    both read as bytes: ``.py`` decoded as UTF-8, any other test file compared as raw bytes); the symbol split is
    ``_cs_symbols``. ``consumer_sweep.py``
    calls :func:`compare_file` per changed existing test file and :func:`unlisted_edits` once.
    Each :class:`Edit` carries the parsed base and current nodes keyed by (file, test) for
    TQ-500g-3-iii (``_cs_asserts.py``). Never stashes, checks out or commits.
"""

from __future__ import annotations

import ast
import hashlib
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from _cs_symbols import Symbol, normalise, symbols

_LOG = logging.getLogger("consumer_sweep")
ABSENT = "absent"
LISTED_STATUSES = frozenset({"strengthened", "removed"})
_PARAM_SUFFIX = re.compile(r"\[.*$", re.DOTALL)


@dataclass
class Edit:
    """One changed existing test or fixture; ``base`` / ``now`` are the parsed nodes (None if absent)."""

    file: str
    test: str
    kind: str  # "changed" | "removed" | "added" (a new fixture, helper or constant)
    fingerprint: str
    base: ast.AST | None = None
    now: ast.AST | None = None


@dataclass
class FileResult:
    """The edits of one file, or why it could not be compared."""

    edits: list[Edit]
    problem: str | None = None


def is_raw(rel: str) -> bool:
    """True for a test file compared as raw bytes (anything that is not a ``.py`` file)."""
    return not rel.endswith(".py")


def decode_source(rel: str, data: bytes) -> str:
    """The text a file's bytes are compared as: UTF-8 for ``.py`` (raises), lossless latin-1 for the rest."""
    return data.decode("latin-1") if is_raw(rel) else data.decode("utf-8-sig")


def fingerprint_of(source: str | None, raw: bool = False) -> str:
    """The sha256 of *source* (LF-normalised; the exact bytes when *raw*), or ``absent`` when there is none."""
    if source is None:
        return ABSENT
    if raw:
        return hashlib.sha256(source.encode("latin-1")).hexdigest()
    return hashlib.sha256(normalise(source).encode("utf-8")).hexdigest()


def bare_name(test: str) -> str:
    """The symbol a recorded ``test`` names: the optional ``[param-id]`` suffix is dropped."""
    return _PARAM_SUFFIX.sub("", test)


def symbol_table(rel: str, source: str | None) -> dict[str, Symbol]:
    """The comparable symbols of one file; a non-Python test file is one symbol named by its file name."""
    if source is None:
        return {}
    if is_raw(rel):
        return {rel.rsplit("/", 1)[-1]: Symbol(source)}
    return symbols(source)


def _is_test_name(name: str) -> bool:
    """True for a new test (function, method or ``Test*`` class), which is not an edit to an existing one."""
    last = name.rsplit("::", 1)[-1]
    return last.startswith("test") or ("::" not in name and name.startswith("Test"))


def compare_file(rel: str, base_source: str | None, now_source: str | None) -> FileResult:
    """Compare one existing test file at the base against the working tree.

    Args:
        rel: Repo-relative POSIX path.
        base_source: The file at the base ref (``None`` when unreadable there: the file is inconclusive).
        now_source: The file in the working tree (``None`` when deleted).

    Returns:
        The edits (changed or removed symbols); ``problem`` names a file that does not parse.
    """
    if base_source is None:
        return FileResult([], f"{rel} could not be read at the base ref, so its edits cannot be told")
    try:
        base, now = symbol_table(rel, base_source), symbol_table(rel, now_source)
    except SyntaxError as exc:
        return FileResult([], f"{rel} does not parse: {exc.msg} (line {exc.lineno})")
    raw = is_raw(rel)
    edits = []
    for name, old in base.items():
        new = now.get(name)
        if new is None:
            edits.append(Edit(rel, name, "removed", ABSENT, old.node, None))
        elif new.source != old.source:
            edits.append(Edit(rel, name, "changed", fingerprint_of(new.source, raw), old.node, new.node))
    edits.extend(
        Edit(rel, name, "added", fingerprint_of(new.source, raw), None, new.node)
        for name, new in now.items()
        if name not in base and not _is_test_name(name)
    )
    return FileResult(edits)


def current_fingerprint(root: Path, rel: str, test: str) -> str:
    """The fingerprint of *test* in the working-tree file *rel*; ``absent`` when it is not there."""
    try:
        source = decode_source(rel, (root / rel).read_bytes())
        table = symbol_table(rel, source)
        found = table.get(test) or table.get(bare_name(test))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        _LOG.warning("fingerprint of %s::%s: %s", rel, test, exc)
        return ABSENT
    return fingerprint_of(found.source if found else None, is_raw(rel))


def _read_file_at_ref(root: Path, ref: str, rel: str) -> str | None:
    """The file *rel* at *ref* decoded as UTF-8 (BOM dropped); ``None`` when git cannot show it.

    Reads the blob as bytes so the result never depends on the locale or ``PYTHONUTF8``; a non-``.py``
    file is kept byte-for-byte (latin-1), never decoded as text.

    Raises:
        UnicodeDecodeError: When the blob is not UTF-8.
    """
    try:
        proc = subprocess.run(["git", "-C", str(root), "show", f"{ref}:{rel}"], capture_output=True,
                              timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        _LOG.warning("git show %s:%s failed: %s", ref, rel, exc)
        return None
    return decode_source(rel, proc.stdout) if proc.returncode == 0 else None


def read_sources(root: Path, base_ref: str, rel: str) -> tuple[str | None, str | None]:
    """Return ``(base source, working-tree source)`` of *rel*; either is ``None`` when absent or unreadable."""
    base = _read_file_at_ref(root, base_ref, rel)
    try:
        now = decode_source(rel, (root / rel).read_bytes())
    except FileNotFoundError:
        now = None
    return base, now


def unlisted_edits(edits: list[Edit], entries: list[dict]) -> list[Edit]:
    """The edits no recorded entry excuses.

    An entry excuses an edit only when it names the same file and symbol, has status
    ``strengthened`` or ``removed``, and its fingerprint equals the edit's current one.
    """
    listed = set()
    for e in entries:
        if e.get("status") in LISTED_STATUSES:
            test = str(e.get("test", ""))
            listed.update((e.get("file"), name, e.get("fingerprint")) for name in (test, bare_name(test)))
    return [e for e in edits if (e.file, e.test, e.fingerprint) not in listed]
