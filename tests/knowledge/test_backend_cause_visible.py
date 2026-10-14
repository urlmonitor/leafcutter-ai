"""MODULE: test_backend_cause_visible
GOAL: Prove BackendUnavailable names the underlying driver failure.
BUSINESS CONTEXT: Sixty identical "backend unavailable" CI failures hid two root causes.
ARCHITECTURE: Drives the real Neo4jBackend._transaction path with a failing driver double.

DECISION HISTORY
========================================
- 2026-10-09 12:00 [python-coder]: Cover cause visibility, no-code exceptions and bounded length.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

pytest.importorskip("neo4j")

from neo4j.exceptions import Neo4jError

from knowledge.adapters.neo4j_backend import Neo4jBackend
from knowledge.errors import BackendUnavailable

SECRET_URI = "neo4j+s://user:hunter2@example.invalid"


def _server_error(code: str, message: str) -> Neo4jError:
    """Build the concrete Neo4jError subclass the driver raises for a server code."""
    return Neo4jError._hydrate_neo4j(code=code, message=message)


def _backend(error: BaseException) -> Neo4jBackend:
    """Build a backend whose driver session raises the given error."""
    backend = object.__new__(Neo4jBackend)
    backend.database = "neo4j"
    backend.query_timeout = 1.0
    backend.driver = MagicMock()
    session = backend.driver.session.return_value.__enter__.return_value
    session.execute_read.side_effect = error
    session.execute_write.side_effect = error
    return backend


def _raised(error: BaseException) -> BackendUnavailable:
    """Run a transaction against the failing driver and return the normalized error."""
    with pytest.raises(BackendUnavailable) as caught:
        asyncio.run(_backend(error)._transaction(lambda tx: None))
    return caught.value


def test_neo4j_error_exposes_class_code_and_message() -> None:
    """The class name, code and server message must all reach the caller."""
    cause = _server_error(
        "Neo.DatabaseError.Statement.ExecutionFailed",
        "The database 2fb38dda is in read-only mode on this Neo4j server",
    )
    raised = _raised(cause)
    text = str(raised)
    assert type(cause).__name__ in text
    assert "Neo.DatabaseError.Statement.ExecutionFailed" in text
    assert "read-only mode" in text
    assert raised.__cause__ is cause


def test_public_contract_is_unchanged() -> None:
    """Status category and retryability must survive the richer message."""
    raised = _raised(_server_error("Neo.ClientError.Database.DatabaseNotFound", "x"))
    assert raised.code == "unavailable"
    assert raised.retryable is True


def test_exception_without_code_attribute() -> None:
    """OSError has no .code; the message still names the class and text."""
    raised = _raised(OSError("connection refused"))
    assert "OSError" in str(raised)
    assert "connection refused" in str(raised)
    assert "None" not in str(raised)


def test_message_is_bounded() -> None:
    """A pathological server message cannot flood logs."""
    raised = _raised(OSError("A" * 100_000))
    assert len(str(raised)) < 1000


def test_message_never_contains_connection_secrets() -> None:
    """The adapter must not interpolate its URI or credentials into the message."""
    raised = _raised(OSError("connection refused"))
    assert "hunter2" not in str(raised)
    assert SECRET_URI not in str(raised)
