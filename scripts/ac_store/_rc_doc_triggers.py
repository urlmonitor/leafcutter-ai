"""
MODULE: _rc_doc_triggers
GOAL: Rule family "documentation trigger to documentation requirement mapping": every
    documentation trigger on an L1 has a documentation requirement for its specialist in
    the checked folder; an uncovered trigger is reported, no record is ever created.
BUSINESS CONTEXT: ACD-2500a-2-v. The product owner sets documentation triggers on an L1;
    this rule check (not the IT PO template) owns whether each has a requirement.
ARCHITECTURE: Pure `evaluate_record`, L1 records only. The trigger-to-specialist map
    lives HERE, in one place (TRIGGER_SPECIALISTS): how-to and reference-doc ->
    documentation-expert; sequence-diagram, state-diagram, component-diagram ->
    architecture-diagram-author. Counting is per specialist (architect note D4): a trigger
    is covered when any record other than the L1 has `assigned_agent` equal to its
    specialist. An L1 with `documentation_triggers: []` and no `documentation_rationale`
    is reported; an absent or null key (legacy L1) is not. A trigger absent from the map is `failed` (never silent). Deployed flat.

DECISION HISTORY:
  - 2026-10-14 [python-coder/ACD-2500a-2-v]: Created (ticket 14). The map is kept in this
    module (decision D1 allowed a schema annotation only if the tests read it; they do not).
"""

from __future__ import annotations

from typing import Any

from _rc_report import DISPOSITION_DECISION, DISPOSITION_FAILED, FAMILY_DOC_TRIGGERS, Finding

NAME = FAMILY_DOC_TRIGGERS

_DOC_AGENT = "documentation-expert"
_DIAGRAM_AGENT = "architecture-diagram-author"
TRIGGER_SPECIALISTS = {
    "how-to": _DOC_AGENT,
    "reference-doc": _DOC_AGENT,
    "sequence-diagram": _DIAGRAM_AGENT,
    "state-diagram": _DIAGRAM_AGENT,
    "component-diagram": _DIAGRAM_AGENT,
}


def evaluate_record(ctx: Any, record: Any) -> list[Finding]:
    """One `needs a decision` per uncovered trigger (or empty-without-rationale L1); `failed` for an unmapped trigger."""
    if record.get("level") != "L1":
        return []
    triggers = record.get("documentation_triggers")
    if not isinstance(triggers, list):
        return []
    rid = str(record["id"])
    if not triggers:
        if str(record.get("documentation_rationale") or "").strip():
            return []
        message = f"{rid} declares no documentation triggers and states no documentation_rationale"
        return [Finding.for_record(record, NAME, DISPOSITION_DECISION, message, subject="empty-triggers")]
    assigned = {other.get("assigned_agent") for other in ctx.peers(record) if other["id"] != record["id"]}
    found: list[Finding] = []
    for trigger in dict.fromkeys(t for t in triggers if isinstance(t, str)):
        specialist = TRIGGER_SPECIALISTS.get(trigger)
        if specialist is None:
            message = f"documentation trigger {trigger!r} on {rid} maps to no specialist; the check cannot judge it"
            found.append(Finding.for_record(record, NAME, DISPOSITION_FAILED, message, subject=trigger))
            continue
        if specialist in assigned:
            continue
        message = (
            f"documentation trigger {trigger!r} on {rid} has no documentation requirement: "
            f"no record in the folder is assigned {specialist}"
        )
        found.append(Finding.for_record(record, NAME, DISPOSITION_DECISION, message, subject=trigger))
    return found
