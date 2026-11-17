"""Tests for AC INF-500d-4-x: the per-machine log-root declaration is kept out of git.

The build must leave a ``config/.gitignore`` naming only ``knowledge_sink.json``, written
idempotently and preserving any other line. Behavioural: real ``git`` in a temp repository.
"""
# @ac-tag: INF-500d-4-x

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from build_phases_knowledge import build_knowledge_sink_declaration  # noqa: E402

_GIT_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True, env=_GIT_ENV, timeout=60, check=False)


def test_build_keeps_the_log_root_declaration_out_of_git(tmp_path):
    # covers: INF-500d-4-x
    # angle: criterion
    """AC INF-500d-4-x: the build leaves an ignore rule so knowledge_sink.json never reaches git."""
    repo = tmp_path / "consumer"
    repo.mkdir()
    assert _git(repo, "init", "-q").returncode == 0
    output_root = repo / ".leafcutter"
    decl = output_root / "config" / "knowledge_sink.json"

    assert build_knowledge_sink_declaration(output_root, {}, False, False) == 1
    sibling = decl.parent / "other_config.json"
    sibling.write_text("{}\n", encoding="utf-8")

    rel = decl.relative_to(repo).as_posix()
    assert _git(repo, "check-ignore", "-q", rel).returncode == 0, "declaration is not git-ignored"
    status = _git(repo, "status", "--porcelain", "--untracked-files=all").stdout
    assert "knowledge_sink.json" not in status
    assert "other_config.json" in status

    ignore_file = decl.parent / ".gitignore"
    with ignore_file.open("a", encoding="utf-8") as fh:
        fh.write("unrelated_line.tmp\n")
    build_knowledge_sink_declaration(output_root, {}, False, False)
    lines = ignore_file.read_text(encoding="utf-8").splitlines()
    assert sum(1 for ln in lines if "knowledge_sink.json" in ln) == 1
    assert "unrelated_line.tmp" in lines
    assert _git(repo, "check-ignore", "-q", rel).returncode == 0

    values = json.loads(decl.read_text(encoding="utf-8"))
    assert values["operational_log_root"] == str(repo / "debugging" / "logs")
    assert all(Path(v).is_absolute() for v in values.values())
