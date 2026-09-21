"""
MODULE: build_referential_integrity_closure_resolvers
GOAL: Detect the three reference shapes AC BP-900g-8 requires the
    intra-package dependency closure to resolve a sibling MODULE through --
    static imports, the ``importlib.util.spec_from_file_location`` dynamic
    loader, and a ``sys.path`` push followed by a plain import.
BUSINESS CONTEXT: Split out of build_referential_integrity_closure.py (AC
    BP-100n-4, file-size refactor): that module itself exceeded its 400
    -counted-line cap once ClosureAnalysisError and every AST-analysis
    internal moved out of build_referential_integrity.py in the same AC's
    earlier step. This module holds the module-RESOLUTION detectors
    specifically (as opposed to the shared expression evaluator in
    build_referential_integrity_closure_eval.py, or the non-code data-file
    detectors that stayed in the hub module). Nothing in this module's
    behaviour, error handling, or message text changed as part of either
    move; see the DECISION HISTORY at the tail of
    build_referential_integrity_closure.py for the moved-vs-changed
    boundary.
ARCHITECTURE: ``_extract_static_import_candidates()`` handles shape 1
    (``import foo``, ``from foo import bar``, relative imports, and the
    ``importlib.import_module()``/``__import__()`` dynamic forms), via the
    ``_module_name_candidates()`` helper and ``_dynamic_import_module_name()``
    detector. ``_extract_dynamic_loader_paths()`` handles shape 2
    (``importlib.util.spec_from_file_location(name, path)`` with a
    statically-evaluable ``path``), via ``_is_spec_from_file_location_call()``.
    ``_extract_syspath_directories()`` handles shape 3
    (``sys.path.insert``/``append``/``extend``, or a ``sys.path[:0] = [...]``
    slice assignment, each recognised via its own helper), so a plain import
    that follows can resolve against the pushed directory rather than the
    script's own directory or the package root. All three reuse
    ``_eval_static_path`` (imported from the sibling ``_eval`` module) as the
    shared local-variable-aware expression evaluator, and all three log an
    unresolvable argument as a WARNING naming the file and line rather than
    silently dropping it -- per AC BP-900g-8's disclosure constraint.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

from build_referential_integrity_closure_eval import (
    _annotate_parents,
    _build_local_assignments,
    _enclosing_scope,
    _eval_static_path,
)

# Pinned to the ORIGINAL module's name, not __name__ (which would resolve to
# "build_referential_integrity_closure_resolvers" post-split) -- a test
# (test_bp_900g_8_unresolvable_syspath_push_logs_a_warning) asserts on the
# WARNING record via
# ``caplog.at_level(logging.WARNING, logger="build_referential_integrity")``.
# Moving the emitting code without moving the logger identity would silently
# stop that assertion from ever seeing the record: caplog filters by logger
# NAME, not by which module the call site happens to live in. This is
# exactly the kind of anchor the BP-100n-4 refactor was told to grep for and
# preserve character-for-character rather than let a mechanical split touch.
_log = logging.getLogger("build_referential_integrity")


def _is_spec_from_file_location_call(node: ast.Call) -> bool:
    """Return True when *node* calls ``importlib.util.spec_from_file_location``.

    Matches both the attribute form (``importlib.util.spec_from_file_location``)
    and the bare-name form (``spec_from_file_location`` after
    ``from importlib.util import spec_from_file_location``).
    """
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "spec_from_file_location":
        return True
    return bool(isinstance(func, ast.Name) and func.id == "spec_from_file_location")


def _extract_dynamic_loader_paths(tree: ast.AST, script: Path) -> list[Path]:
    """Return candidate paths from every resolvable ``spec_from_file_location`` call.

    Unresolvable calls (the ``location`` argument does not reduce via
    ``_eval_static_path``) are logged as a WARNING and skipped -- per AC
    BP-900g-8's constraint, an unknown must be surfaced for a human rather
    than silently treated as external.
    """
    _annotate_parents(tree)
    candidates: list[Path] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_spec_from_file_location_call(node):
            continue
        location_node: ast.AST | None = None
        if len(node.args) >= 2:
            location_node = node.args[1]
        else:
            for kw in node.keywords:
                if kw.arg == "location":
                    location_node = kw.value
                    break
        if location_node is None:
            continue
        # Resolve name indirection against this call's own enclosing
        # function/module scope, plus module-level fallback (see
        # _build_local_assignments) -- a same-named local variable in an
        # unrelated function must never be substituted in.
        scope = _enclosing_scope(node, tree)
        assignments = _build_local_assignments(scope, tree)
        resolved = _eval_static_path(location_node, script, assignments)
        if resolved is None:
            _log.warning(
                "compute_intra_package_closure: unresolvable dynamic loader "
                "reference in %s at line %s -- static analysis could not reduce "
                "the spec_from_file_location() location argument to a concrete "
                "path. A human should verify whether this reference is external "
                "or needs to be deployed (AC BP-900g-8).",
                script,
                getattr(node, "lineno", "?"),
            )
            continue
        candidates.extend(resolved)
    return candidates


def _is_syspath_expression(node: ast.AST) -> bool:
    """Return True when *node* is the ``sys.path`` attribute expression itself."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "path"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
    )


def _is_syspath_mutation_call(node: ast.Call) -> bool:
    """Return True when *node* mutates ``sys.path`` via insert/append/extend.

    Matches only the attribute form reached through a bare ``sys`` name.

    ``extend`` was added for KI-BP-021. It was previously absent, so
    ``sys.path.extend([...])`` produced no candidate directory and every plain
    import that depended on it was dropped -- and dropped SILENTLY, because the
    caller's ``continue`` fires before the disclosure warning, so the idiom was
    invisible at every log level.
    """
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr not in ("insert", "append", "extend"):
        return False
    return _is_syspath_expression(func.value)


def _syspath_pushed_path_nodes(node: ast.Call) -> list[ast.AST]:
    """Return the pushed-path argument nodes of a ``sys.path`` mutation call.

    ``append(path)`` takes the path as its sole positional argument;
    ``insert(index, path)`` as its second; ``extend(paths)`` takes a SEQUENCE
    rather than a path.

    That last distinction is why KI-BP-021 needs both halves of the fix.
    Widening ``_is_syspath_mutation_call`` alone would hand the extend call's
    ``ast.List`` to ``_eval_static_path``, which cannot reduce a list to a
    directory and returns None -- converting a silent drop into a spurious
    "unresolvable" warning rather than a resolution. A list literal is
    therefore unpacked into its elements here.

    A non-literal argument (``sys.path.extend(some_var)``) yields the single
    node unchanged, so it reaches the evaluator and, failing to reduce, is
    disclosed as a warning. That is the correct outcome: unknown, and said out
    loud.

    Returns:
        Zero or more nodes, each a candidate pushed-path expression. Empty when
        the call carries too few positional arguments to identify one.
    """
    func = node.func
    if not isinstance(func, ast.Attribute):
        # Unreachable in practice: callers only pass nodes that already
        # passed _is_syspath_mutation_call, which requires this shape.
        return []
    if func.attr == "extend":
        if not node.args:
            return []
        first = node.args[0]
        if isinstance(first, (ast.List, ast.Tuple)):
            return list(first.elts)
        return [first]
    if func.attr == "append":
        return [node.args[0]] if node.args else []
    return [node.args[1]] if len(node.args) >= 2 else []


def _syspath_slice_assignment_nodes(node: ast.Assign) -> list[ast.AST]:
    """Return pushed-path nodes from a ``sys.path[:0] = [...]`` slice assignment.

    KI-BP-021: this form is an ``ast.Assign`` whose target is an
    ``ast.Subscript``, never an ``ast.Call``. The walk loop filters to
    ``ast.Call`` before testing anything, so no amount of widening the
    call predicate can reach it -- it needs its own branch.

    Returns:
        The assigned sequence's elements, or a single-element list holding the
        assigned value when it is not a literal sequence (so it still reaches
        the evaluator and is disclosed if it cannot be reduced). Empty when
        this is not a ``sys.path`` slice assignment.
    """
    if not any(
        isinstance(t, ast.Subscript) and _is_syspath_expression(t.value)
        for t in node.targets
    ):
        return []
    value = node.value
    if isinstance(value, (ast.List, ast.Tuple)):
        return list(value.elts)
    return [value]


def _extract_syspath_directories(tree: ast.AST, script: Path) -> list[Path]:
    """Return candidate directories pushed onto ``sys.path`` by *script*.

    This is the third reference shape AC BP-900g-8 requires the closure to
    see, alongside static imports and the dynamic loader:
    ``sys.path.insert(0, <dir-expression>)`` followed by a plain
    ``import``/``from ... import`` statement that resolves against the
    pushed directory rather than the script's own directory or the package
    root. ``scripts/ac_store/epic_ac_phases.py`` is the live instance --
    ``goal_to_epic.py``'s ``run()`` was, until the 2026-09 decomposition moved
    the import to that sibling and the push to module scope; this function
    walks the whole tree, so either placement is seen:
    ``sys.path.insert(0, str(_sibling_dir))`` then
    ``from scan_ac_store import traverse_ac_tree`` -- neither
    ``scripts/scan_ac_store.py`` (script's own directory) nor
    ``scripts/scan_ac_store.py``/``scripts/scan_ac_store/__init__.py``
    (package root) exist, so without this function the plain import is
    resolved against zero candidates and the dependency is dropped with no
    log line at all.

    Reuses ``_eval_static_path`` (the same local-variable-aware evaluator the
    dynamic-loader path above uses) so a ``sys.path`` argument built through
    local-variable indirection, a ``str(...)`` wrapper, or a ternary over two
    statically-known branches is reduced the same way a
    ``spec_from_file_location`` argument would be.

    Per AC BP-900g-8's disclosure constraint, a pushed-path argument that does
    NOT reduce statically is logged as a WARNING naming the file and line --
    never silently dropped. This mirrors the treatment
    ``_extract_dynamic_loader_paths`` already gives an unresolvable dynamic
    loader call.

    The scope of that guarantee, stated precisely (KI-BP-021): it holds for a
    mutation this function RECOGNISES and cannot evaluate. It has never held
    for a mutation it does not recognise at all -- an unrecognised form is
    skipped before any logging runs, at every log level. The docstring
    previously claimed "no path through this module produces an unresolved
    intra-package reference with zero log output", which read as coverage this
    code did not have. The four recognised forms are now ``insert``,
    ``append``, ``extend``, and slice assignment; anything else is still
    silent, and that is the honest description.
    """
    _annotate_parents(tree)
    directories: list[Path] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_syspath_mutation_call(node):
            path_nodes = _syspath_pushed_path_nodes(node)
        elif isinstance(node, ast.Assign):
            path_nodes = _syspath_slice_assignment_nodes(node)
        else:
            continue
        for path_node in path_nodes:
            scope = _enclosing_scope(node, tree)
            assignments = _build_local_assignments(scope, tree)
            resolved = _eval_static_path(path_node, script, assignments)
            if resolved is None:
                _log.warning(
                    "compute_intra_package_closure: unresolvable sys.path "
                    "mutation in %s at line %s -- static analysis could not "
                    "reduce the pushed path argument to a concrete directory. "
                    "A human should verify whether an import that follows "
                    "resolves an intra-package module via this path "
                    "(AC BP-900g-8).",
                    script,
                    getattr(node, "lineno", "?"),
                )
                continue
            directories.extend(resolved)
    return directories


def _module_name_candidates(
    module_name: str,
    script_dir: Path,
    root: Path,
    extra_dirs: tuple[Path, ...] = (),
) -> list[Path]:
    """Return plausible file-path candidates for an absolute-import module name.

    Candidates are only kept if they later pass an ``is_file()`` check by the
    caller, so listing implausible candidates here is safe -- it never
    manufactures a false positive, it only risks missing a true one.

    *extra_dirs* adds one more candidate root per directory: any directory
    the same script statically pushes onto ``sys.path`` via
    ``_extract_syspath_directories`` before the import runs (AC BP-900g-8's
    third reference shape). Without this, an import resolved only through a
    ``sys.path.insert`` push -- e.g. ``scripts/goal_to_epic.py``'s
    ``from scan_ac_store import traverse_ac_tree`` after
    ``sys.path.insert(0, str(_sibling_dir))`` -- has no matching candidate
    (``scripts/scan_ac_store.py`` and the package-root forms both point at
    the wrong directory) and silently resolves to nothing.
    """
    parts = module_name.split(".")
    rel = Path(*parts)
    candidates = [root / f"{rel}.py", root / rel / "__init__.py"]
    if len(parts) == 1:
        # Bare same-directory import, e.g. `from test_enforcement import X`
        # inside scripts/ac_store/done_proof.py -- resolved relative to the
        # IMPORTING script's own directory, not the package root.
        candidates.insert(0, script_dir / f"{parts[0]}.py")
    for extra_dir in extra_dirs:
        candidates.append(extra_dir / f"{rel}.py")
        candidates.append(extra_dir / rel / "__init__.py")
    return candidates


def _extract_static_import_candidates(
    tree: ast.AST,
    script_dir: Path,
    root: Path,
    extra_dirs: tuple[Path, ...] = (),
) -> list[Path]:
    """Return file-path candidates for every ``import`` / ``from ... import`` statement.

    *extra_dirs* (directories the script statically pushes onto ``sys.path``,
    see ``_extract_syspath_directories``) is applied only to ABSOLUTE imports
    -- a relative import (``from . import foo``) is resolved purely from the
    script's own package location and is never affected by ``sys.path``.

    KI-BP-021 added two shapes this missed. ``importlib.import_module("x")``
    and ``__import__("x")`` are imports by any reasonable reading of the
    criterion, but matched neither this function (which tested only
    ``ast.Import``/``ast.ImportFrom``) nor the dynamic-loader lens (which
    matches only ``spec_from_file_location``), so they produced no candidate
    and no log line. And ``from . import sub`` offered only ``sub.py`` as a
    candidate, never ``sub/__init__.py`` -- so a relative import of a
    SUBPACKAGE resolved to nothing and was classified external by the
    resolve-or-it-is-third-party rule, which is right for a real third-party
    module and wrong for a subpackage shipping in this very tree.
    """
    candidates: list[Path] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                candidates.extend(
                    _module_name_candidates(alias.name, script_dir, root, extra_dirs)
                )
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                base = script_dir
                for _ in range(node.level - 1):
                    base = base.parent
                if node.module:
                    candidates.extend(_module_name_candidates(node.module, base, root))
                else:
                    for alias in node.names:
                        candidates.append(base / f"{alias.name}.py")
                        candidates.append(base / alias.name / "__init__.py")
            elif node.module:
                candidates.extend(
                    _module_name_candidates(node.module, script_dir, root, extra_dirs)
                )
        elif isinstance(node, ast.Call):
            name = _dynamic_import_module_name(node)
            if name is not None:
                candidates.extend(
                    _module_name_candidates(name, script_dir, root, extra_dirs)
                )
    return candidates


def _dynamic_import_module_name(node: ast.Call) -> str | None:
    """Return the module name of an ``importlib.import_module`` / ``__import__`` call.

    Only a literal string argument is resolved. A computed name
    (``import_module(f"pkg.{which}")``) is genuinely undecidable statically, so
    None is returned and the call contributes nothing -- the same treatment any
    other unresolvable reference gets.

    Args:
        node: A call node to inspect.

    Returns:
        The imported module name, or None when *node* is not one of these two
        calls or its argument is not a literal string.
    """
    func = node.func
    is_import_module = (
        isinstance(func, ast.Attribute) and func.attr == "import_module"
    ) or (isinstance(func, ast.Name) and func.id == "import_module")
    is_dunder_import = isinstance(func, ast.Name) and func.id == "__import__"
    if not (is_import_module or is_dunder_import):
        return None
    if not node.args:
        return None
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None
