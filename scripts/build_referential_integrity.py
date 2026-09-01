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
    AC BP-900g-8-ii widens Set A/Set B to also see NON-CODE (data/config) reads
    a deployed script performs -- a schema, a vocabulary, a registry, a data
    table -- on the same terms as a module import, through the SAME two
    functions and the SAME ``closure``/``uncovered`` sets, rather than a
    second, parallel notion of "data dependency". See the DECISION comment
    above ``_extract_data_file_read_candidates`` for the three detectors this
    requires (a data read is an ordinary function call against a
    possibly-constructed path, unlike an import's fixed syntactic declaration).
    A later fix within the same AC adds an optional ``data_root`` parameter to
    ``compute_intra_package_closure()``/``find_uncovered_closure_dependencies()``
    and a new ``compute_intra_package_closure_with_deploy_root_relative()``:
    a template-sourced family's MODULE root (e.g. ``<package_root>/templates``
    for the whole commit-guardian family) is the wrong base for a
    repo-root-relative data read such as ``config/doc_types.json`` -- relative
    to that root it never exists, so it was silently dropped. ``data_root``
    gives such a read a second, DEPLOY-rooted base to resolve against, and the
    ``_with_deploy_root_relative`` variant tells a namespacing caller
    (``build.py``) which entries came from which root, since the two must be
    namespaced differently (a deploy-root-relative entry must NOT receive the
    family's deploy-namespace prefix, or it lands at a path nothing deploys).
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

    # AC BP-900g-8-ii: ``package_root or _PACKAGE_ROOT``-shaped fallback
    # expressions (e.g. ``injection_builders.py``'s
    # ``root = package_root or _PACKAGE_ROOT``). Unlike ``IfExp`` above, a
    # runtime-only branch (a bare function parameter with no default here) must
    # NOT poison the whole expression -- at runtime exactly one operand wins,
    # and the module-level fallback operand is the one most commonly reachable
    # statically. Every operand that DOES resolve contributes its candidates;
    # an operand that does not (e.g. an unassigned parameter) is skipped rather
    # than treated as a hard failure the way IfExp's two required branches are.
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
        resolved: list[Path] = []
        for value in node.values:
            candidate = _eval_static_path(value, script, assignments, _seen)
            if candidate is not None:
                resolved.extend(candidate)
        return resolved or None

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
        # AC BP-900g-8-ii: a bare ``Path("<literal>")`` seed -- e.g.
        # ``validate_ac_schema.py``'s ``_SCHEMA_REL = Path("config") / ...``.
        # This produces a RELATIVE path fragment (never anchored at *script*),
        # meaningful only when later combined via ``/`` with something that IS
        # anchored (handled by the BinOp branch above).
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "Path"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            return [Path(node.args[0].value)]

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
            rel = candidate.resolve().relative_to(root).as_posix()
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


def compute_intra_package_closure(script: Path, root: Path, data_root: Path | None = None) -> set[str]:
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
        data_root: AC BP-900g-8-ii. The root a non-code (data/config) read is
            expressed against when it does NOT resolve under *root* -- see
            ``compute_intra_package_closure_with_deploy_root_relative`` for
            why a template-sourced family needs a second root and which
            entries land where. Defaults to *root* when omitted (module
            resolution and data resolution then share the single root the
            module half has always used, i.e. no behaviour change from
            before this AC for any caller that does not pass it).

    Returns:
        Set of root-relative POSIX path strings (e.g.
        ``"scripts/ac_store/_component_migration_map.py"``) for every
        intra-package module resolved, directly or transitively, UNIONED
        with every non-code (data/config) file resolved under *root* or
        *data_root* (AC BP-900g-8-ii). Modules that do not resolve to a real
        file under *root* (standard library, third-party distributions,
        host-project paths) are never included -- no allowlist is needed
        because non-existence under *root* is itself the discriminator.

        An empty set means the script genuinely resolves no intra-package
        modules. It never means the analysis failed -- that raises.

        This is a plain UNION: it does not tell a caller which entries came
        from *root* versus *data_root*, which a deploy-namespace-prefixing
        caller (``build.py``) needs to know. Use
        ``compute_intra_package_closure_with_deploy_root_relative`` for that.

    Raises:
        ClosureAnalysisError: If *script*, or any module reached transitively
            from it, cannot be read or parsed. Callers must not treat this as
            an empty closure (KI-BP-022): the guard is a deployment preflight,
            and a script about to be deployed whose dependencies cannot be
            determined has not been checked.
    """
    closure, _deploy_root_relative = compute_intra_package_closure_with_deploy_root_relative(
        script, root, data_root
    )
    return closure


def compute_intra_package_closure_with_deploy_root_relative(
    script: Path, root: Path, data_root: Path | None = None
) -> tuple[set[str], set[str]]:
    """Compute the closure like ``compute_intra_package_closure``, tagging deploy-root-only entries.

    AC BP-900g-8-ii's central-case regression: for a template-sourced family
    (e.g. commit-guardian, whose closure *root* is ``<package_root>/templates``
    so its sibling modules resolve correctly) a repo-root-relative data read
    such as ``config/doc_types.json`` is written the way the DEPLOYED script
    sees it -- relative to the deploy root, not the family's own source
    prefix. Resolving it against *root* alone makes it land at
    ``templates/config/doc_types.json``, which never exists, so it is
    silently dropped. Resolving it against *data_root* (the deploy root, e.g.
    *package_root*) instead makes it resolve correctly -- but a caller that
    then applies the family's deploy-namespace prefix uniformly (as
    ``build.py`` did before this fix) corrupts it a second way, turning
    ``config/doc_types.json`` into ``<family-prefix>config/doc_types.json``,
    a path nothing deploys either.

    This function reports which of the two roots produced each entry so a
    namespacing caller can treat them differently: prefix the *root*-relative
    ones (they need the SAME prefix a module dependency needs), and use the
    *data_root*-relative ones AS-IS (they are already expressed in final
    deploy-root-relative form).

    Args:
        script: Absolute path to the script to analyse.
        root: The module/family closure root (see ``compute_intra_package_closure``).
        data_root: The deploy root a data read resolves against when it does
            not resolve under *root*. Defaults to *root* (no split -- every
            entry is reported as family-relative, matching every caller's
            behaviour before this AC).

    Returns:
        A ``(closure, deploy_root_relative)`` pair. ``closure`` is the same
        union ``compute_intra_package_closure`` returns.
        ``deploy_root_relative`` is the subset of ``closure`` that resolved
        ONLY under *data_root*, never under *root*.

    Raises:
        ClosureAnalysisError: See ``compute_intra_package_closure``.
    """
    closure: set[str] = set()
    deploy_root_relative: set[str] = set()
    resolved_data_root = (data_root or root).resolve()
    _closure_walk(
        script.resolve(), root.resolve(), set(), closure, deploy_root_relative, resolved_data_root
    )
    return closure, deploy_root_relative


def find_uncovered_closure_dependencies(
    script_rel_path: str, root: Path, declared: set[str], data_root: Path | None = None
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
        data_root: AC BP-900g-8-ii. See ``compute_intra_package_closure``.
            Defaults to *root* when omitted.

    Returns:
        Set of root-relative path strings present in the script's closure but
        absent from *declared*. Empty when *declared* already contains the
        full closure.
    """
    closure = compute_intra_package_closure(root / script_rel_path, root, data_root=data_root)
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
#   [2026-09-01, BO-2400c-1-v: the example file fast-lane-build.js was an
#   orphaned second runner and has been deleted. The dated text above is left
#   as written. The residual gap it describes is still OPEN and still
#   unexercised by this guard — read the example as fast-lane-ship.js, which
#   carries the same `${worktreePath}/.leafcutter/scripts/injection_builders.py`
#   shape and is the lane that actually runs.]
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
