"""
MODULE: unit_tests/commit_guardian/_bp_1300e_lint_gate_env.py
COVERS: BP-1300e-1, -1-i, -1-ii, -1-iii, -1-iv, -1-v (helper module -- no tests)

GOAL: Build the REAL process environments the lint-gate tests run a commit in:
    a stub `ruff` module that reports a chosen version and delegates every other
    call to the real linter, a `ruff` module that cannot be imported, a `ruff`
    module that cannot start, a PATH with or without a ruff executable, and a
    `git` wrapper that fails one subcommand.

WHY THE ENVIRONMENT IS MANIPULATED, NOT THE LOCATOR PATCHED: the defect class
    is about what the hook process DISCOVERS in the environment it is given
    (GE-108e's rationale). Patching the locator would test the patch.

DECISION HISTORY
- 2026-10-12 [test-writer/BP-1300e-1]: Created. The "module unimportable"
    mechanism is a `sitecustomize.py` that sets ``sys.modules['ruff'] = None``,
    which makes `python -m ruff` print exactly "No module named ruff" -- the
    marker GE-108e's rule keys on -- instead of a differently-worded error.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

PIN = "0.15.15"
BOOM_TEXT = "boom: cannot start"


def real_ruff_bin() -> str:
    """Absolute path of the real ruff executable, found without the stubs."""
    try:
        from ruff.__main__ import find_ruff_bin  # type: ignore[import-not-found]

        return str(find_ruff_bin())
    except ImportError:
        found = shutil.which("ruff")
    assert found, "no real ruff available to delegate to: install requirements-dev.txt"
    return found


def _write(path: Path, text: str, executable: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _stub_dir(work: Path, tag: str, main_source: str) -> Path:
    stub = work / f"stub_{tag}"
    _write(stub / "ruff" / "__init__.py", "")
    _write(stub / "ruff" / "__main__.py", main_source)
    return stub


def version_stub(work: Path, version: str) -> Path:
    """`python -m ruff --version` answers `ruff <version>`; all else is real ruff."""
    source = (
        "import os, sys\n"
        f"VERSION = {version!r}\n"
        f"REAL = {real_ruff_bin()!r}\n"
        "args = sys.argv[1:]\n"
        "if args and args[0] in ('--version', 'version'):\n"
        "    print('ruff ' + VERSION)\n"
        "    raise SystemExit(0)\n"
        "os.execv(REAL, [REAL, *args])\n"
    )
    return _stub_dir(work, "v" + version.replace(".", "_"), source)


def boom_stub(work: Path) -> Path:
    """A ruff that writes BOOM_TEXT to stderr and exits 2 before reading input."""
    source = f"import sys\nsys.stderr.write({BOOM_TEXT + chr(10)!r})\nraise SystemExit(2)\n"
    return _stub_dir(work, "boom", source)


def blocked_module_dir(work: Path) -> Path:
    """A sitecustomize that makes the `ruff` module unimportable."""
    blocked = work / "blocked_ruff"
    _write(blocked / "sitecustomize.py", "import sys\nsys.modules['ruff'] = None\n")
    return blocked


def path_without_ruff() -> str:
    """The inherited PATH minus every directory that holds a `ruff` executable."""
    kept = [d for d in os.environ.get("PATH", "").split(os.pathsep) if d and not (Path(d) / "ruff").exists()]
    return os.pathsep.join(kept)


def path_with_ruff_exe(work: Path) -> str:
    """PATH without ruff, plus one directory whose only entry is a `ruff` link."""
    exe_dir = work / "exe_only"
    exe_dir.mkdir(parents=True, exist_ok=True)
    link = exe_dir / "ruff"
    if not link.exists():
        link.symlink_to(real_ruff_bin())
    return os.pathsep.join([path_without_ruff(), str(exe_dir)])


def git_wrapper_dir(work: Path, failing_subcommand: str, failing_flag: str) -> Path:
    """A `git` first on PATH that exits 128 for `<sub> ... <flag>` and delegates the rest."""
    real_git = shutil.which("git")
    assert real_git, "git not found"
    script = (
        "#!/bin/sh\n"
        f'if [ "$1" = "{failing_subcommand}" ]; then\n'
        "  for a in \"$@\"; do\n"
        f'    if [ "$a" = "{failing_flag}" ]; then echo "fatal: simulated failure" >&2; exit 128; fi\n'
        "  done\n"
        "fi\n"
        f'exec "{real_git}" "$@"\n'
    )
    wrapper = work / "git_wrapper"
    _write(wrapper / "git", script, executable=True)
    # The wrapper doubles as a GIT_EXEC_PATH (see hook_env), so it must also hold every helper
    # git looks up there; link the real exec-path entries in, except `git` itself.
    exec_path = subprocess.run([real_git, "--exec-path"], capture_output=True, text=True, check=True).stdout.strip()
    for entry in Path(exec_path).iterdir():
        link = wrapper / entry.name
        if entry.name != "git" and not link.exists():
            link.symlink_to(entry)
    return wrapper


def base_env() -> dict[str, str]:
    """Inherited environment with every GIT_* variable removed."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["COMMIT_AGENT_MODE"] = "1"
    env["PRE_COMMIT_COLOR"] = "never"
    env.pop("PYTHONPATH", None)
    return env


def hook_env(work: Path, *, ruff: str = f"stub:{PIN}", path: str = "inherit",
             git_wrapper: Path | None = None) -> dict[str, str]:
    """Compose the environment a commit (or a direct gate run) executes in.

    ruff: ``stub:<version>`` | ``boom`` | ``blocked`` | ``real``.
    path: ``inherit`` | ``strip`` (no ruff executable) | ``exe_only`` (strip, then
        one ruff executable and nothing else that provides ruff).
    """
    env = base_env()
    if ruff.startswith("stub:"):
        env["PYTHONPATH"] = str(version_stub(work, ruff.split(":", 1)[1]))
    elif ruff == "boom":
        env["PYTHONPATH"] = str(boom_stub(work))
    elif ruff == "blocked":
        env["PYTHONPATH"] = str(blocked_module_dir(work))
    assert ruff in ("boom", "blocked", "real") or ruff.startswith("stub:"), ruff
    if path == "strip":
        env["PATH"] = path_without_ruff()
    elif path == "exe_only":
        env["PATH"] = path_with_ruff_exe(work)
    if git_wrapper is not None:
        # git runs hooks with PATH=<exec-path>:<original PATH>, so a wrapper merely first on PATH
        # is shadowed by <exec-path>/git and never reached. GIT_EXEC_PATH moves the wrapper to
        # the front of the hook's PATH, which is the only place the gate's `git` is resolved.
        env["GIT_EXEC_PATH"] = str(git_wrapper)
    return env


PYTHON = sys.executable
