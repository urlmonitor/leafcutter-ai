"""
MODULE: shared_block_identity
GOAL: Check that every INSTALLED copy of a shared block equals its single source, rendered as the
    install renders it, byte for byte, and name every copy that differs.
BUSINESS CONTEXT: A fix to a shared block must reach every route (BO-4500b). Filling at install
    time (BO-4500b-1) covers what the install produced; this check covers what is in the
    installed routes NOW, including a hand edit made after the install (BO-4500b-2, -i, -ii).
ARCHITECTURE: Reads installed ``*.js`` routes under a deployed layout root (never templates) and
    block sources under ``<package_root>/templates/workflows-js/_shared``. Consumers are
    discovered from installed marker pairs, never from a list. The expected text reuses the
    install's own resolution (``build_shared_blocks._block_text`` then ``inject_config``). The
    awaiting-adoption declaration is read with the install's ``read_declaration``. Files are read
    as bytes so no newline or encoding translation hides drift. No build.py is spawned.
"""

from __future__ import annotations

import itertools
import re
from pathlib import Path
from typing import Any

from build_shared_blocks import SharedBlockError, _block_text, read_hand_kept
from build_shared_validation import read_declaration
from template_compiler import inject_config

# The check side is deliberately looser than the install's MARKER_RE: any line beginning
# ``// NAME-START`` counts, whatever follows it or however the line ends, so a copy whose
# START line is not byte-exact (CRLF, trailing text) is inspected and reported, never skipped.
_START_RE = re.compile(rb"^// ([A-Z][A-Z0-9-]*)-START", re.MULTILINE)
_END_RE = re.compile(rb"^// ([A-Z][A-Z0-9-]*)-END", re.MULTILINE)
_SHARED_REL = Path("templates") / "workflows-js"


def _read_bytes(path: Path) -> bytes:
    """Return the raw bytes of ``path``; an unreadable file is a loud failure."""
    try:
        return path.read_bytes()
    except OSError as exc:
        msg = f"{path}: installed route cannot be read: {exc}"
        raise SharedBlockError(msg) from exc


def _first_differing_line(actual: bytes, expected: bytes, body_first_line: int) -> int:
    """Return the 1-based installed-file line of the first difference between two bodies."""
    pairs = itertools.zip_longest(actual.split(b"\n"), expected.split(b"\n"))
    for index, (got, want) in enumerate(pairs):
        if got != want:
            return body_first_line + index
    return body_first_line


def _find_copies(raw: bytes) -> tuple[list[tuple[str, bytes | None, int, int]], list[tuple[str, int]]]:
    """Return ``(copies, orphan_ends)`` found in ``raw``.

    A copy is ``(block, body bytes or None, first body line, START line)``: the body runs from the
    byte after the START line's ``\\n`` up to the END marker, so the line ending is judged by the
    comparison, not by the finder. ``body`` is ``None`` when no END follows the START. An orphan
    end is ``(block, line)`` for an END marker no START pairs with.
    """
    copies: list[tuple[str, bytes | None, int, int]] = []
    paired_ends: set[int] = set()
    for match in _START_RE.finditer(raw):
        block = match.group(1).decode("ascii")
        newline = raw.find(b"\n", match.end())
        body_start = newline + 1 if newline != -1 else len(raw)
        end = raw.find(f"// {block}-END".encode(), body_start)
        body = raw[body_start:end] if end != -1 else None
        if end != -1:
            paired_ends.add(end)
        copies.append((block, body, raw.count(b"\n", 0, body_start) + 1, raw.count(b"\n", 0, match.start()) + 1))
    orphans = [
        (m.group(1).decode("ascii"), raw.count(b"\n", 0, m.start()) + 1)
        for m in _END_RE.finditer(raw) if m.start() not in paired_ends
    ]
    return copies, orphans


def _expected_bodies(shared_dir: Path, package_root: Path, config: dict[str, Any]) -> dict[str, bytes]:
    """Return ``{BLOCK: rendered source bytes}`` for every source under ``_shared``."""
    expected = {}
    for source in sorted(shared_dir.glob("*.js")):
        block = source.stem.upper()
        rendered = inject_config(_block_text(block, source.name, shared_dir.parent, package_root), config)
        expected[block] = rendered.encode("utf-8")
    return expected


def _collect(
    layout_root: Path, expected: dict[str, bytes], hand_kept: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, list[str]], set[tuple[str, str]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Compare every installed copy.

    Returns ``(differences, copies_by_block, bad, unpaired, not_checked)``: ``bad`` holds the
    ``(block, route)`` pairs that did not match; ``unpaired`` lists a START without END or an END
    without START ({route, block, line, problem}); ``not_checked`` lists hand-kept and unknown
    block marker pairs ({route, block, reason}) which are reported but never fail the check.
    """
    differences: list[dict[str, Any]] = []
    copies: dict[str, list[str]] = {}
    bad: set[tuple[str, str]] = set()
    unpaired: list[dict[str, Any]] = []
    not_checked: list[dict[str, Any]] = []
    for path in sorted(layout_root.rglob("*.js")):
        route = path.relative_to(layout_root).as_posix()
        found, orphans = _find_copies(_read_bytes(path))
        for block, line in orphans:
            if block in expected and block not in hand_kept:
                unpaired.append({"route": route, "block": block, "line": line, "problem": "END without START"})
        for block, body, first_line, start_line in found:
            if block not in expected or block in hand_kept:
                reason = "hand-kept (declared)" if block in hand_kept else "unknown block (no source)"
                not_checked.append({"route": route, "block": block, "reason": reason})
                continue
            copies.setdefault(block, []).append(route)
            if body is None:
                unpaired.append({"route": route, "block": block, "line": start_line, "problem": "START without END"})
                bad.add((block, route))
            elif body != expected[block]:
                line = _first_differing_line(body, expected[block], first_line)
                differences.append({"route": route, "block": block, "first_differing_line": line})
                bad.add((block, route))
    return differences, copies, bad, unpaired, not_checked


def _failure_lines(result: dict[str, Any], layout_root: Path) -> list[str]:
    """Return the human lines describing why the check failed (empty when it passed)."""
    lines = [
        f"{d['route']}: block {d['block']} differs from its source at line {d['first_differing_line']}"
        for d in result["differences"]
    ]
    lines += [f"{u['route']}: block {u['block']} {u['problem']} at line {u['line']}" for u in result["unpaired"]]
    lines += [f"block {b} has no installed copy under {layout_root}" for b in result["missing_blocks"]]
    return lines


def check_identity(layout_root: Path, package_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    """Check every installed copy of every shared block against its rendered source.

    ``layout_root`` is the deployed layout root (absolute); every ``*.js`` under it carrying a
    marker pair is inspected, in every deployed location. Returns ``passed``, ``message``,
    ``differences`` ({route, block, first_differing_line}), ``matched`` ({block, inspected,
    routes}), ``not_inspected`` ({block, reason}), ``missing_blocks``, ``unpaired`` ({route, block,
    line, problem}; a START without END or END without START fails), ``not_checked`` ({route,
    block, reason}; hand-kept and unknown-block pairs, reported but never failing) and
    ``inspected_total``. Zero copies inspected is a failure naming ``layout_root``.
    """
    shared_dir = package_root / _SHARED_REL / "_shared"
    expected = _expected_bodies(shared_dir, package_root, config)
    declared, decl_errors = read_declaration(shared_dir, package_root)
    differences, copies, bad, unpaired, not_checked = _collect(layout_root, expected, read_hand_kept(shared_dir))
    total = sum(len(routes) for routes in copies.values())
    absent = [b for b in sorted(expected) if b not in copies]
    result: dict[str, Any] = {
        "differences": differences,
        "matched": [
            {"block": b, "inspected": len(r), "routes": r}
            for b, r in sorted(copies.items()) if not any((b, x) in bad for x in r)
        ],
        "not_inspected": [
            {"block": b, "reason": "not inspected because it awaits adoption (awaiting adoption)"}
            for b in absent if b in declared
        ],
        "missing_blocks": [b for b in absent if b not in declared],
        "unpaired": unpaired,
        "not_checked": not_checked,
        "inspected_total": total,
    }
    problems = _failure_lines(result, layout_root) + decl_errors
    if total == 0:
        problems.insert(0, f"zero installed copies were inspected under {layout_root}")
    result["passed"] = not problems
    result["message"] = "\n".join(problems) if problems else _pass_message(result)
    if problems and not_checked:
        result["message"] += "\n" + _pass_message({"matched": [], "not_inspected": [], "not_checked": not_checked})
    return result


def _pass_message(result: dict[str, Any]) -> str:
    """Return the pass report: per block the copies inspected and the routes carrying it."""
    lines = [f"{m['block']}: {m['inspected']} copies inspected ({', '.join(m['routes'])})"
             for m in result["matched"]]
    lines += [f"{n['block']}: {n['reason']}" for n in result["not_inspected"]]
    lines += [f"{n['route']}: block {n['block']} not checked: {n['reason']}" for n in result["not_checked"]]
    return "\n".join(lines)


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-10-23 [python-coder/BO-4500b-2]: New identity check. Compares raw bytes
#   (no normalisation), discovers consumers from installed markers, renders the
#   expected text with the install's own _block_text + inject_config, and fails
#   when nothing was inspected or a non-declared source has no installed copy.
# ===========================================================================
