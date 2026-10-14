"""
MODULE: unit_tests/commit_guardian/_ge_127g_1_fixture.py
GOAL: Shared fixture for the GE-127g-1 / GE-127g-1-i tests. Builds a real
    throwaway git repo, commits a baseline, stages a "regeneration", and runs
    the REAL check_doc_length.py script (source copy or deployed copy) as a
    subprocess. No figure from the AC criteria is pinned: every length is
    derived from the shipped limit (``doc_length.max_lines``) read at test
    time, and every assertion is made against the fixture's own constructed set.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARDIAN_DIR = REPO_ROOT / "templates" / "scripts" / "commit_guardian"
CONFIG_NAME = "commit_guardian.json"
CARDS_DIR = "docs/agents/cards/"
PYTHON = sys.executable
TIMEOUT = 60

CLEAN_EXIT = 0
REFUSED_EXIT = 1


def shipped_limit() -> int:
    config = json.loads((GUARDIAN_DIR / CONFIG_NAME).read_text(encoding="utf-8"))
    return int(config["doc_length"]["max_lines"])


def git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=TIMEOUT, check=True
    )


def init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    git(["init", "-q", "-b", "main"], root)
    git(["config", "user.email", "ge127g1@example.com"], root)
    git(["config", "user.name", "GE-127g-1 fixture"], root)


def doc_text(body_lines: int, tag: str) -> str:
    """A doc whose measured length (frontmatter stripped) is exactly body_lines + 1."""
    frontmatter = "---\ntitle: fixture\ntype: reference\n---\n"
    return frontmatter + "\n".join(f"{tag} line {i}" for i in range(body_lines)) + "\n"


def write_doc(root: Path, rel: str, body_lines: int) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc_text(body_lines, Path(rel).stem), encoding="utf-8")


def commit_baseline(root: Path) -> None:
    git(["add", "-A"], root)
    git(["commit", "-q", "--no-verify", "-m", "baseline"], root)


def stage_all(root: Path) -> None:
    git(["add", "-A"], root)


def run_gate(root: Path, guardian_dir: Path) -> subprocess.CompletedProcess:
    """Run the real check_doc_length.py script from *guardian_dir* against root's index."""
    return subprocess.run(
        [PYTHON, str(guardian_dir / "check_doc_length.py")],
        cwd=str(root), capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT,
    )


def copy_guardian(dest: Path) -> Path:
    """A private copy of the SOURCE commit_guardian dir whose declaration the test may edit."""
    shutil.copytree(GUARDIAN_DIR, dest, ignore=shutil.ignore_patterns("__pycache__"))
    return dest


def set_aside_paths(guardian_dir: Path) -> list[str]:
    """The declared set-aside paths, read from the declaration next to the gate."""
    config = json.loads((guardian_dir / CONFIG_NAME).read_text(encoding="utf-8"))
    entries = config["doc_length"].get("set_aside_locations", [])
    return [entry["path"] for entry in entries]


def named_docs(output: str, prefix: str = "docs/") -> set[str]:
    """Every docs/**.md path a gate run's output names."""
    return set(re.findall(re.escape(prefix) + r"[\w./\-]*\.md", output))


def output_of(result: subprocess.CompletedProcess) -> str:
    return result.stdout + result.stderr
