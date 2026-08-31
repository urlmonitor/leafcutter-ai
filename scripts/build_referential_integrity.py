"""
MODULE: build_referential_integrity
GOAL: Post-build validation that every file/directory path referenced in
    skills_config.json actually exists on disk, and pre-build extraction
    of all script path references embedded in source agent, skill, and
    workflow templates.
BUSINESS CONTEXT: skills_config.json references paths like testing_context.readme_path,
    precommit_autofix_config_path, changelog_folder, and changelog_categories_path.
    Downstream agents (test-planner, precommit-autofix, changelog) fail silently when
    these files don't exist. This module catches those gaps at build time.
    The extract_script_path_refs function implements AC BP-900b-1: before build.py
    runs phases, this function scans source agent and skill templates and extracts
    all script path references for the broken-reference guard.
    AC BP-900g-6 extends the same scan to workflow sources
    (``templates/workflows-js/*.js`` and ``templates/workflows/*.md``): a workflow
    that shells out to an undeployed script was previously invisible to the guard,
    the same defect class BP-900g-4/BP-900g-5 closed for agent and skill templates.
ARCHITECTURE: Four public functions. check_referential_integrity() validates path-valued
    fields in the config dict and is wired into build.py as a post-build warning phase
    (non-blocking). extract_script_path_refs() scans source .md/.js template files and
    returns a set of all script paths referenced via python/python3 invocations and
    sys.path.insert calls, enabling the pre-build validation phase (BP-900b-1).
    extract_script_path_refs_with_sources() is the richer variant that returns a mapping
    from each script path to the set of template files referencing it, used by the JSONL
    report phase (BP-900c-1).
    Both functions scan ``templates_dir/agents/`` and ``templates_dir/skills/`` (``.md``),
    plus ``templates_dir/workflows/`` (``.md``) and ``templates_dir/workflows-js/``
    (``.js``) as of BP-900g-6. The scan is text-based and language-agnostic — the same
    compiled regexes match a Python invocation whether it appears in prose, Markdown, or
    a JavaScript string literal — so adding a directory/glob pair is sufficient; no new
    pattern was required for the ``.js`` file type itself. See the DECISION HISTORY at
    the tail of this module for why JS template-literal interpolation prefixes
    (``${worktreePath}/scripts/...``) are deliberately NOT extracted.
    extract_compiled_script_path_refs() is the fourth function (AC BP-900b-1 ticket
    05_TICKET-20260611-BP-900b-1): it reuses the same ``_SCRIPT_PATTERNS`` regex set but
    targets the COMPILED output tree (``<target>/.claude/agents/`` and
    ``<target>/.claude/skills/``) rather than the source ``templates/`` tree, and returns
    ``set[tuple[str, str]]`` of ``(relative_template_path, referenced_script_path)`` so a
    caller can trace each reference back to its compiled template. It is a read-only,
    standalone scan available for a future post-compile validation phase; no production
    call site invokes it yet (see ``doc_links`` on the AC — this is the single
    reference-extraction-pass location the AC's ``n_location_rule`` requires; wiring it
    into ``build.py``'s phase list is intentionally out of this ticket's ``files_touched``
    scope).
    compute_intra_package_closure() and find_uncovered_closure_dependencies() (AC
    BP-900g-8) are a DIFFERENT axis from everything above: the functions so far scan
    TEMPLATE PROSE for invocation-style script references
    (``python scripts/<path>``). BP-900g-8 instead performs AST-based static analysis
    of a deployed Python SCRIPT's own code -- its ``import`` statements, relative
    imports, ``sys.path.insert``/``sys.path.append`` mutations that redirect a
    subsequent plain import to a non-default directory, and
    ``importlib.util.spec_from_file_location`` dynamic-loader calls resolved
    relative to ``__file__`` -- to derive the TRANSITIVE set of sibling modules
    it actually resolves at runtime (Set A, ``resolved_closure``). This
    closure is never hand-maintained: a module added to a deployed script's imports
    tomorrow is picked up automatically because the scan reads the code, not a list.
    ``find_uncovered_closure_dependencies()`` is the containment check: it computes
    the closure for a named script and reports which entries are absent from a
    caller-supplied declared set (Set B, ``deploy_declaration``), so a build-time
    caller (``build.py``) can fail loudly when a script resolves a dependency that
    no deploy phase ships. Both functions are root-relative: the caller passes the
    root a returned path string is relative to, so the same functions work
    unmodified against the SOURCE tree (root=package root) or the DEPLOYED tree
    (root=output root) -- the latter is what proves the closure is actually shipped,
    not merely present in source by construction.
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


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
# Patterns for script path extraction (AC BP-900b-1)
# ---------------------------------------------------------------------------
#
# Matches:
#   python3 scripts/<path>          (inline invocation)
#   python scripts/<path>           (inline invocation)
#   python3 {{config.output_root}}/scripts/<path>   (output-root template form)
#   python3 .leafcutter/scripts/<path>              (rendered output-root form)
#   sys.path.insert(<N>, 'scripts/<path>')   (single-quoted)
#   sys.path.insert(<N>, "scripts/<path>")   (double-quoted)
#
# All patterns capture only the ``scripts/<path>`` portion (group 1), so an
# output-root-prefixed reference normalises to the same deploy-namespace key as
# a bare one and can be compared against the deployable manifest directly.
#
# The optional prefix accepts ONLY an output root: the literal
# ``{{config.output_root}}/`` token, or a rendered dot-prefixed root such as
# ``.leafcutter/``.  It is not a general "any one segment" allowance.
#
# Requiring the leading dot is the discriminator that keeps this honest. Templates
# also reference HOST-project paths that merely contain a ``scripts/`` component —
# ``python debugging/scripts/check/prod_status_check.py`` in status-checker.md,
# ``python leafcutter/scripts/build.py`` in package-developer prose. Those are not
# leafcutter deliverables and must never be normalised into ``scripts/...`` deploy
# keys, or the guard demands a deploy phase for a script that belongs to the user's
# own project. An unbounded ``.*/`` prefix is worse still: it would capture
# ``scripts/other.py`` out of ``/usr/lib/vendor/nested/scripts/other.py``. Both are
# the false-positive failure mode EPIC-BuildGuardFalsePositive already had to fix
# once, so both are excluded and pinned by negative-control tests.
#
# NOTE: the two ``sys.path.insert`` patterns below are intentionally NOT widened.
# They capture ``(scripts/[^']+)`` with no ``.py`` anchor, and the only
# output-root-form occurrence in the templates is a DIRECTORY
# (``sys.path.insert(0, '{{config.output_root}}/scripts/ac_store')``).  Widening
# them would extract ``scripts/ac_store``, which is absent from the ``.py``-only
# deployable manifest, and abort every build with a phantom broken reference.
# Undeployed directories added via sys.path therefore remain outside this guard.

_PYTHON_INVOKE_RE = re.compile(
    r"""(?:python3?)\s+(?:\{\{config\.output_root\}\}/|\.[\w.\-]+/)?(scripts/[\w./\-]+\.py)"""
)

_SYSPATH_SINGLE_RE = re.compile(
    r"""sys\.path\.insert\s*\(\s*\d+\s*,\s*'(scripts/[^']+)'\s*\)"""
)

_SYSPATH_DOUBLE_RE = re.compile(
    r"""sys\.path\.insert\s*\(\s*\d+\s*,\s*"(scripts/[^"]+)"\s*\)"""
)

_SCRIPT_PATTERNS: tuple[re.Pattern[str], ...] = (
    _PYTHON_INVOKE_RE,
    _SYSPATH_SINGLE_RE,
    _SYSPATH_DOUBLE_RE,
)

# ---------------------------------------------------------------------------
# Scan targets (AC BP-900g-6)
# ---------------------------------------------------------------------------
# Each entry is (subdirectory-under-templates_dir, glob-pattern). The scan is
# text-based and language-agnostic: the same _SCRIPT_PATTERNS above match a
# Python invocation whether it sits in Markdown prose or inside a JavaScript
# string literal, so no JS-specific pattern is needed here — only the
# directory/extension pair changes per source kind.
#
# workflows/ (.md) and workflows-js/ (.js) are the sources for the
# workflow-orchestration layer (slash-command bodies and JS workflow engines
# respectively). Before BP-900g-6 neither was scanned, so a workflow that
# shells out to an undeployed script was invisible to
# _check_script_reference_guard() — the same defect class BP-900g-4/BP-900g-5
# closed for agent and skill templates.
_SCAN_TARGETS: tuple[tuple[str, str], ...] = (
    ("agents", "*.md"),
    ("skills", "*.md"),
    ("workflows", "*.md"),
    ("workflows-js", "*.js"),
)


def _scan_targets(templates_dir: Path) -> tuple[tuple[Path, str], ...]:
    """Return the (directory, glob-pattern) pairs to scan under *templates_dir*."""
    return tuple((templates_dir / subdir, glob) for subdir, glob in _SCAN_TARGETS)


_PATH_KEYS: list[str] = [
    "tickets_inbox_path",
    "tickets_inbox_epics_path",
    "tickets_todo_path",
    "tickets_done_path",
    "tickets_rejected_path",
    "ticket_lifecycle_path",
    "docs_root",
    "precommit_autofix_config_path",
    "changelog_folder",
    "changelog_categories_path",
]

_NESTED_PATH_KEYS: dict[str, list[str]] = {
    "testing_context": ["readme_path", "test_root"],
}


def extract_script_path_refs(templates_dir: Path) -> set[str]:
    """Extract all script path references from source templates.

    Scans every ``.md`` file under ``templates_dir/agents/``,
    ``templates_dir/skills/``, and ``templates_dir/workflows/`` (recursive),
    plus every ``.js`` file under ``templates_dir/workflows-js/``, and returns
    the set of all script paths that match any of these patterns:

    - ``python3 scripts/<path>``
    - ``python scripts/<path>``
    - ``sys.path.insert(<N>, 'scripts/<path>')``
    - ``sys.path.insert(<N>, "scripts/<path>")``

    Each returned path string begins with ``"scripts/"`` (e.g.
    ``"scripts/ac_store/ac_prioritizer.py"``).  When a referenced path appears
    more than once across all scanned files it is deduplicated in the returned
    set.

    This function is the pre-build validation phase for AC BP-900b-1, extended
    to workflow sources by AC BP-900g-6.  It is intentionally read-only and
    never raises: unreadable files are silently skipped so the audit is
    always fail-open.

    Args:
        templates_dir: Path to the templates directory in the package root.
            The function looks for ``.md`` files under ``templates_dir/agents/``,
            ``templates_dir/skills/``, and ``templates_dir/workflows/``, and
            ``.js`` files under ``templates_dir/workflows-js/``.

    Returns:
        Set of ``scripts/<path>`` strings extracted from all matching
        references.  Returns an empty set when no matching references are
        found or when none of the scanned directories exist.
    """
    refs: set[str] = set()
    for scan_dir, glob_pattern in _scan_targets(templates_dir):
        if not scan_dir.exists():
            continue
        for source_file in scan_dir.rglob(glob_pattern):
            try:
                text = source_file.read_text(encoding="utf-8")
            except OSError:
                _log.debug("Skipping unreadable template: %s", source_file)
                continue
            for pattern in _SCRIPT_PATTERNS:
                for match in pattern.finditer(text):
                    refs.add(match.group(1))
    return refs


def extract_script_path_refs_with_sources(
    templates_dir: Path,
) -> dict[str, set[str]]:
    """Extract script path references mapped to the templates that reference them.

    Identical scanning logic to ``extract_script_path_refs()``, but instead of
    returning a flat set of script paths this function returns a mapping from
    each script path to the set of relative template paths (e.g.
    ``"agents/build-ac.md"`` or ``"workflows-js/finalize-feature.js"``) in
    which that script path was found.

    This richer shape is required by the broken-reference report (AC BP-900c-1)
    which must name the referencing template alongside the missing script path
    and a suggested action.

    Args:
        templates_dir: Path to the templates directory in the package root.
            The function looks for ``.md`` files under ``templates_dir/agents/``,
            ``templates_dir/skills/``, and ``templates_dir/workflows/``, and
            ``.js`` files under ``templates_dir/workflows-js/``.

    Returns:
        Dict mapping ``"scripts/<path>"`` strings to a set of relative
        template path strings (e.g. ``{"scripts/ac_store/ac_prioritizer.py":
        {"agents/build-ac.md"}}``).  Returns an empty dict when no matching
        references are found or when none of the scanned directories exist.
    """
    refs_to_sources: dict[str, set[str]] = {}
    for scan_dir, glob_pattern in _scan_targets(templates_dir):
        if not scan_dir.exists():
            continue
        for source_file in scan_dir.rglob(glob_pattern):
            try:
                text = source_file.read_text(encoding="utf-8")
            except OSError:
                _log.debug("Skipping unreadable template: %s", source_file)
                continue
            try:
                rel_path = source_file.relative_to(templates_dir).as_posix()
            except ValueError:
                rel_path = source_file.name
            for pattern in _SCRIPT_PATTERNS:
                for match in pattern.finditer(text):
                    script_path = match.group(1)
                    refs_to_sources.setdefault(script_path, set()).add(rel_path)
    return refs_to_sources


# ---------------------------------------------------------------------------
# Compiled-output scan targets (AC BP-900b-1, post-compile variant)
# ---------------------------------------------------------------------------
# Unlike _SCAN_TARGETS (source templates_dir/{agents,skills,workflows,workflows-js}),
# the compiled output tree has no workflows/ or workflows-js/ directory of its own —
# workflow bodies compile into commands/ under a different naming scheme that is out
# of scope for this AC. Only agents/ and skills/ are named in the Gherkin.
_COMPILED_SCAN_TARGETS: tuple[tuple[str, str], ...] = (
    ("agents", "*.md"),
    ("skills", "*.md"),
)


def extract_compiled_script_path_refs(compiled_root: Path) -> set[tuple[str, str]]:
    """Extract script path references from COMPILED agent/skill templates.

    This is the post-compile counterpart to ``extract_script_path_refs()``: the
    latter scans the SOURCE ``templates/`` tree before ``build.py`` writes any
    output; this function scans the COMPILED output tree (e.g.
    ``<target>/.claude``) after compilation, per AC BP-900b-1's Gherkin: "Given
    build.py has compiled agent templates and skill files to the output
    directory ... it scans every .md file in the compiled agents/ and skills/
    directories".

    Scans every ``.md`` file under ``compiled_root/agents/`` and
    ``compiled_root/skills/`` (recursive, so nested skill directories such as
    ``skills/some-skill/SKILL.md`` are covered) and extracts references
    matching the same three patterns as ``extract_script_path_refs()``:

    - ``python3 scripts/<path>``
    - ``python scripts/<path>``
    - ``sys.path.insert(<N>, 'scripts/<path>')``
    - ``sys.path.insert(<N>, "scripts/<path>")``

    Args:
        compiled_root: Path to the compiled output directory (e.g. the
            ``.claude`` directory written by a ``build.py --target-dir`` run).
            The function looks for ``.md`` files under
            ``compiled_root/agents/`` and ``compiled_root/skills/``.

    Returns:
        Set of ``(relative_template_path, "scripts/<path>")`` tuples, where
        ``relative_template_path`` is the ``.md`` file's path relative to
        ``compiled_root`` (POSIX-style, e.g. ``"agents/build-ac.md"`` or
        ``"skills/some-skill/SKILL.md"``). Returns an empty set when no
        matching references are found or when neither scanned directory
        exists. Intentionally read-only and never raises: unreadable files
        are silently skipped so the scan is always fail-open.
    """
    refs: set[tuple[str, str]] = set()
    for subdir, glob_pattern in _COMPILED_SCAN_TARGETS:
        scan_dir = compiled_root / subdir
        if not scan_dir.exists():
            continue
        for source_file in scan_dir.rglob(glob_pattern):
            try:
                text = source_file.read_text(encoding="utf-8")
            except OSError:
                _log.debug("Skipping unreadable compiled template: %s", source_file)
                continue
            try:
                rel_path = source_file.relative_to(compiled_root).as_posix()
            except ValueError:
                rel_path = source_file.name
            for pattern in _SCRIPT_PATTERNS:
                for match in pattern.finditer(text):
                    refs.add((rel_path, match.group(1)))
    return refs


def check_referential_integrity(
    target_root: Path,
    config: dict[str, Any],
) -> list[dict[str, str]]:
    """Validate that all path-valued fields in config point to existing files/dirs.

    Args:
        target_root: Absolute path to the target project root.
        config: The skills_config dict.

    Returns:
        List of dicts with keys: config_key (str), expected_path (str).
        Empty list means all referenced paths exist.
    """
    missing: list[dict[str, str]] = []

    for key in _PATH_KEYS:
        value = config.get(key)
        if not value or not isinstance(value, str):
            continue
        path = target_root / value
        if not path.exists():
            missing.append({"config_key": key, "expected_path": value})

    for parent_key, child_keys in _NESTED_PATH_KEYS.items():
        parent = config.get(parent_key)
        if not isinstance(parent, dict):
            continue
        for child_key in child_keys:
            value = parent.get(child_key)
            if not value or not isinstance(value, str):
                continue
            path = target_root / value
            if not path.exists():
                missing.append({
                    "config_key": f"{parent_key}.{child_key}",
                    "expected_path": value,
                })

    return missing


def format_integrity_report(missing: list[dict[str, str]]) -> str:
    """Format missing paths as a human-readable warning report.

    Args:
        missing: List of missing-path dicts from check_referential_integrity().

    Returns:
        Markdown-formatted report string, or empty string if no issues.
    """
    if not missing:
        return ""
    lines = [
        "## Referential Integrity Warnings",
        "",
        "The following paths are referenced in skills_config.json but do not exist:",
        "",
    ]
    for item in missing:
        lines.append(f"  - `{item['config_key']}` -> `{item['expected_path']}`")
    lines.append("")
    lines.append("These may cause downstream agents to fail. Run the onboard agent")
    lines.append("or create the missing files manually.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Intra-package dependency closure (AC BP-900g-8)
# ---------------------------------------------------------------------------
#
# Unlike the template-prose scan above, this scans a deployed Python SCRIPT's
# own AST for three ways it can resolve a sibling module belonging to the same
# package:
#
#   1. Static imports: ``import foo``, ``from foo import bar``, and relative
#      imports (``from . import foo``, ``from .foo import bar``). Resolved by
#      trying each plausible file-path candidate for the imported name and
#      keeping the ones that exist on disk under *root* -- existence-checking
#      is what keeps stdlib/third-party names (``import yaml``, ``import os``)
#      out of the closure without an allowlist: they simply never resolve to a
#      real file under the package root.
#   2. Dynamic loads: ``importlib.util.spec_from_file_location(name, path)``
#      where *path* is a statically-evaluable expression built from
#      ``Path(__file__)``, chained ``.parent`` attribute access, ``.resolve()``,
#      and ``/`` (division) against string literals -- the exact shape
#      generate_ticket_from_ac.py's ``_load_migration_map`` and
#      ``_load_derive_parent_id_fn`` use. When the expression is NOT reducible
#      to a concrete path this way, the reference is logged as a WARNING naming
#      the file and line for a human to verify -- never silently treated as
#      external. This is the documented static-analysis blind spot;
#      BP-900g-10 is the runtime backstop for it.
#   3. ``sys.path.insert(0, <dir-expression>)`` / ``sys.path.append(...)``
#      followed by a plain import that resolves against the pushed directory
#      rather than the script's own directory or the package root --
#      goal_to_epic.py's dual source/deployed-layout guard is the live
#      instance: ``sys.path.insert(0, str(_sibling_dir))`` then
#      ``from scan_ac_store import traverse_ac_tree``, where ``_sibling_dir``
#      is itself an ``if``/``else`` ternary over two statically-known
#      directories. Reuses the SAME statically-evaluable-expression handling
#      as (2) (including the ternary, resolved to both candidate directories
#      since which branch runs depends on a runtime condition) and gives an
#      unresolvable pushed-path argument the identical WARNING treatment as an
#      unresolvable dynamic loader argument -- there is no path through this
#      module where an unresolved intra-package reference produces zero log
#      output.
#
# The closure is TRANSITIVE: each newly-discovered dependency file is itself
# scanned for further sibling references, with a visited-set guarding against
# import cycles.


def _iter_same_scope(node: ast.AST) -> Any:
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
    if isinstance(node, ast.IfExp):
        body_paths = _eval_static_path(node.body, script, assignments, _seen)
        orelse_paths = _eval_static_path(node.orelse, script, assignments, _seen)
        if body_paths is None or orelse_paths is None:
            return None
        return body_paths + orelse_paths

    if isinstance(node, ast.Name):
        if node.id == "__file__" or node.id in _seen or node.id not in assignments:
            return None
        return _eval_static_path(
            assignments[node.id], script, assignments, _seen | {node.id}
        )

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _eval_static_path(node.left, script, assignments, _seen)
        if left is None:
            return None
        if isinstance(node.right, ast.Constant) and isinstance(node.right.value, str):
            return [path / node.right.value for path in left]
        return None

    if isinstance(node, ast.Attribute) and node.attr == "parent":
        base = _eval_static_path(node.value, script, assignments, _seen)
        return None if base is None else [path.parent for path in base]

    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "resolve":
            return _eval_static_path(node.func.value, script, assignments, _seen)
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "str"
            and len(node.args) == 1
        ):
            return _eval_static_path(node.args[0], script, assignments, _seen)
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "Path"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "__file__"
        ):
            return [script]

    return None


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
    root. ``goal_to_epic.py``'s ``run()`` is the live instance:
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


def _closure_walk(script: Path, root: Path, visited: set[Path], closure: set[str]) -> None:
    """Recursively add *script*'s resolvable intra-package dependencies to *closure*."""
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
            rel = candidate.resolve().relative_to(root).as_posix()
        except ValueError:
            continue
        if rel not in closure:
            closure.add(rel)
        _closure_walk(candidate.resolve(), root, visited, closure)


def compute_intra_package_closure(script: Path, root: Path) -> set[str]:
    """Return the transitive set of intra-package modules *script* resolves.

    Performs AST-based static analysis of *script* (and, transitively, every
    sibling module it resolves) to derive the set the AC calls Set A
    (``resolved_closure``): every module belonging to the same package that
    *script* imports, resolves via a relative import, or loads dynamically via
    ``importlib.util.spec_from_file_location`` with a statically-evaluable
    ``__file__``-relative path.

    This set is DERIVED from the code, never from a hand-maintained list: a
    module added to *script*'s imports (or to a dependency's imports) tomorrow
    is picked up automatically on the next call, with no list to edit.

    Args:
        script: Absolute path to the script to analyse.
        root: The directory that returned dependency strings are expressed
            relative to. Pass the package source root to analyse the SOURCE
            tree, or a deployed output root to analyse the DEPLOYED tree --
            the same function works unmodified against either, which is what
            lets a caller prove a dependency is actually shipped rather than
            merely present in source by construction.

    Returns:
        Set of root-relative POSIX path strings (e.g.
        ``"scripts/ac_store/_component_migration_map.py"``) for every
        intra-package module resolved, directly or transitively. Modules that
        do not resolve to a real file under *root* (standard library,
        third-party distributions, host-project paths) are never included --
        no allowlist is needed because non-existence under *root* is itself
        the discriminator.

        An empty set means the script genuinely resolves no intra-package
        modules. It never means the analysis failed -- that raises.

    Raises:
        ClosureAnalysisError: If *script*, or any module reached transitively
            from it, cannot be read or parsed. Callers must not treat this as
            an empty closure (KI-BP-022): the guard is a deployment preflight,
            and a script about to be deployed whose dependencies cannot be
            determined has not been checked.
    """
    closure: set[str] = set()
    _closure_walk(script.resolve(), root.resolve(), set(), closure)
    return closure


def find_uncovered_closure_dependencies(
    script_rel_path: str, root: Path, declared: set[str]
) -> set[str]:
    """Return closure entries for *script_rel_path* that are absent from *declared*.

    Implements the AC's binding-direction rule: Set B (*declared*, the deploy
    declaration) must CONTAIN closure(Set A). This function computes Set A via
    ``compute_intra_package_closure`` and returns the entries Set B is missing
    -- a non-empty result means the containment check has failed and the build
    must abort naming these entries.

    Args:
        script_rel_path: Root-relative POSIX path string to the script to
            analyse (e.g. ``"scripts/ac_store/generate_ticket_from_ac.py"``).
        root: The directory *script_rel_path* is relative to, and that closure
            entries are expressed relative to (see ``compute_intra_package_closure``).
        declared: The declared/deployed set to check the closure against (Set B).

    Returns:
        Set of root-relative path strings present in the script's closure but
        absent from *declared*. Empty when *declared* already contains the
        full closure.
    """
    closure = compute_intra_package_closure(root / script_rel_path, root)
    return closure - declared


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-14 [BrainCandy/BP-900g-6]: extract_script_path_refs() and
#   extract_script_path_refs_with_sources() scanned ONLY templates/agents/ and
#   templates/skills/ (.md). Workflow sources — templates/workflows-js/*.js
#   (JS orchestration engines) and templates/workflows/*.md (slash-command
#   bodies) — were completely unscanned, so a workflow that shells out to a
#   script the build never deploys was invisible to
#   _check_script_reference_guard(). This is the same defect class BP-900g-4
#   and BP-900g-5 closed for agent/skill templates, just in the workflow layer.
#   Fix: both functions now iterate a shared (subdirectory, glob) target list
#   (_SCAN_TARGETS) that adds ("workflows", "*.md") and ("workflows-js", "*.js")
#   alongside the existing ("agents", "*.md") and ("skills", "*.md") pairs. No
#   new regex was needed: _SCRIPT_PATTERNS is plain text matching and does not
#   care whether the surrounding syntax is Markdown prose or a JavaScript
#   string/backtick literal — only the directory and file extension differ per
#   source kind.
#
#   Template-literal decision: templates/workflows-js/*.js builds several script
#   paths with JS template-literal interpolation, e.g.
#   `${worktreePath}/scripts/build_orchestration/fast_lane.py` or
#   `${baselineTmpPath}/scripts/build.py`. These are DELIBERATELY NOT extracted.
#   A `${...}` prefix is not an output-root token — it is a JS variable holding
#   an arbitrary RUNTIME path (a worktree checkout, a temp baseline clone, a
#   caller-supplied script path) that need not be, and often is not, the
#   deployed package's output root. Treating any `${...}/` as equivalent to
#   `{{config.output_root}}/` or a dot-prefixed root would reopen the exact
#   over-wide-prefix failure mode _PYTHON_INVOKE_RE's bound was written to
#   prevent (EPIC-BuildGuardFalsePositive): e.g. `${baselineTmpPath}` legitimately
#   points at a full clone of the SOURCE repo, not the deployed output, so
#   resolving `${baselineTmpPath}/scripts/build.py` against the deployable
#   manifest would produce a false positive (build.py is a source-tree tool,
#   never a deployed artifact) — failing the build for a reference that was
#   never broken. Verified empirically: even leaving `${...}` prefixes
#   unextracted, adding the bare-form scan of templates/workflows-js/*.js
#   surfaces `scripts/pause_store.py` (referenced via the plain
#   `python scripts/pause_store.py ...` form in finalize-feature.js and
#   plan-feature.js) as a genuinely undeployed script — see the python-coder
#   BP-900g-6 sign-off comment for the exact list. That is a true positive this
#   ticket intentionally surfaces and does not fix (out of scope; the deploy
#   phase is another agent's job). Residual gap: a `${...}`-prefixed reference
#   to a genuinely undeployed script (e.g. `scripts/injection_builders.py` via
#   `${worktreePath}/scripts/injection_builders.py` in fast-lane-build.js)
#   remains invisible to this guard. Closing that gap needs a way to distinguish
#   "this JS variable mirrors the output root" from "this JS variable is an
#   arbitrary runtime path" — real static analysis, not a text regex — so it is
#   left as a documented follow-up rather than bolted on here. (#BP-900g-6)
# - 2026-08-18 [python-coder/EPIC-DeploymentCompleteness/05_BP-900b-1]: Added
#   extract_compiled_script_path_refs(), the post-compile counterpart to
#   extract_script_path_refs()/extract_script_path_refs_with_sources(). Those two
#   functions are wired into build.py's PRE-build guard (_check_script_reference_guard,
#   which runs before _run_phases() writes output) and scan the SOURCE templates_dir
#   tree. The AC's literal Gherkin describes a scan of the COMPILED agents/ and
#   skills/ directories after build.py has written them — no existing function
#   targeted that tree with the ticket's delivers_to shape (set[tuple[str, str]] of
#   (template_path, referenced_script_path), pairing each reference with its
#   referencing template rather than the flat set extract_script_path_refs()
#   returns). Reused the same _SCRIPT_PATTERNS regex set (no new pattern needed —
#   confirmed by a real-artifact behavioral test that runs build.py --target-dir
#   into a tmp_path and scans the real compiled .claude/agents and .claude/skills
#   directories, recovering scripts/ac_store/ac_prioritizer.py and
#   scripts/ac_store/generate_ticket_from_ac.py from real compiled agent
#   templates). Scoped to agents/ and skills/ only (per the Gherkin's literal
#   wording) — the compiled tree has no workflows/ or workflows-js/ directory of
#   its own, so _COMPILED_SCAN_TARGETS omits the workflow entries _SCAN_TARGETS
#   carries. This function is a standalone, read-only scan; wiring it into an
#   actual build.py post-compile phase is out of this ticket's files_touched
#   scope (scripts/build_propagation_audit.py, scripts/build_referential_integrity.py,
#   docs/architecture/components/template-compiler.md only — build.py is not
#   listed) and is left as a follow-up. (#BP-900b-1)
# ====================================================================
