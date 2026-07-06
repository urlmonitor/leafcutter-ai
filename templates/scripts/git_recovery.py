"""
MODULE: git_recovery.py
GOAL: Human-invoked entry point for guided git repository recovery after the
    BO-1600c corruption-detection halt has reported that the shared repository
    is in a damaged state.
BUSINESS CONTEXT: Parallel drive loops can corrupt the shared git object store
    (0-byte loose objects, broken index). The BO-1600c halt path detects the
    damage and stops the drive loop. This script is the SEPARATE, HUMAN-INVOKED
    recovery surface that the operator runs manually after reading the halt
    report. It must never be called automatically by the drive loop or by the
    BO-1600c halt path.
ARCHITECTURE: Standalone Python stdlib script (no project-specific imports).
    Ships in templates/scripts/ so build_template_standalone_scripts() in
    build_phases.py auto-deploys it via its shallow glob('*.py'). Detailed
    recovery plan-and-confirm behavior is owned by BO-1600d-2; step execution
    is owned by BO-1600d-3. This script is the entry shell only — it gates on
    explicit human confirmation before passing control to those layers.

    IMPORTANT — HUMAN-INVOKED ONLY: This script must NOT be called from any
    automatic drive loop, from the BO-1600c halt path, or from any orchestrator.
    The BO-1600c halt path only reports the damage and points the human at this
    script — it does not chain into running recovery itself.

    Serial-drive and commit-serialization-lock prevention is owned by
    templates/skills/building-epics/SKILL.md — see that file, not this script,
    for the prevention rules.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


def parse_args(args=None):
    """Parse command-line arguments for the recovery entry point.

    Parameters
    ----------
    args:
        Argument list to parse; defaults to ``sys.argv[1:]`` when ``None``.

    Returns
    -------
    argparse.Namespace
        Parsed arguments with at least a ``repo`` attribute.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Human-invoked git repository recovery entry point. "
            "Run this script after the BO-1600c halt has stopped an automatic "
            "drive and reported repository corruption. "
            "DO NOT call this from an automated loop."
        )
    )
    parser.add_argument(
        "--repo",
        default=os.getcwd(),
        help="Path to the git repository to recover (default: current directory).",
    )
    return parser.parse_args(args)


def run_status_probe(repo_path: Path) -> str | None:
    """Run a read-only git status probe on the repository.

    This function performs NO git writes. It is a read-only diagnostic probe
    only. Errors are logged at WARNING level and ``None`` is returned so the
    caller can abort gracefully without propagating an unhandled exception.

    Parameters
    ----------
    repo_path:
        Absolute path to the git repository root.

    Returns
    -------
    str or None
        A human-readable summary string on success, or ``None`` if the probe
        failed (the error is logged before returning ``None``).
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.warning("Git status probe failed for %s: %s", repo_path, exc)
        return None
    except OSError as exc:
        logger.warning("Filesystem probe failed for %s: %s", repo_path, exc)
        return None

    # Pure computation outside the I/O boundary — no try/except needed here.
    lines = [ln for ln in result.stdout.strip().splitlines() if ln]
    count = len(lines)
    return (
        f"Repository: {repo_path}\n"
        f"Git status: {count} modified/untracked file(s) detected.\n"
        "\nNote: Further diagnosis and recovery steps are handled in "
        "BO-1600d-2 and BO-1600d-3."
    )


def main(args=None) -> None:
    """Entry point for the human-invoked git recovery script.

    Behaviour:

    1. If the process is not attached to an interactive TTY, exits ``0``
       immediately without making any git write.
    2. Runs a read-only status probe and displays the summary.
    3. Asks the human to confirm before proceeding.
    4. Only after the human types ``yes`` does it proceed to recovery steps
       (stubbed here — implemented in BO-1600d-2 and BO-1600d-3).

    Parameters
    ----------
    args:
        Optional argument list; defaults to ``sys.argv[1:]`` when ``None``.
    """
    parsed = parse_args(args)
    repo_path = Path(parsed.repo).resolve()

    # Non-interactive guard: no git writes without a TTY.
    if not sys.stdin.isatty():
        print(
            "Recovery requires interactive confirmation. "
            "Run this script in an interactive terminal."
        )
        sys.exit(0)

    # Read-only probe — no git writes at this stage.
    probe_summary = run_status_probe(repo_path)
    if probe_summary is None:
        print(
            "Error: repository probe failed. "
            "Check the log above for details. Recovery aborted."
        )
        return

    print(probe_summary)
    print()

    # Confirmation gate — no git writes until human explicitly confirms.
    try:
        answer = input("Proceed with recovery? [yes/N]: ").strip()
    except EOFError:
        print("\nNo input received. Recovery aborted — no changes made.")
        return

    if answer != "yes":
        print("Recovery aborted — no changes made.")
        return

    # Post-confirmation stub: detailed recovery is implemented in BO-1600d-2/3.
    print(
        "Confirmation received. "
        "Detailed recovery steps (BO-1600d-2 and BO-1600d-3) are not yet implemented."
    )


if __name__ == "__main__":
    main()
