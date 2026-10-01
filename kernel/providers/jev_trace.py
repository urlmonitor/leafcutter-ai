"""
MODULE: kernel.providers.jev_trace
GOAL: Build and emit the one GENERATION observation of a Jev call through the Tracer port.
BUSINESS CONTEXT: Langfuse only shows model, usage and cost for generation observations; the
    LangChain callback path records a Jev call as a usage-less CHAIN. Each assess call must
    therefore emit a generation carrying purpose, model id, adapter version, token usage
    (unknown stays None, never 0), estimated cost, latency and the raw answer distributions
    (design part 5, Rev 3 section 12).
ARCHITECTURE: Pure payload building plus a single tracer.generation call; the tracer redactor
    masks secrets and denied excerpts. Questions are summarised by id, kind and template (the
    state is referenced by its fingerprint and size, never copied), so a trace never carries the
    full evidence payload. Failures emit the same generation with `status=error` and no output.
"""

from __future__ import annotations

from typing import Any

from kernel.observability.tracer import Tracer
from kernel.providers.base import JevBatch, JevError, JevResult

DEFAULT_MODEL_NAME = "jev"


def _input_summary(batch: JevBatch, state_chars: int) -> dict[str, Any]:
    """Describe the request without copying the state."""
    return {
        "questions": [{"id": q.id, "kind": q.kind, "template_id": q.template_id,
                       "template_version": q.template_version} for q in batch.questions],
        "state_chars": state_chars, "input_fingerprint": batch.input_fingerprint()}


def emit_generation(tracer: Tracer, batch: JevBatch, *, adapter_version: str,
                    model_name: str | None, state_chars: int, latency_ms: int,
                    result: JevResult | None = None, error: JevError | None = None) -> None:
    """Emit the generation for one assess call (success when result is set, else the error).

    Args:
        tracer: Tracer receiving the observation (parented to the current span of the caller).
        batch: The batch that was assessed; its correlation ids are attached.
        adapter_version: Transport identity and version.
        model_name: Configured model, used when the provider did not report one.
        state_chars: Serialised state size (the state itself is not recorded).
        latency_ms: Wall time of the whole assess call.
        result: The normalised result, if the call succeeded.
        error: The raised error, if it failed.
    """
    meta: dict[str, Any] = {
        "purpose": batch.purpose, "adapter_version": adapter_version, "latency_ms": latency_ms,
        "question_count": len(batch.questions), "status": "error" if error else "ok",
        "template_ids": sorted({f"{q.template_id}@{q.template_version}"
                                for q in batch.questions})}
    output: dict[str, Any] | None = None
    if result is not None:
        meta.update(request_id=result.request_id, calls=result.usage.calls,
                    input_fingerprint=result.input_fingerprint)
        output = {"answers": {qid: a.model_dump(mode="json")
                              for qid, a in result.answers.items()}}
    if error is not None:
        meta["error"] = f"{type(error).__name__}: {error}"
    model = (result.model_id if result else None) or model_name or DEFAULT_MODEL_NAME
    tracer.generation(f"jev.{batch.purpose}", batch.correlation, model=model,
                      input=_input_summary(batch, state_chars), output=output,
                      usage=result.usage if result else None, metadata=meta)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 00:30 [python-coder]: State is summarised, not recorded: traces reference
#   evidence by fingerprint and size (design part 5: never the full payload), and the state can
#   be 10k+ characters per call. (#KernelBootstrapV0/OBS)
# ====================================================================
