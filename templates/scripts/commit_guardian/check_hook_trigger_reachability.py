"""
MODULE: check_hook_trigger_reachability
GOAL: Pre-commit hook — the "registry's own reachability check" required by
    BP-100k-4. For every gate registered in ``hooks_manifest.hooks`` of
    commit_guardian.json, determines whether at least one path this
    repository actually tracks can ever activate it, and whether a
    whole-tree gate (``always_run: true``, never consulting the staged
    file list) has been given a path-based ``files`` filter it never
    consults. A gate that can never fire, or whose stated activation
    mechanism contradicts its own execution shape, is reported and blocks
    the commit.
BUSINESS CONTEXT: Two gates in this registry — check-build-drift and
    check-output-drift — were registered with ``files`` triggers that could
    never match anything this repository is able to stage (one named a
    consumer-install-only location, the other named locations that are
    either gitignored or absent), so both had never fired despite guarding
    roughly 3,000 lines of drift-gate hardening. Correcting those two
    triggers alone leaves the defect CLASS intact for the next hook added
    to the registry; this check makes the class itself a reported, blocking
    condition. See
    docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/BP-100k-4.yaml
    and BP-100k-4-i.yaml (the paired negative case: no false alarm on a
    gate that legitimately fires, and fail-closed — never a silent pass —
    when reachability cannot be determined at all).
ARCHITECTURE: This hook itself inspects the WHOLE registry, never a staged
    file list, so it is registered in hooks_manifest.hooks with
    ``always_run: true`` and ``pass_filenames: false`` — it is itself an
    instance of the whole-tree-gate shape this AC exists to police.

    Registry resolution (mirrors the HOOK_TEST_CONFIG convention already
    established by check_build_drift.py / check_output_drift.py, and the
    two-tier fallback established by check_hook_parity.py's
    ``_load_config``):
      1. ``HOOK_TEST_CONFIG`` env var, if set: read that JSON file directly
         (must contain a top-level ``hooks_manifest`` key shaped like
         ``{"hooks": [...]}``). Used INSTEAD of the real registry — never
         falls through to it.
      2. ``<cwd>/scripts/commit_guardian/commit_guardian.json`` (the
         deployed runtime copy).
      3. ``commit_guardian.json`` colocated with this script (the template
         source tree copy).
      4. If none of the above can be read and parsed as JSON: INDETERMINATE
         (see below) — never a silent pass.

    Tracked-path acquisition: ``git ls-files`` run with this process's cwd
    as the working directory. A non-zero exit (including "not a git
    repository") or a missing ``git`` executable is INDETERMINATE.

    FAIL-CLOSED CONTRACT (BP-100k-4-i): an inability to read the registry
    or to obtain the tracked-path set is reported via an
    ``INDETERMINATE: reason=<text>`` line and a non-zero (2) exit — it must
    never be reported as a clean, zero-unreachable pass. Conversely, a
    whole-tree gate (``always_run: true``) that carries no ``files`` key is
    the legitimate shape and must never be flagged merely for lacking a
    path filter.

    Per-gate rule (an ``enabled: false`` entry is skipped — intentionally
    off, not a reachability question). This is a THREE-WAY verdict —
    reachable / declared-exempt-with-ground / unreachable — reusing the
    exemption vocabulary BP-100k-3 established for the drift gates
    (``_drift_exemptions.py``: ``EXEMPT <key> ground=<text>``, with a
    groundless entry REJECTED and falling through to the un-exempted
    verdict) rather than inventing a third one:
      - ``always_run: true`` AND a ``files`` key present -> UNREACHABLE
        (whole-tree gate carrying a filter it never consults — this shape
        is never exemptable, it is always a real authoring mistake).
      - ``always_run: true``, no ``files`` -> reachable.
      - ``files`` present (``always_run`` not true): compiled as a regex
        and ``re.search`` against every ``git ls-files`` path. One or more
        matches -> reachable. Zero matches -> check the
        ``hook_trigger_reachability_exemption_registry`` (a top-level key
        of the SAME loaded registry, entries shaped ``{"id": <gate-id>,
        "ground": <text>}``) for this gate's id. A valid (non-blank
        ``ground``) entry -> EXEMPT (reported, not counted as unreachable,
        never blocks). No entry, or a groundless one (rejected with
        ``REJECTED EXEMPTION ENTRY: <id> reason=no ground stated``) ->
        UNREACHABLE.
      - neither key present -> reachable (pre-commit's own default: an
        absent ``files`` filter matches everything).

    "Zero matches in the CURRENT repository" is not always "cannot ever
    match" — a correctly-authored trigger for a file family this specific
    checkout happens not to have (e.g. ``check-infra-docs``' docker-compose
    pattern in a repo with no Docker infrastructure) is context-dependent,
    not structurally dead, and must not be forced into ``always_run`` or a
    rewritten pattern merely to satisfy this check (that would silently
    convert a conditional gate into an unconditional one for every consumer
    install). The exemption registry is the correct instrument for that
    case, exactly as BP-100k-3 established for the drift gates.

    CONSUMER BLAST-RADIUS NOTE (BP-100k-4-i): this registry ships to every
    consumer install verbatim. A gate whose ``files`` target lives inside
    the package's own vendored subtree (e.g. ``config/paths.json``,
    ``templates/docs/architecture/``) may have zero tracked matches in a
    consumer's outer repository even though the pattern is correct for the
    self-hosted package checkout — the vendored package directory can be
    gitignored or a submodule there. Such gates are declared exempt (see
    ``check-paths-integrity`` / ``check-architecture-scaffolds`` in
    commit_guardian.json) rather than forced to ``always_run`` or having
    the check's own verdict weakened, so this gate can never become a
    universal commit-blocker across every consumer project.

    Exit status: 0 when unreachable == 0 and determinate; 1 when
    unreachable > 0; 2 when indeterminate.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

# No ImportError fallback here (contrast check_build_drift.py's
# _drift_exemptions import): build_commit_guardian deploys the ENTIRE
# templates/scripts/commit_guardian/ directory verbatim (never a per-file
# allowlist), and every test fixture in this file family deploys the whole
# directory too (see _deploy_commit_guardian_dir in test_bp_100k_4.py) — so
# this sibling module is always present alongside this one.
from _hook_trigger_reachability_helpers import (
    UNKNOWN_GATE_ID_SENTINEL,
    RegexTimeoutError,
    evaluate_gate,
    regex_match_timeout_seconds,
    validate_exemptions,
)

_GATE_NAME = "check-hook-trigger-reachability"
_HOOK_FILE = Path(__file__).resolve()
_SUBPROCESS_TIMEOUT_SECONDS = 20


# ---------------------------------------------------------------------------
# Registry resolution
# ---------------------------------------------------------------------------


def _read_json_file(path: Path) -> dict | None:
    """Read and parse one JSON file, returning None on any I/O or parse error.

    Args:
        path: Absolute path to the candidate JSON file.

    Returns:
        The parsed JSON value, or None if the file cannot be read or is not
        valid JSON. Logs a WARNING in either failure case.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError as exc:
        print(f"{_GATE_NAME}: WARNING - could not read {path}: {exc}", file=sys.stderr)
        return None
    except json.JSONDecodeError as exc:
        print(f"{_GATE_NAME}: WARNING - {path} is not valid JSON: {exc}", file=sys.stderr)
        return None


def _load_registry() -> tuple[dict | None, str | None]:
    """Resolve and load the hooks_manifest registry per the BP-100k-4 order.

    BP-100k-4 round-2 hardening (F6): "absent" and "corrupt" are DIFFERENT
    conditions and must not be treated alike. A candidate that does not
    exist is skipped in favour of the next one (the documented fresh-clone
    fallback). A candidate that EXISTS but cannot be parsed as JSON is a
    broken build artifact — the file pre-commit would actually consume is
    broken, so this stops immediately rather than silently verifying a
    DIFFERENT registry (the colocated source copy) and reporting a clean
    pass against a tree it never examined.

    Returns:
        A ``(registry, reason)`` pair. On success, ``registry`` is the
        parsed dict and ``reason`` is None. On failure, ``registry`` is None
        and ``reason`` is a diagnostic string suitable for the
        ``INDETERMINATE: reason=<...>`` line — distinguishing "no candidate
        exists" from "a candidate exists but could not be parsed".
    """
    test_config_path = os.environ.get("HOOK_TEST_CONFIG")
    if test_config_path:
        candidate = Path(test_config_path)
        registry = _read_json_file(candidate)
        if registry is None:
            return None, (
                f"HOOK_TEST_CONFIG={candidate} could not be read or parsed as JSON"
            )
        return registry, None

    candidates = [
        Path.cwd() / "scripts" / "commit_guardian" / "commit_guardian.json",
        _HOOK_FILE.parent / "commit_guardian.json",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        registry = _read_json_file(candidate)
        if registry is None:
            return None, (
                f"{candidate} exists but could not be parsed as JSON — this is "
                "the registry pre-commit would actually run, so the check is "
                "not falling through to try a different copy"
            )
        return registry, None
    return None, (
        "no hooks_manifest registry candidate exists (HOOK_TEST_CONFIG unset; "
        "deployed and source commit_guardian.json are both absent)"
    )


# ---------------------------------------------------------------------------
# Tracked-path acquisition
# ---------------------------------------------------------------------------


def _get_tracked_paths(cwd: Path) -> list[str] | None:
    """Return the repository-tracked paths via ``git ls-files``.

    Args:
        cwd: Working directory to run ``git ls-files`` in.

    Returns:
        The tracked, forward-slash, repo-root-relative paths exactly as
        ``git ls-files`` emits them, or None if the command could not be
        run at all or exited non-zero (e.g. not a git repository).
    """
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"{_GATE_NAME}: WARNING - could not run 'git ls-files': {exc}", file=sys.stderr)
        return None

    if result.returncode != 0:
        print(
            f"{_GATE_NAME}: WARNING - 'git ls-files' exited "
            f"{result.returncode}: {result.stderr.strip()}",
            file=sys.stderr,
        )
        return None

    return [line for line in result.stdout.splitlines() if line]


# ---------------------------------------------------------------------------
# Exemption registry validation and the per-gate reachability rule now live
# in _hook_trigger_reachability_helpers.py (imported above as
# validate_exemptions / evaluate_gate) — split out purely to stay under the
# 400-line file-size limit. See that module's docstring for the contract.
# ---------------------------------------------------------------------------


def _resolve_hooks_or_reason(registry: dict) -> tuple[list[dict] | None, str | None]:
    """Extract and floor-check ``hooks_manifest.hooks`` from a loaded registry.

    BP-100k-4 round-2 hardening (F7): a run that inspected zero gates has
    established nothing — mirrors the ``verified == 0`` floor the sibling
    drift gates already enforce. An absent/wrong-typed list, an empty list,
    or a list whose every entry is disabled/non-dict are all INDETERMINATE,
    never a clean pass.

    Args:
        registry: The loaded registry dict.

    Returns:
        A ``(hooks, reason)`` pair: ``(hooks_list, None)`` on success, or
        ``(None, reason)`` with a diagnostic suitable for the
        ``INDETERMINATE: reason=<...>`` line.
    """
    hooks_manifest = registry.get("hooks_manifest")
    hooks = hooks_manifest.get("hooks") if isinstance(hooks_manifest, dict) else None
    if not isinstance(hooks, list):
        return None, "registry is missing a valid hooks_manifest.hooks list"

    eligible_entries = [
        entry
        for entry in hooks
        if isinstance(entry, dict) and entry.get("enabled") is not False
    ]
    if not eligible_entries:
        return None, (
            "hooks_manifest.hooks contains no evaluable entries (empty "
            "list, or every entry is disabled/non-dict) — a run that "
            "inspected zero gates has established nothing"
        )
    return hooks, None


def _resolve_tracked_paths_or_reason(cwd: Path) -> tuple[list[str] | None, str | None]:
    """Obtain the tracked-path set and floor-check it against emptiness.

    BP-100k-4 round-2 hardening (M / zero-tracked-path finding): a
    SUCCESSFUL empty result (``git ls-files`` exited 0 with no output — a
    fresh clone/submodule/shallow checkout before the first ``git add``) is
    the same epistemic state as the lookup failing outright: no evidence
    either way. It must never be treated as proof that every
    files-triggered gate is unreachable.

    Args:
        cwd: Working directory to run ``git ls-files`` in.

    Returns:
        A ``(tracked_paths, reason)`` pair: ``(paths, None)`` on success, or
        ``(None, reason)`` with a diagnostic suitable for the
        ``INDETERMINATE: reason=<...>`` line.
    """
    tracked_paths = _get_tracked_paths(cwd)
    if tracked_paths is None:
        return None, "could not obtain the repository's tracked-path set via 'git ls-files'"
    if not tracked_paths:
        return None, (
            "the repository tracks zero paths ('git ls-files' succeeded "
            "but returned no paths) — reachability cannot be established "
            "from no evidence"
        )
    return tracked_paths, None


def _evaluate_all_gates(
    hooks: list[dict], tracked_paths: list[str], exemptions: dict[str, str]
) -> tuple[int, int, int] | None:
    """Evaluate every hooks_manifest entry, printing per-gate diagnostics.

    BP-100k-4 round-2 hardening (F5, duplicate ids): a hooks-manifest id
    that appears more than once can never safely share one exemption entry
    — the ground given for one gate is not guaranteed to apply to the
    other. Detected up front so every occurrence is handled uniformly.

    Args:
        hooks: The full ``hooks_manifest.hooks`` list (non-dict and
            disabled entries are skipped internally).
        tracked_paths: The repository's tracked paths.
        exemptions: Valid gate-id -> ground map.

    Returns:
        ``(total, unreachable, exempt)`` on completion, or None if a regex
        evaluation exceeded its wall-clock bound — in which case this
        function has already printed the ``INDETERMINATE`` line itself.
    """
    id_counts = Counter(
        entry.get("id")
        for entry in hooks
        if isinstance(entry, dict) and entry.get("enabled") is not False and entry.get("id")
    )
    duplicate_ids = {gate_id for gate_id, count in id_counts.items() if count > 1}
    reported_duplicate_ids: set[str] = set()

    total = 0
    unreachable = 0
    exempt = 0
    for entry in hooks:
        if not isinstance(entry, dict) or entry.get("enabled") is False:
            continue
        total += 1
        gate_id = entry.get("id")
        display_id = gate_id if gate_id else UNKNOWN_GATE_ID_SENTINEL

        try:
            verdict, detail = evaluate_gate(entry, tracked_paths, exemptions)
        except RegexTimeoutError:
            print(
                f"INDETERMINATE: reason=evaluating gate {display_id!r}'s "
                f"files pattern {entry.get('files')!r} against "
                f"{len(tracked_paths)} tracked path(s) exceeded its "
                f"{regex_match_timeout_seconds()}s wall-clock budget — "
                "reachability cannot be determined in bounded time",
                file=sys.stderr,
            )
            return None

        verdict, detail = _apply_duplicate_id_override(
            gate_id, verdict, detail, duplicate_ids, id_counts, reported_duplicate_ids
        )

        if verdict == "unreachable":
            unreachable += 1
            print(f"UNREACHABLE: {display_id} reason={detail}", file=sys.stderr)
        elif verdict == "exempt":
            exempt += 1
            print(f"EXEMPT: {display_id} ground={detail}", file=sys.stderr)

    return total, unreachable, exempt


def _apply_duplicate_id_override(
    gate_id: str | None,
    verdict: str,
    detail: str | None,
    duplicate_ids: set[str],
    id_counts: Counter,
    reported_duplicate_ids: set[str],
) -> tuple[str, str | None]:
    """Force a duplicated-id gate's "exempt" verdict to "unreachable".

    Also prints the ``DUPLICATE-ID: ...`` diagnostic once per duplicated id
    (BP-100k-4 round-2 hardening, F5) — a duplicate id is itself a reported
    condition, never a silent shared exemption key.

    Args:
        gate_id: The entry's raw id (may be None).
        verdict: The verdict from ``evaluate_gate``.
        detail: The detail text from ``evaluate_gate``.
        duplicate_ids: Set of ids that appear more than once.
        id_counts: Occurrence count per id.
        reported_duplicate_ids: Mutated in place — ids already diagnosed.

    Returns:
        The (possibly overridden) ``(verdict, detail)`` pair.
    """
    if gate_id not in duplicate_ids:
        return verdict, detail

    if gate_id not in reported_duplicate_ids:
        print(
            f"DUPLICATE-ID: {gate_id} reason=id appears "
            f"{id_counts[gate_id]} times in hooks_manifest.hooks; a "
            "duplicate id can never share one exemption entry across "
            "distinct gates",
            file=sys.stderr,
        )
        reported_duplicate_ids.add(gate_id)

    if verdict == "exempt":
        return "unreachable", (
            f"id {gate_id!r} is duplicated in hooks_manifest.hooks; "
            "duplicate ids are never eligible for a shared exemption "
            f"(the ground text was: {detail!r})"
        )
    return verdict, detail


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def main() -> int:
    """Entry point for the pre-commit hook.

    Returns:
        0 when every non-skipped gate is reachable (determinate run); 1
        when one or more gates are unreachable; 2 when reachability could
        not be determined at all (registry unreadable, no evaluable gates,
        an unobtainable or empty tracked-path set, or a regex evaluation
        exceeding its wall-clock bound) — never a silent pass in any of
        those cases (BP-100k-4-i).
    """
    registry, load_failure_reason = _load_registry()
    if registry is None:
        print(f"INDETERMINATE: reason={load_failure_reason}", file=sys.stderr)
        return 2

    hooks, hooks_failure_reason = _resolve_hooks_or_reason(registry)
    if hooks is None:
        print(f"INDETERMINATE: reason={hooks_failure_reason}", file=sys.stderr)
        return 2

    tracked_paths, tracked_failure_reason = _resolve_tracked_paths_or_reason(Path.cwd())
    if tracked_paths is None:
        print(f"INDETERMINATE: reason={tracked_failure_reason}", file=sys.stderr)
        return 2

    exemptions = validate_exemptions(
        registry.get("hook_trigger_reachability_exemption_registry", [])
    )

    counts = _evaluate_all_gates(hooks, tracked_paths, exemptions)
    if counts is None:
        return 2
    total, unreachable, exempt = counts

    print(
        f"{_GATE_NAME}: RESULT total={total} unreachable={unreachable} exempt={exempt}",
        file=sys.stderr,
    )

    return 1 if unreachable else 0


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-25 [python-coder/EPIC-BuildPipelinePhantomRemediation]:
#   BP-100k-4 / BP-100k-4-i: created module. Registry-wide reachability
#   verdict for every hooks_manifest entry: a files-triggered gate whose
#   pattern matches no tracked path, or a whole-tree (always_run) gate that
#   also carries a files filter, is reported UNREACHABLE and the run exits
#   1. An unreadable registry or an unobtainable tracked-path set is
#   INDETERMINATE (exit 2) — never a silent pass. Paired with fixing
#   check-build-drift's and check-output-drift's dead files triggers to
#   always_run: true in commit_guardian.json.
# - 2026-08-25 [python-coder/EPIC-BuildPipelinePhantomRemediation, r2]:
#   Coordinator review found two defects in r1. (1) check-infra-docs' files
#   trigger was CORRECT (docker-compose/Dockerfile patterns) but matched
#   zero tracked paths only because this package repo has no Docker
#   infrastructure — "no match today" != "cannot ever match", and deleting
#   the filter would make the gate unconditional in every consumer install
#   that DOES have such files. Restored the filter and added the
#   three-way reachable/exempt/unreachable vocabulary (reusing BP-100k-3's
#   EXEMPT-with-ground / REJECTED-groundless shape from
#   _drift_exemptions.py) via a new
#   hook_trigger_reachability_exemption_registry key; check-infra-docs is
#   now declared exempt with a stated ground instead of unconditional.
#   (2) Consumer blast-radius check: check-paths-integrity and
#   check-architecture-scaffolds target the package's OWN internal files
#   (config/paths.json, templates/docs/architecture/); in a consumer
#   install where the vendored package directory is untracked/gitignored/
#   a submodule, these have zero tracked matches and would otherwise block
#   EVERY consumer commit forever. Verified via a synthetic consumer-layout
#   fixture (untracked package subtree) against the deployed hook. Also
#   corrected the consumer-layout alternation from the wrong `leafcutter/`
#   prefix to the documented `leafcutter-ai/` (CLAUDE.md "Repository
#   Structure"), and declared both gates exempt with a stated ground for
#   the same reason as check-infra-docs, so a correct-but-context-
#   dependent trigger can never become a universal commit-blocker.
# - 2026-08-26 [python-coder/EPIC-BuildPipelinePhantomRemediation, r2
#   hardening]: An adversarial logic review that EXECUTED this gate (not
#   just read it) found five defects — the charter defect ("a check that
#   cannot perform its check reporting a pass") recurring inside the check
#   written to police it:
#   (F5) an exemption entry keyed on the "<unknown>" display sentinel
#   silenced EVERY id-less gate at once, and a duplicated hooks-manifest id
#   let one exemption entry cover two distinct gates. Fixed by never
#   defaulting a missing id to the sentinel for LOOKUP purposes (only for
#   display), rejecting sentinel-keyed exemption entries outright, and
#   detecting duplicate ids up front so a duplicate can never resolve to
#   "exempt" — it is reported (`DUPLICATE-ID: ...`) and forced unreachable
#   instead.
#   (F6) a deployed registry that EXISTS but fails to parse fell through to
#   the colocated source copy and reported a clean pass against a registry
#   that was not the one pre-commit would actually run. `_load_registry` now
#   distinguishes "no candidate exists" (try the next one) from "a candidate
#   exists but is corrupt" (stop, INDETERMINATE) — mirrors the F2 finding
#   already known for the sibling drift gates.
#   (F7) an empty (or all-disabled/non-dict) `hooks_manifest.hooks` list
#   exited 0 with `total=0` — a run that inspected zero gates reported
#   clean. Added the same `verified == 0`-shaped floor BP-100k-3 uses for
#   the drift gates: zero evaluable entries is now INDETERMINATE.
#   (M) a repository with a successfully-empty tracked-path set (fresh
#   clone/submodule/shallow checkout before the first `git add`) was
#   evaluated as if the empty set were proof every files-triggered gate is
#   unreachable, rather than as "no evidence either way". Now INDETERMINATE.
#   (M) an unbounded `re.search` let a catastrophic-backtracking `files`
#   pattern hang the process forever with no verdict. Bounded with a
#   SIGALRM-based wall-clock guard (`search_any_with_timeout`, default 2s,
#   overridable via HOOK_TRIGGER_REGEX_TIMEOUT_SECONDS for tests only);
#   exceeding the bound is INDETERMINATE, never a pass.
#   Exemption validation, the per-gate rule, and the timeout guard were
#   split into the new sibling module _hook_trigger_reachability_helpers.py
#   to stay under the 400-line file-size limit after this round's additions.
#   F8 (an empty-but-present `commands/` directory passing
#   `check_command_reachability`) is a DIFFERENT gate in
#   scripts/build_phases.py, out of this module's scope — not addressed
#   here. See /tmp/review_logic_round2.md and /tmp/review_code_round2.md.
# ====================================================================
