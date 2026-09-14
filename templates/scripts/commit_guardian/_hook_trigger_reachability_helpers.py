"""
MODULE: _hook_trigger_reachability_helpers
GOAL: Per-gate reachability rule, exemption-registry validation, and the
    wall-clock-bounded regex match used by check_hook_trigger_reachability.py
    (BP-100k-4 / BP-100k-4-i / BP-100k-4-ii). Split out of the hook module
    itself purely to stay under the project's 400-line file-size limit
    (mirrors the build_phases.py / build_helpers.py and check_build_drift.py
    / check_output_drift.py / _drift_exemptions.py split precedents) — there
    is exactly one caller and no independent versioning concern.
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

    BP-100k-4-ii (KI-CG-20260831-0713): the reachability rule then went too
    far the OTHER direction — a ``files`` condition that selects paths by
    KIND (an extension or filename family, e.g. ``\\.py$``) and matches zero
    of THIS checkout's tracked paths was reported UNREACHABLE exactly like a
    condition naming a location no checkout could ever produce, blocking the
    first commit of any adopter that has not yet added a file of that kind
    (e.g. a fresh TypeScript project with two registered Python-kind gates).
    ``has_location_anchor`` supplies the missing COULD-EVER/DOES-NOW
    distinction; ``evaluate_gate`` now reports the kind-based, zero-match
    case as a fourth "nothing_to_match" verdict instead.
ARCHITECTURE: ``validate_exemptions`` rejects both a groundless entry (mirrors
    ``_drift_exemptions.validate_exemption_registry``) AND an entry keyed on
    the unknown-gate display sentinel (new — an id-less hooks-manifest entry
    must never be exemptible, and the sentinel string used to DISPLAY such an
    entry must never double as a LOOKUP key). ``evaluate_gate`` is the
    four-way reachable/nothing_to_match/exempt/unreachable verdict for one
    hooks_manifest entry, using ``search_any_with_timeout`` instead of a bare
    ``any(compiled.search(p) for p in paths)`` so a catastrophic-backtracking
    pattern is bounded rather than left to hang. Duplicate-id detection lives
    in ``main()`` (it is a registry-wide, not per-gate, condition) — this
    module only guarantees that an id-less or duplicated gate can never
    resolve to "exempt" via the sentinel path; the duplicate-id override
    itself is applied by the caller once it knows which ids repeat.

    ``has_location_anchor`` (BP-100k-4-ii) draws the could-ever/does-now line
    on a single structural signal: every location-anchored condition already
    registered in commit_guardian.json is written with a regex
    start-of-string anchor (``^``) on each alternative that names a path
    (``^docs/.*\\.md$``, ``^(leafcutter-ai/)?config/paths\\.json$``), while
    every purely kind-based condition (``\\.py$``, ``.*\\.(md|py|sql)$``, the
    docker-infra alternation) never anchors to the start of the path at all
    — matching is deliberately position-independent.

    ORDERING CORRECTION (BP-100k-4-ii H-1): ``evaluate_gate`` consults the
    ``hook_trigger_reachability_exemption_registry`` FIRST, before
    ``has_location_anchor`` is ever reached. An entry that already carries a
    human-authored ``ground`` is an AUDITED decision and is honoured as
    "exempt" unconditionally — the ``^`` heuristic is a fallback used ONLY
    for patterns the registry says nothing about. This matters because the
    claim above ("every location-anchored condition ... carries a leading
    ^") is false for two real entries: ``check-doc-types-agents``
    (``(config/doc_types\\.json|config/agent_registry\\.json)``) and
    ``check-hook-parity`` (``scripts/commit_guardian/|templates/scripts/
    commit_guardian/|templates/commit-guardian/``) both name exact,
    audited-exempt locations with no anchor at all. Running the kind-based
    check first (the pre-fix ordering) reclassified both as
    "nothing_to_match" without ever reading their ``ground`` — harmless
    only by coincidence (neither was blocking either way today), but it
    means a future rename that made either pattern genuinely and
    permanently dead would still auto-pass as "nothing_to_match" instead of
    surfacing as "unreachable", reviving exactly the fail-open shape
    BP-100k-4-i exists to forbid. The heuristic itself was deliberately
    NOT widened to also recognise a bare substring naming a real package
    path as location-based — that would trade one fragile heuristic for a
    more fragile one and would misclassify again the next time someone
    writes an unusual pattern. The registry, not a pattern-shape heuristic,
    is the audited source of truth and must never be silently overridden.
    A kind-based condition matching zero tracked paths (and carrying no
    exemption entry) is reported "nothing_to_match" (never blocking, never
    needing a stated exemption ground); a location-anchored condition with
    no exemption entry is entirely unaffected and keeps flowing through the
    pre-existing unreachable path. ``kind_distinction_disabled`` is a
    test-only escape hatch (mirrors ``HOOK_TRIGGER_REGEX_TIMEOUT_SECONDS``)
    that reverts to the pre-fix behavior so the fix's own test suite can
    prove its assertions are capable of failing.
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

# Test-only override (BP-100k-4-ii): forces evaluate_gate back to its
# pre-fix behavior, where a kind-based "files" condition matching zero
# tracked paths is classified exactly like a location-anchored one. Exists
# solely as the mutation-proof control test_bp_100k_4_ii.py's
# TestRemovingTheDistinctionRestoresTheBlocker requires — production code
# never sets this variable. See kind_distinction_disabled().
KIND_DISTINCTION_DISABLE_ENV_VAR = "HOOK_TRIGGER_DISABLE_KIND_DISTINCTION"


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


def kind_distinction_disabled() -> bool:
    """Resolve whether the BP-100k-4-ii could-ever/does-now distinction is
    disabled for this run.

    Test-only override (mirrors ``regex_match_timeout_seconds``'s
    ``HOOK_TRIGGER_REGEX_TIMEOUT_SECONDS`` convention): when enabled,
    ``evaluate_gate`` never reports "nothing_to_match" — a kind-based
    ``files`` condition matching zero tracked paths falls through to the
    pre-BP-100k-4-ii exempt/unreachable path instead, exactly as it did
    before this fix. This exists purely so the fix's own test suite can
    prove its assertions are capable of failing (see test_bp_100k_4_ii.py's
    MUTATION-PROOF CONTRACT); production never sets this variable.

    Returns:
        True if ``HOOK_TRIGGER_DISABLE_KIND_DISTINCTION`` is set to "1",
        "true", or "yes" (case-insensitive); False otherwise, including
        when the variable is unset.
    """
    raw = os.environ.get(KIND_DISTINCTION_DISABLE_ENV_VAR, "")
    return raw.strip().lower() in ("1", "true", "yes")


def has_location_anchor(files_pattern: str) -> bool:
    r"""Determine whether a ``files`` regex pattern is location-anchored.

    BP-100k-4-ii: distinguishes a condition that selects paths by KIND (the
    shape of the file — an extension or a specific filename family, with no
    fixed position in the tree) from one that names a LOCATION (a directory
    or file path a checkout must place a match under). Every
    location-anchored condition already registered in commit_guardian.json
    is written with a leading ``^`` on each alternative that names a path
    (``^docs/.*\.md$``, ``^(leafcutter-ai/)?config/paths\.json$``,
    ``(^docs/product-truth/|^docs/acceptance-criteria/.*\.yaml$)``), while
    every purely kind-based condition (``\.py$``, ``.*\.(md|py|sql)$``, the
    docker-infra alternation) never anchors to the start of the path at all
    — matching is deliberately position-independent.

    A ``^`` that appears inside a bracket expression (``[^...]``, a negated
    character class) or is backslash-escaped (``\^``, a literal caret) is
    NOT a location anchor and is ignored.

    ORDERING NOTE (BP-100k-4-ii H-1 fix): this heuristic is a FALLBACK, only
    ever consulted by ``evaluate_gate`` for a pattern that has NO entry in
    ``hook_trigger_reachability_exemption_registry``. The claim above — that
    every location-anchored condition carries a leading ``^`` — is in fact
    false for two audited, real registry entries: ``check-doc-types-agents``
    (``(config/doc_types\.json|config/agent_registry\.json)``) and
    ``check-hook-parity`` (``scripts/commit_guardian/|templates/scripts/
    commit_guardian/|templates/commit-guardian/``) both name exact locations
    but carry no anchor at all. Both are exempt because they carry a
    human-authored ``ground`` in the exemption registry, which
    ``evaluate_gate`` now consults BEFORE this function is ever called —
    so this function's inaccuracy for those two ids is harmless: they never
    reach this heuristic. Do NOT "fix" this by widening the anchor check to
    catch more location-like substrings; that would replace one fragile
    heuristic with a more fragile one. The registry is the audited source of
    truth for any pattern it names; this function only draws the could-ever/
    does-now line for patterns the registry says nothing about.

    Args:
        files_pattern: The raw ``files`` regex string from a hooks_manifest
            entry.

    Returns:
        True if the pattern contains at least one un-escaped, out-of-bracket
        ``^`` (location-anchored — this AC's classification is unchanged for
        it); False if it contains none (kind-based — eligible for the
        "nothing_to_match" classification when it matches zero tracked
        paths).
    """
    in_bracket = False
    index = 0
    length = len(files_pattern)
    while index < length:
        char = files_pattern[index]
        if char == "\\" and index + 1 < length:
            index += 2
            continue
        if char == "[" and not in_bracket:
            in_bracket = True
        elif char == "]" and in_bracket:
            in_bracket = False
        elif char == "^" and not in_bracket:
            return True
        index += 1
    return False


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
        (detail is None), "exempt" (detail is the ground text — BP-100k-4-ii
        H-1 fix: the exemption registry is consulted BEFORE the kind-based
        check below, so any entry carrying a human-authored ``ground`` is
        honoured regardless of whether its pattern happens to be anchored),
        "nothing_to_match" (BP-100k-4-ii: detail is the free-text reason —
        a kind-based condition, no location anchor, AND no exemption entry,
        matching zero tracked paths; never blocks, never needs a stated
        exemption ground), or "unreachable" (detail is the free-text
        reason).

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

    # BP-100k-4-ii ORDERING CORRECTION (H-1): the exemption registry is
    # consulted FIRST, before the kind-based has_location_anchor() check is
    # ever reached. An entry that already carries a human-authored `ground`
    # is an AUDITED decision — it must be honoured as EXEMPT regardless of
    # whether its pattern happens to carry a leading `^`. has_location_
    # anchor()'s docstring claimed every location-anchored condition in
    # commit_guardian.json carries such an anchor; that is false for
    # check-doc-types-agents ("(config/doc_types\.json|config/agent_registry
    # \.json)") and check-hook-parity ("scripts/commit_guardian/|templates/
    # scripts/commit_guardian/|templates/commit-guardian/") — both are
    # audited, exact-location exemption entries with no anchor at all. Under
    # the pre-fix ordering, the kind-based check ran first and reclassified
    # both as NOTHING-TO-MATCH before their `ground` was ever consulted:
    # today's exit code was unaffected (neither blocked before), but if
    # either pattern were later broken by a rename — genuinely and
    # permanently dead — the gate would still auto-classify it
    # NOTHING-TO-MATCH and pass, silently reviving the exact fail-open shape
    # BP-100k-4-i exists to forbid. See this module's DECISION HISTORY.
    ground = exemptions.get(gate_id) if gate_id else None
    if ground:
        return ("exempt", ground)

    # Only a pattern with NO exemption entry falls through to the
    # could-ever/does-now classification. A kind-based condition (no
    # location anchor) matching zero tracked paths is a gate with nothing
    # to do today, not a gate that could never fire. A location-anchored
    # condition (has an anchor) is unaffected and falls straight through to
    # the unreachable verdict below, exactly as before this AC.
    if not kind_distinction_disabled() and not has_location_anchor(files_pattern):
        return (
            "nothing_to_match",
            f"files pattern {files_pattern!r} selects by file kind (no "
            "location anchor) and matches none of the "
            f"{len(tracked_paths)} path(s) this repository tracks yet — a "
            "checkout that later acquires a file of this kind would "
            "activate it, so this is not a structurally unreachable gate",
        )

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
# - 2026-09-07 [python-coder/BP-100k-4-ii] (KI-CG-20260831-0713): a
#   kind-based files condition (no location anchor, e.g. "\.py$") matching
#   zero of THIS checkout's tracked paths was reported UNREACHABLE exactly
#   like a condition naming a location no checkout could ever produce,
#   blocking the first commit of any adopter that has not yet acquired a
#   file of that kind (e.g. a fresh TypeScript project tripping over
#   check-placeholder-defaults / check-exception-handling). Added
#   has_location_anchor() (the could-ever/does-now line, drawn on the
#   regex start-of-string anchor) and a fourth "nothing_to_match" verdict
#   in evaluate_gate, checked BEFORE the exemption registry and requiring
#   no stated ground. A location-anchored condition is untouched by this
#   change. kind_distinction_disabled() (HOOK_TRIGGER_DISABLE_KIND_
#   DISTINCTION=1) is a test-only escape hatch restoring the pre-fix
#   behavior, required by test_bp_100k_4_ii.py's mutation-proof test.
#   (#BP-100k-4-ii)
# - 2026-09-07 [python-coder/BP-100k-4-ii, review finding H-1]: an
#   adversarial review found that has_location_anchor()'s docstring claim —
#   "every location-anchored condition in commit_guardian.json carries a
#   leading ^" — is false for 2 of the 8 hook_trigger_reachability_
#   exemption_registry entries: check-doc-types-agents
#   ("(config/doc_types\.json|config/agent_registry\.json)") and
#   check-hook-parity ("scripts/commit_guardian/|templates/scripts/
#   commit_guardian/|templates/commit-guardian/") both name exact, audited
#   locations but carry no anchor. Because evaluate_gate ran the kind-based
#   check BEFORE consulting the exemption registry, both were silently
#   reclassified NOTHING-TO-MATCH and their human-authored ground was never
#   read — today's exit code was unaffected (neither blocked before), but a
#   future rename making either pattern genuinely, permanently dead would
#   still auto-pass as NOTHING-TO-MATCH, reviving the exact fail-open shape
#   BP-100k-4-i forbids. FIXED by taking the ORDERING option: evaluate_gate
#   now consults the exemption registry FIRST — any entry with a
#   human-authored ground is honoured as EXEMPT unconditionally, before
#   has_location_anchor is ever reached. The HEURISTIC option (widening
#   has_location_anchor to also treat a bare substring naming a real
#   package path as location-based) was explicitly REJECTED: it would
#   replace one fragile heuristic with a more fragile one and would
#   misclassify again the next time someone authors an unusual pattern —
#   the registry, not a pattern-shape heuristic, is the audited source of
#   truth and must never be silently overridden by one. Everything BP-
#   100k-4-ii already got right is unchanged: a kind-based condition with
#   NO exemption entry, matching nothing yet, is still NOTHING-TO-MATCH and
#   non-blocking; a location-based condition with no exemption entry that
#   no checkout could ever produce is still UNREACHABLE and still blocks.
#   (#BP-100k-4-ii, H-1)
# ====================================================================
