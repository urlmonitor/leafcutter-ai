"""MODULE: retention.reclaim
GOAL: Reclaim the generations a declared retention bound permits, inside a successful publication.
BUSINESS CONTEXT: Superseded generations must not accumulate until the store latches read-only, and nothing may be deleted on a guess.
ARCHITECTURE: Acts on evaluate_retention's verdicts only after the active pointer switched; deletes by each generation's own key.

DECISION HISTORY
========================================
- 2026-10-16 11:00 [restructuring-specialist]: Moved from knowledge/adapters/neo4j_reclaim.py into the knowledge/adapters/retention/ sub-package to stay under the folder-density cap; behaviour unchanged. (#KM-400f-2/03)
- 2026-10-16 09:00 [python-coder]: An absent pin frees a generation only once it is older than the shared continuation lifetime; a failure after the pointer switch is logged and reported, never raised. (#KM-400f-2/02)
- 2026-10-15 04:00 [python-coder]: Reclaim only an assessed evaluation, never a generation whose pin state is unknown or whose publication is unfinished, and report counts and reasons. (#KM-400f-2)
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from knowledge.adapters.neo4j_backend import scope_key
from knowledge.adapters.neo4j_retention import evaluate_retention
from knowledge.adapters.retention.assessment import UNDETERMINED
from knowledge.cursors import CONTINUATION_LIFETIME_SECONDS
from knowledge.errors import BackendUnavailable

if TYPE_CHECKING:
    from knowledge.adapters.neo4j_backend import Neo4jBackend
    from knowledge.config import RetentionBound

logger = logging.getLogger(__name__)

IN_PROGRESS = "publication_in_progress"
PIN_UNKNOWN = "pin_state_unknown"
PINNED = "pinned_continuation_unexpired"
LIVE_CONTINUATION = "continuation_may_be_live"
RECLAIM_REFUSED = "reclaim_refused"
_UNFINISHED = ("building", "validated")


def nothing_reclaimed(status: str = "not_attempted") -> dict:
    """State a reclamation that reclaimed nothing, with its figure explicit.

    Args:
        status: Why nothing was reclaimed (``not_attempted`` or an assessment status).

    Returns:
        The reclamation report with ``reclaimed`` stated as 0.
    """
    return _summary(status, [], UNDETERMINED, [])


def _summary(status: str, reclaimed: list[str], retained: object, named: list[dict]) -> dict:
    """Shape the reclamation report consumed by the operator surface.

    Args:
        status: The evaluation's assessment status.
        reclaimed: Generation ids actually reclaimed.
        retained: Count of retained generations, or ``"undetermined"``.
        named: Each retained generation with the reason it was retained.

    Returns:
        Mapping with both counts, both lists and the assessment status.
    """
    return {
        "reclaimed": len(reclaimed),
        "retained": retained,
        "reclaimed_generations": reclaimed,
        "retained_generations": named,
        "assessment_status": status,
    }


def _guard(verdict: dict, fact: dict | None, now: float | None = None) -> str | None:
    """Name the reason a reclaimable verdict must still be declined.

    Pin rule: continuations are signed tokens, not stored, and none outlives
    ``CONTINUATION_LIFETIME_SECONDS`` after its first issue. So a numeric
    ``pinned_until`` is trusted (future = pinned, past = free), and an absent one
    is free only once the generation is older than that lifetime, measured from
    its retirement time when it has one, else its creation time (the verdict's
    ``age_seconds``). Anything else cannot be read as a pin state.

    Args:
        verdict: A per-generation verdict from the evaluation (carries ``age_seconds``).
        fact: The freshly read generation record, or None when it is gone.
        now: Optional clock value; defaults to the current time.

    Returns:
        ``publication_in_progress``, ``pinned_continuation_unexpired``,
        ``continuation_may_be_live`` or ``pin_state_unknown``; None when reclaiming is safe.
    """
    if fact is None:
        return PIN_UNKNOWN
    if fact.get("publication_status") in _UNFINISHED:
        return IN_PROGRESS
    pinned = fact.get("pinned_until")
    if pinned is None:
        return _absent_pin_guard(verdict.get("age_seconds"))
    if isinstance(pinned, bool) or not isinstance(pinned, (int, float)):
        return PIN_UNKNOWN
    clock = time.time() if now is None else now
    return PINNED if pinned > clock else None


def _absent_pin_guard(age_seconds: object) -> str | None:
    """Decide an unrecorded pin from the generation's age alone.

    Args:
        age_seconds: The verdict's age (retired_at, else created_at), or None when undetermined.

    Returns:
        ``pin_state_unknown`` for an undetermined age, ``continuation_may_be_live`` when the
        generation is not older than the continuation lifetime, else None.
    """
    if isinstance(age_seconds, bool) or not isinstance(age_seconds, (int, float)):
        return PIN_UNKNOWN
    return None if age_seconds > CONTINUATION_LIFETIME_SECONDS else LIVE_CONTINUATION


async def reclaim_superseded(db: Neo4jBackend, repository_id: str, bound: RetentionBound) -> dict:
    """Reclaim every generation of one repository the bound permits, and report it.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        repository_id: Trusted repository namespace; no other repository is touched.
        bound: Declared retention bound.

    Returns:
        The reclamation report; ``reclaimed`` is always an explicit integer.
    """
    # This runs after the active pointer switched: nothing here may turn a committed
    # publication into a reported failure, so every backend refusal is logged and reported.
    try:
        report = await evaluate_retention(db, repository_id, bound)
    except (BackendUnavailable, TypeError, ValueError) as exc:
        # TypeError/ValueError: a stored property of an unexpected type (e.g. a non-numeric pin).
        logger.warning("reclamation could not evaluate retention: %s", exc)
        return nothing_reclaimed("could_not_assess")
    status = report["assessment"]["status"]
    if status != "assessed" or not isinstance(report["reclaimable"], list):
        retained = UNDETERMINED if status == "could_not_assess" else len(report["generations"])
        return _summary(status, [], retained, _named(report, set(), {}))
    try:
        facts = {f["generation_id"]: f for f in await db.retention_facts(repository_id)}
    except BackendUnavailable as exc:
        logger.warning("reclamation could not re-read generation records: %s", exc)
        return nothing_reclaimed("could_not_assess")
    reclaimed: list[str] = []
    declined: dict[str, str] = {}
    for verdict in report["generations"]:
        if not verdict["reclaimable"]:
            continue
        gid = verdict["generation_id"]
        reason = await _reclaim_guarded(db, repository_id, verdict, facts.get(gid))
        if reason is None:
            reclaimed.append(gid)
        else:
            declined[gid] = reason
    named = _named(report, set(reclaimed), declined)
    return _summary(status, reclaimed, len(named), named)


async def _reclaim_guarded(db: Neo4jBackend, repository_id: str, verdict: dict, fact: dict | None) -> str | None:
    """Apply the guards, then reclaim one generation, turning any refusal into a reason.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        repository_id: Trusted repository namespace.
        verdict: The reclaimable verdict for the generation.
        fact: The freshly read generation record, or None when it is gone.

    Returns:
        None when the generation was reclaimed, else the reason it was kept.
    """
    reason = _guard(verdict, fact)
    if reason is not None:
        return reason
    try:
        reclaimed = await _reclaim_one(db, repository_id, verdict["generation_id"])
    except (BackendUnavailable, ValueError) as exc:
        logger.warning("generation %s could not be reclaimed: %s", verdict["generation_id"], exc)
        return RECLAIM_REFUSED
    return None if reclaimed else RECLAIM_REFUSED


def _named(report: dict, reclaimed: set[str], declined: dict[str, str]) -> list[dict]:
    """Name each retained generation with the reason it was retained.

    Args:
        report: The evaluation report.
        reclaimed: Generation ids that were reclaimed (not retained).
        declined: Reason overriding the verdict for generations declined at reclaim time.

    Returns:
        One ``{"generation_id", "reason"}`` entry per retained generation.
    """
    return [
        {"generation_id": v["generation_id"], "reason": declined.get(v["generation_id"], v["reason"])}
        for v in report["generations"]
        if v["generation_id"] not in reclaimed
    ]


async def _reclaim_one(db: Neo4jBackend, repository_id: str, generation_id: str) -> bool:
    """Delete one generation's records by its own key, its Snapshot record last.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        repository_id: Trusted repository namespace.
        generation_id: The generation to reclaim.

    Returns:
        True when every delete was accepted; False leaves the Snapshot record for a later pass.
    """
    from knowledge.adapters.neo4j_projection import _delete_tagged

    key = scope_key(repository_id, generation_id)
    if await _delete_tagged(db, key):
        return False
    return await _delete_record(db, repository_id, key)


async def _delete_record(db: Neo4jBackend, repository_id: str, key: str) -> bool:
    """Delete the Snapshot record and drop the vector indexes it names.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        repository_id: Trusted repository namespace scoping the record.
        key: Trusted hashed repository/generation scope key.

    Returns:
        Whether the record delete was accepted; an index drop refusal is logged only.
    """
    from knowledge.adapters.neo4j_vectors import trusted_name

    params = {"key": key, "repo": repository_id}
    match = "MATCH (g:Snapshot {key:$key, repository_id:$repo}) "
    try:
        rows = await db._run(match + "RETURN g.vector_indexes AS vector_indexes", params)
        await db._run(match + "DELETE g", params, True)
    except BackendUnavailable as exc:
        logger.warning("generation record could not be removed: %s", exc)
        return False
    for name in (rows[0]["vector_indexes"] or []) if rows else []:
        try:
            await db._run("DROP INDEX " + trusted_name(name) + " IF EXISTS", write=True)
        except BackendUnavailable as exc:
            logger.warning("vector index %s of a reclaimed generation was not dropped: %s", name, exc)
    return True
