"""
MODULE: unit_tests/commit_guardian/_bp_1100g_4_ii_fixture.py
SHARED FIXTURE for BP-1100g-4-ii's test files (private sibling module; importers
    ``sys.path.insert(0, str(Path(__file__).resolve().parent))`` before
    ``import _bp_1100g_4_ii_fixture``, the package-import pattern used by
    ``_ge_127e_1_fixture.py``).

Holds the deployed-hook paths, the real-serializer Test Requirements block, the
ticket / temp-git-project builders and the subprocess runner shared by
test_bp_1100g_4_ii.py and test_bp_1100g_4_ii_parked.py. Split out so neither
file crosses the 400-counted-line gate (GE-127a-1).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEPLOYED_RUN_HOOK = (
    _REPO_ROOT / ".leafcutter" / "scripts" / "commit_guardian" / "run_hook.py"
)
_DEPLOYED_HOOK = (
    _REPO_ROOT / ".leafcutter" / "scripts" / "commit_guardian" / "check_proof_promise_claim.py"
)

_SUBPROCESS_TIMEOUT_SECONDS = 60

_SHARED_AC_ID = "ZZ-BP1100G4II-LIFECYCLE"
_SHARED_ANGLE = "reachability"
_SHARED_BEHAVIOUR = "the promise-claim lifecycle demo behaviour is reachable end to end"


def _build_test_requirements_block() -> str:
    """Build the ``## Test Requirements`` fenced YAML body via the REAL serializer.

    Mirrors exactly what ``generate_ticket_from_ac.py``'s
    ``_build_test_requirements_section`` emits — ``yaml.dump`` of a
    ``{"tests": [...]}`` dict — per the fixture-authenticity convention
    (never a hand-typed YAML string). Computed ONCE at module load so every
    ticket fixture built below shares the byte-identical block.

    Returns:
        The fenced block's inner YAML text (no ``---``/heading wrapper).
    """
    descriptors = [
        {
            "name": f"test_zz_lifecycle_{_SHARED_ANGLE}",
            "file": "unit_tests/zz/test_lifecycle.py",
            "covers": [_SHARED_AC_ID],
            "asserts": _SHARED_BEHAVIOUR,
            "framework": "unittest",
            "type": "integration",
            "angle": _SHARED_ANGLE,
        }
    ]
    return yaml.dump(
        {"tests": descriptors},
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).rstrip()


_TEST_REQUIREMENTS_BLOCK = _build_test_requirements_block()


def _build_ticket_fixture(state_line: str | None) -> str:
    """Build a real ticket fixture, varying ONLY the frontmatter state line.

    Every other line — the ``---`` delimiters, the title, the
    ``## Test Requirements`` heading, and the fenced YAML block itself — is
    byte-identical across every call. This is the mutation-proof property
    REQUIRED TEST PROPERTIES #4 demands: nothing but *state_line* can explain
    a difference in the check's outcome between two fixtures built from this
    same function.

    Args:
        state_line: The raw frontmatter line encoding the ticket's declared
            state (e.g. ``"status: todo"``, ``"status: {unterminated"`` for
            an unparseable value). ``None`` omits the status line entirely
            — the "no status: key at all" shape.

    Returns:
        The full ticket markdown text.
    """
    lines = ["---", "title: zz-bp-1100g-4-ii fixture ticket"]
    if state_line is not None:
        lines.append(state_line)
    lines.append("---")
    lines.append("")
    lines.append("## Test Requirements")
    lines.append("")
    lines.append("```yaml")
    lines.append(_TEST_REQUIREMENTS_BLOCK)
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def _init_temp_git_project(project_root: Path) -> None:
    """``git init`` a fresh, disposable project root.

    Required so the deployed hook's ``find_project_root()`` (which prefers
    ``git rev-parse --show-toplevel``) resolves to THIS isolated tree rather
    than to the real repository's own root — meaning the scanned claim tree
    is exactly, and only, whatever this test wrote into it.

    Args:
        project_root: Directory to initialise as a git repository.
    """
    subprocess.run(
        ["git", "init", "-q"],
        cwd=str(project_root),
        check=True,
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _write_claim_file(directory: Path, filename: str, ac_id: str, angle: str) -> Path:
    """Write a real on-disk test file carrying a ``# covers:`` + ``# angle:`` claim.

    Tags sit directly above the ``def`` line — one of the three positions the
    shared ``collect_test_tag_records`` scanner recognises — so this is
    scanned exactly as a real contributor's test would be.

    Args:
        directory: Directory to write the file into.
        filename: File name to write.
        ac_id: The ``ac_id`` to claim.
        angle: The ``angle`` to claim.

    Returns:
        Path to the written file.
    """
    path = directory / filename
    path.write_text(
        f"# covers: {ac_id}\n"
        f"# angle: {angle}\n"
        "def test_zz_lifecycle_claim():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    return path


def _run_check(project_root: Path, ticket_path: Path) -> subprocess.CompletedProcess:
    """Invoke the DEPLOYED hook via ``run_hook.py`` exactly as pre-commit would.

    Args:
        project_root: Working directory for the subprocess — a fresh,
            git-initialised, disposable project root.
        ticket_path: Path to the staged ticket markdown file, passed as the
            hook's ``argv``.

    Returns:
        The completed subprocess result (stdout/stderr/returncode).
    """
    return subprocess.run(
        [sys.executable, str(_DEPLOYED_RUN_HOOK), str(_DEPLOYED_HOOK), str(ticket_path)],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )
