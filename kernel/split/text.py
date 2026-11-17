"""
MODULE: kernel.split.text
GOAL: The shared text normalisation and the derived fields of a split record.
BUSINESS CONTEXT: A split keeps the goal exactly as submitted; only whitespace runs collapse to
    one space. The same helper serves the quote check of a proposed part (DK-400c-2), so a quote
    and its subject are compared on the same footing.
ARCHITECTURE: Pure functions over strings and contract values.
"""

from __future__ import annotations

from kernel.contracts import SubjectKind, schema_ids, sha256_hex


def normalize_text(text: str) -> str:
    """Return the text with every whitespace run collapsed to one space and nothing else changed."""
    return " ".join(text.split())


def split_id(work_item_id: str) -> str:
    """Return the split id (`dcp-` plus 16 hex) derived from the owning work item id."""
    return f"dcp-{sha256_hex(work_item_id)[:16]}"


def derive_subject_kind(requested_output_schema: str | None, *, mid_run_question: bool = False
                        ) -> SubjectKind:
    """Return the subject kind: research request, decision question (mid run) or goal."""
    if requested_output_schema == schema_ids.EVIDENCE_BUNDLE:
        return SubjectKind.RESEARCH_REQUEST
    return SubjectKind.DECISION_QUESTION if mid_run_question else SubjectKind.GOAL

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-06 18:00 [python-coder]: New shared whitespace normalisation and subject-kind derivation. (#TICKET-20261006-DK-400a-1)
# ====================================================================
