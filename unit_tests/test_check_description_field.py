"""
MODULE: test_check_description_field
GOAL: Unit tests for check_description_field.py pre-commit hook.
BUSINESS CONTEXT: Verifies the description-field enforcement hook correctly
    accepts staged doc files that have a non-empty description: frontmatter
    field, rejects those that are missing it, and silently ignores ticket
    files and skill/template files that are out of scope.
ARCHITECTURE: Tests invoke the hook via subprocess (CLI contract) so exit
    codes, output format, and scope-exclusion logic are all exercised end-to-end.
    Temporary directories are used to isolate each test's filesystem state.
    The hook file is expected at scripts/commit_guardian/check_description_field.py
    relative to the project root.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

HOOK_SCRIPT = (
    Path(__file__).parent.parent
    / "scripts"
    / "commit_guardian"
    / "check_description_field.py"
)


def _run_hook(*file_paths: Path) -> subprocess.CompletedProcess:
    """Run check_description_field.py with the given file paths as positional args.

    Args:
        *file_paths: Absolute Path objects to pass as CLI arguments.

    Returns:
        CompletedProcess with returncode, stdout, and stderr captured.
    """
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)] + [str(p) for p in file_paths],
        capture_output=True,
        text=True,
    )


def test_exits_0_when_all_staged_docs_have_description() -> None:
    """Hook exits 0 when every staged docs/ file has a non-empty description: field."""
    with tempfile.TemporaryDirectory() as tmp:
        docs_dir = Path(tmp) / "docs"
        docs_dir.mkdir(parents=True)
        doc_file = docs_dir / "example.md"
        doc_file.write_text(
            textwrap.dedent("""\
                ---
                title: Example Doc
                description: A short description of this example document.
                ---

                # Example Doc
            """),
            encoding="utf-8",
        )

        result = _run_hook(doc_file)
        assert result.returncode == 0, (
            f"Expected exit 0 for doc with description, got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


def test_exits_1_when_staged_doc_missing_description() -> None:
    """Hook exits 1 and prints a violation when a docs/ file is missing description:."""
    with tempfile.TemporaryDirectory() as tmp:
        docs_dir = Path(tmp) / "docs"
        docs_dir.mkdir(parents=True)
        doc_file = docs_dir / "missing_desc.md"
        doc_file.write_text(
            textwrap.dedent("""\
                ---
                title: Missing Description
                status: active
                ---

                # Missing Description
            """),
            encoding="utf-8",
        )

        result = _run_hook(doc_file)
        assert result.returncode == 1, (
            f"Expected exit 1 for doc missing description, got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "FAIL:" in result.stdout or "FAIL:" in result.stderr, (
            "Expected a FAIL: violation line in output.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "missing description field" in (result.stdout + result.stderr), (
            "Expected 'missing description field' in violation output.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


def test_ignores_ticket_files() -> None:
    """Hook exits 0 and does NOT flag ticket files (tickets/ tree is out of scope)."""
    with tempfile.TemporaryDirectory() as tmp:
        tickets_dir = Path(tmp) / "tickets" / "00_inbox"
        tickets_dir.mkdir(parents=True)
        ticket_file = tickets_dir / "01_some_ticket.md"
        ticket_file.write_text(
            textwrap.dedent("""\
                ---
                title: Some Ticket
                status: todo
                ---

                # Some Ticket
            """),
            encoding="utf-8",
        )

        result = _run_hook(ticket_file)
        assert result.returncode == 0, (
            "Expected exit 0 for ticket file (out of scope), "
            f"got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


def test_ignores_skill_files() -> None:
    """Hook exits 0 and does NOT flag templates/skills/ SKILL.md files (out of scope)."""
    with tempfile.TemporaryDirectory() as tmp:
        skills_dir = Path(tmp) / "templates" / "skills" / "my-skill"
        skills_dir.mkdir(parents=True)
        skill_file = skills_dir / "SKILL.md"
        skill_file.write_text(
            textwrap.dedent("""\
                ---
                name: my-skill
                ---

                # my-skill

                This skill has no description: field.
            """),
            encoding="utf-8",
        )

        result = _run_hook(skill_file)
        assert result.returncode == 0, (
            "Expected exit 0 for skill file (out of scope), "
            f"got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
