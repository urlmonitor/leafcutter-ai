"""
MODULE: scripts/build_orchestration/_wvr_scope.py
GOAL: What the wrong-version runner runs: the tests in scope, the wrong versions
    each one answers for, the alterations manifest, and "the fix undone".
BUSINESS CONTEXT: TQ-500g-1-i. Scope is declared, never inferred: a covering test
    is in scope only when its own AC ``test_spec`` entry carries ``must_catch`` or
    ``angle: discrimination``. Requirement prose is never read. Each test answers
    for the wrong versions its OWN entry names; "the fix undone" is the code as it
    stood at the base ref, prepared from git and never by an agent.
ARCHITECTURE: Declared-name matching reuses
    ``_fl_red_baseline_support._load_declared_test_names`` and
    ``done_proof._nodeid_function_name``; covers tags come from done_proof's
    scanner. The alias constant :data:`ALIASES` is the one place the
    "revert the fix" spellings live (documented on the TQ-500g-5 reference page).
    Manifest claim fields (``caught`` and the like) are never read: only ``name``,
    ``status``, ``reason`` and ``files`` are.
"""

from __future__ import annotations

import ast
import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath

from _fl_common import _load_ac_by_id, _nodeid_function_name, _scan_test_root_for_covers_tags
from _fl_red_baseline_support import _load_declared_test_names
from _wvr_pytest import NodeSpec

_LOG = logging.getLogger("wrong_version_runner")
UNDONE_NAME = "the fix undone"
ALIASES = frozenset({"revert the fix", "the fix undone"})
_TEST_DIR_NAMES = frozenset({"tests", "unit_tests", "test", "__tests__"})


def norm_name(name: str) -> str:
    """Trim and case-fold a wrong-version name for matching."""
    return name.strip().casefold()


def wrong_version_key(name: str) -> str:
    """Return the matching key of *name*; every alias spelling shares one key."""
    key = norm_name(name)
    return norm_name(UNDONE_NAME) if key in ALIASES else key


@dataclass
class ScopedTest:
    """One in-scope covering test and the wrong versions its entry names."""

    node: NodeSpec | None
    label: str
    function: str
    names: list[str] = field(default_factory=list)
    issue: str = ""

    @property
    def versions(self) -> dict[str, str]:
        """``{key: display name}`` the test answers for (undone when it names none)."""
        if not self.names:
            return {wrong_version_key(UNDONE_NAME): UNDONE_NAME}
        return {wrong_version_key(n): (UNDONE_NAME if norm_name(n) in ALIASES else n) for n in self.names}


@dataclass
class Scope:
    """The resolved scope of one run."""

    tests: list[ScopedTest] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    problem: str = ""


def _chains(file: Path, function: str) -> list[tuple[str, ...]]:
    """Return the class chains under which *function* is defined in *file*."""
    tree = ast.parse(file.read_text(encoding="utf-8"))
    found: list[tuple[str, ...]] = []

    def walk(node: ast.AST, prefix: tuple[str, ...]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                walk(child, (*prefix, child.name))
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == function:
                found.append((*prefix, function))

    walk(tree, ())
    return found


def _must_catch_by_name(ac_ids: list[str], ac_root: Path) -> dict[str, list[str]]:
    """Collect the declared ``must_catch`` strings per test_spec entry name."""
    out: dict[str, list[str]] = {}
    for ac_id in ac_ids:
        record = _load_ac_by_id(ac_root, ac_id) or {}
        for entry in record.get("test_spec") or []:
            if isinstance(entry, dict) and entry.get("name"):
                names = [m for m in (entry.get("must_catch") or []) if isinstance(m, str) and m.strip()]
                out.setdefault(entry["name"], []).extend(names)
    return out


def _scoped_test(tag: dict, must_catch: dict[str, list[str]]) -> ScopedTest:
    """Build one :class:`ScopedTest`, resolving the node id from the test's source."""
    file, function = Path(tag["file"]), tag["function"]
    label = f"{file.as_posix()}::{function}"
    try:
        chains = _chains(file, function)
    except (OSError, SyntaxError, ValueError) as exc:
        return ScopedTest(None, label, function, issue=f"the test file cannot be read: {exc}")
    if len(chains) != 1:
        return ScopedTest(None, label, function, issue=f"{function} resolves to {len(chains)} tests, not one")
    node = NodeSpec(file, chains[0])
    return ScopedTest(node, f"{file.as_posix()}::{'::'.join(chains[0])}", function, list(must_catch.get(function, [])))


def resolve_scope(ac_ids: list[str], test_root: Path, ac_root: Path) -> Scope:
    """Resolve the declared scope of the runs for *ac_ids*.

    Args:
        ac_ids: The requirement ids whose covering tests are held to wrong versions.
        test_root: Root directory scanned for ``# covers:`` tags.
        ac_root: Root of the AC store (``test_spec`` is the declaration).

    Returns:
        The :class:`Scope`; ``problem`` is set when a declared AC record is unavailable.
    """
    declared, unavailable = _load_declared_test_names(ac_ids, ac_root)
    if unavailable:
        return Scope(problem=f"declared_ac_record_unavailable: {', '.join(unavailable)}")
    wanted = set(ac_ids)
    must_catch = _must_catch_by_name(ac_ids, ac_root)
    scope, seen, found = Scope(), set(), set()
    for tag in _scan_test_root_for_covers_tags(test_root):
        if tag["ac_id"] not in wanted or not tag.get("function") or Path(tag["file"]).suffix != ".py":
            continue
        key = (Path(tag["file"]).resolve(), tag["function"])
        if key in seen:
            continue
        seen.add(key)
        found.add(_nodeid_function_name(f"{tag['file']}::{tag['function']}"))
        if _nodeid_function_name(f"{tag['file']}::{tag['function']}") in declared:
            scope.tests.append(_scoped_test(tag, must_catch))
        else:
            scope.out_of_scope.append(f"{Path(tag['file']).as_posix()}::{tag['function']}")
    scope.missing = sorted(declared - found)
    return scope


def load_manifest(path: str | None) -> tuple[dict[str, dict], str]:
    """Read the alterations manifest into ``{wrong-version key: entry}``.

    Args:
        path: The manifest path, or ``None``/empty when none was given.

    Returns:
        ``(entries, problem)``; *problem* is non-empty when the manifest is unreadable
        (the named wrong versions then count as not prepared, never as passed).
    """
    if not path:
        return {}, ""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return {wrong_version_key(e["name"]): e for e in data["entries"] if isinstance(e.get("name"), str)}, ""
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        _LOG.warning("alterations manifest %s is unreadable: %s", path, exc)
        return {}, f"the alterations manifest is unreadable: {exc}"


def is_test_path(rel: str, test_root_rel: str | None) -> bool:
    """Return whether *rel* (repo-relative POSIX) is a test file no wrong version may touch.

    Compared case-insensitively, because the worktree may sit on a case-insensitive filesystem.
    """
    folded = rel.casefold()
    parts = folded.split("/")
    name = parts[-1]
    if test_root_rel:
        prefix = test_root_rel.casefold().rstrip("/")
        if folded == prefix or folded.startswith(prefix + "/"):
            return True
    return (
        bool(_TEST_DIR_NAMES.intersection(parts[:-1]))
        or name.startswith("test_")
        or name.endswith(("_test.py", ".test.ts", ".test.tsx", ".spec.ts"))
        or name == "conftest.py"
    )


def _safe_rel(root: Path, raw: str) -> str | None:
    """Return *raw* as a repo-relative POSIX path inside *root*, else ``None``.

    Rejects a drive or anchor, a leading slash or backslash, ``..``, any ``.git`` component
    (case-insensitive) and anything whose resolved path leaves *root* (symlinks, junctions).
    """
    if not raw or raw[0] in "/\\":
        return None
    pure = PureWindowsPath(raw)
    if pure.drive or pure.anchor or ".." in pure.parts or any(p.casefold() == ".git" for p in pure.parts):
        return None
    try:
        (root / pure.as_posix()).resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return None
    return pure.as_posix()


def build_alterations(entry: dict, root: Path, test_root_rel: str | None) -> tuple[dict[str, bytes], str]:
    """Turn a prepared manifest entry into ``{relative path: altered bytes}``.

    Args:
        entry: One manifest entry.
        root: The worktree root.
        test_root_rel: The test root relative to *root*, or ``None``.

    Returns:
        ``(files, problem)``; *problem* is non-empty when the entry cannot be applied.
    """
    if entry.get("status") != "prepared":
        reason = entry.get("reason") or "no reason given"
        return {}, f"wrong version could not be prepared: {reason}"
    files: dict[str, bytes] = {}
    for item in entry.get("files") or []:
        rel = _safe_rel(root, str(item.get("path", ""))) if isinstance(item, dict) else None
        if rel is None:
            return {}, "the manifest names a path outside the repository"
        if is_test_path(rel, test_root_rel):
            return {}, f"the alteration would change a test file: {rel}"
        if not (root / rel).is_file():
            return {}, f"the altered file does not exist as written: {rel}"
        try:
            files[rel] = Path(str(item.get("altered_copy", ""))).read_bytes()
        except OSError as exc:
            return {}, f"the altered copy of {rel} cannot be read: {exc}"
    return (files, "") if files else ({}, "the manifest entry names no file")


def _under(rel: str, prefix: str | None) -> bool:
    """Return whether *rel* is *prefix* or below it (case-insensitive)."""
    if not prefix:
        return False
    folded, base = rel.casefold(), prefix.casefold().rstrip("/")
    return folded == base or folded.startswith(base + "/")


def _git_bytes(root: Path, *args: str) -> bytes:
    """Run git in *root* and return raw stdout bytes (raises ``OSError`` on failure)."""
    try:
        proc = subprocess.run(["git", *args], cwd=root, capture_output=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        msg = f"git {' '.join(args)} could not run: {exc}"
        raise OSError(msg) from exc
    if proc.returncode != 0:
        msg = f"git {' '.join(args)} failed: {proc.stderr.decode('utf-8', 'replace').strip()[:300]}"
        raise OSError(msg)
    return proc.stdout


def prepare_fix_undone(root: Path, base_ref: str, test_root_rel: str | None,
                       ac_root_rel: str | None = None) -> tuple[dict[str, bytes], str, str]:
    """Prepare "the fix undone" from git: changed non-test files at their base content.

    A file the work created is left in place (deleting it would be an absence red).

    Args:
        root: The worktree root.
        base_ref: The ref the work began from.
        test_root_rel: The test root relative to *root*, or ``None``.
        ac_root_rel: The AC store relative to *root*, or ``None``; its files are not undone.

    Returns:
        ``(files, state, detail)``; *state* is ``ready``, ``not_applicable`` or ``error``.
    """
    try:
        tokens = _git_bytes(root, "diff", "--name-status", "-z", "--no-renames", base_ref, "--").decode("utf-8").split("\0")
        files: dict[str, bytes] = {}
        created = 0
        for status, rel in zip(tokens[0::2], tokens[1::2]):
            if is_test_path(rel, test_root_rel) or _under(rel, ac_root_rel):
                continue
            if status == "A":
                created += 1
            elif status in ("M", "D"):
                files[rel] = _git_bytes(root, "show", f"{base_ref}:{rel}")
            else:
                return {}, "error", f"the change of {rel} has status {status}, which cannot be undone"
    except (OSError, UnicodeDecodeError, subprocess.TimeoutExpired) as exc:
        return {}, "error", f"the fix undone could not be prepared from git: {exc}"
    if not files:
        return {}, "not_applicable", f"every changed non-test file is new ({created} created); the fix undone does not apply"
    return files, "ready", ""
