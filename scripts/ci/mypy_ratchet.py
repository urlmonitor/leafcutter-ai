#!/usr/bin/env python3
"""
MODULE: mypy_ratchet
GOAL: Fail a pull request for the mypy errors and the ``# type: ignore`` comments
    it ADDS, and never for the ones its changed files already had (BP-1300f-1).
    Each changed Python file in scope is type-checked at the pull request's head
    and at its merge base, both with the whole repository around it, and the two
    error lists are compared without line numbers.
BUSINESS CONTEXT: The CI typecheck job ran mypy over whole changed files, so a
    pull request touching any file inherited every old error in it (789 errors in
    158 files on 2026-11-16). The job could therefore only ever be informational
    (continue-on-error), and its findings were read by nobody. Comparing against
    the merge base charges a pull request for exactly what it adds, which makes a
    failing job fair while other work clears the backlog (user decision,
    BrainCandy, 2026-11-16).
ARCHITECTURE: One module, stdlib only, invoked by job ``typecheck`` of
    .github/workflows/ci.yml. Pure functions (``parse_name_status``,
    ``parse_mypy_output``, ``compare_errors``, ``type_ignore_lines``,
    ``compare_ignores`` and the renderers) hold the rule and carry no try/except.
    The I/O boundary (``_run``, file reads, the temporary base worktree) turns
    every failure into ``RatchetError``, which ``main`` reports as COULD NOT CHECK
    with exit 2.

    The rule: an error's key is (head path, error code, message with "line <n>"
    written as "line N"). Per key, new = max(0, head - base), untouched =
    min(head, base), removed = max(0, base - head). A renamed file's base errors
    are read under its old path and re-keyed to the new one; a new file has no
    base errors. A file's type-ignore count is the number of COMMENT tokens that
    start with ``# type: ignore`` (the only form mypy honours), and it may not rise.

Usage::

    python scripts/ci/mypy_ratchet.py --base origin/main [--repo .] \\
        [--cache-dir DIR] -- 'scripts/*.py' 'scripts/**/*.py' ...

Exit codes:
    0 -- no new error and no new type-ignore, or nothing in scope (stated).
    1 -- at least one new error or one new type-ignore comment.
    2 -- could not check: git or mypy failed, a file could not be read, bad usage.
"""

from __future__ import annotations

import argparse
import io
import logging
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
from collections import Counter
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("mypy_ratchet")

MYPY_FLAGS = (
    "--ignore-missing-imports",
    "--explicit-package-bases",
    "--no-error-summary",
    "--show-error-codes",
    "--no-pretty",
    "--no-color-output",
    "--hide-error-context",
)
ERROR_REMEDY = (
    "  remedy: fix the type at this line; do not add '# type: ignore' "
    "(an added ignore fails this check too)"
)
IGNORE_REMEDY = "  remedy: remove the ignore and fix the underlying type error"
_ERROR_LINE = re.compile(
    r"^(?P<path>[^:]+):(?P<line>\d+)(?::\d+){0,3}: error: "
    r"(?P<message>.*?)(?:  \[(?P<code>[a-z0-9-]+)\])?$"
)
_LINE_IN_MESSAGE = re.compile(r"\bline \d+\b")
_TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore(?!\w)")
_GIT_TIMEOUT = 600
_MYPY_TIMEOUT = 3600

ErrorKey = tuple[str, str, str]
IgnoreLines = list[tuple[int, str]]


class RatchetError(Exception):
    """The check could not reach a verdict: git, mypy or a file read failed."""

    @classmethod
    def cannot_run(cls, argv: list[str], exc: Exception) -> RatchetError:
        return cls(f"could not run {' '.join(argv[:4])}: {exc}")

    @classmethod
    def git_failed(cls, args: tuple[str, ...], code: int, detail: str) -> RatchetError:
        return cls(f"git {' '.join(args[:3])} failed (exit {code}): {detail}")

    @classmethod
    def no_merge_base(cls, base: str, cause: Exception) -> RatchetError:
        return cls(f"cannot resolve the merge base of {base!r} and HEAD -- {cause}")

    @classmethod
    def mypy_incomplete(cls, code: int, root: Path, output: str) -> RatchetError:
        return cls(
            f"mypy exited with status {code} in {root}, so it produced no complete "
            f"error list. mypy said:\n{output}"
        )

    @classmethod
    def unreadable(cls, path: Path, exc: Exception) -> RatchetError:
        return cls(f"could not read or tokenize {path}: {exc}")

    @classmethod
    def no_scratch(cls, exc: Exception) -> RatchetError:
        return cls(f"could not create a temporary directory: {exc}")


@dataclass(frozen=True)
class Change:
    """One changed file: its head path, and its base path (None when it is new)."""

    head_path: str
    base_path: str | None


@dataclass(frozen=True)
class MypyError:
    """One mypy error line; the line number is for display, never for matching."""

    path: str
    line: int
    code: str
    message: str

    def key(self) -> ErrorKey:
        return (self.path, self.code, _LINE_IN_MESSAGE.sub("line N", self.message))


@dataclass(frozen=True)
class NewError:
    """A key that occurs more often at the head than at the base."""

    path: str
    code: str
    message: str
    lines: tuple[int, ...]
    base_count: int

    @property
    def count(self) -> int:
        return len(self.lines) - self.base_count


@dataclass
class ErrorComparison:
    """The verdict over the error lists of every inspected file."""

    new: list[NewError] = field(default_factory=list)
    untouched: int = 0
    removed: int = 0


@dataclass(frozen=True)
class IgnoreIncrease:
    """A file whose count of type-ignore comments rose."""

    path: str
    base_count: int
    head_count: int
    added_lines: tuple[int, ...]


# --------------------------------------------------------------------------
# Pure functions: the rule itself.
# --------------------------------------------------------------------------


def parse_name_status(raw: str) -> list[Change]:
    """Parse ``git diff --name-status -z`` output into the changed ``.py`` files."""
    fields = raw.split("\0")
    changes: list[Change] = []
    index = 0
    while index < len(fields) and fields[index]:
        status = fields[index][0]
        if status in "RC":
            old, new = fields[index + 1], fields[index + 2]
            changes.append(Change(new, old if status == "R" else None))
            index += 3
        else:
            path = fields[index + 1]
            changes.append(Change(path, None if status == "A" else path))
            index += 2
    return [change for change in changes if change.head_path.endswith(".py")]


def parse_mypy_output(text: str, wanted: Iterable[str]) -> list[MypyError]:
    """The error lines of mypy's text output that name one of the *wanted* files."""
    keep = set(wanted)
    errors: list[MypyError] = []
    for raw_line in text.splitlines():
        match = _ERROR_LINE.match(raw_line.rstrip())
        if match is None:
            continue
        path = match.group("path").replace("\\", "/")
        if path in keep:
            code = match.group("code") or ""
            errors.append(MypyError(path, int(match.group("line")), code, match.group("message")))
    return errors


def compare_errors(head: list[MypyError], base: list[MypyError]) -> ErrorComparison:
    """Compare two error lists as multisets of keys, never by line number."""
    base_counts: Counter[ErrorKey] = Counter(error.key() for error in base)
    head_by_key: dict[ErrorKey, list[MypyError]] = {}
    for error in head:
        head_by_key.setdefault(error.key(), []).append(error)
    result = ErrorComparison()
    for key, errors in head_by_key.items():
        prior = base_counts[key]
        result.untouched += min(prior, len(errors))
        if len(errors) > prior:
            first = errors[0]
            lines = tuple(sorted(error.line for error in errors))
            result.new.append(NewError(first.path, first.code, first.message, lines, prior))
    result.removed = sum(
        max(0, count - len(head_by_key.get(key, []))) for key, count in base_counts.items()
    )
    return result


def type_ignore_lines(source: bytes) -> IgnoreLines:
    """Every comment that starts with ``# type: ignore``, as (line, stripped line).

    Uses the tokenizer, so text inside strings, f-strings and docstrings is never
    read. Raises tokenize.TokenError, SyntaxError or UnicodeDecodeError on source
    the tokenizer cannot read; the caller at the I/O boundary handles that.
    """
    found: IgnoreLines = []
    for token in tokenize.tokenize(io.BytesIO(source).readline):
        if token.type == tokenize.COMMENT and _TYPE_IGNORE.match(token.string):
            found.append((token.start[0], token.line.strip()))
    return found


def compare_ignores(path: str, head: IgnoreLines, base: IgnoreLines) -> IgnoreIncrease | None:
    """An IgnoreIncrease when *head* carries more ignore comments than *base*."""
    if len(head) <= len(base):
        return None
    remaining = Counter(text for _line, text in base)
    added: list[int] = []
    for line, text in head:
        if remaining[text] > 0:
            remaining[text] -= 1
        else:
            added.append(line)
    return IgnoreIncrease(path, len(base), len(head), tuple(added))


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def render_new_error(error: NewError) -> list[str]:
    """Output lines for one new error key, each followed by the remedy."""
    what = f"new error [{error.code or '-'}] {error.message}"
    if error.base_count == 0:
        rendered: list[str] = []
        for line in error.lines:
            rendered += [f"{error.path}:{line}: {what}", ERROR_REMEDY]
        return rendered
    where = ",".join(str(line) for line in error.lines)
    note = (
        f"({error.count} new among these {len(error.lines)}; the base already had "
        f"{error.base_count} identical in this file, so which one is new cannot be told)"
    )
    return [f"{error.path}:{where}: {what} {note}", ERROR_REMEDY]


def render_ignore_increase(increase: IgnoreIncrease) -> list[str]:
    """Output lines for one file whose type-ignore count rose."""
    lines = ", ".join(str(line) for line in increase.added_lines) or "unknown"
    label = "line" if len(increase.added_lines) == 1 else "lines"
    return [
        f"{increase.path}: type-ignore comments rose from {increase.base_count} to "
        f"{increase.head_count}; added at {label} {lines}",
        IGNORE_REMEDY,
    ]


def summary_line(files: int, errors: ErrorComparison, new_ignores: int) -> str:
    """The one line that states what was inspected and the verdict's counts."""
    failed = bool(errors.new) or new_ignores > 0
    prefix = "mypy ratchet FAILED" if failed else "mypy ratchet"
    new_count = sum(error.count for error in errors.new)
    return (
        f"{prefix}: {_plural(files, 'file')}, {_plural(new_count, 'new error')} "
        f"({_plural(errors.untouched, 'existing error')} untouched, {errors.removed} removed), "
        f"{_plural(new_ignores, 'new type-ignore')}"
    )


# --------------------------------------------------------------------------
# I/O boundary: git, mypy, files. Every failure becomes RatchetError.
# --------------------------------------------------------------------------


def _run(argv: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    """Run one external command; one that cannot start or finish is RatchetError."""
    try:
        return subprocess.run(
            argv, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("could not run %s: %s", argv[0], exc)
        raise RatchetError.cannot_run(argv, exc) from exc


def _git(repo: Path, *args: str) -> str:
    done = _run(["git", *args], repo, _GIT_TIMEOUT)
    if done.returncode != 0:
        detail = done.stderr.strip() or done.stdout.strip()
        raise RatchetError.git_failed(args, done.returncode, detail)
    return done.stdout


def resolve_merge_base(repo: Path, base: str) -> str:
    try:
        return _git(repo, "merge-base", base, "HEAD").strip()
    except RatchetError as exc:
        raise RatchetError.no_merge_base(base, exc) from exc


def changed_files(repo: Path, merge_base: str, pathspecs: list[str]) -> list[Change]:
    """The .py files changed between *merge_base* and HEAD, renames detected."""
    raw = _git(
        repo, "diff", "--name-status", "-z", "-M", "--diff-filter=ACMR",
        merge_base, "HEAD", "--", *pathspecs,
    )
    return parse_name_status(raw)


def run_mypy(root: Path, paths: list[str], cache_dir: Path) -> list[MypyError]:
    """mypy over *paths* with *root* as cwd, so the whole tree is the context."""
    argv = [sys.executable, "-m", "mypy", *MYPY_FLAGS, "--cache-dir", str(cache_dir), *paths]
    done = _run(argv, root, _MYPY_TIMEOUT)
    if done.returncode not in (0, 1):
        raise RatchetError.mypy_incomplete(done.returncode, root, (done.stdout + done.stderr).strip())
    return parse_mypy_output(done.stdout, paths)


def read_ignores(path: Path) -> IgnoreLines:
    try:
        return type_ignore_lines(path.read_bytes())
    except (OSError, tokenize.TokenError, SyntaxError, UnicodeDecodeError) as exc:
        logger.warning("could not count type-ignore comments in %s: %s", path, exc)
        raise RatchetError.unreadable(path, exc) from exc


def _make_temp_dir(prefix: str) -> Path:
    try:
        return Path(tempfile.mkdtemp(prefix=prefix))
    except OSError as exc:
        logger.warning("could not create a temporary directory: %s", exc)
        raise RatchetError.no_scratch(exc) from exc


@contextmanager
def _cache_root(cache_dir: Path | None) -> Iterator[Path]:
    """The given cache root, or a temporary one removed afterwards."""
    if cache_dir is not None:
        yield cache_dir
        return
    tmp = _make_temp_dir("mypy-ratchet-cache-")
    try:
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@contextmanager
def base_checkout(repo: Path, rev: str) -> Iterator[Path]:
    """A detached temporary worktree of *rev*, removed whatever happens."""
    tmp = _make_temp_dir("mypy-ratchet-base-")
    root = tmp / "base"
    try:
        _git(repo, "worktree", "add", "--detach", "--quiet", str(root), rev)
        yield root
    finally:
        _discard_checkout(repo, tmp, root)


def _discard_checkout(repo: Path, tmp: Path, root: Path) -> None:
    if root.exists():
        try:
            _git(repo, "worktree", "remove", "--force", str(root))
        except RatchetError as exc:
            logger.warning("could not remove the base worktree %s: %s", root, exc)
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        _git(repo, "worktree", "prune")
    except RatchetError as exc:
        logger.warning("git worktree prune failed: %s", exc)


def _base_side(
    repo: Path, merge_base: str, changes: list[Change], cache_root: Path
) -> tuple[list[MypyError], dict[str, IgnoreLines]]:
    """Base errors (re-keyed to head paths) and base ignore lines per head path."""
    pairs: list[tuple[str, str]] = []
    for change in changes:
        if change.base_path is not None:
            pairs.append((change.base_path, change.head_path))
    if not pairs:
        return [], {}
    head_of = dict(pairs)
    with base_checkout(repo, merge_base) as root:
        raw = run_mypy(root, [old for old, _new in pairs], cache_root / "base")
        ignores = {new: read_ignores(root / old) for old, new in pairs}
    errors = [MypyError(head_of[e.path], e.line, e.code, e.message) for e in raw]
    return errors, ignores


# --------------------------------------------------------------------------
# Orchestration and CLI.
# --------------------------------------------------------------------------


def _describe(change: Change) -> str:
    if change.base_path is None:
        return f"  {change.head_path} (new file)"
    if change.base_path != change.head_path:
        return f"  {change.head_path} (renamed from {change.base_path})"
    return f"  {change.head_path}"


def _report(files: int, errors: ErrorComparison, increases: list[IgnoreIncrease]) -> int:
    lines: list[str] = []
    for error in errors.new:
        lines += render_new_error(error)
    for increase in increases:
        lines += render_ignore_increase(increase)
    new_ignores = sum(item.head_count - item.base_count for item in increases)
    lines.append(summary_line(files, errors, new_ignores))
    print("\n".join(lines))
    return 1 if errors.new or increases else 0


def run_ratchet(repo: Path, base: str, pathspecs: list[str], cache_dir: Path | None) -> int:
    """Compare the head with the merge base of *base* and HEAD; return the exit code."""
    merge_base = resolve_merge_base(repo, base)
    changes = changed_files(repo, merge_base, pathspecs)
    if not changes:
        print(
            f"mypy ratchet: NOTHING INSPECTED -- 0 changed Python files in scope between "
            f"{base} (merge base {merge_base[:12]}) and HEAD for {' '.join(pathspecs)}; "
            "no type check ran. This is not a pass on content."
        )
        return 0
    print(f"Changed Python files in scope ({len(changes)}), merge base {merge_base[:12]}:")
    print("\n".join(_describe(change) for change in changes))
    head_paths = [change.head_path for change in changes]
    with _cache_root(cache_dir) as cache_root:
        head_errors = run_mypy(repo, head_paths, cache_root / "head")
        head_ignores = {path: read_ignores(repo / path) for path in head_paths}
        base_errors, base_ignores = _base_side(repo, merge_base, changes, cache_root)
    increases: list[IgnoreIncrease] = []
    for path in head_paths:
        increase = compare_ignores(path, head_ignores[path], base_ignores.get(path, []))
        if increase is not None:
            increases.append(increase)
    return _report(len(changes), compare_errors(head_errors, base_errors), increases)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base", required=True, help="Target branch; compared at its merge base with HEAD.")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Repository root (default: cwd).")
    parser.add_argument("--cache-dir", type=Path, default=None, help="Keep mypy caches here (head/, base/).")
    parser.add_argument("pathspecs", nargs="*", help="git pathspecs naming the files in scope (after --).")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point. 0 = pass or nothing in scope, 1 = something new, 2 = could not check."""
    args = _parser().parse_args(argv)
    if not args.pathspecs:
        print("mypy ratchet: COULD NOT CHECK -- no pathspecs given; pass the scope after --")
        return 2
    try:
        return run_ratchet(args.repo.resolve(), args.base, args.pathspecs, args.cache_dir)
    except RatchetError as exc:
        print(f"mypy ratchet: COULD NOT CHECK -- {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-11-16 [python-coder/BP-1300f-1]: Created. Ratchet over the CI mypy
#   job: two runs (head, merge-base worktree) on the changed files with full
#   repository context, line-insensitive multiset matching, renames re-keyed
#   from their old path, tokenizer-counted type-ignores, and a summary that
#   never looks like a pass when nothing was inspected or mypy could not
#   finish. (#TICKETLESS reason=bp-1300f-ac-driven-no-ticket-file)
# ====================================================================
