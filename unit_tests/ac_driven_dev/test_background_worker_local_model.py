"""Local model catalog and configuration contracts without network or inference."""

import json
from pathlib import Path
import subprocess
import tomllib

import pytest

from scripts.background_worker.local_model import write_catalog
from scripts.background_worker.settings import validate


@pytest.mark.parametrize("metadata,expected", [
    ({}, "none"),
    ({"thinking": {"values": [False, True], "default": True}}, "high"),
    ({"thinking": {"values": [False, True], "default": False}}, "none"),
    ({"thinking": {"values": [True, False]}}, "none"),
    ({"thinking": {"values": [True], "default": True}}, "high"),
    ({"thinking": {"values": ["low", "medium", "high"], "default": "medium"}}, "medium"),
])
def test_catalog_chooses_supported_thinking_without_host_profile(tmp_path, metadata, expected):
    # covers: ACD-1300g-1
    path, effort, window = write_catalog(tmp_path, "qwen-fixture", metadata)
    catalog = json.loads(path.read_text())["models"]
    assert len(catalog) == 1
    entry = catalog[0]
    assert path.parent == tmp_path and effort == expected and window == 65536
    assert entry["slug"] == entry["display_name"] == "qwen-fixture"
    assert entry["default_reasoning_level"] == expected
    assert entry["base_instructions"] == ""
    assert entry["context_window"] == 65536
    assert entry["supports_parallel_tool_calls"] is False
    assert entry["experimental_supported_tools"] == []


def test_catalog_bounds_context_and_preserves_explicit_supported_effort(tmp_path):
    # covers: ACD-1300g-1
    metadata = {"thinking": {"values": [False, True]},
                "model_info": {"qwen.context_length": 32768}}
    path, effort, window = write_catalog(tmp_path, "fixture", metadata, 65536, "high")
    assert effort == "high" and window == 32768
    entry = json.loads(path.read_text())["models"][0]
    assert [level["effort"] for level in entry["supported_reasoning_levels"]] == ["none", "high"]
    assert entry["context_window"] == window


@pytest.mark.parametrize("window", [True, 0, -1, "65536", 3.5])
def test_invalid_context_rejected_before_catalog_write(tmp_path, window):
    # covers: ACD-1300g-1-i
    with pytest.raises(ValueError, match="context_window"):
        write_catalog(tmp_path, "fixture", context_window=window)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("effort", [True, "unknown", "high"])
def test_unsupported_explicit_effort_rejected(tmp_path, effort):
    # covers: ACD-1300g-1-i
    with pytest.raises(ValueError, match="reasoning"):
        write_catalog(tmp_path, "nonthinking-fixture", reasoning_effort=effort)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("extra", [{"context_window": 65536}, {"reasoning_effort": "none"}])
def test_optional_local_model_settings_are_accepted(extra):
    # covers: ACD-1300g-1
    validate({"implementation": {"executor": "codex-cli", "provider": "ollama",
                                 "model": "fixture", **extra}})


@pytest.mark.parametrize("extra", [{"context_window": False}, {"context_window": 0},
                                  {"reasoning_effort": "unknown"}, {"reasoning_effort": True}])
def test_invalid_local_model_settings_are_rejected(extra):
    # covers: ACD-1300g-1-i
    with pytest.raises(ValueError):
        validate({"implementation": {"executor": "codex-cli", "provider": "ollama",
                                     "model": "fixture", **extra}})


def test_implementation_uses_ephemeral_verified_catalog_and_bounded_context(tmp_path, monkeypatch):
    # covers: ACD-1300g-1, ACD-1300b-1
    from scripts.background_worker.executors import LocalCodexExecutor

    host = tmp_path / "host-profile"
    host.mkdir()
    (host / "config.toml").write_text("host secret profile must not be imported")
    monkeypatch.setenv("CODEX_HOME", str(host))
    paths = []

    def invoke(argv, **kwargs):
        home = Path(kwargs["env"]["CODEX_HOME"])
        options = tomllib.loads("\n".join(argv[i + 1] for i, value in enumerate(argv) if value == "-c"))
        path = Path(options["model_catalog_json"])
        paths.append(path)
        assert path.parent == home and home != host
        entry = json.loads(path.read_text())["models"][0]
        assert entry["default_reasoning_level"] == options["model_reasoning_effort"] == "high"
        assert entry["context_window"] == options["model_context_window"] == 32768
        assert options["model_auto_compact_token_limit"] == 24576
        assert options["web_search"] == "disabled"
        assert options["permissions"]["leafcutter-worker"]["filesystem"][":root"] == "deny"
        assert "--ignore-user-config" in argv and "--ignore-rules" in argv
        assert "host secret" not in (home / "config.toml").read_text()
        events = [{"type": "item.completed", "item": {"type": "command_execution", "exit_code": 0}},
                  {"type": "item.completed", "item": {"type": "agent_message", "text":
                      '{"status":"completed","questions":[]}'}}, {"type": "turn.completed"}]
        return subprocess.CompletedProcess(argv, 0, "\n".join(map(json.dumps, events)), "")

    executor = LocalCodexExecutor({"model": "fixture", "context_window": 65536}, invoke=invoke)
    executor.metadata = {"thinking": {"values": [True]}, "model_info": {"fixture.context_length": 32768}}
    assert executor.implement(tmp_path, "approved context", timeout=10)["status"] == "completed"
    assert len(paths) == 1 and not paths[0].exists()
    assert (host / "config.toml").read_text() == "host secret profile must not be imported"



def test_explicit_none_overrides_advertised_thinking_default(tmp_path):
    # covers: ACD-1300g-1
    path, effort, _ = write_catalog(tmp_path, "fixture", {
        "thinking": {"values": [False, True], "default": True}}, reasoning_effort="none")
    assert effort == "none"
    assert json.loads(path.read_text())["models"][0]["default_reasoning_level"] == "none"


@pytest.mark.parametrize("default", [True, "medium", "unsupported", None])
@pytest.mark.parametrize("override", [None, "none"])
def test_unsupported_advertised_default_fails_without_writing(tmp_path, default, override):
    # covers: ACD-1300g-1-i
    with pytest.raises(ValueError, match="reasoning"):
        write_catalog(tmp_path, "fixture", {
            "thinking": {"values": [False], "default": default}}, reasoning_effort=override)
    assert not list(tmp_path.iterdir())
