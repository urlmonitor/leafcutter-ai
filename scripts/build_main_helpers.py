"""
MODULE: build_main_helpers
GOAL: Cohesive, single-purpose steps extracted from build.py's main() to keep
    main() itself (and every extracted step) under the check-complexity gate's
    cyclomatic-complexity threshold, and to keep build.py itself under the
    check-file-size gate's line-count ratchet.
BUSINESS CONTEXT: build.py is the leafcutter build entry point: every consumer
    bootstrap, every deploy, and CI itself run it. BP-100n-4 registers
    check-complexity as a live pre-commit gate, and build.py was already the
    worst offender (main() alone measured complexity 37). This module holds
    the extracted steps so build.py's own line count does not grow past its
    check-file-size ratchet baseline while paying down that complexity debt.
ARCHITECTURE: Pure extraction, no new behaviour. Each function is one
    formerly-inline step of main(), called in exactly the original order with
    exactly the original branching, printed messages, and exit-code
    semantics. A handful of steps need to call back into build.py's OWN
    local functions (e.g. ``_validate_all``, ``_check_tracked_source_guard``,
    ``_run_migration_report``, ``_check_command_reachability_guard``,
    ``_cleanup_stale_paths``, ``_build_source_manifests``) — rather than
    import those from build.py (which would be a circular import, since
    build.py imports this module), main() passes them in as plain
    parameters. This keeps this module import-cycle-free: it only ever
    imports from build.py's OTHER dependencies (build_colors, build_helpers,
    build_halt_guard, build_phases, build_placeholder_detection,
    build_referential_integrity), never from build.py itself.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from build_colors import (
    RESET,
    GREEN,
    DIM,
    warn as _warn,
    error as _error,
    success as _success,
    dry_run as _dry_run_msg,
    heading as _heading,
)
from build_helpers import (
    seed_docs as _seed_docs,
    update_diagrams as _update_diagrams,
    install_shims as _install_shims,
    install_hooks as _install_hooks,
    write_build_manifest,
)
from seed_example_product import run_as_build_step as _seed_example_product
from build_halt_guard import (
    check_halt_guard,
    format_migration_notice,
    write_lock_file,
    _resolve_package_sha,
)
from build_phases import (
    DeployDeclarationError,
    raise_if_deploy_failures,
    get_uptodate_count,
    clean_stale_artifacts,
)
from build_placeholder_detection import scan_for_placeholders, format_placeholder_report
from build_referential_integrity import check_referential_integrity, format_integrity_report


def _build_arg_parser() -> argparse.ArgumentParser:
    """Construct the build.py CLI argument parser (BP-100n-4 split of main())."""
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
    parser.add_argument("--seed-example-product", metavar="NAME", default=None,
                        help=(
                            "Seed the named example product's worked-example artifacts "
                            "(flows/mock-data/mockups) into docs/product-truth/, by name. "
                            "Not seeded by default; missing-only semantics. "
                            "See leafcutter/scripts/seed_example_product.py."
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
    return parser


def _run_validation_guards(
    config: dict,
    package_root: Path,
    args: argparse.Namespace,
    validate_all,
    script_reference_guards: tuple,
) -> int | None:
    """Run config validation and pre-deploy guards (BP-100n-4 split of main()).

    Returns an exit code when the caller should return immediately (either a
    failure or the --validate-only success path), or None when the build
    should continue.

    Args:
        config: Merged config dictionary.
        package_root: Absolute path to the leafcutter package root.
        args: Parsed CLI namespace.
        validate_all: build.py's local ``_validate_all`` (passed in rather
            than imported, to avoid a circular import with build.py).
        script_reference_guards: build.py's local
            ``(_check_script_reference_guard, _check_tracked_source_guard,
            _check_intra_package_closure_guard)``, called in that order —
            same reasoning as ``validate_all`` above.
    """
    if validate_all(config, package_root, args.validate_only, args.dry_run):
        return 1

    # Script reference guard: exit non-zero and halt before writing any output
    # when templates reference scripts that will not be deployed (BP-900b-3).
    # Tracked-source guard: exit non-zero when any deployable script source is
    # present on disk but not committed to git (BP-900f-1/f-2/f-3).
    # Intra-package closure guard: exit non-zero when a script this build WILL
    # deploy resolves (via import, relative import, or dynamic loader) a
    # sibling module that no deploy phase ships (BP-900g-8).
    # All three guards skip under --validate-only since they are deployment
    # preflights, not config correctness checks.
    if not args.validate_only:
        for guard in script_reference_guards:
            if guard(package_root):
                return 1

    if args.validate_only:
        _success("Config validation complete (no files written).")
        return 0

    return None


def _maybe_run_migration_report(
    args: argparse.Namespace, target_root: Path, config: dict, run_migration_report
) -> int | None:
    """Run the --migrate report if requested (BP-100n-4 split of main()).

    Returns the report's exit code when --migrate was passed, else None.

    Args:
        run_migration_report: build.py's local ``_run_migration_report``
            (passed in rather than imported, to avoid a circular import).
    """
    if not args.migrate:
        return None
    output_root_name = config.get("output_root", ".leafcutter")
    output_root = target_root / output_root_name
    return run_migration_report(target_root, output_root)


def _run_halt_guard(target_root: Path, package_root: Path, args: argparse.Namespace) -> int | None:
    """Check the breaking-change halt guard (BP-100n-4 split of main()).

    Returns exit code 1 when the build must halt, else None to continue.
    """
    changelogs_dir = package_root / "changelogs"
    halt_result = check_halt_guard(target_root, package_root, changelogs_dir)
    if not halt_result.should_halt:
        return None

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
    return None


def _run_optional_pre_deploy_steps(
    args: argparse.Namespace, package_root: Path, target_root: Path
) -> None:
    """Run optional --update-diagrams, --seed-docs, --seed-example-product steps.

    (BP-100n-4 split of main(); --seed-example-product added by UXP-700a-3.)
    """
    if args.update_diagrams:
        _update_diagrams(package_root)

    if args.seed_docs:
        _seed_docs(target_root, args.dry_run)

    if args.seed_example_product:
        _seed_example_product(target_root, args.seed_example_product, args.dry_run)


def _warn_if_conflicting_overwrite_flags(args: argparse.Namespace) -> None:
    """Warn when both --force and --no-overwrite are supplied (BP-100n-4 split).

    --no-overwrite wins; --force is retained as a no-op alias for the default.
    """
    if args.force and args.no_overwrite:
        _warn("Both --force and --no-overwrite were supplied; "
              "--no-overwrite wins — existing files will be skipped.")


def _resolve_self_description_enforcement(args: argparse.Namespace) -> str:
    """Resolve the effective self-description enforcement level.

    (BP-100n-4 split of main().) CLI flag overrides the registry config key;
    registry key overrides the 'warning' built-in default.
    """
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
    return _sd_enforcement


def _check_self_description_error_gate(sd_error_count: int, sd_enforcement: str) -> int | None:
    """Return exit code 1 when self-description errors must hard-fail the build.

    (BP-100n-4 split of main().)
    """
    if sd_error_count > 0 and sd_enforcement == "error":
        _error(
            f"Self-description validation failed with {sd_error_count} error(s). "
            "Fix the missing fields and re-run the build."
        )
        return 1
    return None


def _raise_deploy_failures_if_any() -> int | None:
    """Surface accumulated deploy-declaration failures as an exit code.

    (BP-100n-4 split of main().)
    """
    try:
        raise_if_deploy_failures()
    except DeployDeclarationError as exc:
        print(f"[DEPLOY DECLARATION] {exc}", file=sys.stderr)
        return 1
    return None


def _check_command_reachability_if_live(
    output_root: Path, config: dict, dry_run: bool, check_command_reachability_guard
) -> int | None:
    """Run the command-reachability guard on a real (non-dry-run) build.

    (BP-100n-4 split of main().) Command-reference reachability guard
    (BP-900g-1 / BP-900g-1-i): after the deploy phases have written real
    files, scan every deployed command's Workflow()/Skill() handoff targets
    against the TRUE post-deploy layout and abort the build if any target
    does not resolve. Skipped under --dry-run, where no files were actually
    written to output_root to scan.

    Args:
        check_command_reachability_guard: build.py's local
            ``_check_command_reachability_guard`` (passed in rather than
            imported, to avoid a circular import).
    """
    if not dry_run and check_command_reachability_guard(output_root, config):
        return 1
    return None


def _print_write_summary(total: int, dry_run: bool) -> None:
    """Print the total-files-written/would-write summary lines (BP-100n-4 split)."""
    uptodate = get_uptodate_count()
    if dry_run:
        print(f"Total files to write: {GREEN}{total}{RESET}")
        if uptodate:
            print(f"Would be up-to-date: {uptodate} files (unchanged)")
    else:
        print(f"Total files written: {GREEN}{total}{RESET}")
        if uptodate:
            print(f"Up-to-date: {uptodate} files (unchanged)")


def _write_version_files(
    target_root: Path, computed_version: str, package_version: str, dry_run: bool
) -> None:
    """Write VERSION/LEAFCUTTER_VERSION to target_root, or print dry-run messages.

    (BP-100n-4 split of main().) Skipped (files not written) under --dry-run;
    the version is still printed by the caller in that case.
    """
    if not dry_run:
        version_file = target_root / "VERSION"
        version_file.write_text(computed_version + "\n", encoding="utf-8")
        # Write LEAFCUTTER_VERSION file so deployed consumers can determine the
        # package version without reading the source package directly (ACD-1100e-2).
        lv_file = target_root / "LEAFCUTTER_VERSION"
        lv_file.write_text(package_version + "\n", encoding="utf-8")
    else:
        _dry_run_msg(f"would write {target_root / 'VERSION'}")
        _dry_run_msg(f"would write {target_root / 'LEAFCUTTER_VERSION'}")


def _write_and_verify_manifest(
    package_root: Path, args: argparse.Namespace, target_root: Path, config: dict
) -> int | None:
    """Write the build manifest; return exit code 1 if it could not be produced.

    (BP-100n-4 split of main().)
    """
    manifest_error = write_build_manifest(
        package_root,
        dry_run=args.dry_run,
        target_root=target_root,
        config=config,
    )
    # BP-1500d-3: the record of what this build put into target_root is the
    # output_mappings section of .build_manifest.json. When it could not be
    # produced, write_build_manifest() returns the non-empty error instead of
    # only warning -- this is the load-bearing enforcement point: the exit
    # status must be a function of whether the record was producible, not
    # just the printed message (a build that only warns here leaves every
    # automated caller believing the install is protected when it is not).
    if manifest_error:
        _error(
            "Build manifest record (output_mappings) could not be produced "
            f"for target project {target_root}: {manifest_error}. This "
            "install has no verifiable output_mappings record, so the build "
            "has failed rather than reporting success with a missing record."
        )
        return 1
    return None


def _write_lock_file_if_applicable(target_root: Path, package_root: Path, dry_run: bool) -> None:
    """Write .leafcutter.lock with the current package SHA, unless dry-run.

    (BP-100n-4 split of main().) Lets the halt-guard know the build baseline.
    """
    if not dry_run:
        pkg_sha = _resolve_package_sha(package_root)
        if pkg_sha:
            write_lock_file(target_root, pkg_sha)


def _run_stale_cleanup(
    target_root: Path, output_root: Path, dry_run: bool, cleanup_stale_paths
) -> None:
    """Print the stale-file-cleanup heading and report (BP-100n-4 split).

    Args:
        cleanup_stale_paths: build.py's local ``_cleanup_stale_paths`` (passed
            in rather than imported, to avoid a circular import).
    """
    print()
    _heading("Stale file cleanup")
    stale_count = cleanup_stale_paths(target_root, output_root, dry_run)
    if stale_count == 0:
        print(f"  {DIM}(no stale files found){RESET}")


def _run_clean_mode_if_requested(
    args: argparse.Namespace, target_root: Path, output_root: Path, build_source_manifests
) -> None:
    """Run --clean mode: remove stale compiled artifacts (BP-100n-4 split).

    Args:
        build_source_manifests: build.py's local ``_build_source_manifests``
            (passed in rather than imported, to avoid a circular import).
    """
    if not args.clean:
        return
    print()
    _heading("Clean mode")
    source_manifests = build_source_manifests(output_root)
    clean_stale_artifacts(target_root, source_manifests)


def _run_shim_and_hook_install(
    target_root: Path,
    output_root: Path,
    config: dict,
    dry_run: bool,
    effective_force: bool,
    no_shims: bool,
) -> None:
    """Install pre-commit shims and hooks unless --no-shims (BP-100n-4 split)."""
    if no_shims:
        return
    print()
    _heading("Shim install")
    _install_shims(
        target_root,
        output_root=output_root,
        config=config,
        dry_run=dry_run,
        force=effective_force,
    )

    print()
    _heading("Hook install")
    _install_hooks(target_root, dry_run=dry_run)


def _run_post_build_scans(target_root: Path, config: dict, dry_run: bool) -> None:
    """Scan for placeholder content and referential integrity (BP-100n-4 split).

    Skipped under --dry-run, matching the original inline check.
    """
    if dry_run:
        return
    placeholder_hits = scan_for_placeholders(target_root)
    if placeholder_hits:
        print()
        print(format_placeholder_report(placeholder_hits))

    integrity_missing = check_referential_integrity(target_root, config)
    if integrity_missing:
        print()
        print(format_integrity_report(integrity_missing))


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [python-coder/BP-100n-4]: New module. Extracted from
  build.py's main() (18 helper functions covering CLI parsing, guards,
  self-description resolution, deploy-failure surfacing, and the final
  summary/manifest/lockfile/cleanup/shim-install/post-build-scan steps)
  so that paying down main()'s cyclomatic-complexity debt (measured at
  37 before this split) did not grow build.py past its check-file-size
  ratchet baseline (1915 counted lines). Five functions
  (_run_validation_guards, _maybe_run_migration_report,
  _check_command_reachability_if_live, _run_stale_cleanup,
  _run_clean_mode_if_requested) need to call back into build.py's own
  LOCAL functions (_validate_all and friends); rather than import those
  from build.py (a circular import, since build.py imports this module),
  main() passes them in as plain parameters. Every branch, comment,
  print, and early-return moved verbatim; nothing was removed. See
  build.py's own DECISION HISTORY entry for the same date for the
  paired change on that side.
====================================================================
"""
