"""
Pre-commit hook to block commits that do not meet documentation standards.

Checks:
1. Any modified or new .py or .sql file must have a README.md in its parent directory.
2. NEW .sql files must have a header containing "Object Name:", "Goal:", "Business Context:".
3. NEW .py files (excluding __init__.py and specific folders) must have a module docstring containing "MODULE:", "GOAL:", "BUSINESS CONTEXT:".

Exit Codes:
    0 - All files meet documentation standards
    1 - One or more files are missing required documentation

Usage:
    poetry run python scripts/commit_guardian/check_documentation.py
"""

import subprocess
import sys
import argparse
from pathlib import Path

from _resolve_root import find_project_root

project_root = find_project_root()

from check_root_files import ALLOWED_ROOT_FILES, ALLOWED_EXTENSIONS
from config import (
    EXCLUDED_DIRS,
    SQL_REQUIRED_FIELDS,
    PYTHON_REQUIRED_FIELDS,
)
from doc_validators import (
    extract_header_text,
    verify_decision_history,
    _validate_architecture,
    validate_tail_tags_in_diff,
    report_legacy_untagged,
)


def get_staged_files() -> dict[str, str]:
    """Get all staged files with their status."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
    except subprocess.CalledProcessError:
        return {}

    staged_files = {}
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            status = parts[0]
            filepath = parts[-1]
            staged_files[filepath] = status

    return staged_files


def is_in_excluded_dir(filepath: str) -> bool:
    """Check if the file is in a directory we shouldn't strictly enforce."""
    path_parts = Path(filepath).parts
    return any(ex_dir in path_parts for ex_dir in EXCLUDED_DIRS)


def check_readme(filepath: str) -> bool:
    """Check if the parent directory has a README.md.

    Args:
        filepath: Path to the file being checked.

    Returns:
        bool: True if a README.md exists in the parent directory.
    """
    path = Path(filepath)

    # Don't require README for root directory files
    if len(path.parts) <= 1:
        return True

    readme_path = path.parent / "README.md"
    return readme_path.exists()


def check_sql_header(filepath: str) -> tuple[bool, str]:
    """Check if the SQL file has the required header and verifies basic diagram accuracy.

    Args:
        filepath: Path to the SQL file.

    Returns:
        tuple[bool, str]: (passed, error_message).
    """
    try:
        content = Path(filepath).read_text(encoding="utf-8")
    except OSError as e:
        return False, f"Could not read file: {e}"

    reqs = SQL_REQUIRED_FIELDS
    missing = [req for req in reqs if req.lower() not in content.lower()]
    if missing:
        return False, (
            f"Missing required SQL header fields: {', '.join(missing)}\n"
            "   FIX: Add a block comment at the very top of the file with ALL of these fields:\n"
            "   /*\n"
            "     Object Name: <procedure/function name>\n"
            "     Goal: <what it does in one sentence>\n"
            "     Business Context: <why this exists>\n"
            "     Architecture: <Mermaid diagram OR 'Not needed.' if no Temp Tables/CTEs/CALLs>\n"
            "   */\n"
            "   📖 Rules: .agents/rules/documentation.md #4 (Mandatory Architectural Diagrams)\n"
            "   🔧 Skill: .agents/skills/doc-enforcer/SKILL.md"
        )

    header_text = extract_header_text(content)

    # Validate architecture field
    passed, err = _validate_architecture(content, header_text)
    if not passed:
        return False, err

    # Enforce DECISION HISTORY at the bottom for ALL SQL files
    arch_line = [l for l in header_text.split('\n') if l.lower().strip().startswith("architecture:")]
    if arch_line:
        passed, err = verify_decision_history(filepath, content, file_type="sql")
        if not passed:
            return False, err

    return True, ""


def check_py_header(filepath: str) -> tuple[bool, str]:
    """Check if the Python file has the required header.

    Args:
        filepath: Path to the Python file.

    Returns:
        tuple[bool, str]: (passed, error_message).
    """
    if Path(filepath).name == "__init__.py":
        return True, ""

    try:
        content = Path(filepath).read_text(encoding="utf-8")
    except OSError as e:
        return False, f"Could not read file: {e}"

    reqs = PYTHON_REQUIRED_FIELDS
    missing = [req for req in reqs if req not in content]
    if missing:
        return False, (
            f"Missing required Python docstring fields: {', '.join(missing)}\n"
            '   FIX: Add a module-level docstring at the top of the file with ALL of these fields:\n'
            '   """\n'
            '   MODULE: <module name>\n'
            '   GOAL: <what it does in one sentence>\n'
            '   BUSINESS CONTEXT: <why this exists>\n'
            "   ARCHITECTURE: <'Not needed.' if simple, or a Mermaid diagram if it orchestrates 3+ systems>\n"
            '   """\n'
            '   📖 Rules: .agents/rules/documentation.md #4 (Mandatory Architectural Diagrams)\n'
            '   🔧 Skill: .agents/skills/doc-enforcer/SKILL.md'
        )

    # Enforce DECISION HISTORY for all Python files
    passed, err = verify_decision_history(filepath, content, file_type="python")
    if not passed:
        return False, err

    return True, ""


def check_yaml_adr(filepath: str) -> tuple[bool, str]:
    """Check if the YAML file has the required ADR/Decision History at the bottom.

    Args:
        filepath: Path to the YAML file.

    Returns:
        tuple[bool, str]: (passed, error_message).
    """
    try:
        content = Path(filepath).read_text(encoding="utf-8")
    except OSError as e:
        return False, f"Could not read file: {e}"

    passed, err = verify_decision_history(filepath, content, file_type="yaml")
    if not passed:
        return False, err

    return True, ""


def process_staged_file(filepath: str, status: str, path: Path) -> list[str]:
    """Run all documentation checks on a single staged file.

    Args:
        filepath: Path to the file.
        status: Git status code (e.g. 'A', 'M', 'D').
        path: Resolved Path object for the file.

    Returns:
        list[str]: Error messages for failed checks.
    """
    # 1. README Check (Apply to all staged files in subdirectories)
    failed_checks = []
    if not check_readme(filepath):
        parent_dir = path.parent
        failed_checks.append(
            f"❌ DIRECTORY README MISSING: '{parent_dir}/README.md' does not exist.\n"
            f"   You modified/added '{path.name}' — every directory with code MUST have a README.md.\n"
            f"   FIX: Create '{parent_dir}/README.md' with sections: Purpose, Key Files, Critical Context, Maintenance.\n"
            f"   📖 Rules: .agents/rules/documentation.md #2 (Directory README Requirements)\n"
            f"   🔧 Skill: .agents/skills/doc-enforcer/SKILL.md"
        )

    # 2. Header Check (Apply to added and modified files - Boy Scout Rule)
    is_applicable = status.startswith("A") or status.startswith("M")
    if is_applicable:
        if path.suffix.lower() == ".sql":
            passed, error_msg = check_sql_header(filepath)
            if not passed:
                failed_checks.append(
                    f"❌ SQL DOCUMENTATION VIOLATION: '{filepath}'\n"
                    f"   {error_msg}"
                )
        elif path.suffix.lower() == ".py":
            passed, error_msg = check_py_header(filepath)
            if not passed:
                failed_checks.append(
                    f"❌ PYTHON DOCUMENTATION VIOLATION: '{filepath}'\n"
                    f"   {error_msg}"
                )
        elif path.suffix.lower() in (".yaml", ".yml"):
            passed, error_msg = check_yaml_adr(filepath)
            if not passed:
                failed_checks.append(
                    f"❌ YAML DOCUMENTATION VIOLATION: '{filepath}'\n"
                    f"   {error_msg}"
                )
    return failed_checks


def configure_stdout() -> None:
    """Ensure header output works on Windows with UTF-8."""
    if sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass


def get_files_to_check(target_file: str | None) -> dict[str, str]:
    """Determine which files to check based on arguments.

    Args:
        target_file: Specific file path, or None for staged files.

    Returns:
        dict[str, str]: Mapping of filepath to git status.
    """
    if target_file:
        try:
            filepath = Path(target_file).resolve().relative_to(project_root).as_posix()
        except ValueError:
            filepath = Path(target_file).as_posix()
        return {filepath: "M"}
    return get_staged_files()


def should_check_file(filepath: str, status: str, path: Path) -> bool:
    """Determine whether to apply documentation checks to a given file.

    Args:
        filepath: Path to the file.
        status: Git status code.
        path: Resolved Path object for the file.

    Returns:
        bool: True if the file should be checked.
    """
    if path.suffix.lower() not in (".py", ".sql", ".yaml", ".yml"):
        return False

    if is_in_excluded_dir(filepath):
        return False

    if status.startswith("D"):
        return False

    # Root files are handled by check_root_files.py
    if len(path.parts) == 1:
        if path.name not in ALLOWED_ROOT_FILES and path.suffix not in ALLOWED_EXTENSIONS:
            return False

    return True


def print_results(failed_checks: list[str], passed_files_count: int) -> int:
    """Print results of documentation checks and return exit code.

    Args:
        failed_checks: List of error messages from failed checks.
        passed_files_count: Number of files that passed all checks.

    Returns:
        int: Exit code (0 = pass, 1 = violations found).
    """
    if failed_checks:
        print("\n📚 Documentation Check Failed\n")
        for fail_msg in failed_checks:
            print(fail_msg)
            print()
        print("   AI AGENT ACTION REQUIRED: You must fix all documentation violations.")
        print("   Use the doc-enforcer skill to help resolve these issues.")
        print("   DO NOT ask the user to bypass this rule.\n")
        return 1

    if passed_files_count > 0:
        print(f"✅ PASSED: {passed_files_count} files passed documentation checks")

    return 0


def main() -> int:
    """Entry point for the documentation pre-commit hook.

    Returns:
        int: Exit code (0 success, 1 violations found).
    """
    parser = argparse.ArgumentParser(description="Check documentation requirements.")
    parser.add_argument("--file", help="Specific file to check (bypasses git staged files).")
    parser.add_argument(
        "--report-legacy",
        action="store_true",
        help=(
            "Advisory: scan all tracked .py and .sql files for untagged DECISION HISTORY "
            "entries (legacy entries without the (#EPIC-Name/NN) tail-tag). "
            "Prints a count per file and exits 0 — never blocks a commit."
        ),
    )
    args = parser.parse_args()

    configure_stdout()

    if args.report_legacy:
        untagged = report_legacy_untagged()
        if untagged:
            total = sum(untagged.values())
            print(f"\n📊 Legacy untagged DECISION HISTORY entries: {total} across {len(untagged)} files\n")
            for path, count in sorted(untagged.items()):
                print(f"  {count:3d}  {path}")
            print(
                "\nThese are legacy entries written before EPIC-DocTraceability. "
                "They are NOT required to be updated. This report is advisory only."
            )
        else:
            print("✅ No legacy untagged DECISION HISTORY entries found.")
        return 0

    staged_files = get_files_to_check(args.file)

    if not staged_files:
        return 0

    failed_checks = []
    passed_files_count = 0

    for filepath, status in staged_files.items():
        path = Path(filepath)
        if not should_check_file(filepath, status, path):
            continue

        file_fails = process_staged_file(filepath, status, path)
        if file_fails:
            failed_checks.extend(file_fails)
        else:
            passed_files_count += 1

        # Validate tail-tags on newly-added DECISION HISTORY entries (fail-open)
        # Only run when processing staged files (not when --file is used for simple checks)
        if not args.file and path.suffix in (".py", ".sql"):
            tail_errors = validate_tail_tags_in_diff(filepath)
            if tail_errors:
                failed_checks.extend(tail_errors)

    return print_results(failed_checks, passed_files_count)


if __name__ == "__main__":
    sys.exit(main())

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-04-30 19:12 [AI/Antigravity]: Added Google-style docstrings to all
  functions for self-compliance with check_docstrings.py enforcement.
- 2026-04-29 10:00: Initial implementation with MODULE/GOAL/BUSINESS CONTEXT
  header validation and DECISION HISTORY enforcement.
- 2026-05-01 14:43 [AI/Hendrik]: Added PL/Python complexity detection to
  _detect_complex_constructs: multiple plpy.execute() calls (≥2) and
  pandas/numpy imports now trigger architecture diagram requirements. Previously
  only SQL-level constructs (temp tables, CTEs, CALL, LATERAL) were detected,
  letting PL/Python data pipeline functions slip through with 'Not needed.'
- 2026-05-01 11:40 [AI]: Added YAML Decision History validation enforcement.
- 2026-05-01 20:30 [AI]: Updated failure message to mandate agent-led refactoring
  for documentation violations. Extracted all validation helpers (Mermaid diagram
  verification, DECISION HISTORY enforcement, architecture validation, complex
  construct detection) to doc_validators.py to stay under 400-line limit.
- 2026-05-18 12:45 [python-coder]: Wired --report-legacy flag (advisory legacy entry count) and validate_tail_tags_in_diff call into main() for EPIC-DocTraceability ADR-033. (#EPIC-DocTraceability/03) (ADR-033)
- 2026-06-03 [python-coder]: Added encoding="utf-8" to subprocess.run() in get_staged_files() to fix UnicodeDecodeError on Windows when git output contains non-cp1252 bytes. Refactored check_sql_header, check_py_header, check_yaml_adr to use OSError instead of bare Exception catch (BLE001/TRY300 compliance). (#EPIC-TemplateDocViolations/05)
====================================================================
"""
