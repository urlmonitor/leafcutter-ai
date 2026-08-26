#!/usr/bin/env python3
"""
MODULE: check_consumer_install
GOAL: Simulate a real consumer install of the leafcutter-ai package into an
    empty scratch project — run the real build.py against it and verify the
    deployed tree is complete and internally consistent.
BUSINESS CONTEXT: AC BP-900a..BP-900g verify deployment completeness
    *statically*, from inside the build. Nothing had verified it
    *empirically*, by performing an install and inspecting the result — the
    gap that let seven consumer-install defects (BP-900g-4/-5/-6, BP-015,
    BP-016, BP-017, BP-018) ship and get hotfixed after release between
    2026-08-13 and 2026-08-17 (AC BP-900h-1). This script is the CI-facing
    entry point that closes that gap: it drives a real ``build.py`` run into a
    genuinely empty scratch directory (never a copy of this repository, which
    would reintroduce the source-tree bias that hides missing-deploy defects)
    and then reuses the existing reference-resolution machinery against the
    deployed output.
ARCHITECTURE: A single CLI entry point (``main``) that composes four small,
    independently testable steps: (1) ``_ensure_scratch_environment`` creates
    ``--target-dir`` and seeds a minimal ``skills_config.json`` when absent;
    (2) ``_maybe_run_build`` shells out to ``<--package-dir>/scripts/build.py``
    unless ``--skip-build`` is given; (3) ``_verify_deployed_tree`` asserts the
    deployed output root contains ``scripts/`` and ``agents/``; (4)
    ``_check_unresolved_references`` imports
    ``build_referential_integrity.extract_compiled_script_path_refs`` and
    ``build_propagation_audit.build_broken_ref_report`` from
    ``--package-dir/scripts`` and reuses them, unmodified, against the
    deployed tree — per the ticket's Implementation Notes, this script does
    not reimplement the matching rules those modules already own.

Usage::

    python scripts/ci/check_consumer_install.py \\
        --package-dir <path-to-leafcutter-ai-checkout> \\
        --target-dir <scratch-dir> \\
        [--skip-build]

CI registration::

    # In your CI YAML (e.g. .github/workflows/ci.yml):
    - name: Consumer install simulation
      run: python leafcutter-ai/scripts/ci/check_consumer_install.py \\
             --package-dir leafcutter-ai --target-dir .

Exit codes:
    0 — build succeeded, deployed tree is complete, all references resolve.
    1 — build.py exited non-zero, the deployed tree is missing scripts/ or
        agents/, or one or more compiled-template script references do not
        resolve to a deployed file (unresolved paths are named on stderr).
    2 — usage/environment error (bad --package-dir, filesystem error, or the
        reference-resolution modules could not be imported).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

_MINIMAL_SKILLS_CONFIG: dict[str, str] = {
    "_comment": "Minimal config for consumer-install simulation (BP-900h-1).",
}


def _ensure_scratch_environment(target_dir: Path) -> int:
    """Create ``target_dir`` and seed a minimal skills_config.json if absent.

    Never clobbers a caller-supplied ``skills_config.json`` — only writes one
    when the file does not already exist.

    Returns:
        0 on success, 2 on any filesystem error.
    """
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"ERROR: could not create --target-dir {target_dir}: {exc}", file=sys.stderr)
        return 2

    config_path = target_dir / "skills_config.json"
    if config_path.exists():
        return 0

    try:
        config_path.write_text(json.dumps(_MINIMAL_SKILLS_CONFIG), encoding="utf-8")
    except OSError as exc:
        print(
            f"ERROR: could not write minimal skills_config.json to {config_path}: {exc}",
            file=sys.stderr,
        )
        return 2

    return 0


def _maybe_run_build(package_dir: Path, target_dir: Path, skip_build: bool) -> int:
    """Run ``build.py --target-dir <target_dir>`` unless ``skip_build`` is set.

    Returns:
        0 on success (or when skipped), 1 when build.py exits non-zero
        (its combined stdout/stderr is printed to our stderr), 2 when the
        subprocess itself cannot be started.
    """
    if skip_build:
        return 0

    build_py = package_dir / "scripts" / "build.py"
    try:
        result = subprocess.run(
            [sys.executable, str(build_py), "--target-dir", str(target_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        print(f"ERROR: could not invoke build.py subprocess: {exc}", file=sys.stderr)
        return 2

    if result.returncode != 0:
        print(
            "CONSUMER INSTALL SIMULATION FAILED: build.py exited non-zero.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            file=sys.stderr,
        )
        return 1

    return 0


def _resolve_output_root(target_dir: Path) -> Path:
    """Resolve the deployed output root from ``target_dir/skills_config.json``.

    Reads the ``output_root`` key, defaulting to ``.leafcutter`` when the key
    is absent or the file cannot be parsed.
    """
    config_path = target_dir / "skills_config.json"
    output_root_name = ".leafcutter"
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(
                f"WARNING: could not parse {config_path}: {exc} — "
                "defaulting output_root to .leafcutter",
                file=sys.stderr,
            )
        else:
            output_root_name = data.get("output_root", ".leafcutter")
    return target_dir / output_root_name


def _verify_deployed_tree(target_dir: Path) -> tuple[Path, int]:
    """Verify the deployed output root contains ``scripts/`` and ``agents/``.

    Returns:
        A ``(output_root, code)`` pair: ``code`` is 0 on success, or 1 with
        the missing directory named on stderr.
    """
    output_root = _resolve_output_root(target_dir)

    if not output_root.is_dir():
        print(
            f"CONSUMER INSTALL SIMULATION FAILED: deployed output root missing: {output_root}",
            file=sys.stderr,
        )
        return output_root, 1

    for sub in ("scripts", "agents"):
        sub_dir = output_root / sub
        if not sub_dir.is_dir():
            print(
                f"CONSUMER INSTALL SIMULATION FAILED: missing deployed directory: {sub_dir}",
                file=sys.stderr,
            )
            return output_root, 1

    return output_root, 0


def _import_audit_modules(package_dir: Path) -> tuple[ModuleType, ModuleType]:
    """Import the existing reference-resolution modules from ``package_dir/scripts``.

    Reuses ``build_referential_integrity`` and ``build_propagation_audit``
    as-is (per the ticket's Implementation Notes — the matching rules are not
    reimplemented here).

    Raises:
        ImportError: if either module cannot be imported.
    """
    scripts_dir = str(package_dir / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import build_propagation_audit as bpa
    import build_referential_integrity as bri

    return bri, bpa


def _collect_deployed_scripts(scripts_dir: Path) -> set[str]:
    """Walk ``scripts_dir`` and return the set of deployed ``scripts/<relpath>`` strings."""
    deployed: set[str] = set()
    if not scripts_dir.is_dir():
        return deployed
    try:
        for script_file in scripts_dir.rglob("*.py"):
            deployed.add(f"scripts/{script_file.relative_to(scripts_dir).as_posix()}")
    except OSError as exc:
        print(
            f"ERROR: could not walk deployed scripts directory {scripts_dir}: {exc}",
            file=sys.stderr,
        )
        raise
    return deployed


def _check_unresolved_references(package_dir: Path, output_root: Path) -> int:
    """Reuse the BP-900b/BP-900c reference-resolution machinery against the deployed tree.

    Returns:
        0 when every compiled-template script reference resolves to a
        deployed file, 1 when unresolved references are found (each named on
        stderr), 2 on an environment error (e.g. the audit modules cannot be
        imported, or the deployed scripts directory cannot be walked).
    """
    try:
        bri, bpa = _import_audit_modules(package_dir)
    except ImportError as exc:
        print(
            f"ERROR: could not import reference-resolution modules from {package_dir}: {exc}",
            file=sys.stderr,
        )
        return 2

    refs = bri.extract_compiled_script_path_refs(output_root)
    refs_to_sources: dict[str, set[str]] = {}
    for template_path, script_path in refs:
        refs_to_sources.setdefault(script_path, set()).add(template_path)

    try:
        deployed_scripts = _collect_deployed_scripts(output_root / "scripts")
    except OSError:
        return 2

    broken = bpa.build_broken_ref_report(refs_to_sources, deployed_scripts)
    if not broken:
        return 0

    print(
        f"CONSUMER INSTALL SIMULATION FAILED: {len(broken)} unresolved script reference(s).",
        file=sys.stderr,
    )
    for entry in broken:
        referencing = ", ".join(entry.referencing_templates)
        print(
            f"  MISSING: {entry.missing_path} — referenced by: {referencing} "
            f"— suggested action: {entry.suggested_action}",
            file=sys.stderr,
        )
    return 1


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--package-dir",
        type=Path,
        required=True,
        help="Path to a leafcutter-ai package checkout containing scripts/build.py.",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        required=True,
        help="Scratch consumer-install directory. Created if absent.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help=(
            "Skip invoking build.py and only run the reference-resolution "
            "check against an already-deployed tree."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns an exit code (0 = OK, 1 = simulation failed, 2 = usage/environment error)."""
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    package_dir: Path = args.package_dir.resolve()
    target_dir: Path = args.target_dir.resolve()

    if not (package_dir / "scripts" / "build.py").exists():
        print(
            f"ERROR: --package-dir {package_dir} does not contain scripts/build.py",
            file=sys.stderr,
        )
        return 2

    setup_code = _ensure_scratch_environment(target_dir)
    if setup_code != 0:
        return setup_code

    build_code = _maybe_run_build(package_dir, target_dir, args.skip_build)
    if build_code != 0:
        return build_code

    output_root, tree_code = _verify_deployed_tree(target_dir)
    if tree_code != 0:
        return tree_code

    refs_code = _check_unresolved_references(package_dir, output_root)
    if refs_code != 0:
        return refs_code

    print(f"CONSUMER INSTALL SIMULATION OK: deployed output root at {output_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-26 [python-coder/EPIC-DeploymentCompleteness/12_BP-900h-1]: Created
#   scripts/ci/check_consumer_install.py to close the empirical-install gap
#   identified in the ticket: BP-900a..BP-900g verify deployment completeness
#   statically, from inside the build, but nothing had performed a real
#   install into a genuinely empty scratch project and inspected the result.
#   Composed of four small steps (scratch-env setup, build invocation,
#   deployed-tree shape check, reference-resolution check) so each is
#   independently testable and main() stays low-complexity. The
#   reference-resolution check reuses
#   build_referential_integrity.extract_compiled_script_path_refs() and
#   build_propagation_audit.build_broken_ref_report() unmodified (per the
#   ticket's Implementation Notes) rather than reimplementing the matching
#   rules BP-900b-1/BP-900c-1 already built. (#EPIC-DeploymentCompleteness/12)
# ====================================================================
