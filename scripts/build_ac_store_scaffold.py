"""
MODULE: build_ac_store_scaffold
GOAL: Install the docs/acceptance-criteria/ directory scaffold into a target
    project during the build.py phase run.
BUSINESS CONTEXT: The AC store (docs/acceptance-criteria/) is a portable
    artifact that any project running build.py should receive automatically.
    This module provides the build_ac_store_scaffold() phase function that
    creates docs/acceptance-criteria/ with an index.yaml and README.md when
    the directory does not exist, following the same pattern as
    build_config_scaffolds() for write-if-absent scaffolds.
ARCHITECTURE: Single public function build_ac_store_scaffold() that reads
    the template files from templates/acceptance-criteria/ in the package root,
    installs them to {target_root}/docs/acceptance-criteria/, and applies
    write-if-absent semantics (never overwrites user-edited files). Follows the
    signature convention (target_root, config, dry_run, force) used by all
    other build phase functions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_AC_TEMPLATES_DIR = _PACKAGE_ROOT / "templates" / "acceptance-criteria"


def build_ac_store_scaffold(
    target_root: Path,
    config: dict[str, Any],
    dry_run: bool,
    force: bool,
) -> int:
    """Install the docs/acceptance-criteria/ scaffold into the target project.

    Installs ``index.yaml`` and ``README.md`` from
    ``templates/acceptance-criteria/`` into ``{target_root}/docs/acceptance-criteria/``.
    Uses write-if-absent semantics — existing files are never overwritten,
    regardless of the ``force`` parameter. This preserves user-edited component
    registries and README customisations across subsequent build runs.

    Logs "AC store scaffold installed" on first install, or
    "AC store scaffold: already present, skipping" when the directory exists.

    Args:
        target_root: Absolute path to the target project root. The scaffold is
            installed at ``{target_root}/docs/acceptance-criteria/``.
        config: Build configuration dict (not used by this phase, accepted for
            interface consistency).
        dry_run: When True, logs intent but writes nothing.
        force: Ignored — this phase always uses write-if-absent semantics so
            that user-edited AC files are never clobbered by a build re-run.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    ac_dir = target_root / "docs" / "acceptance-criteria"
    written = 0

    template_files = [
        ("index.yaml", _AC_TEMPLATES_DIR / "index.yaml"),
        ("README.md", _AC_TEMPLATES_DIR / "README.md"),
    ]

    for filename, template_path in template_files:
        dest = ac_dir / filename
        if dest.exists():
            continue
        if dry_run:
            print(f"  [DRY-RUN] would scaffold docs/acceptance-criteria/{filename}")
            written += 1
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                content = template_path.read_text(encoding="utf-8")
            except OSError as exc:
                print(
                    f"  [WARNING] AC store scaffold: could not read template "
                    f"{template_path}: {exc}"
                )
                continue
            dest.write_text(content, encoding="utf-8")
            written += 1

    if written > 0:
        if not dry_run:
            print("  AC store scaffold installed at docs/acceptance-criteria/")
    else:
        print("  AC store scaffold: already present, skipping")

    return written
