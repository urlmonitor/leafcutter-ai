"""
MODULE: _declaring_files_scan
GOAL: Pure AST-scanning primitives behind AC BP-900h-4's declaring-file
    derivation — the two narrowly-scoped scans that recognise a resolver
    shape a deployed guardrail uses, and the string-literal / import
    extraction helpers they share. Split out of ``_declaring_files_derivation``
    (see that module's own DECISION HISTORY) purely to keep both files under
    the repository's 400-line-per-file limit; there is no behavioural
    boundary here beyond "AST recognition" vs. "file-walk orchestration".
BUSINESS CONTEXT: On 2026-08-18 five declaring files were confirmed absent
    from a genuine consumer install while every build test passed, because
    every build test to date installs into leafcutter's own self-hosted
    workspace, where the package source tree sits beside the deployed output
    root and each missing file resolves anyway by accident. The two scans in
    this module recognise the exact resolver shape those regressions share,
    from a deployed guardrail's OWN source (AST, never a hand-typed list).
ARCHITECTURE: Two independent, narrowly-scoped scans, each targeting one
    concrete code shape already used by a real guardrail in this repository:

    (1) FILE-ANCHORED ANCESTOR-WALK CONFIG PATHS. A function whose own AST
        subtree references both the module's ``__file__`` global and an
        attribute named ``parents`` is walking upward from *this script's
        own deployed location* — as opposed to ``Path.cwd()`` or a
        ``git rev-parse --show-toplevel`` subprocess, which resolve relative
        to the *invoking process*, a materially different and out-of-scope
        resolution strategy documented as such in ``doc_type_validators.py``'s
        own docstring. Every ``config/*.json`` / ``config/*.yaml`` string
        literal (bare, tuple/list element, or ``Path("config") / "x.json"``
        join) found inside such a function is a declaring file this
        guardrail needs to exist somewhere under the walked ancestors —
        which, from the deployed layout, means under the deployed output
        root itself.
    (2) LOCAL UNDERSCORE-PREFIXED HELPER MODULES. A bare (non-dotted) import
        of a leading-underscore name (``from _ac_components import ...``),
        or a bare leading-underscore ``"*.py"`` string literal used to build
        a dynamic-import path (``Path(__file__).parent / "_x.py"``), names a
        sibling helper module the importing script cannot run without.
        Imports guarded by a ``try/except ImportError`` (the codebase's own
        optional-dependency idiom, e.g. ``check_ac_schema.py``'s
        ``_ac_store_index``) are excluded — the reader itself has already
        declared that module optional.

    Deliberately NOT scanned: any resolver keyed off ``Path.cwd()`` or a
    ``git rev-parse`` subprocess (e.g. ``check_paths_integrity.py``,
    ``check_roadmap_schema.py``, ``check_surface_components_e3.py``) — these
    depend on the invoking process's working directory, not on where the
    guardrail itself is deployed, and are out of this AC's scope by the same
    distinction ``doc_type_validators.py`` draws in its own docstring.

    This module has no dependency on ``_declaring_files_derivation`` — the
    dependency runs the other way (that module imports the scan entry points
    and the shared literal-extraction primitives from here), so there is no
    import cycle between the two.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_CONFIG_PATH_RE = re.compile(r"^(?:leafcutter/)?config/[\w./\-]+\.(?:json|ya?ml)$")
_HELPER_FILENAME_RE = re.compile(r"^_[A-Za-z0-9][A-Za-z0-9_]*\.py$")
_UNDERSCORE_MODULE_RE = re.compile(r"^_[A-Za-z0-9][A-Za-z0-9_]*$")


def _normalize_config_literal(value: str) -> str:
    """Strip the ``leafcutter/`` ancestor-walk prefix, if present.

    Both ``config/x.json`` and ``leafcutter/config/x.json`` are candidates
    the SAME ancestor-walk resolver tries at different ancestor depths for
    the SAME file; once anchored to an explicit ``--deployed-root``, both
    name one location: ``<deployed-root>/config/x.json``.
    """
    return value.removeprefix("leafcutter/")


def _extract_path_literal(node: ast.AST) -> str | None:
    """Pure: resolve a string-literal, or a ``Path(...)``/``/``-joined chain
    of string literals, to its effective path string. Returns ``None`` for
    any expression that is not built entirely from literals (e.g.
    ``Path(__file__).resolve()``), which is the correct outcome — this
    function derives constants, not runtime paths.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _extract_path_literal(node.left)
        right = _extract_path_literal(node.right)
        if left is not None and right is not None:
            return f"{left.rstrip('/')}/{right}"
        return None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id == "Path" and len(node.args) == 1:
            return _extract_path_literal(node.args[0])
    return None


def _is_file_anchored_ancestor_walk(node: ast.AST) -> bool:
    """Pure: True when a function's own AST subtree references the module's
    ``__file__`` global AND an attribute named ``parents`` — the resolver
    shape this AC's regression class shares, as opposed to a
    ``Path.cwd()``- or ``git rev-parse``-based resolver (out of scope; see
    module ARCHITECTURE note).

    Determined structurally (a single walk of *node*'s own subtree) rather
    than via a source-text substring search: a prior text-based
    implementation called ``ast.get_source_segment`` — which re-splits the
    ENTIRE file's source into lines on every call, uncached — once per
    function definition found anywhere in a deployed file, regardless of
    whether that function ultimately qualified. Across a real deployed tree
    (225 files, ~2000 function defs) that dominated this module's own
    runtime (~2s of a ~7s per-invocation cost, profiled during BP-900h-4-i's
    authoring — see ``_declaring_files_derivation``'s DECISION HISTORY). The
    AST check below performs the equivalent test without ever touching the
    file's source text.
    """
    has_file = False
    has_parents = False
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id == "__file__":
            has_file = True
        elif isinstance(sub, ast.Attribute) and sub.attr == "parents":
            has_parents = True
        if has_file and has_parents:
            return True
    return False


def _collect_config_literals(node: ast.AST, constants: dict[str, str]) -> set[str]:
    """Pure: collect every ``config/*.json``/``config/*.yaml``-shaped path
    literal reachable within *node* — as a bare string constant, as an
    element of a tuple/list literal, as a ``Path(...) / "..."`` join, or via
    a ``Name`` reference to a constant (local or cross-module — see
    *constants*) already resolved to such a literal.
    """
    found: set[str] = set()
    for sub in ast.walk(node):
        literal: str | None = None
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            literal = sub.value
        elif isinstance(sub, ast.Name) and sub.id in constants:
            literal = constants[sub.id]
        elif isinstance(sub, ast.BinOp):
            literal = _extract_path_literal(sub)
        if literal is not None and _CONFIG_PATH_RE.match(literal):
            found.add(_normalize_config_literal(literal))
    return found


def _imports_resolve_root(all_nodes: list[ast.AST]) -> bool:
    """Pure: True when *all_nodes* (a file's full node set — see
    ``_declaring_files_derivation._entries_for_file``) contains an import of
    the shared ``_resolve_root`` helper (``from _resolve_root import
    find_project_root`` or ``import _resolve_root``) — itself a confirmed
    ``__file__``+``.parents``-fallback resolver (see module ARCHITECTURE
    note). A file that delegates root resolution to it and then joins the
    result with a config-relative constant (commonly imported from a
    sibling ``config`` module, e.g. ``_signoff_parity_checks.py`` joining
    ``config.AGENT_REGISTRY_PATH``) is relying on the same file-anchored
    resolution chain even though the walk itself lives in the imported
    helper, not in this file's own source.
    """
    for node in all_nodes:
        if isinstance(node, ast.ImportFrom) and node.module == "_resolve_root":
            return True
        if isinstance(node, ast.Import) and any(
            alias.name == "_resolve_root" for alias in node.names
        ):
            return True
    return False


def _config_declaring_files(
    tree: ast.Module, all_nodes: list[ast.AST], constants: dict[str, str]
) -> set[str]:
    """Pure (given an already-parsed tree, its pre-computed full node list —
    see ``_declaring_files_derivation._entries_for_file`` — and the
    cross-module constants map — see ``derive_inventory``): collect
    config-path literals from every file-anchored-ancestor-walk function in
    *tree*, plus — when *tree* imports ``_resolve_root`` — every
    config-path literal anywhere else in the file (see
    ``_imports_resolve_root``).
    """
    found: set[str] = set()
    for node in all_nodes:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and _is_file_anchored_ancestor_walk(node):
            found |= _collect_config_literals(node, constants)
    if _imports_resolve_root(all_nodes):
        found |= _collect_config_literals(tree, constants)
    return found


def _handles_import_error(handler: ast.ExceptHandler) -> bool:
    """Pure: True when *handler* catches ImportError/ModuleNotFoundError (or
    a broader Exception), the codebase's own optional-dependency idiom.
    """
    exc_type = handler.type
    if exc_type is None:
        return True
    names: list[str] = []
    if isinstance(exc_type, ast.Name):
        names = [exc_type.id]
    elif isinstance(exc_type, ast.Tuple):
        names = [elt.id for elt in exc_type.elts if isinstance(elt, ast.Name)]
    return any(
        name in ("ImportError", "ModuleNotFoundError", "Exception", "BaseException")
        for name in names
    )


def _import_error_guarded_names(all_nodes: list[ast.AST]) -> set[str]:
    """Pure: bare (non-dotted) import names that appear inside a
    ``try: ... except ImportError:``-guarded block anywhere in *all_nodes*
    (a file's full node set — see
    ``_declaring_files_derivation._entries_for_file``) — these are declared
    optional by the reader itself and must not be reported missing.
    """
    guarded: set[str] = set()
    for node in all_nodes:
        if not isinstance(node, ast.Try):
            continue
        if not any(_handles_import_error(h) for h in node.handlers):
            continue
        for stmt in node.body:
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.Import):
                    guarded.update(alias.name for alias in sub.names)
                elif isinstance(sub, ast.ImportFrom) and sub.module:
                    guarded.add(sub.module)
    return guarded


def _sibling_relative_path(read_by_rel: str, filename: str) -> str:
    """Pure: the deployed-root-relative path of *filename* sitting alongside
    the guardrail at *read_by_rel*.
    """
    parent = Path(read_by_rel).parent
    return filename if str(parent) == "." else (parent / filename).as_posix()


def _helper_module_declaring_files(all_nodes: list[ast.AST], read_by_rel: str) -> set[str]:
    """Pure: local leading-underscore sibling-module declaring files this
    guardrail imports (statically) or loads dynamically via a bare filename
    literal — excluding any import guarded by ``try/except ImportError``.
    """
    guarded = _import_error_guarded_names(all_nodes)
    found: set[str] = set()
    for node in all_nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if (
                    "." not in alias.name
                    and _UNDERSCORE_MODULE_RE.match(alias.name)
                    and alias.name not in guarded
                ):
                    found.add(_sibling_relative_path(read_by_rel, f"{alias.name}.py"))
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            if (
                (node.level or 0) == 0
                and module
                and "." not in module
                and _UNDERSCORE_MODULE_RE.match(module)
                and module not in guarded
            ):
                found.add(_sibling_relative_path(read_by_rel, f"{module}.py"))
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            # Only a Path-join right operand counts as "loading a sibling
            # file" (Path(__file__).resolve().parent / "_x.py"). A bare
            # string constant elsewhere (e.g. name.endswith("_test.py"))
            # is not a file-load and must not be treated as one.
            right = node.right
            if isinstance(right, ast.Constant) and isinstance(right.value, str):
                if _HELPER_FILENAME_RE.match(right.value):
                    found.add(_sibling_relative_path(read_by_rel, right.value))
    return found


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-07 [python-coder/fast-lane BP-900h-4 build set]: Split out of
#   _declaring_files_derivation.py, which had grown to 455 lines (over the
#   repository's 400-line-per-file limit enforced by check_file_size.py)
#   after the AST-based _is_file_anchored_ancestor_walk rewrite and the
#   single-materialized-walk performance pass. This module holds every pure
#   AST-recognition primitive (the two scan shapes plus the literal/import
#   extraction helpers they share); _declaring_files_derivation.py keeps the
#   file-walk orchestration (parse, derive, merge, find_missing) and imports
#   the scan entry points from here. One-directional dependency (derivation
#   -> scan) — this module never imports from _declaring_files_derivation,
#   so there is no import cycle.
# ====================================================================
