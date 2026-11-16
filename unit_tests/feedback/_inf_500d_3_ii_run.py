"""
MODULE: _inf_500d_3_ii_run
GOAL: Run the submit / search commands lifted from the DEPLOYED instructions, filled in for
    a concrete run, inside a copied layout (own declared sink, TMPDIR confined to the test).
BUSINESS CONTEXT: INF-500d-3-ii is about which file each agent's error stream lands in, so
    the tests execute the prescribed commands and read the files back.
ARCHITECTURE: ``prepare`` fills the placeholders for a run, confines ``/tmp/`` to the test's
    own tmpdir and points the ``scripts/feedback/`` prefix at the copied install. No build.py.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from unit_tests.feedback import _inf_500d_4_helpers as h
from unit_tests.feedback._inf_500d_3_helpers import Layout
from unit_tests.feedback._inf_500d_3_ii_check import Redirect, Run, Search, fill
from unit_tests.feedback._inf_500d_4_vi_helpers import _SCRIPT_PREFIX_RE


def prepare(command: str, run: Run, layout: Layout) -> str:
    """``command`` as ``run`` would execute it, confined to ``layout``."""
    text = fill(command, run).replace("/tmp/", f"{layout.tmpdir}/")
    text = _SCRIPT_PREFIX_RE.sub(lambda m: f"{layout.out_root}/{m.group(1)}", text)
    if text.startswith("FB_ID="):  # the capture form keeps the id in a variable: print it for the harness
        text += '; printf "%s" "$FB_ID"'
    return text


def _env(layout: Layout) -> dict[str, str]:
    env = h.make_env(layout.tmpdir, None, None)
    env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
    return env


def start(command: str, layout: Layout) -> subprocess.Popen[str]:
    return subprocess.Popen(["/bin/bash", "-c", command], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, cwd=str(layout.project), env=_env(layout))


def run_shell(command: str, layout: Layout) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["/bin/bash", "-c", command], capture_output=True, text=True, cwd=str(layout.project),
                          timeout=h.RUN_TIMEOUT, check=False, env=_env(layout))


def error_file(red: Redirect, run: Run, layout: Layout) -> Path:
    """Where ``run``'s error stream lands: the filled target, /tmp confined, relative names under the worktree."""
    target = fill(red.target, run).replace("/tmp/", f"{layout.tmpdir}/")
    path = Path(target)
    return path if path.is_absolute() else layout.project / path


def search_command(search: Search, run: Run, layout: Layout) -> str:
    return prepare(search.command, run, layout)


def sidecar_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.startswith("sidecar:")]
