"""The sync writer must not publish under the serving-read transaction timeout.

knowledge/cli_sync.py's writer_backend() was the only Aura writer that left
Neo4jBackend's query_timeout at its 3.0s default. A publication writes ~9.8k
nodes and ~26.1k relationships across ~165 batched transactions, so against a
real instance that default produced
Neo.ClientError.Transaction.TransactionTimedOutClientConfiguration and the job
had never once completed.
"""

from __future__ import annotations

import unittest
from unittest import mock

from knowledge import cli_sync
from knowledge.adapters.neo4j_backend import Neo4jBackend

_ENV = {
    "LEAFCUTTER_NEO4J_URI": "neo4j+s://example.databases.neo4j.io",
    "LEAFCUTTER_NEO4J_WRITER_USERNAME": "writer",
    "LEAFCUTTER_NEO4J_WRITER_PASSWORD": "secret-value",
    "LEAFCUTTER_NEO4J_DATABASE": "example",
}


def _build_writer() -> Neo4jBackend:
    """Construct the writer through the real entrypoint with stubbed settings."""
    with mock.patch.object(cli_sync, "environment_sources", create=True, return_value=[_ENV]):
        with mock.patch(
            "knowledge.environment.environment_sources", return_value=[_ENV]
        ), mock.patch("knowledge.environment.select_value", side_effect=lambda s, *n: _ENV.get(n[0])):
            return cli_sync.writer_backend("/nonexistent-root")


class TestWriterQueryTimeout(unittest.TestCase):
    """The writer's per-transaction timeout must exceed the serving default."""

    def test_writer_does_not_use_the_serving_default(self) -> None:
        """A publication must not inherit Neo4jBackend's 3.0s read-shaped default."""
        backend = _build_writer()
        default = Neo4jBackend.__init__.__defaults__
        self.assertIn(3.0, default, "guard assumes 3.0 is still the adapter default")
        self.assertNotEqual(
            backend.query_timeout,
            3.0,
            "writer_backend left the 3.0s serving default in place; a publication "
            "cannot complete ~165 batched transactions under it",
        )

    def test_writer_matches_the_other_writer_entrypoints(self) -> None:
        """native_refresh and domain_migrate both raise it to 30; so must this."""
        self.assertEqual(_build_writer().query_timeout, 30)

    def test_constant_is_within_the_adapter_ceiling(self) -> None:
        """Neo4jBackend clamps to 30.0, so a larger constant would silently shrink."""
        self.assertLessEqual(cli_sync.WRITER_QUERY_TIMEOUT_SECONDS, 30)
        backend = _build_writer()
        self.assertEqual(backend.query_timeout, cli_sync.WRITER_QUERY_TIMEOUT_SECONDS)


if __name__ == "__main__":
    unittest.main()
