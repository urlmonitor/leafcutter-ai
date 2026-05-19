"""
MODULE: seed_project_docs
GOAL: Missing-only seeder that copies architecture-doc convention scaffolds from
    leafcutter/templates/docs/architecture/ into the project's
    docs/architecture/ folder, resolving the target path from paths.json.
BUSINESS CONTEXT: When a project installs leafcutter it receives agents
    and hooks but no starter architecture-doc scaffolds. This script seeds the
    five canonical scaffolds (README, FRONTMATTER, c1-001 stub, ADR README, ADR
    template) on first install so that every adopting project starts with
    convention-compliant content rather than an empty folder. Missing-only semantics
    preserve all project-local edits — the seeder never overwrites an existing file.
    Decision (D11.2): placed in a sibling script (not embedded in build.py) so that
    seeding is independently runnable and opt-in. Wire it via --seed-docs flag on
    build.py to keep the install step discoverable.
ARCHITECTURE: No model calls. Pure filesystem + JSON parsing. Entry point:
    seed_architecture_scaffolds(project_root) returns {"copied": [...], "skipped": [...]}.
    CLI: python seed_project_docs.py [--project-root PATH] [--dry-run].
    Reads destination path from paths.json via path_resolver.resolve_path("docs.architecture").
    Walks leafcutter/templates/docs/architecture/ recursively.
    Strips .template extension when copying so c1-001-system-context.md.template
    seeds as c1-001-system-context.md. Creates intermediate dirs as needed.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_SCAFFOLD_SOURCE = _PACKAGE_ROOT / "templates" / "docs" / "architecture"
_TEMPLATE_EXT = ".template"


def _resolve_target_dir(project_root: Path) -> Path:
    """Resolve the target architecture directory via path_resolver.

    Falls back to ``docs/architecture/`` relative to ``project_root`` when
    ``path_resolver`` is unavailable (e.g. the package scripts directory is
    not on sys.path in a bare invocation).

    Args:
        project_root: Absolute path to the target project root.

    Returns:
        Absolute path to the project's architecture docs directory.
    """
    scripts_dir = _PACKAGE_ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from path_resolver import resolve_path  # type: ignore[import]
        rel = resolve_path("docs.architecture", package_root=_PACKAGE_ROOT)
        return (project_root / rel).resolve()
    except Exception:
        # Graceful fallback when path_resolver is unavailable.
        return (project_root / "docs" / "architecture").resolve()


def seed_architecture_scaffolds(
    project_root: Path,
    dry_run: bool = False,
) -> dict[str, list[str]]:
    """Copy missing scaffold files into the project's docs/architecture/ directory.

    Walks ``leafcutter/templates/docs/architecture/`` recursively.
    For each file found:
    - Strips ``.template`` extension from the target filename.
    - Resolves the target path under ``{paths.docs.architecture}``.
    - If the target already exists: records it as ``skipped``.
    - If the target is absent: copies the file verbatim, records it as ``copied``.

    Creates intermediate directories with ``mkdir(parents=True, exist_ok=True)``
    before copying.

    Args:
        project_root: Absolute path to the target project root.
        dry_run: When True, logs intent but writes nothing.

    Returns:
        Summary dict with ``"copied"`` and ``"skipped"`` keys, each containing
        a list of relative path strings (relative to the architecture docs directory).
    """
    target_dir = _resolve_target_dir(project_root)
    source_dir = _SCAFFOLD_SOURCE

    if not source_dir.is_dir():
        print(f"  [SEED] Scaffold source not found: {source_dir}; nothing to seed.")
        return {"copied": [], "skipped": []}

    copied: list[str] = []
    skipped: list[str] = []

    for src_path in sorted(source_dir.rglob("*")):
        if not src_path.is_file():
            continue

        # Build relative path from the scaffold source root.
        rel = src_path.relative_to(source_dir)

        # Strip .template extension from the target filename.
        parts = list(rel.parts)
        last = parts[-1]
        if last.endswith(_TEMPLATE_EXT):
            parts[-1] = last[: -len(_TEMPLATE_EXT)]
        target_rel = Path(*parts)

        dest = target_dir / target_rel
        rel_str = target_rel.as_posix()

        if dest.exists():
            print(f"  skipped: {rel_str}")
            skipped.append(rel_str)
        else:
            if dry_run:
                print(f"  [DRY-RUN] would copy: {rel_str}")
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dest)
                print(f"  copied: {rel_str}")
            copied.append(rel_str)

    return {"copied": copied, "skipped": skipped}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the architecture scaffold seeder.

    Args:
        argv: Argument list to parse. Defaults to ``sys.argv[1:]`` when None.

    Returns:
        Exit code: 0 on success.
    """
    parser = argparse.ArgumentParser(
        description="Seed architecture-doc convention scaffolds into a project."
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
    print(f"Seeding architecture scaffolds{dry_label} into: {project_root}\n")
    result = seed_architecture_scaffolds(project_root, dry_run=args.dry_run)

    print(
        f"\nDone: {len(result['copied'])} copied, {len(result['skipped'])} skipped."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-14 12:00 [EPIC-ArchitectureDocsEnforcement/ticket 11 — D11.2]: (#EPIC-LeafcutterMVP/01)
#   Created as a standalone seeder script (not embedded in build.py) so that
#   seeding is independently runnable and opt-in. Seeder reads the target path
#   from paths.json via path_resolver and falls back to docs/architecture/ when
#   path_resolver is unavailable. Strips .template extension on copy.
#   Wire into build.py via --seed-docs flag (see D11.2 in build.py).
# ====================================================================
