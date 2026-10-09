#!/usr/bin/env python3
"""
MODULE: check_exclusion_compensation
GOAL: Refuse a deselection that has no INVOKED opt-in. Exit 0 when nothing is
    deselected or every deselected marker is collected by an opt-in that runs
    automatically and fails its job on a failing test; exit non-zero, naming the
    marker and what is missing, otherwise.
BUSINESS CONTEXT: TQ-600a-13-i. A deselection with no invoked alternative costs
    the only quick warning of a shared-layout corruption. The deselection is one
    line and the compensating cadence is not, so the cheap half would land first
    unless landing it alone is made to fail. This gate runs in CI on every pull
    request, so a deselection cannot merge ahead of its compensation.
ARCHITECTURE: Reads ``<root>/pytest.ini`` (the ``-m "not <marker> ..."``
    expression in addopts gives the deselected markers) and
    ``<root>/.github/workflows/*.yml``. An opt-in is INVOKED only when ALL of:
    the workflow triggers on EVERY merge to main or on a schedule (a push with a
    tags-only filter, a ``paths`` filter, or a branches filter excluding main does
    not count; workflow_dispatch alone is a button, not a cadence); the lane's
    first ``pytest -m <expr>`` ``run:`` step names the marker positively; neither
    its job nor the step carries an ``if:`` that is not trivially true (absent,
    ``always()``, ``success()``, ``true``); and its failure is not swallowed (no
    ``continue-on-error``, no ``|| true``). A step wrapped by
    ``post_merge_suite.py run`` exits 0 by design, so it only counts when a
    downstream job that ``needs`` the lane job runs ``post_merge_suite.py
    exit-status`` unswallowed. Only the FIRST opt-in step of a workflow is the
    lane's step; a later one (the retry job) is the same cadence. An input that
    cannot be read is refused, never assumed fine. ``evaluate_marker_expression``
    is a small local evaluator for ``-m`` expressions (and/or/not/parentheses over
    bare marker names) that refuses anything else, so tests need no private pytest
    API. Usage: ``python scripts/suite_performance/check_exclusion_compensation.py
    [--root <project>]`` (``--root`` defaults to the current directory).
"""

from __future__ import annotations

import argparse
import configparser
import fnmatch
import logging
import re
import shlex
import sys
from collections.abc import Collection
from pathlib import Path

import yaml

logger = logging.getLogger("check_exclusion_compensation")

_OPERATORS = {"&&", "||", ";", "|"}
_NOT_MARKER = re.compile(r"\bnot\s+(\w+)")
_SWALLOWED_STATUS = re.compile(r"\|\|\s*(true\b|:)")
_WRAPPER_RUN = re.compile(r"post_merge_suite\.py\s+run\b")
_RED_GATE = re.compile(r"post_merge_suite\.py\s+exit-status\b")
_DROPPED_WITH_VALUE = {"--splits", "--group", "--durations-path"}
_TRIVIALLY_TRUE = {"always()", "success()", "true"}


class GateInputError(RuntimeError):
    """An input the gate must read (pytest.ini or a workflow) could not be read or parsed."""


class MarkerExpressionError(ValueError):
    """A ``-m`` expression is outside the small grammar this module evaluates."""


# --------------------------------------------------------------------------- marker expressions
_TOKEN = re.compile(r"\s*(\(|\)|[A-Za-z_]\w*)")
_KEYWORDS = {"and", "or", "not"}


def _tokenize(expression: str) -> list[str]:
    """Split an expression into parens and words; anything else is refused."""
    tokens, position = [], 0
    while position < len(expression.rstrip()):
        match = _TOKEN.match(expression, position)
        if match is None:
            detail = f"unsupported character in marker expression {expression!r} at {position}"
            raise MarkerExpressionError(detail)
        tokens.append(match.group(1))
        position = match.end()
    return tokens


class _Parser:
    """Recursive-descent evaluator: or > and > not > (group | marker name)."""

    def __init__(self, tokens: list[str], markers: Collection[str], expression: str) -> None:
        self.tokens, self.markers, self.expression, self.at = tokens, markers, expression, 0

    def _peek(self) -> str | None:
        return self.tokens[self.at] if self.at < len(self.tokens) else None

    def _take(self) -> str:
        token = self._peek()
        if token is None:
            detail = f"marker expression {self.expression!r} ends unexpectedly"
            raise MarkerExpressionError(detail)
        self.at += 1
        return token

    def parse(self) -> bool:
        value = self._or()
        if self._peek() is not None:
            detail = f"marker expression {self.expression!r}: unexpected {self._peek()!r}"
            raise MarkerExpressionError(detail)
        return value

    def _or(self) -> bool:
        value = self._and()
        while self._peek() == "or":
            self._take()
            value = self._and() or value
        return value

    def _and(self) -> bool:
        value = self._not()
        while self._peek() == "and":
            self._take()
            value = self._not() and value
        return value

    def _not(self) -> bool:
        token = self._take()
        if token == "not":
            return not self._not()
        if token == "(":
            value = self._or()
            if self._take() != ")":
                detail = f"marker expression {self.expression!r}: expected ')'"
                raise MarkerExpressionError(detail)
            return value
        if token == ")" or token in _KEYWORDS:
            detail = f"marker expression {self.expression!r}: unexpected {token!r}"
            raise MarkerExpressionError(detail)
        return token in self.markers


def evaluate_marker_expression(expression: str, markers: Collection[str]) -> bool:
    """Evaluate a ``-m`` expression for a test carrying ``markers``; refuse anything outside the grammar."""
    return _Parser(_tokenize(expression), markers, expression).parse()


# --------------------------------------------------------------------------- inputs
def _read_workflow(path: Path) -> dict:
    """Parse one workflow file; an unreadable one is a refusal, not a skip."""
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        detail = f"cannot read workflow {path}: {exc}"
        raise GateInputError(detail) from exc
    return doc if isinstance(doc, dict) else {}


def deselected_markers(root: Path) -> list[str]:
    """Return the markers pytest.ini's addopts ``-m`` expression deselects (``not <marker>``)."""
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string((root / "pytest.ini").read_text(encoding="utf-8"))
    except (OSError, configparser.Error) as exc:
        detail = f"cannot read {root / 'pytest.ini'}: {exc}"
        raise GateInputError(detail) from exc
    addopts = parser.get("pytest", "addopts", fallback="")
    tokens = shlex.split(addopts)
    found: list[str] = []
    for index, token in enumerate(tokens[:-1]):
        if token == "-m":
            found += [m for m in _NOT_MARKER.findall(tokens[index + 1]) if m not in found]
    return found


# --------------------------------------------------------------------------- workflow reading
def events(doc: dict) -> dict:
    """The workflow's trigger events; PyYAML parses the bare key ``on`` as boolean True."""
    on = doc.get("on", doc.get(True))
    if isinstance(on, str):
        return {on: None}
    if isinstance(on, list):
        return dict.fromkeys(on)
    return dict(on or {})


def _push_covers_main(push: object) -> bool:
    """True only for a push trigger that fires on EVERY merge to main."""
    config = push if isinstance(push, dict) else {}
    if push is not None and not isinstance(push, dict):
        return False
    if "paths" in config or "paths-ignore" in config:
        return False
    if ("tags" in config or "tags-ignore" in config) and not ({"branches", "branches-ignore"} & set(config)):
        return False
    branches, ignored = config.get("branches"), config.get("branches-ignore")
    if branches is not None and not any(fnmatch.fnmatchcase("main", p) for p in branches):
        return False
    return not (ignored is not None and any(fnmatch.fnmatchcase("main", p) for p in ignored))


def is_automatic(doc: dict) -> bool:
    """True when the workflow runs with no human action: a schedule, or every push to main."""
    triggers = events(doc)
    return "schedule" in triggers or ("push" in triggers and _push_covers_main(triggers["push"]))


def pytest_args(run_text: str) -> list[str] | None:
    """Return the args after ``pytest`` on the first logical line that runs it, minus shard flags."""
    for line in re.sub(r"\\\n", " ", run_text).splitlines():
        if "pytest" not in line:
            continue
        try:
            tokens = shlex.split(line)
        except ValueError:
            continue
        if "pytest" not in tokens:
            continue
        args: list[str] = []
        skip = False
        for token in tokens[tokens.index("pytest") + 1 :]:
            if token in _OPERATORS:
                break
            if skip:
                skip = False
            elif token in _DROPPED_WITH_VALUE:
                skip = True
            else:
                args.append(token)
        return args
    return None


def marker_expression(args: list[str]) -> str | None:
    """Return the ``-m`` expression among pytest args, or None."""
    if "-m" in args and args.index("-m") + 1 < len(args):
        return args[args.index("-m") + 1]
    return None


def swallows(value: object) -> bool:
    """True when a ``continue-on-error`` value makes a failure non-fatal."""
    return value not in (None, False, "false")


def trivially_true(condition: object) -> bool:
    """True for an absent ``if:`` or one that is just always() / success() / true."""
    if condition is None or condition is True:
        return True
    text = str(condition).strip()
    wrapped = re.fullmatch(r"\$\{\{(.*)\}\}", text, re.S)
    return (wrapped.group(1).strip() if wrapped else text) in _TRIVIALLY_TRUE


def _unswallowed(job: dict, step: dict) -> bool:
    """True when neither the job, the step nor the command swallows a failure."""
    return not (
        swallows(job.get("continue-on-error"))
        or swallows(step.get("continue-on-error"))
        or _SWALLOWED_STATUS.search(step.get("run") or "")
    )


def _has_red_gate(doc: dict, lane_job_id: str) -> bool:
    """True when a downstream job needing the lane job runs ``exit-status`` unswallowed (job if: trivial)."""
    for job_id, job in (doc.get("jobs") or {}).items():
        needs = (job or {}).get("needs") or []
        needs = [needs] if isinstance(needs, str) else list(needs)
        if job_id == lane_job_id or lane_job_id not in needs or not trivially_true(job.get("if")):
            continue
        if any(_RED_GATE.search(s.get("run") or "") and _unswallowed(job, s) for s in job.get("steps") or []):
            return True
    return False


def lane_step(doc: dict) -> str | None:
    """Return the run text of the workflow's first opt-in step if it counts as INVOKED, else None."""
    for job_id, job in (doc.get("jobs") or {}).items():
        for step in (job or {}).get("steps") or []:
            run_text = step.get("run") or ""
            if marker_expression(pytest_args(run_text) or []) is None:
                continue
            if not (_unswallowed(job, step) and trivially_true(job.get("if")) and trivially_true(step.get("if"))):
                return None
            if _WRAPPER_RUN.search(run_text) and not _has_red_gate(doc, job_id):
                return None
            return run_text
    return None


def invoked_cadences(root: Path) -> list[tuple[str, str]]:
    """Return (workflow file name, lane step run text) for every INVOKED opt-in cadence under root."""
    found = []
    for path in sorted((root / ".github" / "workflows").glob("*.yml")):
        doc = _read_workflow(path)
        run_text = lane_step(doc) if is_automatic(doc) else None
        if run_text is not None:
            found.append((path.name, run_text))
    return found


def invoked_expressions(root: Path) -> list[tuple[str, str]]:
    """Return (workflow file name, ``-m`` expression) for every INVOKED opt-in cadence under root."""
    return [(name, marker_expression(pytest_args(text) or []) or "") for name, text in invoked_cadences(root)]


def _selects(expression: str, marker: str) -> bool:
    """True when the expression names the marker positively (not as ``not <marker>``)."""
    stripped = _NOT_MARKER.sub("", expression)
    return re.search(rf"\b{re.escape(marker)}\b", stripped) is not None


def uncompensated(root: Path) -> list[str]:
    """Return the deselected markers that no invoked opt-in collects."""
    markers = deselected_markers(root)
    if not markers:
        return []
    cadences = invoked_expressions(root)
    return [m for m in markers if not any(_selects(expr, m) for _name, expr in cadences)]


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: 0 accepted, 1 refused (names the marker), 2 unreadable input (refused)."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Refuse a deselection with no invoked opt-in.")
    parser.add_argument("--root", default=".", help="project root holding pytest.ini and .github/workflows")
    root = Path(parser.parse_args(argv).root)
    try:
        missing = uncompensated(root)
    except GateInputError:
        logger.exception("REFUSED: cannot establish what is deselected or invoked")
        return 2
    for marker in missing:
        logger.error(
            "REFUSED: pytest.ini deselects tests marked '%s' but no INVOKED opt-in collects them. "
            "Add a workflow, triggered by every push to main or a schedule, whose pytest step runs "
            "`-m %s`, has no conditional `if:`, and whose failure fails the job (no continue-on-error, "
            "no `|| true`; a post_merge_suite.py run wrapper needs a downstream exit-status job). "
            "An opt-in that is only defined, or only workflow_dispatch, is not invoked.",
            marker,
            marker,
        )
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
