"""
MODULE: tests.kernel.live.test_live_jev
GOAL: Exercise the real Jev (TypeSafe System One) through both adapter transports with
    synthetic, non-sensitive inputs.
BUSINESS CONTEXT: Mocked transports cannot show that the wire shapes, key handling and answer
    validation work against the real provider; this suite proves it on demand and prints model
    id, latency and token usage so calibration can be reviewed.
ARCHITECTURE: Skipped unless LEAFCUTTER_KERNEL_LIVE=1 (skipif only). The key comes from
    kernel.secrets (environment or the walked-up .env) and is never printed. A few cents at most.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from kernel.config import load_kernel_config
from kernel.providers import JevBatch, JevUnavailable, QuestionSpec
from kernel.providers.jev import TypeSafeJevAdapter
from kernel.secrets import load_secrets

LIVE = os.environ.get("LEAFCUTTER_KERNEL_LIVE") == "1"
STATE = {
    "request": {"goal": "Cache computed reports between runs.",
                "question": "Should the cache live in SQLite or in flat JSON files?"},
    "facts": {"existing_storage": "The project already ships a SQLite file for run state."},
}
CHOICES = {"sqlite": "Use SQLite for the cache.", "json_files": "Use flat JSON files.",
           "__NONE__": "Neither option fits.",
           "__NEEDS_CONTEXT__": "The request lacks enough information to choose."}


def _batch(purpose: str) -> JevBatch:
    """Return three literal questions over one synthetic state."""
    questions = [
        QuestionSpec(id="noul.storage", kind="noul", template_id="live.noul",
                     template_version="1",
                     instructions="Does `facts` state that the project already uses SQLite?"),
        QuestionSpec(id="choice.route", kind="choice", template_id="live.choice",
                     template_version="1", criteria=CHOICES,
                     instructions="According to `request` and `facts`, which option fits best?"),
        QuestionSpec(id="score.detail", kind="score", template_id="live.score",
                     template_version="1",
                     criteria=["No detail.", "Some detail.", "Enough detail to decide."],
                     instructions="How much detail does `facts` give for deciding `request`?"),
    ]
    return JevBatch(purpose=purpose, state=STATE, questions=questions)


def _api_key() -> str:
    """Return the Jev key without ever printing it."""
    key = load_secrets().jev_api_key
    assert key is not None, "JEV_API_KEY is not available"
    return key.get_secret_value()


async def _assess_and_close(adapter: TypeSafeJevAdapter, batch: JevBatch):
    """Assess and close inside one event loop (pooled connections are loop-bound)."""
    try:
        return await adapter.assess(batch)
    finally:
        await adapter.aclose()


def _run(transport: str) -> None:
    """Assess the batch live on one transport and check the normalised result."""
    adapter = TypeSafeJevAdapter.from_config(load_kernel_config(env={}), _api_key(),
                                             transport=transport)
    result = asyncio.run(_assess_and_close(adapter, _batch(f"live.{transport}")))
    noul, choice = result.noul("noul.storage"), result.choice("choice.route")
    score = result.answers["score.detail"]
    print(f"\n[{transport}] adapter={adapter.adapter_version} model={result.model_id} "
          f"latency_ms={result.latency_ms} usage={result.usage.model_dump()}")
    print(f"[{transport}] noul={noul.probability:.3f} choice={choice.choice} "
          f"conf={choice.confidence} probs={choice.probabilities} score={score.score:.2f}")
    assert result.model_id
    assert 0.0 <= noul.probability <= 1.0
    assert choice.choice in CHOICES
    assert abs(sum(choice.probabilities.values()) - 1.0) <= 0.02
    assert 0.0 <= score.score <= 2.0
    assert result.usage.input_tokens is None or result.usage.input_tokens > 0
    assert result.latency_ms is not None


@pytest.mark.skipif(not LIVE, reason="set LEAFCUTTER_KERNEL_LIVE=1 to call the real Jev")
class TestLiveJev:
    """Real-provider checks with synthetic inputs."""

    def test_classifier_transport(self) -> None:
        """langchain-typesafe path returns valid noul, choice and score answers."""
        _run("classifier")

    def test_http_transport(self) -> None:
        """The direct-HTTP fallback returns the same shapes."""
        _run("http")

    def test_rejected_key_is_unavailable(self) -> None:
        """A bad key maps to JevUnavailable, not a fabricated answer."""
        adapter = TypeSafeJevAdapter.from_config(load_kernel_config(env={}), "-".join(("bad", "0")),
                                                 transport="http")
        with pytest.raises(JevUnavailable):
            asyncio.run(_assess_and_close(adapter, _batch("live.badkey")))


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: Synthetic state only; prints go to stdout for review with
#   -s and never include the key. (#KernelBootstrapV0/P3)
# ====================================================================
