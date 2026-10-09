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


def _git_names(stage: str) -> str:
    """Return git's NUL-separated path list for *stage* (empty on a non-zero exit); log and re-raise when git cannot be run."""
    try:
        return subprocess.run(["git", *_NAME_ONLY[stage]], capture_output=True, text=True, check=False).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"precommit_canary: git failed for {stage}: {exc}", file=sys.stderr)
        raise


def _is_reserved(stage: str, spec: dict, args: list[str]) -> bool:
    """True when *stage*'s input is the declared reserved input (a path in the change, or the exact first line)."""
    if stage == "commit-msg":
        reserved = spec.get("message")
        if not isinstance(reserved, str) or not args:
            return False
        lines = Path(args[0]).read_text(encoding="utf-8").splitlines()
        return bool(lines) and lines[0].rstrip(chr(13)) == reserved
    reserved = spec.get("path")
    if not isinstance(reserved, str) or not reserved:
        return False
    return reserved in _git_names(stage).split(chr(0))


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
