"""
MODULE: scripts/ac_store/covers_tag_identity.py
GOAL: The ONE place a ``# covers:`` tag is matched to the test it sits on in a
    pytest run's ``{nodeid: outcome}`` results, at full identity (path within
    the test root + class + function name).
BUSINESS CONTEXT: TQ-500f-3-iii. The proof-of-done check (done_proof.py) and the
    red-baseline reader (fast_lane.py verify_red_baseline) both turn a covering
    tag into a pytest outcome. They used to match on (file basename, bare
    function name), so two tests sharing those collapsed onto one result and one
    test's outcome stood in for the other's. Both readers now call this module,
    so a given run and tag set can never be attributed differently by the two
    lanes. A tag that still cannot be tied to exactly one test is never guessed:
    ``resolve_tag`` reports every candidate and the readers refuse it.
ARCHITECTURE: Pure stdlib, no import of done_proof (done_proof and
    done_proof_kind_support import this module; the reverse would deadlock).
    The verdict for a tag is a pure function of the SET of results: nodeids are
    visited in sorted order, never in report order, and no first-wins or
    last-wins rule decides between two tests that share a name. The tagged
    test's class chain comes from an AST read of the tagged file, so a test
    defined once in a mixin and inherited (not overridden) by several collected
    classes resolves to every inheriting nodeid. Deployed beside done_proof.py
    (build_phases_ac_store deploy_map); importers: done_proof.py and
    build_orchestration/_fl_common.py (-> _fl_red_baseline_support.py).
    Named without a leading underscore: it lives in a different deployed
    directory than its build_orchestration importer (BP-900h-4 NAMING rule).
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path, PurePosixPath

# Prefix of the failing-entry text standing in for a tag that matches two or
# more distinct tests; done_proof's reason builder passes it through verbatim.
AMBIGUOUS_PREFIX = "ambiguous_test_identity: "

_FUNC_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


def _nodeid_function_name(nodeid: str) -> str:
    """Return the bare function name a pytest nodeid's final segment names.

    The ``[params]`` suffix is stripped FIRST (split on the first ``[``) so a
    parameter id containing ``::`` is never mistaken for the delimiter.

    Args:
        nodeid: A pytest nodeid, e.g. ``"path::test_widget[case1]"``.

    Returns:
        The bare function name, e.g. ``"test_widget"``.
    """
    return nodeid.split("[", 1)[0].rsplit("::", 1)[-1]


def _find_nodeids_for_test(func_name: str, file_basename: str, pytest_results: dict[str, str]) -> list[str]:
    """Return every nodeid of a function by name, same-file matches first (legacy name matcher).

    Kept for direct callers of the pre-TQ-500f-3-iii name-only matching;
    :func:`resolve_tag` is the full-identity matcher both readers use.

    Args:
        func_name: Python function name (e.g. ``"test_foo"``).
        file_basename: Basename of the test file (e.g. ``"test_foo.py"``).
        pytest_results: ``{nodeid: outcome}`` from a pytest run.

    Returns:
        All matching nodeids, same-file matches preferred as a group.
    """
    matches = [nodeid for nodeid in pytest_results if _nodeid_function_name(nodeid) == func_name]
    return [nodeid for nodeid in matches if file_basename in nodeid] or matches


def _find_nodeid_for_test(func_name: str, file_basename: str, pytest_results: dict[str, str]) -> str | None:
    """Return one nodeid for a function by name, first non-PASSED case winning (legacy name matcher).

    Args:
        func_name: Python function name (e.g. ``"test_foo"``).
        file_basename: Basename of the test file (e.g. ``"test_foo.py"``).
        pytest_results: ``{nodeid: outcome}`` from a pytest run.

    Returns:
        A matching nodeid string, or ``None`` if no match is found.
    """
    matches = _find_nodeids_for_test(func_name, file_basename, pytest_results)
    default = matches[0] if matches else None
    return next((nodeid for nodeid in matches if pytest_results[nodeid] != "PASSED"), default)


def _split_nodeid(nodeid: str) -> tuple[str, tuple[str, ...], str]:
    """Split a nodeid into ``(file path, class chain, function name)``, params dropped.

    Args:
        nodeid: A pytest nodeid, e.g. ``"a/test_x.py::TestA::test_y[1]"``.

    Returns:
        ``("a/test_x.py", ("TestA",), "test_y")``.
    """
    parts = nodeid.split("[", 1)[0].split("::")
    return parts[0], tuple(parts[1:-1]), parts[-1]


# Known limitation (review M-3): the class table is keyed by BARE class name, so two
# same-named classes in one file (e.g. nested) overwrite each other.
def _collect_defs(body: list, chain: tuple[str, ...], defs: list, classes: dict) -> None:
    """Walk module/class bodies recording every function def and every class.

    Args:
        body: AST statements of a module or class body.
        chain: Names of the classes enclosing *body*.
        defs: Output list of ``(class chain, name, first line, last line)``.
        classes: Output ``{class name: (base names, method names)}``.
    """
    for node in body:
        if isinstance(node, ast.ClassDef):
            bases = [b.id if isinstance(b, ast.Name) else b.attr for b in node.bases if isinstance(b, (ast.Name, ast.Attribute))]
            classes[node.name] = (bases, {n.name for n in node.body if isinstance(n, _FUNC_NODES)})
            _collect_defs(node.body, (*chain, node.name), defs, classes)
        elif isinstance(node, _FUNC_NODES):
            start = min([node.lineno, *(d.lineno for d in node.decorator_list)])
            defs.append((chain, node.name, start, node.end_lineno))


def _file_facts(path: Path) -> tuple[list, dict] | None:
    """Read the function defs and class table of a Python file, or ``None`` when unreadable.

    Args:
        path: The tagged test file.

    Returns:
        ``(defs, classes)`` as filled by :func:`_collect_defs`, else ``None``.
    """
    try:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError) as exc:
        print(f"WARNING: covers_tag_identity: cannot read {path}: {exc}", file=sys.stderr)
        return None
    defs: list = []
    classes: dict = {}
    _collect_defs(tree.body, (), defs, classes)
    return defs, classes


def _defining_chain(tag: dict, defs: list) -> tuple[str, ...] | None:
    """Return the class chain of the def the tag sits on, or ``None`` when unknown.

    One def of that name decides it; several (same name in two classes) are told
    apart by the tag's own line number (inside the def, else the next def below
    a tag written above it).

    Args:
        tag: Covers-tag dict with ``function`` and ``location`` (``file:line``).
        defs: Function defs from :func:`_file_facts`.

    Returns:
        The defining class chain (``()`` for a module-level function).
    """
    found = [d for d in defs if d[1] == tag["function"]]
    if len(found) < 2:
        return found[0][0] if found else None
    tail = str(tag.get("location", "")).rsplit(":", 1)[-1]
    line = int(tail) if tail.isdigit() else 0
    inside = [d for d in found if d[2] <= line <= d[3]]
    after = sorted((d for d in found if d[2] > line), key=lambda d: d[2])
    return (inside or after or found)[0][0]


def _first_definer(name: str, func: str, classes: dict) -> str | None:
    """Return the first class in *name*'s depth-first base order that defines *func*.

    Args:
        name: Class name of a collected test class.
        func: The test function name.
        classes: Class table from :func:`_file_facts`.

    Returns:
        The defining class name, or ``None`` when no class in the file defines it.
    """
    seen: set[str] = set()
    stack = [name]
    while stack:
        current = stack.pop()
        if current in seen or current not in classes:
            continue
        seen.add(current)
        if func in classes[current][1]:
            return current
        stack.extend(reversed(classes[current][0]))
    return None


def _inherits(chain: tuple[str, ...], defining: tuple[str, ...], func: str, classes: dict) -> bool:
    """Return whether a collected class chain runs the def at *defining* (own or inherited, not overridden).

    Args:
        chain: Class chain of a candidate nodeid.
        defining: Class chain of the tagged def.
        func: The test function name.
        classes: Class table from :func:`_file_facts`.

    Returns:
        True when *chain* is the defining chain or inherits *func* from its class.
    """
    if chain == defining:
        return True
    return bool(chain and defining) and _first_definer(chain[-1], func, classes) == defining[-1]


def _dotdot_same_file(parts: tuple[str, ...], tag_file: Path) -> bool | None:
    """Decide a ``..``-relative nodeid path by resolving it against the working directory.

    pytest spells a test outside its rootdir as ``../..``-prefixed. When the
    path resolved from the current directory is a real file it is decisive;
    otherwise the caller falls back to the suffix comparison (``..`` dropped).

    Args:
        parts: Components of the nodeid file path, containing ``..``.
        tag_file: Path of the tagged test file.

    Returns:
        True/False when the resolved path is a real file, else ``None``.
    """
    resolved = Path(os.path.normpath(Path.cwd().joinpath(*parts)))
    if not resolved.is_file():
        return None
    try:
        return resolved.samefile(Path(tag_file).absolute())
    except OSError:
        return None


def _same_file(nodeid_path: str, tag_file: Path) -> bool:
    """Return whether a nodeid's file path is the tagged file (pytest-rootdir or alias root).

    A nodeid path that is a component-wise suffix of the tag's path is that
    file. A path sharing at least two trailing components that is NOT a real
    file under any ancestor of the tag is the same file collected under another
    root (an alias). A basename-only coincidence between two real files never
    counts.

    Args:
        nodeid_path: File segment of a pytest nodeid.
        tag_file: Path of the tagged test file.

    Returns:
        True when both name the same test file.
    """
    parts = PurePosixPath(nodeid_path.replace("\\", "/")).parts
    if ".." in parts:
        decided = _dotdot_same_file(parts, tag_file)
        if decided is not None:
            return decided
        parts = tuple(p for p in parts if p != "..")
    theirs = tuple(os.path.normcase(p) for p in parts)
    ours = tuple(os.path.normcase(p) for p in PurePosixPath(Path(tag_file).as_posix()).parts)
    shared = 0
    for a, b in zip(reversed(theirs), reversed(ours)):
        if a != b:
            break
        shared += 1
    if shared == len(theirs):
        return True
    return shared >= 2 and not any((anc / nodeid_path).is_file() for anc in Path(tag_file).absolute().parents)


def _pool_verdict(pool: dict, chain_known: bool) -> tuple[list[list[str]], list[str]]:
    """Turn the surviving ``{(path, chain): [case nodeids]}`` units into ``(units, ambiguous)``.

    Ambiguous when one class chain appears under two paths, or when several
    units survive but the tag's own class could not be determined.

    Args:
        pool: ``{(file path, class chain): [case nodeids]}`` surviving the filters.
        chain_known: Whether the tagged def's class chain was determined.

    Returns:
        ``(units, ambiguous)`` exactly as :func:`resolve_tag` returns them.
    """
    chains = [chain for _path, chain in pool]
    if len(set(chains)) < len(chains) or (not chain_known and len(pool) > 1):
        return [], sorted({nid.split("[", 1)[0] for cases in pool.values() for nid in cases})
    return [sorted(pool[key]) for key in sorted(pool)], []


def resolve_tag(tag: dict, pytest_results: dict[str, str]) -> tuple[list[list[str]], list[str]]:
    """Resolve a covers tag to the test(s) it sits on, at full identity.

    Same-file tests (path within the test root + class + function name) win over
    name-only tests elsewhere; a UNIQUE name-only match is still allowed. A test
    defined once and inherited by several collected classes resolves to every
    inheriting class. Every parametrised case of a test is one unit.

    Args:
        tag: Covers-tag dict with ``file``, ``function``, ``location``.
        pytest_results: ``{nodeid: outcome}`` from a pytest run.

    Returns:
        ``(units, ambiguous)``. *units* is a list of per-test lists of case
        nodeids (empty when nothing matched). *ambiguous* lists every candidate
        test (params dropped) when the tag cannot be tied to exactly one
        definition; *units* is then empty and the caller must refuse the tag.
    """
    func = tag["function"]
    units: dict[tuple[str, tuple[str, ...]], list[str]] = {}
    for nodeid in sorted(pytest_results):
        path, chain, name = _split_nodeid(nodeid)
        if name == func:
            units.setdefault((path, chain), []).append(nodeid)
    same = {key: cases for key, cases in units.items() if _same_file(key[0], tag["file"])}
    facts = _file_facts(tag["file"]) if same else None
    defining = _defining_chain(tag, facts[0]) if facts else None
    if defining is None:
        return _pool_verdict(same or units, False)
    return _pool_verdict({k: v for k, v in same.items() if _inherits(k[1], defining, func, facts[1])}, True)


def aggregate_unit(cases: list[str], pytest_results: dict[str, str]) -> tuple[str, str]:
    """Return ``(nodeid, outcome)`` for one test: its first non-PASSED case, else its first case.

    Args:
        cases: Case nodeids of one test, from :func:`resolve_tag`.
        pytest_results: ``{nodeid: outcome}`` from a pytest run.

    Returns:
        The nodeid standing for the test and its outcome.
    """
    nodeid = next((n for n in cases if pytest_results[n] != "PASSED"), cases[0])
    return nodeid, pytest_results[nodeid]


def judge_tag(tag: dict, pytest_results: dict[str, str]) -> tuple[list[str], list[str]]:
    """Split one tag's test(s) into passing and non-passing nodeids (fail closed).

    A test passes only when every one of its parametrised cases PASSED; any
    other case makes the test non-passing. An unmatched tag is non-passing, and
    an ambiguous tag is non-passing with one entry naming the tag and every
    candidate test.

    Args:
        tag: Covers-tag dict with ``ac_id``, ``file``, ``function``, ``location``.
        pytest_results: ``{nodeid: outcome}`` from a pytest run.

    Returns:
        ``(passing_nodeids, failing_entries)``.
    """
    units, ambiguous = resolve_tag(tag, pytest_results)
    if ambiguous:
        return [], [f"{AMBIGUOUS_PREFIX}{tag['ac_id']} matches {', '.join(ambiguous)}"]
    if not units:
        return [], [f"{tag['file']}::{tag['function']}"]
    passing: list[str] = []
    failing: list[str] = []
    for cases in units:
        nodeid, outcome = aggregate_unit(cases, pytest_results)
        if outcome == "PASSED":
            passing.extend(cases)
        else:
            failing.append(nodeid)
    return passing, failing
