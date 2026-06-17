"""
MODULE: build
GOAL: CLI entry point and orchestrator for the leafcutter build system.
BUSINESS CONTEXT: The leafcutter package materialises agent/skill
    templates into a target project by resolving skills_config.json values and
    stripping metadata. This module owns the CLI, config loading, validation,
    and build-phase dispatch. Actual phase logic lives in build_phases.py;
    template compilation in template_compiler.py; config I/O in config_loader.py;
    manifest writing and supplementary helpers in build_helpers.py.
ARCHITECTURE: Three-layer delegation. build.py -> build_phases.py (nine phase
    functions) -> template_compiler.py (parse, strip, inject, compile). Config
    loading and validation are in config_loader.py. Overwrites existing files by
    default so that template edits always reach the target project; use
    --no-overwrite to restore the legacy skip-existing behaviour. Supports
    --dry-run and --validate-only. A compare-before-write guard in write_file
    (and in build_phases._write) skips byte-identical files to eliminate mtime
    churn; the summary reports written vs up-to-date counts separately.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from config_loader import load_config, validate_config, _JSONSCHEMA_AVAILABLE  # noqa: F401
from build_phases import (
    build_agents,
    build_workflow_scripts,
    build_ac_store,
    build_skills,
    build_commands,
    build_workflows,
    build_hooks,
    build_rules,
    build_ticket_lifecycle,
    build_commit_guardian,
    build_precommit_config,
    build_doc_compliance,
    build_feedback,
    build_vision,
    build_components_registry,
    build_antigravity_instructions,
    build_sync_platforms,
    build_ac_store_docs,
    build_agent_cards,
    validate_agent_self_description,
    reset_uptodate_count,
    get_uptodate_count,
    clean_stale_artifacts,
    build_workflow_tools,
    build_knowledge_scripts,
    build_template_standalone_scripts,
)
from registry_validator import validate_agent_registry
from project_context_discovery import (  # noqa: F401 — re-exported for callers
    find_project_contexts,
    get_project_context_metadata,
)
from build_helpers import (
    seed_docs as _seed_docs,
    update_diagrams as _update_diagrams,
    install_shims as _install_shims,
    install_hooks as _install_hooks,
    write_build_manifest,
)
from build_glossary import build_glossary
from build_propagation_audit import (
    propagation_audit,
    build_broken_ref_report,
    emit_broken_ref_report_jsonl,
)
from build_claude_settings import build_claude_settings
from build_roadmap_phase import build_roadmap
from build_placeholder_detection import scan_for_placeholders, format_placeholder_report
from build_referential_integrity import (
    check_referential_integrity,
    format_integrity_report,
    extract_script_path_refs_with_sources,
)
from build_config_scaffolds import build_config_scaffolds
from build_ac_store_scaffold import build_ac_store_scaffold
from build_halt_guard import (
    check_halt_guard,
    format_migration_notice,
    write_lock_file,
    _resolve_package_sha,
)
from build_colors import (
    BOLD,
    RESET,
    GREEN,
    DIM,
    warn as _warn,
    error as _error,
    success as _success,
    dry_run as _dry_run_msg,
    heading as _heading,
)
from release.compute_next_version import (
    _resolve_repo_root as _cnv_resolve_repo_root,
    _resolve_changelogs_dir as _cnv_resolve_changelogs_dir,
    _find_last_version_tag,
    _changelog_entries_since,
    _compute_bump,
    _bump_version,
)
# Re-export for backward compatibility with tests that access via _build.*
from template_compiler import (  # noqa: F401
    parse_frontmatter,
    strip_metadata_sections,
    inject_config,
)


# ---------------------------------------------------------------------------
# File-write helpers (used by tests via _build.write_file)
# ---------------------------------------------------------------------------

def should_overwrite(target: Path, force: bool) -> bool:
    """Return True if the file should be written (either does not exist or force is True).

    The CLI default passes ``force=True`` so that every build run keeps
    materialised outputs in sync with their templates. Pass ``force=False``
    (via ``--no-overwrite``) to restore the legacy skip-existing behaviour
    where only absent files are written.

    Args:
        target: Absolute path to the output file to check.
        force: When True, existing files are overwritten; when False, only
            missing files are written.

    Returns:
        True if the file does not exist or ``force`` is True; False otherwise.
    """
    return not target.exists() or force


def write_file(target: Path, content: str, dry_run: bool, force: bool) -> bool:
    """Write content to target file, respecting dry-run and force flags.

    Adds a compare-before-write guard: when the target already exists and the
    encoded content is byte-identical to what is already on disk, the write is
    skipped and False is returned.  This eliminates mtime churn and spurious
    ``git status`` entries for files whose content did not change between
    builds.  Binary or unreadable files fall through to an unconditional write
    (UnicodeDecodeError / OSError are caught and silently ignored).

    In dry-run mode, prints what would happen but does not write. Creates
    parent directories as needed.

    Args:
        target: Absolute path to the destination file.
        content: Text content to write (UTF-8 encoded).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files; when False, skips them.

    Returns:
        True if anything was (or would be in dry-run mode) written; False if
        the file was skipped because it already existed and either force was
        False or the on-disk content was byte-identical to ``content``.
    """
    if not should_overwrite(target, force):
        return False
    if dry_run:
        _dry_run_msg(f"would write {target}")
        return True
    # Compare-before-write: skip if on-disk content is byte-identical.
    # This check runs only for real writes; dry-run always reports True
    # (intent to write) regardless of on-disk state.
    if target.exists():
        try:
            existing = target.read_text(encoding="utf-8")
            if existing == content:
                return False
        except (UnicodeDecodeError, OSError):
            pass  # Binary or unreadable file — fall through to write.
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Validation helpers (extracted to keep main() below complexity threshold)
# ---------------------------------------------------------------------------

def _handle_config_errors(errors: list[str], validate_only: bool, dry_run: bool) -> int:
    """Print config errors and return exit code (0 to continue, 1 to abort).

    Called only when ``validate_config`` returns a non-empty list. Returns 1
    when the errors are fatal; 0 when they are advisory (e.g. jsonschema
    unavailable) and the build should continue.

    Args:
        errors: Non-empty list of validation error strings from validate_config.
        validate_only: When True, validation errors are always fatal.
        dry_run: When True, non-fatal errors emit a warning and build continues.

    Returns:
        0 if the build should continue despite the errors, 1 to abort.
    """
    for err in errors:
        _error(f"[CONFIG] {err}")
    if validate_only or not dry_run:
        if not _JSONSCHEMA_AVAILABLE:
            _warn("Skipping validation (jsonschema not installed).")
            return 0
        if errors[0].startswith("jsonschema"):
            _warn("jsonschema unavailable — proceeding without strict validation.")
            return 0
        return 1
    return 0


def _handle_registry_errors(errors: list[str], dry_run: bool) -> int:
    """Print registry errors and return exit code (0 to continue, 1 to abort).

    Args:
        errors: Non-empty list of error strings from validate_agent_registry.
        dry_run: When True, registry errors are non-fatal (build continues with
            a printed warning).

    Returns:
        0 if the build should continue, 1 to abort.
    """
    for err in errors:
        _error(f"[REGISTRY] {err}")
    return 0 if dry_run else 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _inject_file_size_limits(config: dict, package_root: Path) -> None:
    """Inject file-size limit values from commit_guardian.json into the config dict.

    Reads ``file_size.line_limits[".py"]`` from the commit-guardian template JSON
    and adds ``file_size_limit_py`` to ``config`` so that agent templates can
    reference it as ``{{config.file_size_limit_py}}`` without hardcoding the number.

    Falls back to ``file_size.default_limit``, then to ``400`` if the JSON is
    absent or malformed.

    Args:
        config: The mutable config dict returned by ``load_config``; modified
            in-place with the new ``file_size_limit_py`` key.
        package_root: Absolute path to the leafcutter package root,
            used to locate ``templates/scripts/commit_guardian/commit_guardian.json``.
    """
    cg_path = package_root / "templates" / "scripts" / "commit_guardian" / "commit_guardian.json"
    if not cg_path.exists():
        # Fall back to legacy path for backward compatibility
        cg_path = package_root / "templates" / "commit-guardian" / "commit_guardian.json"
    py_limit: int = 400  # ultimate fallback
    try:
        with cg_path.open(encoding="utf-8") as fh:
            cg = json.load(fh)
        file_size = cg.get("file_size", {})
        py_limit = (
            file_size.get("line_limits", {}).get(".py")
            or file_size.get("default_limit")
            or 400
        )
        py_limit = int(py_limit)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass  # Fallback already set to 400
    config["file_size_limit_py"] = py_limit


def _inject_changelogs_dir(config: dict, package_root: Path) -> None:
    """Inject changelogs_dir from commit_guardian.json into the config dict.

    Reads changelogs_dir from the commit-guardian template JSON and adds
    changelog_folder to config so that the changelog-agent template
    can reference it as {{config.changelog_folder}}.

    Falls back to "changelogs/" when the JSON is absent or malformed.

    Args:
        config: The mutable config dict returned by load_config; modified
            in-place with the new changelog_folder key.
        package_root: Absolute path to the leafcutter package root,
            used to locate templates/scripts/commit_guardian/commit_guardian.json.
    """
    cg_path = package_root / "templates" / "scripts" / "commit_guardian" / "commit_guardian.json"
    if not cg_path.exists():
        cg_path = package_root / "templates" / "commit-guardian" / "commit_guardian.json"
    changelogs_dir: str = "changelogs/"
    try:
        with cg_path.open(encoding="utf-8") as fh:
            cg = json.load(fh)
        raw = cg.get("changelogs_dir", "changelogs")
        changelogs_dir = raw.rstrip("/") + "/"
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    config["changelog_folder"] = changelogs_dir


def _validate_all(config: dict, package_root: Path, validate_only: bool, dry_run: bool) -> int:
    """Run config and registry validation and return an exit code.

    Returns 0 to continue, 1 to abort.

    Args:
        config: Loaded config dict from load_config.
        package_root: Root of the leafcutter package.
        validate_only: When True, validation errors are always fatal.
        dry_run: When True, non-fatal errors emit a warning and build continues.

    Returns:
        0 if the build should continue, 1 to abort.
    """
    errors = validate_config(config)
    if errors:
        if _handle_config_errors(errors, validate_only, dry_run):
            return 1
    registry_errors = validate_agent_registry(package_root)
    if registry_errors:
        if _handle_registry_errors(registry_errors, dry_run):
            return 1
    return 0


def _manifest_ac_store_scripts(package_root: Path) -> set[str]:
    """Return ``scripts/ac_store/<name>`` entries for all non-.pyc source files.

    Scans ``package_root/scripts/ac_store/`` and returns one manifest entry per
    file, matching what ``build_ac_store`` deploys to the target project.

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        Set of ``scripts/ac_store/<name>`` strings, or empty set when absent.
    """
    result: set[str] = set()
    src = package_root / "scripts" / "ac_store"
    if src.is_dir():
        for f in src.iterdir():
            if f.is_file() and f.suffix != ".pyc":
                result.add(f"scripts/ac_store/{f.name}")
    return result


def _manifest_commit_guardian_scripts(package_root: Path) -> set[str]:
    """Return ``scripts/commit_guardian/<rel>`` entries for all template .py files.

    Scans both ``templates/scripts/commit_guardian/`` (canonical) and
    ``templates/commit-guardian/`` (legacy) and unions their ``.py`` files.
    Scanning both paths prevents false positives for scripts that reside only in
    the legacy location (e.g. ``check_v2_ac_store_alignment.py``).

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        Set of ``scripts/commit_guardian/<rel>`` strings, or empty set when
        both source directories are absent.
    """
    result: set[str] = set()
    for src in (
        package_root / "templates" / "scripts" / "commit_guardian",
        package_root / "templates" / "commit-guardian",
    ):
        if src.is_dir():
            for f in src.rglob("*"):
                if f.is_file() and f.suffix == ".py":
                    result.add(f"scripts/commit_guardian/{f.relative_to(src).as_posix()}")
    return result


def _manifest_feedback_scripts(package_root: Path) -> set[str]:
    """Return ``scripts/feedback/<name>`` entries for all source .py files.

    Scans ``package_root/scripts/feedback/`` dynamically, eliminating the
    previous hardcoded three-name list that caused Class A false positives for
    ``aggregate.py`` and ``resolve_feedback.py``.

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        Set of ``scripts/feedback/<name>`` strings, or empty set when absent.
    """
    result: set[str] = set()
    src = package_root / "scripts" / "feedback"
    if src.is_dir():
        for f in src.iterdir():
            if f.is_file() and f.suffix == ".py":
                result.add(f"scripts/feedback/{f.name}")
    return result


def _manifest_workflow_tool_scripts(package_root: Path) -> set[str]:
    """Return ``scripts/<name>`` entries for workflow-tool scripts deployed by build_workflow_tools.

    Scans the package source for the four workflow-tool scripts and returns
    manifest entries for those that exist.

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        Set of ``scripts/<name>`` strings for deployable workflow-tool scripts.
    """
    result: set[str] = set()
    scripts_src = package_root / "scripts"
    for fname in (
        "add_component.py",
        "knowledge_query.py",
        "set_ticket_status.py",
        "ticket_prioritizer.py",
    ):
        if (scripts_src / fname).is_file():
            result.add(f"scripts/{fname}")
    return result


def _manifest_knowledge_scripts(package_root: Path) -> set[str]:
    """Return ``scripts/knowledge/<name>`` entries for knowledge scripts deployed by build_knowledge_scripts.

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        Set of ``scripts/knowledge/<name>`` strings for deployable knowledge scripts.
    """
    result: set[str] = set()
    knowledge_src = package_root / "scripts" / "knowledge"
    for fname in ("harvest_learnings.py",):
        if (knowledge_src / fname).is_file():
            result.add(f"scripts/knowledge/{fname}")
    return result


def _manifest_template_standalone_scripts(package_root: Path) -> set[str]:
    """Return ``scripts/<name>`` entries for standalone scripts from ``templates/scripts/``.

    Scans the top-level ``templates/scripts/`` directory (non-recursive) for
    ``.py`` files and returns manifest entries.  These are deployed by
    ``build_template_standalone_scripts``.

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        Set of ``scripts/<name>`` strings for deployable template-standalone scripts.
    """
    result: set[str] = set()
    templates_scripts = package_root / "templates" / "scripts"
    if templates_scripts.is_dir():
        for f in templates_scripts.glob("*.py"):
            if f.is_file():
                result.add(f"scripts/{f.name}")
    return result


def _get_source_deployable_scripts(package_root: Path) -> set[str]:
    """Compute the set of script paths that build.py will deploy from package source.

    Delegates to per-phase helper functions and unions their results.  Seven
    deployment locations are covered:

    * ``scripts/ac_store/`` — from ``_manifest_ac_store_scripts``.
    * ``scripts/commit_guardian/`` — from ``_manifest_commit_guardian_scripts``.
    * ``scripts/feedback/`` — from ``_manifest_feedback_scripts``.
    * ``scripts/<name>`` — workflow-tool scripts from ``_manifest_workflow_tool_scripts``.
    * ``scripts/knowledge/`` — knowledge scripts from ``_manifest_knowledge_scripts``.
    * ``scripts/<name>`` — standalone Python files from ``templates/scripts/``
      (includes ``setup_ticket_worktree.py``).
    * ``scripts/<name>`` — two named AC-pipeline scripts from ``templates/scripts/``.

    This function is intentionally source-only and never reads the target
    project directory: it is used as a preflight guard BEFORE any output is
    written, so the result reflects what *will* be deployed rather than what
    *has* been deployed.

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        Set of ``scripts/<path>`` strings (forward-slash separated) for all
        scripts that will be deployed to the target project on the next build
        run.  Returns an empty set when all source directories are absent.
    """
    manifest = (
        _manifest_ac_store_scripts(package_root)
        | _manifest_commit_guardian_scripts(package_root)
        | _manifest_feedback_scripts(package_root)
        | _manifest_workflow_tool_scripts(package_root)
        | _manifest_knowledge_scripts(package_root)
        | _manifest_template_standalone_scripts(package_root)
    )

    # Standalone scripts (build_standalone_scripts) — two named scripts only
    # NOTE: goal_to_epic.py and build_ac_mode_detection.py may also appear in
    # _manifest_template_standalone_scripts if they exist under templates/scripts/,
    # so this check is a belt-and-suspenders guard for backward compatibility.
    templates_scripts = package_root / "templates" / "scripts"
    for fname in ("goal_to_epic.py", "build_ac_mode_detection.py"):
        if (templates_scripts / fname).is_file():
            manifest.add(f"scripts/{fname}")

    return manifest


def _check_script_reference_guard(package_root: Path) -> int:
    """Preflight guard: exit non-zero when broken script references are detected.

    Scans all source agent and skill templates for script path references
    (patterns: ``python3 scripts/<path>``, ``python scripts/<path>``,
    ``sys.path.insert(<N>, 'scripts/<path>')`` and the double-quoted variant).
    Cross-checks the extracted references against the set of scripts that this
    build run will deploy, using the external-dependency allowlist from
    ``build_propagation_audit.EXTERNAL_DEPENDENCY_ALLOWLIST``.

    When broken references are found, the error report is emitted to stderr as
    JSONL (one JSON object per line) with keys ``"missing_path"``,
    ``"referencing_template"``, and ``"suggested_action"`` (AC BP-900c-2).
    No error output is written to stdout so that piped build output is not
    polluted.

    This guard runs BEFORE ``_run_phases()`` writes any output to the target
    project directory, so no partial deployment is written when broken
    references exist.

    Args:
        package_root: Absolute path to the leafcutter package root. Used to
            locate ``templates/agents/``, ``templates/skills/``, and the
            source script directories.

    Returns:
        0 if all script references are resolved (build may continue).
        1 if one or more broken references are found (build must abort).
    """
    templates_dir = package_root / "templates"

    # Extract script references with source-template provenance for JSONL reporting.
    refs_to_sources = extract_script_path_refs_with_sources(templates_dir)

    if not refs_to_sources:
        return 0

    deployable = _get_source_deployable_scripts(package_root)
    entries = build_broken_ref_report(refs_to_sources, deployable)

    if not entries:
        return 0

    # Emit structured JSONL to stderr (AC BP-900c-2): all error output on stderr,
    # nothing on stdout, so piped build output is never polluted.
    emit_broken_ref_report_jsonl(entries)
    return 1


def _read_package_version(package_root: Path) -> str:
    """Read the package version from config/version.json.

    Returns the ``version`` string from ``config/version.json`` relative to
    *package_root*.  Falls back to ``"unknown"`` when the file is absent or
    malformed so the build never hard-fails on a missing version marker.

    Args:
        package_root: Absolute path to the leafcutter package root.  The file
            ``config/version.json`` must live directly under this directory.

    Returns:
        Version string (e.g. ``"2.0.0"``), or ``"unknown"`` on any read error.
    """
    version_path = package_root / "config" / "version.json"
    try:
        with version_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        return str(data["version"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return "unknown"


def _compute_version_str(package_root: Path) -> str:
    """Derive the next SemVer version by scanning changelog entries.

    Delegates entirely to the helpers in ``release.compute_next_version``.
    Never stamps a git tag — tag creation is the responsibility of the CI
    release workflow, not the build orchestrator.

    Args:
        package_root: Root of the leafcutter package (parents[0] of build.py).
            Used to locate the repository root and the changelogs directory.

    Returns:
        Version string in ``vMAJOR.MINOR.PATCH`` format (e.g. ``v0.1.4``).
        Falls back to ``v0.0.0`` when no changelog entries or v* tags are found.
    """
    repo_root = _cnv_resolve_repo_root()
    changelogs_dir = _cnv_resolve_changelogs_dir(repo_root)
    last_tag = _find_last_version_tag(repo_root)
    baseline = last_tag or "v0.0.0"
    entries = _changelog_entries_since(last_tag, changelogs_dir, repo_root)
    if not entries:
        return baseline
    bump = _compute_bump(entries)
    return _bump_version(baseline, bump)


def build_doc_index(target_root: Path, config: dict, dry_run: bool, force: bool) -> int:  # noqa: ARG001
    """Generate docs/INDEX.md by walking the docs tree.

    The index is regenerated on every build run (not write-if-absent) because
    it is fully derived from the existing docs tree and must stay current.
    Idempotent: if the content is byte-identical to what is already on disk,
    no write is performed and 0 is returned.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary (unused — index generation is
            self-contained; kept for API parity with other phase functions).
        dry_run: When True, logs intent but writes nothing.
        force: Ignored — index is always regenerated (content-addressed write).

    Returns:
        1 if the file was written; 0 if the content was already up-to-date.
    """
    from generate_doc_index import generate_index

    docs_dir = config.get("docs_root", "docs/").rstrip("/")
    output_path = target_root / docs_dir / "INDEX.md"
    content = generate_index(target_root)

    if dry_run:
        _dry_run_msg(f"would write {output_path}")
        return 1

    if output_path.exists():
        try:
            existing = output_path.read_text(encoding="utf-8")
            if existing == content:
                return 0
        except OSError:
            pass

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        _warn(f"Failed to write {output_path}: {exc}")
        return 0
    else:
        _success(f"wrote {output_path.relative_to(target_root)}")
        return 1


def _run_phases(
    target_root: Path,
    output_root: Path,
    config: dict,
    dry_run: bool,
    effective_force: bool,
) -> int:
    """Execute all build phases and print per-phase totals.

    Build artifact phases write into ``output_root`` (.leafcutter/ by default).
    User-curated scaffold phases (vision, glossary, roadmap, tickets) write
    directly into ``target_root`` since they are write-if-absent and user-owned.

    Args:
        target_root: Absolute path to the target project root.
        output_root: Absolute path to the consolidated output directory.
        config: Build configuration dict from load_config.
        dry_run: When True, logs intent but writes nothing.
        effective_force: When True, overwrites existing files.

    Returns:
        Total number of files written (or would-be-written in dry-run mode).
    """
    from typing import Any

    # Phases whose output goes into .leafcutter/ (external tools hardcode paths)
    artifact_phases: list[tuple[str, Any]] = [
        ("Agents", build_agents),
        ("Workflow scripts", build_workflow_scripts),
        ("AC store scripts", build_ac_store),
        ("Skills", build_skills),
        ("Commands", build_commands),
        ("Claude settings", build_claude_settings),
        ("Workflows", build_workflows),
        ("Hooks", build_hooks),
        ("Pre-commit config", build_precommit_config),
        ("Antigravity instructions", build_antigravity_instructions),
    ]

    # Phases that write internal-only outputs into .leafcutter/ (no shim needed,
    # but still consolidated so we don't pollute the user's scripts/, config/, etc.)
    internal_phases: list[tuple[str, Any]] = [
        ("Rules", build_rules),
        ("Commit guardian", build_commit_guardian),
        ("Feedback", build_feedback),
        ("Propagation audit", propagation_audit),
        ("Doc compliance", build_doc_compliance),
        ("Sync platforms", build_sync_platforms),
        ("Workflow tools", build_workflow_tools),
        ("Knowledge scripts", build_knowledge_scripts),
        ("Template standalone scripts", build_template_standalone_scripts),
    ]

    # Phases that write user-curated scaffolds at target_root (write-if-absent)
    scaffold_phases: list[tuple[str, Any]] = [
        ("Ticket lifecycle", build_ticket_lifecycle),
        ("Vision", build_vision),
        ("Roadmap", build_roadmap),
        ("Components registry", build_components_registry),
        ("Glossary", build_glossary),
        ("Config scaffolds", build_config_scaffolds),
        ("AC store scaffold", build_ac_store_scaffold),
        ("AC store docs", build_ac_store_docs),
        ("Agent cards", build_agent_cards),
        ("Doc index", build_doc_index),
    ]

    total = 0
    for label, fn in artifact_phases:
        _heading(label)
        total += fn(output_root, config, dry_run, effective_force)
        print()

    for label, fn in internal_phases:
        _heading(label)
        total += fn(output_root, config, dry_run, effective_force)
        print()

    for label, fn in scaffold_phases:
        _heading(label)
        total += fn(target_root, config, dry_run, effective_force)
        print()

    return total


_PRE_CONSOLIDATION_PATHS = [
    ".claude/agents",
    ".claude/skills",
    ".claude/commands",
    ".claude/hooks",
    ".claude/settings.json",
    ".pre-commit-config.yaml",
    ".gemini",
    "scripts/commit_guardian",
    "scripts/doc_compliance",
    "scripts/feedback",
    "scripts/sync_platforms",
]


def _build_source_manifests(output_root: Path) -> dict:
    """Compute the set of artifact names that build.py currently manages.

    Scans the template directories for each artifact type and returns a dict
    mapping artifact type names to the set of expected output file/directory
    base names that a build pass would produce. This set is used by
    clean_stale_artifacts() to determine which compiled outputs are stale.

    Args:
        output_root: The consolidated output directory (e.g. ``<target>/.leafcutter``
            or ``<target>`` when shims are used). The cleaned directories are
            ``agents/``, ``skills/``, and ``hooks/`` under this root.

    Returns:
        Dict with keys ``"agents"``, ``"skills"``, ``"hooks"``, each mapping to
        a ``set[str]`` of expected base names.
    """
    package_root = Path(__file__).resolve().parent.parent
    templates_dir = package_root / "templates"

    # Agents: each *.md file in templates/agents/ (excluding helper _*.md files)
    agents_template_dir = templates_dir / "agents"
    agents: set[str] = set()
    if agents_template_dir.exists():
        for f in agents_template_dir.glob("*.md"):
            if not f.name.startswith("_"):
                agents.add(f.name)

    # Skills: each subdirectory in templates/skills/
    skills_template_dir = templates_dir / "skills"
    skills: set[str] = set()
    if skills_template_dir.exists():
        for d in skills_template_dir.iterdir():
            if d.is_dir():
                skills.add(d.name)

    # Hooks: each *.py (or other files) in templates/hooks/ (if it exists)
    hooks_template_dir = templates_dir / "hooks"
    hooks: set[str] = set()
    if hooks_template_dir.exists():
        for f in hooks_template_dir.iterdir():
            if f.is_file():
                hooks.add(f.name)

    # Workflow scripts: each *.js file in templates/workflows-js/
    workflows_js_dir = templates_dir / "workflows-js"
    workflows: set[str] = set()
    if workflows_js_dir.exists():
        for f in workflows_js_dir.glob("*.js"):
            if f.is_file():
                workflows.add(f.name)

    return {
        "agents": agents,
        "skills": skills,
        "hooks": hooks,
        "workflows": workflows,
    }


def _cleanup_stale_paths(target_root: Path, output_root: Path, dry_run: bool) -> int:
    """Auto-remove stale pre-consolidation files that have moved into .leafcutter/.

    Only removes paths that are real directories/files (not symlinks pointing
    into the output root — those are shims we created).

    Returns count of paths removed.
    """
    import shutil

    removed = 0
    for rel_path in _PRE_CONSOLIDATION_PATHS:
        full = target_root / rel_path
        if not full.exists() and not full.is_symlink():
            continue
        if full.is_symlink():
            link_target = full.resolve()
            if str(link_target).startswith(str(output_root.resolve())):
                continue
        if dry_run:
            kind = "directory" if full.is_dir() else "file"
            _dry_run_msg(f"would remove stale {kind}: {rel_path}")
            removed += 1
            continue
        if full.is_symlink() or full.is_file():
            full.unlink()
        elif full.is_dir():
            shutil.rmtree(full)
        _success(f"removed stale: {rel_path}")
        removed += 1
    return removed


def _run_migration_report(target_root: Path, output_root: Path) -> int:
    """Scan for stale pre-consolidation files and print a migration report.

    Checks known pre-consolidation output paths. If a path exists and is NOT
    a symlink pointing into the output root, it is reported as stale.

    Returns 0 always (report-only, no deletions).
    """
    print(f"\nMigration report for: {target_root}")
    print(f"Output root: {output_root}\n")

    stale: list[str] = []
    for rel_path in _PRE_CONSOLIDATION_PATHS:
        full = target_root / rel_path
        if not full.exists() and not full.is_symlink():
            continue
        if full.is_symlink():
            link_target = full.resolve()
            if str(link_target).startswith(str(output_root.resolve())):
                continue
        stale.append(rel_path)

    if not stale:
        print("No stale pre-consolidation files found. Migration complete.")
        return 0

    print(f"Found {len(stale)} stale pre-consolidation path(s):\n")
    for p in stale:
        full = target_root / p
        kind = "directory" if full.is_dir() else "file"
        print(f"  STALE: {p} ({kind})")

    print("\nTo remove stale files, run:")
    for p in stale:
        full = target_root / p
        if full.is_dir():
            print(f"  rm -rf {p}")
        else:
            print(f"  rm {p}")

    print(f"\nThen re-run: python {Path(__file__).name} --target-dir {target_root}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for the build script.

    Parses CLI arguments, loads and validates config, then runs all build
    phases in sequence. Optionally installs pre-commit shims as a final step.

    Args:
        argv: Argument list to parse. Defaults to ``sys.argv[1:]`` when None.

    Returns:
        Exit code: 0 on success, 1 on config validation error.
    """
    parser = argparse.ArgumentParser(
        description="Build leafcutter templates into a target project."
    )
    parser.add_argument(
        "--target-dir", "-t", metavar="DIR",
        help="Root directory of the target project. Defaults to current directory.",
    )
    parser.add_argument(
        "--config-path", "-c", metavar="FILE",
        help="Path to skills_config.json. Defaults to <target-dir>/.claude/skills_config.json.",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be generated without writing.")
    parser.add_argument("--validate-only", action="store_true",
                        help="Validate config against schema and exit without writing.")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing files (default behaviour; accepted as a no-op alias).")
    parser.add_argument("--no-overwrite", action="store_true",
                        help="Skip files that already exist (restores legacy skip-existing behaviour).")
    parser.add_argument("--force-breaking", action="store_true",
                        help="Proceed despite breaking changes since last build (acknowledge migration steps).")
    parser.add_argument("--no-shims", action="store_true",
                        help="Skip the install_shims step at the end.")
    parser.add_argument("--migrate", action="store_true",
                        help="Scan for stale pre-consolidation files and print a migration report. No files are deleted.")
    parser.add_argument("--update-diagrams", action="store_true",
                        help="Regenerate Mermaid diagrams from registry and embed into target docs.")
    parser.add_argument("--seed-docs", action="store_true",
                        help=(
                            "Seed missing architecture-doc convention scaffolds into "
                            "{paths.docs.architecture} with missing-only semantics. "
                            "Existing files are never overwritten. "
                            "See leafcutter/scripts/seed_project_docs.py."
                        ))
    parser.add_argument("--clean", action="store_true",
                        help=(
                            "After building, remove stale compiled artifacts in the target "
                            "directory that have no corresponding source template. Only removes "
                            "files under .claude/agents/, .claude/skills/, and .claude/hooks/. "
                            "Files not managed by build.py are never removed."
                        ))
    parser.add_argument(
        "--self-description-enforcement",
        choices=["warning", "error"],
        default=None,
        metavar="LEVEL",
        help=(
            "Override the self_description_enforcement level from "
            "config/agent_registry.json. "
            "Choices: 'warning' (build continues with printed warnings) or "
            "'error' (build exits non-zero when any agent is missing required "
            "self-description fields). When omitted, reads from the registry "
            "config key (default: 'warning' when the key is absent)."
        ),
    )

    args = parser.parse_args(argv)

    target_root = Path(args.target_dir).resolve() if args.target_dir else Path.cwd()
    config_path = Path(args.config_path).resolve() if args.config_path else None

    print(f"{BOLD}Loading config for target:{RESET} {target_root}")
    config = load_config(config_path, target_root)

    package_root = Path(__file__).resolve().parent.parent
    _inject_file_size_limits(config, package_root)
    _inject_changelogs_dir(config, package_root)
    if _validate_all(config, package_root, args.validate_only, args.dry_run):
        return 1

    # Script reference guard: exit non-zero and halt before writing any output
    # when templates reference scripts that will not be deployed (BP-900b-3).
    # Skip under --validate-only since the guard is a deployment preflight, not
    # a config correctness check.
    if not args.validate_only:
        if _check_script_reference_guard(package_root):
            return 1

    if args.validate_only:
        _success("Config validation complete (no files written).")
        return 0

    # Compute the next SemVer version from changelog entries.
    # Skipped under --validate-only (exits above); respected under --dry-run
    # (prints the version but does not write the VERSION file).
    computed_version = _compute_version_str(package_root)

    # Read the declared package version from config/version.json (ACD-1100e-2).
    # This is the stable marketing version (e.g. "2.0.0") that consumers see;
    # computed_version is the granular SemVer derived from changelog entries.
    package_version = _read_package_version(package_root)

    if args.migrate:
        output_root_name = config.get("output_root", ".leafcutter")
        output_root = target_root / output_root_name
        return _run_migration_report(target_root, output_root)

    # Halt-guard: check for breaking changes since last build
    changelogs_dir = package_root / "changelogs"
    halt_result = check_halt_guard(target_root, package_root, changelogs_dir)
    if halt_result.should_halt:
        notice = format_migration_notice(halt_result)
        print(notice, file=sys.stderr)
        if args.dry_run:
            print()
            _dry_run_msg("Would halt here — continuing for dry-run inspection.")
        elif not args.force_breaking:
            return 1
        else:
            print()
            _warn("--force-breaking: proceeding despite breaking changes.")
            print()

    if args.update_diagrams:
        _update_diagrams(package_root)

    if args.seed_docs:
        _seed_docs(target_root, args.dry_run)

    # Resolve the effective overwrite flag.  Default is True (overwrite);
    # --no-overwrite restores the legacy skip-existing behaviour.  --force is
    # retained as a no-op alias for the default.  When both --force and
    # --no-overwrite are supplied, --no-overwrite wins and a warning is printed.
    if args.force and args.no_overwrite:
        _warn("Both --force and --no-overwrite were supplied; "
              "--no-overwrite wins — existing files will be skipped.")
    effective_force: bool = not args.no_overwrite

    output_root_name = config.get("output_root", ".leafcutter")
    output_root = target_root / output_root_name

    dry_label = f" {DIM}(dry-run){RESET}" if args.dry_run else ""
    print(f"\n{BOLD}Building{RESET}{dry_label} into: {target_root}")
    print(f"Output root: {output_root}\n")

    # Reset the up-to-date counter before this run so consecutive CLI calls
    # report accurate per-run numbers.
    reset_uptodate_count()

    # Self-description validation: resolve enforcement level (CLI flag overrides
    # registry config key; registry key overrides the 'warning' built-in default).
    _sd_enforcement: str = "warning"
    package_root_for_sd = Path(__file__).resolve().parent.parent
    _registry_path_for_sd = package_root_for_sd / "config" / "agent_registry.json"
    if _registry_path_for_sd.exists():
        try:
            _reg_data = json.loads(
                _registry_path_for_sd.read_text(encoding="utf-8")
            )
            _sd_enforcement = _reg_data.get(
                "self_description_enforcement", "warning"
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            pass  # Fallback to 'warning' — non-fatal read failure.
    # CLI flag overrides registry config value.
    _cli_sd = getattr(args, "self_description_enforcement", None)
    if _cli_sd is not None:
        _sd_enforcement = _cli_sd

    _heading("Self-description validation")
    _sd_error_count, _sd_warning_count = validate_agent_self_description(
        target_root=target_root,
        config=config,
        dry_run=args.dry_run,
        enforcement_level=_sd_enforcement,
    )
    print()
    if _sd_error_count > 0 and _sd_enforcement == "error":
        _error(
            f"Self-description validation failed with {_sd_error_count} error(s). "
            "Fix the missing fields and re-run the build."
        )
        return 1

    total = _run_phases(target_root, output_root, config, args.dry_run, effective_force)

    uptodate = get_uptodate_count()
    if args.dry_run:
        print(f"Total files to write: {GREEN}{total}{RESET}")
        if uptodate:
            print(f"Would be up-to-date: {uptodate} files (unchanged)")
    else:
        print(f"Total files written: {GREEN}{total}{RESET}")
        if uptodate:
            print(f"Up-to-date: {uptodate} files (unchanged)")

    print(f"Build version: {GREEN}{computed_version}{RESET}")
    print(f"Package version: {GREEN}{package_version}{RESET}")

    # Write the VERSION file to target_root so downstream tooling can read the
    # computed version without re-running compute_next_version.py.
    # Skipped under --dry-run (version is still printed above).
    if not args.dry_run:
        version_file = target_root / "VERSION"
        version_file.write_text(computed_version + "\n", encoding="utf-8")
        # Write LEAFCUTTER_VERSION file so deployed consumers can determine the
        # package version without reading the source package directly (ACD-1100e-2).
        lv_file = target_root / "LEAFCUTTER_VERSION"
        lv_file.write_text(package_version + "\n", encoding="utf-8")
    else:
        _dry_run_msg(f"would write {target_root / 'VERSION'}")
        _dry_run_msg(f"would write {target_root / 'LEAFCUTTER_VERSION'}")

    print()
    _heading("Build manifest")
    write_build_manifest(
        package_root,
        dry_run=args.dry_run,
        target_root=target_root,
        config=config,
    )

    # Write .leafcutter.lock so the halt-guard knows the build baseline
    if not args.dry_run:
        pkg_sha = _resolve_package_sha(package_root)
        if pkg_sha:
            write_lock_file(target_root, pkg_sha)

    print()
    _heading("Stale file cleanup")
    stale_count = _cleanup_stale_paths(target_root, output_root, args.dry_run)
    if stale_count == 0:
        print(f"  {DIM}(no stale files found){RESET}")

    if args.clean:
        print()
        _heading("Clean mode")
        source_manifests = _build_source_manifests(output_root)
        clean_stale_artifacts(target_root, source_manifests)

    if not args.no_shims:
        print()
        _heading("Shim install")
        _install_shims(
            target_root,
            output_root=output_root,
            config=config,
            dry_run=args.dry_run,
            force=effective_force,
        )

        print()
        _heading("Hook install")
        _install_hooks(target_root, dry_run=args.dry_run)

    # Post-build: scan for placeholder content and referential integrity
    if not args.dry_run:
        placeholder_hits = scan_for_placeholders(target_root)
        if placeholder_hits:
            print()
            print(format_placeholder_report(placeholder_hits))

        integrity_missing = check_referential_integrity(target_root, config)
        if integrity_missing:
            print()
            print(format_integrity_report(integrity_missing))

    return 0


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-13 15:30 [epic-supervisor/T03]: Added build_precommit_config to (#EPIC-LeafcutterMVP/01)
#   the phase dispatch list. Reads hooks_manifest from commit_guardian.json
#   template and emits/merges .pre-commit-config.yaml at the consumer project
#   root. Package-managed hook blocks are tagged with @package-managed sentinel
#   and replaced on re-run; project-specific hooks are preserved.
# - 2026-05-13 12:00 [epic-supervisor/ticket-13]: Initial implementation. (#EPIC-LeafcutterMVP/01)
#   Chose YAML frontmatter stripping over keeping metadata in prompts.
#   Used importlib for dynamic shims import to avoid path manipulation.
# - 2026-05-13 12:15 [epic-supervisor/ticket-13]: Refactored to stay under (#EPIC-LeafcutterMVP/01)
#   400-line limit. Extracted template compilation to template_compiler.py,
#   config I/O to config_loader.py, and build phases to build_phases.py.
#   build.py now owns only CLI, write helpers, and orchestration dispatch.
# - 2026-05-13 10:30 [epic-supervisor/ticket-20]: Added agent registry validation (#EPIC-LeafcutterMVP/01)
#   via registry_validator.py. validate_agent_registry() runs before build
#   phases and reports bidirectional consistency errors.
# - 2026-05-13 19:00 [epic-supervisor/ticket-28]: Added --update-diagrams flag (#EPIC-LeafcutterMVP/01)
#   that regenerates Mermaid diagrams from agent_registry.json.
# - 2026-05-13 00:00 [python-coder/ticket-37]: Added write_build_manifest() and call (#EPIC-LeafcutterMVP/01)
#   site in main(). Writes leafcutter/.build_manifest.json with
#   SHA-256 hashes of templates/agents/ after each build.
# - 2026-05-13 22:00 [python-coder/TICKET-20260513]: Flipped CLI default from (#EPIC-LeafcutterMVP/01)
#   force=False to force=True. Added --no-overwrite flag. Retained --force as
#   no-op alias. Rationale: old force=False caused silently stale outputs.
# - 2026-05-14 12:00 [python-coder/TICKET-20260513-CompareBeforeWrite]: Added (#EPIC-LeafcutterMVP/01)
#   compare-before-write guard to write_file(); skips byte-identical files.
# - 2026-05-14 13:00 [EPIC-ArchitectureDocsEnforcement/ticket 11 — D11.2]: (#EPIC-LeafcutterMVP/01)
#   Added --seed-docs flag and _seed_docs() helper. Delegates to
#   seed_project_docs.seed_architecture_scaffolds() for missing-only copy
#   semantics. Decision: seeder lives in a sibling script so it is
#   independently runnable; build.py wires it as an opt-in --seed-docs flag.
# - 2026-05-15 10:15 [python-coder/EPIC-PortableSQLAgents/ticket-01]: Added (#EPIC-LeafcutterMVP/01)
#   PROJECT_CONTEXT discovery helpers (ADR-025). Extracted write_build_manifest,
#   _seed_docs, _update_diagrams, _install_shims to build_helpers.py and the
#   new project_context_discovery.py to keep build.py under 400 lines. Imports
#   find_project_contexts / get_project_context_metadata for metadata reporting;
#   compiled agent body is unchanged (runtime-only discovery, not build-time).
# - 2026-05-15 10:30 [python-coder/TICKET-20260515]: Merged Direction B manifest (#EPIC-LeafcutterMVP/01)
#   support. write_build_manifest() in build_helpers.py extended with
#   output_mappings section. build.py imports remain pointed at build_helpers
#   (canonical module); build_manifest.py and build_extras.py superseded.
#   Call site in main() passes target_root and config so output_mappings are
#   populated on every real build run.
# - 2026-05-17 12:00 [python-coder/TICKET-20260517-VisionTemplate]: Imported (#EPIC-LeafcutterMVP/01)
#   build_vision from build_phases and added ("Vision", build_vision) entry
#   to _run_phases(). The vision phase uses unconditional write-if-absent
#   semantics so docs/vision.md is never overwritten once created.
# - 2026-05-18 20:00 [python-coder/EPIC-GlossaryAutomation/ticket-05]: Imported (#EPIC-GlossaryAutomation/05)
#   build_glossary from build_glossary.py and added ("Glossary", build_glossary)
#   to _run_phases(). GlossaryAutomation wiring: seed docs/glossary.md +
#   glossary_blacklist.md (copy-if-not-exists), register check_glossary_coverage
#   hook (idempotent), wire CLAUDE.md glossary section (marker-based idempotency).
# - 2026-05-18 00:00 [python-coder/EPIC-ProjectRoadmap/ticket-07]: Imported (#EPIC-ProjectRoadmap/07)
#   build_roadmap from build_roadmap_phase.py and added ("Roadmap", build_roadmap)
#   to _run_phases() between Vision and Glossary. The roadmap phase uses
#   write-if-absent semantics (force always ignored) — docs/roadmap.json is
#   copied from ROADMAP.template.json only when absent. Extracted into its own
#   module to keep build_phases.py under the 400-non-docstring-line limit.
# - 2026-05-18 10:15 [python-coder/TICKET-20260518-FileSizeLimit_BuildTimeInjection]: (#TICKETLESS reason=standalone-ticket-closeout)
#   Added _inject_file_size_limits() helper. Reads file_size.line_limits[".py"]
#   from commit_guardian.json after load_config() and injects config["file_size_limit_py"].
#   Enables python-coder template to reference {{config.file_size_limit_py}} without
#   hardcoding the limit. Fallback chain: line_limits[".py"] -> default_limit -> 400.
# - 2026-05-18 11:30 [EPIC-PortableInstallHardening/T04]: Imported propagation_audit from build_propagation_audit.py and added ("Propagation audit", propagation_audit) entry to _run_phases() immediately after ("Commit guardian", build_commit_guardian). (#EPIC-PortableInstallHardening/T04)
# - 2026-05-18 12:30 [EPIC-PortableInstallHardening/T06]: Imported build_claude_settings from build_claude_settings.py and added ("Claude settings", build_claude_settings) entry to _run_phases() after ("Skills", build_skills). (#EPIC-PortableInstallHardening/T06)
# - 2026-05-22 [python-coder/EPIC-AntigravitySupport/09]: Imported and registered build_antigravity_instructions phase in _run_phases.
# - 2026-05-22 [python-coder/Ticket-10]: Imported and registered build_sync_platforms phase in _run_phases.
# - 2026-05-26 [python-coder/EPIC-LeafcutterVersioning/04]: (#EPIC-LeafcutterVersioning/04)
#   Added halt-guard for breaking changes. Imports check_halt_guard and
#   format_migration_notice from build_halt_guard.py. Runs after config
#   validation but before phase dispatch. Writes .leafcutter.lock (JSON
#   with package SHA) after successful builds. --force-breaking flag
#   overrides the halt; --dry-run prints notice but continues.
# - 2026-05-27 12:00 [python-coder/TICKET-20260527-WireVersionIntoBuild]: (#TICKETLESS reason=standalone-ticket-closeout)
#   Wired compute_next_version.py into build.py to auto-apply SemVer.
#   Strategy chosen: write VERSION file to target_root (Option 1) + print
#   "Build version: vX.Y.Z" in summary (Option 3). Option 2 (manifest key)
#   not chosen to keep the manifest schema stable. Import path:
#   `from release.compute_next_version import ...` (direct, not subprocess)
#   — scripts/release/ is a proper package; scripts/ is already on sys.path
#   when build.py runs. Version computation runs after config validation
#   and before _run_phases(); skipped by --validate-only (early return);
#   --dry-run prints but does not write the VERSION file.
# - 2026-05-30 10:05 [python-coder/TICKET-20260530-ChangelogAgentPlaceholderFix]: (#TICKETLESS reason=standalone-ticket-closeout)
#   Added _inject_changelogs_dir() helper. Reads changelogs_dir from commit_guardian.json
#   and injects config["changelog_folder"] so the changelog-agent template can reference
#   {{config.changelog_folder}} instead of the hardcoded "changelogs/" literal.
#   Called immediately after _inject_file_size_limits(). Fallback: "changelogs/".
# - 2026-06-02 [python-coder/TICKET-20260602-ComponentsRegistryScaffold]: Imported
#   build_components_registry from build_phases and added ("Components registry",
#   build_components_registry) entry to scaffold_phases between ("Roadmap", build_roadmap)
#   and ("Glossary", build_glossary). (#TICKET-20260602-ComponentsRegistryScaffold)
# - 2026-06-04 13:10 [documentation-expert/EPIC-ACTraceabilityStore/09]: Imported
#   build_ac_store_docs from build_phases and added ("AC store docs",
#   build_ac_store_docs) entry to scaffold_phases after ("AC store scaffold",
#   build_ac_store_scaffold). Installs how-to and reference docs for the AC
#   Traceability Store into target projects. (#EPIC-ACTraceabilityStore/09)
# - 2026-06-05 10:30 [python-coder/EPIC-SelfDescribingAgents/02]: Imported
#   build_agent_cards from build_phases and added ("Agent cards", build_agent_cards)
#   entry to scaffold_phases after ("AC store docs", build_ac_store_docs) and
#   before ("Doc index", build_doc_index). Generates .card.md files for all
#   agent templates into docs/agents/cards/ on every build run.
#   (#EPIC-SelfDescribingAgents/02)
# - 2026-06-05 12:30 [python-coder/EPIC-SelfDescribingAgents/04]: Imported
#   validate_agent_self_description from build_phases. Added
#   --self-description-enforcement CLI flag (choices: warning|error, default None).
#   Validation runs in main() before _run_phases() as the first phase. Enforcement
#   level resolved: CLI flag > registry config key > built-in default ('warning').
#   When enforcement='error' and errors found, main() returns 1 after printing
#   all errors (aggregated output, never halts on first error). When enforcement
#   ='warning', main() continues with 0 exit code. (#EPIC-SelfDescribingAgents/04)
# - 2026-06-10 [python-coder/EPIC-AcPipelineConsolidation/12]: Added
#   _read_package_version() to read config/version.json. Called in main() after
#   _compute_version_str(). Prints "Package version: X.Y.Z" in build summary.
#   Writes LEAFCUTTER_VERSION file to target_root so deployed consumers can
#   determine the package version without reading the source package directly.
#   Fallback: "unknown" on any read error. (#EPIC-AcPipelineConsolidation/12)
# - 2026-06-17 [python-coder/EPIC-AcPipelineDeployGaps/03]: Imported
#   build_ac_store from build_phases and added ("AC store scripts",
#   build_ac_store) entry to artifact_phases after ("Workflow scripts",
#   build_workflow_scripts). Closes the portable-skill/missing-script gap
#   for ac-scanner and build-ac per ADR-013. (#EPIC-AcPipelineDeployGaps/03)
# - 2026-06-17 [python-coder/EPIC-BuildGuardFalsePositive/02]: Added
#   _get_source_deployable_scripts() and _check_script_reference_guard() preflight
#   functions. The manifest function now scans commit_guardian and feedback source
#   directories dynamically — eliminating the hardcoded name lists that caused 10
#   Class A false positives (8 commit_guardian + 2 feedback). The guard emits
#   broken-ref JSONL to stderr and exits 1 before _run_phases() writes any output.
#   Added extract_script_path_refs_with_sources import from build_referential_integrity
#   and build_broken_ref_report/emit_broken_ref_report_jsonl from build_propagation_audit.
#   (#EPIC-BuildGuardFalsePositive/02)
# - 2026-06-17 [python-coder/EPIC-BuildGuardFalsePositive/03]: Class B resolution.
#   Extended _get_source_deployable_scripts() with four new per-phase manifest helpers:
#   _manifest_workflow_tool_scripts (add_component, knowledge_query, set_ticket_status,
#   ticket_prioritizer), _manifest_knowledge_scripts (harvest_learnings),
#   _manifest_template_standalone_scripts (setup_ticket_worktree + others from
#   templates/scripts/*.py). Imported and wired three new phases into internal_phases
#   in _run_phases(): build_workflow_tools, build_knowledge_scripts,
#   build_template_standalone_scripts. These close the Class B deploy gaps so the
#   script reference guard passes after all legitimate scripts are deployed.
#   (#EPIC-BuildGuardFalsePositive/03)
# ====================================================================
