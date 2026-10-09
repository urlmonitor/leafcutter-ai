"""
MODULE: kernel.split.convert
GOAL: Convert the host's goal_decomposition.v1 proposal into the parts of a split record: the
    refusal checks (dependencies, allowed capabilities) and the deterministic steps that follow
    (quote check and set-aside, release of dependencies, count, the five-part cut).
BUSINESS CONTEXT: ADR-053 and ADR-067 section 5: the host proposes, deterministic code checks
    every part, a person approves. Jev is never asked to write, merge, reword, order or judge a
    part, so this module has no provider access at all.
ARCHITECTURE: Pure functions over plain values. The refusal checks run when the host answer is
    submitted (a refused answer leaves the run unchanged and is repaired by the host); the
    conversion runs when the router meets the accepted proposal. The order is fixed: dependencies,
    capabilities, quote check, release, count, cut.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from typing import Any

from kernel.contracts.split import GoalDecompositionPayload, PartProposal, SubjectKind
from kernel.split.text import normalize_text

QUOTE_NOT_FOUND = {SubjectKind.GOAL: "quote not found in the goal",
                   SubjectKind.RESEARCH_REQUEST: "quote not found in the research request",
                   SubjectKind.DECISION_QUESTION: "quote not found in the decision question"}
CAP_REASON = "beyond the five-part cap"
ALLOWANCE_REASON = "beyond the run's part allowance"
#: The record fields a freshly offered part carries beside the host's five (ADR-067 section 4.3).
UNSETTLED = {"proposed_text": None, "review": "proposed", "outcome": "not_run",
             "settled_order": None, "run_id": None, "decision_id": None, "result_ref": None,
             "findings": None, "stop_reason": None, "waited_for": None}


@dataclass(frozen=True)
class Conversion:
    """What a proposal became: offered parts, set-aside proposals and parts beyond the cut."""

    parts: list[dict[str, Any]] = field(default_factory=list)
    dropped: list[dict[str, Any]] = field(default_factory=list)
    not_covered: list[dict[str, Any]] = field(default_factory=list)
    #: (part id, released dependency ids) for every kept part that waited for a set-aside one.
    released: list[tuple[str, list[str]]] = field(default_factory=list)
    rewording: str | None = None
    #: Parts the proposal held after the set-aside and before the cut.
    kept_count: int = 0


def _cycle(parts: Sequence[PartProposal]) -> list[str] | None:
    """Return the first dependency cycle in proposed order (first id repeated), else None."""
    deps = {p.id: p.depends_on for p in parts}
    done: set[str] = set()

    def visit(node: str, path: list[str]) -> list[str] | None:
        if node in path:
            return [*path[path.index(node):], node]
        if node in done:
            return None
        for nxt in deps.get(node, []):
            found = visit(nxt, [*path, node])
            if found:
                return found
        done.add(node)
        return None

    for part in parts:
        found = visit(part.id, [])
        if found:
            return found
    return None


def dependency_problems(parts: Sequence[PartProposal]) -> list[str]:
    """Return why the proposal's ids and dependencies are refused (empty when they are sound)."""
    seen: set[str] = set()
    duplicates = [p.id for p in parts if p.id in seen or seen.add(p.id)]
    if duplicates:
        return [f"duplicate part id: {i}" for i in dict.fromkeys(duplicates)]
    unknown = [f"{p.id} depends on {d}, which the proposal does not contain"
               for p in parts for d in p.depends_on if d not in seen]
    if unknown:
        return unknown
    cycle = _cycle(parts)
    return [f"dependency cycle: {' -> '.join(cycle)}"] if cycle else []


def capability_problems(parts: Sequence[PartProposal], allowed: Collection[str]) -> list[str]:
    """Return one line per part naming a capability the subject kind does not allow."""
    return [f"part {p.id} names capability {p.child_capability}, allowed: {', '.join(allowed)}"
            for p in parts if p.child_capability not in allowed]


def run_order(parts: Sequence[dict[str, Any]]) -> list[str]:
    """Return part ids in Kahn's dependency order, the lowest proposed index first."""
    index = {p["id"]: n for n, p in enumerate(parts)}
    waiting = {p["id"]: set(p["depends_on"]) for p in parts}
    order: list[str] = []
    while waiting:
        ready = sorted((i for i, deps in waiting.items() if not deps), key=index.__getitem__)
        if not ready:  # a cycle cannot reach here (refused at submission); stay total anyway
            ready = sorted(waiting, key=index.__getitem__)
        head = ready[0]
        order.append(head)
        waiting.pop(head)
        for deps in waiting.values():
            deps.discard(head)
    return order


def _part(proposal: PartProposal, covers: str, depends_on: list[str]) -> dict[str, Any]:
    """Return the record of one offered part (every part not run)."""
    return {"id": proposal.id, "text": proposal.text, "covers": covers,
            "depends_on": depends_on, "child_capability": proposal.child_capability, **UNSETTLED}


def convert_proposal(payload: GoalDecompositionPayload, subject_text: str, kind: SubjectKind, *,
                     max_parts: int, allowance: int) -> Conversion:
    """Apply quote check, release, count and the cut to an already-accepted proposal."""
    subject = normalize_text(subject_text)
    kept: list[tuple[PartProposal, str]] = []
    dropped: list[dict[str, Any]] = []
    for proposal in payload.parts:
        covers = normalize_text(proposal.covers)
        if covers and covers in subject:
            kept.append((proposal, covers))
        else:
            dropped.append({"text": proposal.text, "covers": proposal.covers,
                            "reason": QUOTE_NOT_FOUND[kind]})
    kept_ids = {p.id for p, _ in kept}
    parts, released = [], []
    for proposal, covers in kept:
        gone = [d for d in proposal.depends_on if d not in kept_ids]
        if gone:
            released.append((proposal.id, gone))
        parts.append(_part(proposal, covers, [d for d in proposal.depends_on if d in kept_ids]))
    limit = max(0, min(max_parts, allowance))  # the caller's allowance can go negative
    offered = set(run_order(parts)[:limit])
    reason = CAP_REASON if max_parts <= allowance else ALLOWANCE_REASON
    cut = [{"id": p["id"], "text": p["text"], "covers": p["covers"], "reason": reason}
           for p in parts if p["id"] not in offered]
    return Conversion(
        parts=[{**p, "depends_on": [d for d in p["depends_on"] if d in offered]}
               for p in parts if p["id"] in offered],
        dropped=dropped, not_covered=cut, rewording=payload.one_question_rewording,
        released=[(i, g) for i, g in released if i in offered], kept_count=len(parts))


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-09 [python-coder]: The refusal checks (dependencies, capabilities) are separate from
#   the conversion because they run at submission time, where a refusal is repairable and leaves
#   the run unchanged; set-aside, release, count and cut run when the router meets the accepted
#   proposal. Not-covered parts lose their depends_on, as the spec requires.
#   (#TICKET-20261006-DK-400c-1)
# - 2026-10-09 [python-coder]: The offered limit is clamped at 0 because the caller's allowance can
#   go negative (a slice with a negative limit would offer all but the last parts). A cut cannot
#   strand a dependency: it keeps a prefix of run_order, the dependency order.
#   (#TICKET-20261006-DK-400c-1)
# ====================================================================
