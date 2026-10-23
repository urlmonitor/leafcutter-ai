"""
MODULE: build_shared_validation
GOAL: Validate every workflow route template and every shared-block source in one pass, and
    collect every problem, before the install writes any route (BO-4500b-1-i..v).
BUSINESS CONTEXT: A half-installed route set would mix old and new block text -- the drift the
    shared-block mechanism exists to prevent. So all failures are found first, reported
    together with route path, 1-based marker line and block name, and the install then stops.
ARCHITECTURE: Pure text functions plus one read of ``_shared/``. The marker grammar is the
    one defined in build_shared_blocks (``MARKER_RE`` family); this module only adds the END
    form of the same grammar. Blocks are the ``_shared/*.js`` sources, consumers are the
    top-level ``*.js`` route templates; neither set is listed in code. The awaiting-adoption
    declaration is tracked data in ``_shared/awaiting-adoption.json``; marker pairs kept by
    hand on purpose are declared in ``_shared/hand-kept.json``.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from build_shared_blocks import (
    HAND_KEPT_FILE,
    MARKER_RE,
    SharedBlockError,
    load_commit_step_values,
    read_hand_kept,
)
from template_compiler import inject_config

DECLARATION_FILE = "awaiting-adoption.json"
_COMMIT_STEP_PLACEHOLDER = "{{config.commit_step_"
_PLACEHOLDER_LEFT_RE = re.compile(r"\{\{config\.[^}\s]*\}\}")
# Same grammar as build_shared_blocks.MARKER_RE, covering both ends of a pair.
_EDGE_RE = re.compile(MARKER_RE.pattern.replace("-START[", "-(START|END)[", 1), re.MULTILINE)


def _rel(path: Path, package_root: Path) -> str:
    """Return ``path`` relative to the package root (posix form) when possible."""
    try:
        return path.relative_to(package_root).as_posix()
    except ValueError:
        return path.as_posix()


def _markers(text: str) -> list[tuple[int, str, str]]:
    """Return ``(1-based line, 'START'|'END', block name)`` for every marker line in ``text``."""
    return [
        (text.count("\n", 0, m.start()) + 1, m.group(2), m.group(1))
        for m in _EDGE_RE.finditer(text)
    ]


def scan_route(text: str) -> tuple[list[tuple[int, int, str]], list[tuple[int, str]]]:
    """Pair the markers of one route template.

    Returns ``(pairs, problems)``: ``pairs`` holds ``(start line, end line, name)`` for each
    properly paired place; ``problems`` holds ``(line, message)`` for unpaired, nested and
    overlapping markers.
    """
    pairs: list[tuple[int, int, str]] = []
    problems: dict[int, str] = {}
    stack: list[tuple[str, int]] = []
    nested: dict[int, str] = {}
    for line, kind, name in _markers(text):
        if kind == "START":
            if stack:
                outer, outer_line = stack[-1]
                nested[line] = (
                    f"{name} (start marker line {line}) is marked inside {outer} "
                    f"(start marker line {outer_line}); marker pairs must not nest"
                )
            stack.append((name, line))
            continue
        idx = next((i for i in range(len(stack) - 1, -1, -1) if stack[i][0] == name), None)
        if idx is None:
            problems[line] = (
                f"{name}-END has no matching {name}-START before it; add the start marker "
                f"or remove this end marker"
            )
            continue
        for inner, inner_line in stack[idx + 1:]:
            nested.pop(inner_line, None)
            problems[inner_line] = (
                f"{name} (start marker line {stack[idx][1]}) and {inner} (start marker line "
                f"{inner_line}) overlap; close {inner} before {name}"
            )
        pairs.append((stack[idx][1], line, name))
        del stack[idx]
    for name, line in stack:
        problems.setdefault(
            line,
            f"{name}-START has no matching {name}-END after it; add the end marker",
        )
    problems.update({k: v for k, v in nested.items() if k not in problems})
    return pairs, sorted(problems.items())


def read_declaration(shared_dir: Path, package_root: Path) -> tuple[dict[str, list[str]], list[str]]:
    """Return ``(declared, errors)`` from ``_shared/awaiting-adoption.json``.

    An entry with an empty adopter list counts as no declaration and is dropped.
    """
    path = shared_dir / DECLARATION_FILE
    if not path.is_file():
        return {}, []
    rel = _rel(path, package_root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {}, [f"{rel}: the awaiting-adoption declaration cannot be read: {exc}"]
    ok = isinstance(data, dict) and all(
        isinstance(v, list) and all(isinstance(a, str) for a in v) for v in data.values()
    )
    if not ok:
        return {}, [f"{rel}: must hold one object mapping a block name to a list of adopting record ids"]
    return {k: v for k, v in data.items() if v}, []


def _check_route(rel: str, text: str, known: dict[str, bool], used: dict[str, list[str]],
                 hand_kept: dict[str, str]) -> list[str]:
    """Return the problem messages of one route template and record which blocks it uses."""
    lines = text.splitlines(keepends=True)
    pairs, problems = scan_route(text)
    found: list[tuple[int, str]] = []
    names = ", ".join(sorted(known))
    for start, end, name in pairs:
        if name not in known:
            if end == start + 1:
                found.append((start, f"unknown block {name}; known blocks: {names}"))
            elif name not in hand_kept:
                found.append((start, (
                    f"unknown block {name}; known blocks: {names}; or declare it hand-kept "
                    f"in _shared/{HAND_KEPT_FILE}")))
            continue
        used.setdefault(name, [])
        if rel not in used[name]:
            used[name].append(rel)
        if end != start + 1:
            filler = "".join(lines[start:end - 1])
            kind = "only whitespace" if not filler.strip() else "text"
            found.append((start, (
                f"the {name} marker pair holds {kind}; the marker pair in a route template "
                f"must be empty (the install fills it from _shared/{name.lower()}.js)")))
    found.extend(problems)
    return [f"{rel}:{line}: {msg}" for line, msg in sorted(found, key=lambda f: f[0])]


def unresolved_placeholders(src: Path, package_root: Path, config: dict[str, Any]) -> list[str]:
    """Return one message per ``{{config.<key>}}`` in block source ``src`` that cannot be resolved.

    The values are the ones the install uses: the commit-step values (when the source
    carries a ``commit_step_`` placeholder) over the build's ``config``.
    """
    text = src.read_text(encoding="utf-8")
    rel = _rel(src, package_root)
    values = dict(config)
    if _COMMIT_STEP_PLACEHOLDER in text:
        try:
            values.update(load_commit_step_values(package_root))
        except SharedBlockError as exc:
            return [f"{rel}: the commit step values it needs cannot be loaded: {exc}"]
    found: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for left in _PLACEHOLDER_LEFT_RE.findall(inject_config(line, values)):
            found.append(
                f"{rel}:{number}: placeholder {left} cannot be resolved; "
                f"set it in skills_config.json or remove it"
            )
    return found


def validate_shared_blocks(src_dir: Path, package_root: Path,
                           config: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Validate all route templates and block sources; return ``(errors, awaiting_report)``.

    ``errors`` holds every problem found, route problems first in route-path then line
    order, then unresolvable block placeholders; ``awaiting_report`` holds one line per
    block declared as awaiting adoption. ``config`` is the build's merged configuration.
    """
    shared = src_dir / "_shared"
    sources = sorted(shared.glob("*.js")) if shared.is_dir() else []
    known: dict[str, bool] = {}
    for src in sources:
        known[src.stem.upper()] = bool(src.read_text(encoding="utf-8").strip(" \t\r\n"))
    declared, errors = read_declaration(shared, package_root)
    try:
        hand_kept = read_hand_kept(shared)
    except SharedBlockError as exc:
        hand_kept = {}
        errors.append(str(exc))
    used: dict[str, list[str]] = {}
    route_errors: list[str] = []
    for route in sorted(src_dir.glob("*.js")):
        rel = _rel(route, package_root)
        route_errors.extend(_check_route(rel, route.read_text(encoding="utf-8"), known, used, hand_kept))
    errors = route_errors + errors
    for src in sources:
        errors.extend(unresolved_placeholders(src, package_root, config))
    for name in sorted(known):
        if not known[name]:
            needed = ", ".join(used.get(name, [])) or "(no route yet)"
            errors.append(f"{name}: the source _shared/{name.lower()}.js is empty; needed by {needed}")
        if name not in used and name not in declared:
            errors.append(
                f"{name}: a source exists but no route uses it; mark a place for it in a route, "
                f"or declare it awaiting adoption in _shared/{DECLARATION_FILE}"
            )
    for name in sorted(declared):
        if name in used:
            errors.append(
                f"{name}: the awaiting-adoption declaration is stale because {', '.join(used[name])} "
                f"uses the block; remove it from _shared/{DECLARATION_FILE}"
            )
        elif name not in known:
            errors.append(f"{name}: declared awaiting adoption in _shared/{DECLARATION_FILE} but has no source")
    report = [
        f"Shared block {name} awaiting adoption by {', '.join(declared[name])}"
        for name in sorted(declared) if name not in used
    ]
    return errors, report


def validate_or_fail(src_dir: Path, package_root: Path, config: dict[str, Any]) -> None:
    """Run the validation pass; print every failure to stderr and raise, or report declarations.

    The raised ``SharedBlockError`` carries every problem line, so a caller that sees only
    the exception still learns the route path, line and block name of each.
    """
    errors, report = validate_shared_blocks(src_dir, package_root, config)
    if errors:
        for msg in errors:
            print(f"[ERROR] shared blocks: {msg}", file=sys.stderr)
        head = f"{len(errors)} shared-block problem(s) found; no workflow route was installed"
        raise SharedBlockError("\n".join([head, *errors]))
    for line in report:
        print(line)


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-10-23 [python-coder/BO-4500b-1]: One validation pass collects every route and
#   source problem before any route is written; the exception text carries all problem
#   lines (callers that catch only the exception, e.g. BO-4300c-3, still see them).
# - 2026-10-23 [python-coder/BO-4500b-1]: Unresolvable {{config.*}} placeholders in a
#   block source fail the install here, because inject_config passes unknown keys
#   through and the raw placeholder would otherwise ship in every route.
# - 2026-10-23 [python-coder/BO-4500b-1]: A marker pair holding text with no _shared
#   source must be declared in _shared/hand-kept.json, so no route is silently skipped.
# ===========================================================================
