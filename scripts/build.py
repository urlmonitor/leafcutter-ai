"""
MODULE: build
GOAL: CLI entry point and orchestrator for the leafcutter build system.
BUSINESS CONTEXT: The leafcutter package materialises agent/skill
    templates into a target project by resolving skills_config.json values and
    stripping metadata. This module owns the CLI, config loading, validation,
    and build-phase dispatch. Actual phase logic lives in build_phases.py;
    template compilation in template_compiler.py; config I/O in config_loader.py;
    manifest writing and supplementary helpers in build_helpers.py.
ARCHITECTURE: Three-layer delegation. build.py -> build_phases.py (eight phase
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
    build_skills,
    build_workflows,
    build_rules,
    build_ticket_lifecycle,
    build_commit_guardian,
    build_precommit_config,
    build_doc_compliance,
    build_feedback,
    build_vision,
    build_antigravity_instructions,
    build_sync_platforms,
    reset_uptodate_count,
    get_uptodate_count,
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
    write_build_manifest,
)
from build_glossary import build_glossary
from build_propagation_audit import propagation_audit
from build_claude_settings import build_claude_settings
from build_roadmap_phase import build_roadmap
from build_placeholder_detection import scan_for_placeholders, format_placeholder_report
from build_referential_integrity import check_referential_integrity, format_integrity_report
from build_config_scaffolds import build_config_scaffolds
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
        print(f"  [DRY-RUN] would write {target}")
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
        print(f"  [CONFIG ERROR] {err}", file=sys.stderr)
    if validate_only or not dry_run:
        if not _JSONSCHEMA_AVAILABLE:
            print("  [WARNING] Skipping validation (jsonschema not installed).")
            return 0
        if errors[0].startswith("jsonschema"):
            print("  [WARNING] jsonschema unavailable — proceeding without strict validation.")
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
        print(f"  [REGISTRY ERROR] {err}", file=sys.stderr)
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



def _run_phases(
    target_root: Path,
    config: dict,
    dry_run: bool,
    effective_force: bool,
) -> int:
    """Execute all build phases and print per-phase totals.

    Args:
        target_root: Absolute path to the target project root.
        config: Build configuration dict from load_config.
        dry_run: When True, logs intent but writes nothing.
        effective_force: When True, overwrites existing files.

    Returns:
        Total number of files written (or would-be-written in dry-run mode).
    """
    from typing import Any
    phases: list[tuple[str, Any]] = [
        ("Agents", build_agents),
        ("Skills", build_skills),
        ("Claude settings", build_claude_settings),
        ("Workflows", build_workflows),
        ("Rules", build_rules),
        ("Ticket lifecycle", build_ticket_lifecycle),
        ("Commit guardian", build_commit_guardian),
        ("Feedback", build_feedback),
        ("Propagation audit", propagation_audit),
        ("Pre-commit config", build_precommit_config),
        ("Doc compliance", build_doc_compliance),
        ("Vision", build_vision),
        ("Roadmap", build_roadmap),
        ("Glossary", build_glossary),
        ("Config scaffolds", build_config_scaffolds),
        ("Antigravity instructions", build_antigravity_instructions),
        ("Sync platforms", build_sync_platforms),
    ]
    total = 0
    for label, fn in phases:
        print(f"{label}:")
        total += fn(target_root, config, dry_run, effective_force)
        print()
    return total


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
    parser.add_argument("--no-shims", action="store_true",
                        help="Skip the install_shims step at the end.")
    parser.add_argument("--update-diagrams", action="store_true",
                        help="Regenerate Mermaid diagrams from registry and embed into target docs.")
    parser.add_argument("--seed-docs", action="store_true",
                        help=(
                            "Seed missing architecture-doc convention scaffolds into "
                            "{paths.docs.architecture} with missing-only semantics. "
                            "Existing files are never overwritten. "
                            "See leafcutter/scripts/seed_project_docs.py."
                        ))

    args = parser.parse_args(argv)

    target_root = Path(args.target_dir).resolve() if args.target_dir else Path.cwd()
    config_path = Path(args.config_path).resolve() if args.config_path else None

    print(f"Loading config for target: {target_root}")
    config = load_config(config_path, target_root)

    package_root = Path(__file__).resolve().parent.parent
    _inject_file_size_limits(config, package_root)
    if _validate_all(config, package_root, args.validate_only, args.dry_run):
        return 1

    if args.validate_only:
        print("Config validation complete (no files written).")
        return 0

    if args.update_diagrams:
        _update_diagrams(package_root)

    if args.seed_docs:
        _seed_docs(target_root, args.dry_run)

    # Resolve the effective overwrite flag.  Default is True (overwrite);
    # --no-overwrite restores the legacy skip-existing behaviour.  --force is
    # retained as a no-op alias for the default.  When both --force and
    # --no-overwrite are supplied, --no-overwrite wins and a warning is printed.
    if args.force and args.no_overwrite:
        print("[WARNING] Both --force and --no-overwrite were supplied; "
              "--no-overwrite wins — existing files will be skipped.")
    effective_force: bool = not args.no_overwrite

    dry_label = " (dry-run)" if args.dry_run else ""
    print(f"\nBuilding{dry_label} into: {target_root}\n")

    # Reset the up-to-date counter before this run so consecutive CLI calls
    # report accurate per-run numbers.
    reset_uptodate_count()

    total = _run_phases(target_root, config, args.dry_run, effective_force)

    uptodate = get_uptodate_count()
    if args.dry_run:
        print(f"Total files to write: {total}")
        if uptodate:
            print(f"Would be up-to-date: {uptodate} files (unchanged)")
    else:
        print(f"Total files written: {total}")
        if uptodate:
            print(f"Up-to-date: {uptodate} files (unchanged)")

    # Write build manifest so check_build_drift.py (Direction A) and
    # check_output_drift.py (Direction B) can verify hashes.
    print("\nBuild manifest:")
    write_build_manifest(
        package_root,
        dry_run=args.dry_run,
        target_root=target_root,
        config=config,
    )

    if not args.dry_run and not args.no_shims:
        _install_shims(target_root)

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
# ====================================================================
