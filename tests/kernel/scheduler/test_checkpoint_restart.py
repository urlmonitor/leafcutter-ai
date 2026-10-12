"""
MODULE: tests.kernel.scheduler.test_checkpoint_restart
GOAL: Test that scheduler state survives a real sqlite checkpointer with the strict msgpack
    allowlist and a process-style restart (new connection, new graph, new runtime) between the
    pause and the resume, and that the allowlist seam (contracts plus STATE_MODELS) is complete.
BUSINESS CONTEXT: A run paused for host work must resume after the process exits (Rev 3 section
    13.1); LangGraph's strict serde only revives allowlisted types, so a state type missing from
    the allowlist would turn a resume into a crash.
ARCHITECTURE: Uses LangGraph's AsyncSqliteSaver directly in a temporary directory (P2's saver is
    not available to this phase) with `JsonPlusSerializer(allowed_msgpack_modules=...)`; the
    allowlist completeness test walks the real final state, not a hand-written type list.
"""

from __future__ import annotations

import enum
import tempfile
import unittest
from pathlib import Path
from typing import Any

import aiosqlite
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel

from kernel.contracts import (
    ALL_MODELS,
    Actor,
    ActorKind,
    InteractionSubmission,
    RunStatus,
    schema_ids,
)
from kernel.scheduler import STATE_MODELS, build_kernel_graph, initial_state, run_config
from tests.kernel.scheduler.test_interaction_basic import _host_rig

ALLOWED = [*ALL_MODELS, *STATE_MODELS]


def _model_types(value: Any, found: set[type] | None = None) -> set[type]:
    """Collect the pydantic model and enum classes reachable in a state value."""
    found = set() if found is None else found
    if isinstance(value, (BaseModel, enum.Enum)):
        found.add(type(value))
    if isinstance(value, BaseModel):
        for name in type(value).model_fields:
            _model_types(getattr(value, name), found)
    elif isinstance(value, dict):
        for item in (*value.keys(), *value.values()):
            _model_types(item, found)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _model_types(item, found)
    return found


class TestCheckpointRestart(unittest.IsolatedAsyncioTestCase):
    """Pause, restart and resume through a real sqlite checkpointer."""

    async def test_paused_run_resumes_after_a_restart_with_the_strict_allowlist(self) -> None:
        rig = _host_rig()
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "checkpoints.sqlite"
            serde = JsonPlusSerializer(allowed_msgpack_modules=ALLOWED)
            state = initial_state("run-0000000000000001", rig.task_input(), rig.snapshot())
            config = run_config("run-0000000000000001", rig.config.limits.langgraph_recursion_limit)
            async with aiosqlite.connect(db) as conn:
                graph = build_kernel_graph(AsyncSqliteSaver(conn, serde=serde))
                paused = await graph.ainvoke(state, config, context=rig.runtime(), version="v2",
                                             durability="sync")
            packet = paused.interrupts[0].value
            self.assertEqual(paused.value["status"], RunStatus.WAITING_HOST)
            answer = InteractionSubmission(
                run_id="run-0000000000000001", interaction_id=packet["id"],
                expected_state_revision=packet["state_revision"],
                actor=Actor(id="host", kind=ActorKind.HOST),
                response_schema_id=schema_ids.EVIDENCE_BUNDLE,
                response={"evidence": [], "findings": [], "evidence_ids": []}
            ).model_dump(mode="json")
            async with aiosqlite.connect(db) as conn:
                graph = build_kernel_graph(AsyncSqliteSaver(conn, serde=serde))
                final = await rig.resume(graph, config, answer)
        self.assertEqual(final.value["outcome"].status, RunStatus.COMPLETED)
        self.assertEqual(final.value["budgets"].host_operations, 1)

    async def test_every_model_in_a_real_run_state_is_allowlisted(self) -> None:
        rig = _host_rig()
        _, _, out = await rig.start_raw()
        used = _model_types(dict(out.value))
        missing = sorted(t.__name__ for t in used if t not in set(ALLOWED))
        self.assertEqual(missing, [])
        self.assertTrue({"Budgets", "WorkItem", "RoutingAssessment"} <= {t.__name__ for t in used})


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:50 [python-coder]: Verified against the real sqlite saver that strict serde
#   returns a dict for a non-allowlisted Budgets and the integrate node crashes: P2 must
#   allowlist `kernel.scheduler.STATE_MODELS` next to `contracts.ALL_MODELS`.
#   (#KernelBootstrapV0/P4)
# ====================================================================
