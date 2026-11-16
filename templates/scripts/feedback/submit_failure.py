"""
MODULE: leafcutter/scripts/feedback/submit_failure.py
GOAL: Make every failure exit of ``submit_feedback.py`` say WHY it failed: print
      exactly one ``submit-failed:<reason>:<category>`` line on stderr, with
      ``<reason>`` drawn from the closed set in ``submit_failure_reasons.json``.
BUSINESS CONTEXT: A caller that cannot confirm a report landed records a failure
      marker. Without a reason the roughly 780 historical markers are
      indistinguishable, and a report that WAS written (empty stdout capture)
      looks the same as one that was lost, so a retry would duplicate it. The
      reason and the destined category travel on the script's own error stream
      (AC INF-500d-3).
ARCHITECTURE: Sibling of ``submit_feedback.py``; the build deploys
      ``templates/scripts/feedback/`` whole, so neither this module nor the
      vocabulary file needs a deploy-map entry. The vocabulary is read from
      ``submit_failure_reasons.json`` beside this file and is the ONLY source of
      identifiers: there is no built-in fallback list. Standard library only, so
      it works in the very case it must report (PyYAML not installed).

Stderr contract: one line ``submit-failed:<reason>:<category>`` and nothing else
on that line; stdout stays empty and the exit status stays non-zero. The
``<category>`` part is the ``--category`` value, or ``-`` when it is missing,
empty or not a single token free of whitespace, ``:``, ``(`` and ``)``.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterator, NoReturn, Sequence

VOCABULARY_NAME = "submit_failure_reasons.json"
REASON_PREFIX = "submit-failed:"
NO_CATEGORY = "-"

WRITER_NOT_ALLOWED = "writer-not-allowed"
MALFORMED_SUBMISSION = "malformed-submission"
FACILITY_UNAVAILABLE = "facility-unavailable"
DESTINATION_UNWRITABLE = "destination-unwritable"

_CATEGORY_TOKEN_RE = re.compile(r"[^\s:()]+")
_CATEGORY_FLAG = "--category"


class VocabularyError(Exception):
    """The reason vocabulary file is missing, unreadable or not shaped as expected."""

    def __init__(self, path: Path, problem: object) -> None:
        """Name the file and what is wrong with it in one message."""
        super().__init__(f"{path}: {problem}")


def vocabulary_path() -> Path:
    """Return where ``submit_failure_reasons.json`` is expected: beside this module.

    The invoked (absolute) location is preferred so a symlinked deployed copy
    stays anchored there; the resolved location is used when the first is absent.

    Returns:
        Path: The vocabulary file path (it may not exist).
    """
    invoked = Path(os.path.abspath(__file__)).parent / VOCABULARY_NAME
    if invoked.is_file():
        return invoked
    return Path(__file__).resolve().parent / VOCABULARY_NAME


def load_reason_ids(path: Path | None = None) -> frozenset[str]:
    """Read the closed set of reason identifiers from the vocabulary file.

    Args:
        path: Override path; the file beside this module when None.

    Returns:
        frozenset[str]: The reason identifiers the file declares.

    Raises:
        VocabularyError: When the file cannot be read, is not JSON, or holds no
            ``reasons`` list of objects with a string ``id``.
    """
    target = path or vocabulary_path()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise VocabularyError(target, exc) from exc
    reasons = data.get("reasons") if isinstance(data, dict) else None
    if not isinstance(reasons, list) or not reasons:
        raise VocabularyError(target, "no 'reasons' list")
    ids = [item["id"] for item in reasons if isinstance(item, dict) and isinstance(item.get("id"), str)]
    if len(ids) != len(reasons):
        raise VocabularyError(target, "every reason needs a string 'id'")
    return frozenset(ids)


def category_token(value: object) -> str:
    """Return ``value`` when it is one token free of whitespace, ``:``, ``(``, ``)``; else ``-``."""
    if isinstance(value, str) and _CATEGORY_TOKEN_RE.fullmatch(value):
        return value
    return NO_CATEGORY


def category_from_argv(argv: Sequence[str]) -> str:
    """Find the ``--category`` value in raw argv, in ``--category v`` or ``--category=v`` form.

    Used when the argument parser itself failed, so no parsed value exists.

    Args:
        argv: The raw argument list (without the program name).

    Returns:
        str: The value as a category token, or ``-`` when absent or unrepresentable.
    """
    for index, token in enumerate(argv):
        if token.startswith(_CATEGORY_FLAG + "="):
            return category_token(token.split("=", 1)[1])
        if token == _CATEGORY_FLAG:
            following = argv[index + 1] if index + 1 < len(argv) else ""
            return category_token("" if following.startswith("--") else following)
    return NO_CATEGORY


class Reporter:
    """Prints the one ``submit-failed:<reason>:<category>`` line of a failed run."""

    def __init__(self, reason_ids: frozenset[str]) -> None:
        """Remember the vocabulary every emitted reason must belong to."""
        self._ids = reason_ids

    def emit(self, reason: str, category: str) -> None:
        """Print the reason line to stderr when ``reason`` is a vocabulary member.

        A reason absent from the vocabulary is never printed (the line would
        name an identifier no consumer knows); a WARNING without it is printed.
        """
        if reason not in self._ids:
            print("[submit_feedback] WARNING: failure reason is not in the vocabulary; no reason line printed", file=sys.stderr)
            return
        print(f"{REASON_PREFIX}{reason}:{category}", file=sys.stderr)

    @contextlib.contextmanager
    def scope(self, reason: str, category: str) -> Iterator[None]:
        """Emit the reason line when the wrapped code exits non-zero via SystemExit, then re-raise."""
        try:
            yield
        except SystemExit as exc:
            if exc.code not in (0, None):
                self.emit(reason, category)
            raise


def open_reporter() -> Reporter | None:
    """Load the vocabulary and return a Reporter, or None after naming the unreadable file.

    The caller must then fail (non-zero, empty stdout) WITHOUT a reason line:
    the run's error stream then holds none of the lines a caller recognises, and
    the caller rule yields facility-unavailable. No built-in list stands in.
    """
    try:
        return Reporter(load_reason_ids())
    except VocabularyError as exc:
        print(f"[submit_feedback] ERROR: cannot read the failure-reason vocabulary: {exc}", file=sys.stderr)
        return None


class ReasonedParser(argparse.ArgumentParser):
    """ArgumentParser whose usage errors also print a malformed-submission reason line."""

    def __init__(self, *args: object, reporter: Reporter | None = None, raw_argv: Sequence[str] = (), **kwargs: object) -> None:
        """Build the parser; ``reporter`` and ``raw_argv`` serve the failure line."""
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._reporter = reporter
        self._raw_argv = list(raw_argv)

    def error(self, message: str) -> NoReturn:
        """Print usage and the message as argparse does, add the reason line, exit 2."""
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        if self._reporter is not None:
            self._reporter.emit(MALFORMED_SUBMISSION, category_from_argv(self._raw_argv))
        sys.exit(2)

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-11-16 [python-coder/fastlane/INF-500d-3]:
#   New module. The closed reason set lives in submit_failure_reasons.json (JSON,
#   standard library only: PyYAML may be the very thing that is missing). The
#   script reads it on every run and fails closed, with no reason line, when it
#   is unreadable; it never substitutes a built-in list. Validators keep calling
#   sys.exit(1); Reporter.scope wraps them so the reason is attached by the
#   caller that knows it, and the exit stays non-zero. (AC INF-500d-3)
# ====================================================================
