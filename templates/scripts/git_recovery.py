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

    BO-1600d-3-ii (2026-07-06): Added unrecoverable-origin detection. After a
    single git fetch --refetch origin attempt, step_refetch_and_verify() probes
    each previously-zero-byte object SHA via git cat-file -e. If origin cannot
    supply the needed objects, the function returns {"status": "unrecoverable",
    "missing_objects": [...], "message": str}; the plan action raises
    UnrecoverableOriginError and execution halts immediately. No further deletions
    are made on the unrecoverable path — the store is left in its pre-halt state.

    BO-1600d-3-iv (2026-07-07): Hardened branch-ref reset to never use a hardcoded
    branch name. Added RecoveryError, _get_current_head_branch,
    _get_default_remote_branch, and _determine_branch_to_reset. Branch detection
    now follows a strict priority order: (a) the corrupt ref name itself, (b) the
    current HEAD branch, (c) the remote default branch. If none of the three sources
    yield an unambiguous branch name, RecoveryError is raised with an explicit report
    rather than guessing. The deferred-reset execution path uses this hierarchy so the
    safety invariant holds even when plan-time reflog lookup fails.
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


class UnrecoverableOriginError(RuntimeError):
    """Raised when origin cannot supply the objects needed to repair the store.

    The recovery step engine raises this after a single ``git fetch --refetch
    origin`` attempt fails to restore the required objects.  The ``result``
    attribute holds the structured unrecoverable payload so callers can display
    the names of the missing objects.

    Parameters
    ----------
    result:
        Structured dict with keys ``status`` (``"unrecoverable"``),
        ``missing_objects`` (list of SHA hex strings), and ``message`` (str).
    """

    def __init__(self, result: dict) -> None:
        self.result = result
        super().__init__(result.get("message", "origin cannot supply the needed objects"))


class RecoveryError(RuntimeError):
    """Raised when the affected branch cannot be determined unambiguously.

    Used by :func:`_determine_branch_to_reset` when none of the three detection
    sources (corrupt ref name, current HEAD branch, remote default branch) yield
    an unambiguous branch name.  Propagates through
    :func:`execute_recovery_plan` and :func:`main` so the operator sees a
    structured stop-and-report rather than a raw exception traceback.
    """


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


def _get_current_head_branch(repo_path: Path) -> str | None:
    """Return the current HEAD branch name, or None if HEAD is detached or on error.

    Runs ``git rev-parse --abbrev-ref HEAD``.  Returns ``None`` when the output
    is the literal string ``"HEAD"`` (indicating a detached HEAD state), when the
    subprocess exits non-zero, or when the output is empty.

    Pure subprocess I/O — no try/except on the pure parsing step (Rule 4).

    Parameters
    ----------
    repo_path:
        Absolute path to the git repository root.

    Returns
    -------
    str or None
        Branch name string when HEAD is on a named branch, ``None`` otherwise.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.warning(
            "git rev-parse --abbrev-ref HEAD failed for %s: %s", repo_path, exc
        )
        return None

    branch = result.stdout.strip()
    # "HEAD" means detached HEAD — not a usable named branch.
    if not branch or branch == "HEAD":
        return None
    return branch


def _get_default_remote_branch(repo_path: Path) -> str | None:
    """Return the repository's default remote branch name, or None if not determinable.

    Runs ``git symbolic-ref refs/remotes/origin/HEAD`` and extracts the branch
    name from output of the form ``refs/remotes/origin/<branch>``.  Returns
    ``None`` when the symbolic ref is not set, when the subprocess exits
    non-zero, or when the output cannot be parsed into a non-empty branch name.

    Parameters
    ----------
    repo_path:
        Absolute path to the git repository root.

    Returns
    -------
    str or None
        Default remote branch name, or ``None`` when not determinable.
    """
    try:
        result = subprocess.run(
            [
                "git", "-C", str(repo_path), "symbolic-ref",
                "refs/remotes/origin/HEAD",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.warning(
            "git symbolic-ref refs/remotes/origin/HEAD failed for %s: %s",
            repo_path,
            exc,
        )
        return None

    ref = result.stdout.strip()
    prefix = "refs/remotes/origin/"
    if ref.startswith(prefix):
        branch = ref[len(prefix):]
        if branch:
            return branch
    return None


def _determine_branch_to_reset(repo_path: Path, hint: str | None = None) -> str:
    """Determine the branch to reset without ever hardcoding or guessing a name.

    Detection order (AC BO-1600d-3-iv):

    1. ``hint`` — the branch name extracted from the corrupt ref itself.  When
       provided and non-empty, returned immediately without any subprocess call.
    2. Current HEAD branch — ``git rev-parse --abbrev-ref HEAD``.  Used only
       when HEAD is on a named branch (not detached).
    3. Remote default branch — ``git symbolic-ref refs/remotes/origin/HEAD``.

    If none of the three sources yield an unambiguous branch name,
    :exc:`RecoveryError` is raised.  The caller is responsible for logging and
    displaying the structured stop-and-report to the operator.

    Parameters
    ----------
    repo_path:
        Absolute path to the git repository root.
    hint:
        Branch name derived from the corrupt ref itself.  When non-empty,
        returned directly; no subprocess calls are made.

    Returns
    -------
    str
        The unambiguous branch name to reset.

    Raises
    ------
    RecoveryError
        When the branch cannot be determined from any of the three sources.
        The message instructs the operator to inspect the repository manually
        rather than letting the engine guess.
    """
    if hint:
        return hint

    head_branch = _get_current_head_branch(repo_path)
    if head_branch:
        return head_branch

    default_branch = _get_default_remote_branch(repo_path)
    if default_branch:
        return default_branch

    raise RecoveryError(
        "Cannot identify affected branch unambiguously; stopping recovery rather "
        "than guessing. HEAD is detached or not a named branch and no remote "
        "default branch is configured. Inspect the repository manually and run "
        "'git update-ref refs/heads/<branch> <sha>' directly."
    )


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


def _sha_from_object_path(obj_path: Path) -> str:
    """Extract the full 40-character SHA from a loose git object file path.

    Combines the two-character parent directory name (first two hex digits of
    the SHA) with the 38-character filename (remaining 38 hex digits) to form
    the complete 40-character object SHA.

    Pure function — no I/O, no try/except.

    Parameters
    ----------
    obj_path:
        Path of the form ``.../.git/objects/<2-char>/<38-char>``.

    Returns
    -------
    str
        Full 40-character hex SHA-1 string.
    """
    return obj_path.parent.name + obj_path.name


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
        msg = f"Cannot parse git version from output: {raw!r}; expected at least major.minor"
        raise ValueError(msg)

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
        except subprocess.CalledProcessError:
            continue
        else:
            return sha

    msg = f"No readable reflog entry found for branch {branch_name!r} in {repo_path}"
    raise ValueError(msg)


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


def check_object_present(repo_path: Path, sha: str) -> bool:
    """Return True if the object identified by *sha* is accessible in the store.

    Probes with ``git cat-file -e <sha>``, which exits 0 when the object exists
    and is readable, non-zero otherwise.  Never writes to disk.

    Parameters
    ----------
    repo_path:
        Absolute path to the git repository root.
    sha:
        40-character hex SHA-1 (or any prefix accepted by git).

    Returns
    -------
    bool
        ``True`` when the object is present and readable; ``False`` otherwise.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "cat-file", "-e", sha],
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        logger.warning("OS error checking object %s in %s: %s", sha, repo_path, exc)
        return False
    else:
        return result.returncode == 0


def step_refetch_and_verify(repo_path: Path, required_sha_list: list) -> dict:
    """Run a single ``git fetch --refetch origin`` then verify required objects.

    Performs exactly **one** fetch attempt — no retry loop.  After the fetch,
    probes each SHA in *required_sha_list* with :func:`check_object_present`.
    Returns an ``"unrecoverable"`` payload when origin could not supply all
    required objects; returns ``"ok"`` otherwise.

    Does NOT delete any objects at any point — the store state before the call
    is preserved when returning ``"unrecoverable"``.

    Parameters
    ----------
    repo_path:
        Absolute path to the git repository root.
    required_sha_list:
        List of 40-character SHA-1 hex strings to verify after the fetch.
        Pass an empty list to perform the fetch without object verification.

    Returns
    -------
    dict
        ``{"status": "ok"}`` when all required objects are accessible after
        the fetch, or ``{"status": "unrecoverable", "missing_objects": [...],
        "message": str}`` when origin could not supply one or more objects.

    Raises
    ------
    subprocess.CalledProcessError
        Re-raised (after logging at WARNING) if ``git fetch --refetch`` exits
        non-zero.
    """
    try:
        subprocess.run(
            ["git", "-C", str(repo_path), "fetch", "--refetch", "origin"],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.warning("git fetch --refetch failed for %s: %s", repo_path, exc)
        raise

    # Single pass — no retry loop.
    still_missing = [
        sha for sha in required_sha_list
        if not check_object_present(repo_path, sha)
    ]

    if still_missing:
        missing_str = ", ".join(still_missing)
        msg = (
            f"Recovery unrecoverable: origin did not supply {len(still_missing)} "
            f"required object(s) after re-fetch: {missing_str}. "
            "Cannot restore from origin — manual intervention required."
        )
        logger.warning("step_refetch_and_verify: %s", msg)
        return {
            "status": "unrecoverable",
            "missing_objects": still_missing,
            "message": msg,
        }

    return {"status": "ok"}


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

    # Collect SHAs of zero-byte objects at plan time so the refetch step can
    # verify them after the fetch (before files are removed by the delete step).
    zero_byte_shas: list = []

    zero_byte = detect_zero_byte_objects(repo_path)
    if zero_byte:
        if refetch_viable:
            # Capture SHA hashes now — the delete step will remove the files,
            # so we must extract them before execution begins.
            zero_byte_shas = [_sha_from_object_path(p) for p in zero_byte]
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
                    ver_str = ".".join(str(v) for v in ver)
                    min_str = ".".join(str(v) for v in min_ver)
                    msg = (
                        f"Recovery blocked: installed git {ver_str} does not support "
                        f"fetch --refetch (minimum required: {min_str}). "
                        f"Upgrade git to {min_str} or later."
                    )
                    raise RuntimeError(msg)
                return _blocked_fn

            plan.append(RecoveryAction(blocked_description, _make_blocked_fn(detected_ver, _GIT_REFETCH_MIN_VERSION)))

    if refetch_viable:
        # After the fetch, step_refetch_and_verify checks whether the previously-
        # zero-byte objects are now accessible.  If origin cannot supply them,
        # UnrecoverableOriginError is raised — no retry, no further deletion.
        def _make_refetch_and_verify_fn(repo, sha_list):
            def _refetch_and_verify_fn():
                result = step_refetch_and_verify(repo, sha_list)
                if result["status"] == "unrecoverable":
                    raise UnrecoverableOriginError(result)
            return _refetch_and_verify_fn

        plan.append(
            RecoveryAction(
                "Re-fetch objects from origin",
                _make_refetch_and_verify_fn(repo_path, zero_byte_shas),
            )
        )

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
            # Re-derive the target branch through the detection hierarchy at
            # execution time.  ``branch`` captured in the closure is always the
            # name from the corrupt ref, so _determine_branch_to_reset returns
            # it immediately as the unambiguous hint.  This call is the explicit
            # safeguard that prevents hardcoded fallbacks — if the hint were
            # somehow empty, RecoveryError would propagate up rather than
            # guessing "main" or "master".
            resolved_branch = _determine_branch_to_reset(repo, hint=branch)
            try:
                tip_sha = get_reflog_tip(repo, resolved_branch)
            except (subprocess.CalledProcessError, ValueError) as exc:
                logger.warning(
                    "No readable reflog entry for branch %s at execute time: %s",
                    resolved_branch,
                    exc,
                )
                raise
            try:
                subprocess.run(
                    [
                        "git", "-C", str(repo), "update-ref",
                        f"refs/heads/{resolved_branch}", tip_sha,
                    ],
                    check=True,
                )
            except subprocess.CalledProcessError as exc:
                logger.warning(
                    "Failed to reset branch ref %s to %s: %s",
                    resolved_branch,
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


def detect_shallow_or_bare_repo(repo_path: Path) -> tuple:
    """Detect whether the repository is a shallow or bare clone.

    Shallow detection is performed in the following order:

    1. Check whether ``.git/shallow`` exists in *repo_path*. Its mere presence
       indicates a shallow clone (no ``try/except`` — pure filesystem probe,
       per Rule 4).
    2. Run ``git -C <repo> rev-parse --is-shallow-repository``; if it outputs
       ``"true"``, the repository is shallow.

    Bare detection:
    - Run ``git -C <repo> rev-parse --is-bare-repository``; if it outputs
      ``"true"``, the repository is a bare clone (no working tree).

    Subprocess failures (command not found, not a git repo) are logged at
    WARNING level and treated as "not shallow / not bare" so the main flow
    continues and surfaces a clearer diagnostic on the next operation.

    Parameters
    ----------
    repo_path:
        Absolute path to the git repository root (or the bare repository
        directory itself).

    Returns
    -------
    tuple[bool, str]
        ``(True, reason)`` when the repository is shallow or bare, where
        *reason* is a human-readable explanation of why recovery is refused.
        ``(False, "")`` when neither condition is detected.
    """
    # Rule 4: pure filesystem existence probe — no try/except.
    shallow_file = repo_path / ".git" / "shallow"
    if shallow_file.exists():
        return (
            True,
            f"Repository at {repo_path} is a shallow clone (.git/shallow marker is present).",
        )

    # Shallow probe via git command — Rule 1/2/3: wrap subprocess in specific try/except.
    try:
        shallow_result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "--is-shallow-repository"],
            capture_output=True,
            text=True,
            check=True,
        )
        if shallow_result.stdout.strip() == "true":
            return (
                True,
                (
                    f"Repository at {repo_path} is a shallow clone "
                    "(git rev-parse --is-shallow-repository reports true)."
                ),
            )
    except subprocess.CalledProcessError as exc:
        logger.warning(
            "git rev-parse --is-shallow-repository failed for %s: %s", repo_path, exc
        )
    except OSError as exc:
        logger.warning(
            "OS error running git rev-parse --is-shallow-repository for %s: %s",
            repo_path,
            exc,
        )

    # Bare-repository probe — Rule 1/2/3: wrap subprocess in specific try/except.
    try:
        bare_result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "--is-bare-repository"],
            capture_output=True,
            text=True,
            check=True,
        )
        if bare_result.stdout.strip() == "true":
            return (
                True,
                f"Repository at {repo_path} is a bare clone (no working tree).",
            )
    except subprocess.CalledProcessError as exc:
        logger.warning(
            "git rev-parse --is-bare-repository failed for %s: %s", repo_path, exc
        )
    except OSError as exc:
        logger.warning(
            "OS error running git rev-parse --is-bare-repository for %s: %s",
            repo_path,
            exc,
        )

    return (False, "")


def _report_unrecoverable(result: dict) -> None:
    """Print a structured unrecoverable-origin report to stdout.

    Called by :func:`main` when :func:`execute_recovery_plan` raises
    :exc:`UnrecoverableOriginError`.  Formats the result dict into a
    human-readable message naming the objects that could not be restored from
    origin so the operator knows exactly which SHAs require manual recovery.

    Parameters
    ----------
    result:
        Structured dict from :func:`step_refetch_and_verify` with keys
        ``status``, ``missing_objects``, and ``message``.
    """
    print("\nRecovery halted — origin cannot supply the needed objects.")
    print(result.get("message", "No additional details available."))
    missing = result.get("missing_objects", [])
    if missing:
        print(f"\nObjects that could not be restored from origin ({len(missing)}):")
        for sha in missing:
            print(f"  {sha}")
    print(
        "\nThe object store is preserved in its current state. "
        "Manual intervention is required to restore the missing objects."
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

    # Shallow/bare clone guard — pre-plan check, fires before any repair action
    # (AC BO-1600d-3-iii).  No object removal, no ref reset, no index rebuild
    # may occur before this guard returns clean.
    is_unsupported, unsupported_reason = detect_shallow_or_bare_repo(repo_path)
    if is_unsupported:
        print(f"Recovery refused: {unsupported_reason}")
        print("This recovery does not support shallow or bare clones.")
        return

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
        try:
            execute_recovery_plan(plan)
        except UnrecoverableOriginError as exc:
            _report_unrecoverable(exc.result)
            return
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
        try:
            execute_recovery_plan(plan)
        except UnrecoverableOriginError as exc:
            _report_unrecoverable(exc.result)
            return
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
