"""
MODULE: seed_example_product
GOAL: Missing-only seeder that copies the package's OWN worked example
    (the "fern-and-fig" example product's flows/mock-data/mockups) into a
    target project's docs/product-truth/ tree, but ONLY when explicitly
    asked for by name.
BUSINESS CONTEXT: UXP-700a-3 requires that a freshly installed project's
    product-truth record carries ZERO artifacts of every type by default
    (AC-1) and none of the tooling's own example product or project record
    (AC-2) -- both already hold today via build_phases.build_product_truth()'s
    write-if-absent EMPTY scaffold. The gap this module closes is AC-3: the
    example product must remain OBTAINABLE by asking for it by name, so the
    zero-by-default separation above is never achieved by deletion. Mirrors
    the shipped --seed-docs / scripts/seed_project_docs.py precedent
    (missing-only semantics, independently runnable script, opt-in CLI flag)
    per the architect-review sign-off on this ticket, reusing ADR-013's
    already-decided deployment-boundary pattern rather than inventing a new
    one.
ARCHITECTURE: No model calls. Pure filesystem I/O. Entry point:
    seed_example_product(project_root, product, dry_run=False) returns
    {"copied": [...], "skipped": [...]}, mirroring
    seed_project_docs.seed_architecture_scaffolds()'s return shape. Copies
    the package's own docs/product-truth/{flows,mock-data,mockups}/<product>/
    tree verbatim and recursively into
    <project_root>/docs/product-truth/<type>/<product>/ for every artifact
    -type directory that holds *product*. Validates *product* against
    docs/product-truth/scripts/product_ownership.py's own EXAMPLE_PRODUCT
    constant (today: only "fern-and-fig") and raises ValueError for anything
    else, so a typo'd request fails clearly rather than silently no-op'ing.
    run_as_build_step() is the tolerant wrapper build_main_helpers.py's
    --seed-example-product flag calls (warns and continues on failure,
    exactly like build_helpers.seed_docs() does for --seed-docs) so an
    optional pre-deploy step never aborts the whole build.
    CLI: python seed_example_product.py --product NAME [--project-root PATH]
    [--dry-run].
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_PT_ROOT = _PACKAGE_ROOT / "docs" / "product-truth"

#: The three artifact-type directories under docs/product-truth/ that hold
#: per-product content. Mirrors unit_tests/product_truth/test_uxp_700a_3.py's
#: own _ARTIFACT_TYPE_DIRS.
_ARTIFACT_TYPE_DIRS = ("flows", "mock-data", "mockups")


def _known_example_product() -> str:
    """Return the package's own EXAMPLE_PRODUCT constant, imported live.

    Imported from docs/product-truth/scripts/product_ownership.py rather
    than restated here, so this seeder can never validate a request against
    a stale copy of the constant it does not own.

    Returns:
        The example product's name (today: "fern-and-fig").
    """
    scripts_dir = str(_PT_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from product_ownership import EXAMPLE_PRODUCT  # noqa: PLC0415

    return EXAMPLE_PRODUCT


def seed_example_product(
    project_root: Path,
    product: str,
    dry_run: bool = False,
) -> dict[str, list[str]]:
    """Copy the named example product's worked-example artifacts by request.

    Missing-only semantics: an existing destination file is never
    overwritten, exactly like seed_project_docs.seed_architecture_scaffolds().

    Args:
        project_root: Absolute path to the target project root.
        product: The example product's name, asked for explicitly by the
            caller (e.g. "fern-and-fig"). Must equal
            product_ownership.EXAMPLE_PRODUCT.
        dry_run: When True, logs intent but writes nothing.

    Returns:
        Summary dict with "copied" and "skipped" keys, each a list of
        path strings relative to the target project's docs/product-truth/
        directory (e.g. "flows/fern-and-fig/customer-buys-a-plant.flow.json").

    Raises:
        ValueError: *product* is not the known example product. Asking for
            an unknown product must fail clearly rather than silently
            copying nothing (a real ask-by-name contract, not a typo trap).
    """
    known_product = _known_example_product()
    if product != known_product:
        raise ValueError(
            f"unknown example product {product!r}; the only known example "
            f"product is {known_product!r}"
        )

    target_pt_root = project_root / "docs" / "product-truth"
    copied: list[str] = []
    skipped: list[str] = []

    for artifact_type in _ARTIFACT_TYPE_DIRS:
        source_dir = _PT_ROOT / artifact_type / product
        if not source_dir.is_dir():
            continue
        _copy_product_artifact_dir(source_dir, target_pt_root, artifact_type, product, dry_run, copied, skipped)

    return {"copied": copied, "skipped": skipped}


def _copy_product_artifact_dir(
    source_dir: Path,
    target_pt_root: Path,
    artifact_type: str,
    product: str,
    dry_run: bool,
    copied: list[str],
    skipped: list[str],
) -> None:
    """Copy every file under one product's one artifact-type source directory.

    Missing-only: an existing destination file is recorded as skipped
    rather than overwritten. Appends relative path strings (rooted at the
    target project's docs/product-truth/ directory) into *copied* / *skipped*
    in place.

    Args:
        source_dir: The package's own source directory for this product and
            artifact type (e.g. docs/product-truth/flows/fern-and-fig/).
        target_pt_root: The target project's docs/product-truth/ directory.
        artifact_type: One of _ARTIFACT_TYPE_DIRS.
        product: The example product's name.
        dry_run: When True, logs intent but writes nothing.
        copied: Accumulator list of copied relative path strings.
        skipped: Accumulator list of skipped relative path strings.
    """
    for src_path in sorted(source_dir.rglob("*")):
        if not src_path.is_file():
            continue
        rel = Path(artifact_type) / product / src_path.relative_to(source_dir)
        rel_str = rel.as_posix()
        dest = target_pt_root / rel

        if dest.exists():
            print(f"  skipped: {rel_str}")
            skipped.append(rel_str)
            continue

        if dry_run:
            print(f"  [DRY-RUN] would copy: {rel_str}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dest)
            print(f"  copied: {rel_str}")
        copied.append(rel_str)


def run_as_build_step(target_root: Path, product: str, dry_run: bool) -> None:
    """Tolerant wrapper for build.py's optional --seed-example-product step.

    Mirrors build_helpers.seed_docs()'s tolerance: a failure here warns and
    lets the rest of the build proceed rather than aborting it, since asking
    for the example product is an opt-in convenience step, not a required
    deploy phase.

    Args:
        target_root: Absolute path to the target project root.
        product: The example product's name requested via
            --seed-example-product NAME.
        dry_run: When True, logs intent but writes nothing.
    """
    from build_colors import warn as _warn  # noqa: PLC0415

    try:
        dry_label = " (dry-run)" if dry_run else ""
        print(f"\nSeeding example product '{product}'{dry_label}:")
        result = seed_example_product(target_root, product, dry_run=dry_run)
        print(f"  Done: {len(result['copied'])} copied, {len(result['skipped'])} skipped.")
    except (ValueError, OSError, ImportError) as exc:
        print()
        _warn(
            f"Example product seeding failed: {exc}. "
            "Run manually: python leafcutter/scripts/seed_example_product.py --product NAME"
        )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the example-product seeder.

    Args:
        argv: Argument list to parse. Defaults to ``sys.argv[1:]`` when None.

    Returns:
        Exit code: 0 on success, 1 when *product* is not the known example
        product.
    """
    parser = argparse.ArgumentParser(
        description="Seed the named example product's worked example into a project, by name."
    )
    parser.add_argument(
        "--product", required=True, metavar="NAME",
        help="The example product to seed (e.g. fern-and-fig).",
    )
    parser.add_argument(
        "--project-root", "-r", metavar="DIR",
        help="Root directory of the target project. Defaults to current directory.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be copied without writing.",
    )
    args = parser.parse_args(argv)

    project_root = (
        Path(args.project_root).resolve() if args.project_root else Path.cwd()
    )
    dry_label = " (dry-run)" if args.dry_run else ""
    print(f"Seeding example product '{args.product}'{dry_label} into: {project_root}\n")
    try:
        result = seed_example_product(project_root, args.product, dry_run=args.dry_run)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"\nDone: {len(result['copied'])} copied, {len(result['skipped'])} skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-16 [python-coder/UXP-700a-3]: New module. AC-1/AC-2 (a fresh
  install carries zero artifacts of every type, and none of the example
  product's or the tooling's own record's content) already held via
  build_phases.build_product_truth()'s existing write-if-absent EMPTY
  scaffold -- see the architect-review sign-off on this ticket. The real
  gap was AC-3: no way to obtain the example product ("fern-and-fig") by
  asking for it by name. Mirrors seed_project_docs.py's missing-only,
  opt-in-flag, independently-runnable-script shape rather than inventing a
  new deploy convention, reusing ADR-013's deployment-boundary decision.
  Wired as --seed-example-product NAME on scripts/build.py via
  run_as_build_step(), called from build_main_helpers.py's
  _run_optional_pre_deploy_steps() exactly the way --seed-docs already is.
  (#EPIC-TruthfulProjectRecord)
====================================================================
"""
