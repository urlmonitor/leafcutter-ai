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

DECISION HISTORY:
    BO-1600d-2 (2026-07-06): Added dry-run-first behavior. plan_recovery_actions()
    computes the ordered plan without executing it. print_recovery_plan() shows the
    plan to the operator. execute_recovery_plan() executes the same plan object,
    guaranteeing the executed set matches what was printed. --execute flag bypasses
    interactive confirmation for scripted use.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

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
        Parsed arguments with at least a ``repo`` attribute and an
        ``execute`` boolean flag.
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
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help=(
            "Execute the recovery plan after printing it. Without this flag, "
            "the script prints the plan and exits after interactive confirmation "
            "(dry-run-first mode)."
        ),
    )
    return parser.parse_args(args)


class RecoveryAction:
    """A single step in the recovery plan.

    Holds a human-readable description and a callable that performs the step
    when invoked. The callable must be self-contained — it receives no arguments
    and raises on failure so ``execute_recovery_plan`` can propagate the error.

    Parameters
    ----------
    description:
        Human-readable label shown in the dry-run plan and in the execution log.
    execute_fn:
        Zero-argument callable that carries out the recovery step. Called by
        ``execute()``; must raise on failure.
    """

    def __init__(self, description: str, execute_fn: Callable[[], None]) -> None:
        self.description = description
        self._execute_fn = execute_fn

    def execute(self) -> None:
        """Invoke the underlying recovery callable.

        Raises
        ------
        Exception
            Re-raises whatever the underlying callable raises, so callers can
            decide how to handle or report the failure.
        """
        self._execute_fn()


def detect_zero_byte_objects(repo_path: Path) -> list:
    """Scan the git object store for zero-byte loose objects.

    Walks ``repo_path/.git/objects/`` looking for two-character hex subdirectories
    and returns any file entries whose size on disk is exactly zero bytes. Pure
    filesystem I/O — does NOT invoke any subprocess.

    Parameters
    ----------
    repo_path:
        Absolute path to the git repository root.

    Returns
    -------
    list[Path]
        Paths of zero-byte loose object files, or an empty list if none are
        found or the objects directory cannot be read.
    """
    objects_dir = repo_path / ".git" / "objects"
    zero_byte_paths: list = []

    try:
        subdirs = list(objects_dir.iterdir())
    except OSError as exc:
        logger.warning("Cannot read git objects directory %s: %s", objects_dir, exc)
        return zero_byte_paths

    for entry in subdirs:
        # Loose object subdirectories are exactly two hex characters.
        if not (entry.is_dir() and len(entry.name) == 2 and _is_hex(entry.name)):
            continue
        try:
            for obj_file in entry.iterdir():
                try:
                    if obj_file.stat().st_size == 0:
                        zero_byte_paths.append(obj_file)
                except OSError as exc:
                    logger.warning(
                        "Cannot stat git object %s: %s", obj_file, exc
                    )
                    continue
        except OSError as exc:
            logger.warning("Cannot read object subdir %s: %s", entry, exc)
            continue

    return zero_byte_paths


def _is_hex(s: str) -> bool:
    """Return True if every character in *s* is a hexadecimal digit.

    Pure function — no I/O, no try/except.
    """
    return all(c in "0123456789abcdefABCDEF" for c in s)


def plan_recovery_actions(repo_path: Path) -> list:
    """Compute the ordered recovery plan without executing any git writes.

    Detects zero-byte loose objects and always appends a re-fetch step. The
    returned list is the authoritative plan — pass the same object to both
    ``print_recovery_plan`` and ``execute_recovery_plan`` to guarantee that
    what is printed is exactly what is executed.

    Parameters
    ----------
    repo_path:
        Absolute path to the git repository root.

    Returns
    -------
    list[RecoveryAction]
        Ordered list of actions to be executed during recovery.
    """
    plan: list = []

    zero_byte = detect_zero_byte_objects(repo_path)
    if zero_byte:
        paths_str = ", ".join(str(p) for p in zero_byte)
        description = f"Remove {len(zero_byte)} zero-byte loose object(s): {paths_str}"

        # Capture zero_byte in the closure — we must not re-detect at execute time
        # so the executed set matches the printed plan exactly.
        def _make_delete_fn(paths):
            def _delete_fn():
                for path in paths:
                    try:
                        path.unlink()
                    except OSError as exc:
                        logger.warning("Failed to remove %s: %s", path, exc)
                        raise
            return _delete_fn

        plan.append(RecoveryAction(description, _make_delete_fn(zero_byte)))

    def _refetch_fn():
        try:
            subprocess.run(
                ["git", "-C", str(repo_path), "fetch", "--refetch", "origin"],
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            logger.warning("git fetch --refetch failed for %s: %s", repo_path, exc)
            raise

    plan.append(RecoveryAction("Re-fetch objects from origin", _refetch_fn))
    return plan


def print_recovery_plan(plan: list) -> None:
    """Print the recovery plan to stdout without executing any step.

    Parameters
    ----------
    plan:
        Ordered list of ``RecoveryAction`` objects as returned by
        ``plan_recovery_actions``.
    """
    if not plan:
        print("No recovery actions needed.")
        return
    print(f"Recovery plan ({len(plan)} action(s)):")
    for i, action in enumerate(plan, start=1):
        print(f"  {i}. {action.description}")


def execute_recovery_plan(plan: list) -> None:
    """Execute each action in *plan* in order, logging progress to stdout.

    Parameters
    ----------
    plan:
        Ordered list of ``RecoveryAction`` objects — must be the same object
        that was passed to ``print_recovery_plan`` for this repository state.
    """
    for i, action in enumerate(plan, start=1):
        print(f"  Executing step {i}: {action.description}")
        action.execute()
        print(f"  Step {i} complete.")


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

    Dry-run-first behaviour (BO-1600d-2):

    1. Parse args — includes new ``--execute`` flag.
    2. Resolve ``repo_path``.
    3. TTY guard: if NOT attached to a TTY AND ``--execute`` was not supplied,
       print a message and exit 0 without any git write.
    4. Run read-only status probe; if it fails, print an error and return.
    5. Print the probe summary.
    6. Compute the recovery plan via ``plan_recovery_actions()``.
    7. Print the plan via ``print_recovery_plan()``.
    8. If ``--execute`` flag is set: execute the plan and return (no prompt).
    9. Interactive confirmation: prompt ``Execute this plan? [yes/N]: ``.
    10. If "yes": execute the plan; print "Recovery complete."
    11. Otherwise: print "Recovery aborted — no changes made."

    Key invariant: the same ``plan`` object is passed to both
    ``print_recovery_plan`` and ``execute_recovery_plan`` so the executed set
    is guaranteed to match the printed plan for this repository state.

    Parameters
    ----------
    args:
        Optional argument list; defaults to ``sys.argv[1:]`` when ``None``.
    """
    parsed = parse_args(args)
    repo_path = Path(parsed.repo).resolve()

    # Non-interactive guard: no git writes without a TTY unless --execute was given.
    if not sys.stdin.isatty() and not parsed.execute:
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

    # Compute and display the recovery plan — no git writes during planning.
    plan = plan_recovery_actions(repo_path)
    print_recovery_plan(plan)
    print()

    # --execute flag: skip interactive prompt and execute immediately.
    if parsed.execute:
        execute_recovery_plan(plan)
        print("Recovery complete.")
        return

    # Interactive confirmation gate — no git writes until human explicitly confirms.
    try:
        answer = input("Execute this plan? [yes/N]: ").strip()
    except EOFError:
        print("\nNo input received. Recovery aborted — no changes made.")
        return

    if answer == "yes":
        execute_recovery_plan(plan)
        print("Recovery complete.")
    else:
        print("Recovery aborted — no changes made.")


if __name__ == "__main__":
    main()
