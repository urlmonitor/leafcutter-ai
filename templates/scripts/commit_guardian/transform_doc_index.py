"""
MODULE: leafcutter/scripts/commit_guardian/transform_doc_index.py
GOAL: Pre-stage transformer that regenerates docs/INDEX.md and re-stages it
      whenever at least one staged file is under docs/ (excluding INDEX.md
      itself), so the index is always current at commit time.
BUSINESS CONTEXT: docs/INDEX.md drifts between build.py runs because nothing
      regenerates it per-commit. This hook auto-regenerates it before the
      doc-frontmatter and description-field validators run, so INDEX.md
      frontmatter always passes validation without manual intervention.
ARCHITECTURE: Reads staged .md files under docs/ via git diff --cached with
      filter ACDMR (Added, Copied, Deleted, Modified, Renamed) so that doc
      deletions and renames also trigger regeneration.  If any qualifying file
      is staged (docs/*.md, but NOT docs/INDEX.md), calls
      generate_doc_index.generate_index() and writes the result only when it
      differs from the on-disk content (idempotency guard), then re-stages
      docs/INDEX.md via git add.  Exits 0 always (fail-open contract — never
      blocks a commit).

      generate_doc_index.py is located by searching an ordered list of
      candidate directories:
        1. <hook-dir>/../ — deployed layout: hook lives at
           <output_root>/scripts/commit_guardian/, generator is a sibling at
           <output_root>/scripts/.
        2. <repo-root>/scripts/ — source/git layout.
      The first directory containing generate_doc_index.py is prepended to
      sys.path.  repo_root is resolved via ``git rev-parse --show-toplevel``
      (pre-commit always sets CWD = repo root), which is layout-independent.

====================================================================
DECISION HISTORY
====================================================================
- 2026-07-15 [TICKET-20260715-DocIndexAutoRegen]: Initial implementation.
  Mirrors transform_doc_frontmatter.py structure. Fail-open contract.
  Ordered before check-doc-frontmatter and check-description-field in
  commit_guardian.json so generator-emitted frontmatter survives validation.
- 2026-07-15 [TICKET-20260715-DocIndexAutoRegen / defect-remediation]:
  Fixed repo-root resolution to use ``git rev-parse --show-toplevel``
  (parents[3] misresolved in deployed layout — produced workspace parent,
  not git root). Fixed generator import to search ordered candidate dirs
  instead of a hardcoded parents[3]/scripts path (generate_doc_index.py was
  absent from the deployed .leafcutter/scripts/ tree — silent no-op on every
  consumer). Changed --diff-filter=AM to --diff-filter=ACDMR so doc
  deletions and renames also trigger regeneration (otherwise a deleted doc
  leaves a stale INDEX entry). Added idempotency guard: INDEX.md is only
  written and re-staged when its content actually changed. Added ValueError
  to the regeneration except clause (UnicodeDecodeError is a ValueError,
  raised on non-UTF-8 docs — previously escaped main()).
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

    Queries git for staged file names using filter ``ACDMR`` (Added, Copied,
    Deleted, Modified, Renamed) and filters to files matching
    ``^docs/.*\\.md$`` but excluding ``docs/INDEX.md`` itself to avoid
    triggering an infinite re-stage loop.

    Args: None

    Returns:
        List of repo-relative staged file paths (possibly empty). Returns
        an empty list and prints a warning on any subprocess error.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACDMR"],
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


def _resolve_repo_root() -> Path:
    """Resolve the repository root via ``git rev-parse --show-toplevel``.

    Pre-commit always runs with CWD equal to the repository root, so this
    call reliably returns the correct root regardless of where the hook
    script lives in the directory tree (deployed layout, source layout, or
    worktree).

    Args: None

    Returns:
        Repository root as an absolute Path.  Falls back to ``Path.cwd()``
        (with a WARNING printed) if the subprocess call fails or returns
        an empty string.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            toplevel = result.stdout.strip()
            if toplevel:
                return Path(toplevel)
    except OSError as exc:
        print(
            f"[transform-doc-index] WARNING: git rev-parse failed: {exc}",
            file=sys.stderr,
        )
    cwd = Path.cwd()
    print(
        f"[transform-doc-index] WARNING: could not determine repo root via git, "
        f"falling back to cwd: {cwd}",
        file=sys.stderr,
    )
    return cwd


def _find_generator_module(repo_root: Path) -> object | None:
    """Find and import ``generate_doc_index`` from deployment or source candidates.

    Searches an ordered list of candidate directories for
    ``generate_doc_index.py`` and inserts the first found candidate onto
    ``sys.path`` (guard against duplicate inserts).  Candidates are:

    1. ``Path(__file__).resolve().parents[1]`` — deployed layout: hook lives
       at ``<output_root>/scripts/commit_guardian/``, generator is a sibling
       at ``<output_root>/scripts/``.
    2. ``repo_root / "scripts"`` — source/git layout.

    If neither candidate contains ``generate_doc_index.py``, a WARNING is
    printed with the searched paths and ``None`` is returned (fail-open).

    Args:
        repo_root: Repository root path (used for the source-layout candidate).

    Returns:
        The imported ``generate_doc_index`` module, or None if not found.
    """
    candidates = [
        Path(__file__).resolve().parents[1],  # deployed: <output_root>/scripts/
        repo_root / "scripts",                # source/git: <repo>/scripts/
    ]
    for candidate in candidates:
        if (candidate / "generate_doc_index.py").is_file():
            candidate_str = str(candidate)
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)
            break

    try:
        import generate_doc_index as _gdi  # noqa: PLC0415
    except ImportError as exc:
        searched = [str(c) for c in candidates]
        print(
            f"[transform-doc-index] WARNING: cannot import generate_doc_index "
            f"(searched {searched}): {exc}",
            file=sys.stderr,
        )
        return None
    else:
        return _gdi


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
    (other than docs/INDEX.md itself) is among the staged changes (added,
    copied, deleted, modified, or renamed).  An idempotency guard ensures
    INDEX.md is only written and re-staged when the freshly generated content
    actually differs from the on-disk file.  Exits 0 always — this hook must
    never block a commit (fail-open contract).

    Args:
        repo_root: Repository root path. When None (normal pre-commit
            invocation), resolved via ``git rev-parse --show-toplevel``.
            Pass an explicit Path in tests to use a temporary directory
            without triggering the git subprocess.

    Returns:
        int: Always 0 (fail-open — errors are logged but never block commits).
    """
    staged = _get_staged_docs_files()
    if not staged:
        return 0

    if repo_root is None:
        repo_root = _resolve_repo_root()

    index_path = repo_root / "docs" / "INDEX.md"

    try:
        index_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(
            f"[transform-doc-index] WARNING: cannot create docs/ directory: {exc}",
            file=sys.stderr,
        )
        return 0

    gdi = _find_generator_module(repo_root)
    if gdi is None:
        return 0

    try:
        new_content = gdi.generate_index(repo_root)
    except (ImportError, OSError, ValueError) as exc:
        print(
            f"[transform-doc-index] WARNING: index regeneration failed: {exc}",
            file=sys.stderr,
        )
        return 0

    # Idempotency guard: only write and re-stage when content actually changed.
    if index_path.exists():
        try:
            existing_content = index_path.read_text(encoding="utf-8")
            if existing_content == new_content:
                return 0
        except OSError as exc:
            print(
                f"[transform-doc-index] WARNING: cannot read existing {index_path}, "
                f"proceeding to overwrite: {exc}",
                file=sys.stderr,
            )

    try:
        index_path.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        print(
            f"[transform-doc-index] WARNING: failed to write {index_path}: {exc}",
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
