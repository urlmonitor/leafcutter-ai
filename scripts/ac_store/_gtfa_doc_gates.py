#!/usr/bin/env python3
"""
MODULE: _gtfa_doc_gates
GOAL: Decide, from ``config/guardrail_gates.yaml`` alone, whether a generated
    ticket must carry the documentation-expert / documentation-verifier pair.
BUSINESS CONTEXT: Whether a change demands documentation is a policy question,
    and the policy lives entirely in config — no trigger value is hard-coded in
    the generator, so adding or retiring one is a configuration edit. There are
    three dimensions and they are not symmetrical: two positive triggers OR'd
    together, and one explicit negative guard that can cancel them.
ARCHITECTURE: The subtlety worth the separate module is Dimension 3's union
    semantics (BO-2200a-4). For a list-valued ``change_target``, a
    ``non_triggering`` entry matching ONE element must not cancel the demand
    raised by a DIFFERENT element — so when Dimension 1 is the source of the
    demand, suppression applies only if EVERY triggering element is covered.
    When the demand came from Dimension 2 (risk_surface) instead, the original
    scalar rule applies: any covered change_target suppresses. Collapsing the
    two into one rule is what the BO-2200a-4 fix exists to prevent.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

# See the "Sibling wiring" note in generate_ticket_from_ac.py for why the
# sibling package prefix is derived from __name__ rather than hard-coded.
_PKG = __name__.rpartition(".")[0]
_gtfa_seams = importlib.import_module(f"{_PKG}._gtfa_seams" if _PKG else "_gtfa_seams")

logger = logging.getLogger(_gtfa_seams.logger_name())


def _doc_gate_triggers(
    doc_gates_policy: dict[str, Any],
    change_targets: list[str],
    risk_surface: "str | None",
) -> tuple[bool, set[str], set[str]]:
    """Evaluate the two positive documentation trigger dimensions.

    Dimension 1 (BO-2200a-1): ``change_target_triggers`` — documentation-expert
    is required when any change_target intersects the trigger list.

    Dimension 2 (BO-2200a-2): ``risk_surface_triggers`` — documentation-expert
    is required when risk_surface matches any entry in the trigger list,
    independently of the change_target dimension (OR semantics).

    Both trigger lists are read from config at call-time — no hard-coded set
    exists in the generator — so adding or removing a triggering value is a
    configuration edit only.

    Args:
        doc_gates_policy: The ``documentation_gates`` section of the gates config.
        change_targets: The call's change_target list.
        risk_surface: The call's risk_surface.

    Returns:
        ``(triggered, doc_change_triggers, triggering_via_change_target)`` —
        whether documentation-expert is demanded, the configured Dimension-1
        trigger set, and the subset of *change_targets* that raised the demand
        through Dimension 1 (empty when only Dimension 2 fired).
    """
    doc_change_triggers: set[str] = set(
        doc_gates_policy.get("change_target_triggers") or []
    )
    triggering_via_change_target: set[str] = set()
    triggered = False
    if doc_change_triggers and set(change_targets) & doc_change_triggers:
        triggering_via_change_target = set(change_targets) & doc_change_triggers
        triggered = True

    doc_risk_triggers: set[str] = set(
        doc_gates_policy.get("risk_surface_triggers") or []
    )
    if doc_risk_triggers and risk_surface and risk_surface in doc_risk_triggers:
        triggered = True

    return triggered, doc_change_triggers, triggering_via_change_target


def _doc_gate_suppressed(
    doc_gates_policy: dict[str, Any],
    change_targets: list[str],
    risk_surface: "str | None",
    triggering_via_change_target: set[str],
) -> bool:
    """Evaluate Dimension 3 — the explicit ``non_triggering_classifications`` guard.

    BO-2200a-3: an explicit negative rule that removes documentation-expert when
    the call's (change_target, risk_surface) pair matches any entry in the
    exclusion list, even if the trigger dimensions above would otherwise add it.
    This ensures purely internal refactors never impose a documentation burden
    regardless of any future expansion of the trigger lists.

    Union semantics (BO-2200a-4): for list-valued change_targets, a
    non_triggering entry for one element must NOT cancel the trigger raised
    by a DIFFERENT element.  When Dimension 1 (change_target_triggers) is
    the source of the documentation demand, suppression only applies when
    EVERY triggering element is covered by a non_triggering entry for the
    current risk_surface.

    Args:
        doc_gates_policy: The ``documentation_gates`` section of the gates config.
        change_targets: The call's change_target list.
        risk_surface: The call's risk_surface.
        triggering_via_change_target: The change_target elements that raised
            the demand through Dimension 1; empty when only Dimension 2 fired.

    Returns:
        True when documentation-expert must be discarded.
    """
    non_triggering: list = list(
        doc_gates_policy.get("non_triggering_classifications") or []
    )
    if not non_triggering:
        return False

    # Collect the set of change_target values covered by a non_triggering
    # entry for the current risk_surface.
    suppressed_targets: set[str] = {
        str(entry["change_target"])
        for entry in non_triggering
        if isinstance(entry, dict)
        and entry.get("change_target")
        and entry.get("risk_surface") == risk_surface
    }

    if triggering_via_change_target:
        # documentation-expert was triggered by at least one change_target
        # element via Dimension 1.  Union semantics (BO-2200a-4): suppress
        # only when EVERY triggering change_target element is covered by a
        # non_triggering entry for this risk_surface.  A match on one list
        # element must NOT cancel the trigger raised by a different element.
        return not (triggering_via_change_target - suppressed_targets)

    # documentation-expert was triggered by risk_surface_triggers only
    # (Dimension 2).  Apply the original scalar suppression: if any
    # change_target for this call has a non_triggering entry for the
    # current risk_surface, suppress.
    return any(ct in suppressed_targets for ct in change_targets)


def apply_documentation_gates(
    gates: dict[str, Any],
    change_targets: list[str],
    risk_surface: "str | None",
    guardrail_set: set[str],
) -> None:
    """Add or withhold the documentation phase pair on *guardrail_set*, in place.

    Runs the two positive trigger dimensions, then the negative guard, then —
    only if documentation-expert survived — injects documentation-verifier as
    its companion verification phase (BO-2200b-4). Both agents are gated on the
    same trigger decision, so removing documentation-expert via
    ``non_triggering_classifications`` also removes documentation-verifier,
    because the inject below is only reached when documentation-expert remains.

    Args:
        gates: The parsed guardrail gates config.
        change_targets: The call's change_target list.
        risk_surface: The call's risk_surface.
        guardrail_set: The accumulating set of guardrail agent names, mutated
            in place.
    """
    doc_gates_policy = gates.get("documentation_gates") or {}

    triggered, _doc_change_triggers, triggering_via_change_target = _doc_gate_triggers(
        doc_gates_policy, change_targets, risk_surface
    )
    if triggered:
        guardrail_set.add("documentation-expert")

    if "documentation-expert" in guardrail_set and _doc_gate_suppressed(
        doc_gates_policy, change_targets, risk_surface, triggering_via_change_target
    ):
        guardrail_set.discard("documentation-expert")

    if "documentation-expert" in guardrail_set:
        guardrail_set.add("documentation-verifier")
