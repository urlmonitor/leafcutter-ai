"""
MODULE: check_fixed_scratch_paths
GOAL: Statically examine the real test suite and fail when any test keeps its
    scratch at a fixed location that two parallel workers could both reach
    (TQ-600b-2).
BUSINESS CONTEXT: A fixed-path collision is timing-dependent, so an equivalence
    run of the parallel suite catches it only by luck. A standing examination
    names the offender by construction and keeps doing so as tests are added.
ARCHITECTURE: Mode is STATIC (``ast`` over test sources, printed as
    ``mode: static``). Four shapes are recognised: a hardcoded absolute temp
    path literal; ``gettempdir()`` joined with a constant; a fixed ``dir=`` plus
    ``prefix=`` on a tempfile call; and a module-level constant holding any of
    these. A site is exempt only through ``# scratch-fixed-ok: <reason>`` on the
    offending line -- there is no file-name keyed exemption. Files that cannot
    be parsed are printed as ``UNEXAMINED`` and fail the run; an inspected count
    of zero also fails. CLI: ``python -m scripts.suite_performance.
    check_fixed_scratch_paths [--root DIR ...]``.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOTS = ("tests", "unit_tests")
_FIXED_TEMP = re.compile(r"^(/tmp|/var/tmp|/dev/shm)/[^/\s]")
_EXEMPT = re.compile(r"#\s*scratch-fixed-ok:\s*\S")
_TEMPFILE_CALLS = {"mkdtemp", "mkstemp", "NamedTemporaryFile", "TemporaryDirectory"}
_JOINERS = {"join", "joinpath", "Path", "PurePath"}


def _call_name(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    return func.id if isinstance(func, ast.Name) else None


def _has_gettempdir(node: ast.AST) -> bool:
    return any(_call_name(sub) == "gettempdir" for sub in ast.walk(node))


def _str_value(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _kwarg_str(call: ast.Call, name: str) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return _str_value(keyword.value)
    return None


def _joined_constant(node: ast.AST) -> str | None:
    """Constant string joined onto gettempdir() by ``/`` or a join call."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        constant = _str_value(node.right)
        if constant is not None and _has_gettempdir(node.left):
            return constant
    if _call_name(node) in _JOINERS:
        args = node.args
        constants = [c for c in map(_str_value, args) if c is not None]
        if constants and any(_has_gettempdir(arg) for arg in args if _str_value(arg) is None):
            return constants[-1]
    return None


def _fixed_dir_and_prefix(node: ast.AST) -> str | None:
    if _call_name(node) not in _TEMPFILE_CALLS:
        return None
    directory, prefix = _kwarg_str(node, "dir"), _kwarg_str(node, "prefix")
    if directory is None or prefix is None:
        return None
    return f"{directory.rstrip('/')}/{prefix}"


def _fixed_location(node: ast.AST) -> str | None:
    """The fixed location a node uses, or None when the node is not a fixed site."""
    literal = _str_value(node)
    if literal is not None:
        return literal if _FIXED_TEMP.match(literal) else None
    return _joined_constant(node) or _fixed_dir_and_prefix(node)


def _declared_exempt(lines: list[str], node: ast.AST) -> bool:
    first = node.lineno
    last = getattr(node, "end_lineno", None) or first
    return any(_EXEMPT.search(line) for line in lines[first - 1 : last])


def find_offenders(source: str) -> list[tuple[int, str]]:
    """Return ``(line, fixed location)`` for each undeclared fixed-path site."""
    tree = ast.parse(source)
    lines = source.splitlines()
    seen: dict[tuple[int, str], None] = {}
    for node in ast.walk(tree):
        if not hasattr(node, "lineno"):
            continue
        location = _fixed_location(node)
        if location is not None and not _declared_exempt(lines, node):
            seen.setdefault((node.lineno, location), None)
    return sorted(seen)


def _discover(roots: list[Path]) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    problems: list[str] = []
    for root in roots:
        if not root.is_dir():
            problems.append(f"UNEXAMINED {root}: root is not a directory")
            continue
        files.extend(sorted(p for p in root.rglob("test_*.py") if p.is_file()))
    return files, problems


def examine(roots: list[Path]) -> tuple[int, list[str], list[str]]:
    """Return ``(inspected, offender lines, unexamined lines)`` for the roots."""
    files, unexamined = _discover(roots)
    offenders: list[str] = []
    inspected = 0
    for path in files:
        try:
            found = find_offenders(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, ValueError) as exc:  # UnicodeDecodeError is a ValueError
            unexamined.append(f"UNEXAMINED {path}: {type(exc).__name__}: {exc}")
            continue
        inspected += 1
        offenders.extend(f"OFFENDER {path}:{line}: {where}" for line, where in found)
    return inspected, offenders, unexamined


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; exit non-zero on any offender, unexamined file or zero inspected."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", default=[], help="directory to scan")
    args = parser.parse_args(argv)
    roots = [Path(r) for r in args.root] or [REPO_ROOT / name for name in DEFAULT_ROOTS]
    inspected, offenders, unexamined = examine(roots)
    print("mode: static")
    print(f"inspected: {inspected}")
    for line in (*offenders, *unexamined):
        print(line)
    return 1 if (offenders or unexamined or inspected == 0) else 0


if __name__ == "__main__":
    sys.exit(main())
