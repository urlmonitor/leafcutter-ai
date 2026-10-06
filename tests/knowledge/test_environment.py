"""Serving credentials follow explicit source precedence without secret disclosure."""

import sys
from types import SimpleNamespace
import pytest
from knowledge.config import KnowledgeConfig, build_retriever
from knowledge.errors import InvalidRequest


def backend_capture(monkeypatch):
    received = []
    monkeypatch.setitem(
        sys.modules,
        "knowledge.adapters.neo4j_backend",
        SimpleNamespace(
            Neo4jBackend=lambda *args, **kwargs: received.append((args, kwargs)) or object()
        ),
    )
    return received


def isolate(monkeypatch, tmp_path):
    for name in tuple(__import__("os").environ):
        if name.startswith(("NEO4J_", "LEAFCUTTER_NEO4J_")) or name == "LEAFCUTTER_ENV_FILE":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LEAFCUTTER_ENV_FILE", str(tmp_path / ".env"))


def test_aura_dotenv_default_user_does_not_use_instance_as_database(monkeypatch, tmp_path):
    # covers: KM-400e-1
    # angle: seam
    isolate(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text(
        'export NEO4J_URI="neo4j+s://example.databases.neo4j.io"\nNEO4J_PASSWORD=fixture-secret\nNEO4J_INSTANCE=instance-id\n'
    )
    received = backend_capture(monkeypatch)
    build_retriever(KnowledgeConfig(backend="neo4j"))
    assert received == [
        (
            ("neo4j+s://example.databases.neo4j.io", "neo4j", "fixture-secret"),
            {"database": "neo4j", "query_timeout": 3.0},
        )
    ]
    assert "NEO4J_PASSWORD" not in __import__("os").environ


def test_environment_alias_beats_file_legacy_name(monkeypatch, tmp_path):
    # covers: KM-400e-1
    # angle: criterion
    isolate(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text(
        "LEAFCUTTER_NEO4J_URI=neo4j+s://file.example\n"
        "LEAFCUTTER_NEO4J_USERNAME=file-user\n"
        "LEAFCUTTER_NEO4J_PASSWORD=file-secret\n"
        ""
    )
    monkeypatch.setenv("NEO4J_URI", "neo4j+s://environment.example")
    monkeypatch.setenv("NEO4J_USERNAME", "environment-user")
    monkeypatch.setenv("NEO4J_PASSWORD", "environment-secret")
    received = backend_capture(monkeypatch)
    build_retriever(KnowledgeConfig(backend="neo4j"))
    assert received[0][0] == (
        "neo4j+s://environment.example",
        "environment-user",
        "environment-secret",
    )


def test_custom_environment_name_does_not_fall_back_or_leak(monkeypatch, tmp_path, capsys):
    # covers: KM-400e-1
    # angle: adversarial
    isolate(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text(
        "NEO4J_URI=neo4j+s://example.databases.neo4j.io\nNEO4J_PASSWORD=must-not-leak\n"
    )
    with pytest.raises(InvalidRequest) as error:
        build_retriever(KnowledgeConfig(backend="neo4j", neo4j_password_env="CUSTOM_PASSWORD"))
    assert "CUSTOM_PASSWORD" in str(error.value)
    assert "must-not-leak" not in str(error.value) + repr(error.value) + str(capsys.readouterr())


def test_disabled_does_not_read_named_file(monkeypatch, tmp_path):
    # covers: KM-400e-1
    # angle: reachability
    isolate(monkeypatch, tmp_path)
    from pathlib import Path

    monkeypatch.setattr(Path, "read_text", lambda *a, **k: pytest.fail("disabled read credentials"))
    assert build_retriever(KnowledgeConfig()).__class__.__name__ == "NullKnowledgeRetriever"


def test_legacy_wins_same_source_and_nearest_file_walk(monkeypatch, tmp_path):
    # covers: KM-400e-1
    # angle: seam
    isolate(monkeypatch, tmp_path)
    monkeypatch.delenv("LEAFCUTTER_ENV_FILE")
    child = tmp_path / "worktree"
    child.mkdir()
    monkeypatch.chdir(child)
    (tmp_path / ".env").write_text(
        "\ufeffNEO4J_URI=neo4j+s://alias.example\n"
        "LEAFCUTTER_NEO4J_URI=neo4j+s://legacy.example\n"
        "NEO4J_USERNAME=alias-user\n"
        "LEAFCUTTER_NEO4J_USERNAME=legacy-user\n"
        "NEO4J_PASSWORD=alias-secret\n"
        "LEAFCUTTER_NEO4J_PASSWORD=legacy-secret\n"
        "",
        encoding="utf-8",
    )
    received = backend_capture(monkeypatch)
    build_retriever(KnowledgeConfig(backend="neo4j"))
    assert received[0][0] == ("neo4j+s://legacy.example", "legacy-user", "legacy-secret")


def test_named_file_missing_is_secret_safe_configuration_error(monkeypatch, tmp_path):
    # covers: KM-400e-1
    # angle: adversarial
    isolate(monkeypatch, tmp_path)
    with pytest.raises(InvalidRequest, match="named LEAFCUTTER_ENV_FILE"):
        build_retriever(KnowledgeConfig(backend="neo4j"))


def test_writer_accepts_shared_uri_but_never_serving_password(monkeypatch, tmp_path):
    # covers: KM-400e-5
    # angle: seam
    isolate(monkeypatch, tmp_path)
    from knowledge.cli_sync import writer_backend

    fixture = tmp_path / ".env"
    fixture.write_text(
        "NEO4J_URI=neo4j+s://example.databases.neo4j.io\nNEO4J_PASSWORD=serving-secret\n"
    )
    received = backend_capture(monkeypatch)
    with pytest.raises(ValueError, match="WRITER_PASSWORD"):
        writer_backend()
    fixture.write_text(
        fixture.read_text() + "LEAFCUTTER_NEO4J_WRITER_USERNAME=writer\n"
        "LEAFCUTTER_NEO4J_WRITER_PASSWORD=writer-secret\n"
        ""
    )
    writer_backend()
    assert received[0][0] == ("neo4j+s://example.databases.neo4j.io", "writer", "writer-secret")


def test_unreadable_discovered_file_warns_without_secret_details(monkeypatch, tmp_path, caplog):
    # covers: KM-400e-1
    # angle: adversarial
    isolate(monkeypatch, tmp_path)
    monkeypatch.delenv("LEAFCUTTER_ENV_FILE")
    (tmp_path / ".env").write_text("ignored")
    from pathlib import Path

    def denied(*args, **kwargs):
        raise PermissionError("must-not-leak")

    monkeypatch.setattr(Path, "read_text", denied)
    with pytest.raises(InvalidRequest):
        build_retriever(KnowledgeConfig(backend="neo4j"))
    assert "could not read discovered knowledge env file" in caplog.text
    assert "must-not-leak" not in caplog.text


def test_empty_environment_falls_back_to_file_like_kernel(monkeypatch, tmp_path):
    # covers: KM-400e-1
    # angle: seam
    isolate(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text(
        "NEO4J_URI=neo4j+s://example.databases.neo4j.io\nNEO4J_PASSWORD=fixture-secret\n"
    )
    monkeypatch.setenv("NEO4J_PASSWORD", "")
    received = backend_capture(monkeypatch)
    build_retriever(KnowledgeConfig(backend="neo4j"))
    assert received[0][0][2] == "fixture-secret"


def test_database_env_alias_applies_to_serving_and_writer(monkeypatch, tmp_path):
    # covers: KM-400e-1
    # covers: KM-400e-5
    # angle: seam
    isolate(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text(
        "NEO4J_URI=neo4j+s://example.databases.neo4j.io\n"
        "NEO4J_PASSWORD=fixture-secret\n"
        "NEO4J_DATABASE=aura-home\n"
        "LEAFCUTTER_NEO4J_WRITER_USERNAME=writer\n"
        "LEAFCUTTER_NEO4J_WRITER_PASSWORD=writer-secret\n"
        ""
    )
    received = backend_capture(monkeypatch)
    build_retriever(KnowledgeConfig(backend="neo4j"))
    from knowledge.cli_sync import writer_backend

    writer_backend()
    assert [kwargs["database"] for _, kwargs in received] == ["aura-home", "aura-home"]
    build_retriever(KnowledgeConfig(backend="neo4j", database="neo4j"))
    assert received[-1][1]["database"] == "neo4j"


def test_database_source_and_legacy_alias_precedence(monkeypatch, tmp_path):
    # covers: KM-400e-1
    # angle: criterion
    isolate(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text(
        "NEO4J_URI=neo4j+s://example.databases.neo4j.io\n"
        "NEO4J_PASSWORD=fixture-secret\n"
        "LEAFCUTTER_NEO4J_DATABASE=file-db\n"
        ""
    )
    monkeypatch.setenv("NEO4J_DATABASE", "process-db")
    received = backend_capture(monkeypatch)
    build_retriever(KnowledgeConfig(backend="neo4j"))
    assert received[-1][1]["database"] == "process-db"
    monkeypatch.setenv("LEAFCUTTER_NEO4J_DATABASE", "legacy-db")
    build_retriever(KnowledgeConfig(backend="neo4j"))
    assert received[-1][1]["database"] == "legacy-db"
