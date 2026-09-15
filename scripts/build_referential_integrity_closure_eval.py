"""
MODULE: build_referential_integrity_closure_eval
GOAL: Shared local-scope AST helpers and the ``_eval_static_path`` expression
    evaluator that every intra-package-closure detector reduces a
    ``Path(__file__)``-rooted (or otherwise statically-resolvable) expression
    through.
BUSINESS CONTEXT: Split out of build_referential_integrity_closure.py (AC
    BP-100n-4, file-size refactor): that module itself exceeded its 400
    -counted-line cap once ClosureAnalysisError and every AST-analysis
    internal moved out of build_referential_integrity.py in the same AC's
    earlier step. Rather than re-merging everything into one oversized file,
    the expression-evaluator family -- cohesive on its own, and the part
    that carried the original complexity-reduction refactor -- lives here.
    Nothing in this module's behaviour, error handling, or message text
    changed as part of either move; see the DECISION HISTORY at the tail of
    build_referential_integrity_closure.py for the moved-vs-changed
    boundary.
ARCHITECTURE: ``_eval_static_path()`` is a thin dispatcher (AC BP-100n-4
    complexity refactor) over the ``_STATIC_PATH_HANDLERS`` family -- one
    small function per recognised AST node shape (``ast.IfExp``,
    ``ast.BoolOp`` with ``or``, ``ast.Name``, ``ast.BinOp`` with ``/``,
    ``ast.Attribute`` ``.parent``, and ``ast.Call``, itself dispatched
    further via ``_CALL_PATH_HANDLERS`` into four call-shape sub-handlers).
    The shapes are mutually exclusive by AST node type, so exactly one
    handler's ``isinstance`` guard can pass for a given node -- trying them
    all in order and returning the first non-``None`` result is
    behaviourally identical to what used to be one function's sequence of
    ``if isinstance(node, ...): ...`` blocks. This is what let
    build_referential_integrity.py (and, transitively, this module's own
    predecessor) register the check-complexity gate without
    ``_eval_static_path`` itself blocking it.

    ``_iter_same_scope()``, ``_annotate_parents()``, ``_enclosing_scope()``,
    and ``_build_local_assignments()`` are the scope-aware local-variable
    -indirection support ``_eval_static_path`` (and every detector built on
    it, in the sibling ``_resolvers`` and hub modules) needs to resolve a
    reference built through one level of ``name = <expr>`` assignment before
    being passed to a call site -- e.g. ``sibling = Path(__file__).parent /
    "x.py"`` followed by a call that passes the bare name ``sibling``.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path


def _iter_same_scope(node: ast.AST) -> ast.AST:
    """Yield *node* and its descendants, without crossing into a nested function/class.

    Used to collect a scope's OWN local assignments without leaking in (or
    being shadowed by) a same-named local variable in a sibling function --
    e.g. ``generate_ticket_from_ac.py`` has TWO unrelated functions that each
    assign a local variable named ``sibling`` for their own, different,
    sibling-module load. A flat whole-module scan would let the later
    function's assignment silently overwrite the earlier one in a shared dict,
    corrupting resolution for the first call site.
    """
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield from _iter_same_scope(child)


def _annotate_parents(tree: ast.AST) -> None:
    """Attach a ``_closure_parent`` back-reference to every node in *tree*."""
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child._closure_parent = node  # noqa: SLF001


def _enclosing_scope(node: ast.AST, tree: ast.AST) -> ast.AST:
    """Return the nearest enclosing Module/FunctionDef/AsyncFunctionDef for *node*.

    Requires ``_annotate_parents(tree)`` to have been called first. Falls back
    to *tree* (the module) when no parent chain is available.
    """
    current = getattr(node, "_closure_parent", None)
    while current is not None and not isinstance(
        current, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef)
    ):
        current = getattr(current, "_closure_parent", None)
    return current if current is not None else tree


def _build_local_assignments(
    scope: ast.AST, tree: ast.AST | None = None
) -> dict[str, ast.AST]:
    """Map every simple ``name = <expr>`` assignment DIRECTLY within *scope* to its value.

    "Directly within" means: found by ``_iter_same_scope(scope)``, so a nested
    function or class body defined inside *scope* does not contribute (and
    cannot shadow) an entry here -- each call site is resolved against only
    its own enclosing function's (or the module's top-level) assignments.

    The real-world pattern this closure computation must see (e.g.
    ``generate_ticket_from_ac.py``'s ``_load_migration_map``) never inlines the
    ``Path(__file__)...`` expression directly as the ``spec_from_file_location``
    argument -- it assigns it to a local variable first (``sibling = ...``) a
    few lines earlier and passes the variable. Without resolving that
    indirection, every real dynamic-loader reference in this codebase would be
    misclassified as unresolvable.

    When *tree* is supplied and *scope* is a function (not the module itself),
    the function's own assignments are overlaid ON TOP OF the module's
    top-level assignments -- mirroring Python's own local-then-global name
    resolution. This is required for a pattern like ``goal_to_epic.py``'s
    ``run()``: it pushes ``sys.path.insert(0, str(_sibling_dir))`` where
    ``_sibling_dir`` is assigned at MODULE level, not inside ``run()`` itself.
    Without the module-level fallback, that name would never resolve from
    inside the function scope and the reference would be misclassified as
    unresolvable. A same-named LOCAL assignment always wins over the
    module-level one, so this cannot reintroduce the cross-function shadowing
    bug ``_iter_same_scope`` guards against -- only true module globals are
    merged in, never another function's locals.
    """
    assignments: dict[str, ast.AST] = {}
    if tree is not None and scope is not tree:
        assignments.update(_build_local_assignments(tree))
    for node in _iter_same_scope(scope):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.value
        # KI-BP-021: an ANNOTATED assignment (``_dir: Path = ...``) is an
        # ast.AnnAssign, a different node type that this loop used to skip
        # entirely -- so the name never entered the map and every reference
        # through it was reported unresolvable. In a codebase that annotates
        # as heavily as this one, that is the form most likely to appear.
        # ``value`` is None for a bare declaration (``_dir: Path``), which
        # binds no value and must not enter the map.
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if isinstance(node.target, ast.Name):
                assignments[node.target.id] = node.value
    return assignments


def _eval_ifexp_path(
    node: ast.AST,
    script: Path,
    assignments: dict[str, ast.AST],
    _seen: frozenset[str],
) -> list[Path] | None:
    """Reduce an ``if``/``else`` ternary (``ast.IfExp``) to its combined candidates.

    Extracted from ``_eval_static_path`` (see that function's docstring for
    the full picture). Returns candidates from BOTH branches -- e.g.
    ``goal_to_epic.py``'s dual source/deployed-layout guard
    (``_sibling_dir = _scripts_dir if <cond> else _scripts_dir / "ac_store"``)
    -- since a runtime condition decides which branch actually applies, and
    accepting both (letting the caller's existence check discard whichever
    one is not real) is the safer reading than guessing or discarding the
    reference outright.
    """
    if not isinstance(node, ast.IfExp):
        return None
    body_paths = _eval_static_path(node.body, script, assignments, _seen)
    orelse_paths = _eval_static_path(node.orelse, script, assignments, _seen)
    if body_paths is None or orelse_paths is None:
        return None
    return body_paths + orelse_paths


def _eval_or_boolop_path(
    node: ast.AST,
    script: Path,
    assignments: dict[str, ast.AST],
    _seen: frozenset[str],
) -> list[Path] | None:
    """Reduce a ``package_root or _PACKAGE_ROOT``-shaped ``or`` fallback expression.

    Extracted from ``_eval_static_path`` (AC BP-900g-8-ii). Unlike ``IfExp``
    above, a runtime-only branch (a bare function parameter with no default
    here) must NOT poison the whole expression -- at runtime exactly one
    operand wins, and the module-level fallback operand is the one most
    commonly reachable statically. Every operand that DOES resolve
    contributes its candidates; an operand that does not (e.g. an unassigned
    parameter) is skipped rather than treated as a hard failure the way
    IfExp's two required branches are.
    """
    if not (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or)):
        return None
    resolved: list[Path] = []
    for value in node.values:
        candidate = _eval_static_path(value, script, assignments, _seen)
        if candidate is not None:
            resolved.extend(candidate)
    return resolved or None


def _eval_name_path(
    node: ast.AST,
    script: Path,
    assignments: dict[str, ast.AST],
    _seen: frozenset[str],
) -> list[Path] | None:
    """Resolve a bare ``ast.Name`` through one level of local-variable indirection.

    Extracted from ``_eval_static_path``.
    """
    if not isinstance(node, ast.Name):
        return None
    if node.id == "__file__" or node.id in _seen or node.id not in assignments:
        return None
    return _eval_static_path(
        assignments[node.id], script, assignments, _seen | {node.id}
    )


def _eval_binop_div_path(
    node: ast.AST,
    script: Path,
    assignments: dict[str, ast.AST],
    _seen: frozenset[str],
) -> list[Path] | None:
    """Reduce a ``/`` (division) expression against a literal or resolvable right side.

    Extracted from ``_eval_static_path``.
    """
    if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
        return None
    left = _eval_static_path(node.left, script, assignments, _seen)
    if left is None:
        return None
    if isinstance(node.right, ast.Constant) and isinstance(node.right.value, str):
        return [path / node.right.value for path in left]
    # AC BP-900g-8-ii: the right operand may itself be a statically
    # resolvable path FRAGMENT rather than a bare string literal -- e.g.
    # ``validate_ac_schema.py``'s ``repo_root / _SCHEMA_REL`` where
    # ``_SCHEMA_REL = Path("config") / "ac_store_schema.json"`` is a
    # module-level RELATIVE path built the same way. Resolving the right
    # side through the same evaluator (rather than requiring a bare
    # Constant) lets one level of this "build a relative fragment, then
    # anchor it later" indirection resolve without a special case per shape.
    right = _eval_static_path(node.right, script, assignments, _seen)
    if right is not None:
        return [lp / rp for lp in left for rp in right]
    return None


def _eval_parent_attr_path(
    node: ast.AST,
    script: Path,
    assignments: dict[str, ast.AST],
    _seen: frozenset[str],
) -> list[Path] | None:
    """Reduce a ``.parent`` attribute access against its already-resolved base.

    Extracted from ``_eval_static_path``.
    """
    if not (isinstance(node, ast.Attribute) and node.attr == "parent"):
        return None
    base = _eval_static_path(node.value, script, assignments, _seen)
    return None if base is None else [path.parent for path in base]


def _eval_call_resolve_path(
    node: ast.AST,
    script: Path,
    assignments: dict[str, ast.AST],
    _seen: frozenset[str],
) -> list[Path] | None:
    """Unwrap a ``.resolve()`` call as a no-op around its receiver expression.

    One of four mutually-exclusive ``ast.Call`` shapes ``_eval_call_path``
    dispatches to; extracted from ``_eval_static_path``.
    """
    if isinstance(node.func, ast.Attribute) and node.func.attr == "resolve":
        return _eval_static_path(node.func.value, script, assignments, _seen)
    return None


def _eval_call_str_path(
    node: ast.AST,
    script: Path,
    assignments: dict[str, ast.AST],
    _seen: frozenset[str],
) -> list[Path] | None:
    """Unwrap a bare ``str(...)`` call around a resolvable path expression.

    One of four mutually-exclusive ``ast.Call`` shapes ``_eval_call_path``
    dispatches to; extracted from ``_eval_static_path``.
    """
    if (
        isinstance(node.func, ast.Name)
        and node.func.id == "str"
        and len(node.args) == 1
    ):
        return _eval_static_path(node.args[0], script, assignments, _seen)
    return None


def _eval_call_path_from_file(
    node: ast.AST,
    script: Path,
    assignments: dict[str, ast.AST],
    _seen: frozenset[str],
) -> list[Path] | None:
    """Recognise the ``Path(__file__)`` seed expression.

    One of four mutually-exclusive ``ast.Call`` shapes ``_eval_call_path``
    dispatches to; extracted from ``_eval_static_path``.
    """
    if (
        isinstance(node.func, ast.Name)
        and node.func.id == "Path"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "__file__"
    ):
        return [script]
    return None


def _eval_call_path_literal(
    node: ast.AST,
    script: Path,
    assignments: dict[str, ast.AST],
    _seen: frozenset[str],
) -> list[Path] | None:
    """Recognise a bare ``Path("<literal>")`` seed.

    One of four mutually-exclusive ``ast.Call`` shapes ``_eval_call_path``
    dispatches to; extracted from ``_eval_static_path``.

    AC BP-900g-8-ii: a bare ``Path("<literal>")`` seed -- e.g.
    ``validate_ac_schema.py``'s ``_SCHEMA_REL = Path("config") / ...``. This
    produces a RELATIVE path fragment (never anchored at *script*),
    meaningful only when later combined via ``/`` with something that IS
    anchored (handled by ``_eval_binop_div_path``).
    """
    if (
        isinstance(node.func, ast.Name)
        and node.func.id == "Path"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ):
        return [Path(node.args[0].value)]
    return None


_CALL_PATH_HANDLERS: tuple[
    Callable[[ast.AST, Path, dict[str, ast.AST], frozenset[str]], list[Path] | None], ...
] = (
    _eval_call_resolve_path,
    _eval_call_str_path,
    _eval_call_path_from_file,
    _eval_call_path_literal,
)


def _eval_call_path(
    node: ast.AST,
    script: Path,
    assignments: dict[str, ast.AST],
    _seen: frozenset[str],
) -> list[Path] | None:
    """Reduce an ``ast.Call`` node via each recognised call-shape handler in turn.

    Extracted from ``_eval_static_path``. The four call shapes in
    ``_CALL_PATH_HANDLERS`` are mutually exclusive (``.resolve()`` requires
    an ``Attribute`` func; ``str(...)``/``Path(...)`` require a ``Name`` func
    further discriminated by ``.id`` and argument shape), so trying each in
    turn and returning the first non-``None`` result is equivalent to the
    original single ``if isinstance(node, ast.Call):`` block with four inner
    ``if`` returns.
    """
    if not isinstance(node, ast.Call):
        return None
    for handler in _CALL_PATH_HANDLERS:
        result = handler(node, script, assignments, _seen)
        if result is not None:
            return result
    return None


_STATIC_PATH_HANDLERS: tuple[
    Callable[[ast.AST, Path, dict[str, ast.AST], frozenset[str]], list[Path] | None], ...
] = (
    _eval_ifexp_path,
    _eval_or_boolop_path,
    _eval_name_path,
    _eval_binop_div_path,
    _eval_parent_attr_path,
    _eval_call_path,
)


def _eval_static_path(
    node: ast.AST,
    script: Path,
    assignments: dict[str, ast.AST],
    _seen: frozenset[str] = frozenset(),
) -> list[Path] | None:
    """Reduce a ``Path(__file__)``-rooted expression to concrete Path(s), if possible.

    Recognises the shape used by this codebase's sibling-module loaders:
    ``Path(__file__)``, any number of chained ``.resolve()`` calls (no-ops for
    this purpose) and ``.parent`` attribute accesses, combined with ``/``
    (division) against string-literal path segments -- e.g.
    ``Path(__file__).resolve().parent / "sibling.py"`` -- and resolves through
    one level of local-variable indirection at each step via *assignments*
    (e.g. ``sibling = Path(__file__).resolve().parent / "x.py"`` followed by
    a call site that passes the bare name ``sibling``). Also unwraps a bare
    ``str(...)`` call around the expression (e.g. ``str(_sibling_dir)`` in a
    ``sys.path.insert(0, str(_sibling_dir))`` call) since the string
    conversion does not change which directory is meant.

    Returns a LIST because one shape -- an ``if``/``else`` ternary
    (``ast.IfExp``) over two statically-known branches, e.g.
    ``goal_to_epic.py``'s dual source/deployed-layout guard
    (``_sibling_dir = _scripts_dir if <cond> else _scripts_dir / "ac_store"``)
    -- cannot be reduced to a single path without evaluating a runtime
    condition. Accepting candidates from BOTH branches (and letting the
    caller's existence check discard whichever one is not real) is the safer
    reading than guessing or discarding the reference outright. Every other
    recognised shape returns a single-element list.

    This function is a thin dispatcher (AC BP-100n-4 complexity refactor):
    each recognised node shape is handled by its own module-level function
    in ``_STATIC_PATH_HANDLERS``, tried in order. The shapes are mutually
    exclusive by AST node type, so exactly one handler's ``isinstance`` guard
    can pass for a given *node* -- trying them all and returning the first
    non-``None`` result is behaviourally identical to the original single
    function's sequence of ``if isinstance(node, ...): ...`` blocks.

    Args:
        node: The AST expression node to reduce.
        script: Absolute path to the script being analysed (the value that
            ``Path(__file__)`` evaluates to inside that script).
        assignments: Map of local variable name to its assigned expression,
            from ``_build_local_assignments``.
        _seen: Variable names already substituted on this resolution path,
            guarding against a circular ``a = b; b = a`` assignment chain.

    Returns:
        A list of one or more resolved absolute Paths, or None when the
        expression is not reducible this way (e.g. it depends on a runtime
        value this function does not recognise, or an unassigned variable).
    """
    for handler in _STATIC_PATH_HANDLERS:
        result = handler(node, script, assignments, _seen)
        if result is not None:
            return result
    return None
