"""Tool-capable generation retains strict post-turn reply validation."""
import json
from pathlib import Path
import subprocess

import jsonschema
import pytest

from scripts.background_worker.executors import ExecutorError, LocalCodexExecutor
from scripts.background_worker.reply_contract import reply_schema
from .test_background_worker_discovery_contract import transcript, ready


@pytest.mark.parametrize("discovery", [False, True])
def test_tool_turn_uses_prompt_contract_without_forced_generation_schema(tmp_path, discovery):
    # covers: ACD-1300g-1
    # angle: seam
    homes = []
    reply = ready() if discovery else {"status": "completed", "questions": []}
    def invoke(argv, **kwargs):
        assert not any(arg == "--output-schema" or arg.startswith("--output-schema=") for arg in argv)
        home = Path(kwargs["env"]["CODEX_HOME"])
        homes.append(home)
        assert not (home / "outcome.schema.json").exists()
        schema = json.JSONDecoder().raw_decode(kwargs["input_text"].split("Final-response JSON Schema: ")[1])[0]
        assert schema == reply_schema(discovery=discovery)
        jsonschema.validate(reply, schema)
        (tmp_path / "tool-sentinel").write_text("tool performed")
        return subprocess.CompletedProcess(argv, 0, transcript(reply, tool=True), "")
    executor = LocalCodexExecutor({"model": "fixture"}, invoke=invoke)
    method = executor.discover if discovery else executor.implement
    result = method(tmp_path, "context", timeout=10)
    assert result["status"] == reply["status"] and result["questions"] == []
    assert (tmp_path / "tool-sentinel").read_text() == "tool performed"
    assert len(homes) == 1 and not homes[0].exists()


@pytest.mark.parametrize("discovery", [False, True])
@pytest.mark.parametrize("invalid", ["prose", "missing", "forged"])
def test_unconstrained_generation_still_rejects_invalid_final_report(tmp_path, discovery, invalid):
    # covers: ACD-1300g-1-i
    # angle: failure
    reply = ready() if discovery else {"status": "completed", "questions": []}
    if invalid == "missing":
        reply.pop("questions")
    elif invalid == "forged":
        reply["approved"] = True
    lines = [json.loads(line) for line in transcript(reply, tool=True).splitlines()]
    if invalid == "prose":
        lines[-2]["item"]["text"] = "Here is my report: " + lines[-2]["item"]["text"]
    calls = []
    def invoke(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "\n".join(map(json.dumps, lines)), "")
    executor = LocalCodexExecutor({"model": "fixture"}, invoke=invoke)
    method = executor.discover if discovery else executor.implement
    with pytest.raises(ExecutorError) as caught:
        method(tmp_path, "context", timeout=10)
    assert caught.value.stop_run and len(calls) == 1


def test_implementation_completion_without_tool_event_still_blocks(tmp_path):
    # covers: ACD-1300g-1-i
    # angle: failure
    def invoke(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, transcript({"status": "completed", "questions": []}), "")
    with pytest.raises(ExecutorError, match="actual tool"):
        LocalCodexExecutor({"model": "fixture"}, invoke=invoke).implement(tmp_path, "context", timeout=10)
