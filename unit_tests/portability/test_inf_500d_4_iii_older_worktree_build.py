"""
MODULE: test_inf_500d_4_iii_older_worktree_build
GOAL: RED tests for review-fix defect M-3 -- the worktree bootstrap must survive a worktree whose own
    ``build.py`` predates ``--log-root`` / ``--no-log-root``.
AC: INF-500d-4-iii (every per-drive workspace is built pointing at the enduring log location of its project;
    when it cannot be, say so loudly rather than leave a silent gap); ADR-069 section 3.

THE DEFECT: ``templates/scripts/setup_ticket_worktree.py`` ``_bootstrap`` runs the WORKTREE'S OWN ``build.py``
    (the branch's, not the main tree's) and always appends ``--log-root <root>`` or ``--no-log-root``. A branch
    cut before those flags existed has a ``build.py`` whose argparse rejects them (exit 2). ``_bootstrap`` treats
    that as "the build failed", and -- because nothing was built -- the pre-commit safety net then either links the
    MAIN tree's ``.leafcutter`` into the worktree silently (no build, no warning that the worktree has no durable
    root) or, when the main tree has none, raises ``BootstrapError.missing_config``.

THE CONTRACT: a build that rejects the log-root flag is retried ONCE WITHOUT the flag; the bootstrap then
    warns on stderr, loudly (``WARNING``), that the worktree got no durable log root (so what it logs will not
    survive its removal); it does not raise ``missing_config``; and the worktree carries its own build output,
    not a link into the main tree. A build that accepts the flag is called once, with the recorded root, and no
    warning of this kind is printed (the control).

REAL-ARTIFACT NOTE: the REAL ``_bootstrap`` of ``templates/scripts/setup_ticket_worktree.py`` runs in a fresh
    process against a git-initialised temp worktree. The only stand-in is the worktree's ``scripts/build.py``: a
    small real argparse program that behaves like a pre-flag build (``--target-dir`` only), records every argv
    it receives, and materialises ``<target>/.leafcutter/`` -- a real build costs ~60s (see CLAUDE.md "Tests must
    not spawn their own build.py"). The main install's declaration is written by the REAL build helper.
"""
# @ac-tag: INF-500d-4-iii

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _WORKTREE_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from build_log_root import CONFIG_KEY  # noqa: E402
from build_phases_knowledge import build_knowledge_sink_declaration  # noqa: E402

_TEMPLATE_BOOTSTRAP = _WORKTREE_ROOT / "templates" / "scripts" / "setup_ticket_worktree.py"
_RUN_TIMEOUT = 120
_LOG_FLAGS = ("--log-root", "--no-log-root")

_BOOTSTRAP_DRIVER = (
    "import importlib.util, sys\n"
    "from pathlib import Path\n"
    "spec = importlib.util.spec_from_file_location('swt', sys.argv[1])\n"
    "m = importlib.util.module_from_spec(spec)\n"
    "sys.modules['swt'] = m\n"
    "spec.loader.exec_module(m)\n"
    "m._bootstrap(Path(sys.argv[2]), Path(sys.argv[3]))\n"
)

# A worktree's build.py from a branch cut BEFORE the log-root flags: argparse knows --target-dir only.
_OLD_BUILD = '''\
import argparse, json, os, sys
from pathlib import Path

with open(os.environ["BUILD_STUB_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\\n")
parser = argparse.ArgumentParser()
parser.add_argument("--target-dir", required=True)
args = parser.parse_args()  # an unknown --log-root / --no-log-root exits 2 here, like the old build
out = Path(args.target_dir) / ".leafcutter" / "config"
out.mkdir(parents=True, exist_ok=True)
(out / "built_by_stub.txt").write_text("built without a log-root flag\\n", encoding="utf-8")
'''

# The same program for a branch that DOES know the flags.
_NEW_BUILD = _OLD_BUILD.replace(
    'parser.add_argument("--target-dir", required=True)',
    'parser.add_argument("--target-dir", required=True)\n'
    'parser.add_argument("--log-root", default=None)\n'
    'parser.add_argument("--no-log-root", action="store_true")',
)


def _main_repo(base: Path, *, declared: bool) -> tuple[Path, Path]:
    """A main tree; with ``declared`` it carries the build helper's real declaration. Returns ``(main, root)``."""
    main = base / "main"
    (main / ".leafcutter").mkdir(parents=True)
    root = base / "enduring" / "debugging" / "logs"
    if declared:
        build_knowledge_sink_declaration(main / ".leafcutter", {CONFIG_KEY: str(root)}, False, True)
        recorded = json.loads((main / ".leafcutter" / "config" / "knowledge_sink.json").read_text(encoding="utf-8"))
        assert recorded["operational_log_root"] == str(root), "fixture: the real helper must record the inherited root"
    else:
        (main / ".leafcutter").rmdir()
    return main, root


def _worktree(base: Path, build_source: str) -> Path:
    worktree = base / "worktree"
    (worktree / "scripts").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(worktree)], check=True, capture_output=True)
    (worktree / "scripts" / "build.py").write_text(build_source, encoding="utf-8")
    (worktree / "skills_config.json").write_text(json.dumps({"_comment": "minimal"}), encoding="utf-8")
    return worktree


def _bootstrap(main: Path, worktree: Path, calls: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["BUILD_STUB_LOG"] = str(calls)
    return subprocess.run(
        [sys.executable, "-c", _BOOTSTRAP_DRIVER, str(_TEMPLATE_BOOTSTRAP), str(main), str(worktree)],
        capture_output=True, text=True, timeout=_RUN_TIMEOUT, cwd=str(worktree), check=False, env=env,
    )


def _calls(path: Path) -> list[list[str]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


def _has_log_flag(argv: list[str]) -> bool:
    return any(arg in _LOG_FLAGS for arg in argv)


def _no_durable_root_warning(stderr: str) -> list[str]:
    """WARNING lines saying the worktree has no durable/enduring log root (its logs will not survive removal)."""
    return [
        line for line in stderr.splitlines()
        if "WARNING" in line and "root" in line.lower() and re.search(r"durable|enduring|survive", line, re.IGNORECASE)
    ]


@pytest.mark.parametrize("main_declares_a_root", [True, False], ids=["main_has_a_declaration", "main_has_none"])
def test_a_worktree_build_that_rejects_the_log_root_flag_is_retried_without_it_and_warned_about(tmp_path, main_declares_a_root):
    # covers: INF-500d-4-iii
    # angle: failure
    """The worktree's own build.py rejects --log-root/--no-log-root (exit 2): the bootstrap retries the build
    without the flag, prints a WARNING that the worktree got no durable log root, raises nothing, and leaves the
    worktree with its OWN build output rather than a link into the main tree."""
    main, _root = _main_repo(tmp_path, declared=main_declares_a_root)
    worktree = _worktree(tmp_path, _OLD_BUILD)
    calls = tmp_path / "build_calls.jsonl"

    proc = _bootstrap(main, worktree, calls)

    assert "missing_config" not in proc.stderr and proc.returncode == 0, (
        f"an older worktree build must not abort the bootstrap: rc={proc.returncode}\n{proc.stderr}")
    argvs = _calls(calls)
    assert len(argvs) >= 2, f"the bootstrap must RETRY a build that rejected the flag; the build ran {len(argvs)} time(s): {argvs}"
    assert _has_log_flag(argvs[0]), f"fixture: the first attempt is the one that carries the flag: {argvs[0]}"
    assert not _has_log_flag(argvs[-1]), f"the fallback build must run WITHOUT the log-root flags: {argvs[-1]}"
    leafcutter = worktree / ".leafcutter"
    assert leafcutter.is_dir() and not leafcutter.is_symlink(), (
        f"the worktree must carry its own build output, not a link into the main tree: {leafcutter}")
    assert (leafcutter / "config" / "built_by_stub.txt").is_file(), "the fallback build did not produce the worktree's output"
    warnings = _no_durable_root_warning(proc.stderr)
    assert warnings, (
        "the bootstrap must warn loudly that this worktree got no durable log root (what it logs will not survive "
        f"its removal); stderr was:\n{proc.stderr}")


def test_a_worktree_build_that_knows_the_flag_is_called_once_with_the_recorded_root(tmp_path):
    # covers: INF-500d-4-iii
    # angle: discrimination
    """Control for the retry above (green today): a build that accepts the flag runs once, gets the root the main
    install recorded, and no 'no durable root' warning is printed -- so the fallback is only for a rejection and
    cannot be satisfied by always dropping the flag."""
    main, root = _main_repo(tmp_path, declared=True)
    worktree = _worktree(tmp_path, _NEW_BUILD)
    calls = tmp_path / "build_calls.jsonl"

    proc = _bootstrap(main, worktree, calls)

    assert proc.returncode == 0, proc.stderr
    argvs = _calls(calls)
    assert len(argvs) == 1, f"a build that accepts the flag must not be retried: {argvs}"
    assert argvs[0][argvs[0].index("--log-root") + 1] == str(root), f"the recorded root must be passed verbatim: {argvs[0]}"
    assert not _no_durable_root_warning(proc.stderr), f"nothing is wrong, nothing to warn about:\n{proc.stderr}"
