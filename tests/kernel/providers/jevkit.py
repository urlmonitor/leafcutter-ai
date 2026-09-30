"""
MODULE: tests.kernel.providers.jevkit
GOAL: Shared builders for the Jev adapter tests: questions, batches, response bodies and an
    adapter wired to a mocked transport.
BUSINESS CONTEXT: The adapter tests exercise both transports (classifier and direct HTTP) with
    the same questions and responses so their behaviour stays identical.
ARCHITECTURE: Bodies come from a JSON fixture; requests are recorded by the handler closures.
    No network and no sleeping: the adapter gets a recording sleep.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from kernel.providers.base import JevBatch, QuestionSpec
from kernel.providers.jev import TypeSafeJevAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "jev_response_mixed.json"
FAKE_KEY = "-".join(("tk", "0000"))


def body() -> dict:
    """Return a fresh copy of the mixed (noul, choice, score) response body."""
    return copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))


def spec(kind: str, qid: str) -> QuestionSpec:
    """Return a question of the given kind with fixed criteria."""
    criteria: dict | list | None = None
    if kind == "choice":
        criteria = {"alpha": "first", "beta": "second", "__NONE__": "neither"}
    elif kind == "score":
        criteria = ["low", "mid", "high"]
    return QuestionSpec(id=qid, kind=kind, template_id=f"t.{kind}", template_version="1",
                        instructions=f"Judge `{qid}` literally.", criteria=criteria)


def mixed_batch(purpose: str = "test.mixed") -> JevBatch:
    """Return the three-question batch matching the mixed fixture."""
    return JevBatch(purpose=purpose, state={"item": "synthetic"},
                    questions=[spec("noul", "q.noul"), spec("choice", "q.choice"),
                               spec("score", "q.score")])


class Sleeper:
    """Records requested backoff delays instead of sleeping."""

    def __init__(self) -> None:
        """Start with no recorded delays."""
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        """Record one delay."""
        self.delays.append(seconds)


def make_adapter(transport: object, sleeper: Sleeper, **overrides: object) -> TypeSafeJevAdapter:
    """Build an adapter with small, test-friendly limits."""
    params = {"timeout_seconds": 5.0, "max_questions_per_call": 20, "max_state_chars": 10000,
              "max_retries": 2, "retry_backoff_seconds": 1.0,
              "price_per_input_token_usd": 4.2e-8, "sleep": sleeper}
    params.update(overrides)
    return TypeSafeJevAdapter(transport, **params)


def http_transport(handler: object) -> tuple[object, object]:
    """Return (HttpTransport over httpx MockTransport, the httpx module)."""
    import httpx  # noqa: PLC0415

    from kernel.providers.jev_http import HttpTransport  # noqa: PLC0415

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return HttpTransport(api_key=FAKE_KEY, model="jev-test", timeout_seconds=5.0,
                         client=client), httpx


def classifier_transport(handler: object) -> tuple[object, object]:
    """Return (ClassifierTransport over httpx2 MockTransport, the httpx2 module)."""
    import httpx2  # noqa: PLC0415

    from kernel.providers.jev import ClassifierTransport  # noqa: PLC0415

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return ClassifierTransport(api_key=FAKE_KEY, model="jev-test", timeout_seconds=5.0,
                               async_client=client), httpx2


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: Both transports are fed by the same handlers so the
#   fallback cannot drift from the primary path. (#KernelBootstrapV0/P3)
# ====================================================================
