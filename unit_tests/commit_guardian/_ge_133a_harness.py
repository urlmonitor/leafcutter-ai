"""
MODULE: unit_tests/commit_guardian/_ge_133a_harness.py
COVERS: GE-133a-1, GE-133a-2 (shared harness -- carries no tests of its own)

GOAL: Drive the folder-density check through a REAL ``git commit`` in a scratch
    repository. The DEPLOYED commit_guardian directory is taken from the shared
    reference layout (read-only) and copied OUTSIDE the scratch repo, so the
    declaration under test is varied only in the scratch copy of
    commit_guardian.json. A plain git pre-commit hook runs the deployed
    check_folder_density.py; the verdict is the commit's own exit status and
    output.

REACHABILITY ENTRY POINT (resolved): ``git commit`` -> pre-commit hook ->
    deployed check_folder_density.py.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

GIT_TIMEOUT = 60
STORE = "docs/acceptance-criteria"
STORE_GROUND = "GROUND-MARKER-STORE records read by tools and navigated by nobody"
STORE_ENTRY = {"path": "docs/acceptance-criteria/", "ground": STORE_GROUND}
FAMILY = f"{STORE}/build-orchestration/BO-3800-refusal-summons-specialist"


def git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=GIT_TIMEOUT, check=check
    )


def deployed_guardian(layout: Path) -> Path:
    for rel in ("scripts/commit_guardian", ".leafcutter/scripts/commit_guardian"):
        if (layout / rel).is_dir():
            return layout / rel
    msg = f"no deployed commit_guardian dir under {layout}"
    raise AssertionError(msg)


def make_files(root: Path, folder: str, count: int, tag: str = "f", start: int = 0) -> None:
    d = root / folder
    d.mkdir(parents=True, exist_ok=True)
    for i in range(start, start + count):
        (d / f"{tag}_{i:03d}.yaml").write_text(f"id: {tag}-{i}\n", encoding="utf-8")


class Scratch:
    """A scratch repo whose pre-commit hook runs the deployed density check."""

    def __init__(self, layout: Path, tmp: Path, declaration: object = "unset") -> None:
        self.repo = tmp / "repo"
        self.guardian = tmp / "guardian"
        self.repo.mkdir()
        shutil.copytree(deployed_guardian(layout), self.guardian)
        self.config = self.guardian / "commit_guardian.json"
        cfg = json.loads(self.config.read_text(encoding="utf-8"))
        section = cfg.setdefault("folder_density", {})
        section.pop("set_aside_locations", None)
        if declaration == "unset":
            declaration = [STORE_ENTRY]
        if declaration != "absent":
            section["set_aside_locations"] = declaration
        self.config.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        git(["init", "-q"], self.repo)
        git(["config", "user.email", "t@example.com"], self.repo)
        git(["config", "user.name", "GE-133a fixture"], self.repo)

    def baseline(self) -> None:
        """Commit the parent revision (hook not yet installed), then install it."""
        git(["add", "-A"], self.repo)
        git(["commit", "-q", "-m", "parent revision"], self.repo)
        hook = self.repo / ".git" / "hooks" / "pre-commit"
        hook.write_text(
            f"#!/bin/sh\nexec {sys.executable} {self.guardian / 'check_folder_density.py'}\n", encoding="utf-8"
        )
        hook.chmod(0o755)

    def commit(self) -> tuple[int, str]:
        git(["add", "-A"], self.repo)
        proc = git(["commit", "-q", "-m", "ordinary commit"], self.repo, check=False)
        return proc.returncode, proc.stdout + proc.stderr


def too_dense(output: str) -> dict[str, int]:
    """Map folder -> count for every 'FOLDER TOO DENSE' block in *output*."""
    found: dict[str, int] = {}
    lines = output.splitlines()
    for i, line in enumerate(lines):
        m = re.search(r"FOLDER TOO DENSE:\s*(\S+?)/?\s*$", line)
        if m:
            n = re.search(r"(\d+)", lines[i + 1]) if i + 1 < len(lines) else None
            found[m.group(1).rstrip("/")] = int(n.group(1)) if n else -1
    return found


def figure(output: str, word_re: str) -> set[int]:
    """Numbers stated next to *word_re* (e.g. 'judged', 'set aside') in the output."""
    nums: set[int] = set()
    for m in re.finditer(rf"(\d+)\s+(?:folders?\s+)?(?:were\s+|was\s+)?{word_re}", output, re.IGNORECASE):
        nums.add(int(m.group(1)))
    for m in re.finditer(rf"{word_re}[^\n\d]{{0,12}}(\d+)", output, re.IGNORECASE):
        nums.add(int(m.group(1)))
    return nums


def leaks_into_judged_lists(output: str, folder: str) -> list[str]:
    """Lines that report *folder* as within-limit or already-over (not as set aside)."""
    bad = []
    for line in output.splitlines():
        if folder not in line:
            continue
        low = line.lower()
        if "pre-existing" in low:
            bad.append(line)
        elif re.search(r"\(\d+ files?\)", line) and "set aside" not in low and "set-aside" not in low and "GROUND-MARKER" not in line:
            bad.append(line)
    return bad
