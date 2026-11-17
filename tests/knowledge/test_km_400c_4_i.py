"""KM-400c-4-i: the embedding ingestion job requires a provider.

embed_snapshot binds every vector it publishes to its provider's model and
dimensions, and reads both unconditionally. Its declared contract must
therefore not admit a missing provider, and its only real caller, the
synthetic demonstration, must hand it the provider it constructed.
"""

import asyncio
import importlib
import inspect
import typing

import pytest


def test_embed_snapshot_provider_parameter_does_not_admit_none():
    # covers: KM-400c-4-i
    # angle: discrimination
    jobs = importlib.import_module("knowledge.embedding_jobs")
    ports = importlib.import_module("knowledge.ports")

    provider_type = typing.get_type_hints(jobs.embed_snapshot)["provider"]

    assert type(None) not in typing.get_args(provider_type), (
        "embed_snapshot declares provider as %r, which admits None, but it reads "
        "provider.model, provider.dimensions and provider.embed unconditionally" % (provider_type,)
    )
    assert provider_type is ports.EmbeddingProvider, (
        "embed_snapshot must declare provider as knowledge.ports.EmbeddingProvider, got %r"
        % (provider_type,)
    )
    parameter = inspect.signature(jobs.embed_snapshot).parameters["provider"]
    assert parameter.default is inspect.Parameter.empty, (
        "embed_snapshot gives provider the default %r, so a caller can leave it out"
        % (parameter.default,)
    )


def test_synthetic_demo_embeds_with_the_provider_it_constructs(monkeypatch):
    # covers: KM-400c-4-i
    # angle: reachability
    demo = importlib.import_module("knowledge.examples.synthetic_demo")
    jobs = importlib.import_module("knowledge.embedding_jobs")
    real_embed_snapshot = jobs.embed_snapshot
    seen = {}

    class StopAfterEmbedding(Exception):
        """Ends the demonstration once its embedding step has run."""

    class RecordingWriter:
        """Stands in for the Neo4j backend up to and including the embedding step."""

        def __init__(self, *args):
            self.writes = []
            self.closed = False

        async def setup(self):
            return None

        async def publish(self, snapshot):
            return None

        async def put_embeddings(
            self, repository_id, generation_id, embeddings, *, model, dimensions, content_hashes
        ):
            self.writes.append(
                {
                    "generation_id": generation_id,
                    "ids": sorted(embeddings),
                    "model": model,
                    "dimensions": dimensions,
                }
            )

        async def close(self):
            self.closed = True

    async def recording_embed_snapshot(writer, snapshot, provider, **kwargs):
        seen["writer"] = writer
        seen["provider"] = provider
        seen["result"] = await real_embed_snapshot(writer, snapshot, provider, **kwargs)
        raise StopAfterEmbedding

    monkeypatch.setattr(demo, "Neo4jBackend", RecordingWriter)
    monkeypatch.setattr(demo, "embed_snapshot", recording_embed_snapshot)

    with pytest.raises(StopAfterEmbedding):
        asyncio.run(demo.run_demo())

    assert seen["provider"] is not None
    assert isinstance(seen["provider"], demo.FixtureEmbeddings)
    result = seen["result"]
    assert result["embedded_entities"] == 3
    assert result["model"] == "synthetic-fixture-v1"
    assert result["dimensions"] == 2
    writer = seen["writer"]
    assert writer.writes == [
        {
            "generation_id": "synthetic-v1",
            "ids": ["D-new", "D-old", "L"],
            "model": "synthetic-fixture-v1",
            "dimensions": 2,
        }
    ]
    assert writer.closed is True
