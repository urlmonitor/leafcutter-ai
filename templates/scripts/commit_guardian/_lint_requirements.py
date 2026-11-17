"""
MODULE: _lint_requirements
GOAL: Find the exact ruff version a project's CI installs, by reading the pip
    requirements file CI installs from (BP-1300e-1-v), so the lint gate can
    refuse a local linter that is not that version.
BUSINESS CONTEXT: A linter whose version differs from CI's can reach a
    different verdict on the same bytes (new rules, changed defaults). The
    required version is therefore read from the file CI runs `pip install -r`
    on -- never from a second copy of the version in the gate or in
    leafcutter-lint.json, which would fail the "no second copy" rule.
ARCHITECTURE: Stdlib only (no `packaging`; hooks run in adopter environments
    where it is not guaranteed). `scan_requirements()` and `combine()` are
    pure and carry no try/except. `resolve()` is the I/O edge: it reads the
    version source and any `-r` include through a reader callback, from the
    INDEX in staged mode (so a commit that bumps the pin is judged against the
    version it will commit) or the work tree otherwise. An exact pin is a
    single `==<version>` specifier with no wildcard; a range, a bare name, or
    no ruff line means "no exact version declared" (no check, stated), while
    two different exact pins, an environment marker, `===`, or an unreadable
    include is unreadable (a declared source that silently stopped being read
    would turn the check off without anyone deciding to).

DECISION HISTORY
- 2026-10-12 [python-coder/BP-1300e-1-v]: Created. pyproject dependency tables
    and lock files are deliberately NOT version sources (BP-1300e-1-v caveat).
"""

from __future__ import annotations

import logging
import posixpath
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import _lint_git as lg

logger = logging.getLogger(__name__)

EXACT = "exact"
NOT_DECLARED = "not_declared"
UNREADABLE = "unreadable"

_COMMENT = re.compile(r"(^|\s)#.*$")
_REQUIREMENT = re.compile(r"^([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)\s*(?:\[[^\]]*\])?\s*(.*)$")
_EXACT_SPEC = re.compile(r"^==\s*([0-9A-Za-z.!+_-]+)$")
_MAX_INCLUDE_DEPTH = 8


@dataclass(frozen=True)
class RuffLine:
    """What one requirements line says about ruff: exact, loose or unreadable."""

    kind: str
    version: str | None
    line_no: int
    raw: str


@dataclass(frozen=True)
class Requirement:
    """The project's declared linter version, or why none applies."""

    kind: str
    version: str | None = None
    source: str | None = None
    detail: str = ""


def _logical_lines(text: str) -> list[tuple[int, str]]:
    """Join backslash continuations and strip comments; keep first physical line numbers."""
    joined: list[tuple[int, str]] = []
    pending, start = "", 0
    for number, physical in enumerate(text.splitlines(), start=1):
        if not pending:
            start = number
        if physical.rstrip().endswith("\\"):
            pending += physical.rstrip()[:-1] + " "
            continue
        joined.append((start, _COMMENT.sub("", pending + physical).strip()))
        pending = ""
    if pending:
        joined.append((start, _COMMENT.sub("", pending).strip()))
    return [(n, line) for n, line in joined if line]


def _include_target(line: str) -> str | None:
    """Return the path named by a ``-r``/``--requirement`` line, else None."""
    for flag in ("--requirement", "-r"):
        if line.startswith(flag):
            return line[len(flag):].lstrip("= \t").strip() or None
    return None


def _classify(name: str, rest: str, number: int, raw: str) -> RuffLine | None:
    """Classify one requirement line, or None when it does not name ruff."""
    if re.sub(r"[-_.]+", "-", name).lower() != "ruff":
        return None
    spec = re.split(r"\s--", " " + rest)[0].strip()
    if ";" in spec or "===" in spec:
        return RuffLine(UNREADABLE, None, number, raw)
    exact = _EXACT_SPEC.match(spec) if "," not in spec else None
    if exact and "*" not in exact.group(1):
        return RuffLine(EXACT, exact.group(1), number, raw)
    return RuffLine("loose", None, number, raw)


def scan_requirements(text: str) -> tuple[list[RuffLine], list[str]]:
    """Scan one requirements file (pure): its ruff lines and its ``-r`` includes."""
    ruff_lines: list[RuffLine] = []
    includes: list[str] = []
    for number, line in _logical_lines(text):
        target = _include_target(line)
        if target is not None:
            includes.append(target)
            continue
        match = None if line.startswith("-") else _REQUIREMENT.match(line)
        found = _classify(match.group(1), match.group(2), number, line) if match else None
        if found is not None:
            ruff_lines.append(found)
    return ruff_lines, includes


def combine(lines: list[RuffLine]) -> Requirement:
    """Reduce every ruff line of a file and its includes to one Requirement (pure)."""
    bad = [ln for ln in lines if ln.kind == UNREADABLE]
    if bad:
        detail = f"line {bad[0].line_no} is not a plain requirement: {bad[0].raw!r}"
        return Requirement(UNREADABLE, detail=detail)
    pins = sorted({ln.version for ln in lines if ln.kind == EXACT if ln.version})
    if len(pins) > 1:
        return Requirement(UNREADABLE, detail=f"two different exact ruff pins: {', '.join(pins)}")
    if pins:
        return Requirement(EXACT, version=pins[0])
    return Requirement(NOT_DECLARED, detail="no exact ruff version")


Reader = Callable[[str], str | None]


def index_reader(root: Path) -> Reader:
    """Read requirement files from the index (staged mode)."""

    def read(rel: str) -> str | None:
        blob = lg.index_blob(root, rel)
        return None if blob is None else blob.decode("utf-8")

    return read


def worktree_reader(root: Path) -> Reader:
    """Read requirement files from the work tree (full and files modes)."""

    def read(rel: str) -> str | None:
        path = root / rel
        return path.read_text(encoding="utf-8") if path.is_file() else None

    return read


def _include_path(including: str, target: str) -> str | None:
    """Resolve an include relative to its includer, confined to the project root."""
    if target.startswith("/") or re.match(r"^[A-Za-z]:", target):
        return None
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(including), target))
    return None if joined == ".." or joined.startswith("../") else joined


def _gather(read: Reader, rel: str, seen: set[str], depth: int) -> list[RuffLine] | str:
    """Collect ruff lines from *rel* and its includes; a str is the failure detail."""
    if depth > _MAX_INCLUDE_DEPTH:
        return f"{rel}: requirement includes are nested too deeply"
    try:
        text = read(rel)
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("cannot read requirements file %s: %s", rel, exc)
        return f"{rel} could not be read: {exc}"
    if text is None:
        return f"{rel} does not exist"
    lines, includes = scan_requirements(text)
    seen.add(rel)
    for target in includes:
        inner = _include_path(rel, target)
        if inner is None:
            return f"{rel}: include {target!r} escapes the project"
        if inner in seen:
            continue
        gathered = _gather(read, inner, seen, depth + 1)
        if isinstance(gathered, str):
            return gathered
        lines += gathered
    return lines


def resolve(read: Reader, source: str, *, declared: bool) -> Requirement:
    """Resolve the project's required linter version from its version source.

    Args:
        read: Reader callback (index or work tree).
        source: Repo-relative path of the requirements file.
        declared: True when leafcutter-lint.json named *source* explicitly; a
            declared source that is missing is unreadable, an undeclared
            default that is missing simply means no version is declared.

    Returns:
        A Requirement: exact (with version), not_declared, or unreadable. The
        ``source`` field names the file consulted, or None when none existed.
    """
    gathered = _gather(read, source, set(), 0)
    if isinstance(gathered, str):
        if gathered == f"{source} does not exist" and not declared:
            return Requirement(NOT_DECLARED, source=None, detail=f"{source} does not exist")
        return Requirement(UNREADABLE, source=source, detail=gathered)
    combined = combine(gathered)
    return Requirement(combined.kind, combined.version, source, combined.detail)
