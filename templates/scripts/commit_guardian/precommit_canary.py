#!/usr/bin/env python3
"""
MODULE: precommit_canary
GOAL: Canary hook -- with no arguments emits PRECOMMIT_CANARY_OK and exits 0;
    with ``--stage <stage>`` rejects (exit 1) the stage's own known-bad input.
BUSINESS CONTEXT: Part of the WorktreeQualityGateGuard system. With no
    arguments this script is the manual-stage-only pre-commit hook
    (stages: [manual]) whose PRECOMMIT_CANARY_OK stdout verify_precommit_active.py
    check D inspects. With ``--stage`` it is the hook the workspace maker's
    per-stage canaries (BO-4300c-1-ii) are declared to be rejected by: the
    known-bad input for each stage is read from this install's own
    ``commit_guardian.json`` ``stage_canaries`` entry, never hard-coded here.
ARCHITECTURE: Stdlib only (json, subprocess, sys, pathlib). The no-argument
    path is unchanged and import-free of any logic that could mask a
    worktree-environment failure. ``--stage pre-commit`` scans the staged diff,
    ``--stage commit-msg <msgfile>`` the message file, and ``--stage post-merge``
    the merge's own diff (``ORIG_HEAD..HEAD``) for the declared token.

====================================================================
DECISION HISTORY
====================================================================
- 2026-07-06 [EPIC-WorktreeQualityGateGuard/02]: Initial implementation.
  Canary is intentionally minimal -- any logic here would mask worktree
  environment failures, defeating the probe's purpose.
- 2026-10-01 00:30 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05]:
  (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05)
  Added the ``--stage`` mode (BO-4300c-1-ii); the no-argument output is
  byte-for-byte unchanged. (ADR-018)
- 2026-10-09 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05]:
  (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05)
  git call wrapped (check-exception-handling IO-001); git being unrunnable
  (OSError/SubprocessError) now fails CLOSED (exit 1, stderr message, no PRECOMMIT_CANARY_REJECTED marker).
- 2026-10-10 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/15]:
  (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/15)
  BO-4300c-6: git non-zero exits fail closed with a one-line report and no
  marker; post-merge treats only a missing ORIG_HEAD as "nothing merged";
  names and commit messages are compared as bytes (never decoded).
====================================================================
"""

import json
import subprocess
import sys
from pathlib import Path

_DECLARATION = Path(__file__).resolve().parent / "commit_guardian.json"
_NAME_ONLY = {
    "pre-commit": ["diff", "--cached", "--name-only", "-z"],
    "post-merge": ["diff", "--name-only", "-z", "--diff-filter=A", "ORIG_HEAD", "HEAD"],
}


def declared_spec(stage: str) -> dict | None:
    """Return the reserved-input declaration for *stage*, or ``None`` when undeclared/unreadable."""
    try:
        spec = json.loads(_DECLARATION.read_text(encoding="utf-8"))["stage_canaries"][stage]
    except (OSError, ValueError, KeyError) as exc:
        print(f"precommit_canary: no canary declared for {stage}: {exc}", file=sys.stderr)
        return None
    return spec if isinstance(spec, dict) else None


def _git(stage: str, args: list[str]) -> subprocess.CompletedProcess:
    """Run git with *args* for *stage*, capturing raw bytes; log and re-raise when git cannot be started."""
    try:
        return subprocess.run(["git", *args], capture_output=True, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"precommit_canary: git failed for {stage}: {exc}", file=sys.stderr)
        raise


def _git_failure(args: list[str], done: subprocess.CompletedProcess) -> subprocess.CalledProcessError:
    """Print the one-line git failure report (command, status, git's own stderr) and return the error to raise."""
    text = done.stderr.decode("utf-8", errors="replace").strip()
    print(f"precommit_canary: git {' '.join(args)} exited {done.returncode}: {text}", file=sys.stderr)
    return subprocess.CalledProcessError(done.returncode, ["git", *args], done.stdout, done.stderr)


def _git_names(stage: str) -> list[bytes]:
    """Return git's NUL-split raw path list for *stage*; raise on any git failure (never read as empty)."""
    where = ["rev-parse", "--git-dir"]  # a non-repository must report itself, not fall into diff --no-index
    located = _git(stage, where)
    if located.returncode != 0:
        raise _git_failure(where, located)
    if stage == "post-merge":
        probe = ["rev-parse", "-q", "--verify", "ORIG_HEAD"]
        done = _git(stage, probe)
        if done.returncode == 1:
            return []  # only a missing ORIG_HEAD record means nothing was merged
        if done.returncode != 0:
            raise _git_failure(probe, done)
    args = _NAME_ONLY[stage]
    done = _git(stage, args)
    if done.returncode != 0:
        raise _git_failure(args, done)
    return done.stdout.split(b"\0")


def _first_line_is(path: str, reserved: str) -> bool:
    """True when the message file's first line equals *reserved* exactly (bytes compared, CR dropped)."""
    lines = Path(path).read_bytes().splitlines()
    return bool(lines) and lines[0].rstrip(bytes([13])) == reserved.encode("utf-8")


def _is_reserved(stage: str, spec: dict, args: list[str]) -> bool:
    """True when *stage*'s input is the declared reserved input (a path in the change, or the exact first line)."""
    if stage == "commit-msg":
        reserved = spec.get("message")
        if not isinstance(reserved, str) or not args:
            return False
        return _first_line_is(args[-1], reserved)
    reserved = spec.get("path")
    if not isinstance(reserved, str) or not reserved:
        return False
    return reserved.encode("utf-8") in _git_names(stage)


def run_stage(stage: str, args: list[str]) -> int:
    """Exit 1 only when *stage*'s input is its declared reserved input, else 0 (never scans contents)."""
    spec = declared_spec(stage)
    if spec is None or stage not in ("pre-commit", "commit-msg", "post-merge"):
        return 0
    try:
        found = _is_reserved(stage, spec, args)
    except (OSError, subprocess.SubprocessError) as exc:
        # Fail CLOSED without the rejection marker: an infrastructure error is never proof a stage fired.
        print(f"precommit_canary: cannot read the {stage} input, failing closed: {exc}", file=sys.stderr)
        return 1
    if found:
        print(f"PRECOMMIT_CANARY_REJECTED ({stage}): known-bad input")
    return 1 if found else 0


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--stage":
        sys.exit(run_stage(sys.argv[2], sys.argv[3:]))
    print("PRECOMMIT_CANARY_OK")
