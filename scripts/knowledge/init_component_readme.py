"""
init_component_readme.py — CLI entry point for initialising component README.md files.

Provides a command-line interface to create a component AC directory README.md
using ``context_file_maintenance.create_readme``. Idempotent: if the file already
exists, the script exits cleanly without modifying it.

Usage
-----
    python scripts/knowledge/init_component_readme.py <component> [--dest PATH]

Arguments
---------
component
    Component name, e.g. "infrastructure". Used as the section title in the
    generated README header: "# <component> — domain conventions".

--dest PATH
    Destination path for the README.md file.
    Default: docs/acceptance-criteria/<component>/README.md (relative to CWD).

--dry-run
    Print the resolved destination path and exit without writing.

Exit codes
----------
0   Success (file created or already exists).
1   Error (destination directory cannot be created, or write fails).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from scripts.knowledge.context_file_maintenance import create_readme

logger = logging.getLogger("init_component_readme")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="init_component_readme",
        description="Initialise a component README.md for AC domain conventions.",
    )
    parser.add_argument(
        "component",
        help="Component name (used in the README header).",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Destination path for the README.md. "
            "Default: docs/acceptance-criteria/<component>/README.md"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved destination path and exit without writing.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for component README initialisation."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _parse_args(argv)

    dest: Path = args.dest or Path(
        "docs", "acceptance-criteria", args.component, "README.md"
    )

    if args.dry_run:
        print(f"Would create: {dest} (component={args.component!r})")
        return

    if dest.exists():
        print(f"Already exists: {dest} — no changes made.")
        return

    try:
        create_readme(path=dest, component=args.component)
        print(f"Created: {dest}")
    except OSError as exc:
        logger.warning("Failed to create README at %s: %s", dest, exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
