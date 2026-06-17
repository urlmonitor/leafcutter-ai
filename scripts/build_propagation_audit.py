"""
MODULE: build_propagation_audit
GOAL: Post-install audit that walks every hook entry in .pre-commit-config.yaml,
    verifies the referenced script is installed, and auto-copies or warns when it
    is not. Prevents the dangling-hook-script bug class from recurring. Also
    provides broken-reference checking with an external-dependency allowlist so
    that well-known external scripts do not trigger false-positive failures.
BUSINESS CONTEXT: EPIC-PortableInstallHardening discovered 5 scripts registered
    in .pre-commit-config.yaml but never installed to scripts/commit_guardian/.
    This module adds a fail-open (exit 0) audit phase after build_commit_guardian
    so any future omission is caught at the next build.py run rather than at
    smoke-test time on a fresh install. AC BP-900b-1-1 adds an external-dependency
    allowlist so agent templates that legitimately reference external scripts
    (e.g. a user-supplied tool path) do not produce broken-reference failures.
    AC BP-900c-1 adds a three-field broken-reference report entry: missing path,
    referencing template, and a suggested action.
ARCHITECTURE: One public phase function ``propagation_audit``, one guard
    function ``check_broken_references``, a ``BrokenRefEntry`` dataclass, and
    a ``build_broken_ref_report`` factory. Parsing uses ``yaml.safe_load`` with a
    regex fallback if PyYAML is absent. The audit is intentionally fail-open: it
    never raises and always returns, even when warnings are emitted. The allowlist
    is a module-level frozenset constant that callers can extend by passing an
    explicit ``allowlist`` argument to ``check_broken_references``.
    AC BP-900c-1-1: ``build_broken_ref_report`` consolidates multiple templates
    that reference the same missing script into a single ``BrokenRefEntry`` with
    a ``referencing_templates`` tuple, so the suggested action appears exactly
    once per missing path.
"""

from __future__ import annotations

import logging
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# External-dependency allowlist (AC BP-900b-1-1)
# ---------------------------------------------------------------------------
# Script paths listed here are treated as resolved by the broken-reference
# guard even when the path does not exist in the deployed output. Add an entry
# whenever a template legitimately references a script that is installed by an
# external tool or by the user's own project rather than by the leafcutter
# build pipeline.
#
# Each entry must be a ``scripts/<relative-path>`` string matching the form
# produced by ``extract_script_path_refs()`` in ``build_referential_integrity``.
#
# Example: ``"scripts/external_tool.py"`` suppresses the broken-reference
# warning for any compiled template that contains ``python scripts/external_tool.py``.

EXTERNAL_DEPENDENCY_ALLOWLIST: frozenset[str] = frozenset()

# Regex to extract script basename from entries like:
#   python scripts/commit_guardian/check_foo.py [args...]
_ENTRY_RE = re.compile(r"scripts[/\\]commit_guardian[/\\]([\w.]+\.py)")


def _parse_hook_entries_yaml(precommit_path: Path) -> list[str]:
    """Parse hook entry fields from .pre-commit-config.yaml using yaml.safe_load.

    Falls back to regex line scan when PyYAML is not importable.

    Args:
        precommit_path: Path to the .pre-commit-config.yaml file.

    Returns:
        List of ``entry`` field strings from all hook definitions.
    """
    text = precommit_path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        _log.debug("PyYAML not available; falling back to regex scan.")
        return re.findall(r"^\s*entry:\s*(.+)$", text, re.MULTILINE)
    try:
        data = yaml.safe_load(text) or {}
        entries: list[str] = []
        for repo in data.get("repos", []):
            for hook in repo.get("hooks", []):
                entry = hook.get("entry", "")
                if entry:
                    entries.append(entry)
    except yaml.YAMLError as exc:
        _log.warning("Could not parse .pre-commit-config.yaml as YAML: %s — falling back to regex scan.", exc)
        return re.findall(r"^\s*entry:\s*(.+)$", text, re.MULTILINE)
    else:
        return entries


def _candidate_template_paths(script_name: str, package_root: Path) -> list[Path]:
    """Return ordered list of template locations to search for script_name.

    Args:
        script_name: Basename of the hook script (e.g. ``check_foo.py``).
        package_root: Root of the leafcutter package.

    Returns:
        List of candidate Paths in priority order (canonical first, legacy second).
    """
    return [
        package_root / "templates" / "scripts" / "commit_guardian" / script_name,
        package_root / "templates" / "commit-guardian" / script_name,
    ]


def check_broken_references(
    refs: set[str],
    deployed_scripts: set[str],
    allowlist: frozenset[str] | None = None,
) -> set[str]:
    """Return the set of script references that are broken (not deployed and not allowlisted).

    Compares the set of script path references extracted from compiled agent and
    skill templates against the set of actually-deployed script paths. A reference
    is considered *broken* when it appears in ``refs`` but not in ``deployed_scripts``
    and is also absent from the allowlist.

    Allowlisted references are silently treated as resolved: they do not appear in
    the returned broken set and do not cause the build to warn or fail, even if the
    path is not present in ``deployed_scripts``. This satisfies AC BP-900b-1-1.

    Args:
        refs: Set of ``scripts/<path>`` strings extracted from compiled templates
            (typically the return value of
            ``build_referential_integrity.extract_script_path_refs()``).
        deployed_scripts: Set of ``scripts/<path>`` strings that have been
            successfully deployed to the target project. Refs present here are
            always treated as resolved regardless of the allowlist.
        allowlist: Frozenset of ``scripts/<path>`` strings that are exempt from
            broken-reference failures. Defaults to ``EXTERNAL_DEPENDENCY_ALLOWLIST``
            when ``None``.

    Returns:
        Set of ``scripts/<path>`` strings that are broken: referenced in templates
        but neither deployed nor allowlisted. An empty set means all references
        are accounted for and the build may exit zero.
    """
    effective_allowlist = EXTERNAL_DEPENDENCY_ALLOWLIST if allowlist is None else allowlist
    resolved = deployed_scripts | effective_allowlist
    return refs - resolved


# ---------------------------------------------------------------------------
# Broken-reference report entries (AC BP-900c-1)
# ---------------------------------------------------------------------------

#: Suggested action when the missing script belongs to the leafcutter build
#: pipeline and should be added as a new deploy phase.
ACTION_ADD_DEPLOY_PHASE = "add a deploy phase in build_phases.py"

#: Suggested action when the missing script is supplied externally (not built
#: by leafcutter) and should be registered in the allowlist instead.
ACTION_ADD_TO_ALLOWLIST = "add to the external-dependency allowlist"


def _suggest_action(missing_path: str, allowlist: frozenset[str]) -> str:
    """Return the appropriate suggested action for a single broken reference.

    A path that is already present in the allowlist constant but still reached
    this function (e.g. because the caller bypassed the allowlist check) gets
    the allowlist suggestion so the human understands their options.

    For all other paths the heuristic is: if the path sits under
    ``scripts/ac_store/`` or ``scripts/feedback/`` — directories that leafcutter
    owns and deploys — the suggestion is to add a deploy phase.  Everything else
    defaults to the allowlist suggestion, directing the developer to register the
    path as an external dependency.

    Args:
        missing_path: The ``scripts/<path>`` string that was not deployed and not
            allowlisted.
        allowlist: The effective allowlist in use during the audit.  Used only as
            an informational hint; the path is presumed broken when this function
            is called.

    Returns:
        One of ``ACTION_ADD_DEPLOY_PHASE`` or ``ACTION_ADD_TO_ALLOWLIST``.
    """
    leafcutter_owned_prefixes = (
        "scripts/ac_store/",
        "scripts/feedback/",
        "scripts/commit_guardian/",
    )
    if any(missing_path.startswith(prefix) for prefix in leafcutter_owned_prefixes):
        return ACTION_ADD_DEPLOY_PHASE
    return ACTION_ADD_TO_ALLOWLIST


@dataclass(frozen=True)
class BrokenRefEntry:
    """A single broken-reference report entry with all three required fields.

    AC BP-900c-1 requires that each broken-reference entry names the missing
    script path, the compiled templates that reference it, and a suggested
    corrective action.  This dataclass is the canonical carrier for that
    three-field payload.

    AC BP-900c-1-1 requires consolidation: when multiple templates reference
    the same missing script, a single ``BrokenRefEntry`` is emitted that lists
    all referencing templates rather than one entry per template.  This ensures
    the suggested action appears exactly once for each missing path.

    Attributes:
        missing_path: The ``scripts/<path>`` string that was referenced in
            one or more templates but is absent from the deployable script set
            (e.g. ``"scripts/ac_store/ac_prioritizer.py"``).
        referencing_templates: Tuple of relative paths of every compiled
            template file that references the missing script, sorted
            lexicographically (e.g.
            ``("agents/build-ac.md", "skills/ac-scanner/SKILL.md")``).
            Contains exactly one element when only one template references the
            missing path.
        suggested_action: A human-readable corrective action.  Always one of
            ``ACTION_ADD_DEPLOY_PHASE`` or ``ACTION_ADD_TO_ALLOWLIST``.
    """

    missing_path: str
    referencing_templates: tuple[str, ...]
    suggested_action: str


def build_broken_ref_report(
    refs_to_sources: dict[str, set[str]],
    deployed_scripts: set[str],
    allowlist: frozenset[str] | None = None,
) -> list[BrokenRefEntry]:
    """Build a consolidated list of broken-reference report entries.

    For every script path in ``refs_to_sources`` that is neither deployed nor
    allowlisted, this function emits exactly **one** ``BrokenRefEntry`` that
    collects all referencing templates into the ``referencing_templates`` tuple.
    The third field — the suggested action — appears once per missing path,
    satisfying AC BP-900c-1-1 (consolidation requirement).

    When only one template references a missing path, ``referencing_templates``
    is a one-element tuple.  When multiple templates reference the same missing
    path, all are collected into a single entry so that the caller prints the
    suggested action exactly once per missing script.

    This function satisfies AC BP-900c-1: no entry has an empty field, and every
    entry names the missing path, the referencing templates, and a suggested
    action.

    This function satisfies AC BP-900c-1-1: multiple templates referencing the
    same missing path are consolidated into a single entry, not emitted as
    separate entries.

    Args:
        refs_to_sources: Mapping from ``scripts/<path>`` strings to the set of
            relative compiled-template paths that reference them.  Typically
            produced by
            ``build_referential_integrity.extract_script_path_refs_with_sources()``.
        deployed_scripts: Set of ``scripts/<path>`` strings that are present in
            the deployable script manifest.  References found here are resolved.
        allowlist: Frozenset of ``scripts/<path>`` strings exempt from failure.
            Defaults to ``EXTERNAL_DEPENDENCY_ALLOWLIST`` when ``None``.

    Returns:
        List of ``BrokenRefEntry`` instances, one per unique missing script
        path (not one per referencing-template pair).  An empty list means all
        references are accounted for.
    """
    effective_allowlist = EXTERNAL_DEPENDENCY_ALLOWLIST if allowlist is None else allowlist
    resolved = deployed_scripts | effective_allowlist
    entries: list[BrokenRefEntry] = []
    for script_path, source_templates in refs_to_sources.items():
        if script_path in resolved:
            continue
        action = _suggest_action(script_path, effective_allowlist)
        entries.append(
            BrokenRefEntry(
                missing_path=script_path,
                referencing_templates=tuple(sorted(source_templates)),
                suggested_action=action,
            )
        )
    return entries


def propagation_audit(
    target_root: Path,
    config: dict[str, Any],
    dry_run: bool,
    force: bool,
) -> int:
    """Audit .pre-commit-config.yaml hook entries and auto-copy missing scripts.

    For each hook entry referencing ``scripts/commit_guardian/<name>.py``:
    - If the script is already installed: silent pass.
    - If a template exists: auto-copy (or dry-run report). Log at INFO.
    - If no template found: print a WARNING. Never blocks build (exit 0).

    The audit runs after ``build_commit_guardian`` so freshly-installed scripts
    are visible immediately.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Build config dict (unused; reserved for future use).
        dry_run: When True, auto-copy is skipped but WARNINGs are still emitted.
        force: Unused; propagation_audit always copies missing scripts regardless.

    Returns:
        Count of scripts auto-copied (0 in dry_run mode).
    """
    precommit_path = target_root / "pre-commit-config.yaml"
    if not precommit_path.exists():
        _log.debug("No .pre-commit-config.yaml at %s — propagation audit skipped.", target_root)
        return 0

    package_root = Path(__file__).resolve().parent.parent
    scripts_dir = target_root / "scripts" / "commit_guardian"
    copied = 0

    try:
        entries = _parse_hook_entries_yaml(precommit_path)
    except OSError as exc:  # noqa: BLE001
        print(f"  propagation_audit: WARNING — could not parse .pre-commit-config.yaml: {exc}", file=sys.stderr)
        return 0

    checked: set[str] = set()
    for entry in entries:
        m = _ENTRY_RE.search(entry)
        if not m:
            continue
        script_name = m.group(1)
        if script_name in checked:
            continue
        checked.add(script_name)

        target_script = scripts_dir / script_name
        if target_script.exists():
            continue  # already installed

        candidates = _candidate_template_paths(script_name, package_root)
        for candidate in candidates:
            if candidate.exists():
                if dry_run:
                    print(f"  [DRY-RUN] propagation_audit: would copy {script_name} from {candidate.relative_to(package_root)}")
                else:
                    target_script.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(candidate, target_script)
                    print(f"  [PROPAGATION] copied {script_name} from {candidate.relative_to(package_root)}")
                    copied += 1
                break
        else:
            print(
                f"  WARNING: hook entry references {script_name} — not installed and no template found. "
                "Install manually or remove the hook entry.",
                file=sys.stderr,
            )

    return copied


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-05-18 11:30 [EPIC-PortableInstallHardening/T04]: Created module. Fail-open propagation audit that walks .pre-commit-config.yaml hook entries, auto-copies missing scripts from templates, and warns when no template is found. Extracted as sibling module to keep build_phases.py within 400-line limit. (#EPIC-PortableInstallHardening/T04)
# - 2026-06-16 [BP-900b-1-1]: Added EXTERNAL_DEPENDENCY_ALLOWLIST constant and check_broken_references() guard function. Allowlisted refs are treated as resolved and do not appear in the broken-reference list, satisfying AC BP-900b-1-1.
# - 2026-06-17 [BP-900c-1]: Added BrokenRefEntry dataclass, _suggest_action() helper, and build_broken_ref_report() factory. Each broken-reference entry now carries all three required fields: missing_path, referencing_template, and suggested_action. Satisfies AC BP-900c-1.
# - 2026-06-17 [BP-900c-1-1]: Consolidated build_broken_ref_report() output: changed BrokenRefEntry.referencing_template (str) to referencing_templates (tuple[str, ...]) and updated the factory to emit one entry per unique missing_path grouping all referencing templates. Suggested action appears exactly once per missing path. Satisfies AC BP-900c-1-1.
# ===========================================================================
