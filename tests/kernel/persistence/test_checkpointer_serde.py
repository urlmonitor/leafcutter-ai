"""
MODULE: tests.kernel.persistence.test_checkpointer_serde
GOAL: Test the strict checkpoint serializer and the AsyncSqliteSaver factory: Pydantic contract
    state round-trips, unlisted classes stay inert, and a paused graph resumes from sqlite after
    the connection is closed and reopened (simulated restart).
BUSINESS CONTEXT: A run paused for a host or human must resume in a new process with its typed
    state intact, and untrusted checkpoint bytes must not be able to build arbitrary objects.
ARCHITECTURE: unittest.IsolatedAsyncioTestCase; real sqlite in a TemporaryDirectory and a tiny
    two-node LangGraph with an interrupt; no network.
"""

from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel

from kernel.contracts import Evidence
from kernel.persistence.checkpointer import (
    CHECKPOINT_DB_NAME,
    build_serializer,
    open_checkpointer,
)
from tests.kernel.helpers import make_evidence


_EVIDENCE = make_evidence()


class _Unlisted(BaseModel):
    """A model that is not part of the kernel contracts."""

    x: int = 1


class _State(TypedDict, total=False):
    evidence: Evidence
    answer: str


def _ask(state: _State) -> _State:
    """Pause until the host answers."""
    return {"answer": interrupt({"need": "answer"})}


def _graph(saver: object) -> object:
    builder = StateGraph(_State)
    builder.add_node("seed", lambda state: {"evidence": _EVIDENCE})
    builder.add_node("ask", _ask)
    builder.add_edge(START, "seed")
    builder.add_edge("seed", "ask")
    builder.add_edge("ask", END)
    return builder.compile(checkpointer=saver)


class TestSerializer(unittest.TestCase):
    """build_serializer allowlist behaviour."""

    def test_contract_models_round_trip_as_models(self) -> None:
        serde = build_serializer()
        evidence = make_evidence()
        payload = {"e": evidence, "many": [evidence]}
        restored = serde.loads_typed(serde.dumps_typed(payload))
        self.assertEqual(restored, payload)
        self.assertIsInstance(restored["e"], Evidence)

    def test_unlisted_class_is_not_revived(self) -> None:
        serde = build_serializer()
        with self.assertLogs("langgraph.checkpoint.serde.jsonplus", level=logging.WARNING):
            restored = serde.loads_typed(serde.dumps_typed({"u": _Unlisted()}))
        self.assertNotIsInstance(restored["u"], _Unlisted)
        self.assertEqual(restored["u"], {"x": 1})

    def test_extra_types_extend_the_allowlist(self) -> None:
        serde = build_serializer(extra_types=[_Unlisted])
        restored = serde.loads_typed(serde.dumps_typed({"u": _Unlisted(x=5)}))
        self.assertEqual(restored["u"], _Unlisted(x=5))


class TestSqliteRestart(unittest.IsolatedAsyncioTestCase):
    """A paused graph resumes from sqlite in a fresh connection."""

    async def test_interrupted_run_resumes_after_reopen(self) -> None:
        config = {"configurable": {"thread_id": "run-0123456789abcdef"}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            async with open_checkpointer(root) as saver:
                await _graph(saver).ainvoke({}, config)
            self.assertTrue((root / CHECKPOINT_DB_NAME).is_file())
            async with open_checkpointer(root) as saver:
                graph = _graph(saver)
                paused = await graph.aget_state(config)
                self.assertEqual(paused.next, ("ask",))
                self.assertEqual(paused.values["evidence"], _EVIDENCE)
                self.assertIsInstance(paused.values["evidence"], Evidence)
                final = await graph.ainvoke(Command(resume="yes"), config)
            self.assertEqual(final["answer"], "yes")


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: Restart is simulated by closing and reopening the sqlite connection with a real interrupt.
#   (#KernelBootstrapV0/P2)
# ====================================================================
