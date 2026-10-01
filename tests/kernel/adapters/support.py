"""
MODULE: tests.kernel.adapters.support
GOAL: Shared builders for the P7 tests: a KernelEnvironment over the scheduler test rig and real
    file stores, a tracer that gives every segment its own root observation id, and envelope and
    submission helpers.
BUSINESS CONTEXT: The service, the CLI and the restart scenarios must all be proven against the
    real compiled graph, the real sqlite checkpointer and the real file stores; only Jev, the
    executors and the tracer are doubles, so no test depends on the network.
ARCHITECTURE: `rig_environment` mirrors `kernel.bootstrap.build_environment` but takes its
    registry snapshot and bindings from a scheduler `Rig`. The same function builds the
    environment inside the CLI harness process, so in-process and subprocess tests exercise one
    composition.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kernel.bootstrap import KernelEnvironment
from kernel.contracts import InteractionSubmission
from kernel.contracts.run import RunEnvelope
from kernel.observability.redaction import Redactor
from kernel.observability.tracer import RecordingTracer, TraceState
from kernel.persistence import FileArtifactStore, FileGapStore, FileRunStore
from kernel.secrets import SecretSettings
from tests.kernel.helpers import narrow
from tests.kernel.interaction.restart_harness import CrashingRunStore
from tests.kernel.interaction.support import BUNDLE, raw_submission
from tests.kernel.scheduler.support import Rig, with_limits

__all__ = ["BUNDLE", "SegmentTracer", "answer", "rig_environment", "task_input_json"]


class SegmentTracer(RecordingTracer):
    """RecordingTracer whose segments get distinct, predictable root observation ids."""

    def __init__(self, *args: Any, prefix: str = "seg", **kwargs: Any) -> None:
        """Name this process's segments `<prefix>-<n>-<kind>`."""
        super().__init__(*args, **kwargs)
        self.prefix = prefix

    def open_segment(self, run_id: str, root_task_id: str, kind: str) -> TraceState:
        """Record the segment and return a trace whose root id names the segment kind."""
        state = super().open_segment(run_id, root_task_id, kind)
        return state.model_copy(update={"root_observation_id": f"{self.prefix}-{len(self.segments)}-{kind}",
                                        "trace_url": f"https://trace.example/{state.trace_id}"})


def rig_environment(root: Path, rig: Rig, *, tracer: Any = None, crash: str | None = None,
                    with_jev: bool = True, **limits: Any) -> KernelEnvironment:
    """Build a KernelEnvironment over `rig` with real file stores under `root`.

    Args:
        root: The run root (runs, checkpoints).
        rig: Scheduler rig providing descriptors, bindings, Jev and config.
        tracer: Tracer to use (default: a fresh SegmentTracer).
        crash: Crash point for CrashingRunStore (subprocess tests only).
        with_jev: False leaves `jev_factory` empty (no credential).
        **limits: Config limit overrides (for example langgraph_recursion_limit=3).

    Returns:
        KernelEnvironment: The composed environment.
    """
    config = with_limits(rig.config, **limits) if limits else rig.config
    store = CrashingRunStore(root, crash) if crash else FileRunStore(root)
    return KernelEnvironment(
        config=config, secrets=SecretSettings(), snapshot=rig.snapshot(),
        bindings=rig.runtime().bindings, repo_root=root, run_root=root, run_store=store,
        gap_store=FileGapStore(root), artifacts=FileArtifactStore(root),
        tracer=tracer or SegmentTracer(), redactor=Redactor({}, config.data_policy, []),
        jev_factory=(lambda: rig.jev) if with_jev else None)


def task_input_json(rig: Rig, goal: str = "Decide the cache store") -> dict[str, Any]:
    """Return the rig's TaskInput as the JSON a client would send."""
    return rig.task_input(goal).model_dump(mode="json")


def answer(envelope: RunEnvelope, **overrides: Any) -> InteractionSubmission:
    """Return a valid host submission for the envelope's pending host packet."""
    packet = narrow(envelope.pending_interaction).model_dump(mode="json")
    raw = raw_submission(packet, envelope.run_id, **overrides)
    return InteractionSubmission.model_validate(raw)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 13:00 [python-coder]: One environment builder serves in-process and subprocess
#   tests so they cannot drift apart. (#KernelBootstrapV0/P7)
# ====================================================================
