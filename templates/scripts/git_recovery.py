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

_GIT_REFETCH_MIN_VERSION: tuple = (2, 36, 0)


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


def _git_version() -> tuple:
    """Return the installed git version as a 3-int tuple (major, minor, patch).

    Runs ``git --version``, parses the output, and returns a tuple of exactly
    3 ints.  Handles both ``"git version 2.41.0"`` and Apple-style outputs
    such as ``"2.39.2 (Apple Git-143)"`` — takes the first ``N.N[.N]`` numeric
    token and pads patch to 0 when absent.

    Returns
    -------
    tuple
        Three-element tuple of ints ``(major, minor, patch)``.

    Raises
    ------
    subprocess.CalledProcessError
        Re-raised (after logging at WARNING) if ``git --version`` exits
        non-zero or cannot be launched.
    ValueError
        Raised when the version string cannot be parsed into at least two
        numeric components.
    """
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.warning("git --version failed: %s", exc)
        raise

    raw = result.stdout.strip()
    # Strip leading "git version " prefix if present, then tokenise.
    text = raw.replace("git version ", "")
    # Take the first whitespace-separated token to strip Apple annotations.
    first_token = text.split()[0] if text.split() else ""
    # Split on dots and take only leading digit groups.
    parts = first_token.split(".")
    numeric: list = []
    for part in parts:
        # Strip any trailing non-digit characters (e.g. "(Apple").
        digits = ""
        for ch in part:
            if ch.isdigit():
                digits += ch
            else:
                break
        if not digits:
            break
        numeric.append(int(digits))
        if len(numeric) == 3:
            break

    if len(numeric) < 2:
        raise ValueError(
            f"Cannot parse git version from output: {raw!r}; "
            f"expected at least major.minor"
        )

    # Pad patch to 0 when absent.
    while len(numeric) < 3:
        numeric.append(0)

    return (numeric[0], numeric[1], numeric[2])


def detect_corrupt_branch_refs(repo_path: Path) -> list:
    """Detect branch refs that point at corrupt (unreadable) commits.

    Enumerates all local branch refs via ``git for-each-ref`` and probes each
    tip commit with ``git cat-file -t``. A branch is considered corrupt when
    its tip commit SHA cannot be read.  NEVER hardcodes branch names.

    Parameters
    ----------
    repo_path:
        Absolute path to the git repository root.

    Returns
    -------
    list[tuple[str, str]]
        List of ``(branch_name, sha)`` tuples for each branch whose tip commit
        cannot be read by ``git cat-file``. Empty list when no corrupt refs are
        found.

    Raises
    ------
    subprocess.CalledProcessError
        Re-raised if ``git for-each-ref`` itself fails (e.g. not a git repo).
    """
    corrupt: list = []
    if not (repo_path / ".git").is_dir():
        return corrupt
    try:
        result = subprocess.run(
            [
                "git", "-C", str(repo_path), "for-each-ref",
                "--format=%(refname:short) %(objectname)", "refs/heads/",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.warning("git for-each-ref failed for %s: %s", repo_path, exc)
        raise

    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 2:
            continue
        branch_name, sha = parts
        try:
            subprocess.run(
                ["git", "-C", str(repo_path), "cat-file", "-t", sha],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            corrupt.append((branch_name, sha))

    return corrupt


def get_reflog_tip(repo_path: Path, branch_name: str) -> str:
    """Return the first readable commit SHA from the branch's reflog.

    Iterates the branch reflog in order (most-recent first) and returns the
    first SHA that ``git cat-file -t`` can read.  Skips entries that are
    themselves corrupt.

    Parameters
    ----------
    repo_path:
        Absolute path to the git repository root.
    branch_name:
        Local branch name (no ``refs/heads/`` prefix).

    Returns
    -------
    str
        A readable commit SHA from the reflog.

    Raises
    ------
    subprocess.CalledProcessError
        Re-raised if ``git reflog show`` itself fails.
    ValueError
        Raised when no readable reflog entry exists for the branch.
    """
    try:
        result = subprocess.run(
            [
                "git", "-C", str(repo_path), "reflog", "show",
                "--format=%H", branch_name,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.warning(
            "git reflog failed for %s branch %s: %s", repo_path, branch_name, exc
        )
        raise

    for sha in result.stdout.strip().splitlines():
        sha = sha.strip()
        if not sha:
            continue
        try:
            subprocess.run(
                ["git", "-C", str(repo_path), "cat-file", "-t", sha],
                capture_output=True,
                text=True,
                check=True,
            )
            return sha
        except subprocess.CalledProcessError:
            continue

    raise ValueError(
        f"No readable reflog entry found for branch {branch_name!r} in {repo_path}"
    )


def detect_poisoned_index(repo_path: Path) -> bool:
    """Detect whether the git index cache-tree is poisoned.

    Runs ``git status --short`` and inspects stderr for well-known
    cache-tree corruption signals.  Returns ``True`` if the index appears
    poisoned, ``False`` if it reads cleanly.

    Parameters
    ----------
    repo_path:
        Absolute path to the git repository root.

    Returns
    -------
    bool
        ``True`` when a corruption signal is found in stderr; ``False``
        otherwise.

    Raises
    ------
    OSError
        Re-raised when the OS cannot even launch the git subprocess (e.g.
        ``git`` binary missing).
    """
    if not (repo_path / ".git").is_dir():
        return False
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "status", "--short"],
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        logger.warning("OS error running git status for %s: %s", repo_path, exc)
        raise

    stderr_lower = result.stderr.lower() if isinstance(result.stderr, str) else ""
    corruption_signals = [
        "error: invalid object",
        "fatal: ",
        "error: cache-tree",
        "error: object file",
    ]
    return any(signal in stderr_lower for signal in corruption_signals)


def verify_recovery_integrity(repo_path: Path, plan: list) -> bool:
    """Verify that the items addressed by *plan* are now clean.

    Scopes its checks to only the facets the plan explicitly addressed,
    avoiding false positives from unrelated repository state.

    Parameters
    ----------
    repo_path:
        Absolute path to the git repository root.
    plan:
        The same ``list[RecoveryAction]`` that was executed; used to
        determine which integrity checks are relevant.

    Returns
    -------
    bool
        ``True`` when all addressed items are clean, ``False`` when at least
        one addressed item remains corrupted.
    """
    plan_desc_lower = [a.description.lower() for a in plan]

    # Check zero-byte objects are gone.
    if any("remove" in d or "zero" in d for d in plan_desc_lower):
        remaining = detect_zero_byte_objects(repo_path)
        if remaining:
            logger.warning(
                "verify_recovery_integrity: %d zero-byte object(s) remain after recovery",
                len(remaining),
            )
            return False

    # Check branch refs are now readable.
    if any("reset" in d and ("ref" in d or "branch" in d) for d in plan_desc_lower):
        corrupt_refs = detect_corrupt_branch_refs(repo_path)
        if corrupt_refs:
            logger.warning(
                "verify_recovery_integrity: %d branch ref(s) still corrupt after recovery",
                len(corrupt_refs),
            )
            return False

    # Check index cache-tree is clean.
    if any(
        ("cache" in d and "tree" in d) or ("rebuild" in d and "index" in d)
        for d in plan_desc_lower
    ):
        if detect_poisoned_index(repo_path):
            logger.warning(
                "verify_recovery_integrity: index cache-tree still poisoned after recovery"
            )
            return False

    return True


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

    # Check git version before the zero-byte detection block.
    # If the version check fails or the version is too old, the refetch path is
    # not viable and the remove step must also be suppressed (to avoid leaving
    # the store in a worse state than the halted state — see AC invariant).
    refetch_viable: bool
    detected_ver: tuple = (0, 0, 0)
    try:
        detected_ver = _git_version()
        refetch_viable = detected_ver >= _GIT_REFETCH_MIN_VERSION
    except (subprocess.CalledProcessError, ValueError) as exc:
        logger.warning(
            "Cannot determine git version; disabling refetch path: %s", exc
        )
        refetch_viable = False

    zero_byte = detect_zero_byte_objects(repo_path)
    if zero_byte:
        if refetch_viable:
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
        else:
            # Refuse path: do NOT remove objects (would leave store worse off).
            ver_str = ".".join(str(v) for v in detected_ver)
            min_ver_str = ".".join(str(v) for v in _GIT_REFETCH_MIN_VERSION)
            n = len(zero_byte)
            blocked_description = (
                f"BLOCKED — git {ver_str} does not support fetch --refetch "
                f"(minimum required: {min_ver_str}). "
                f"{n} zero-byte object(s) detected but the remove step is not applied: "
                f"without --refetch the objects cannot be restored from origin and the "
                f"object store would be left in a worse state. "
                f"Upgrade git to 2.36 or later and re-run recovery."
            )

            def _make_blocked_fn(ver, min_ver):
                def _blocked_fn():
                    raise RuntimeError(
                        f"Recovery blocked: installed git {'.'.join(str(v) for v in ver)} "
                        f"does not support fetch --refetch (minimum required: "
                        f"{'.'.join(str(v) for v in min_ver)}). "
                        f"Upgrade git to {'.'.join(str(v) for v in min_ver)} or later."
                    )
                return _blocked_fn

            plan.append(RecoveryAction(blocked_description, _make_blocked_fn(detected_ver, _GIT_REFETCH_MIN_VERSION)))

    if refetch_viable:
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

    # (b) Branch ref reset — AFTER remove+refetch so the object store is clean first.
    try:
        corrupt_refs = detect_corrupt_branch_refs(repo_path)
    except subprocess.CalledProcessError:
        corrupt_refs = []

    def _make_ref_reset_fn(repo, branch, tip_sha):
        def _ref_reset_fn():
            try:
                subprocess.run(
                    [
                        "git", "-C", str(repo), "update-ref",
                        f"refs/heads/{branch}", tip_sha,
                    ],
                    check=True,
                )
            except subprocess.CalledProcessError as exc:
                logger.warning(
                    "Failed to reset branch ref %s to %s: %s",
                    branch,
                    tip_sha,
                    exc,
                )
                raise
        return _ref_reset_fn

    def _make_deferred_ref_reset_fn(repo, branch):
        def _deferred_ref_reset_fn():
            try:
                tip_sha = get_reflog_tip(repo, branch)
            except (subprocess.CalledProcessError, ValueError) as exc:
                logger.warning(
                    "No readable reflog entry for branch %s at execute time: %s",
                    branch,
                    exc,
                )
                raise
            try:
                subprocess.run(
                    [
                        "git", "-C", str(repo), "update-ref",
                        f"refs/heads/{branch}", tip_sha,
                    ],
                    check=True,
                )
            except subprocess.CalledProcessError as exc:
                logger.warning(
                    "Failed to reset branch ref %s to %s: %s",
                    branch,
                    tip_sha,
                    exc,
                )
                raise
        return _deferred_ref_reset_fn

    for branch_name, corrupt_sha in corrupt_refs:
        try:
            reflog_tip = get_reflog_tip(repo_path, branch_name)
            desc = (
                f"Reset branch ref '{branch_name}' from corrupt {corrupt_sha[:8]} "
                f"to reflog tip {reflog_tip}"
            )
            plan.append(
                RecoveryAction(desc, _make_ref_reset_fn(repo_path, branch_name, reflog_tip))
            )
        except (subprocess.CalledProcessError, ValueError) as exc:
            logger.warning(
                "Cannot find reflog tip for branch %s at plan time: %s — "
                "will retry at execution",
                branch_name,
                exc,
            )
            desc = (
                f"Reset branch ref '{branch_name}' from corrupt {corrupt_sha[:8]} "
                f"(reflog tip unavailable at plan time — will retry at execution)"
            )
            plan.append(
                RecoveryAction(desc, _make_deferred_ref_reset_fn(repo_path, branch_name))
            )

    # (c) Cache-tree rebuild — AFTER remove+refetch so the object store is clean first.
    try:
        index_poisoned = detect_poisoned_index(repo_path)
    except OSError:
        index_poisoned = False

    if index_poisoned:
        def _make_cache_tree_fn(repo):
            def _cache_tree_fn():
                try:
                    subprocess.run(
                        ["git", "-C", str(repo), "read-tree", "HEAD"],
                        check=True,
                    )
                except subprocess.CalledProcessError as exc:
                    logger.warning(
                        "git read-tree HEAD failed for %s: %s", repo, exc
                    )
                    raise
            return _cache_tree_fn

        plan.append(
            RecoveryAction(
                "Rebuild index cache-tree (git read-tree HEAD)",
                _make_cache_tree_fn(repo_path),
            )
        )

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
        if not verify_recovery_integrity(repo_path, plan):
            print(
                "Warning: Post-recovery integrity check found remaining issues. "
                "Check the log above for details."
            )
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
        if not verify_recovery_integrity(repo_path, plan):
            print(
                "Warning: Post-recovery integrity check found remaining issues. "
                "Check the log above for details."
            )
        print("Recovery complete.")
    else:
        print("Recovery aborted — no changes made.")


if __name__ == "__main__":
    main()
