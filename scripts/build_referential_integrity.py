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
ARCHITECTURE: Three public functions. check_referential_integrity() validates path-valued
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
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

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
# ====================================================================
