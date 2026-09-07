"""
MODULE: _authored_change
GOAL: Derive, in exactly one place, the "authored change set" that a
    self-deriving commit-guardian check should judge its verdict against —
    the content that differs from EVERY state the current commit is built
    on, so work carried in from another line of development (e.g. the whole
    incoming branch of a merge) is excluded.
BUSINESS CONTEXT: Before this module, ``check_contract_shrinking.py`` and
    ``check_doc_frontmatter.py`` (via ``frontmatter_validators.py``) each
    independently hand-implemented the identical "diff differs from both
    merge parents" idiom (``_merge_scoped_paths`` / ``merge_scoped_md_paths``)
    and, on top of that, each independently fell back to the UNSCOPED
    (whole-staged-tree) diff whenever the derivation could not be computed —
    the exact could-not-check-vs-widen anti-pattern GE-120e-1's Implementation
    Notes forbid ("A git failure must NOT degrade to using the whole staged
    tree"). A large mainline merge into a working branch whose own change set
    touched none of the carried-in files could therefore trip a check on
    content its author never wrote. This module is the single shared source
    both checks now consume, so "what did the author change" is answered
    identically for both (AC GE-120e-1's last clause), and it reports a
    could-not-check outcome IN BAND (``could_not_check=True`` plus ``error``)
    — a could-not-check outcome in GE-120a-1's vocabulary — rather than a
    widened change set whenever the derivation genuinely cannot be computed.

    Named ``_authored_change.py`` / ``get_authored_change()`` /
    ``AuthoredChange`` (not ``_resolve_change_set.py`` / ``get_change_set()``
    / ``ChangeSet``, this module's original names) to honour the contract
    ``unit_tests/portability/test_ge_120e_4_i.py`` (ticket 36, GE-120e-4-i)
    pre-established for GE-120e-1's implementer to "honour or update" — see
    that file's module docstring, "CONTRACT THIS TEST FILE ESTABLISHES".
    GE-120e-4 (ticket 35, still ``todo`` as of this rename) is expected to
    extend ``get_authored_change()`` to also discover a commit's parent(s)
    from the commit itself and to consult ``REVERT_HEAD`` / ``CHERRY_PICK_HEAD``
    in addition to ``MERGE_HEAD`` — none of that semantics is implemented
    here; this module still derives only from ``HEAD`` and, when present,
    ``MERGE_HEAD``.
ARCHITECTURE: A leaf module with no imports beyond the standard library, in
    the same family as ``_resolve_root.py`` (one shared facility, many
    importers) but solving a different problem: ``_resolve_root.py`` resolves
    a PREREQUISITE (the project root); this module derives the CHANGE SET
    itself. ``get_authored_change(cwd=None)`` returns a memoised
    ``AuthoredChange`` (one per resolved cwd per process — the pre-commit
    latency budget forbids one git invocation per consuming check) exposing
    ``paths``, ``states``, ``diff_text``, ``name_status``, ``could_not_check``,
    and ``error`` as plain data attributes (never callables — ticket 36's
    contract shapes this as data, not lazily-invoked accessors), so both
    known diff shapes (full text diff for the contract-shrinking scan,
    name-status for the frontmatter scan) are served from the one derivation,
    along with the provenance (``states``) a consumer needs to describe what
    it inspected. Every git call runs with an explicit ``cwd=`` argument
    rather than assuming ``<root>/.git`` exists as a directory, so this
    remains correct inside a linked git worktree, where there is no such
    directory.

    SEMANTIC CHOICE FORCED BY THE ATTRIBUTE (NOT METHOD) SHAPE: the prior
    revision of this module exposed ``.text_diff()`` / ``.name_status()`` as
    lazily-derived, memoised accessors, so a consumer that only ever read one
    shape (e.g. ``check_doc_frontmatter.py`` reading only name-status) paid
    for only one extra ``git`` invocation beyond the paths probe. Ticket 36's
    contract instead declares ``diff_text`` / ``name_status`` as plain data
    fields, which this module satisfies by computing BOTH eagerly inside
    ``get_authored_change()`` — every call now issues the paths probe plus
    both diff invocations (three ``git`` calls total on the merge path, two
    on the ordinary path), regardless of which shape the caller actually
    reads. This trades a small, bounded amount of latency (still one
    derivation per resolved ``cwd`` per process, thanks to memoisation) for
    honouring the cross-ticket contract literally. If this cost proves
    material against the ~500-file latency budget, a future revision could
    reintroduce ``functools.cached_property``-backed attributes (still
    attribute *access*, not method *calls*) to restore laziness without
    reopening the naming/shape question this revision closes.

DOC_LINKS:
  - docs/architecture/components/commit-guardian.md

DECISION HISTORY:
  - 2026-08-31 [python-coder/GE-120e-1, pr-reviewer remediation]: Renamed
    from ``_resolve_change_set.py`` (``get_change_set()`` / ``ChangeSet``,
    with ``base_ref``/``head_ref`` provenance and ``.text_diff()``/
    ``.name_status()`` as lazy methods returning ``None`` on could-not-check)
    to ``_authored_change.py`` (``get_authored_change()`` / ``AuthoredChange``,
    with a ``states`` list and ``diff_text``/``name_status`` as eager data
    attributes, plus in-band ``could_not_check``/``error`` instead of a
    ``None`` sentinel), to honour the contract
    ``unit_tests/portability/test_ge_120e_4_i.py`` (ticket 36) had already
    established for this exact module. No change to the underlying
    derivation logic (still ``HEAD``-only, or ``HEAD``+``MERGE_HEAD`` when a
    merge is in progress) — GE-120e-4's parent-discovery and
    REVERT_HEAD/CHERRY_PICK_HEAD extension is out of scope for this pass.
    (#EPIC-TrustThatAGreenCheckActuallyChecked/28)
  - 2026-08-31 [python-coder/GE-120e-1]: Created as ``_resolve_change_set.py``.
    Consolidates check_contract_shrinking.py's ``_merge_scoped_paths`` and
    frontmatter_validators.py's ``merge_scoped_md_paths`` (both already
    landed, independently, under GE-120e-1-i / GE-120e-3-ii) into one shared
    derivation, and fixes both checks' documented fall-back-to-unscoped-diff
    behaviour on git failure.
    (#EPIC-TrustThatAGreenCheckActuallyChecked/28)
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_GIT_TIMEOUT = 30

# One derivation per resolved cwd per process (latency budget: do not issue
# one git invocation per consuming check). Keyed by the string form of the
# resolved cwd rather than the process's single cwd, because a single test
# process (and, in principle, a single hook run with HOOK_TEST_* overrides)
# may legitimately ask about more than one working tree.
_CACHE: dict[str, "AuthoredChange"] = {}


@dataclass
class AuthoredChange:
    """The authored change set for one commit, plus the states it was derived against.

    Every field is a plain data attribute (never a method to call) per the
    contract ``unit_tests/portability/test_ge_120e_4_i.py`` established for
    this module. A failed derivation is reported IN BAND via
    ``could_not_check`` / ``error`` rather than by returning ``None`` —
    callers must check ``could_not_check`` before trusting the other fields.

    Attributes:
        diff_text: The full text diff (``git diff --cached``, scoped to
            ``states[-1]`` during a merge). Empty string when
            ``could_not_check`` is True or the change set is empty.
        name_status: ``(path, status)`` pairs from ``git diff --cached
            --name-status``, same scoping as ``diff_text``. Empty list when
            ``could_not_check`` is True or the change set is empty.
        paths: Repo-relative paths in scope. During a merge (``states``
            includes ``"MERGE_HEAD"``) these are the paths differing from
            ``MERGE_HEAD`` (the incoming branch) — i.e. NOT content carried
            in verbatim from the other line of development, whether that
            content is a genuine conflict resolution (differs from both
            parents) or the author's own earlier work on this branch
            (matches ``HEAD`` exactly but was never recorded on the incoming
            branch). Excluding only by ``MERGE_HEAD`` — rather than requiring
            a difference from BOTH parents — is what keeps AC GE-120e-1's
            "verdict on the author's own content is unchanged" clause true
            even when that content was committed before the merge began.
            Outside a merge, every staged path.
        states: The commit-ish(es) this change set was derived against, for
            provenance in a consumer's objection text — ``["HEAD"]`` on the
            ordinary (single-state) path, ``["HEAD", "MERGE_HEAD"]`` during a
            merge.
        could_not_check: ``True`` when the derivation itself failed (a git
            call errored, timed out, or exited non-zero) — never license to
            widen the scope to the whole staged tree.
        error: A short message describing what failed, when
            ``could_not_check`` is True; ``None`` otherwise.
    """

    diff_text: str
    name_status: list[tuple[str, str]]
    paths: list[str]
    states: list[str]
    could_not_check: bool
    error: str | None
    _cwd: Path = field(repr=False)


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess | None:
    """Run a git subcommand with ``cwd`` as the working directory.

    Never raises: an ``OSError`` or timeout is logged at WARNING and reported
    to the caller as ``None`` so a git failure degrades to a could-not-check
    outcome, never to a wider scan.

    Args:
        args: Arguments to append to ``git`` (e.g. ``["diff", "--cached"]``).
        cwd: Working directory the command is run in.

    Returns:
        The completed process, or ``None`` when the invocation could not be
        run or timed out.
    """
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("git %s failed in %s: %s", args, cwd, exc)
        return None


def _name_only(extra: list[str], cwd: Path) -> list[str] | None:
    """Return staged path names via ``git diff --cached -z --name-only``.

    ``-z`` is required, not cosmetic: without it git C-quotes any path
    holding a non-ASCII byte and whitespace-splitting the output tears a
    spaced path into two tokens, silently emptying the scope.

    Args:
        extra: Additional arguments appended to the command (e.g. a ref).
        cwd: Working directory the command is run in.

    Returns:
        Repo-relative path strings, or ``None`` when the git call failed or
        exited non-zero.
    """
    result = _run_git(["diff", "--cached", "-z", "--name-only", *extra], cwd)
    if result is None or result.returncode != 0:
        return None
    return [p for p in result.stdout.split("\0") if p]


def _parse_name_status(raw: str) -> list[tuple[str, str]]:
    """Parse ``git diff --cached --name-status`` output into ``(path, status)`` pairs.

    Args:
        raw: Raw stdout from the name-status invocation.

    Returns:
        list[tuple[str, str]]: ``(path, status)`` pairs, one per changed
        file, in the order git reported them.
    """
    parsed: list[tuple[str, str]] = []
    for line in raw.strip().splitlines():
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            parsed.append((parts[-1], parts[0]))
    return parsed


def _could_not_check(cwd: Path, error: str) -> AuthoredChange:
    """Build the in-band could-not-check ``AuthoredChange`` result.

    Args:
        cwd: The working directory the derivation was attempted against.
        error: A short description of what failed.

    Returns:
        An ``AuthoredChange`` with ``could_not_check=True`` and every other
        field empty — callers must check ``could_not_check`` before trusting
        ``paths`` / ``states`` / ``diff_text`` / ``name_status``.
    """
    return AuthoredChange(
        diff_text="",
        name_status=[],
        paths=[],
        states=[],
        could_not_check=True,
        error=error,
        _cwd=cwd,
    )


def _build_authored_change(
    paths: list[str], states: list[str], extra_args: list[str], cwd: Path,
) -> AuthoredChange:
    """Eagerly compute both diff shapes and assemble the ``AuthoredChange``.

    Args:
        paths: The already-derived path set (see ``_derive_authored_change``).
        states: The commit-ish(es) this derivation was computed against.
        extra_args: Extra ref arguments (e.g. ``["MERGE_HEAD"]``) applied to
            both the text-diff and name-status invocations, so both shapes
            are scoped identically to ``paths``.
        cwd: Working directory the commands are run in.

    Returns:
        The assembled ``AuthoredChange``, or a could-not-check result if
        either diff invocation failed.
    """
    diff_result = _run_git(["diff", "--cached", *extra_args], cwd)
    if diff_result is None:
        return _could_not_check(cwd, "git diff --cached failed while building the text diff")

    name_status_result = _run_git(["diff", "--cached", "--name-status", *extra_args], cwd)
    if name_status_result is None:
        return _could_not_check(
            cwd, "git diff --cached --name-status failed while building name-status",
        )

    return AuthoredChange(
        diff_text=diff_result.stdout,
        name_status=_parse_name_status(name_status_result.stdout),
        paths=paths,
        states=states,
        could_not_check=False,
        error=None,
        _cwd=cwd,
    )


def _derive_authored_change(cwd: Path) -> AuthoredChange:
    """Compute the ``AuthoredChange`` for *cwd*.

    Args:
        cwd: Working directory to derive the change set for.

    Returns:
        An ``AuthoredChange`` (scoped when a merge is in progress, otherwise
        covering every staged path), or a could-not-check result when the
        derivation could not be computed at all — the caller must treat this
        as a could-not-check outcome, never as license to use an unscoped
        diff.
    """
    merge_probe = _run_git(["rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd)
    if merge_probe is None:
        return _could_not_check(cwd, "git rev-parse --verify MERGE_HEAD failed or timed out")

    if merge_probe.returncode != 0:
        paths = _name_only([], cwd)
        if paths is None:
            return _could_not_check(cwd, "git diff --cached --name-only failed")
        return _build_authored_change(paths, ["HEAD"], [], cwd)

    # Paths differing from MERGE_HEAD (the incoming branch) are NOT carried
    # in verbatim from that other line of development -- whether they are a
    # genuine conflict resolution or the author's own earlier work on this
    # branch. Deliberately NOT intersected with "differs from HEAD" too: that
    # stricter form would also exclude the author's own already-committed
    # content (it matches HEAD exactly), which is precisely the carried-in-
    # work-only exclusion AC GE-120e-1 forbids over-applying to the author's
    # own work ("its verdict on the same commit's own content is unchanged").
    scoped_paths = _name_only(["MERGE_HEAD"], cwd)
    if scoped_paths is None:
        return _could_not_check(cwd, "git diff --cached --name-only MERGE_HEAD failed")
    return _build_authored_change(scoped_paths, ["HEAD", "MERGE_HEAD"], ["MERGE_HEAD"], cwd)


def get_authored_change(cwd: Path | None = None) -> AuthoredChange:
    """Return the authored change set for the commit staged in *cwd*.

    The single shared source every self-deriving commit-guardian check
    consumes in place of a private ``git diff --cached`` call. Memoised per
    resolved ``cwd`` for the lifetime of the process.

    Args:
        cwd: Working directory to derive the change set for. Defaults to the
            process's current working directory (the git working-tree root
            during a real pre-commit run).

    Returns:
        The ``AuthoredChange``. Check ``.could_not_check`` before trusting
        any other field — ``True`` means the derivation could not be
        computed (e.g. git is unreachable, or the merge-parent side of the
        diff could not be resolved), and callers must NOT fall back to an
        unscoped diff on receiving it.
    """
    resolved_cwd = Path(cwd) if cwd is not None else Path.cwd()
    cache_key = str(resolved_cwd)
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    result = _derive_authored_change(resolved_cwd)
    _CACHE[cache_key] = result
    return result
