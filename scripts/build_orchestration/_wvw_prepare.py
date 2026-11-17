"""
MODULE: scripts/build_orchestration/_wvw_prepare.py
GOAL: Apply one wrong version's exact-match replacements to copies of the code as written,
    all or nothing, and compute the diff from the bytes.
BUSINESS CONTEXT: TQ-500g-1-ix. A replacement counts only where its old text occurs exactly
    once in the current text; a path outside the repository, inside the version-control
    folder, a test file or a file not in scope for the name is refused before any file is
    read. One refused replacement refuses the whole name: a partial copy would run a
    different wrong version from the one named.
ARCHITECTURE: Path rules come from ``_wvr_scope`` (``path_refusal``, ``is_test_path``).
    Files are read as bytes and decoded as strict UTF-8 (a BOM stays part of the text). A
    uniformly CRLF file is matched and replaced on its LF text and turned back into CRLF;
    every other file is matched raw. Reads only the files the replacements name.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from _wvr_scope import is_test_path, path_refusal


@dataclass
class Altered:
    """One altered file: its repo-relative path, the altered bytes and both texts in LF form."""

    rel: str
    data: bytes
    before: str
    after: str


@dataclass
class _FileState:
    """A file being altered: its texts (LF form when CRLF) and whether it is CRLF."""

    rel: str
    crlf: bool
    before: str
    text: str


def _is_crlf(text: str) -> bool:
    """True when *text* has a CRLF, every LF is part of one and there is no lone CR."""
    pairs = text.count("\r\n")
    return pairs > 0 and text.count("\n") == pairs and text.count("\r") == pairs


def _count(text: str, old: str) -> int:
    """Count the (overlapping) occurrences of *old* in *text*."""
    found, at = 0, text.find(old)
    while at != -1:
        found, at = found + 1, text.find(old, at + 1)
    return found


def _load(root: Path, rel: str) -> tuple[_FileState | None, str]:
    """Read *rel* under *root*; return ``(state, "")`` or ``(None, reason)``."""
    path = root / rel
    try:
        raw = path.read_bytes() if path.is_file() else None
    except OSError:
        raw = None
    if raw is None:
        return None, f"{rel} not found"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, f"{rel} is not UTF-8 text"
    crlf = _is_crlf(text)
    work = text.replace("\r\n", "\n") if crlf else text
    return _FileState(rel, crlf, work, work), ""


def _check_paths(name: str, repls: list[dict], root: Path, in_scope: list[str],
                 test_root_rel: str | None) -> tuple[list[str], str]:
    """Check every replacement path in reply order; return ``(rels, "")`` or ``([], first reason)``."""
    rels: list[str] = []
    for repl in repls:
        raw = repl["path"]
        refusal = path_refusal(root, raw)
        if refusal:
            return [], f"{raw} is {refusal}"
        rel = PureWindowsPath(raw).as_posix()
        if is_test_path(rel, test_root_rel):
            return [], f"{rel} is a test file"
        if rel not in in_scope:
            return [], f'{rel} is not in scope for "{name}"'
        rels.append(rel)
    return rels, ""


def _replace_once(state: _FileState, old: str, new: str) -> str:
    """Replace the one occurrence of *old* in *state*; return the refusal reason or ``""``."""
    if state.crlf:
        old, new = old.replace("\r\n", "\n"), new.replace("\r\n", "\n")
    if not old:
        return f"old text is empty in {state.rel}"
    found = _count(state.text, old)
    if found != 1:
        return f"old text found {found} times in {state.rel}" if found else f"old text not found in {state.rel}"
    state.text = state.text.replace(old, new, 1)
    return ""


def _finish(state: _FileState) -> Altered:
    """Turn a settled :class:`_FileState` into the altered bytes."""
    text = state.text.replace("\n", "\r\n") if state.crlf else state.text
    return Altered(state.rel, text.encode("utf-8"), state.before, state.text)


def alter(name: str, repls: list[dict], root: Path, in_scope: list[str],
          test_root_rel: str | None) -> tuple[list[Altered], str]:
    """Apply *repls* of one name, in reply order, to copies of the code as written.

    Args:
        name: The owed name (quoted in the out-of-scope reason).
        repls: ``[{path, old, new}]`` (already shape-checked).
        root: The worktree root.
        in_scope: The files in scope for *name*.
        test_root_rel: The test root relative to *root*, or ``None``.

    Returns:
        ``(altered files in reply order, "")``, or ``([], reason of the first refused replacement)``.
    """
    rels, reason = _check_paths(name, repls, root, in_scope, test_root_rel)
    if reason:
        return [], reason
    states: dict[str, _FileState] = {}
    for repl, rel in zip(repls, rels, strict=True):
        if rel not in states:
            state, reason = _load(root, rel)
            if state is None:
                return [], reason
            states[rel] = state
        reason = _replace_once(states[rel], repl["old"], repl["new"])
        if reason:
            return [], reason
    return [_finish(s) for s in states.values()], ""


def unified_diff(files: list[Altered]) -> str:
    """Return the unified diff (3 lines of context) of the as-written texts against the altered ones."""
    parts = (difflib.unified_diff(f.before.splitlines(True), f.after.splitlines(True), f"a/{f.rel}", f"b/{f.rel}", n=3)
             for f in files)
    return "".join("".join(p) for p in parts)
