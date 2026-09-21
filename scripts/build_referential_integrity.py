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

    AC BP-100n-4 (file-size refactor): the AST-analysis INTERNALS behind
    compute_intra_package_closure() / find_uncovered_closure_dependencies()
    -- ClosureAnalysisError, the _eval_static_path dispatcher family, the
    static-import / dynamic-loader / sys.path extractors, and the non-code
    data-file detectors -- now live in the sibling module
    build_referential_integrity_closure.py, imported back into this module
    so every existing caller is unaffected. See that module's own docstring
    for the AST-analysis detail, and the DECISION HISTORY at the tail of
    this module for why the split happened.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

# ClosureAnalysisError and _closure_walk moved to the sibling module
# build_referential_integrity_closure.py (AC BP-100n-4, file-size refactor --
# see this file's own DECISION HISTORY and that module's docstring). Both are
# imported straight back so every existing caller -- build.py's
# `from build_referential_integrity import (..., ClosureAnalysisError, ...)`,
# tests' `_bri.ClosureAnalysisError`, and this file's own
# compute_intra_package_closure_with_deploy_root_relative() below -- keeps
# working against this module unchanged; the split is invisible to callers.
from build_referential_integrity_closure import ClosureAnalysisError  # noqa: F401  # re-exported for callers
from build_referential_integrity_closure import _closure_walk

_log = logging.getLogger(__name__)


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
# Intra-package dependency closure (AC BP-900g-8) -- public entry surface
# ---------------------------------------------------------------------------
# AC BP-100n-4 (file-size refactor): the AST-based closure ANALYSIS internals
# -- ClosureAnalysisError, _closure_walk, and everything they in turn depend
# on (_eval_static_path and its handler family, the static-import / dynamic
# -loader / sys.path extractors, and the non-code data-file detectors) --
# moved to the sibling module build_referential_integrity_closure.py to bring
# this file back under its file-size cap after the earlier BP-100n-4
# complexity-reduction split grew it past the limit. Only the three PUBLIC
# entry points below stayed here: same signatures, same return shapes, same
# docstrings, same behaviour -- this is a pure move, not a rewrite. See
# build_referential_integrity_closure.py's own module docstring for the full
# picture of the AST analysis these three functions now delegate to via the
# ClosureAnalysisError / _closure_walk imported above.


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
# - 2026-09-14 [python-coder/BP-100n-4]: Complexity refactor, then a follow-up
#   file-size split, both pure (no behaviour change). Step 1: _eval_static_path
#   was measured at complexity 41 (over the check-complexity gate's threshold
#   of 15, as that gate prepares to register as a live pre-commit hook on this
#   branch) because it was a single function's sequence of ``if isinstance(node,
#   ...): ...`` branches for six mutually-exclusive AST node shapes, four of
#   them themselves multi-branch ``ast.Call`` sub-shapes. Extracted one
#   module-level handler function per shape (_eval_ifexp_path,
#   _eval_or_boolop_path, _eval_name_path, _eval_binop_div_path,
#   _eval_parent_attr_path, and _eval_call_path's own four
#   _eval_call_*_path sub-handlers), dispatched via _STATIC_PATH_HANDLERS /
#   _CALL_PATH_HANDLERS tuples tried in order -- safe because the shapes are
#   mutually exclusive by AST node type, so exactly one handler's isinstance
#   guard can ever pass for a given node. _eval_static_path itself drops to
#   complexity 3. Step 2: decomposing in place grew this file's own
#   check-file-size-counted length from 1039 to 1151 (the file was already
#   over its 400-line cap, so growth of an already-oversized file is refused
#   outright rather than judged against the absolute limit) -- the complexity
#   win had traded into size debt on a file that was already in debt. Moved
#   ALL the AST-analysis internals (ClosureAnalysisError, _closure_walk, and
#   everything _closure_walk depends on, including every function this
#   refactor step just extracted) to the new sibling module
#   build_referential_integrity_closure.py, leaving only the three PUBLIC
#   entry points (compute_intra_package_closure,
#   compute_intra_package_closure_with_deploy_root_relative,
#   find_uncovered_closure_dependencies) and the pre-existing script-path-ref
#   scanning functions here. Every moved function's body, docstring, and log
#   message is byte-for-byte identical to before the move -- see that
#   module's own DECISION HISTORY entry for the logger-name pin this move
#   required to preserve a caplog-based test assertion. No new deploy_map /
#   shim_map entry was needed: like its sibling build_helpers.py,
#   build_phases.py, and build_phases_*.py modules, build_referential_
#   integrity.py (and now its new sibling) is a plain, git-tracked
#   scripts/*.py source file imported directly by build.py at build time from
#   this repo's own scripts/ directory -- it is neither deployed wholesale to
#   consumer projects via the commit_guardian rglob path, nor invoked by any
#   consumer-facing agent template via the scripts/ac_store/ hardcoded
#   deploy_map path, so neither applies here. Confirmed by grep: no other
#   sibling build_*.py helper module (build_helpers.py, build_phases_
#   knowledge.py, build_phases_self_description.py, build_precommit.py) has a
#   deploy_map or shim_map entry either. (#BP-100n-4)
# ====================================================================
