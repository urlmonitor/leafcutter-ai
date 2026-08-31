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
import uuid
from dataclasses import dataclass, field
from pathlib import Path

_SUBPROCESS_TIMEOUT_SECONDS = 180
_ALWAYS_KEEP_HOOK_IDS = {"ensure-precommit-config"}
_RELEVANT_ENTRY_SUBSTRING = "check_identifier_uniqueness"

_HOOK_BLOCK_PATTERN = re.compile(r"      - id: .*?\n(?:(?!      - id:).*\n)*")
_HOOK_ID_PATTERN = re.compile(r"      - id: (\S+)")
_HOOK_NAME_LINE_PATTERN = re.compile(r"^        name: (.+)$", re.MULTILINE)

# pre-commit's classic dot-fill status line: "<name><dots><Status>".
_HOOK_STATUS_LINE_PATTERN = re.compile(
    r"^(?P<name>.+?)\.{3,}(?P<status>Passed|Failed|Skipped)\s*$",
    re.MULTILINE,
)

# Applied to every guard the scratch-fixture whitelist (see
# _isolate_precommit_registry_for_scratch_fixture's ARCHITECTURE note) drops
# before the commit is attempted. Shared rather than per-guard because the
# withholding mechanism itself is uniform (a single whitelist test), but
# still recorded individually against EVERY withheld guard id — BP-900h-6-ii
# requires each withheld guard to be named "together with the recorded
# reason it was withheld", not merely a footnote about the mechanism.
_WITHHELD_REASON = (
    "narrowed out of the scratch-fixture's pre-commit registry before the "
    "commit was attempted: several judgment-tier hooks in this package's own "
    "manifest assume the self-hosted, fully-tracked leafcutter-ai checkout "
    "they were authored against and are documented (KI-CG-017 and sibling "
    "entries in docs/known-issues/commit-guardian.md) to misfire against a "
    "scratch project that tracks only its own first commit"
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
        deployed_guard_ids: Every hook id present in the registry BEFORE this
            step's own narrowing — the population an adopter would actually
            face (BP-900h-6-ii's "deployed count", taken from the
            pre-narrowing registry, never the post-narrowing one).
        executed_guard_ids: Hook ids (not display names) among
            ``deployed_guard_ids`` that the commit path reported as having
            run (Passed or Failed).
        withheld_guard_ids: Hook ids this step's own narrowing removed from
            the registry before the commit was attempted.
        withheld_guard_reasons: Maps every id in ``withheld_guard_ids`` to
            the recorded reason it was withheld.
        unaccounted_guard_ids: Deployed ids that ended up in neither
            ``executed_guard_ids`` nor ``withheld_guard_ids`` — the
            silent-narrowing failure state BP-900h-6-ii exists to catch.
        commit_stdout: Raw stdout of the ``git commit`` invocation.
        commit_stderr: Raw stderr of the ``git commit`` invocation.
        exit_code: The exit code ``check_consumer_install.py`` should return
            for this step (0 = commit completed with >=1 guard executed and
            nothing unaccounted; 1 otherwise).
    """

    commit_completed: bool
    executed_guard_names: list[str] = field(default_factory=list)
    failed_guard_names: list[str] = field(default_factory=list)
    deployed_guard_ids: list[str] = field(default_factory=list)
    executed_guard_ids: list[str] = field(default_factory=list)
    withheld_guard_ids: list[str] = field(default_factory=list)
    withheld_guard_reasons: dict[str, str] = field(default_factory=dict)
    unaccounted_guard_ids: list[str] = field(default_factory=list)
    commit_stdout: str = ""
    commit_stderr: str = ""
    exit_code: int = 1


def check_target_entitlement(target_dir: Path) -> str | None:
    """Refuse targets this step is not entitled to destroy, before any mutation.

    Entitlement is about ownership, not emptiness (see this module's
    ARCHITECTURE note and BP-900h-6-i's notes: an emptiness rule would wrongly
    refuse the CI job's own target, ``github.workspace``, which already holds
    a checkout directory but is itself not part of any git working tree).
    A target is UNENTITLED when it is already inside an existing git working
    tree that holds at least one commit this step did not create — a stand-in
    for a developer's real working tree or the shared install tree the
    workspace's worktrees resolve configuration through. A target that is not
    inside any git working tree at all (the disposable, freshly-built case),
    or one whose git history this step itself is about to create, is
    entitled.

    Args:
        target_dir: The directory the use-install step is about to mutate.

    Returns:
        ``None`` when the target is entitled. Otherwise a human-readable
        description of the failed entitlement condition (never including the
        target path itself — callers are expected to name the path
        alongside this description).
    """
    try:
        inside_probe = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(
            f"WARNING: could not probe git work-tree status for {target_dir}: {exc}",
            file=sys.stderr,
        )
        return "could not determine whether the target is already inside a git working tree"

    if inside_probe.returncode != 0 or inside_probe.stdout.strip() != "true":
        # Not inside any existing git working tree at all -> entitled. This
        # is the branch that keeps github.workspace (which contains the
        # leafcutter-ai/ checkout as a SUBDIRECTORY, but is not itself part
        # of any git working tree) entitled, per the AC's "not an emptiness
        # rule" constraint.
        return None

    try:
        head_probe = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(
            f"WARNING: could not probe git HEAD for {target_dir}: {exc}",
            file=sys.stderr,
        )
        return "could not determine whether the target's existing git working tree already holds a commit"

    if head_probe.returncode == 0:
        return (
            "target is already inside a git working tree holding a pre-existing "
            "commit this step did not create"
        )

    return None


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


@dataclass(frozen=True)
class _RegistryNarrowingReport:
    """What the scratch-fixture narrowing found and did, captured from the
    registry BEFORE narrowing (BP-900h-6-ii's "deployed count" must come from
    here, never from re-reading the file after narrowing).
    """

    deployed_guard_ids: list[str] = field(default_factory=list)
    withheld_guard_ids: list[str] = field(default_factory=list)
    id_to_name: dict[str, str] = field(default_factory=dict)


def _hook_id_and_name(block: str) -> tuple[str, str]:
    """Extract a hook's ``id:`` and display ``name:`` from one registry block.

    Falls back to the id itself when no ``name:`` line is found, so a
    guard is always nameable even against a malformed or hand-edited entry.
    """
    id_match = _HOOK_ID_PATTERN.search(block)
    hook_id = id_match.group(1) if id_match else ""
    name_match = _HOOK_NAME_LINE_PATTERN.search(block)
    raw_name = name_match.group(1) if name_match else hook_id
    # Strip a trailing YAML comment (e.g. "  # @package-managed"), mirroring
    # how pre-commit itself displays the name with no comment suffix.
    name = raw_name.split("  #", 1)[0].strip()
    return hook_id, name or hook_id


def _isolate_precommit_registry_for_scratch_fixture(target_dir: Path) -> _RegistryNarrowingReport:
    """Narrow the deployed ``.pre-commit-config.yaml`` to a scratch-relevant whitelist.

    Keeps the always-present self-healing hook and any hook whose entry
    invokes ``check_identifier_uniqueness`` — see this module's ARCHITECTURE
    note for why the remaining judgment-tier hooks are isolated rather than
    exercised here. A no-op when the config file is absent.

    Args:
        target_dir: Root of the built consumer install.

    Returns:
        A ``_RegistryNarrowingReport`` describing the registry as it stood
        BEFORE narrowing and which ids this call withheld from it — the
        source of truth ``run_use_install_step`` uses for BP-900h-6-ii's
        deployed-count and withheld-guard accounting.
    """
    config_path = target_dir / ".pre-commit-config.yaml"
    if not config_path.exists():
        return _RegistryNarrowingReport()
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"WARNING: could not read {config_path}: {exc}", file=sys.stderr)
        return _RegistryNarrowingReport()

    first_match = _HOOK_BLOCK_PATTERN.search(text)
    header = text[: first_match.start()] if first_match else text

    deployed_ids: list[str] = []
    kept_ids: list[str] = []
    kept_blocks: list[str] = []
    id_to_name: dict[str, str] = {}
    for match in _HOOK_BLOCK_PATTERN.finditer(text):
        block = match.group(0)
        hook_id, hook_name = _hook_id_and_name(block)
        if not hook_id:
            continue
        deployed_ids.append(hook_id)
        id_to_name[hook_id] = hook_name
        if hook_id in _ALWAYS_KEEP_HOOK_IDS or _RELEVANT_ENTRY_SUBSTRING in block:
            kept_blocks.append(block)
            kept_ids.append(hook_id)

    try:
        _write_registry_inside_target_root(config_path, target_dir, header + "".join(kept_blocks))
    except OSError as exc:
        print(f"WARNING: could not rewrite {config_path}: {exc}", file=sys.stderr)
        # The write failed, so the registry on disk is unchanged from what
        # was just read — nothing was actually withheld by THIS call.
        return _RegistryNarrowingReport(deployed_ids, [], id_to_name)

    withheld_ids = [hook_id for hook_id in deployed_ids if hook_id not in kept_ids]
    return _RegistryNarrowingReport(deployed_ids, withheld_ids, id_to_name)


def _write_registry_inside_target_root(config_path: Path, target_dir: Path, content: str) -> None:
    """Write ``content`` to ``config_path`` without ever writing through a
    symlink that resolves outside ``target_dir`` (BP-900h-6-i symlink-safety
    clause).

    When ``config_path`` is a symlink resolving outside ``target_dir`` — the
    shape of a deployed registry that several installs share via one build
    artifact — the link is replaced with a private regular file inside the
    target before writing, so the shared artifact the link used to resolve to
    is left byte-identical. A symlink resolving INSIDE the target root, or a
    plain regular file, is written to directly.

    Args:
        config_path: The (possibly symlinked) registry path to write.
        target_dir: Root of the target the write must stay confined to.
        content: The new registry content.
    """
    if config_path.is_symlink():
        resolved_link = config_path.resolve()
        resolved_root = target_dir.resolve()
        if not resolved_link.is_relative_to(resolved_root):
            config_path.unlink()
    config_path.write_text(content, encoding="utf-8")


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

    The marker value is a fresh token on every call (never a static flag) so
    a repeat invocation against an already-committed target always has a
    genuine, new change to stage. A static flag value made a second run
    against an unchanged target stage nothing — ``git commit`` then refused
    before pre-commit ever ran, and the resulting "no guard reported having
    run" state was previously misreported as an unnamed blocker (BP-900h-6-i
    review finding: an idempotent re-run must not invent a blocker).
    """
    config_path = target_dir / "skills_config.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    except (OSError, json.JSONDecodeError) as exc:
        print(f"WARNING: could not read {config_path}: {exc}", file=sys.stderr)
        data = {}
    if not isinstance(data, dict):
        data = {}
    data["_bp900h6_adopter_change"] = uuid.uuid4().hex
    try:
        config_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"WARNING: could not write {config_path}: {exc}", file=sys.stderr)
        return
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
    itself reported as having run, and reconciles that against the FULL
    deployed guard population captured before narrowing (BP-900h-6-ii).

    Args:
        target_dir: Root of an already-built consumer install (the caller is
            responsible for having run ``build.py`` against it first).

    Returns:
        The ``UseInstallResult`` describing what happened.
    """
    _init_git_repo(target_dir)
    narrowing_report = _isolate_precommit_registry_for_scratch_fixture(target_dir)
    _install_precommit_hook(target_dir)
    _stage_adopter_change(target_dir)

    commit_result = _attempt_commit(target_dir)
    combined_output = commit_result.stdout + commit_result.stderr
    status_lines = _parse_hook_status_lines(combined_output)

    executed_names = [name for name, status in status_lines if status in ("Passed", "Failed")]
    failed_names = [name for name, status in status_lines if status == "Failed"]
    commit_completed = commit_result.returncode == 0

    name_to_id = {name: hook_id for hook_id, name in narrowing_report.id_to_name.items()}
    executed_ids = [name_to_id[name] for name in executed_names if name in name_to_id]

    withheld_ids = narrowing_report.withheld_guard_ids
    withheld_reasons = {hook_id: _WITHHELD_REASON for hook_id in withheld_ids}
    accounted_ids = set(executed_ids) | set(withheld_ids)
    unaccounted_ids = [
        hook_id for hook_id in narrowing_report.deployed_guard_ids if hook_id not in accounted_ids
    ]

    exit_code = 0 if (commit_completed and executed_ids and not unaccounted_ids) else 1

    return UseInstallResult(
        commit_completed=commit_completed,
        executed_guard_names=executed_names,
        failed_guard_names=failed_names,
        deployed_guard_ids=narrowing_report.deployed_guard_ids,
        executed_guard_ids=executed_ids,
        withheld_guard_ids=withheld_ids,
        withheld_guard_reasons=withheld_reasons,
        unaccounted_guard_ids=unaccounted_ids,
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
        ``"EXECUTED GUARDS: <comma-separated hook ids>"``.
    """
    if not result.executed_guard_ids:
        return "EXECUTED GUARDS: (none)"
    return "EXECUTED GUARDS: " + ", ".join(result.executed_guard_ids)


def format_guard_accounting_report(result: UseInstallResult) -> str:
    """Render the full BP-900h-6-ii guard-population accounting block.

    Always states the deployed count (from BEFORE narrowing), names every
    executed and withheld guard by id, and — when any guard was withheld —
    prints the recorded reason against each one individually, so a
    narrowing can never be silent about what it dropped.

    Args:
        result: The result to report on.

    Returns:
        A multi-line report: ``DEPLOYED GUARDS``, ``EXECUTED GUARDS``,
        ``WITHHELD GUARDS`` (each on their own line), a
        ``WITHHELD GUARD REASONS`` block when anything was withheld, and an
        ``UNACCOUNTED GUARDS`` line when the accounting failed to place every
        deployed guard into one of the other two buckets.
    """
    lines = [
        f"DEPLOYED GUARDS: {len(result.deployed_guard_ids)}",
        format_executed_guards_line(result),
        "WITHHELD GUARDS: " + (", ".join(result.withheld_guard_ids) or "(none)"),
    ]
    if result.withheld_guard_ids:
        lines.append("WITHHELD GUARD REASONS:")
        lines.extend(
            f"  {guard_id}: {result.withheld_guard_reasons.get(guard_id, '(no reason recorded)')}"
            for guard_id in result.withheld_guard_ids
        )
    if result.unaccounted_guard_ids:
        lines.append("UNACCOUNTED GUARDS: " + ", ".join(result.unaccounted_guard_ids))
    return "\n".join(lines)


def _format_verdict_line(result: UseInstallResult) -> str:
    """Render the pass verdict line — qualified when anything was withheld.

    A narrowed run (``withheld_guard_ids`` non-empty) must never emit the
    same verdict text as a run in which nothing was withheld (BP-900h-6-ii):
    this is the only line that says "QUALIFIED", and it is only ever printed
    when at least one deployed guard was withheld.
    """
    deployed_count = len(result.deployed_guard_ids)
    if result.withheld_guard_ids:
        return (
            "CONSUMER INSTALL SIMULATION QUALIFIED PASS: "
            f"{len(result.executed_guard_ids)} of {deployed_count} deployed guards "
            f"executed; {len(result.withheld_guard_ids)} withheld (see WITHHELD GUARDS "
            "/ WITHHELD GUARD REASONS above) — this is NOT the same guarantee as a run "
            "in which nothing was withheld."
        )
    return (
        "CONSUMER INSTALL SIMULATION PASS: nothing withheld; all "
        f"{deployed_count} deployed guards executed."
    )


def run_use_install_and_report(target_dir: Path) -> int:
    """Drive BP-900h-6's real-commit step and print its report.

    The single entry point ``check_consumer_install.py --use-install`` calls
    — kept here (rather than inline in that script) so the caller stays a
    thin CLI wrapper, per this AC's "ONE ENTRY POINT FOR THE JOB AND ITS
    TEST" it_requirement.

    Args:
        target_dir: Root of an already-built consumer install.

    Returns:
        0 when the commit completed, at least one guard executed, and every
        deployed guard is accounted for (executed or withheld-with-reason);
        1 when the target is refused for lacking entitlement, the commit
        failed, the executed-guard record was empty, or any deployed guard
        was left unaccounted for (per BP-900h-6 and BP-900h-6-ii's criteria).
    """
    entitlement_violation = check_target_entitlement(target_dir)
    if entitlement_violation is not None:
        # Refused BEFORE any mutation (BP-900h-6-i): no git init, no registry
        # rewrite, no commit. Printed in a shape distinct from both the
        # success report ("EXECUTED GUARDS: ...") and the post-mutation
        # failure report ("CONSUMER INSTALL SIMULATION FAILED: ...") below,
        # per the AC's "a refusal is not reported in the same shape as a
        # successful adopter experience" clause.
        print(
            f"CONSUMER INSTALL SIMULATION REFUSED: target {target_dir} is not "
            f"entitled to the use-install step's destructive actions: "
            f"{entitlement_violation}.",
            file=sys.stderr,
        )
        return 1

    result = run_use_install_step(target_dir)
    print(format_guard_accounting_report(result))

    if not result.commit_completed:
        if result.failed_guard_names:
            blocked_desc = ", ".join(result.failed_guard_names)
        else:
            blocked_desc = (
                "none — no guard reported having run, so this step cannot name "
                "which one blocked the commit"
            )
        print(
            "CONSUMER INSTALL SIMULATION FAILED: the adopter's first commit did not "
            f"complete. Guard(s) that blocked: {blocked_desc}\n"
            f"stdout:\n{result.commit_stdout}\nstderr:\n{result.commit_stderr}",
            file=sys.stderr,
        )
        return 1

    if result.unaccounted_guard_ids:
        print(
            "CONSUMER INSTALL SIMULATION FAILED: "
            f"{len(result.unaccounted_guard_ids)} deployed guard(s) are unaccounted "
            "for — neither executed nor withheld with a recorded reason: "
            f"{', '.join(result.unaccounted_guard_ids)}. A narrowing must never be "
            "silent about what it drops.",
            file=sys.stderr,
        )
        return 1

    if not result.executed_guard_ids:
        print(
            "CONSUMER INSTALL SIMULATION FAILED: the commit completed but no guard "
            "executed at all — an install in which nothing was wired must not be "
            "reported as a successful adopter experience.",
            file=sys.stderr,
        )
        return 1

    print(_format_verdict_line(result))
    return 0
