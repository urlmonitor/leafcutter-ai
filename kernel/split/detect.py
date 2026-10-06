"""
MODULE: kernel.split.detect
GOAL: The "one question or several?" judgement: its literal Jev noul, the deterministic gates that
    decide whether it is asked at all, and the comparison with the configured threshold.
BUSINESS CONTEXT: ADR-053: deterministic gates run first and skip the check entirely when any
    fails; Jev only judges, and a subject counts as bundled only at or above
    `split.bundle_threshold`, which is biased against false positives.
ARCHITECTURE: Pure functions. The question rides an existing Jev batch (intent or routing), so it
    adds no provider request. Config, budgets and the request come in as arguments.
"""

from __future__ import annotations

from kernel.config import KernelConfig
from kernel.contracts import RequestKind, schema_ids
from kernel.contracts.work import RequestBody, WorkItem
from kernel.providers.base import JevError, JevResult, QuestionSpec

BUNDLE_TEMPLATE_ID = "kernel.split.bundled"
BUNDLE_REV = "1"
#: Answer kinds that are never split (ideas, change and out_of_domain roots).
UNSPLITTABLE_KINDS = frozenset({"ideas", "change", "out_of_domain"})
_SCHEMA_KIND = {schema_ids.DECISION_REPORT: "decision", schema_ids.EVIDENCE_BUNDLE: "evidence",
                schema_ids.OPTIONS: "ideas"}


def bundle_question_id(work_item_id: str) -> str:
    """Return the id of the bundle question of one work item."""
    return f"split.bundled.{work_item_id}"


def bundle_question(work_item_id: str, state_path: str) -> QuestionSpec:
    """Return the literal, versioned bundle question; `state_path` names the subject in the state."""
    instructions = (f"Does `{state_path}` hold several separate questions that would each be "
                    "answered on their own, rather than one question? Answer with the "
                    "probability that it holds several separate questions. A single question "
                    "with several details or constraints is one question.")
    return QuestionSpec(id=bundle_question_id(work_item_id), kind="noul",
                        template_id=BUNDLE_TEMPLATE_ID, template_version=BUNDLE_REV,
                        instructions=instructions)


def answer_kind(intent: str | None, requested_output_schema: str | None) -> str | None:
    """Return the resolved answer kind of a root, or None while it is unresolved."""
    if intent is not None and intent not in ("explicit", "default"):
        return intent
    return _SCHEMA_KIND.get(requested_output_schema or "")


def kind_allows_split(intent: str | None, requested_output_schema: str | None) -> bool:
    """Return False for an ideas, change or out-of-domain root; unresolved kinds are allowed."""
    return answer_kind(intent, requested_output_schema) not in UNSPLITTABLE_KINDS


def gates_open(cfg: KernelConfig, *, host_operations_used: int, parts_used: int,
               item: WorkItem, request: RequestBody, is_root: bool) -> bool:
    """Return True when every deterministic gate allows asking the bundle question."""
    if not (cfg.split.enabled and cfg.host.enabled and is_root):
        return False
    if host_operations_used + 1 > cfg.limits.max_host_operations:
        return False
    if item.split_checked or item.binding is not None or request.kind is not RequestKind.CAPABILITY:
        return False
    if request.payload_schema == schema_ids.DECISION_REQUEST:  # a caller-supplied decision
        return False
    return cfg.split.max_parts_per_run - parts_used >= 2


def read_bundle(result: JevResult, work_item_id: str) -> float | None:
    """Return the bundle probability answered for the item, or None when it was not answered."""
    try:
        return result.noul(bundle_question_id(work_item_id)).probability
    except (KeyError, JevError):
        return None


def is_bundled(probability: float | None, threshold: float) -> bool:
    """Return True when the probability reaches the threshold (inclusive)."""
    return probability is not None and probability >= threshold

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-06 18:00 [python-coder]: New deterministic split gates and bundle detection. (#TICKET-20261006-DK-400a-1)
# ====================================================================
