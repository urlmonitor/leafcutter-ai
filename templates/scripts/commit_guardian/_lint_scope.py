"""
MODULE: _lint_scope
GOAL: Be the ONE reader of `leafcutter-lint.json`, the project-owned declaration
    of what the commit-time lint gate (and CI, and every other runner that
    claims to mirror CI) lints and by which rule sets.
BUSINESS CONTEXT: BP-1300e-1-i. Before this module there were three hand-kept
    copies of "what CI lints" (ci.yml, run_ci_local.py, a planned sign-off
    runner). A commit-time hook with its own copy would be a fourth. Parity
    comes from one definition every runner reads, so widening the scope or
    dropping a rule changes every verdict at once, with no second list to edit.
ARCHITECTURE: Stdlib only (hooks run in adopter environments where jsonschema
    is not guaranteed), no {{config.*}} tokens, no leafcutter imports beyond
    the sibling `_lint_git`. `load()` is the only I/O: source="index" reads
    `git show :leafcutter-lint.json` (so a staged scope change is judged
    exactly as it will be committed), source="worktree" reads the file on disk
    (CI and run_ci_local.py; identical to the committed file in a CI checkout).
    `validate()` is pure and has no try/except. A declaration that cannot be
    read is NEVER defaulted: it raises DeclarationError, because falling back
    to the default scope would replace the project's scope with a different
    one and present the result as CI's verdict.

DECISION HISTORY
- 2026-10-12 [python-coder/BP-1300e-1-i, -v]: Created. The default scope
    (whole project, minus the ruff configuration's own excludes) and the
    default linter-version source are declared ONCE here, as constants.
    `linter_version_source` (BP-1300e-1-v) is a PATH to the pip requirements
    file CI installs the linter from, never a version string.
"""

from __future__ import annotations

import json
import logging
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

import _lint_git as lg

logger = logging.getLogger(__name__)

DECLARATION_FILE = "leafcutter-lint.json"
DEFAULT_VERSION_SOURCE = "requirements-dev.txt"
SUPPORTED_VERSION = 1

_TOP_KEYS = frozenset({"version", "steps", "linter_version_source"})
_STEP_KEYS = frozenset({"name", "paths", "select"})
_GLOB_CHARS = re.compile(r"[*?\[\]{}\\]")


@dataclass(frozen=True)
class Step:
    """One lint pass: a name, the repo-relative trees it covers, an optional --select."""

    name: str
    paths: tuple[str, ...]
    select: tuple[str, ...] | None = None

    def covers(self, rel: str) -> bool:
        """True when the repo-relative *rel* lies under one of this step's paths."""
        return any(p == "." or rel == p or rel.startswith(p + "/") for p in self.paths)


@dataclass(frozen=True)
class Declaration:
    """A validated lint declaration (or the default when the file is absent)."""

    steps: tuple[Step, ...]
    linter_version_source: str
    version_source_declared: bool
    is_default: bool


class DeclarationError(Exception):
    """leafcutter-lint.json is present but cannot be read; never defaulted."""

    def __init__(self, detail: str, key: str | None = None) -> None:
        super().__init__(f"{DECLARATION_FILE}: {detail}")
        self.detail = detail
        self.key = key


DEFAULT_DECLARATION = Declaration(
    steps=(Step(name="repository-rules", paths=(".",)),),
    linter_version_source=DEFAULT_VERSION_SOURCE,
    version_source_declared=False,
    is_default=True,
)


def _reject(detail: str, key: str | None = None) -> NoReturn:
    """Raise DeclarationError naming the offending *key* (the single raise site)."""
    raise DeclarationError(detail, key)


def clean_path(value: object, where: str, *, allow_dot: bool = True) -> str:
    """Validate one repo-relative POSIX path and return it normalised.

    Rules: a non-empty string; not absolute; no ``..`` component; no glob
    characters or backslashes; ``.`` means the whole project (steps only).

    Raises:
        DeclarationError: Naming *where* (the offending key) when a rule fails.
    """
    if not isinstance(value, str) or not value.strip():
        _reject(f"{where} must be a non-empty string", where)
    text = value.strip()
    if text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        _reject(f"{where} must be repo-relative, got {text!r}", where)
    if _GLOB_CHARS.search(text):
        _reject(f"{where} must not contain globs or backslashes: {text!r}", where)
    if ".." in text.split("/"):
        _reject(f"{where} must not contain '..': {text!r}", where)
    normal = posixpath.normpath(text)
    if normal == "." and not allow_dot:
        _reject(f"{where} must name a file, got {text!r}", where)
    return normal


def _string_list(value: object, where: str) -> list[str]:
    if not isinstance(value, list) or not value:
        _reject(f"{where} must be a non-empty list", where)
    if not all(isinstance(item, str) and item.strip() for item in value):
        _reject(f"{where} must hold non-empty strings", where)
    return [item.strip() for item in value]


def _step(raw: object, index: int) -> Step:
    where = f"steps[{index}]"
    if not isinstance(raw, dict):
        _reject(f"{where} must be an object", where)
    unknown = sorted(set(raw) - _STEP_KEYS)
    if unknown:
        _reject(f"unknown key {unknown[0]!r} in {where}", unknown[0])
    for required in ("name", "paths"):
        if required not in raw:
            _reject(f"{where} is missing the required key {required!r}", required)
    name = raw["name"]
    if not isinstance(name, str) or not name.strip():
        _reject(f"{where}.name must be a non-empty string", "name")
    paths = tuple(clean_path(p, f"{where}.paths") for p in _string_list(raw["paths"], f"{where}.paths"))
    select = tuple(_string_list(raw["select"], f"{where}.select")) if "select" in raw else None
    return Step(name=name.strip(), paths=paths, select=select)


def validate(data: object) -> Declaration:
    """Validate a parsed declaration (pure; raises DeclarationError, never defaults)."""
    if not isinstance(data, dict):
        _reject("the top level must be a JSON object")
    unknown = sorted(set(data) - _TOP_KEYS)
    if unknown:
        _reject(f"unknown key {unknown[0]!r}", unknown[0])
    if type(data.get("version")) is not int or data["version"] != SUPPORTED_VERSION:
        _reject(f"'version' must be {SUPPORTED_VERSION}", "version")
    raw_steps = data.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        _reject("'steps' must be a non-empty list", "steps")
    steps = tuple(_step(raw, i) for i, raw in enumerate(raw_steps))
    declared = "linter_version_source" in data
    source = DEFAULT_VERSION_SOURCE
    if declared:
        source = clean_path(data["linter_version_source"], "linter_version_source", allow_dot=False)
    return Declaration(steps, source, declared, is_default=False)


def _read_text(root: Path, source: str) -> str | None:
    """Return the declaration text from the index or the work tree; None if absent."""
    if source == "index":
        blob = lg.index_blob(root, DECLARATION_FILE)
        return None if blob is None else blob.decode("utf-8")
    path = root / DECLARATION_FILE
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def load(subject_root: Path, source: str = "worktree") -> Declaration:
    """Read the project's lint declaration, or the default when none exists.

    Args:
        subject_root: The git toplevel of the project being committed.
        source: ``"index"`` (commit hook) or ``"worktree"`` (CI, local runners).

    Returns:
        The validated Declaration; DEFAULT_DECLARATION when the file is absent.

    Raises:
        DeclarationError: The file exists but is unreadable or invalid.
        GitError: git could not answer (an internal defect, not a bad file).
    """
    try:
        text = _read_text(subject_root, source)
        data = None if text is None else json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("cannot read %s from the %s: %s", DECLARATION_FILE, source, exc)
        detail = f"could not be read from the {source}: {exc}"
        raise DeclarationError(detail) from exc
    if text is None:
        return DEFAULT_DECLARATION
    return validate(data)
