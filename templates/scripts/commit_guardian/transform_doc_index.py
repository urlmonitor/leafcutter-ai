"""
MODULE: leafcutter/scripts/commit_guardian/transform_doc_index.py
GOAL: Pre-stage transformer that regenerates docs/INDEX.md and re-stages it
      whenever at least one staged file is under docs/ (excluding INDEX.md
      itself), so the index is always current at commit time.
BUSINESS CONTEXT: docs/INDEX.md drifts between build.py runs because nothing
      regenerates it per-commit. This hook auto-regenerates it before the
      doc-frontmatter and description-field validators run, so INDEX.md
      frontmatter always passes validation without manual intervention.
ARCHITECTURE: Reads staged .md files under docs/ via git diff --cached.
      If any qualifying file is staged (docs/*.md, but NOT docs/INDEX.md),
      calls generate_doc_index.write_index() as a library call (no subprocess)
      and re-stages docs/INDEX.md via git add. Exits 0 always (fail-open
      contract — never blocks a commit).

====================================================================
DECISION HISTORY
====================================================================
- 2026-07-15 [TICKET-20260715-DocIndexAutoRegen]: Initial implementation.
  Mirrors transform_doc_frontmatter.py structure. Fail-open contract.
  Ordered before check-doc-frontmatter and check-description-field in
  commit_guardian.json so generator-emitted frontmatter survives validation.
====================================================================
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DOCS_FILE_PATTERN = re.compile(r"^docs/.*\.md$")
_INDEX_MD_PATH = "docs/INDEX.md"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _get_staged_docs_files() -> list[str]:
    """Return staged .md file paths under docs/, excluding docs/INDEX.md.

    Queries git for staged file names and filters to files matching
    ``^docs/.*\\.md$`` but excluding ``docs/INDEX.md`` itself to avoid
    triggering an infinite re-stage loop.

    Args: None

    Returns:
        List of repo-relative staged file paths (possibly empty). Returns
        an empty list and prints a warning on any subprocess error.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        print(
            f"[transform-doc-index] WARNING: git diff failed: {exc}",
            file=sys.stderr,
        )
        return []

    if result.returncode != 0:
        return []

    paths = []
    for line in result.stdout.splitlines():
        p = line.strip()
        if _DOCS_FILE_PATTERN.match(p) and p != _INDEX_MD_PATH:
            paths.append(p)
    return paths


def _restage_index(index_path: Path) -> None:
    """Re-stage docs/INDEX.md after in-place regeneration.

    Args:
        index_path: Absolute path to the docs/INDEX.md file to re-stage.
    """
    try:
        result = subprocess.run(
            ["git", "add", str(index_path)],
            capture_output=True,
        )
    except OSError as exc:
        print(
            f"[transform-doc-index] WARNING: git add failed for {index_path}: {exc}",
            file=sys.stderr,
        )
        return
    if result.returncode != 0:
        print(
            f"[transform-doc-index] WARNING: git add exited with code {result.returncode}",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(repo_root: Path | None = None) -> int:
    """Entry point for the doc-index regeneration pre-commit hook.

    Regenerates docs/INDEX.md and re-stages it when a docs/*.md file
    (other than docs/INDEX.md itself) is among the staged changes. Exits 0
    always — this hook must never block a commit (fail-open contract).

    Args:
        repo_root: Repository root path. Defaults to the git top-level
            directory inferred from this script's position in the tree.
            Passed explicitly in tests to use a temporary directory.

    Returns:
        int: Always 0 (fail-open — errors are logged but never block commits).
    """
    staged = _get_staged_docs_files()
    if not staged:
        return 0

    if repo_root is None:
        # Resolve repo root from this file's location:
        # templates/scripts/commit_guardian/ → 3 parents → repo root
        # .leafcutter/scripts/commit_guardian/ → 3 parents → project root
        repo_root = Path(__file__).resolve().parents[3]

    index_path = repo_root / "docs" / "INDEX.md"

    try:
        index_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(
            f"[transform-doc-index] WARNING: cannot create docs/ directory: {exc}",
            file=sys.stderr,
        )
        return 0

    # Deferred import of generate_doc_index so sys.path is set up first.
    scripts_dir = Path(__file__).resolve().parents[3] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    try:
        import generate_doc_index as _gdi  # noqa: PLC0415
        _gdi.write_index(repo_root, index_path)
    except (ImportError, OSError) as exc:
        print(
            f"[transform-doc-index] WARNING: index regeneration failed: {exc}",
            file=sys.stderr,
        )
        return 0

    _restage_index(index_path)
    print(
        f"[transform-doc-index] Regenerated and restaged {index_path} "
        f"({len(staged)} staged docs file(s) triggered it)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ImportError, ValueError) as exc:
        print(f"[transform-doc-index] unexpected error, skipping: {exc}", file=sys.stderr)
        sys.exit(0)
