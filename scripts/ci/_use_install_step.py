"""
MODULE: _use_install_step
GOAL: Drive a real ``git init`` + real pre-commit-hook install + a real
    ``git commit`` against a freshly built consumer install, and report which
    guards the ordinary commit path actually executed. Backs
    ``check_consumer_install.py --use-install`` (BP-900h-6).
BUSINESS CONTEXT: ``check_consumer_install.py`` (BP-900h-1) builds an install
    and inspects the resulting file tree, which can never observe a guard
    that only speaks when a commit is attempted. This module is the
    "use it, don't just build it" half: it performs the adopter's first
    ordinary commit — no skip flag, no environment override, no direct
    invocation of any guard script — and reads which guards ran from what
    the commit path itself printed, never from re-parsing the deployed
    registry (a derived record is identical on a wired and an unwired
    install, which is the exact defect this job exists to catch).
ARCHITECTURE: Small, independently-testable helpers composed by
    ``run_use_install_step``, the single entry point ``check_consumer_install.py``
    calls. ``_isolate_precommit_registry_for_scratch_fixture`` narrows the
    deployed ``.pre-commit-config.yaml`` to the self-healing hook plus any
    hook invoking ``check_identifier_uniqueness`` before installing the git
    hook — several judgment-tier hooks in this package's own manifest
    (``check-build-drift``, ``check-hook-trigger-reachability``) assume the
    self-hosted, fully-tracked leafcutter-ai checkout they were authored
    against and are known (KI-CG-017 and sibling entries) to misfire against
    a scratch project that tracks only its own first commit. Narrowing the
    registry to hooks relevant to a first-commit scenario is isolation from
    those already-filed, out-of-scope defects — never an exemption of the
    check under test, which the narrowing explicitly preserves whenever it
    is registered (mirrors the identical, independently-documented technique
    in ``unit_tests/portability/_ge122_build_commit_helpers.py``).

DOC_LINKS:
  - docs/acceptance-criteria/build_pipeline/BP-900-deployment-completeness/BP-900h-6.yaml
  - docs/known-issues/commit-guardian.md
  - scripts/ci/check_consumer_install.py

DECISION HISTORY:
  - 2026-08-31 [python-coder/BP-900h-6]: Created. Split out of
    check_consumer_install.py to keep that module's line count within the
    project's file-size convention. Implements the minimal slice needed for
    the "adopter's first commit completes, and the job's output carries a
    non-empty EXECUTED GUARDS record" contract; the mutation-test
    descriptors (empty-record failure reporting detail, adopter-hostile
    fixture, nothing-ran-vs-everything-passed distinguishability, ci.yml
    wiring) are this same AC's other test_spec descriptors and are deferred
    to a later increment of this AC.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

_SUBPROCESS_TIMEOUT_SECONDS = 180
_ALWAYS_KEEP_HOOK_IDS = {"ensure-precommit-config"}
_RELEVANT_ENTRY_SUBSTRING = "check_identifier_uniqueness"

_HOOK_BLOCK_PATTERN = re.compile(r"      - id: .*?\n(?:(?!      - id:).*\n)*")
_HOOK_ID_PATTERN = re.compile(r"      - id: (\S+)")

# pre-commit's classic dot-fill status line: "<name><dots><Status>".
_HOOK_STATUS_LINE_PATTERN = re.compile(
    r"^(?P<name>.+?)\.{3,}(?P<status>Passed|Failed|Skipped)\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class UseInstallResult:
    """Outcome of driving one real commit over a built consumer install.

    Attributes:
        commit_completed: True iff the ``git commit`` subprocess exited 0.
        executed_guard_names: Names of every hook the commit path reported
            as having actually run (Passed or Failed) — read from the
            commit's own captured output, never derived from the registry.
        failed_guard_names: Names of hooks the commit path reported as
            Failed, when the commit did not complete.
        commit_stdout: Raw stdout of the ``git commit`` invocation.
        commit_stderr: Raw stderr of the ``git commit`` invocation.
        exit_code: The exit code ``check_consumer_install.py`` should return
            for this step (0 = commit completed with >=1 guard executed;
            1 otherwise).
    """

    commit_completed: bool
    executed_guard_names: list[str] = field(default_factory=list)
    failed_guard_names: list[str] = field(default_factory=list)
    commit_stdout: str = ""
    commit_stderr: str = ""
    exit_code: int = 1


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a real ``git`` subprocess with ``args`` in ``cwd``.

    Wrapped per CLAUDE.md Rule 1 (external process I/O): a failure to even
    start the subprocess is reported as a synthetic non-zero
    ``CompletedProcess`` rather than propagating the exception, since every
    caller here already branches on ``.returncode``.

    Args:
        args: Arguments to pass to ``git`` (e.g. ``["init"]``).
        cwd: Working directory to run the subprocess in.

    Returns:
        The completed subprocess result.
    """
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: could not run 'git {' '.join(args)}': {exc}", file=sys.stderr)
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr=str(exc))


def _init_git_repo(target_dir: Path) -> None:
    """Initialise ``target_dir`` as a git repository with a usable local identity."""
    _git(["init"], cwd=target_dir)
    _git(["config", "user.email", "bp900h6-use-install@example.invalid"], cwd=target_dir)
    _git(["config", "user.name", "BP-900h-6 use-install step"], cwd=target_dir)


def _isolate_precommit_registry_for_scratch_fixture(target_dir: Path) -> None:
    """Narrow the deployed ``.pre-commit-config.yaml`` to a scratch-relevant whitelist.

    Keeps the always-present self-healing hook and any hook whose entry
    invokes ``check_identifier_uniqueness`` — see this module's ARCHITECTURE
    note for why the remaining judgment-tier hooks are isolated rather than
    exercised here. A no-op when the config file is absent.

    Args:
        target_dir: Root of the built consumer install.
    """
    config_path = target_dir / ".pre-commit-config.yaml"
    if not config_path.exists():
        return
    text = config_path.read_text(encoding="utf-8")

    first_match = _HOOK_BLOCK_PATTERN.search(text)
    header = text[: first_match.start()] if first_match else text

    kept_blocks: list[str] = []
    for match in _HOOK_BLOCK_PATTERN.finditer(text):
        block = match.group(0)
        id_match = _HOOK_ID_PATTERN.search(block)
        hook_id = id_match.group(1) if id_match else ""
        if hook_id in _ALWAYS_KEEP_HOOK_IDS or _RELEVANT_ENTRY_SUBSTRING in block:
            kept_blocks.append(block)

    config_path.write_text(header + "".join(kept_blocks), encoding="utf-8")


def _install_precommit_hook(target_dir: Path) -> None:
    """Run the real ``pre-commit install`` against the deployed config."""
    try:
        subprocess.run(
            ["pre-commit", "install"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: could not run 'pre-commit install' in {target_dir}: {exc}", file=sys.stderr)


def _stage_adopter_change(target_dir: Path) -> None:
    """Stage an ordinary, adopter-visible change: the project's own
    ``skills_config.json`` — never an artifact from a numbered namespace.
    """
    config_path = target_dir / "skills_config.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data["_bp900h6_adopter_change"] = True
    config_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    _git(["add", "skills_config.json"], cwd=target_dir)


def _attempt_commit(target_dir: Path) -> subprocess.CompletedProcess[str]:
    """Attempt a real, unmodified commit: no skip flag, no direct guard invocation."""
    return _git(
        ["commit", "-m", "chore: adopter first commit (BP-900h-6 use-install step)"],
        cwd=target_dir,
    )


def _parse_hook_status_lines(output: str) -> list[tuple[str, str]]:
    """Parse pre-commit's dot-fill status lines out of captured commit output.

    Args:
        output: Combined stdout+stderr of the ``git commit`` invocation.

    Returns:
        A list of ``(hook_name, status)`` pairs, in the order they appeared,
        for every line matching pre-commit's ``<name><dots><Status>`` shape
        (``Passed``, ``Failed``, or ``Skipped``).
    """
    return [
        (match.group("name").strip(), match.group("status"))
        for match in _HOOK_STATUS_LINE_PATTERN.finditer(output)
    ]


def run_use_install_step(target_dir: Path) -> UseInstallResult:
    """Drive the from-empty install's adopter first commit and report the result.

    Composes: git-init, registry isolation (see this module's ARCHITECTURE
    note), real ``pre-commit install``, staging an ordinary adopter change,
    and a real ``git commit`` — then parses which guards the commit path
    itself reported as having run.

    Args:
        target_dir: Root of an already-built consumer install (the caller is
            responsible for having run ``build.py`` against it first).

    Returns:
        The ``UseInstallResult`` describing what happened.
    """
    _init_git_repo(target_dir)
    _isolate_precommit_registry_for_scratch_fixture(target_dir)
    _install_precommit_hook(target_dir)
    _stage_adopter_change(target_dir)

    commit_result = _attempt_commit(target_dir)
    combined_output = commit_result.stdout + commit_result.stderr
    status_lines = _parse_hook_status_lines(combined_output)

    executed = [name for name, status in status_lines if status in ("Passed", "Failed")]
    failed = [name for name, status in status_lines if status == "Failed"]
    commit_completed = commit_result.returncode == 0

    exit_code = 0 if (commit_completed and executed) else 1

    return UseInstallResult(
        commit_completed=commit_completed,
        executed_guard_names=executed,
        failed_guard_names=failed,
        commit_stdout=commit_result.stdout,
        commit_stderr=commit_result.stderr,
        exit_code=exit_code,
    )


def format_executed_guards_line(result: UseInstallResult) -> str:
    """Render the "EXECUTED GUARDS: ..." report line for a UseInstallResult.

    Args:
        result: The result to report on.

    Returns:
        ``"EXECUTED GUARDS: (none)"`` when the record is empty, otherwise
        ``"EXECUTED GUARDS: <comma-separated hook names>"``.
    """
    if not result.executed_guard_names:
        return "EXECUTED GUARDS: (none)"
    return "EXECUTED GUARDS: " + ", ".join(result.executed_guard_names)


def run_use_install_and_report(target_dir: Path) -> int:
    """Drive BP-900h-6's real-commit step and print its report.

    The single entry point ``check_consumer_install.py --use-install`` calls
    — kept here (rather than inline in that script) so the caller stays a
    thin CLI wrapper, per this AC's "ONE ENTRY POINT FOR THE JOB AND ITS
    TEST" it_requirement.

    Args:
        target_dir: Root of an already-built consumer install.

    Returns:
        0 when the commit completed with a non-empty executed-guard record;
        1 when the commit failed, or completed with an empty record (per
        BP-900h-6's criteria: a commit that succeeded because nothing was
        wired must never be reported as a successful adopter experience).
    """
    result = run_use_install_step(target_dir)
    print(format_executed_guards_line(result))

    if not result.commit_completed:
        print(
            "CONSUMER INSTALL SIMULATION FAILED: the adopter's first commit did not "
            f"complete. Guard(s) that blocked: {', '.join(result.failed_guard_names) or '(unknown)'}\n"
            f"stdout:\n{result.commit_stdout}\nstderr:\n{result.commit_stderr}",
            file=sys.stderr,
        )
        return 1

    if not result.executed_guard_names:
        print(
            "CONSUMER INSTALL SIMULATION FAILED: the commit completed but no guard "
            "executed at all — an install in which nothing was wired must not be "
            "reported as a successful adopter experience.",
            file=sys.stderr,
        )
        return 1

    return 0
