"""Find where production code calls the functions a test calls directly (the `production_callers` state).

Read-only on git: `git grep` at a fixed commit, never a checkout. A test that calls a function
nothing in production calls is the reachability failure the model cannot see from the test alone.

  targets = names called in the test (and its fixtures) that are defined in a code-under-test file
  callers = `git grep -w <name> <sha>` outside tests, docs and tickets, minus the definition line
"""

from __future__ import annotations

import ast
import logging
import re
import subprocess
from pathlib import PurePosixPath

log = logging.getLogger(__name__)

SEARCHED = ["*.py", "*.js", "*.mjs", "*.yml", "*.yaml", "*.sh", "*.toml", "*.cfg", "*.ini", "*.json"]
EXCLUDED_DIRS = {"tests", "unit_tests", "test", "docs", "tickets", "debugging", "node_modules"}
MAX_TARGETS = 5
MAX_SITES = 8


def _defined_functions(code_files: list[tuple[str, str]]) -> set[str]:
    names: set[str] = set()
    for name, text in code_files:
        if not name.endswith(".py"):
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            log.warning("cannot parse %s for definitions: %s", name, exc)
            continue
        names |= {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return names


def _called_names(sources: list[str]) -> list[str]:
    seen: list[str] = []
    for src in sources:
        try:
            tree = ast.parse(src)
        except SyntaxError:
            try:
                tree = ast.parse("if True:\n" + "\n".join("    " + ln for ln in src.splitlines()))
            except SyntaxError as exc:
                log.warning("cannot parse test source for calls: %s", exc)
                continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
                if name and name not in seen:
                    seen.append(name)
    return seen


def _is_excluded(path: str) -> bool:
    p = PurePosixPath(path)
    if any(part in EXCLUDED_DIRS for part in p.parts[:-1]):
        return True
    return p.name.startswith("test_") or p.name == "conftest.py" or p.name.endswith("_test.py")


def _grep(repo: str, sha: str, name: str) -> list[str]:
    cmd = ["git", "-C", repo, "grep", "-n", "-w", "-I", name, sha, "--", *SEARCHED]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("git grep failed for %s at %s: %s", name, sha, exc)
        raise
    if r.returncode not in (0, 1):  # 1 = no match
        log.warning("git grep exit %s for %s: %s", r.returncode, name, r.stderr.strip())
    return r.stdout.splitlines()


def _show(repo: str, sha: str, path: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", repo, "show", f"{sha}:{path}"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("git show %s:%s failed: %s", sha, path, exc)
        raise
    return r.stdout if r.returncode == 0 else None


def _python_call_lines(source: str, name: str) -> list[int]:
    """Line numbers of real calls to `name` (f() or x.f()); docstrings, comments and logs never count."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        log.warning("cannot parse caller file for %s: %s", name, exc)
        return []
    lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if (isinstance(f, ast.Name) and f.id == name) or (isinstance(f, ast.Attribute) and f.attr == name):
                lines.append(node.lineno)
    return sorted(set(lines))


def find_callers(repo: str, sha: str, test_sources: list[str], code_files: list[tuple[str, str]]) -> dict:
    """Return {function: [ "path:line: code", ... ] or a 'no call sites' note} for the test's direct targets."""
    defined = _defined_functions(code_files)
    targets = [n for n in _called_names(test_sources) if n in defined and not n.startswith("test")][:MAX_TARGETS]
    out: dict[str, list[str] | str] = {}
    for name in targets:
        sites: list[str] = []
        candidates: dict[str, list[tuple[str, str]]] = {}
        for line in _grep(repo, sha, name):
            _, _, rest = line.partition(":")          # drop "<sha>:"
            path, _, rest = rest.partition(":")
            lineno, _, text = rest.partition(":")
            if not _is_excluded(path):
                candidates.setdefault(path, []).append((lineno, text.strip()))
        for path, hits in candidates.items():
            if path.endswith(".py"):
                source = _show(repo, sha, path)
                if source is None:
                    continue
                src_lines = source.splitlines()
                sites += [f"{path}:{n}: {src_lines[n - 1].strip()[:160]}" for n in _python_call_lines(source, name)]
            else:  # JS / YAML / shell: a textual call, outside a comment
                sites += [f"{path}:{n}: {t[:160]}" for n, t in hits
                          if not t.startswith(("#", "//", "*")) and re.search(rf"\b{re.escape(name)}\s*\(", t)]
        out[name] = sites[:MAX_SITES] if sites else "no call sites outside tests, docs and tickets at this commit"
    return out
