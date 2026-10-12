"""
MODULE: test_retired_command_outputs_build
GOAL: Prove, through real ``build.py`` subprocesses, that upgrading an adopter
    across a slash-command rename leaves no stale copy of the old command
    behind -- on a plain rebuild and on a ``--clean`` rebuild -- and that the
    deployed ``check-output-drift`` hook is green afterwards with no manual
    deletion.
BUSINESS CONTEXT: TICKET-20260930-RetireRenamedCommandOutputs. Renaming the
    knowledge-hub template ``templates/workflows/leafcutter.md`` to
    ``leafcutter-help.md`` left the old ``leafcutter.md`` in
    ``.leafcutter/commands/``, ``.claude/commands/``,
    ``.leafcutter/gemini/workflows/`` and ``.gemini/workflows/`` of every
    existing install, and ``check-output-drift`` then refused every commit
    (``GAP .claude/commands/leafcutter.md``) until someone deleted it by hand.
ARCHITECTURE: A shared_layout_mutator (it renames a template in a PRIVATE
    package copy before building, so it can never use the shared reference
    layout). One module-scoped fixture builds the package AS IT SHIPPED BEFORE
    THE RENAME into a scratch adopter; each test copies that installed tree,
    restores the current template name in its own package copy, rebuilds, and
    inspects the real files plus the real deployed hook. The package copy comes
    from test_bp_100k_2._build_synthetic_full_package, loaded by file path under
    a private module name (the same discipline test_bp_900g_8.py uses).
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.shared_layout_mutator

_SYNTHETIC_PACKAGE_HELPER = Path(__file__).resolve().parent / "test_bp_100k_2.py"
_BUILD_TIMEOUT_SECONDS = 900
_HOOK_TIMEOUT_SECONDS = 120

_OLD_NAME = "leafcutter.md"
_NEW_NAME = "leafcutter-help.md"

# Every place one workflow template is installed: the consolidated output root
# and the canonical tool directory, for both active platforms (claude and
# antigravity), exactly as the scratch-adopter reproduction observed them.
_INSTALLED_LOCATIONS = (
    ".leafcutter/commands",
    ".claude/commands",
    ".leafcutter/gemini/workflows",
    ".gemini/workflows",
)


def _load_synthetic_package_builder():
    """Return test_bp_100k_2._build_synthetic_full_package, loaded privately.

    Loaded by file path under a name pytest never collects, so it cannot clash
    with pytest's own import of test_bp_100k_2.py.
    """
    spec = importlib.util.spec_from_file_location(
        "_retired_outputs_synthetic_package_helper", _SYNTHETIC_PACKAGE_HELPER
    )
    assert spec is not None and spec.loader is not None, (
        f"cannot load the synthetic-package helper from {_SYNTHETIC_PACKAGE_HELPER}"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._build_synthetic_full_package


def _run(args: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    """Run a Python subprocess with UTF-8 forced on (Windows cp1252 safety)."""
    return subprocess.run(
        [sys.executable, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env={**os.environ, "PYTHONUTF8": "1"},
    )


def _build(workspace: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    """Build the package copy at ``<workspace>/leafcutter-ai`` into ``workspace``."""
    pkg_root = workspace / "leafcutter-ai"
    return _run(
        [str(pkg_root / "scripts" / "build.py"), "--target-dir", str(workspace), *flags],
        cwd=pkg_root,
        timeout=_BUILD_TIMEOUT_SECONDS,
    )


def _rename_hub_template(workspace: Path, old: str, new: str) -> None:
    """Rename the hub workflow template inside this workspace's package copy."""
    workflows = workspace / "leafcutter-ai" / "templates" / "workflows"
    assert (workflows / old).is_file(), f"setup bug: {workflows / old} is missing"
    (workflows / old).rename(workflows / new)


def _combined(result: subprocess.CompletedProcess[str]) -> str:
    return f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"


@pytest.fixture(scope="module")
def pre_rename_install(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A scratch adopter installed from the package as it shipped before the rename.

    Returns:
        The workspace: the adopter root, holding its private package copy at
        ``leafcutter-ai/``.
    """
    workspace = tmp_path_factory.mktemp("pre_rename_install")
    _load_synthetic_package_builder()(workspace)
    _rename_hub_template(workspace, _NEW_NAME, _OLD_NAME)

    result = _build(workspace)
    assert result.returncode == 0, f"pre-rename build failed:\n{_combined(result)}"
    missing = [loc for loc in _INSTALLED_LOCATIONS if not (workspace / loc / _OLD_NAME).is_file()]
    assert not missing, (
        f"setup bug: the pre-rename install should hold {_OLD_NAME} in every "
        f"installed location, but it is missing from {missing}"
    )
    return workspace


def _upgrade(pre_rename: Path, tmp_path: Path, *flags: str):
    """Copy the pre-rename install, apply the rename, and rebuild it.

    Returns:
        ``(workspace, build_result)`` for the upgraded copy.
    """
    workspace = tmp_path / "adopter"
    shutil.copytree(pre_rename, workspace, symlinks=True)
    _rename_hub_template(workspace, _OLD_NAME, _NEW_NAME)
    return workspace, _build(workspace, *flags)


def _assert_upgrade_left_no_stale_hub(workspace: Path, result: subprocess.CompletedProcess[str]) -> None:
    """The shared verdict for a plain and a --clean upgrade."""
    assert result.returncode == 0, f"upgrade build failed:\n{_combined(result)}"

    leftovers = [f"{loc}/{_OLD_NAME}" for loc in _INSTALLED_LOCATIONS if (workspace / loc / _OLD_NAME).exists()]
    assert not leftovers, (
        "The package no longer ships the old hub command, and the previous install "
        "recorded these copies as its own unmodified output, yet the upgrade left "
        f"them in place: {leftovers}\n{_combined(result)}"
    )

    not_installed = [loc for loc in _INSTALLED_LOCATIONS if not (workspace / loc / _NEW_NAME).is_file()]
    assert not not_installed, f"the renamed command {_NEW_NAME} is missing from {not_installed}"

    assert f".claude/commands/{_OLD_NAME}" in result.stdout, (
        "The build must name each retired file it removes, so an adopter can see "
        f"what an upgrade deleted.\n{_combined(result)}"
    )

    drift = _run(
        [str(workspace / ".leafcutter" / "scripts" / "commit_guardian" / "check_output_drift.py")],
        cwd=workspace,
        timeout=_HOOK_TIMEOUT_SECONDS,
    )
    assert drift.returncode == 0 and _OLD_NAME not in drift.stdout, (
        "check-output-drift must pass on the upgraded install without any manual "
        f"deletion (exit {drift.returncode}).\n{_combined(drift)}"
    )


def test_plain_rebuild_after_a_command_rename_removes_every_stale_copy(
    pre_rename_install: Path, tmp_path: Path
) -> None:
    workspace, result = _upgrade(pre_rename_install, tmp_path)
    _assert_upgrade_left_no_stale_hub(workspace, result)


def test_clean_rebuild_after_a_command_rename_removes_every_stale_copy(
    pre_rename_install: Path, tmp_path: Path
) -> None:
    workspace, result = _upgrade(pre_rename_install, tmp_path, "--clean")
    _assert_upgrade_left_no_stale_hub(workspace, result)
