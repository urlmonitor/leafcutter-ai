"""
MODULE: scripts/build_orchestration/path_selection.py
GOAL: Decide which build pipeline lane (fast or heavy) to invoke for a
    given ticket, based on a single documented rule (BO-2400b-3).
BUSINESS CONTEXT: Leafcutter supports two quality pipelines: the fast lane
    (low-overhead checks for small, interactive, low-risk work) and the heavy
    lane (full verification suite for large, unattended, or high-risk work).
    Routing must be deterministic and auditable — every decision records a
    human-readable reason so the choice can be reviewed without re-running the
    rule.
ARCHITECTURE: Single pure function choose_lane(); no I/O, no global mutable
    state, no external calls. The function is the authoritative encoding of
    the documented rule BO-2400b-3 and its sub-rules BO-2400b-3-i (ambiguous
    scope defaults heavy) and BO-2400b-3-ii (explicit override wins).
    Callers that need to persist or log the decision own the I/O boundary.
"""

from __future__ import annotations

_VALID_LANES = frozenset({"fast", "heavy"})


def choose_lane(
    *,
    scope: str,
    attended: bool,
    defect_cost: str,
    override: str | None = None,
) -> dict:
    """Select the build pipeline lane for a ticket (BO-2400b-3).

    Decision rule — evaluated in two steps:

    Step 1 — Override check (unconditional win, BO-2400b-3-ii):
        If ``override`` is "fast" or "heavy", that lane is used unconditionally.
        ``overridden`` is set to True and ``reason`` names both the override
        and what the rule would have computed, making the supersession auditable.

    Step 2 — Documented single rule (no override supplied):

        FAST lane iff ALL of the following hold:
            * ``scope == "scoped"``     — small blast radius
            * ``attended is True``      — interactive, human-attended build
            * ``defect_cost == "low"``  — low cost of an escaped defect

        HEAVY lane when ANY of the following is true:
            * ``scope == "large"``      — large blast radius
            * ``attended is False``     — unattended / batch build
            * ``defect_cost == "high"`` — high cost of an escaped defect

        AMBIGUOUS scope (BO-2400b-3-i):
            When ``scope`` is neither "scoped" nor "large", the scope is
            unrecognized. The rule defaults to the heavy lane (fail-closed)
            and sets ``ambiguous = True`` so callers can surface the warning.

    Parameters
    ----------
    scope:
        Blast-radius classification of the ticket. Recognized values are
        "scoped" (small) and "large". Any other value is treated as ambiguous
        and routes heavy.
    attended:
        True if the build is interactive and human-attended; False for
        unattended / batch mode.
    defect_cost:
        Cost of an escaped defect reaching production. Recognized values are
        "low" and "high".
    override:
        Explicit lane override. When set to "fast" or "heavy", the override
        wins unconditionally over the rule. None (default) means no override.

    Returns
    -------
    dict with keys:
        ``lane``       str  — "fast" or "heavy"
        ``reason``     str  — Human-readable explanation of the routing decision.
        ``ambiguous``  bool — True iff the scope was unrecognized and the heavy
                              default was applied (BO-2400b-3-i).
        ``overridden`` bool — True iff an explicit override was supplied and
                              applied (BO-2400b-3-ii).
    """
    rule_lane, rule_reason, rule_ambiguous = _apply_rule(scope, attended, defect_cost)

    if override in _VALID_LANES:
        reason = (
            f"Lane overridden to '{override}' (rule would have selected '{rule_lane}'). "
            f"Rule basis: {rule_reason}"
        )
        return {
            "lane": override,
            "reason": reason,
            "ambiguous": rule_ambiguous,
            "overridden": True,
        }

    return {
        "lane": rule_lane,
        "reason": rule_reason,
        "ambiguous": rule_ambiguous,
        "overridden": False,
    }


def _apply_rule(scope: str, attended: bool, defect_cost: str) -> tuple[str, str, bool]:
    """Compute the rule-based lane, reason, and ambiguous flag (no override logic).

    Returns a 3-tuple: (lane, reason, ambiguous).
    """
    if scope not in ("scoped", "large"):
        reason = (
            f"Ambiguous scope {scope!r}: unrecognized value (not 'scoped' or 'large'); "
            "defaulting to the heavy pipeline (fail-closed, BO-2400b-3-i)."
        )
        return "heavy", reason, True

    if scope == "scoped" and attended is True and defect_cost == "low":
        reason = (
            "Fast lane: all conditions met — scope is 'scoped', build is attended, "
            "and defect cost is 'low'."
        )
        return "fast", reason, False

    triggers: list[str] = []
    if scope == "large":
        triggers.append("scope is 'large' (large blast radius)")
    if not attended:
        triggers.append("build is unattended")
    if defect_cost == "high":
        triggers.append("defect cost is 'high'")

    reason = "Heavy pipeline selected because: " + "; ".join(triggers) + "."
    return "heavy", reason, False
