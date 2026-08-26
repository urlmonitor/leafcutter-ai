"""
MODULE: _hook_trigger_reachability_helpers
GOAL: Per-gate reachability rule, exemption-registry validation, and the
    wall-clock-bounded regex match used by check_hook_trigger_reachability.py
    (BP-100k-4 / BP-100k-4-i). Split out of the hook module itself purely to
    stay under the project's 400-line file-size limit (mirrors the
    build_phases.py / build_helpers.py and check_build_drift.py /
    check_output_drift.py / _drift_exemptions.py split precedents) — there is
    exactly one caller and no independent versioning concern.
BUSINESS CONTEXT: BP-100k-4 round-2 hardening. An adversarial logic review
    that EXECUTED the reachability gate (not just read it) found that the
    exemption registry could be abused in ways the sibling drift-gate
    exemption registry (``_drift_exemptions.py``) had already been hardened
    against, and that an unbounded regex match let a pathological ``files``
    pattern hang the pre-commit hook indefinitely with no verdict at all.
    Both defects are the epic's own charter defect recurring one level up: a
    check that cannot perform its check reporting a pass (or, for the regex
    case, reporting nothing at all). See /tmp/review_logic_round2.md (F5) and
    check_hook_trigger_reachability.py's DECISION HISTORY for the full
    account.
ARCHITECTURE: ``validate_exemptions`` rejects both a groundless entry (mirrors
    ``_drift_exemptions.validate_exemption_registry``) AND an entry keyed on
    the unknown-gate display sentinel (new — an id-less hooks-manifest entry
    must never be exemptible, and the sentinel string used to DISPLAY such an
    entry must never double as a LOOKUP key). ``evaluate_gate`` is the
    three-way reachable/exempt/unreachable verdict for one hooks_manifest
    entry, using ``search_any_with_timeout`` instead of a bare
    ``any(compiled.search(p) for p in paths)`` so a catastrophic-backtracking
    pattern is bounded rather than left to hang. Duplicate-id detection lives
    in ``main()`` (it is a registry-wide, not per-gate, condition) — this
    module only guarantees that an id-less or duplicated gate can never
    resolve to "exempt" via the sentinel path; the duplicate-id override
    itself is applied by the caller once it knows which ids repeat.
"""

from __future__ import annotations

import os
import re
import signal
import sys

# The display fallback used for a hooks-manifest entry with no "id" field.
# Kept as a single named constant specifically so it can be checked against
# exemption-entry ids and rejected there — it must never be usable as an
# exemption LOOKUP key, only as human-readable display text for an id-less
# entry's own diagnostics.
UNKNOWN_GATE_ID_SENTINEL = "<unknown>"

# Wall-clock bound on evaluating one gate's "files" regex against the
# tracked-path set. Overridable via HOOK_TRIGGER_REGEX_TIMEOUT_SECONDS for
# tests only (mirrors the HOOK_TEST_CONFIG convention) — production always
# uses the default.
DEFAULT_REGEX_MATCH_TIMEOUT_SECONDS = 2.0


class RegexTimeoutError(Exception):
    """Raised when a "files" pattern match exceeds its wall-clock bound.

    Signals that reachability for the gate being evaluated could not be
    determined in time — never that the gate is reachable or unreachable.
    """


def regex_match_timeout_seconds() -> float:
    """Resolve the wall-clock bound for one gate's regex match.

    Returns:
        The timeout in seconds: ``HOOK_TRIGGER_REGEX_TIMEOUT_SECONDS`` if set
        to a valid positive float, else ``DEFAULT_REGEX_MATCH_TIMEOUT_SECONDS``.
    """
    raw = os.environ.get("HOOK_TRIGGER_REGEX_TIMEOUT_SECONDS")
    if not raw:
        return DEFAULT_REGEX_MATCH_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_REGEX_MATCH_TIMEOUT_SECONDS
    return value if value > 0 else DEFAULT_REGEX_MATCH_TIMEOUT_SECONDS


def search_any_with_timeout(compiled: re.Pattern, paths: list[str]) -> bool:
    """Run ``any(compiled.search(p) for p in paths)`` under a wall-clock bound.

    A pathological (catastrophic-backtracking) pattern can make a single
    ``re.search`` call run effectively forever. This is bounded with a
    POSIX ``SIGALRM``-based wall-clock guard so the gate reports a condition
    instead of hanging the pre-commit hook indefinitely, which is
    indistinguishable from a crash to a developer.

    Args:
        compiled: The compiled "files" regex.
        paths: Tracked paths to search against.

    Returns:
        True if any path matches within the time budget.

    Raises:
        RegexTimeoutError: If the match does not complete within the bound.
    """
    if not hasattr(signal, "SIGALRM"):
        # Non-POSIX platform (e.g. Windows): no wall-clock guard is
        # available. This hook is deployed to POSIX pre-commit environments
        # only, so running unbounded here is a documented, narrow gap rather
        # than a silent pass — the regex still evaluates and reports
        # normally, it is only the hang-protection that is unavailable.
        return any(compiled.search(p) for p in paths)

    def _on_alarm(signum: int, frame: object) -> None:
        raise RegexTimeoutError()

    timeout_seconds = regex_match_timeout_seconds()
    previous_handler = signal.signal(signal.SIGALRM, _on_alarm)
    signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        return any(compiled.search(p) for p in paths)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def validate_exemptions(entries: object) -> dict[str, str]:
    """Split raw hook_trigger_reachability_exemption_registry entries.

    Mirrors ``_drift_exemptions.validate_exemption_registry`` (BP-100k-3):
    an entry whose ``ground`` is missing, empty, or whitespace-only is
    REJECTED rather than silently honoured, so its gate falls through to
    the un-exempted UNREACHABLE verdict.

    BP-100k-4 round-2 hardening (F5): an entry whose ``id`` is the
    ``UNKNOWN_GATE_ID_SENTINEL`` display placeholder is ALSO rejected. That
    string is not any single gate's real id — it is what an id-less
    hooks-manifest entry is displayed as — so honouring it as a lookup key
    would let one exemption entry silence every id-less gate in the
    registry at once.

    Args:
        entries: The raw value of the registry's
            ``hook_trigger_reachability_exemption_registry`` key (expected
            to be a list of ``{"id": <gate-id>, "ground": <text>}`` dicts;
            any other shape yields an empty exemption map).

    Returns:
        Mapping of gate id to non-blank ground text, for valid entries only.
    """
    valid: dict[str, str] = {}
    if not isinstance(entries, list):
        return valid
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        gate_id = entry.get("id")
        if not gate_id:
            continue
        if gate_id == UNKNOWN_GATE_ID_SENTINEL:
            print(
                f"REJECTED EXEMPTION ENTRY: {gate_id} reason=id is the "
                "reserved unknown-gate display sentinel, not a real gate id "
                "— it can never be a valid exemption target",
                file=sys.stderr,
            )
            continue
        ground = entry.get("ground", "")
        if isinstance(ground, str) and ground.strip():
            valid[gate_id] = ground.strip()
        else:
            print(
                f"REJECTED EXEMPTION ENTRY: {gate_id} reason=no ground stated",
                file=sys.stderr,
            )
    return valid


def evaluate_gate(
    entry: dict, tracked_paths: list[str], exemptions: dict[str, str]
) -> tuple[str, str | None]:
    """Evaluate one hooks_manifest entry's reachability.

    Args:
        entry: One entry from ``hooks_manifest.hooks``.
        tracked_paths: The repository's tracked paths (``git ls-files``
            output).
        exemptions: Valid gate-id -> ground map from ``validate_exemptions``.

    Returns:
        A ``(verdict, detail)`` pair. ``verdict`` is one of "reachable"
        (detail is None), "exempt" (detail is the ground text), or
        "unreachable" (detail is the free-text reason).

    Raises:
        RegexTimeoutError: If matching the "files" pattern against every
            tracked path does not complete within the wall-clock bound
            (BP-100k-4 round-2 hardening, catastrophic-backtracking finding).
            Propagated to the caller (``main()``), which is the correct I/O
            boundary to report this at — this function stays pure otherwise.
    """
    always_run = bool(entry.get("always_run"))
    files_pattern = entry.get("files")
    # BP-100k-4 round-2 hardening (F5): the raw id, NOT defaulted to the
    # display sentinel — an id-less entry must never be able to match an
    # exemption, and `dict.get(None)` on a str-keyed dict is always None, so
    # leaving this as-is (rather than substituting the sentinel) is what
    # makes that structurally true rather than merely documented.
    gate_id = entry.get("id")

    if always_run and files_pattern:
        return (
            "unreachable",
            "whole-tree gate (always_run: true, never consults the staged "
            f"file list) also carries a files filter it never consults: "
            f"{files_pattern!r}",
        )
    if always_run:
        return ("reachable", None)
    if not files_pattern:
        return ("reachable", None)

    try:
        compiled = re.compile(files_pattern)
    except re.error as exc:
        return ("unreachable", f"files pattern {files_pattern!r} is not a valid regex: {exc}")

    if search_any_with_timeout(compiled, tracked_paths):
        return ("reachable", None)

    ground = exemptions.get(gate_id) if gate_id else None
    if ground:
        return ("exempt", ground)
    return (
        "unreachable",
        f"files pattern {files_pattern!r} matches none of the "
        f"{len(tracked_paths)} path(s) this repository tracks",
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-26 [python-coder/EPIC-BuildPipelinePhantomRemediation, r2
#   hardening]: Split out of check_hook_trigger_reachability.py to stay
#   under the 400-line file-size limit while adding BP-100k-4 round-2
#   hardening (F5 exemption abuse, catastrophic-backtracking wall-clock
#   guard). See check_hook_trigger_reachability.py's own DECISION HISTORY
#   for the full account of what changed and why.
# ====================================================================
