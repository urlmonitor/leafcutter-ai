"""
MODULE: kernel.capabilities.decision.jev_support
GOAL: Shared helpers for the native capabilities: budgeted Jev calls with error mapping, terminal
    result builders, Jev batch construction and child-payload loading.
BUSINESS CONTEXT: Decision, research and retrieval all call Jev and all must turn provider
    failures into explicit, non-fabricated outcomes (Rev 3 section 13.4): an unavailable
    provider is `failed`, never a capability gap and never a guessed answer.
ARCHITECTURE: Lives in decision/ because the three native capabilities are the only P5 packages;
    research/ and retrieval/ import it. StopCapability carries a finished CapabilityResult out of
    deep helper code so graph nodes stay linear.
"""

from __future__ import annotations

import json
import logging

from pydantic import JsonValue

from kernel.capabilities.base import ExecutionContext
from kernel.capabilities.call_costs import jev_available, provider_calls
from kernel.contracts.capability import CapabilityResult, ErrorInfo, Usage
from kernel.contracts.enums import ResultStatus
from kernel.contracts.evidence import Evidence
from kernel.contracts.work import CapabilityInvocation, ChildOutcome
from kernel.providers.base import (
    JevBatch,
    JevError,
    JevInvalidResponse,
    JevPayloadTooLarge,
    JevResult,
    JevUnavailable,
    QuestionSpec,
)
from kernel.providers.jev_errors import JevBudgetExhausted

logger = logging.getLogger(__name__)

QUESTION_REV = "1"
MIN_EXCERPT_CHARS = 200


class StopCapability(Exception):
    """Raised inside a graph node to end the invocation with a finished result."""

    def __init__(self, result: CapabilityResult) -> None:
        """Keep the result and name its status in the message."""
        super().__init__(f"capability stopped with status {result.status.value}")
        self.result = result


def failed_result(invocation: CapabilityInvocation, code: str, message: str, *,
                  retryable: bool = False, usage: list[Usage] | None = None
                  ) -> CapabilityResult:
    """Build a `failed` result with an error code."""
    return CapabilityResult(
        invocation_id=invocation.id, work_item_id=invocation.work_item_id,
        status=ResultStatus.FAILED, usage=usage or [],
        error=ErrorInfo(code=code, message=message, retryable=retryable))


def blocked_result(invocation: CapabilityInvocation, code: str, message: str, *,
                   usage: list[Usage] | None = None) -> CapabilityResult:
    """Build a `blocked` result naming the unmet prerequisite."""
    return CapabilityResult(
        invocation_id=invocation.id, work_item_id=invocation.work_item_id,
        status=ResultStatus.BLOCKED, usage=usage or [],
        error=ErrorInfo(code=code, message=message), limitations=[message])


def noul_question(question_id: str, template_id: str, instructions: str, *,
                  criteria: dict[str, str] | None = None, version: str = QUESTION_REV
                  ) -> QuestionSpec:
    """Build a versioned noul question spec (optionally with explicit true/false criteria)."""
    return QuestionSpec(id=question_id, kind="noul", template_id=template_id,
                        template_version=version, instructions=instructions, criteria=criteria)


def choice_question(question_id: str, template_id: str, instructions: str,
                    criteria: dict[str, str]) -> QuestionSpec:
    """Build a versioned choice question spec."""
    return QuestionSpec(id=question_id, kind="choice", template_id=template_id,
                        template_version=QUESTION_REV,
                        instructions=instructions, criteria=criteria)


def make_batch(ctx: ExecutionContext, purpose: str, state: dict[str, JsonValue],
               questions: list[QuestionSpec]) -> JevBatch:
    """Build a Jev batch carrying the invocation's correlation ids."""
    return JevBatch(purpose=purpose, state=state, questions=questions, correlation=ctx.corr)


def _completed(exc: JevError) -> list[Usage]:
    """Return the usage of the provider calls that finished before the error (maybe none)."""
    return [exc.completed_usage] if exc.completed_usage is not None else []


async def ask_jev(ctx: ExecutionContext, invocation: CapabilityInvocation, batch: JevBatch,
                  *, prior_usage: list[Usage] | None = None) -> JevResult:
    """Reserve budget, call Jev and map provider errors to a stopped invocation.

    The whole batch must fit the budget before the first call is made: a chunked assessment is
    refused up front instead of being aborted half scored. Any result built on a stop carries the
    usage of calls already made (`prior_usage` of this invocation and the finished chunks of this
    batch), so usage, cost and the budget agree even when a stop happens.

    Args:
        ctx: Execution context (budget and provider).
        invocation: The running invocation (for result ids).
        batch: The batch to send.
        prior_usage: Usage of Jev calls this invocation already made.

    Returns:
        JevResult: The provider answers.

    Raises:
        StopCapability: Cancelled, budget refused, or the provider failed or answered badly.
    """
    spent = list(prior_usage or [])
    if ctx.cancelled():
        raise StopCapability(blocked_result(invocation, "cancelled", "run cancelled", usage=spent))
    needed, left = provider_calls(len(batch.questions), ctx.config), jev_available(ctx.budget)
    if left is not None and left < needed:
        raise StopCapability(blocked_result(
            invocation, "budget_exhausted",
            f"jev call budget exhausted: this batch needs {needed} provider call(s), {left} left",
            usage=spent))
    if not ctx.budget.reserve("jev"):
        raise StopCapability(blocked_result(invocation, "budget_exhausted",
                                            "jev call budget exhausted", usage=spent))
    try:
        return await ctx.jev.assess(batch)
    except JevBudgetExhausted as exc:  # not retryable: the budget will not grow by retrying
        raise StopCapability(blocked_result(
            invocation, "budget_exhausted", f"jev call budget exhausted: {exc.reason}",
            usage=[*spent, *_completed(exc)])) from exc
    except JevUnavailable as exc:
        raise StopCapability(failed_result(invocation, "provider_unavailable", exc.reason,
                                           retryable=True,
                                           usage=[*spent, *_completed(exc)])) from exc
    except JevInvalidResponse as exc:
        raise StopCapability(failed_result(invocation, "invalid_provider_response",
                                           exc.reason, usage=[*spent, *_completed(exc)])) from exc
    except JevPayloadTooLarge as exc:
        raise StopCapability(failed_result(invocation, "payload_too_large",
                                           str(exc), usage=[*spent, *_completed(exc)])) from exc


def excerpt_limit(ctx: ExecutionContext, count: int) -> int:
    """Return the per-item excerpt cap that keeps `count` excerpts inside half the state budget."""
    share = ctx.config.jev.max_state_chars // (2 * max(1, count))
    return max(MIN_EXCERPT_CHARS, share)


def evidence_state(ctx: ExecutionContext, items: list[Evidence]) -> dict[str, JsonValue]:
    """Return evidence as quoted state values keyed by id (never as instructions).

    Excerpt text is withheld when the data policy forbids sending excerpts to Jev.
    """
    send = ctx.config.data_policy.send_repo_excerpts_to_jev
    cap = excerpt_limit(ctx, len(items))
    state: dict[str, JsonValue] = {}
    for item in items:
        body = (item.excerpt or "")[:cap] if send else "[excerpt withheld by data policy]"
        state[item.id] = {"title": item.source.title or item.source.locator,
                          "locator": item.source.locator, "excerpt": body}
    return state


def load_output_payload(ctx: ExecutionContext, outcome: ChildOutcome
                        ) -> dict[str, JsonValue] | None:
    """Read a child's output payload through the artifact store; None when unreadable.

    The stored artifact may be the whole CapabilityResult JSON (payload under
    `output_payload`) or the bare payload. A missing or corrupt artifact is logged and reported
    as None so the caller records a limitation instead of treating it as empty output.
    """
    if outcome.result_ref is None:
        return None
    try:
        raw = ctx.artifacts.read_artifact(ctx.run_id, outcome.result_ref)
        data = json.loads(raw.decode("utf-8"))
    except (OSError, LookupError, ValueError) as exc:
        logger.warning("child %s output unreadable: %s", outcome.work_item_id, exc)
        return None
    if not isinstance(data, dict):
        return None
    inner = data.get("output_payload")
    return inner if isinstance(inner, dict) else data


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: ask_jev refuses a batch that does not fit the budget before the
#   first call (no half-scored assessment), treats a mid-assessment budget refusal as a
#   non-retryable `budget_exhausted` (it was retried and blocked before) and keeps the usage of
#   calls that finished. (#KernelV01/E)
# - 2026-09-30 23:00 [python-coder]: Child payloads are read via ctx.artifacts because
#   ChildOutcome carries only result_ref; P4 must make result_ref resolvable there.
#   (#KernelBootstrapV0/P5)
# ====================================================================
