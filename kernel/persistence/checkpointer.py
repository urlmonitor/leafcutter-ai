"""
MODULE: kernel.persistence.checkpointer
GOAL: Build the strict checkpoint serializer and the AsyncSqliteSaver factory for the kernel graph.
BUSINESS CONTEXT: Graph state (Pydantic contracts) must round-trip through the checkpoint so a
    paused run resumes after a process restart, while untrusted checkpoint bytes must never be
    able to instantiate arbitrary classes (Rev 3 section 13.1; LANGGRAPH_STRICT_MSGPACK).
ARCHITECTURE: build_serializer allowlists exactly the contract models and enums (plus caller
    extras such as the graph state types) on JsonPlusSerializer, independent of the strict env
    flag. open_checkpointer is an async context manager: it opens checkpoints.sqlite, enables
    WAL, runs setup and closes the connection on exit; thread_id is the run id by convention.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from kernel.contracts import ALL_MODELS
from kernel.observability.tracer import TraceState
from kernel.persistence.base import ArtifactRef, CancelInfo, RunRecord, SubmissionRecord

logger = logging.getLogger(__name__)

CHECKPOINT_DB_NAME = "checkpoints.sqlite"
_PERSISTENCE_TYPES: tuple[type, ...] = (TraceState, RunRecord, CancelInfo, SubmissionRecord,
                                        ArtifactRef)


def checkpoint_path(run_root: Path) -> Path:
    """Return <run_root>/checkpoints.sqlite."""
    return Path(run_root) / CHECKPOINT_DB_NAME


def build_serializer(extra_types: Iterable[type] = ()) -> JsonPlusSerializer:
    """Return a serializer that only revives the kernel contracts (and the given extras).

    Args:
        extra_types: Additional classes allowed in checkpoints (for example state dataclasses).

    Returns:
        JsonPlusSerializer: Explicit msgpack allowlist; everything else stays inert.
    """
    allowed = [*ALL_MODELS, *_PERSISTENCE_TYPES, *extra_types]
    return JsonPlusSerializer(allowed_msgpack_modules=allowed)


@asynccontextmanager
async def open_checkpointer(run_root: Path, *, extra_types: Iterable[type] = ()
                            ) -> AsyncIterator[AsyncSqliteSaver]:
    """Open checkpoints.sqlite under run_root as a ready AsyncSqliteSaver.

    Args:
        run_root: Kernel run root; created if missing.
        extra_types: Additional classes allowed by the serializer.

    Yields:
        AsyncSqliteSaver: Set up saver using the strict serializer.
    """
    path = checkpoint_path(run_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(str(path))
    except (OSError, sqlite3.Error):
        logger.exception("cannot open checkpoint database %s", path)
        raise
    try:
        await conn.execute("PRAGMA journal_mode=WAL")
        saver = AsyncSqliteSaver(conn, serde=build_serializer(extra_types))
        await saver.setup()
        yield saver
    finally:
        await conn.close()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: aiosqlite.connect is used directly because
#   AsyncSqliteSaver.from_conn_string accepts no serde argument. (#KernelBootstrapV0/P2)
# ====================================================================
