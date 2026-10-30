"""
MODULE: scripts/build_orchestration/_wvr_scope.py
GOAL: What the wrong-version runner runs: the tests in scope, the wrong versions
    each one answers for, the alterations manifest, and "the fix undone".
BUSINESS CONTEXT: TQ-500g-1-i. Scope is declared: a covering test
    is in scope only when its own AC ``test_spec`` entry carries ``must_catch`` or
    ``angle: discrimination``. Requirement prose is never read. Each test answers
    for the wrong versions its OWN entry names; "the fix undone" is the code as it
    stood at the base ref, prepared from git and never by an agent.
ARCHITECTURE: Declared-name matching reuses
    ``_fl_red_baseline_support._load_declared_test_names`` and
    ``done_proof._nodeid_function_name``; covers tags come from done_proof's
    scanner. The alias constant :data:`ALIASES` is the one place the
    "revert the fix" spellings live (documented on the TQ-500g-5 reference page).
    A wrong version whose entries declare no ``in_scope_files`` takes the non-test files the
    work changed against the base ref (TQ-500g-1-x): :class:`DiffCache` is the one
    ``git diff --name-status`` shared by the fix undone and that derived scope.
    Manifest claim fields (``caught`` and the like) are never read: only ``name``,
    ``status``, ``reason`` and ``files`` are.
"""

from __future__ import annotations

import ast
import json
import logging
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath

from _fl_common import _nodeid_function_name
from _wvr_extras import ExtrasRead, attach_extras
from _wvr_pytest import NodeSpec
from _wvr_records import covers_tags, declared_names, load_records, requires_db_names

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
    files: list[str] = field(default_factory=list)
    extras: dict[str, str] = field(default_factory=dict)  # {key: name} the test writer left "to run later" (non-blocking)
    declared: list[dict] = field(default_factory=list)  # TQ-500g-1-xvii: [{ac_id, name, replacements}] this entry declares

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
    db_names: set[str] = field(default_factory=set)  # test_spec names declaring requires_db: true
    extras_read: ExtrasRead = field(default_factory=ExtrasRead)  # the to-run-later extras read, with notes on unusable ones


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


def _must_catch_by_name(records: dict[str, dict | None]) -> dict[str, list[str]]:
    """Collect the declared ``must_catch`` strings per test_spec entry name."""
    out: dict[str, list[str]] = {}
    for record in records.values():
        for entry in (record or {}).get("test_spec") or []:
            if isinstance(entry, dict) and entry.get("name"):
                names = [m for m in (entry.get("must_catch") or []) if isinstance(m, str) and m.strip()]
                out.setdefault(entry["name"], []).extend(names)
    return out


def _in_scope_by_name(records: dict[str, dict | None]) -> dict[str, list[str]]:
    """Collect the declared ``in_scope_files`` (TQ-500g-1-ix) per test_spec entry name."""
    out: dict[str, list[str]] = {}
    for record in records.values():
        for entry in (record or {}).get("test_spec") or []:
            if isinstance(entry, dict) and entry.get("name"):
                files = [f for f in (entry.get("in_scope_files") or []) if isinstance(f, str) and f.strip()]
                bucket = out.setdefault(entry["name"], [])
                bucket += [f for f in dict.fromkeys(files) if f not in bucket]
    return out


def _replacement_list(value: object) -> list[dict] | None:
    """The ``{path, old, new}`` list of a declaration, or ``None`` when it is not well formed (the validator refuses those)."""
    if not isinstance(value, list) or not value:
        return None
    keys = ("path", "old", "new")
    if not all(isinstance(r, dict) and all(isinstance(r.get(k), str) for k in keys) for r in value):
        return None
    return [{k: r[k] for k in keys} for r in value]


def _declared_by_entry(records: dict[str, dict | None]) -> dict[str, list[dict]]:
    """Collect ``declared_replacements`` (TQ-500g-1-xvii) per test_spec entry name, from the records already loaded.

    Only a key that the same entry's ``must_catch`` lists is read. Result items are
    ``{ac_id, name, replacements}``.
    """
    out: dict[str, list[dict]] = {}
    for ac_id, record in records.items():
        for entry in (record or {}).get("test_spec") or []:
            declared = entry.get("declared_replacements") if isinstance(entry, dict) and entry.get("name") else None
            if not isinstance(declared, dict):
                continue
            listed = [m for m in entry.get("must_catch") or [] if isinstance(m, str)]
            for name, repls in declared.items():
                clean = _replacement_list(repls)
                if name in listed and clean is not None:
                    out.setdefault(entry["name"], []).append({"ac_id": ac_id, "name": name, "replacements": clean})
    return out


def _scoped_test(tag: dict, must_catch: dict[str, list[str]], in_scope: dict[str, list[str]] | None = None,
                 declared: dict[str, list[dict]] | None = None) -> ScopedTest:
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
    files = list((in_scope or {}).get(function, []))
    return ScopedTest(node, f"{file.as_posix()}::{'::'.join(chains[0])}", function, list(must_catch.get(function, [])), files=files,
                      declared=list((declared or {}).get(function, [])))


def resolve_scope(ac_ids: list[str], test_root: Path, ac_root: Path) -> Scope:
    """Resolve the declared scope of the runs for *ac_ids*.

    Args:
        ac_ids: The requirement ids whose covering tests are held to wrong versions.
        test_root: Root directory scanned for ``# covers:`` tags.
        ac_root: Root of the AC store (``test_spec`` is the declaration).

    Returns:
        The :class:`Scope`; ``problem`` is set when a declared AC record is unavailable.
    """
    with ThreadPoolExecutor(1) as pool:  # the two reads are independent I/O: overlap them (TQ-500g-1-v)
        tags_future = pool.submit(covers_tags, test_root, ac_ids)
        records = load_records(ac_ids, ac_root)  # one pass over the store
        tags = tags_future.result()
    declared, unavailable = declared_names(records)
    if unavailable:
        return Scope(problem=f"declared_ac_record_unavailable: {', '.join(unavailable)}")
    wanted = set(ac_ids)
    must_catch = _must_catch_by_name(records)
    in_scope = _in_scope_by_name(records)
    declared_repls = _declared_by_entry(records)
    scope, seen, found = Scope(), set(), set()
    for tag in tags:
        if tag["ac_id"] not in wanted or not tag.get("function") or Path(tag["file"]).suffix != ".py":
            continue
        key = (Path(tag["file"]).resolve(), tag["function"])
        if key in seen:
            continue
        seen.add(key)
        found.add(_nodeid_function_name(f"{tag['file']}::{tag['function']}"))
        if _nodeid_function_name(f"{tag['file']}::{tag['function']}") in declared:
            scope.tests.append(_scoped_test(tag, must_catch, in_scope, declared_repls))
        else:
            scope.out_of_scope.append(f"{Path(tag['file']).as_posix()}::{tag['function']}")
    scope.missing = sorted(declared - found)
    scope.db_names = requires_db_names(records)
    scope.extras_read = attach_extras(scope.tests, test_root, ac_ids, wrong_version_key, wrong_version_key(UNDONE_NAME))
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


OUTSIDE = "outside the repository"
VCS_FOLDER = "inside the version-control folder"


def path_refusal(root: Path, raw: str) -> str | None:
    """Return why *raw* is not a repo-relative path inside *root* (``OUTSIDE``/``VCS_FOLDER``), else ``None``.

    Refuses a drive or anchor, a leading slash or backslash, ``..``, any ``.git`` component
    (case-insensitive) and anything whose resolved path leaves *root* (symlinks, junctions).
    """
    if not raw or raw[0] in "/\\":
        return OUTSIDE
    pure = PureWindowsPath(raw)
    if pure.drive or pure.anchor or ".." in pure.parts:
        return OUTSIDE
    if any(p.casefold() == ".git" for p in pure.parts):
        return VCS_FOLDER
    try:
        (root / pure.as_posix()).resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return OUTSIDE
    return None


def _safe_rel(root: Path, raw: str) -> str | None:
    """Return *raw* as a repo-relative POSIX path inside *root*, else ``None`` (see :func:`path_refusal`)."""
    return None if path_refusal(root, raw) else PureWindowsPath(raw).as_posix()


@dataclass
class OwedName:
    """One owed wrong version, the source files it may alter and where that scope came from."""

    name: str
    files: list[str] = field(default_factory=list)
    scope: str = "declared"
    extra: bool = False  # a to-run-later extra: owed, never blocking
    declared: list[dict] | None = None  # TQ-500g-1-xvii: the declared replacements, when exactly one declaration stands
    declared_by: list[dict] = field(default_factory=list)  # [{ac_id, entry}] that declare this name
    declared_error: str = ""  # set when declarations disagree: the name is unfinished


def declared_text(declared_by: list[dict]) -> str:
    """``<ac id>, entry <entry>`` for each declaring entry, joined with ``and`` (the wording of a declared row's reason)."""
    return " and ".join(f"{b['ac_id']}, entry {b['entry']}" for b in declared_by)


def _resolve_declarations(item: OwedName, found: list[dict]) -> None:
    """Set *item*'s declaration from every ``{ac_id, entry, replacements}`` in *found* (identical ones are one)."""
    for f in found:
        by = {"ac_id": f["ac_id"], "entry": f["entry"]}
        if by not in item.declared_by:
            item.declared_by.append(by)
    if len({json.dumps(f["replacements"], sort_keys=True) for f in found}) == 1:
        item.declared = found[0]["replacements"]
    else:
        item.declared_error = f"declared on {declared_text(item.declared_by)}: conflicting declarations for this name"


def owed_names(tests: list[ScopedTest], test_root_rel: str | None,
               derive: Callable[[], list[str]] | None = None) -> list[OwedName]:
    """List the owed wrong versions of *tests* with their per-name in-scope files (TQ-500g-1-ix, -x).

    Names come from the same ``ScopedTest.versions`` the runner holds the tests to, minus the
    aliases, each once (first spelling) in order. A name is ``declared`` when ANY entry naming it
    carries ``in_scope_files``; its files are then the union of those declarations in order of
    first declaration, minus every test file (nothing is derived, even when that leaves ``[]``).
    Any other name is ``derived``: its files are what *derive* returns, called at most once and
    only when some name needs it (``[]`` when *derive* is ``None``). *derive* raises
    :class:`ChangesError` when the work's changed files cannot be worked out.
    """
    owed: dict[str, OwedName] = {}
    declared: set[str] = set()
    declarations: dict[str, list[dict]] = {}
    for test in tests:
        for key, name in test.versions.items() if test.names else ():
            if key == wrong_version_key(UNDONE_NAME):
                continue
            item = owed.setdefault(key, OwedName(name))
            if test.files:
                declared.add(key)
            item.files += [f for f in dict.fromkeys(test.files) if f not in item.files and not is_test_path(f, test_root_rel)]
        for d in test.declared:
            if wrong_version_key(d["name"]) in owed:
                declarations.setdefault(wrong_version_key(d["name"]), []).append(
                    {"ac_id": d["ac_id"], "entry": test.function, "replacements": d["replacements"]})
    for key, found in declarations.items():
        _resolve_declarations(owed[key], found)
    for test in tests:
        for key, name in test.extras.items():
            owed.setdefault(key, OwedName(name, extra=True))
    shared: list[str] | None = None
    for key, item in owed.items():
        if key in declared:
            continue
        if shared is None:
            shared = derive() if derive is not None else []
        item.scope, item.files = "derived", list(shared)
    return list(owed.values())


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


class ChangesError(Exception):
    """The files the work changed cannot be worked out (the message names the base ref)."""


class DiffCache:
    """The one ``git diff --name-status`` of a run, read at most once and shared (TQ-500g-1-x).

    A failure is cached too, so every later reader sees the same error and git is not run again.
    """

    def __init__(self, root: Path, base_ref: str) -> None:
        self.root, self.base_ref = root, base_ref
        self._done = False
        self._value: list[tuple[str, str]] = []
        self._error: Exception | None = None

    def get(self) -> list[tuple[str, str]]:
        """Return ``[(status, path)]`` of the working tree against the base ref (``--no-renames``).

        Raises:
            OSError, UnicodeDecodeError, subprocess.TimeoutExpired: When git or the decoding fails.
        """
        if not self._done:
            self._done = True
            try:
                raw = _git_bytes(self.root, "diff", "--name-status", "-z", "--no-renames", self.base_ref, "--")
                tokens = raw.decode("utf-8").split("\0")
                self._value = list(zip(tokens[0::2], tokens[1::2]))
            except (OSError, UnicodeDecodeError, subprocess.TimeoutExpired) as exc:
                self._error = exc
        if self._error is not None:
            raise self._error
        return self._value


def _base_ref_check(root: Path, base_ref: str) -> None:
    """Raise :class:`ChangesError` naming *base_ref* when it does not resolve to a commit."""
    try:
        _git_bytes(root, "rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}")
    except OSError as exc:
        msg = f'the base ref "{base_ref}" does not exist, so the files the work changed cannot be worked out'
        raise ChangesError(msg) from exc


def changed_non_test_files(root: Path, diff: DiffCache, test_root_rel: str | None, ac_root_rel: str | None) -> list[str]:
    """Return the non-test files the work changed relative to ``diff.base_ref`` (the derived scope).

    The A and M paths of the shared diff plus the untracked files git does not ignore, minus test
    files, the AC store and refused paths; sorted, without duplicates. Other statuses are left out
    with a warning. Nothing is staged or written.

    Raises:
        ChangesError: When the base ref does not exist or git cannot list the changes.
    """
    ref = diff.base_ref
    _base_ref_check(root, ref)
    try:
        changes = diff.get()
        untracked = _git_bytes(root, "ls-files", "--others", "--exclude-standard", "-z").decode("utf-8").split("\0")
    except (OSError, UnicodeDecodeError, subprocess.TimeoutExpired) as exc:
        msg = f'the files changed since the base ref "{ref}" cannot be worked out: {exc}'
        raise ChangesError(msg) from exc
    found = {rel for status, rel in changes if status in ("A", "M")}
    for status, rel in changes:
        if status not in ("A", "M", "D"):
            _LOG.warning("the change of %s has status %s; it is not part of the derived scope", rel, status)
    found.update(rel for rel in untracked if rel)
    kept = sorted(r for r in found if not is_test_path(r, test_root_rel) and not _under(r, ac_root_rel) and not path_refusal(root, r))
    _LOG.debug("derived scope against %s: %s", ref, kept)
    return kept


def prepare_fix_undone(root: Path, base_ref: str, test_root_rel: str | None,
                       ac_root_rel: str | None = None, diff: DiffCache | None = None) -> tuple[dict[str, bytes], str, str]:
    """Prepare "the fix undone" from git: changed non-test files at their base content.

    A file the work created is left in place (deleting it would be an absence red).

    Args:
        root: The worktree root.
        base_ref: The ref the work began from.
        test_root_rel: The test root relative to *root*, or ``None``.
        ac_root_rel: The AC store relative to *root*, or ``None``; its files are not undone.
        diff: The run's shared :class:`DiffCache`, or ``None`` to read the diff here.

    Returns:
        ``(files, state, detail)``; *state* is ``ready``, ``not_applicable`` or ``error``.
    """
    try:
        files: dict[str, bytes] = {}
        created = 0
        for status, rel in (diff or DiffCache(root, base_ref)).get():
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


# DECISION HISTORY
# ================================================================================
# - 2026-10-30 12:00 [python-coder]: Reads test_spec declared_replacements beside must_catch/in_scope_files from the same records; OwedName carries declared, declared_by and declared_error (conflicting declarations). (#EPIC-OnceANamedWrongVersionIsPreparedAnd/08) (ADR-080)
