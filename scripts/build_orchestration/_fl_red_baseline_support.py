"""
MODULE: scripts/build_orchestration/_fl_red_baseline_support.py
GOAL: Private helper functions and types backing fast_lane.py's
    verify_red_baseline gate.
BUSINESS CONTEXT: BO-2400a-3 series — verify_red_baseline derives a
    newly-added / pre-existing partition of the batch's covers-tagged tests
    from git (test-function granularity against the worktree's merge-base
    with origin/main, or an explicit ``base_ref``) and passes when at least
    one newly-added test is classified red. This module holds the git
    plumbing, the newly-added/pre-existing partition, and the outcome
    classification helpers that verify_red_baseline itself composes.
    Extracted verbatim from fast_lane.py (NO behaviour change) as part of
    the 2026-09-14 file-size split — see fast_lane.py's own DECISION
    HISTORY for the full record.
ARCHITECTURE: verify_red_baseline itself (and the ``_run_pytest_and_parse``
    name it calls as a bare global) remains physically defined in
    fast_lane.py — see fast_lane.py's own ARCHITECTURE note — because
    mock.patch("fast_lane._run_pytest_and_parse", ...) in the test suite
    relies on that bare-name lookup resolving through fast_lane's own
    module dict. None of the names in THIS module are patched via
    "fast_lane.<name>", so they can live here and be imported normally by
    fast_lane.py without disturbing any test.

    TQ-500f-3-i (absence-only-red refusal): the private helpers below
    (``_load_declared_test_names``, ``_refuse_absence_only_declared_reds``)
    extend this SAME reader with the rule that a newly-added covering test
    whose AC ``test_spec`` entry declares ``must_catch`` (non-empty) or
    ``angle: discrimination`` — read from the AC record's own ``test_spec``
    field only, NEVER from its ``criteria``/``title``/``notes`` prose — is
    refused as red evidence when its only red is an absence red (an
    import/name/attribute lookup error raised before any code under test
    ran, classified from the SAME single pytest run's own output via
    ``done_proof_kind_support._run_pytest_and_parse_with_kind`` — never
    from a self-reported label). This is opt-in: ``verify_red_baseline``
    only calls these helpers when its caller supplies ``ac_root``, so a
    caller that omits it gets byte-identical behaviour to before this AC.

    H-2 FIX (pr-reviewer finding): declared-name matching now normalises a
    nodeid via ``done_proof._nodeid_function_name`` (strip any ``[params]``
    suffix, then take the last ``::``-delimited segment) instead of a bare
    ``nodeid.rsplit("::", 1)[-1]`` — a parametrized declared test's nodeid
    (``test_x[case0]``) never equalled its bare declared name before this
    fix, so it was silently accepted as ordinary red evidence rather than
    refused. Two further fail-closed gaps closed alongside it: a declared
    ``test_spec`` name with NO matching newly-added test at all (checked
    against ALL declared names together — the gate stays permissive when at
    least one OTHER declared name in the same batch IS matched and properly
    red, matching today's accepted control shape), and an ``--ac-root``
    whose named AC record cannot be loaded at all — both now fail the gate
    closed with their own distinct reason rather than silently degrading to
    "nothing was declared".

    H-4 FIX (pr-reviewer finding; user decision, option A — scope note):
    ``done_proof._find_nodeid_for_test`` (the covers-tag-to-nodeid resolver
    every newly-added tag's outcome/kind lookup goes through) matches by
    ``(file_basename, bare_func_name)`` only, so two genuinely DISTINCT
    covers tags that share both — two classes in one file with the same
    method name, or two files sharing a basename in different package
    directories — collapse onto the SAME resolved nodeid. That collapse
    itself is PRE-EXISTING in done_proof.py, which already sits over the
    file-size ratchet; fixing the resolver's own precision is deferred to a
    separate AC. THIS module's fix is the coarser, batch-wide safety net
    ``_detect_ambiguous_tag_identities`` provides: whenever two newly-added
    tags in the batch share ``(function, file_basename)`` — the exact
    condition that makes ``_find_nodeid_for_test`` unable to tell them apart
    — the gate fails closed with ``"ambiguous_test_identity"`` before even
    running pytest, rather than silently reporting a wrong kind, a wrong
    acceptance, or a wrong refusal for either colliding test. Checked over
    the WHOLE batch, not scoped to a single AC id or to declared tags only —
    an unrelated, undeclared collision elsewhere in the same batch still
    trips it (the ambiguity poisons trust in every resolved nodeid in the
    batch, not just the colliding pair's own).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from _fl_common import (
    _TEST_DEF_RE,
    _find_nodeid_for_test,
    _load_ac_by_id,
    _nodeid_function_name,
)


class _RedBaselineGitError(Exception):
    """Raised when a git query needed to resolve the red-baseline partition fails.

    Carries the failing query in its message so the caller can report a
    fail-closed ``baseline_partition_unavailable`` verdict that names what
    could not be answered (BO-2400a-3-vii), without ever falling back to a
    permissive default (e.g. treating every covering test as newly-added).
    """


_RED_OUTCOMES: frozenset[str] = frozenset({"FAILED", "XFAIL"})
_GREEN_OUTCOMES: frozenset[str] = frozenset({"PASSED", "XPASS"})


def _run_git_in(cwd: Path, args: list[str]) -> str:
    """Run a read-only git subcommand with ``cwd=cwd``; raise on any failure.

    Used exclusively for the read-only queries (``rev-parse``, ``merge-base``,
    ``show``) the red-baseline gate needs to resolve its newly-added
    partition — never ``fetch`` or any ref-mutating command, so resolving the
    partition never advances the worktree's git state (BO-2400a-3-viii).

    Args:
        cwd: Directory to run the git subcommand in.
        args: git subcommand and its arguments (without the leading ``git``).

    Returns:
        The subprocess's stdout text.

    Raises:
        _RedBaselineGitError: git could not be launched, timed out, or
            exited non-zero.
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _RedBaselineGitError(f"git {' '.join(args)}: {exc}") from exc
    if proc.returncode != 0:
        raise _RedBaselineGitError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


def _resolve_git_baseline_context(
    test_root: Path, base_ref: str | None
) -> tuple[Path, str]:
    """Resolve the repo root and the git ref to diff newly-added tests against.

    Args:
        test_root: Directory to resolve the containing git worktree from.
        base_ref: Caller-supplied ref to diff against, or ``None`` to derive
            the default (``git merge-base HEAD origin/main``).

    Returns:
        ``(repo_root, resolved_ref)`` — the worktree's top-level directory and
        the ref whose tree newly-added tests are diffed against.

    Raises:
        _RedBaselineGitError: *test_root* is not inside a git worktree, or
            (when *base_ref* is not supplied) the merge-base with
            ``origin/main`` cannot be resolved.  Never falls back to a
            permissive default (BO-2400a-3-vii).
    """
    toplevel = _run_git_in(test_root, ["rev-parse", "--show-toplevel"]).strip()
    repo_root = Path(toplevel).resolve()
    resolved_ref = (
        base_ref
        if base_ref is not None
        else _run_git_in(test_root, ["merge-base", "HEAD", "origin/main"]).strip()
    )
    return repo_root, resolved_ref


def _read_file_at_ref(repo_root: Path, ref: str, relpath: str) -> str | None:
    """Return the content of *relpath* at git *ref*, or None if absent there.

    *ref* has already been validated by :func:`_resolve_git_baseline_context`
    before this is called, so a non-zero exit from ``git show <ref>:<relpath>``
    is interpreted as "the path does not exist at that ref" — the normal case
    for a newly-added test file or function — rather than a fatal error.

    Args:
        repo_root: The worktree's top-level directory (subprocess ``cwd``).
        ref: A git ref or commit sha already confirmed to resolve.
        relpath: POSIX-style path of the file relative to *repo_root*.

    Returns:
        The file's content at *ref*, or ``None`` when the path does not exist
        there.

    Raises:
        _RedBaselineGitError: git itself could not be launched or timed out.
    """
    try:
        proc = subprocess.run(
            ["git", "show", f"{ref}:{relpath}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _RedBaselineGitError(f"git show {ref}:{relpath}: {exc}") from exc
    if proc.returncode != 0:
        return None
    return proc.stdout


def _test_names_in_source(source: str) -> set[str]:
    """Return the set of ``def test_*`` function names declared in *source*.

    Reuses done_proof's :data:`_TEST_DEF_RE` so a test function counts as
    "present" here under exactly the same rule the covers-tag scanner uses to
    associate a tag with its enclosing function.

    Args:
        source: Python source text (as read from a git blob).

    Returns:
        Set of test function names found via ``_TEST_DEF_RE``.
    """
    return {
        match.group(1)
        for match in (_TEST_DEF_RE.match(line) for line in source.splitlines())
        if match is not None
    }


def _partition_newly_added(
    linked_tags: list[dict],
    repo_root: Path,
    base_ref: str,
) -> tuple[list[dict], list[dict]]:
    """Split *linked_tags* into newly-added and pre-existing lists.

    Classification is at test-function granularity (BO-2400a-3-iii): a tag is
    newly-added when its file is absent at *base_ref* or its function name is
    absent from the *base_ref* version of that file — never merely because the
    file as a whole was modified.

    Args:
        linked_tags: Covers-tag dicts (as produced by
            :func:`~done_proof._scan_test_root_for_covers_tags`) already
            filtered to the batch's AC ids.
        repo_root: The worktree's top-level directory.
        base_ref: The git ref already resolved by
            :func:`_resolve_git_baseline_context`.

    Returns:
        ``(newly_added_tags, preexisting_tags)`` — the same tag dicts,
        partitioned; each retains the scan order of *linked_tags*.

    Raises:
        _RedBaselineGitError: git itself could not be launched or timed out
            while reading a file's content at *base_ref*.
    """
    newly_added: list[dict] = []
    preexisting: list[dict] = []
    base_names_by_relpath: dict[str, set[str] | None] = {}

    for tag in linked_tags:
        relpath = Path(tag["file"]).resolve().relative_to(repo_root).as_posix()
        if relpath not in base_names_by_relpath:
            base_content = _read_file_at_ref(repo_root, base_ref, relpath)
            base_names_by_relpath[relpath] = (
                _test_names_in_source(base_content) if base_content is not None else None
            )
        base_names = base_names_by_relpath[relpath]
        if base_names is None or tag["function"] not in base_names:
            newly_added.append(tag)
        else:
            preexisting.append(tag)

    return newly_added, preexisting


def _classify_outcome_bucket(outcome: str) -> str:
    """Classify a raw pytest outcome token into ``"red"``, ``"green"``, or ``"inconclusive"``.

    Total over the outcome vocabulary the pytest-output parser emits (PASSED,
    FAILED, XFAIL, XPASS, SKIPPED, ERROR); any unrecognised token is treated as
    inconclusive rather than silently dropped (BO-2400a-3-vi).

    Args:
        outcome: Raw outcome token (e.g. ``"XFAIL"``).

    Returns:
        One of ``"red"``, ``"green"``, ``"inconclusive"``.
    """
    if outcome in _RED_OUTCOMES:
        return "red"
    if outcome in _GREEN_OUTCOMES:
        return "green"
    return "inconclusive"


def _resolve_tag_outcome(tag: dict, pytest_results: dict[str, str]) -> tuple[str, str]:
    """Return ``(nodeid, outcome)`` for *tag*, fail-closed when unresolvable.

    Args:
        tag: A covers-tag dict with ``"function"`` and ``"file"`` keys.
        pytest_results: ``{nodeid: outcome}`` from ``_run_pytest_and_parse``.

    Returns:
        The matched pytest nodeid and its outcome; when no run result can be
        located for the tag, a synthetic ``"<file>::<function>"`` nodeid is
        returned paired with outcome ``"ERROR"`` so the test is reported as
        inconclusive rather than silently omitted.
    """
    func_name = tag["function"]
    file_basename = Path(tag["file"]).name
    nodeid = _find_nodeid_for_test(func_name, file_basename, pytest_results)
    if nodeid is None:
        return f"{tag['file']}::{func_name}", "ERROR"
    return nodeid, pytest_results.get(nodeid, "ERROR")


def _build_entry(tag: dict, nodeid: str, outcome: str, results: dict | None = None) -> dict:
    """Build a ``{"nodeid", "ac_id", "outcome"}`` report entry for *tag*.

    TQ-500g-4: when *results* (the shared reading) names failed sub-cases for
    *nodeid*, the entry also carries them under the additive ``"subcases"`` key.
    """
    entry = {"nodeid": nodeid, "ac_id": tag["ac_id"], "outcome": outcome}
    subcases = getattr(results, "subfailed", {}).get(nodeid)
    if subcases:
        entry["subcases"] = list(subcases)
    return entry


def _classify_newly_added(
    newly_added_tags: list[dict],
    pytest_results: dict[str, str],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Classify each newly-added tag's outcome into red / green / inconclusive.

    Args:
        newly_added_tags: Covers-tag dicts classified newly-added by
            :func:`_partition_newly_added`.
        pytest_results: ``{nodeid: outcome}`` from ``_run_pytest_and_parse``.

    Returns:
        ``(red, green_at_baseline, inconclusive)`` — three lists of report
        entries (BO-2400a-3-vi classification), in *newly_added_tags* order.
    """
    red: list[dict] = []
    green_at_baseline: list[dict] = []
    inconclusive: list[dict] = []
    for tag in newly_added_tags:
        nodeid, outcome = _resolve_tag_outcome(tag, pytest_results)
        entry = _build_entry(tag, nodeid, outcome, pytest_results)
        bucket = _classify_outcome_bucket(outcome)
        if bucket == "red":
            red.append(entry)
        elif bucket == "green":
            green_at_baseline.append(entry)
        else:
            inconclusive.append(entry)
    return red, green_at_baseline, inconclusive


def _report_preexisting(
    preexisting_tags: list[dict],
    pytest_results: dict[str, str],
) -> list[dict]:
    """Build report entries for the pre-existing partition (BO-2400a-3-iv).

    Args:
        preexisting_tags: Covers-tag dicts classified pre-existing by
            :func:`_partition_newly_added`.
        pytest_results: ``{nodeid: outcome}`` from ``_run_pytest_and_parse``.

    Returns:
        Report entries — excluded from the verdict but still surfaced so the
        operator can see them.
    """
    return [
        _build_entry(tag, *_resolve_tag_outcome(tag, pytest_results), pytest_results)
        for tag in preexisting_tags
    ]


def _red_baseline_verdict(
    *,
    gate_passed: bool,
    reason: str | None,
    red: list[dict] | None = None,
    green_at_baseline: list[dict] | None = None,
    inconclusive: list[dict] | None = None,
    preexisting: list[dict] | None = None,
    refused: list[dict] | None = None,
) -> dict:
    """Assemble the pinned verify_red_baseline return shape.

    Args:
        gate_passed: Whether the red baseline is established.
        reason: ``None`` when passed, else one of the fixed halt-reason tokens.
        red: Newly-added tests classified red.  Defaults to ``[]``.
        green_at_baseline: Newly-added tests classified green.  Defaults to
            ``[]``.
        inconclusive: Newly-added tests classified inconclusive.  Defaults to
            ``[]``.
        preexisting: Pre-existing tests, excluded from the verdict.  Defaults
            to ``[]``.
        refused: TQ-500f-3-i — declared (must_catch / angle:discrimination)
            newly-added covering tests whose only red was an absence red,
            each ``{"nodeid", "ac_id", "kind": "absence", "message"}``.
            Additive key; always present (``[]`` when unused or when no
            caller-supplied ``ac_root`` is given). Defaults to ``[]``.

    Returns:
        Dict with exactly the keys ``gate_passed``, ``reason``, ``red``,
        ``green_at_baseline``, ``inconclusive``, ``preexisting``, ``refused``.
    """
    return {
        "gate_passed": gate_passed,
        "reason": reason,
        "red": red or [],
        "green_at_baseline": green_at_baseline or [],
        "inconclusive": inconclusive or [],
        "preexisting": preexisting or [],
        "refused": refused or [],
    }


# ---------------------------------------------------------------------------
# TQ-500f-3-i — absence-only-red refusal for a DECLARED covering test.
# ---------------------------------------------------------------------------

# The DECLARED signal's decided text (TQ-500f-3-i criteria): a refused
# entry's message states that a test naming wrong versions to catch must
# fail by reaching the code — never a generic "this test failed" message.
_REACH_THE_CODE_MESSAGE = (
    "A test naming wrong versions to catch must fail by reaching the code, "
    "not by failing to import or find the thing it names."
)


def _is_declared_test_spec_entry(entry: dict) -> bool:
    """Return whether one AC ``test_spec`` entry declares a discrimination guard.

    Declared per TQ-500f-3-i's it_requirements: ``must_catch`` is present and
    non-empty, OR ``angle`` equals ``"discrimination"`` — read from the entry
    itself, never inferred from any other field.

    Args:
        entry: One ``test_spec`` list entry (a dict) from an AC record.

    Returns:
        True when the entry declares a discrimination guard.
    """
    return bool(entry.get("must_catch")) or entry.get("angle") == "discrimination"


def _load_declared_test_names(
    ac_ids: list[str], ac_root: Path
) -> tuple[set[str], list[str]]:
    """Collect every declared test_spec entry name across *ac_ids*' AC records.

    Reads ONLY each covering AC's own ``test_spec`` field (TQ-500f-3-i: "the
    decision uses only what the test requirements declare and the outcome of
    the run — never the wording of the requirement") — ``criteria``,
    ``title``, and ``notes`` are never consulted.

    Args:
        ac_ids: Batch of AC ids to load ``test_spec`` from.
        ac_root: Root directory of the AC YAML store.

    Returns:
        ``(declared_names, unavailable_ac_ids)`` — the set of test function
        names declared by ``must_catch`` or ``angle: discrimination`` on any
        of *ac_ids*' ``test_spec`` entries, and the list of *ac_ids* whose
        record could not be loaded at all (H-2 fix: an unloadable record is
        reported distinctly, never silently folded into "nothing declared").
    """
    declared: set[str] = set()
    unavailable: list[str] = []
    for ac_id in ac_ids:
        record = _load_ac_by_id(ac_root, ac_id)
        if record is None:
            unavailable.append(ac_id)
            continue
        for entry in record.get("test_spec") or []:
            name = entry.get("name") if isinstance(entry, dict) else None
            if name and _is_declared_test_spec_entry(entry):
                declared.add(name)
    return declared, unavailable


def _any_declared_name_matched(
    newly_added_tags: list[dict], declared_names: set[str]
) -> bool:
    """Return whether at least one newly-added tag matches a declared name.

    H-2 fix: a declared ``test_spec`` entry with NO corresponding
    newly-added test at all must not let the batch pass unchallenged on an
    unrelated red test, as if nothing had been declared. Checked over ALL
    declared names together (not per-name) so a batch where at least one
    OTHER declared name IS matched and properly red keeps today's accepted
    shape — only a batch where NONE of the declared names were ever
    attempted fails closed (see :func:`_refuse_absence_only_declared_reds`'s
    caller in ``verify_red_baseline`` for where this is consulted).

    Args:
        newly_added_tags: Covers-tag dicts classified newly-added by
            :func:`_partition_newly_added` (each carries a ``"function"``
            key — the bare, source-scanned def name, never bracket-suffixed).
        declared_names: Test function names from :func:`_load_declared_test_names`.

    Returns:
        True iff at least one newly-added tag's function name is declared.
    """
    return any(tag["function"] in declared_names for tag in newly_added_tags)


def _detect_ambiguous_tag_identities(newly_added_tags: list[dict]) -> bool:
    """Return whether two newly-added tags share ``(function, file_basename)``.

    That pair is exactly the key ``done_proof._find_nodeid_for_test`` matches
    on — two tags sharing it cannot be told apart by the resolver every
    outcome/kind lookup in this module goes through, so resolving either
    tag's nodeid is unsafe (see this module's H-4 ARCHITECTURE note).

    Args:
        newly_added_tags: Covers-tag dicts classified newly-added by
            :func:`_partition_newly_added`.

    Returns:
        True iff at least one ``(function, file_basename)`` pair is shared
        by two or more tags in *newly_added_tags*.
    """
    counts: dict[tuple[str, str], int] = {}
    for tag in newly_added_tags:
        key = (tag["function"], Path(tag["file"]).name)
        counts[key] = counts.get(key, 0) + 1
    return any(count > 1 for count in counts.values())


def _declared_names_preflight(
    ac_ids: list[str], ac_root: Path, newly_added_tags: list[dict]
) -> tuple[set[str], str | None]:
    """Load declared names and check the two H-2 fail-closed preconditions.

    Combines :func:`_load_declared_test_names` and
    :func:`_any_declared_name_matched` into the one pre-pytest check
    ``verify_red_baseline`` needs, so its own body only branches on the
    result rather than repeating this composition inline.

    Args:
        ac_ids: Batch of AC ids whose ``test_spec`` establishes declared names.
        ac_root: Root directory of the AC YAML store.
        newly_added_tags: Covers-tag dicts classified newly-added by
            :func:`_partition_newly_added`.

    Returns:
        ``(declared_names, reason)`` — *reason* is ``None`` when neither
        precondition failed, else ``"declared_ac_record_unavailable"`` or
        ``"declared_test_missing_no_matching_test"``.
    """
    declared_names, unavailable_ac_ids = _load_declared_test_names(ac_ids, ac_root)
    if unavailable_ac_ids:
        return declared_names, "declared_ac_record_unavailable"
    if declared_names and not _any_declared_name_matched(newly_added_tags, declared_names):
        return declared_names, "declared_test_missing_no_matching_test"
    return declared_names, None


def _refuse_absence_only_declared_reds(
    red: list[dict],
    kind_by_nodeid: dict[str, str],
    declared_names: set[str],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Partition *red* into (kept_red, refused, undetermined) per TQ-500f-3-i's rule.

    A red entry is refused when its function name is in *declared_names* AND
    its kind (from *kind_by_nodeid*) is ``"absence"``. A declared entry whose
    kind could not be determined from the run's own output is fail-closed
    (TQ-500f-3-i: "a declared test whose kind of red cannot be determined is
    not accepted as red evidence"): moved into ``undetermined`` rather than
    ``kept_red`` (H-1 fix: the caller reports this with its OWN distinct
    reason — ``declared_test_kind_undetermined`` — never silently as
    ``all_new_tests_green_at_baseline``, which would be a lie about a test
    that actually FAILED). An undeclared entry, and a declared entry whose
    kind is ``"assertion"``, both stay in ``red`` unchanged.

    H-2 fix: the function name is read via ``done_proof._nodeid_function_name``
    (strips any ``[params]`` parametrize suffix before taking the last
    ``::`` segment) rather than a bare ``rsplit``, so a parametrized declared
    test (``test_x[case0]``) matches its bare declared name (``test_x``)
    exactly like an unparametrized one does.

    Args:
        red: Newly-added tests already classified red by
            :func:`_classify_newly_added`.
        kind_by_nodeid: ``{nodeid: "absence" | "assertion"}`` from
            ``done_proof_kind_support._run_pytest_and_parse_with_kind``.
        declared_names: Test function names declaring a discrimination guard,
            from :func:`_load_declared_test_names`.

    Returns:
        ``(kept_red, refused, undetermined)`` — ``kept_red`` is *red* minus
        refused and undetermined entries, in original order; ``refused``
        carries one ``{"nodeid", "ac_id", "kind": "absence", "message"}``
        entry per refusal; ``undetermined`` carries the original red entries
        whose kind could not be resolved.
    """
    kept: list[dict] = []
    refused: list[dict] = []
    undetermined: list[dict] = []
    for entry in red:
        nodeid = entry["nodeid"]
        func_name = _nodeid_function_name(nodeid)
        if func_name not in declared_names:
            kept.append(entry)
            continue
        kind = kind_by_nodeid.get(nodeid)
        if kind == "absence":
            refused.append(
                {
                    "nodeid": nodeid,
                    "ac_id": entry["ac_id"],
                    "kind": "absence",
                    "message": _REACH_THE_CODE_MESSAGE,
                }
            )
        elif kind == "assertion":
            kept.append(entry)
        else:
            # kind is None (undetermined from this run's own output): fail
            # closed — never kept as red, never silently dropped either.
            undetermined.append(entry)
    return kept, refused, undetermined


def _classify_declared_reds(
    red: list[dict],
    kind_by_nodeid: dict[str, str],
    declared_names: set[str],
    green_at_baseline: list[dict],
    inconclusive: list[dict],
    preexisting: list[dict],
) -> tuple[list[dict], list[dict], dict | None]:
    """Run the H-1/H-2 refusal partition and build an early verdict when needed.

    Composes :func:`_refuse_absence_only_declared_reds` with the two verdicts
    a refused or undetermined declared red produces, so ``verify_red_baseline``
    itself only branches on whether an early verdict was built.

    Args:
        red: Newly-added tests already classified red.
        kind_by_nodeid: ``{nodeid: "absence" | "assertion"}``.
        declared_names: Declared test_spec names from :func:`_load_declared_test_names`.
        green_at_baseline: Newly-added tests classified green (report passthrough).
        inconclusive: Newly-added tests classified inconclusive (report passthrough).
        preexisting: Pre-existing tests (report passthrough).

    Returns:
        ``(red, refused, early_verdict)`` — *red* and *refused* are the
        partition's own output; *early_verdict* is a fully-built
        ``_red_baseline_verdict`` dict the caller must return immediately
        when not ``None`` (a refusal or an undetermined kind fired), else
        ``None`` to signal the caller should continue its own flow.
    """
    kept_red, refused, undetermined = _refuse_absence_only_declared_reds(
        red, kind_by_nodeid, declared_names
    )
    if refused:
        return kept_red, refused, _red_baseline_verdict(
            gate_passed=False,
            reason="declared_test_refused_absence_only_red",
            red=kept_red,
            green_at_baseline=green_at_baseline,
            inconclusive=inconclusive,
            preexisting=preexisting,
            refused=refused,
        )
    if undetermined:
        return kept_red, refused, _red_baseline_verdict(
            gate_passed=False,
            reason="declared_test_kind_undetermined",
            red=kept_red,
            green_at_baseline=green_at_baseline,
            inconclusive=inconclusive + undetermined,
            preexisting=preexisting,
            refused=refused,
        )
    return kept_red, refused, None


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-14 [python-coder/refactor-fast-lane-size]: Extracted verbatim
#   from fast_lane.py (NO behaviour change) as part of the file-size split —
#   see fast_lane.py's own DECISION HISTORY for the full record.
#   (#TICKETLESS reason=fast-lane-file-size-split)
# ====================================================================
