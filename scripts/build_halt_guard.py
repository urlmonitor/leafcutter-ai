"""
MODULE: build_halt_guard
GOAL: Detect breaking changelog entries since the consumer's last successful
    build and halt with a structured migration notice — preventing silent
    consumption of backwards-incompatible changes.
BUSINESS CONTEXT: When a consumer runs build.py and the package has introduced
    breaking changes since the consumer's last build, this guard surfaces the
    migration steps required before proceeding. The --force-breaking flag
    overrides the halt for operators who have read and acknowledged the steps.
ARCHITECTURE: Standalone module imported by build.py early in main(). Reads
    .leafcutter.lock (JSON: sha, date) from the consumer's project root. Scans
    changelog entries committed after the pinned SHA for breaking=true. Returns
    a structured result that build.py acts on (halt, warn, or proceed).
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

LOCK_FILENAME = ".leafcutter.lock"


@dataclass
class BreakingEntry:
    """A single breaking changelog entry with its migration steps."""
    title: str
    date: str
    migration_steps: list[str]
    path: Path


@dataclass
class HaltGuardResult:
    """Result of the halt-guard check."""
    should_halt: bool = False
    breaking_entries: list[BreakingEntry] = field(default_factory=list)
    is_first_run: bool = False


# ---------------------------------------------------------------------------
# Lock file I/O
# ---------------------------------------------------------------------------


def read_lock_file(target_root: Path) -> Optional[str]:
    """Read the pinned SHA from .leafcutter.lock.

    Returns the SHA string, or None if the lock file does not exist or is
    malformed.
    """
    lock_path = target_root / LOCK_FILENAME
    if not lock_path.exists():
        return None
    try:
        with lock_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("sha")
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def write_lock_file(target_root: Path, sha: str) -> None:
    """Write the .leafcutter.lock file with the current package SHA."""
    lock_path = target_root / LOCK_FILENAME
    from datetime import datetime, timezone

    data = {
        "sha": sha,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    lock_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# SHA resolution
# ---------------------------------------------------------------------------


def _resolve_package_sha(package_root: Path) -> Optional[str]:
    """Get the current HEAD SHA of the package repo (or subdirectory)."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H"],
            capture_output=True,
            text=True,
            cwd=package_root,
            check=True,
        )
        return result.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


# ---------------------------------------------------------------------------
# Changelog scanning
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _parse_entry_frontmatter(path: Path) -> dict:
    """Parse YAML frontmatter from a changelog entry file (stdlib-only)."""
    content = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}

    result: dict = {}
    current_list_key: Optional[str] = None
    current_list: list[str] = []

    for line in match.group(1).split("\n"):
        if line.startswith("  - ") and current_list_key:
            current_list.append(line[4:].strip())
            continue
        else:
            if current_list_key:
                result[current_list_key] = current_list
                current_list_key = None
                current_list = []

        if ":" not in line or line.startswith("#"):
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key == "breaking":
            result["breaking"] = value.lower() == "true"
        elif key == "title":
            result["title"] = value
        elif key == "date":
            result["date"] = value
        elif key == "migration_steps":
            if value and value != "[]":
                result["migration_steps"] = [value]
            else:
                current_list_key = "migration_steps"
                current_list = []

    if current_list_key:
        result[current_list_key] = current_list

    return result


def _find_breaking_entries_since(
    pinned_sha: str,
    changelogs_dir: Path,
    package_root: Path,
) -> list[BreakingEntry]:
    """Scan changelog entries committed after pinned_sha for breaking=true."""
    if not changelogs_dir.is_dir():
        return []

    try:
        result = subprocess.run(
            ["git", "log", f"{pinned_sha}..HEAD", "--name-only", "--pretty=format:", "--", str(changelogs_dir)],
            capture_output=True,
            text=True,
            cwd=package_root,
            check=True,
        )
        files = {line.strip() for line in result.stdout.strip().split("\n") if line.strip()}
    except subprocess.CalledProcessError:
        files = {str(p.relative_to(package_root)) for p in changelogs_dir.glob("*.md")}

    breaking: list[BreakingEntry] = []
    for f in sorted(files):
        p = package_root / f
        if not p.exists() or p.suffix != ".md":
            continue
        fm = _parse_entry_frontmatter(p)
        if fm.get("breaking") is True:
            breaking.append(BreakingEntry(
                title=fm.get("title", p.stem),
                date=fm.get("date", "unknown"),
                migration_steps=fm.get("migration_steps", []),
                path=p,
            ))

    return breaking


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_halt_guard(
    target_root: Path,
    package_root: Path,
    changelogs_dir: Path,
) -> HaltGuardResult:
    """Run the halt-guard check and return the result.

    Does NOT halt or exit — the caller (build.py) decides how to act based
    on the result and CLI flags (--force-breaking, --dry-run).
    """
    pinned_sha = read_lock_file(target_root)

    if pinned_sha is None:
        return HaltGuardResult(should_halt=False, is_first_run=True)

    entries = _find_breaking_entries_since(pinned_sha, changelogs_dir, package_root)

    if not entries:
        return HaltGuardResult(should_halt=False)

    return HaltGuardResult(should_halt=True, breaking_entries=entries)


def format_migration_notice(result: HaltGuardResult) -> str:
    """Format the halt-guard migration notice for display."""
    lines = [
        "",
        "=" * 70,
        "  BREAKING CHANGES DETECTED — BUILD HALTED",
        "=" * 70,
        "",
        "The following breaking changes have been introduced since your last",
        "successful build. Review the migration steps below before proceeding.",
        "",
    ]

    for entry in result.breaking_entries:
        lines.append(f"  [{entry.date}] {entry.title}")
        if entry.migration_steps:
            for step in entry.migration_steps:
                lines.append(f"    - {step}")
        lines.append("")

    lines.extend([
        "To proceed after reviewing the steps above, re-run with:",
        "  python build.py --force-breaking",
        "",
        "=" * 70,
    ])

    return "\n".join(lines)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-26 [python-coder/EPIC-LeafcutterVersioning/04]: (#EPIC-LeafcutterVersioning/04)
#   Created module. Implements the .leafcutter.lock read/write cycle and
#   breaking-entry scan. Returns a HaltGuardResult dataclass — build.py
#   decides the action based on --force-breaking and --dry-run flags.
#   Lock file format is JSON {sha, date} for extensibility. SHA resolution
#   uses git log -1 --format=%H from the package root.
# ====================================================================
