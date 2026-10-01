"""
MODULE: kernel.scheduler.guards
GOAL: Pure guard functions: run-level limits (time, cost, iterations, Jev-call and host-operation
    caps, no progress), work-item cap and depth, duplicate-request dedup key, no-progress
    fingerprint, dependency and request cycles, retry policy, usage costing, human-wait time and
    the list of work a tripped guard leaves unresolved.
BUSINESS CONTEXT: A run must end as a partial or blocked envelope with diagnostics, never loop
    (Rev 3 sections 8.4 and 13.2); rewording a question must not reset the no-progress guard, so
    the dedup key is computed from a normalised form of the request.
ARCHITECTURE: No IO and no state mutation: nodes call these with counters and limits taken from
    config (no numeric threshold lives here). P9 hardened it: Unicode-stable duplicate keys,
    run-level Jev and host caps as a safety net behind the per-route checks, waiting time measured
    from events (never charged to the active-time budget) and unresolved-work diagnostics.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from datetime import datetime
from dataclasses import dataclass
from typing import Any

from kernel.config import LimitsConfig
from kernel.contracts import (
    ErrorInfo,
    Evidence,
    RunEvent,
    Usage,
    WorkItem,
    WorkItemStatus,
    canonical_json,
    sha256_hex,
)
from kernel.contracts.work import RequestBody
from kernel.scheduler.state import Budgets

TERMINAL_STATUSES = frozenset({WorkItemStatus.COMPLETED, WorkItemStatus.PARTIAL,
                               WorkItemStatus.BLOCKED, WorkItemStatus.FAILED,
                               WorkItemStatus.CANCELLED})
#: Supersteps one scheduling cycle needs at most (schedule, route, execute, integrate, plus the
#: interaction nodes); a structural fact of the graph, used only to derive the iteration guard.
SUPERSTEPS_PER_ITERATION = 6
_TOKEN = re.compile(r"\w+", re.UNICODE)
_STOPWORDS = frozenset({"a", "an", "the", "of", "to", "for", "in", "on", "and", "or", "is", "are",
                        "be", "we", "our", "please", "should", "do", "does", "with", "that"})
_TEXT_KEYS = frozenset({"question", "goal", "problem", "summary", "query"})
CLOSING_INTERACTION_EVENTS = frozenset({"interaction.answered", "interaction.repair_exhausted"})


@dataclass(frozen=True)
class GuardTrip:
    """A tripped guard: its name and a short human-readable detail."""

    guard: str
    detail: str


def max_iterations_for(limits: LimitsConfig, explicit: int | None = None) -> int:
    """Return the scheduler-iteration limit.

    Order: the explicit runtime value, then `limits.max_scheduler_iterations`, then a value
    derived from the LangGraph recursion limit.
    """
    if explicit is not None:
        return explicit
    if limits.max_scheduler_iterations is not None:
        return limits.max_scheduler_iterations
    return max(1, limits.langgraph_recursion_limit // SUPERSTEPS_PER_ITERATION)


def check_run_guards(budgets: Budgets, limits: LimitsConfig, *, max_iterations: int,
                     queue_empty: bool, cancelled: bool) -> GuardTrip | None:
    """Return the first tripped run-level guard, or None.

    Args:
        budgets: Current counters.
        limits: Configured limits.
        max_iterations: Scheduler-iteration limit.
        queue_empty: True when no interaction is pending (waiting time is never a trip).
        cancelled: True when cancellation was requested.

    Returns:
        GuardTrip | None: Guard name (cancelled, max_active_seconds, max_cost_usd,
            max_jev_calls, max_host_operations, max_scheduler_iterations, no_progress) and
            detail.
    """
    if cancelled:
        return GuardTrip("cancelled", "cancellation requested")
    if budgets.active_seconds >= limits.max_active_seconds:
        return GuardTrip("max_active_seconds", f"{budgets.active_seconds:.1f}s active")
    if limits.max_cost_usd is not None and budgets.cost_usd_known > limits.max_cost_usd:
        return GuardTrip("max_cost_usd", f"{budgets.cost_usd_known:.4f} USD known cost")
    if budgets.jev_calls > limits.max_jev_calls:
        return GuardTrip("max_jev_calls", f"{budgets.jev_calls} Jev calls")
    if budgets.host_operations > limits.max_host_operations:
        return GuardTrip("max_host_operations", f"{budgets.host_operations} host operations")
    if budgets.scheduler_iterations > max_iterations:
        return GuardTrip("max_scheduler_iterations", f"{budgets.scheduler_iterations} iterations")
    if queue_empty and budgets.no_progress_streak >= limits.no_progress_limit:
        return GuardTrip("no_progress", f"{budgets.no_progress_streak} passes without progress")
    return None


def work_item_cap_allows(created: int, new_count: int, limits: LimitsConfig) -> bool:
    """Return True if `new_count` more work items stay within the cap."""
    return created + new_count <= limits.max_work_items


def depth_allows(parent_depth: int, limits: LimitsConfig) -> bool:
    """Return True if a child of a parent at `parent_depth` stays within the depth limit."""
    return parent_depth + 1 <= limits.max_depth


def jev_calls_available(budgets: Budgets, limits: LimitsConfig) -> int:
    """Return how many more Jev calls may be reserved."""
    return max(0, limits.max_jev_calls - budgets.jev_calls)


def host_operations_available(budgets: Budgets, limits: LimitsConfig) -> int:
    """Return how many more host operations may be started."""
    return max(0, limits.max_host_operations - budgets.host_operations)


def retry_allowed(budgets: Budgets, work_item_id: str, error: ErrorInfo | None,
                  limits: LimitsConfig) -> bool:
    """Return True if a failed result may be retried: transient error and retries left."""
    if error is None or not error.retryable:
        return False
    return budgets.retries.get(work_item_id, 0) < limits.max_retries


def normalize_text(text: str | None) -> str:
    """Normalise free text for dedup: lowercase, tokenise, drop stopwords, sort the token set.

    Whitespace, punctuation, case (Unicode case folding), width and compatibility variants, word
    order and filler words do not change the result, so a reworded summary of the same request
    keeps its key (Rev 3 section 8.4).
    """
    folded = unicodedata.normalize("NFKC", text or "").casefold()
    tokens = {t for t in _TOKEN.findall(folded) if t not in _STOPWORDS}
    return " ".join(sorted(tokens))


def _canonical_payload(value: Any, key: str | None = None) -> Any:
    """Return the payload without generated `id` keys, with descriptive text normalised."""
    if isinstance(value, Mapping):
        return {k: _canonical_payload(v, k) for k, v in value.items() if k != "id"}
    if isinstance(value, list):
        return [_canonical_payload(v, key) for v in value]
    if isinstance(value, str) and key in _TEXT_KEYS:
        return normalize_text(value)
    return value


def request_dedup_key(body: RequestBody, scope_revision: Mapping[str, Any] | None) -> str:
    """Return the duplicate-request key of a request or proposal (design part 3, Duplicate).

    Args:
        body: Request or proposal.
        scope_revision: The task scope revision as a plain mapping (or None).

    Returns:
        str: sha256 hex digest of the canonical identity.
    """
    needs = sorted(f"{n.category.value}:{normalize_text(n.question)}" for n in body.evidence_needs)
    identity = {
        "kind": body.kind.value, "goal": normalize_text(body.goal),
        "question": normalize_text(body.question), "payload_schema": body.payload_schema,
        "payload": _canonical_payload(dict(body.payload)),
        "requested_output_schema": body.requested_output_schema, "needs": needs,
        "scope_revision": dict(scope_revision) if scope_revision else None,
    }
    return sha256_hex(canonical_json(identity))


def evidence_revision(evidence: Iterable[Evidence]) -> str:
    """Return the hash of the sorted content hashes of the visible evidence."""
    return sha256_hex(canonical_json(sorted(e.content_hash for e in evidence)))


def attempt_fingerprint(dedup_key: str, output_schema: str,
                        scope_revision: Mapping[str, Any] | None, revision: str,
                        versions: Mapping[str, str]) -> str:
    """Return the no-progress fingerprint of one work attempt (design part 3, No progress)."""
    body = {"dedup": dedup_key, "output": output_schema,
            "scope_revision": dict(scope_revision) if scope_revision else None,
            "evidence_revision": revision, "versions": dict(versions)}
    return sha256_hex(canonical_json(body))


def reaches(items: Mapping[str, WorkItem], source: str, target: str) -> bool:
    """Return True if `source` waits (transitively) on `target` through children/dependencies."""
    seen: set[str] = set()
    stack = [source]
    while stack:
        current = stack.pop()
        if current == target:
            return True
        if current in seen or current not in items:
            continue
        seen.add(current)
        stack.extend(items[current].child_ids + items[current].dependency_ids)
    return False


def ancestor_ids(items: Mapping[str, WorkItem], parents: Mapping[str, str | None],
                 work_item_id: str) -> list[str]:
    """Return the work item and its origin ancestors, nearest first (cycle-safe).

    Args:
        items: All work items.
        parents: Map from work item id to the id of the item that proposed it (or None).
        work_item_id: Item to start from.
    """
    chain: list[str] = []
    current: str | None = work_item_id
    while current is not None and current in items and current not in chain:
        chain.append(current)
        current = parents.get(current)
    return chain


def waiting_seconds(events: Iterable[RunEvent]) -> float:
    """Return the seconds interactions spent open (human and host wait), from run events.

    Each `interaction.opened` is paired with the `interaction.answered` or
    `interaction.repair_exhausted` of the same interaction id; an interaction that is still open
    is not counted. This time is reported beside the active-time budget and never charged to it.
    """
    opened: dict[str, datetime] = {}
    total = 0.0
    for event in events:
        key = event.refs.get("interaction_id")
        if key is None:
            continue
        if event.kind == "interaction.opened":
            opened[key] = event.at
        elif event.kind in CLOSING_INTERACTION_EVENTS and key in opened:
            total += max(0.0, (event.at - opened.pop(key)).total_seconds())
    return total


def unresolved_item_ids(items: Mapping[str, WorkItem], root_id: str) -> list[str]:
    """Return the ids of non-root work items that are not terminal, in presentation order."""
    pending = [i for i in items.values() if i.id != root_id and i.status not in TERMINAL_STATUSES]
    return [i.id for i in sorted(pending, key=lambda x: (x.created_seq, x.id))]


def unresolved_text(guard: str, goal: str | None) -> str:
    """Return the limitation line for work a tripped guard left unfinished."""
    subject = (goal or "unnamed request").strip().replace(chr(10), " ")[:120]
    return f"unresolved_at_{guard}: {subject}"


def account_usage(budgets: Budgets, usages: Iterable[Usage],
                  price_per_input_token: float | None) -> Budgets:
    """Fold provider usages into the counters; unknown costs are counted, never guessed as 0.

    Args:
        budgets: Current counters.
        usages: Usage records of one or more provider calls.
        price_per_input_token: Configured price used to estimate a missing cost.

    Returns:
        Budgets: Updated copy (`cost_usd_known` grows by reported or estimated costs only).
    """
    known, unknown = budgets.cost_usd_known, budgets.cost_unknown_calls
    for usage in usages:
        if usage.cost_usd is not None:
            known += usage.cost_usd
        elif price_per_input_token is not None and usage.input_tokens is not None:
            known += usage.input_tokens * price_per_input_token
        else:
            unknown += 1
    return budgets.model_copy(update={"cost_usd_known": known, "cost_unknown_calls": unknown})


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 14:00 [python-coder]: The Jev-call and host-operation caps are also run-level
#   guards using strict `>`: the per-route checks stop new work at the limit, so a trip here only
#   means accounting drifted past it, and it then ends the run with diagnostics instead of
#   spending more. (#KernelBootstrapV0/P9)
# - 2026-10-01 14:00 [python-coder]: Wait time is derived from the event log rather than a new
#   Budgets field (state.py is outside P9): the active-time counter stays free of human wait by
#   construction, and the pairing function makes the split inspectable. (#KernelBootstrapV0/P9)
# - 2026-09-30 22:30 [python-coder]: Payload text is normalised only under descriptive keys
#   (question, goal, ...) so two requests that differ in a path or id list are never merged by
#   accident. (#KernelBootstrapV0/P4)
# ====================================================================
