"""
MODULE: compute_next_version
GOAL: Scan per-file changelog entries since the last v* tag and compute the
    next SemVer version deterministically — no human judgement at release time.
BUSINESS CONTEXT: This is the release script for the leafcutter-ai package.
    It reads YAML frontmatter from changelog entries, determines the bump level
    (MAJOR/MINOR/PATCH) based on breaking flags and type fields, and optionally
    stamps a git tag.
ARCHITECTURE: Single-module CLI (stdlib-only). Reuses the same frontmatter
    parsing approach as emit_entry.py. Invoked manually or from CI via
    .github/workflows/release.yml.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Self-location helpers
# ---------------------------------------------------------------------------


def _resolve_repo_root() -> Path:
    """Compute the repository root from this script's own location.

    Supports three topologies:
    1. Standalone package development workspace:
       __file__ = <repo_root>/scripts/release/compute_next_version.py
       parents[2] = <repo_root>, .git is a directory
    2. Consumer project environment (copy-installed):
       __file__ = <consumer>/leafcutter/scripts/release/compute_next_version.py
       parents[2] = <consumer>/leafcutter/ — no .git at all
       parents[3] = <consumer>/ — .git is a directory
    3. Consumer project submodule environment:
       __file__ = <consumer>/leafcutter/scripts/release/compute_next_version.py
       parents[2] = <consumer>/leafcutter/ — .git is a *file* (submodule pointer)
       .git exists() == True, so parents[2] is returned correctly
    """
    resolved_self = Path(__file__).resolve()
    p2 = resolved_self.parents[2]
    # .git may be a directory (normal clone) or a file (submodule / worktree link)
    if (p2 / ".git").exists():
        return p2
    return resolved_self.parents[3]


def _resolve_changelogs_dir(repo_root: Path) -> Path:
    """Resolve the changelogs directory path."""
    import json

    config_paths = [
        repo_root / "leafcutter" / "templates" / "scripts" / "commit_guardian" / "commit_guardian.json",
        repo_root / "leafcutter" / "templates" / "commit-guardian" / "commit_guardian.json",
        repo_root / "templates" / "scripts" / "commit_guardian" / "commit_guardian.json",
    ]
    for config_path in config_paths:
        if config_path.exists():
            try:
                with config_path.open(encoding="utf-8") as fh:
                    config = json.load(fh)
                return repo_root / config.get("changelogs_dir", "changelogs")
            except (OSError, json.JSONDecodeError):
                pass
    return repo_root / "changelogs"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _find_last_version_tag(repo_root: Path) -> Optional[str]:
    """Find the most recent v* tag by version sort.

    Returns the tag name (e.g. 'v1.2.3') or None if no v* tags exist.
    """
    try:
        result = subprocess.run(
            ["git", "tag", "--sort=-version:refname", "--list", "v*"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            check=True,
        )
        tags = [t.strip() for t in result.stdout.strip().split("\n") if t.strip()]
        return tags[0] if tags else None
    except (subprocess.CalledProcessError, IndexError):
        return None


def _changelog_entries_since(tag: Optional[str], changelogs_dir: Path, repo_root: Path) -> list[Path]:
    """Find changelog entry files committed after the given tag.

    When tag is None (no previous release), returns all entries.
    """
    if not changelogs_dir.is_dir():
        return []

    if tag is None:
        return sorted(changelogs_dir.glob("*.md"))

    try:
        result = subprocess.run(
            ["git", "log", f"{tag}^..HEAD", "--name-only", "--pretty=format:", "--", str(changelogs_dir)],
            capture_output=True,
            text=True,
            cwd=repo_root,
            check=True,
        )
        files = {line.strip() for line in result.stdout.strip().split("\n") if line.strip()}
        entries = []
        for f in files:
            p = repo_root / f
            if p.exists() and p.suffix == ".md":
                entries.append(p)
        return sorted(entries)
    except subprocess.CalledProcessError:
        return sorted(changelogs_dir.glob("*.md"))


# ---------------------------------------------------------------------------
# Frontmatter parsing (stdlib-only)
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _parse_frontmatter(path: Path) -> dict[str, str | bool]:
    """Parse YAML frontmatter from a changelog entry file.

    Returns a flat dict with string values for most fields and bool for
    'breaking'. Only parses the fields relevant to version computation.
    """
    content = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}

    result: dict[str, str | bool] = {}
    for line in match.group(1).split("\n"):
        line = line.strip()
        if ":" not in line or line.startswith("-") or line.startswith("#"):
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key == "breaking":
            result["breaking"] = value.lower() == "true"
        elif key == "type":
            result["type"] = value

    return result


# ---------------------------------------------------------------------------
# Version computation
# ---------------------------------------------------------------------------


def _compute_bump(entries: list[Path]) -> str:
    """Determine the bump level from a set of changelog entries.

    Returns 'major', 'minor', or 'patch'.
    """
    has_feature = False

    for entry in entries:
        fm = _parse_frontmatter(entry)
        if fm.get("breaking") is True:
            return "major"
        if fm.get("type") in {"feature", "epic_completion"}:
            has_feature = True

    return "minor" if has_feature else "patch"


def _parse_version(tag: str) -> tuple[int, int, int]:
    """Parse a v-prefixed SemVer tag into (major, minor, patch)."""
    version_str = tag.lstrip("v")
    parts = version_str.split(".")
    return int(parts[0]), int(parts[1]), int(parts[2])


def _bump_version(tag: str, bump: str) -> str:
    """Apply a bump to a version tag and return the new version string."""
    major, minor, patch = _parse_version(tag)

    if bump == "major":
        return f"v{major + 1}.0.0"
    elif bump == "minor":
        return f"v{major}.{minor + 1}.0"
    else:
        return f"v{major}.{minor}.{patch + 1}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for compute_next_version."""
    parser = argparse.ArgumentParser(
        prog="compute_next_version",
        description="Compute the next SemVer version from changelog entries since the last v* tag.",
    )
    parser.add_argument(
        "--tag",
        action="store_true",
        help="Create the computed git tag (requires clean working tree).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Override repo root detection (for testing).",
    )
    parser.add_argument(
        "--changelogs-dir",
        type=Path,
        default=None,
        help="Override changelogs directory (for testing).",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root or _resolve_repo_root()
    changelogs_dir = args.changelogs_dir or _resolve_changelogs_dir(repo_root)

    last_tag = _find_last_version_tag(repo_root)
    baseline = last_tag or "v0.0.0"

    entries = _changelog_entries_since(last_tag, changelogs_dir, repo_root)

    if not entries:
        print(baseline)
        return

    bump = _compute_bump(entries)
    next_version = _bump_version(baseline, bump)

    if args.tag:
        try:
            subprocess.run(
                ["git", "rev-parse", next_version],
                capture_output=True,
                text=True,
                cwd=repo_root,
                check=True,
            )
            print(f"Tag {next_version} already exists", file=sys.stderr)
            print(next_version)
            return
        except subprocess.CalledProcessError:
            pass

        try:
            subprocess.run(
                ["git", "tag", next_version],
                cwd=repo_root,
                check=True,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            raise subprocess.SubprocessError(  # noqa: TRY003
                f"Failed to create git tag {next_version}: {exc}"
            ) from exc
        print(f"Tagged {next_version}")
    else:
        print(next_version)


if __name__ == "__main__":
    main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-26 [python-coder/EPIC-LeafcutterVersioning/02]: (#EPIC-LeafcutterVersioning/02)
#   Created module. Implements automated SemVer computation by scanning
#   changelog entries since last v* tag. Uses git log to find entries
#   committed after the tag, parses YAML frontmatter with stdlib regex,
#   and applies bump logic: any breaking=true → MAJOR, any type=feature
#   → MINOR, otherwise PATCH. --tag flag stamps the git tag. --repo-root
#   and --changelogs-dir flags provided for testability. Stdlib-only.
#
# - 2026-05-28 [python-coder/TICKET-20260528-FixComputeNextVersionBugs]: (#TICKET-20260528-FixComputeNextVersionBugs)
#   Fixed two silent correctness bugs discovered during EPIC-FrontendAgent
#   finalization (commit 31d135c tagged v0.1.7):
#   Bug 1 (_compute_bump): Changed `fm.get("type") == "feature"` to
#     `fm.get("type") in {"feature", "epic_completion"}` so that changelog
#     entries written by changelog-agent with type: epic_completion (standard
#     for all epic completions) correctly trigger a minor bump. Without this
#     fix, no future epic completion would ever produce a version bump.
#   Bug 2 (_changelog_entries_since): Changed git log range from `{tag}..HEAD`
#     (exclusive — misses the tag commit) to `{tag}^..HEAD` (caret notation —
#     includes the tag commit itself). This fixes silent invisibility of changelog
#     entries committed in the same commit as the tag. The caret notation is safe:
#     `{tag}^` is the parent of the tag commit; entries predating the tag remain
#     excluded by the `..HEAD` right boundary. Shallow-clone edge case (where
#     `{tag}^` may not exist) is already handled by the existing
#     `except subprocess.CalledProcessError` fallback (returns all entries).
# - 2026-05-30 [python-coder/TICKET-20260530-FixRepoRootSubmoduleResolution]:
#   Fixed _resolve_repo_root() to handle .git-as-file (submodule topology).
#   Changed (p2 / ".git").is_dir() to .exists() so that submodule pointer
#   files are recognised. Without this fix, consumer projects using leafcutter
#   as a submodule resolved to the consumer root, producing wrong versions.
# ====================================================================
