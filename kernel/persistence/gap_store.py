"""
MODULE: kernel.persistence.gap_store
GOAL: Durable, file-backed GapStorePort: append-only gap observations aggregated by gap key, plus
    backlog-ready drafts.
BUSINESS CONTEXT: Gaps are the feedback loop for the capability backlog (Rev 3 section 14); the
    same unmet need seen in many runs must become one gap with an occurrence count and a few
    example runs, never a flood of duplicates and never a live registry entry.
ARCHITECTURE: <run_root>/gaps/observations.jsonl holds raw observations (fsynced lines; a repeated
    observation id from a resumed node is ignored); load_gaps aggregates them with the shared
    aggregate_gaps so memory and file stores agree. Drafts live in gaps/drafts/<gap_key>.md and
    are written atomically; the gap key is validated as a path component.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from pydantic import ValidationError

from kernel.contracts.enums import GapType
from kernel.contracts.run import CapabilityGap, GapProposal
from kernel.persistence.base import GapStorePort, aggregate_gaps
from kernel.persistence.fsutil import append_line, atomic_write_bytes, read_lines, safe_component

logger = logging.getLogger(__name__)

#: Only these gap types describe an implementation opportunity (Rev 3 section 14); the others
#: must never produce a "build a new capability" draft.
BUILD_OPPORTUNITY_TYPES = frozenset({GapType.UNSUPPORTED, GapType.HOST_ONLY})
DRAFT_AUTHOR = "template"
_DRAFT_PURPOSE = {
    GapType.UNSUPPORTED: "No registered capability can serve this need; the request was {outcome}.",
    GapType.HOST_ONLY: "Only a host-backed implementation exists; a native one could replace it.",
}


def is_build_opportunity(gap: CapabilityGap) -> bool:
    """Return True when the gap type may produce a backlog draft."""
    return gap.gap_type in BUILD_OPPORTUNITY_TYPES


def _bullets(values: list[str], empty: str = "none recorded") -> str:
    """Render a list as Markdown bullets (or the `empty` text)."""
    return chr(10).join(f"- {v}" for v in values) if values else f"- {empty}"


def render_gap_draft(gap: CapabilityGap) -> str:
    """Render the backlog-ready draft of an aggregated gap from a fixed template.

    The text is assembled from recorded fields only (no model-written prose). It is labelled as
    template-authored, says it is not a registry entry and keeps the uncertainties explicit:
    a count of observations shows demand, never correctness (ADR-056).

    Args:
        gap: An aggregated gap (see aggregate_gaps).

    Returns:
        str: Markdown for gaps/drafts/<gap_key>.md.
    """
    purpose = _DRAFT_PURPOSE.get(gap.gap_type, "Not a build opportunity.").format(
        outcome=gap.fallback_outcome.value)
    lines = [
        f"# Capability gap draft: {gap.normalized_need or gap.goal[:60]}", "",
        f"- Author: {DRAFT_AUTHOR} (kernel gap draft template v1; no model wrote this text)",
        "- Status: proposal only - NOT a registry entry, never installed or routed automatically",
        f"- Gap key: `{gap.gap_key}`", f"- Gap type: {gap.gap_type.value}", "",
        "## Proposed purpose", "", purpose, "", f"Unmet need (first goal seen): {gap.goal}", "",
        "## Contracts", "", f"- Request kind: {gap.request_kind.value}",
        f"- Input schema: `{gap.input_schema}`", f"- Output schema: `{gap.output_schema}`",
        f"- Scope components: {', '.join(gap.scope_component_ids) or 'any'}", "",
        "## Evidence of need", "", f"- Occurrences: {gap.occurrence_count}",
        f"- First seen: {gap.first_seen.isoformat() if gap.first_seen else 'unknown'}",
        f"- Last seen: {gap.last_seen.isoformat() if gap.last_seen else 'unknown'}",
        f"- Fallback outcome (latest): {gap.fallback_outcome.value}",
        "- Example runs:", _bullets([f"`{r}`" for r in gap.example_run_ids]), "",
        "## Closest existing capabilities", "", _bullets(gap.candidates_considered), "",
        "## Why existing capabilities were insufficient", "",
        gap.why_insufficient or "not recorded", "",
        "## Expected benefit", "",
        "Unknown. Weigh observed fallback frequency, known cost, latency and failure rate.", "",
        "## Remaining uncertainties", "",
        "- A single vague request is not evidence that a new subsystem is needed.",
        "- Observation counts show demand, not the correctness of any host fallback result.",
        "- Any implementation must pass normal development, review, versioning and registration.",
        ""]
    return chr(10).join(lines)


def publish_gap(store: GapStorePort, gap: CapabilityGap, *, with_draft: bool = True
                ) -> CapabilityGap | None:
    """Write the backlog draft (build opportunities) and store the observation.

    The draft is rendered from the aggregate of earlier observations of the same gap key plus
    this one, and its reference is kept on the stored observation as a template-authored
    proposal. A draft failure is logged and the observation is stored without a proposal.

    Args:
        store: The gap store.
        gap: The new observation.
        with_draft: False suppresses the draft (for example when a native alternative exists).

    Returns:
        CapabilityGap | None: The observation as stored, or None when storing failed (logged).
    """
    try:
        if with_draft and is_build_opportunity(gap):
            known = [g for g in store.load_gaps() if g.gap_key == gap.gap_key]
            preview = aggregate_gaps([*known, gap])[0]
            ref = store.write_draft(preview, render_gap_draft(preview))
            gap = gap.model_copy(update={"proposal": GapProposal(
                title=f"Capability for: {gap.normalized_need or gap.goal[:60]}",
                purpose=f"{gap.gap_type.value} need", draft_ref=ref)})
    except (OSError, ValueError):
        logger.warning("could not write the draft of gap %s", gap.gap_key, exc_info=True)
    try:
        store.record(gap)
    except OSError:
        logger.warning("could not record capability gap %s", gap.gap_key, exc_info=True)
        return None
    return gap


class FileGapStore:
    """GapStorePort persisting under <run_root>/gaps/."""

    def __init__(self, run_root: Path) -> None:
        """Bind the store to run_root (created lazily)."""
        self.gaps_dir = Path(run_root) / "gaps"
        self._lock = threading.RLock()

    @property
    def observations_file(self) -> Path:
        """Return the path of observations.jsonl."""
        return self.gaps_dir / "observations.jsonl"

    def _observations(self) -> list[CapabilityGap]:
        """Read raw observations, skipping torn or unreadable lines with a warning."""
        found: list[CapabilityGap] = []
        for line in read_lines(self.observations_file):
            try:
                found.append(CapabilityGap.model_validate_json(line))
            except ValidationError:
                logger.warning("skipping unreadable gap observation line")
        return found

    def record(self, gap: CapabilityGap) -> None:
        """Append one observation; an observation id that is already stored is ignored."""
        with self._lock:
            if any(obs.id == gap.id for obs in self._observations()):
                logger.debug("gap observation %s already recorded", gap.id)
                return
            append_line(self.observations_file, gap.model_dump_json())

    def load_gaps(self) -> list[CapabilityGap]:
        """Return gaps aggregated by gap_key (occurrences summed, at most five example runs)."""
        with self._lock:
            return aggregate_gaps(self._observations())

    def write_draft(self, gap: CapabilityGap, markdown: str) -> str:
        """Write gaps/drafts/<gap_key>.md atomically and return its run-root-relative ref."""
        name = f"{safe_component(gap.gap_key)}.md"
        with self._lock:
            atomic_write_bytes(self.gaps_dir / "drafts" / name, markdown.encode("utf-8"))
        return f"drafts/{name}"


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 14:00 [python-coder]: The draft template lives next to the store so memory and
#   file stores share it; it is built only from recorded fields, names its author "template" and
#   states it is not a registry entry (spec section 14, ADR-056). (#KernelBootstrapV0/P9)
# - 2026-09-30 23:00 [python-coder]: Observations dedupe by observation id (not only by gap key)
#   so a node that re-executes after resume cannot double-count an occurrence.
#   (#KernelBootstrapV0/P2)
# ====================================================================
