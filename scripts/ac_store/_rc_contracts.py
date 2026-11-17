"""
MODULE: _rc_contracts
GOAL: Rule family "producer/consumer contract symmetry": a delivery nobody expects and an
    expectation nobody delivers are reported with both ends named; contracts are never
    completed.
BUSINESS CONTEXT: ACD-2500a-2-iii / architect note D3. Whether two contract descriptions
    MEAN the same thing is judgement that stays with the planner, so the check is
    presence-only and never adds, removes or compares contract text.
ARCHITECTURE: Pure `evaluate_record`. `expects_from` and `delivers_to` may each be null,
    a string, an object or a list; `_normalise` reduces them to a list of ids (expects) or
    agent names (delivers); a string `expects_from` is an AC id, a string `delivers_to` an
    agent name. Rule 1: every expected id must exist STORE-WIDE (`ctx.sibling`, then
    `ctx.store_record`) and declare a non-empty `delivers_to`. Rule 2: every delivery
    naming an agent needs a record in the CHECKED folder assigned that agent whose
    `expects_from` names this record. Deliberately does not reuse
    `_gtfa_store._expects_from_ac_ids`. Deployed flat.

DECISION HISTORY:
  - 2026-10-14 [python-coder/ACD-2500a-2-iii]: Created (ticket 12).
"""

from __future__ import annotations

from typing import Any

from _rc_report import DISPOSITION_DECISION, FAMILY_CONTRACTS, Finding

NAME = FAMILY_CONTRACTS


def _normalise(value: Any, key: str) -> list[str]:
    """The ids/agent names a contract field names, over all four shapes (`key` is the object key)."""
    items = value if isinstance(value, list) else [value]
    names: list[str] = []
    for item in items:
        name = item.get(key) if isinstance(item, dict) else item
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return names


def _expects_finding(ctx: Any, record: Any, producer_id: str) -> Finding | None:
    """A finding when the expected producer is unknown or declares no delivery."""
    rid = str(record["id"])
    producer = ctx.sibling(producer_id) or ctx.store_record(producer_id)
    if producer is None:
        message = f"{rid} expects a contract from {producer_id}, which does not exist in the store"
    elif not _normalise(producer.get("delivers_to"), "agent"):
        message = f"{rid} expects a contract from {producer_id}, but {producer_id} declares no delivery (delivers_to is empty)"
    else:
        return None
    return Finding.for_record(record, NAME, DISPOSITION_DECISION, message, subject=f"expects:{producer_id}")


def _has_consumer(ctx: Any, record: Any, agent: str) -> bool:
    """True when a checked-folder record assigned `agent` expects from `rid`."""
    rid = str(record["id"])
    return any(
        other.get("assigned_agent") == agent
        and rid in _normalise(other.get("expects_from"), "ac_id")
        for other in ctx.peers(record)
    )


def evaluate_record(ctx: Any, record: Any) -> list[Finding]:
    """Both contract rules for `record` (presence only)."""
    rid = str(record["id"])
    found: list[Finding] = []
    for producer_id in _normalise(record.get("expects_from"), "ac_id"):
        finding = _expects_finding(ctx, record, producer_id)
        if finding is not None:
            found.append(finding)
    for agent in _normalise(record.get("delivers_to"), "agent"):
        if not _has_consumer(ctx, record, agent):
            message = f"{rid} delivers to {agent}, but no {agent} record in the checked folder expects from {rid}"
            found.append(
                Finding.for_record(record, NAME, DISPOSITION_DECISION, message, subject=f"delivers:{agent}")
            )
    return found
