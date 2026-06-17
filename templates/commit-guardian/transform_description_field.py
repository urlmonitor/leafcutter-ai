"""
MODULE: leafcutter/scripts/commit_guardian/transform_description_field.py
GOAL: Pre-stage transformer that fills a missing ``description`` frontmatter
      field in staged docs/*.md files by deriving a stub from the ``title``
      field, before the check_description_field validator runs.
BUSINESS CONTEXT: Any docs file staged without a ``description`` field causes
      the check_description_field hook to fail.  When a ``title`` is present
      the description can be derived mechanically — no judgment needed.  This
      transformer runs before the validator and writes the stub in place so
      the validator never fires for that class of missing field.
ARCHITECTURE: Reads staged .md files under the configured docs_dir from
      commit_guardian.json.  For each file:
      1. Parses YAML frontmatter (fail-open: skip on parse failure).
      2. If ``description`` absent AND ``title`` present: writes a stub
         description derived from the title.
      3. If ``description`` already present or no ``title``: no edit.
      4. Only writes when a field was added; runs git add to re-stage.
      Exits 0 always (fail-open contract).

====================================================================
DECISION HISTORY
====================================================================
- 2026-06-17 [EPIC-PrecommitSafetyNet/02]: Initial implementation.
  Stubs missing description from title field. Public API: transform_content().
====================================================================
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Attempt to import yaml; fall back gracefully if unavailable
# ---------------------------------------------------------------------------

try:
    import yaml as _yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


# ---------------------------------------------------------------------------
# Config defaults
# ---------------------------------------------------------------------------

_DEFAULT_DOCS_DIR = "docs"


# ---------------------------------------------------------------------------
# Frontmatter parsing helpers (local, no shared import)
# ---------------------------------------------------------------------------


def _split_frontmatter(content: str) -> tuple[str, str, str] | None:
    """Split Markdown content into (delimiter, frontmatter_body, rest).

    Args:
        content: Full file content as a string.

    Returns:
        Tuple of (delimiter, frontmatter_body, remainder) or None when no
        YAML frontmatter block is found.
    """
    if not content.startswith("---"):
        return None
    lines = content.split("\n")
    if len(lines) < 2:
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm_body = "\n".join(lines[1:i])
            rest = "\n".join(lines[i + 1:])
            return ("---", fm_body, rest)
    return None


def _parse_frontmatter(fm_body: str) -> dict | None:
    """Parse YAML frontmatter body into a dict; return None on failure.

    Args:
        fm_body: Raw YAML string between the ``---`` delimiters.

    Returns:
        Parsed dict or None on parse error / unavailable yaml library.
    """
    if not _YAML_AVAILABLE:
        return None
    try:
        parsed = _yaml.safe_load(fm_body)
    except _yaml.YAMLError as exc:
        print(
            f"[transform-description-field] WARNING: YAML parse failed: {exc}",
            file=sys.stderr,
        )
        return None
    else:
        if not isinstance(parsed, dict):
            return None
        return parsed


def _rebuild_content(fm_dict: dict, rest: str) -> str:
    """Serialize frontmatter dict back to YAML and reassemble the file.

    Args:
        fm_dict: Frontmatter as a dict (possibly modified).
        rest: Remaining file content after the closing delimiter.

    Returns:
        Reassembled file content string.
    """
    if not _YAML_AVAILABLE:
        return ""
    fm_yaml = _yaml.dump(fm_dict, default_flow_style=False, allow_unicode=True, sort_keys=False)
    fm_yaml = fm_yaml.rstrip("\n")
    if rest.startswith("\n"):
        return f"---\n{fm_yaml}\n---{rest}"
    return f"---\n{fm_yaml}\n---\n{rest}"


# ---------------------------------------------------------------------------
# Description stub builder
# ---------------------------------------------------------------------------


def _stub_from_title(title: str) -> str:
    """Build a stub description string derived from a document title.

    Args:
        title: The raw title string from frontmatter.

    Returns:
        A short stub description sentence.
    """
    title = title.strip()
    if not title:
        return ""
    return f"Overview of {title}."


# ---------------------------------------------------------------------------
# Public transform API (called by tests directly)
# ---------------------------------------------------------------------------


def transform_content(content: str) -> tuple[str, int]:
    """Fill missing ``description`` field in a docs Markdown file content.

    When ``description`` is absent and ``title`` is present, writes a stub
    description derived from the title.  Never overwrites an existing
    ``description``.  Fails open: returns (content, 0) when frontmatter is
    absent, cannot be parsed, or when ``title`` is missing.

    Args:
        content: Full file content as a string.

    Returns:
        Tuple of (new_content, changed_count) where changed_count is 1 when
        the description field was added, 0 otherwise.
    """
    parts = _split_frontmatter(content)
    if parts is None:
        return content, 0

    _delim, fm_body, rest = parts
    fm_dict = _parse_frontmatter(fm_body)
    if fm_dict is None:
        return content, 0

    # description already present — no edit
    if "description" in fm_dict and fm_dict["description"] is not None:
        return content, 0

    # no title to derive from — fail-open
    title = fm_dict.get("title")
    if not title or not str(title).strip():
        return content, 0

    stub = _stub_from_title(str(title))
    if not stub:
        return content, 0

    fm_dict["description"] = stub
    new_content = _rebuild_content(fm_dict, rest)
    return new_content, 1


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _get_staged_docs_files(docs_dir: str) -> list[str]:
    """Return staged .md file paths under docs_dir.

    Args:
        docs_dir: Repository-relative path to the docs directory.

    Returns:
        List of staged file paths matching the docs glob.
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
            f"[transform-description-field] WARNING: git diff failed: {exc}",
            file=sys.stderr,
        )
        return []

    if result.returncode != 0:
        return []

    prefix = docs_dir.rstrip("/") + "/"
    paths = []
    for line in result.stdout.splitlines():
        p = line.strip()
        if p.startswith(prefix) and p.endswith(".md"):
            paths.append(p)
    return paths


def _restage_file(file_path: str) -> None:
    """Re-stage a file after in-place modification.

    Args:
        file_path: Repository-relative path to the file.
    """
    try:
        subprocess.run(
            ["git", "add", file_path],
            capture_output=True,
        )
    except OSError as exc:
        print(
            f"[transform-description-field] WARNING: git add failed for {file_path}: {exc}",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def _load_docs_dir() -> str:
    """Load the docs_dir value from commit_guardian.json.

    Returns:
        The docs_dir string from config, or the default ``"docs"`` on error.
    """
    config_path = Path(__file__).resolve().parent / "commit_guardian.json"
    try:
        import json
        with open(config_path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("doc_frontmatter", {}).get("docs_dir", _DEFAULT_DOCS_DIR)
    except (OSError, ValueError) as exc:
        print(
            f"[transform-description-field] WARNING: could not load config: {exc}",
            file=sys.stderr,
        )
        return _DEFAULT_DOCS_DIR


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Entry point for the pre-stage transformer hook.

    Reads staged docs .md files, fills missing description fields in place,
    re-stages each modified file, then exits 0.

    Returns:
        int: Always 0 (fail-open — errors are logged but never block commits).
    """
    docs_dir = _load_docs_dir()
    staged = _get_staged_docs_files(docs_dir)
    if not staged:
        return 0

    for file_path in staged:
        path = Path(file_path)
        if not path.exists():
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(
                f"[transform-description-field] WARNING: could not read {file_path}: {exc}",
                file=sys.stderr,
            )
            continue

        new_content, changed = transform_content(content)

        if changed > 0:
            try:
                path.write_text(new_content, encoding="utf-8")
                _restage_file(file_path)
                print(
                    f"[transform-description-field] {file_path}: "
                    "stub description added from title",
                    file=sys.stderr,
                )
            except OSError as exc:
                print(
                    f"[transform-description-field] WARNING: could not write {file_path}: {exc}",
                    file=sys.stderr,
                )

    return 0


if __name__ == "__main__":
    sys.exit(main())
