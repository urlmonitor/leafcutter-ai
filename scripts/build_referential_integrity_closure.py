"""
MODULE: build_referential_integrity_closure
GOAL: AST-based static analysis of a deployed Python script's own code to
    derive the TRANSITIVE set of sibling modules and non-code (data/config)
    files it actually resolves at runtime -- the intra-package dependency
    closure AC BP-900g-8 / BP-900g-8-ii require. This is the HUB module:
    ``ClosureAnalysisError``, the non-code data-file detectors, and the
    recursive ``_closure_walk()`` entry point live here; the shared
    expression evaluator and the module-resolution detectors live in the two
    sibling modules imported below.
BUSINESS CONTEXT: This is the closure-ANALYSIS half of the referential
    -integrity guard split out of build_referential_integrity.py (AC
    BP-100n-4, file-size refactor): that module's own file-size cap was
    exceeded once its ``_eval_static_path`` dispatcher was decomposed into
    the cohesive handler functions the check-complexity gate required. The
    resulting single closure module then ALSO exceeded its own 400-counted
    -line cap (an entirely new file has no ratchet grace), so it was split
    again into three: this hub module, ``_eval`` (the expression evaluator
    family), and ``_resolvers`` (the static-import / dynamic-loader /
    sys.path detectors). Nothing in any of these modules' behaviour, error
    handling, or message text changed as part of either move -- see the
    DECISION HISTORY at the tail of this module for the moved-vs-changed
    boundary.
ARCHITECTURE: ``compute_intra_package_closure()`` and
    ``find_uncovered_closure_dependencies()`` (the PUBLIC entry points,
    still defined in build_referential_integrity.py) delegate to this
    module's ``_closure_walk()`` and ``ClosureAnalysisError``, imported back
    into that module (and re-exported from it, for every existing caller
    that imports ``ClosureAnalysisError`` from ``build_referential_integrity``
    rather than from here) so the two-step split is invisible to every
    caller.

    ``_closure_walk()`` performs AST-based static analysis of a deployed
    Python SCRIPT's own code -- its ``import`` statements, relative imports,
    ``sys.path.insert``/``sys.path.append`` mutations that redirect a
    subsequent plain import to a non-default directory, and
    ``importlib.util.spec_from_file_location`` dynamic-loader calls resolved
    relative to ``__file__`` -- to derive the TRANSITIVE set of sibling
    modules it actually resolves at runtime (Set A, ``resolved_closure``).
    This closure is never hand-maintained: a module added to a deployed
    script's imports tomorrow is picked up automatically because the scan
    reads the code, not a list. The three module-resolution detector
    functions it calls (``_extract_static_import_candidates()``,
    ``_extract_dynamic_loader_paths()``, ``_extract_syspath_directories()``)
    live in the sibling ``build_referential_integrity_closure_resolvers``
    module, imported below.

    AC BP-900g-8-ii widens Set A to also see NON-CODE (data/config) reads a
    deployed script performs -- a schema, a vocabulary, a registry, a data
    table -- on the same terms as a module import, through the SAME
    ``closure`` set, rather than a second, parallel notion of "data
    dependency". See the DECISION comment above
    ``_extract_data_file_read_candidates`` (defined in THIS module) for the
    three detectors this requires (a data read is an ordinary function call
    against a possibly-constructed path, unlike an import's fixed syntactic
    declaration). An optional ``data_root`` parameter (threaded through from
    the public functions) gives a template-sourced family's repo-root
    -relative data read a second, DEPLOY-rooted base to resolve against when
    it does not resolve under the module root -- see the DECISION note above
    ``_add_data_file_candidates``/``_extract_data_file_literal_candidates``
    for why a single root cannot serve both purposes.

    Both the data-file detectors here and the module-resolution detectors in
    ``_resolvers`` reduce a candidate expression to a concrete path via
    ``_eval_static_path()``, imported from the sibling
    ``build_referential_integrity_closure_eval`` module -- see that module's
    own docstring for the evaluator's dispatch design.
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path

from build_referential_integrity_closure_eval import (
    _annotate_parents,
    _build_local_assignments,
    _enclosing_scope,
    _eval_static_path,
)
from build_referential_integrity_closure_resolvers import (
    _extract_dynamic_loader_paths,
    _extract_static_import_candidates,
    _extract_syspath_directories,
)

# Pinned to the ORIGINAL module's name, not __name__ -- see the identical note
# in build_referential_integrity_closure_resolvers.py. This module's own
# _extract_data_file_read_candidates() also emits a WARNING through this same
# logger identity, so the pin matters here too even though the specific test
# anchor (test_bp_900g_8_unresolvable_syspath_push_logs_a_warning) targets the
# sys.path detector that now lives in _resolvers.
_log = logging.getLogger("build_referential_integrity")


class ClosureAnalysisError(Exception):
    """A deployable script's dependency closure could not be determined.

    Raised when :func:`compute_intra_package_closure` cannot read or parse a
    script it was asked to analyse. This exists so that "I could not look" is
    a DIFFERENT outcome from "I looked and found nothing" (KI-BP-022).

    Before this, both were an empty set. The containment check reads an empty
    closure as "no dependencies are missing", so a script whose source could
    not be parsed came back indistinguishable from a genuine leaf module and
    the build reported it clean. A WARNING was logged, but it did not change
    the exit status and nothing downstream could tell the two apart — which is
    the entire value the guard is supposed to provide.

    The guard is a deployment preflight, so there is no legitimate build in
    which one of the scripts about to be deployed cannot be parsed. Failing
    closed and naming the file is the only honest response.

    Args:
        script: The script whose analysis failed.
        reason: Human-readable cause (the underlying exception's message).
    """

    def __init__(self, script: Path, reason: str) -> None:
        self.script = script
        self.reason = reason
        super().__init__(
            f"cannot determine the intra-package dependency closure of "
            f"{script}: {reason}. This is NOT the same as the script having no "
            f"dependencies — the guard could not analyse it, so nothing is "
            f"known about what it needs deployed alongside it."
        )


# ---------------------------------------------------------------------------
# Non-code (data/config) dependency detection (AC BP-900g-8-ii)
# ---------------------------------------------------------------------------
#
# Widens the closure BP-900g-8 computes for MODULES so it treats a non-code
# file a deployed script reads at runtime -- a schema, a vocabulary, a
# registry, a data table -- as the SAME kind of dependency, on the SAME terms:
# derived from the code (never a hand-maintained list of known filenames) and
# reported through the SAME ``closure`` set the module half already populates,
# so a single containment check (``find_uncovered_closure_dependencies``)
# gives both classes the same enforcement force.
#
# Three complementary detectors, because a data read is an ordinary function
# call against a path that may be constructed -- unlike an import, which is
# always a single, syntactically-fixed declaration a static reader can see:
#
#   1. _extract_data_file_read_candidates(): the direct-idiom case --
#      ``open(<path-expr>)``, ``<path-expr>.read_text()``,
#      ``<path-expr>.read_bytes()``, ``<path-expr>.open()`` -- resolved via
#      the SAME ``_eval_static_path`` evaluator the module closure already
#      uses for ``spec_from_file_location`` targets and ``sys.path`` pushes.
#      An argument that does not reduce is logged as a WARNING naming the
#      file and line (the AC's "resolution: underivable" requirement) rather
#      than silently dropped -- mirroring the existing dynamic-loader and
#      sys.path disclosure behaviour.
#   2. _extract_resolvable_binop_paths(): the interprocedural-construction
#      case -- e.g. ``injection_builders.py``'s
#      ``registry_path = root / "config" / "agent_registry.json"``, where the
#      concrete path is BUILT in one function/module scope but actually READ
#      inside a different function (``_load_registry(registry_path)``) that
#      this module's single-scope evaluator cannot trace into. Rather than
#      requiring the read call and the path construction to share a scope,
#      every statically-resolvable ``/`` (Path division) expression anywhere
#      in the script is evaluated; only entries that successfully resolve
#      contribute a candidate, so a routine numeric division (which never
#      reduces to a ``Path(__file__)``-rooted or ``Path("literal")``-rooted
#      expression) is silently excluded rather than warned on -- warning on
#      every unresolvable ``/`` in a script would be indistinguishable from
#      warning on ordinary arithmetic.
#   3. _extract_data_file_literal_candidates(): the ancestor-walk case --
#      e.g. ``doc_type_validators.py``'s ``_find_doc_types_json()``, which
#      builds ``candidate = ancestor / rel`` inside a ``for ancestor in
#      [script_dir, *script_dir.parents]`` / ``for rel in (...)`` double loop.
#      Neither loop variable is a plain assignment ``_build_local_assignments``
#      captures, so no single-expression evaluator can reduce this. Instead,
#      every STANDALONE string literal in the script that already looks like a
#      package-relative data file path (``"config/doc_types.json"``) is
#      checked directly for existence under *root*. Requiring the ENTIRE
#      literal to match (not a substring search) is what keeps this from
#      matching prose mentions of the same path inside a docstring -- a
#      multi-line docstring's Constant value is the whole docstring text, which
#      does not fullmatch the tight relative-path pattern.
#
# All three report through the SAME ``closure`` set _closure_walk populates,
# and a discovered data file is NEVER itself recursed into (it is not
# parseable Python) -- unlike a resolved module candidate.

_DATA_FILE_EXTENSIONS = frozenset({
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".csv", ".txt",
})

# Matches a bare, package-relative, multi-segment path ending in a recognised
# non-code extension: e.g. "config/doc_types.json". Deliberately excludes:
#   - a leading "/" (an absolute, OS-owned path -- AC's boundary clause)
#   - a leading "~" (an external-tool path such as "~/.gitconfig")
#   - a single segment with no "/" (too weak a signal on its own; every real
#     regression instance named in this AC is at least "config/<file>")
#   - a ".py" suffix (that half of the closure is the existing module scan)
_RELATIVE_DATA_PATH_RE = re.compile(
    r"^[A-Za-z0-9_][\w.\-]*(?:/[A-Za-z0-9_][\w.\-]*)+"
    r"\.(?:json|yaml|yml|toml|ini|cfg|csv|txt)$"
)


def _is_data_read_call_target(node: ast.Call) -> ast.AST | None:
    """Return the path-argument node of a recognised file-read call, or None.

    Recognises the builtin ``open(<path>, ...)`` (path is the first positional
    argument) and the pathlib method forms ``<path>.read_text(...)``,
    ``<path>.read_bytes(...)``, ``<path>.open(...)`` (path is the attribute's
    receiver, ``node.func.value``). A method name collision with an unrelated
    object (e.g. some other type's own ``.open()``) is harmless here: the
    receiver only contributes a closure entry if it ALSO resolves via
    ``_eval_static_path`` to a real file under the package root, which a
    non-Path receiver never does.
    """
    func = node.func
    if isinstance(func, ast.Name) and func.id == "open" and node.args:
        return node.args[0]
    if isinstance(func, ast.Attribute) and func.attr in ("read_text", "read_bytes", "open"):
        return func.value
    return None


def _extract_data_file_read_candidates(tree: ast.AST, script: Path) -> list[Path]:
    """Return resolvable path candidates from every recognised file-read call.

    A target that is a BARE, unassigned identifier (no matching entry in this
    call's own scope+module assignments) is skipped WITHOUT a warning -- this
    is overwhelmingly a function parameter or other caller-supplied value
    (e.g. ``open(file_path, encoding=...)`` where ``file_path`` is an
    argument), not an attempted package-relative path construction. Warning on
    every one of these would drown real signal: measured directly against
    this package's own ~150 deployable scripts, treating every unresolvable
    bare name as reportable produced 400+ warnings on a single build, none of
    which named an actual intra-package dependency. A target that IS some
    other expression shape (an attribute chain, a call, a division, or a name
    that resolves to one of those but still fails to reduce) is a genuine
    path-construction ATTEMPT this module could not finish resolving, and is
    logged as a WARNING naming the file and line -- per AC BP-900g-8-ii's
    disclosure requirement, that kind of unknown must be surfaced for a human
    rather than silently dropped.
    """
    _annotate_parents(tree)
    candidates: list[Path] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = _is_data_read_call_target(node)
        if target is None:
            continue
        scope = _enclosing_scope(node, tree)
        assignments = _build_local_assignments(scope, tree)
        if isinstance(target, ast.Name) and target.id not in assignments:
            continue
        resolved = _eval_static_path(target, script, assignments)
        if resolved is None:
            _log.warning(
                "compute_intra_package_closure: unresolvable data-file read in "
                "%s at line %s -- static analysis could not reduce the "
                "open()/read_text()/read_bytes()/.open() target to a concrete "
                "path. A human should verify whether this reference is "
                "external or needs to be deployed (AC BP-900g-8-ii).",
                script,
                getattr(node, "lineno", "?"),
            )
            continue
        candidates.extend(resolved)
    return candidates


def _extract_resolvable_binop_paths(tree: ast.AST, script: Path) -> list[Path]:
    """Return every ``/``-division expression in *tree* that resolves to a path.

    Deliberately does not warn on a ``/`` expression that fails to resolve --
    see the module-level DECISION note above this section for why a routine
    numeric division must not be treated as an unresolvable path reference.
    """
    _annotate_parents(tree)
    candidates: list[Path] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
            continue
        scope = _enclosing_scope(node, tree)
        assignments = _build_local_assignments(scope, tree)
        resolved = _eval_static_path(node, script, assignments)
        if resolved is not None:
            candidates.extend(resolved)
    return candidates


def _extract_data_file_literal_candidates(
    tree: ast.AST, root: Path, data_root: Path
) -> tuple[set[str], set[str]]:
    """Return standalone string literals in *tree* that name a real data file.

    A literal must FULLY match ``_RELATIVE_DATA_PATH_RE`` (never a substring
    search) so a prose mention embedded in a longer docstring never matches.
    It must also resolve to a real, existing file under *root* OR *data_root*
    -- a plausible-looking literal that is not backed by a real file under
    either (e.g. the workspace-layout alternate candidate
    ``"leafcutter/config/doc_types.json"`` when run from the package's own
    source tree) is silently excluded rather than reported, since this
    detector cannot tell whether such a literal is a live reference or an
    alternate-layout candidate that never applies here.

    TWO ROOTS, because an ancestor-directory-walk literal (the shape this
    detector exists for -- see the DECISION note above this section) is
    written the way the DEPLOYED script sees it, which is relative to the
    DEPLOY root, not necessarily the closure root a caller passes for
    resolving this script's OWN sibling modules. ``root`` is tried first (a
    literal that happens to sit inside the script's own family directory,
    the same namespace a sibling module read like
    ``commit_guardian.json`` uses); *data_root* is the fallback for a literal
    that is genuinely deploy-root-relative (e.g. ``"config/doc_types.json"``
    read by a commit-guardian script, whose closure root is
    ``<package_root>/templates`` and where ``config/`` never exists).

    Returns:
        A ``(family_relative, deploy_root_relative)`` pair. A literal found
        under *root* is reported in ``family_relative`` (the caller applies
        the same deploy-namespace prefix a module dependency would get); one
        found only under *data_root* is reported in ``deploy_root_relative``
        (already expressed in final deploy-root-relative form, so the caller
        must NOT prefix it -- prefixing it would land it, e.g.,
        ``<family-prefix>config/doc_types.json``, a path nothing deploys).
    """
    family_relative: set[str] = set()
    deploy_root_relative: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        value = node.value
        if value.startswith(_DATA_FILE_EXCLUDED_PREFIX):
            continue
        if not _RELATIVE_DATA_PATH_RE.match(value):
            continue
        if (root / value).is_file():
            family_relative.add(value)
        elif data_root != root and (data_root / value).is_file():
            deploy_root_relative.add(value)
    return family_relative, deploy_root_relative


# A resolved candidate whose root-relative path starts with this prefix is
# excluded from the data-file closure (never from the pre-existing module
# closure -- this exclusion is scoped to _add_data_file_candidates and
# _extract_data_file_literal_candidates only). ``templates/`` is source-only
# packaging infrastructure: no build phase ever deploys a raw ``templates/``
# directory to a consumer install (everything under it is either compiled to a
# different destination path or read directly from the SOURCE tree by
# build.py itself). A deployed script that references
# ``Path(__file__).resolve().parent.parent / "templates" / ...`` -- as
# injection_builders.py's build_signoff_block() does, for a package-build-time
# convenience read that is ALSO guarded by its own ``if path.exists():`` check
# -- resolves that path against the SOURCE tree only because this closure
# computation evaluates ``Path(__file__)`` as the SOURCE file's own location
# (the same source-relative evaluation BP-900g-8's module closure already
# uses). Treating that as a "this must be deployed" finding would demand the
# build ship a directory it structurally never ships, which is the same
# false-demand failure mode the OS/external-tool-path boundary clause forbids
# for a different reason.
_DATA_FILE_EXCLUDED_PREFIX = "templates/"


def _add_data_file_candidates(
    candidates: list[Path],
    root: Path,
    data_root: Path,
    family_relative: set[str],
    deploy_root_relative: set[str],
) -> None:
    """Resolve *candidates* and sort real, recognised data files into the two output sets.

    Restricted to ``_DATA_FILE_EXTENSIONS`` (the same recognised non-code
    extensions ``_RELATIVE_DATA_PATH_RE`` matches) rather than merely
    excluding ``.py`` -- a resolvable division expression could otherwise
    point at an arbitrary non-Python file this AC's criterion was never about
    (a compiled cache file, a log, an unrelated binary asset). Never recurses
    -- a data file is not parseable Python, unlike a resolved module candidate.

    Each *candidate* is an ABSOLUTE path (already resolved via
    ``_eval_static_path``, anchored at the analysed script's own real
    location). Expressing it relative to *root* is tried FIRST -- this is
    what a sibling-directory read (e.g. ``commit_guardian.json`` next to
    ``config.py``) needs, and it lands the result in the same namespace a
    module dependency would use, so the caller can apply the SAME
    deploy-namespace prefix to it. Only when that fails (the candidate lives
    outside *root* entirely -- e.g. a chained ``.parent`` walk that reaches
    all the way up to the deploy root, or a data read this closure's *root*
    was never meant to cover) is *data_root* tried as a fallback, and the
    result recorded separately as ALREADY deploy-root-relative -- the caller
    must not add a prefix to it, or it lands at a path nothing deploys.

    The ``templates/`` source-only exclusion (see the module-level DECISION
    note on ``_DATA_FILE_EXCLUDED_PREFIX``) is applied to whichever
    resolution actually succeeds, since either root could in principle
    produce a ``templates/``-prefixed result.
    """
    for candidate in candidates:
        if candidate.suffix not in _DATA_FILE_EXTENSIONS or not candidate.is_file():
            continue
        resolved = candidate.resolve()
        try:
            rel = resolved.relative_to(root).as_posix()
        except ValueError:
            rel = None
        if rel is not None and not rel.startswith(_DATA_FILE_EXCLUDED_PREFIX):
            family_relative.add(rel)
            continue
        if data_root == root:
            continue
        try:
            deploy_rel = resolved.relative_to(data_root).as_posix()
        except ValueError:
            continue
        if not deploy_rel.startswith(_DATA_FILE_EXCLUDED_PREFIX):
            deploy_root_relative.add(deploy_rel)


def _relative_to_root_without_symlink_escape(candidate: Path, root: Path) -> str:
    """Return *candidate*'s path relative to *root*, without a false ``.leafcutter/`` prefix.

    A deployed script's sibling directory can itself be a SYMLINK in a
    self-hosted, already-built worktree: ``install_shims()`` (ADR-016) leaves
    ``<package_root>/scripts/commit_guardian`` as a symlink into
    ``<package_root>/.leafcutter/scripts/commit_guardian`` once it has run.
    ``candidate`` is already constructed *root*-relative by pure path
    arithmetic (see ``_eval_static_path`` / ``_module_name_candidates`` --
    every component is either *root* itself, one of its already-resolved
    ancestors, or a literal string segment), so ``candidate.relative_to(root)``
    without resolving is already correct and never crosses the symlink.
    ``candidate.resolve()`` DOES cross it: it follows
    ``scripts/commit_guardian`` to its real target and returns
    ``.leafcutter/scripts/commit_guardian/...`` instead -- a path Set B never
    contains, so the guard reports a live, correctly-deployed dependency as
    undeployed (BO-2900d-1/-2 fast-lane build, 2026-09-07: the first
    ``sys.path.insert``-based cross-directory import from ``scripts/ac_store/``
    into the ``commit_guardian`` family, so the first code to actually walk
    through this symlink during closure analysis).

    Falls back to the resolved form for any candidate that is not already
    *root*-relative as constructed (every other candidate shape this module
    produces) -- unchanged behaviour for every case this fix does not target.

    Args:
        candidate: The already *root*-relative-by-construction absolute path.
        root: The closure/module root (see ``compute_intra_package_closure``).

    Returns:
        POSIX-style path string relative to *root*.

    Raises:
        ValueError: Neither the unresolved nor the resolved form of
            *candidate* is relative to *root* -- the same "not part of this
            closure" signal ``relative_to`` always raises, preserved for the
            caller's existing ``except ValueError: continue``.
    """
    try:
        return candidate.relative_to(root).as_posix()
    except ValueError:
        return candidate.resolve().relative_to(root).as_posix()


def _closure_walk(
    script: Path,
    root: Path,
    visited: set[Path],
    closure: set[str],
    deploy_root_relative: set[str],
    data_root: Path,
) -> None:
    """Recursively add *script*'s resolvable intra-package dependencies to *closure*.

    *root* is the closure/module root: sibling modules (and sibling data
    files read the same way, e.g. ``commit_guardian.json`` next to
    ``config.py``) resolve relative to it, exactly as before AC BP-900g-8-ii.

    *data_root* is the DEPLOY root a non-code read is expressed against when
    it does NOT resolve under *root* -- see the module-level DECISION note
    above ``_add_data_file_candidates``/``_extract_data_file_literal_candidates``
    for why a single root cannot serve both purposes for a template-sourced
    family (e.g. the commit-guardian family, whose module root is
    ``<package_root>/templates`` but whose repo-root-relative data reads,
    such as ``config/doc_types.json``, are written the way the DEPLOYED
    script sees them -- relative to the deploy root, not the family prefix).
    Every entry this walk resolves ONLY via *data_root* is additionally
    recorded in *deploy_root_relative* (a subset of *closure*) so a caller
    building a deploy-namespace string knows NOT to prepend a family prefix
    to it -- prepending one would land it at a path nothing deploys.
    """
    if script in visited:
        return
    visited.add(script)

    # KI-BP-022: both handlers used to log a WARNING and return, leaving the
    # closure empty. An empty closure means "nothing missing" to the caller, so
    # an unreadable or unparseable script was reported CLEAN. Raise instead —
    # see ClosureAnalysisError for why silence is not an option here.
    #
    # UnicodeDecodeError subclasses ValueError, not OSError, so it escaped the
    # read handler entirely and surfaced as a raw traceback out of build.py.
    # That failed closed by accident, which was the right outcome for the wrong
    # reason; it is caught explicitly now.
    try:
        text = script.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ClosureAnalysisError(script, f"cannot read: {exc}") from exc

    try:
        tree = ast.parse(text, filename=str(script))
    except SyntaxError as exc:
        raise ClosureAnalysisError(script, f"cannot parse: {exc}") from exc

    syspath_dirs = tuple(_extract_syspath_directories(tree, script))
    candidates = _extract_static_import_candidates(
        tree, script.parent, root, extra_dirs=syspath_dirs
    )
    candidates.extend(_extract_dynamic_loader_paths(tree, script))

    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            rel = _relative_to_root_without_symlink_escape(candidate, root)
        except ValueError:
            continue
        if rel not in closure:
            closure.add(rel)
        _closure_walk(candidate.resolve(), root, visited, closure, deploy_root_relative, data_root)

    # AC BP-900g-8-ii: non-code (data/config) reads, same terms as modules,
    # never recursed into (not parseable Python). See the DECISION note above
    # _extract_data_file_read_candidates for why three separate detectors are
    # needed rather than one, and the DECISION note above
    # _add_data_file_candidates for why each detector reports into TWO sets
    # (family-relative vs. deploy-root-relative) rather than one.
    data_candidates = _extract_data_file_read_candidates(tree, script)
    data_candidates.extend(_extract_resolvable_binop_paths(tree, script))
    family_data: set[str] = set()
    deploy_data: set[str] = set()
    _add_data_file_candidates(data_candidates, root, data_root, family_data, deploy_data)
    literal_family, literal_deploy = _extract_data_file_literal_candidates(tree, root, data_root)
    family_data |= literal_family
    deploy_data |= literal_deploy
    closure |= family_data | deploy_data
    deploy_root_relative |= deploy_data


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-14 [python-coder/BP-100n-4]: Pure move, no behaviour change,
#   done in two steps. Step 1: ClosureAnalysisError, the AST-analysis
#   internals, and everything they depend on moved OUT of
#   build_referential_integrity.py entirely, into a single new module named
#   build_referential_integrity_closure.py -- that file had grown past its
#   400-counted-line file-size cap once the earlier BP-100n-4
#   complexity-reduction pass decomposed its over-threshold _eval_static_path
#   (42) into cohesive handler functions check-complexity required. Step 2:
#   the resulting SINGLE closure module then exceeded ITS OWN 400-line cap in
#   turn (847 counted lines -- a brand-new file gets no ratchet grace, unlike
#   an already-oversized existing file), so it was split again: the
#   expression-evaluator family (_eval_static_path and everything it
#   dispatches to, plus the shared scope helpers) moved to
#   build_referential_integrity_closure_eval.py, and the module-resolution
#   detectors (static imports, the dynamic loader, sys.path pushes) moved to
#   build_referential_integrity_closure_resolvers.py. This hub module kept
#   ClosureAnalysisError, the non-code data-file detectors, and
#   _closure_walk -- importing the eval and resolver functions it needs back
#   from the two new siblings. Every function body, docstring, and log
#   message across all three modules is byte-for-byte identical to before
#   either move.
#
#   Both this module and _resolvers pin their own module-level logger to the
#   STRING "build_referential_integrity" (not __name__, which would resolve
#   differently per module post-split) specifically to preserve
#   test_bp_900g_8_unresolvable_syspath_push_logs_a_warning's
#   caplog.at_level(..., logger="build_referential_integrity") assertion,
#   which filters by logger NAME and would otherwise silently stop matching
#   once the WARNING-emitting code moved to a differently-named module.
#
#   No new deploy_map / shim_map entry was needed for any of the three
#   modules: like their sibling build_helpers.py, build_phases.py, and
#   build_phases_*.py modules, these are plain, git-tracked scripts/*.py
#   source files imported directly by build.py (transitively, via
#   build_referential_integrity.py) at build time from this repo's own
#   scripts/ directory -- neither the commit_guardian wholesale-rglob deploy
#   path nor the scripts/ac_store/ hardcoded deploy_map path applies to a
#   build-time-only tool with no consumer-facing agent invoking it directly.
#   Confirmed by grep: no other sibling build_*.py helper module has a
#   deploy_map or shim_map entry either. (#BP-100n-4)
# ====================================================================
