"""
MODULE: unit_tests/build_guards/_acs200g_fixture.py
GOAL: Fixture-repository plumbing for the ACS-200g-3 reachability check.
BUSINESS CONTEXT: The reachability check used to point the deployed
    check_ac_schema.py at the real repository, so one staged record made the
    hook index ~5,270 records (22 s cold, 30 s timeout). ACS-200g-3 re-scopes
    it to a small git-initialised fixture repository in a temp directory.
ARCHITECTURE: The fixture holds a copy of the DEPLOYED
    .leafcutter/scripts/commit_guardian/ and .leafcutter/scripts/ac_store/
    directories, the real config/ac_store_schema.json, three valid draft
    records and the malformed ZZTEST-999 record, all written by the real
    serializer (yaml.safe_dump) via unit_tests/ac_store/_declared_files_fixtures.
    The hook runs as a subprocess with HOOK_ROOT and cwd both = fixture.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from unit_tests.ac_store._declared_files_fixtures import (
    copy_real_schema_into,
    init_git_index,
    init_repo_root,
    write_ac_yaml,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEPLOYED_DIR = REPO_ROOT / ".leafcutter" / "scripts"
DEPLOYED_SCHEMA_HOOK = DEPLOYED_DIR / "commit_guardian" / "check_ac_schema.py"
MALFORMED_ID = "ZZTEST-999"
VALID_IDS = ("ZZTEST-101", "ZZTEST-102", "ZZTEST-103")
FIXTURE_IDS = frozenset((*VALID_IDS, MALFORMED_ID))
HOOK_TIMEOUT_SECONDS = 30
COLD_RUN_BOUND_SECONDS = 10.0
CACHE_NAME = "ac_store_index_cache.json"


@dataclass
class HookRun:
    """One timed hook subprocess run."""

    label: str
    returncode: int
    output: str
    seconds: float


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(  # noqa: S603
        ["git", *args], cwd=str(cwd), check=True, capture_output=True
    ).stdout.decode("utf-8", errors="replace")


def real_git_dir() -> Path:
    return Path(_git(["rev-parse", "--absolute-git-dir"], REPO_ROOT).strip())


def cache_snapshot(git_dir: Path) -> tuple[bool, int | None, int | None]:
    """(exists, st_mtime_ns, st_size) of the index cache in git_dir."""
    path = git_dir / CACHE_NAME
    if not path.exists():
        return (False, None, None)
    st = path.stat()
    return (True, st.st_mtime_ns, st.st_size)


def tree_snapshot() -> tuple[str, str]:
    """(porcelain status, sha256 of binary diff vs HEAD) of the real tree."""
    status = _git(["status", "--porcelain=v1", "--untracked-files=all"], REPO_ROOT)
    diff = subprocess.run(  # noqa: S603
        ["git", "diff", "HEAD", "--binary"], cwd=str(REPO_ROOT), check=True, capture_output=True
    ).stdout
    return (status, hashlib.sha256(diff).hexdigest())


def _force_remove(func: Any, path: str, _exc: Any) -> None:
    os.chmod(path, stat.S_IWRITE)
    func(path)


def remove_tree(path: Path) -> None:
    """Windows-safe removal (read-only files under .git)."""
    shutil.rmtree(path, onerror=_force_remove)


def build_fixture(root: Path) -> dict[str, Path]:
    """Build the fixture repository under root; return the staged paths by id."""
    scripts = root / ".leafcutter" / "scripts"
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(DEPLOYED_DIR / "commit_guardian", scripts / "commit_guardian", ignore=ignore)
    shutil.copytree(DEPLOYED_DIR / "ac_store", scripts / "ac_store", ignore=ignore)
    copy_real_schema_into(root)
    store = init_repo_root(root)
    paths = {ac_id: write_ac_yaml(store, ac_id) for ac_id in VALID_IDS}
    bad_dir = store / "ac-driven-dev"
    bad = bad_dir / f"{MALFORMED_ID}.yaml"
    bad.write_text(yaml.safe_dump({"id": MALFORMED_ID}), encoding="utf-8")
    paths[MALFORMED_ID] = bad
    init_git_index(root)
    return paths


def run_hook(root: Path, staged: Path, label: str) -> HookRun:
    """Run the COPIED deployed hook with HOOK_ROOT = cwd = root, timed."""
    env = dict(os.environ)
    env["HOOK_ROOT"] = str(root)
    env["HOOK_TEST_STAGED_FILES"] = str(staged)
    for name in ("HOOK_TEST_FILES_MODIFIED", "HOOK_NO_GIT"):
        env.pop(name, None)
    hook = root / ".leafcutter" / "scripts" / "commit_guardian" / "check_ac_schema.py"
    start = time.monotonic()
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(hook)],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        timeout=HOOK_TIMEOUT_SECONDS,
    )
    return HookRun(label, proc.returncode, proc.stdout + proc.stderr, time.monotonic() - start)
