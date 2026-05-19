"""
MODULE: check_debug_scripts
GOAL: Pre-commit hook to enforce metadata tagging on new/modified debug scripts.
BUSINESS CONTEXT: Prevents untagged debug scripts from accumulating in the codebase.
DEPENDENCIES: Python stdlib only (subprocess, sys, pathlib, re)
PERFORMANCE: O(n) over staged files — fast since only debugging/scripts/ files are checked.
ARCHITECTURE: Not needed.
"""
import re
import subprocess
import sys
import argparse
from pathlib import Path

# Fix import path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.commit_guardian.config import (
    DEBUG_VALID_CATEGORIES,
    DEBUG_REQUIRED_TAGS,
    DEBUG_CONTEXT_TAGS,
    DEBUG_EXEMPT_NAMES,
    DEBUG_EXEMPT_DIRS,
)

# Local aliases for backwards compatibility within this file
VALID_CATEGORIES = DEBUG_VALID_CATEGORIES
REQUIRED_TAGS = DEBUG_REQUIRED_TAGS
CONTEXT_TAGS = DEBUG_CONTEXT_TAGS
EXEMPT_NAMES = DEBUG_EXEMPT_NAMES
EXEMPT_DIRS = DEBUG_EXEMPT_DIRS


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------
def get_staged_debug_scripts() -> dict[str, str]:
    """Get staged files under debugging/scripts/ with their git status.

    Returns:
        dict[str, str]: Mapping of filepath to git status code.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError:
        return {}

    staged = {}
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        filepath = parts[-1]
        # Only check files under debugging/scripts/
        if filepath.startswith("debugging/scripts/"):
            staged[filepath] = status
    return staged


# ---------------------------------------------------------------------------
# Tag parsing (mirrors the skill script logic)
# ---------------------------------------------------------------------------
def _extract_tags(text: str) -> dict[str, str]:
    """Extract KEY: value pairs from a text block.

    Args:
        text: Text block to parse for tag lines.

    Returns:
        dict[str, str]: Mapping of uppercase tag names to their values.
    """
    tags = {}
    all_keys = REQUIRED_TAGS + CONTEXT_TAGS
    for key in all_keys:
        pattern = re.compile(
            rf"^\s*{re.escape(key)}\s*:\s*(.+)$",
            re.MULTILINE | re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            tags[key.upper()] = match.group(1).strip()
    return tags


def parse_python_tags(content: str) -> dict[str, str]:
    """Extract tags from a Python file's docstring.

    Args:
        content: Full file content.

    Returns:
        dict[str, str]: Parsed metadata tags.
    """
    match = re.search(r'^(?:#!/.*\n)?(?:#.*\n)*\s*"""(.*?)"""', content, re.DOTALL)
    if not match:
        match = re.search(r"^(?:#!/.*\n)?(?:#.*\n)*\s*'''(.*?)'''", content, re.DOTALL)
    return _extract_tags(match.group(1)) if match else {}


def parse_sql_tags(content: str) -> dict[str, str]:
    """Extract tags from a SQL file's block comment.

    Args:
        content: Full file content.

    Returns:
        dict[str, str]: Parsed metadata tags.
    """
    match = re.search(r'/\*(.*?)\*/', content, re.DOTALL)
    return _extract_tags(match.group(1)) if match else {}


def parse_bash_tags(content: str) -> dict[str, str]:
    """Extract tags from bash comment lines at the top of a file.

    Args:
        content: Full file content.

    Returns:
        dict[str, str]: Parsed metadata tags.
    """
    lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#!"):
            continue
        if stripped.startswith("#"):
            lines.append(stripped.lstrip("# ").strip())
        elif stripped == "":
            continue
        else:
            break
    return _extract_tags("\n".join(lines))


def _parse_tags_for_ext(content: str, ext: str) -> dict[str, str]:
    """Parse tags from file content based on file extension.

    Args:
        content: Full file content.
        ext: File extension including dot (e.g. '.py').

    Returns:
        dict[str, str]: Parsed metadata tags, empty if extension unsupported.
    """
    parsers = {".py": parse_python_tags, ".sql": parse_sql_tags, ".sh": parse_bash_tags}
    parser = parsers.get(ext)
    return parser(content) if parser else {}


def _check_required_tags(tags: dict[str, str]) -> list[str]:
    """Check that all required tags are present and non-TODO.

    Args:
        tags: Parsed tags dictionary.

    Returns:
        list[str]: Error messages for missing or empty tags.
    """
    errors = []
    for tag in REQUIRED_TAGS:
        if tag.upper() not in tags:
            errors.append(f"Missing required tag: {tag}")
        elif not tags[tag.upper()].strip() or tags[tag.upper()].strip().upper() == "TODO":
            errors.append(f"Tag '{tag}' is empty or still set to TODO")
    return errors


def _check_context_tags(tags: dict[str, str]) -> list[str]:
    """Check at least one context tag is present and non-TODO.

    Args:
        tags: Parsed tags dictionary.

    Returns:
        list[str]: Error messages if no valid context tag found.
    """
    for tag in CONTEXT_TAGS:
        val = tags.get(tag.upper(), "").strip()
        if val and val.upper() != "TODO":
            return []
    return [f"At least one context tag required (non-TODO): {', '.join(CONTEXT_TAGS)}"]


def _check_category_folder(tags: dict[str, str], path: Path) -> list[str]:
    """Check that the script is in the correct subfolder for its category.

    Args:
        tags: Parsed tags dictionary.
        path: Path to the script file.

    Returns:
        list[str]: Error messages for category/folder mismatches.
    """
    cat = tags.get("CATEGORY", "").strip().lower()
    if cat in VALID_CATEGORIES and path.parent.name != cat:
        return [f"Script is in '{path.parent.name}/' but CATEGORY is '{cat}'. Move to debugging/scripts/{cat}/"]
    if cat and cat not in VALID_CATEGORIES and cat != "todo":
        return [f"Invalid CATEGORY '{cat}'. Valid: {', '.join(VALID_CATEGORIES)}"]
    return []


def validate_debug_script(filepath: str) -> list[str]:
    """Validate a debug script has proper metadata.

    Args:
        filepath: Path to the debug script.

    Returns:
        list[str]: Validation errors, empty if compliant.
    """
    path = Path(filepath)

    # Skip exempt files/dirs
    if path.name in EXEMPT_NAMES or path.suffix.lower() not in (".py", ".sql", ".sh"):
        return []
    if any(exempt in path.parts for exempt in EXEMPT_DIRS):
        return []

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"Could not read file: {e}"]

    tags = _parse_tags_for_ext(content, path.suffix.lower())
    return _check_required_tags(tags) + _check_context_tags(tags) + _check_category_folder(tags, path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def configure_stdout() -> None:
    """Ensure output works on Windows with UTF-8."""
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check debug script metadata requirements."
    )
    parser.add_argument(
        "--file",
        help="Specific file to check (bypasses git staged files).",
    )
    args = parser.parse_args()

    configure_stdout()

    # Determine files to check
    if args.file:
        files_to_check = {args.file: "M"}
    else:
        files_to_check = get_staged_debug_scripts()

    if not files_to_check:
        return 0

    failed_checks = []
    passed_count = 0

    for filepath, status in files_to_check.items():
        # Skip deleted files
        if status.startswith("D"):
            continue

        path = Path(filepath)

        # Skip non-script files
        if path.suffix.lower() not in (".py", ".sql", ".sh"):
            continue

        # Skip exempt items
        if path.name in EXEMPT_NAMES:
            continue
        if any(exempt in path.parts for exempt in EXEMPT_DIRS):
            continue

        errors = validate_debug_script(filepath)
        if errors:
            error_lines = "\n".join(f"   • {e}" for e in errors)
            failed_checks.append(
                f"❌ DEBUG SCRIPT METADATA MISSING: '{filepath}'\n{error_lines}\n"
                f"   📖 See: .agents/skills/debug-script-manager/SKILL.md for format"
            )
        else:
            passed_count += 1

    if failed_checks:
        print("\n🏷️  Debug Script Metadata Check Failed\n")
        for msg in failed_checks:
            print(msg)
            print()
        return 1

    if passed_count > 0:
        print(f"✅ PASSED: {passed_count} debug script(s) have proper metadata")

    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-04-29 06:12 [Hendrik]: Initial implementation. Blocks commits
  for untagged debug scripts under debugging/scripts/ (excluding _legacy/).
  Validates required tags, category values, context tags, and subfolder placement.
====================================================================
"""
