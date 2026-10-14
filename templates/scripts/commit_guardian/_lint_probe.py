"""
MODULE: _lint_probe
GOAL: Feed a KNOWN-BAD and a KNOWN-CLEAN staged file through the deployed lint
    gate's real staged-mode pipeline, in a throwaway repository, and hand back
    the gate's own exit status -- so the gate's `negative_control` can be
    exercised by the negative-control liveness sweep in any working copy.
BUSINESS CONTEXT: GE-120f-1 / BP-1300e-1. A guard that has never been shown
    refusing anything is not counted as a guard. The sweep runs a hook's
    declared command in whatever working copy it is invoked from (this
    repository's root at commit time, a deployed-only copy in tests), so the
    known-bad input cannot be a file of the host project: the host's scope,
    excludes and ruff rules are not the subject. The probe therefore builds its
    own one-file project (own ruff.toml selecting E741 only, own staged
    `probe.py`) and runs THIS script on it as a separate process, exactly the
    way pre-commit does.
ARCHITECTURE: Stdlib only. The child runs with every GIT_* variable removed
    (the host hook's GIT_INDEX_FILE would otherwise point git at the HOST's
    index), a private XDG_CONFIG_HOME (no user-level ruff configuration can
    govern the probe) and the host's PATH and interpreter, so the probe also
    proves the toolchain that would judge a real commit works here. Known-bad
    must exit non-zero (`RESULT: refused`); known-clean must exit 0.

DECISION HISTORY
- 2026-10-12 [python-coder/BP-1300e-1]: Created. A first design named a
    checked-in sample file under tests/fixtures; the real-surface liveness
    test (GE-120f-1) runs the declared command in a deployed-only copy where
    that file does not exist, so the control read as not-rejected there.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

SAMPLES = {"known-bad": "l = 1\n", "known-clean": "value = 1\n"}
PROBE_RULES = 'select = ["E741"]'
TIMEOUT = 120


def _clean_env(xdg_home: Path) -> dict[str, str]:
    """The host environment minus GIT_* (it describes the HOST repository), with a private user config."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["XDG_CONFIG_HOME"] = str(xdg_home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _stage(root: Path, env: dict[str, str]) -> None:
    """Initialise the throwaway repo and stage its two files."""
    for argv in (["git", "init", "-q"], ["git", "add", "--", "ruff.toml", "probe.py"]):
        try:
            done = subprocess.run(argv, cwd=str(root), env=env, capture_output=True, text=True, check=False, timeout=TIMEOUT)
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("probe setup `%s` could not run: %s", " ".join(argv), exc)
            raise
        if done.returncode != 0:
            msg = f"probe setup `{' '.join(argv)}` failed: {done.stderr.strip()}"
            raise OSError(msg)


def run_probe(kind: str, gate: Path) -> int:
    """Run *gate* on a throwaway project holding the *kind* sample; return its exit status.

    Args:
        kind: ``"known-bad"`` (an E741 violation) or ``"known-clean"``.
        gate: Absolute path of check_lint_gate.py.

    Returns:
        The gate's own exit status (1 for a refusal, 0 for a clean pass), or 1
        when the probe project could not even be set up -- never a pass.
    """
    with tempfile.TemporaryDirectory(prefix="lint-gate-probe-") as tmp:
        root = Path(tmp)
        (root / "ruff.toml").write_text(f"[lint]\n{PROBE_RULES}\n", encoding="utf-8")
        (root / "probe.py").write_text(SAMPLES[kind], encoding="utf-8")
        env = _clean_env(root / "xdg")
        try:
            _stage(root, env)
            done = subprocess.run(
                [sys.executable, str(gate)], cwd=str(root), env=env, capture_output=True, text=True,
                check=False, timeout=TIMEOUT,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("lint gate probe %s could not run: %s", kind, exc)
            print(f"lint gate probe ({kind}) could not run: {exc}")
            print("RESULT: could_not_check")
            return 1
    print(done.stdout, end="")
    print(done.stderr, end="", file=sys.stderr)
    return done.returncode
