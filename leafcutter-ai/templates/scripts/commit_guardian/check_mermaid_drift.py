"""
MODULE: check_mermaid_drift.py
GOAL: Pre-commit hook that blocks commits where mermaid diagrams have drifted
      out of sync with the code they document.
BUSINESS CONTEXT: Architecture diagrams become stale when the code they document
                  changes without the diagram being updated. This hook enforces
                  synchronisation by checking an embedded hash marker beneath the
                  mermaid fence against the current hash of the related_code or
                  related_surfaces files.
ARCHITECTURE: Reads each staged docs/architecture/**/*.md file, checks diagram_type
              against data_flow / user_flow coverage genres, computes SHA-256 of
              related files, and compares against the embedded marker. Skips all
              other diagram types. Respects [NO-ARCH-UPDATE] bypass.

====
DECISION HISTORY
- 2026-05-14 20:00 [EPIC-ArchitectureDocsEnforcement/ticket 06 — Hendrik/Claude]:
  Created as standalone hook scoped to coverage genres only (data_flow, user_flow).
  Sequence, container, context, erd, state diagrams have no related-code contract
  and are unconditionally skipped. Hash algorithm is SHA-256 truncated to 8 hex
  chars for readability.
====
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BYPASS_TOKEN = "[NO-ARCH-UPDATE]"
_HASH_COMMENT_RE = re.compile(r"<!--\s*related-code-hash:([0-9a-f]{8})\s*-->", re.IGNORECASE)
_COVERAGE_GENRES = {"data_flow", "user_flow"}
_COVERAGE_FIELD: dict[str, str] = {
    "data_flow": "related_code",
    "user_flow": "related_surfaces",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_staged_files() -> list[Path]:
    """Return list of staged file paths from git diff.

    Returns:
        List of Path objects for each file currently staged in the index.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [Path(p) for p in result.stdout.splitlines() if p.strip()]


def _get_commit_message() -> str:
    """Read the pending commit message from COMMIT_EDITMSG if available.

    Returns:
        The commit message string, or empty string when unavailable.
    """
    try:
        msg_file = Path(
            subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        ) / "COMMIT_EDITMSG"
        if msg_file.exists():
            return msg_file.read_text(encoding="utf-8")
    except (subprocess.CalledProcessError, OSError):
        pass
    return ""


def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from a markdown file.

    Args:
        content: Full text content of a markdown file.

    Returns:
        Parsed frontmatter as a dict, or empty dict when no frontmatter found.
    """
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end == -1:
        return {}
    try:
        return yaml.safe_load(content[3:end]) or {}
    except yaml.YAMLError:
        return {}


def _compute_file_hash(paths: list[str], repo_root: Path) -> str:
    """Compute a combined SHA-256 hash of the given file paths.

    Files are sorted before concatenation to ensure hash stability regardless
    of list order. Missing files are silently skipped.

    Args:
        paths: List of file path strings relative to the repo root.
        repo_root: Absolute path to the repository root.

    Returns:
        First 8 hex characters of the SHA-256 digest, or empty string when
        no readable files are found.
    """
    hasher = hashlib.sha256()
    found_any = False
    for rel_path in sorted(paths):
        abs_path = repo_root / rel_path
        if abs_path.exists():
            try:
                hasher.update(abs_path.read_bytes())
                found_any = True
            except OSError:
                pass
    if not found_any:
        return ""
    return hasher.hexdigest()[:8]


def _extract_hash_marker(body: str) -> str | None:
    """Extract the related-code-hash value from a diagram file body.

    Args:
        body: Full text content of the diagram markdown file.

    Returns:
        The 8-char hex hash string when found, or None when absent.
    """
    match = _HASH_COMMENT_RE.search(body)
    if match:
        return match.group(1).lower()
    return None


def _check_diagram_file(path: Path, repo_root: Path) -> list[str]:
    """Check a single architecture diagram file for hash drift.

    Args:
        path: Path to the diagram file (relative to repo root).
        repo_root: Absolute path to the repository root.

    Returns:
        List of error message strings (empty list means no violations).
    """
    abs_path = repo_root / path
    if not abs_path.exists():
        return []

    try:
        content = abs_path.read_text(encoding="utf-8")
    except OSError:
        return []

    fm = _parse_frontmatter(content)
    diagram_type = fm.get("diagram_type", "")

    if diagram_type not in _COVERAGE_GENRES:
        return []

    field_name = _COVERAGE_FIELD[diagram_type]
    related_paths = fm.get(field_name) or []
    if isinstance(related_paths, str):
        related_paths = [related_paths]

    if not related_paths:
        return [
            f"diagram drift: '{path}' has diagram_type '{diagram_type}' but no "
            f"'{field_name}:' in frontmatter — add the field or use {_BYPASS_TOKEN}."
        ]

    errors: list[str] = []
    computed = _compute_file_hash(related_paths, repo_root)
    if not computed:
        return []

    embedded = _extract_hash_marker(content)
    if embedded is None:
        errors.append(
            f"diagram drift: missing related-code-hash marker in '{path}'; "
            f"run `python scripts/commit_guardian/compute_diagram_hash.py {path}` "
            f"to generate it."
        )
    elif embedded != computed:
        errors.append(
            f"diagram drift: related_code hash mismatch for '{path}' — "
            f"embedded={embedded}, current={computed}. "
            f"Update the diagram and regenerate the hash using "
            f"`python scripts/commit_guardian/compute_diagram_hash.py {path}`, "
            f"or use {_BYPASS_TOKEN} to acknowledge technical debt."
        )

    return errors


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the mermaid drift check on all staged architecture diagram files.

    Returns:
        Exit code: 0 when all checks pass or bypass is active, 1 on any violation.
    """
    commit_msg = _get_commit_message()
    if _BYPASS_TOKEN in commit_msg:
        return 0

    try:
        repo_root = Path(
            subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
    except subprocess.CalledProcessError:
        print("check-mermaid-drift: could not determine repo root — skipping.", file=sys.stderr)
        return 0

    staged = _get_staged_files()
    arch_docs = [
        p for p in staged
        if str(p).startswith("docs/architecture/") and p.suffix == ".md"
    ]

    if not arch_docs:
        return 0

    all_errors: list[str] = []
    for doc_path in arch_docs:
        all_errors.extend(_check_diagram_file(doc_path, repo_root))

    if all_errors:
        for err in all_errors:
            print(f"[check-mermaid-drift] {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
