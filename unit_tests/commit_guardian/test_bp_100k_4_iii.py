"""Behavioral consumer-layout regression for BP-100k-4-iii."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "templates/scripts/commit_guardian/check_hook_trigger_reachability.py"


def _run(*args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args), cwd=cwd, env=env, capture_output=True, text=True,
        check=False, timeout=30,
    )


def _fixture_repo(tmp_path: Path, *, ignored_docs: bool = False) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert _run("git", "init", "-b", "main", cwd=repo).returncode == 0
    (repo / "project.txt").write_text("new consumer project\n", encoding="utf-8")
    assert _run("git", "add", "project.txt", cwd=repo).returncode == 0
    docs = repo / "docs" / "guide.md"
    docs.parent.mkdir()
    docs.write_text("A guide that can be staged later.\n", encoding="utf-8")
    if ignored_docs:
        (repo / ".gitignore").write_text("docs/\n", encoding="utf-8")
        assert _run("git", "add", ".gitignore", cwd=repo).returncode == 0
    return repo


def _check(repo: Path, hooks: list[dict]) -> subprocess.CompletedProcess[str]:
    registry = repo / "registry.json"
    registry.write_text(json.dumps({"hooks_manifest": {"hooks": hooks}}), encoding="utf-8")
    env = os.environ.copy()
    env["HOOK_TEST_CONFIG"] = str(registry)
    return _run(sys.executable, str(HOOK), cwd=repo, env=env)


def test_consumer_location_trigger_matching_untracked_stageable_file_does_not_block(tmp_path: Path) -> None:
    # covers: BP-100k-4-iii
    repo = _fixture_repo(tmp_path)
    result = _check(repo, [{"id": "docs-gate", "files": r"^docs/.*\.md$"}])
    assert result.returncode == 0, result.stderr
    assert "UNREACHABLE: docs-gate" not in result.stderr
    assert "unreachable=0" in result.stderr


def test_ignored_only_location_trigger_still_blocks(tmp_path: Path) -> None:
    # covers: BP-100k-4-iii
    repo = _fixture_repo(tmp_path, ignored_docs=True)
    result = _check(repo, [{"id": "docs-gate", "files": r"^docs/.*\.md$"}])
    assert result.returncode == 1
    assert "UNREACHABLE: docs-gate" in result.stderr


@pytest.mark.parametrize(
    "hook",
    [
        {"id": "bad-regex", "files": "["},
        {"id": "contradictory", "always_run": True, "files": r"^docs/.*\.md$"},
    ],
)
def test_consumer_still_blocks_invalid_hook_definitions(tmp_path: Path, hook: dict) -> None:
    # covers: BP-100k-4-iii
    repo = _fixture_repo(tmp_path)
    result = _check(repo, [hook])
    assert result.returncode == 1
    assert f"UNREACHABLE: {hook['id']}" in result.stderr


def test_built_consumer_with_real_registry_has_no_unreachable_hooks(tmp_path: Path) -> None:
    # covers: BP-100k-4-iii
    repo = _fixture_repo(tmp_path)
    build = _run(
        sys.executable, str(ROOT / "scripts/build.py"), "--target-dir", str(repo),
        cwd=repo,
    )
    assert build.returncode == 0, build.stdout[-2000:] + build.stderr[-2000:]
    deployed_hook = repo / ".leafcutter/scripts/commit_guardian/check_hook_trigger_reachability.py"
    result = _run(sys.executable, str(deployed_hook), cwd=repo)
    assert result.returncode == 0, result.stderr
    assert "unreachable=0" in result.stderr
