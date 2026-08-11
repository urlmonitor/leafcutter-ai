"""
MODULE: test_fastlane_template_deploy_parity.py
GOAL: Regression test asserting that the deploy-source template for
    setup_ticket_worktree.py always contains the create-fastlane-worktree
    subcommand so consumers never silently receive a build without it.
BUSINESS CONTEXT: The fast-lane subcommand was present in the generated
    scripts/ output but absent from the template that build.py deploys to
    consumers, silently breaking /fast-lane-build for all consumer installs.
    This test prevents that drift from recurring undetected.
ARCHITECTURE: Pure string-presence check against the template file resolved
    from this test file's own path, so it works in any checkout layout
    without hard-coded absolute paths.
"""
# covers: BO-2400f-3

from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _resolve_template_path() -> Path:
    """Resolve the template file path relative to this test's own location.

    The template lives at ``<repo_root>/templates/scripts/setup_ticket_worktree.py``.
    This test lives at ``<repo_root>/unit_tests/build_orchestration/<this file>``.
    Walking up two directories from this file's parent yields the repo root.

    Returns:
        Absolute Path to the deploy-source template file.
    """
    this_file = Path(__file__).resolve()
    # unit_tests/build_orchestration/ -> unit_tests/ -> repo_root
    repo_root = this_file.parent.parent.parent
    return repo_root / "templates" / "scripts" / "setup_ticket_worktree.py"


def _read_template() -> str:
    """Read the deploy-source template and return its contents as a string.

    Returns:
        Full text of the template file.

    Raises:
        pytest.fail: If the template file cannot be opened (surfaces the path
            and OS error so the failure is immediately actionable).
    """
    template_path = _resolve_template_path()
    try:
        return template_path.read_text(encoding="utf-8")
    except OSError as exc:
        pytest.fail(
            f"Cannot read deploy-source template at {template_path}: {exc}. "
            "Verify the repo layout and that the template file has not been moved."
        )


def test_template_has_fastlane_subcommand_string() -> None:
    """Template contains the create-fastlane-worktree subcommand string.

    The subcommand name must appear in the template so that when build.py
    deploys the template to a consumer project, the deployed script registers
    the subcommand and /fast-lane-build can invoke it successfully.
    """
    content = _read_template()
    assert "create-fastlane-worktree" in content, (
        "The deploy-source template is missing the 'create-fastlane-worktree' "
        "subcommand string. Port the fast-lane subparser block from "
        "scripts/setup_ticket_worktree.py into "
        "templates/scripts/setup_ticket_worktree.py."
    )


def test_template_has_cmd_create_fastlane_worktree_definition() -> None:
    """Template contains the cmd_create_fastlane_worktree function definition.

    The handler function must be present in the template so consumers receive
    a working implementation, not just the subparser registration.
    """
    content = _read_template()
    assert "def cmd_create_fastlane_worktree" in content, (
        "The deploy-source template is missing 'def cmd_create_fastlane_worktree'. "
        "Port cmd_create_fastlane_worktree from "
        "scripts/setup_ticket_worktree.py into "
        "templates/scripts/setup_ticket_worktree.py."
    )


def test_template_does_not_contain_probe_failure() -> None:
    """Template must not contain probe_failure (a scripts/-only gate).

    probe_failure belongs to the generated scripts/ output which includes the
    verify_precommit_active.py gate. The template intentionally uses a simpler
    _bootstrap that does not depend on that gate script, which may not be
    deployed in all consumer layouts.
    """
    content = _read_template()
    assert "probe_failure" not in content, (
        "The deploy-source template unexpectedly contains 'probe_failure'. "
        "This is a scripts/-only gate that must not appear in the template; "
        "remove it to preserve the template's simpler _bootstrap contract."
    )
