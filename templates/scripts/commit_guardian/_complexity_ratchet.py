"""
MODULE: commit_guardian._complexity_ratchet
GOAL: Judge each staged Python function against the greater of the complexity
    limit and that function's own highest previous score (its ceiling), and
    never report a file that cannot be parsed or read as within the limit.
BUSINESS CONTEXT: GE-131a-1. An already-over-limit function may be worked on
    but not made worse; a new function, or one crossing the limit, is held to
    the limit. The staged blob is judged (never the working tree), the previous
    score is the highest across HEAD and every MERGE_HEAD parent, and functions
    are keyed by qualified name plus ordinal so same-named nested functions
    never lend each other a ceiling.
ARCHITECTURE: Sibling of check_complexity.py inside
    templates/scripts/commit_guardian/ (deployed whole by build_commit_guardian,
    so no manifest entry). Git reading reuses _file_size_ratchet. The scoring
    visitor is injected by the caller to avoid a circular import.
"""

from __future__ import annotations

import ast
import subprocess
from dataclasses import dataclass

import _file_size_ratchet as fsr

_TIMEOUT_SECONDS = 15

# Key of one function: (qualified name, ordinal among same-named definitions).
FunctionKey = tuple[str, int]


@dataclass(frozen=True)
class Refusal:
    """One function refused: its score, its ceiling and why (new|grew|crossed)."""

    path: str
    name: str
    score: int
    ceiling: int
    reason: str


@dataclass(frozen=True)
class CouldNotCheck:
    """A file that could not be judged, with the human-readable cause."""

    path: str
    why: str


_WHY = {
    "staged_unreadable": "cannot read the staged version",
    "not_utf8": "staged version is not valid UTF-8",
    "unparseable": "cannot be parsed",
    "previous_unreadable": "previous version unreadable",
}


class UnjudgeableError(Exception):
    """Raised when a source blob cannot be read, decoded or parsed.

    Attributes:
        why: Human-readable cause, "<kind text> (<detail>)".
    """

    def __init__(self, kind: str, detail: object) -> None:
        self.why = f"{_WHY[kind]} ({detail})"
        super().__init__(self.why)


def score_functions(source: str, visitor_cls: type) -> dict[FunctionKey, int]:
    """Score every function in *source*, keyed by qualified name and ordinal.

    Args:
        source: Python source text.
        visitor_cls: The complexity visitor class (counting rule unchanged).

    Returns:
        Mapping of (qualified_name, ordinal) to complexity score.

    Raises:
        SyntaxError: *source* cannot be parsed.
    """
    scores: dict[FunctionKey, int] = {}
    seen: dict[str, int] = {}

    def walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = f"{prefix}{child.name}"
                ordinal = seen.get(qual, 0)
                seen[qual] = ordinal + 1
                visitor = visitor_cls()
                for stmt in child.body:
                    visitor.visit(stmt)
                scores[(qual, ordinal)] = visitor.complexity
                walk(child, f"{qual}.")
            elif isinstance(child, ast.ClassDef):
                walk(child, f"{prefix}{child.name}.")
            else:
                walk(child, prefix)

    walk(ast.parse(source), "")
    return scores


def read_staged_blob(path: str) -> str:
    """Return the staged (index) text of *path*.

    Raises:
        UnjudgeableError: git failed, or the blob is not valid UTF-8.
    """
    try:
        result = subprocess.run(
            ["git", "show", f":{path}"], capture_output=True, timeout=_TIMEOUT_SECONDS, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise UnjudgeableError("staged_unreadable", exc) from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise UnjudgeableError("staged_unreadable", detail)
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UnjudgeableError("not_utf8", exc) from exc


def previous_ceilings(path: str, parents: list[str], visitor_cls: type) -> dict[FunctionKey, int]:
    """Highest previous score of each function across every parent revision.

    Raises:
        UnjudgeableError: a parent's blob cannot be read or decoded.
    """
    ceilings: dict[FunctionKey, int] = {}
    for revision in parents:
        try:
            content = fsr.get_previous_content(path, revision)
        except fsr.PreviousLengthSourceError as exc:
            raise UnjudgeableError("previous_unreadable", exc.reason) from exc
        if content is None:
            continue
        try:
            scores = score_functions(content, visitor_cls)
        except SyntaxError:
            continue  # An unparseable earlier version grants no ceiling.
        for key, score in scores.items():
            ceilings[key] = max(ceilings.get(key, 0), score)
    return ceilings


def _reason(previous: int | None, limit: int) -> str:
    """Why a function is held to the limit: new, crossed it, or grew past its ceiling."""
    if previous is None:
        return "new"
    return "crossed" if previous <= limit else "grew"


def judge_file(path: str, limit: int, parents: list[str], visitor_cls: type) -> list[Refusal]:
    """Judge one staged file; return the functions refused.

    Raises:
        UnjudgeableError: the staged blob or a parent blob cannot be judged.
    """
    try:
        staged = score_functions(read_staged_blob(path), visitor_cls)
    except SyntaxError as exc:
        raise UnjudgeableError("unparseable", exc) from exc
    previous = previous_ceilings(path, parents, visitor_cls)

    refusals = []
    for key, score in staged.items():
        prior = previous.get(key)
        ceiling = max(limit, prior or 0)
        if score > ceiling:
            refusals.append(Refusal(path, key[0], score, ceiling, _reason(prior, limit)))
    return refusals
