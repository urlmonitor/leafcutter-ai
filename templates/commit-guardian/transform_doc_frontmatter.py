"""
MODULE: leafcutter/scripts/commit_guardian/transform_doc_frontmatter.py
GOAL: Pre-stage transformer that fills missing YAML frontmatter fields
      (created, last_updated, type, status) in staged docs/*.md files before
      the check_doc_frontmatter validator runs, so the validator is a no-op
      for documents with deterministic missing fields.
BUSINESS CONTEXT: Any docs file staged with a missing created, last_updated,
      type, or status field causes check_doc_frontmatter to fail, forcing a
      manual edit.  These fields are fully deterministic and can be filled from
      context (current date, project config defaults) with no judgment.  This
      transformer runs at the pre-commit stage, before the validator, and
      silently fills those fields so the validator never fires for them.
ARCHITECTURE: Reads staged .md files under the configured docs_dir from
      commit_guardian.json.  For each file:
      1. Parses YAML frontmatter (fail-open: skip on parse failure).
      2. Fills missing created / last_updated with today's date.
      3. Fills missing type / status from doc_frontmatter defaults config.
      4. Only writes when at least one field changed (never overwrites present values).
      5. Runs git add on the file to re-stage the corrected content.
      Exits 0 always (fail-open contract).

====================================================================
DECISION HISTORY
====================================================================
- 2026-06-17 [EPIC-PrecommitSafetyNet/02]: Initial implementation.
  Fills missing created, last_updated, type, status fields from defaults.
  Modeled on transform_decision_history.py. Public API: transform_content().
====================================================================
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date
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
# Config / defaults
# ---------------------------------------------------------------------------

_DEFAULT_DOCS_DIR = "docs"
_DEFAULT_TYPE = "how-to"
_DEFAULT_STATUS = "draft"

_DATE_FIELDS = ("created", "last_updated")
_ENUM_FIELDS = ("type", "status")


# ---------------------------------------------------------------------------
# Frontmatter parsing helpers
# ---------------------------------------------------------------------------


def _split_frontmatter(content: str) -> tuple[str, str, str] | None:
    """Split Markdown content into (opening_delim, frontmatter_body, rest).

    Returns None when the content does not start with a YAML frontmatter block.

    Args:
        content: Full file content as a string.

    Returns:
        Tuple of (delimiter, frontmatter_body, remainder) or None.
    """
    if not content.startswith("---"):
        return None
    lines = content.split("\n")
    if len(lines) < 2:
        return None
    # Find the closing ---
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
            f"[transform-doc-frontmatter] WARNING: YAML parse failed: {exc}",
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
    # Ensure no trailing newline issues
    fm_yaml = fm_yaml.rstrip("\n")
    if rest.startswith("\n"):
        return f"---\n{fm_yaml}\n---{rest}"
    return f"---\n{fm_yaml}\n---\n{rest}"


# ---------------------------------------------------------------------------
# Public transform API (called by tests directly)
# ---------------------------------------------------------------------------


def transform_content(content: str, today_date: str, defaults: dict) -> tuple[str, int]:
    """Fill missing frontmatter fields in a docs Markdown file content.

    Only fills fields that are absent; never overwrites fields that already
    have a value.  Fails open: returns (content, 0) when frontmatter is
    absent or cannot be parsed.

    Args:
        content: Full file content as a string.
        today_date: ISO date string to use for created / last_updated fields
            (e.g. ``"2026-06-17"``).
        defaults: Dict with optional keys ``"type"`` and ``"status"`` whose
            values are used as defaults when those fields are absent.

    Returns:
        Tuple of (new_content, changed_count) where changed_count is the
        number of fields that were added.
    """
    parts = _split_frontmatter(content)
    if parts is None:
        return content, 0

    _delim, fm_body, rest = parts
    fm_dict = _parse_frontmatter(fm_body)
    if fm_dict is None:
        return content, 0

    changed = 0

    for field in _DATE_FIELDS:
        if field not in fm_dict or fm_dict[field] is None:
            fm_dict[field] = today_date
            changed += 1

    default_type = defaults.get("type", _DEFAULT_TYPE)
    default_status = defaults.get("status", _DEFAULT_STATUS)

    if "type" not in fm_dict or fm_dict["type"] is None:
        fm_dict["type"] = default_type
        changed += 1

    if "status" not in fm_dict or fm_dict["status"] is None:
        fm_dict["status"] = default_status
        changed += 1

    if changed == 0:
        return content, 0

    new_content = _rebuild_content(fm_dict, rest)
    return new_content, changed


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
            f"[transform-doc-frontmatter] WARNING: git diff failed: {exc}",
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
            f"[transform-doc-frontmatter] WARNING: git add failed for {file_path}: {exc}",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def _load_config() -> dict:
    """Load doc_frontmatter config section from commit_guardian.json.

    Returns:
        The doc_frontmatter config dict, or an empty dict on any error.
    """
    config_path = Path(__file__).resolve().parent / "commit_guardian.json"
    try:
        import json
        with open(config_path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("doc_frontmatter", {})
    except (OSError, ValueError) as exc:
        print(
            f"[transform-doc-frontmatter] WARNING: could not load config: {exc}",
            file=sys.stderr,
        )
        return {}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Entry point for the pre-stage transformer hook.

    Reads staged docs .md files, fills missing frontmatter fields in place,
    re-stages each modified file, then exits 0.

    Returns:
        int: Always 0 (fail-open — errors are logged but never block commits).
    """
    today_date = date.today().isoformat()
    config = _load_config()
    docs_dir = config.get("docs_dir", _DEFAULT_DOCS_DIR)
    allowed_types = config.get("allowed_types", [_DEFAULT_TYPE])
    allowed_statuses = config.get("allowed_statuses", [_DEFAULT_STATUS])

    defaults = {
        "type": allowed_types[0] if allowed_types else _DEFAULT_TYPE,
        "status": allowed_statuses[0] if allowed_statuses else _DEFAULT_STATUS,
    }

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
                f"[transform-doc-frontmatter] WARNING: could not read {file_path}: {exc}",
                file=sys.stderr,
            )
            continue

        new_content, changed = transform_content(content, today_date, defaults)

        if changed > 0:
            try:
                path.write_text(new_content, encoding="utf-8")
                _restage_file(file_path)
                print(
                    f"[transform-doc-frontmatter] {file_path}: "
                    f"filled {changed} missing frontmatter field(s)",
                    file=sys.stderr,
                )
            except OSError as exc:
                print(
                    f"[transform-doc-frontmatter] WARNING: could not write {file_path}: {exc}",
                    file=sys.stderr,
                )

    return 0


if __name__ == "__main__":
    sys.exit(main())
