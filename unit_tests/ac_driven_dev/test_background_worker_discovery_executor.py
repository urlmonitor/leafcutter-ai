"""Read-only discovery execution contracts without model inference."""
import json
import os
import subprocess
import sys
import tomllib

import pytest

from scripts.background_worker.executors import ExecutorError, LocalCodexExecutor
from scripts.background_worker.local_outcome import parse_outcome


def events(outcome, command="cat README.md", output="project facts", exit_code=0):
    return "\n".join(map(json.dumps, [
        {"type": "item.completed", "item": {"type": "command_execution", "command": command,
            "aggregated_output": output, "exit_code": exit_code}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(outcome)}},
        {"type": "turn.completed"}]))


def test_discovery_calls_same_local_model_with_only_read_permissions(tmp_path):
    # covers: ACD-1300g-1
    protected = tmp_path / ".leafcutter/scripts"
    protected.mkdir(parents=True)
    def invoke(argv, **kwargs):
        options = tomllib.loads("\n".join(argv[i+1] for i,v in enumerate(argv) if v == "-c"))
        grants = options["permissions"]["leafcutter-worker"]["filesystem"][":workspace_roots"]
        assert grants["."] == "read" and all(v != "write" for v in grants.values())
        assert "--oss" in argv and "fixture-model" in argv
        prompt = kwargs["input_text"]
        assert "read-only" in prompt and "run checks or formatters" in prompt
        assert "approved context" in prompt
        return subprocess.CompletedProcess(argv,0,events({"status": "ready", "questions": [], "assessment": "Assigned requirements and saved decisions are sufficient to begin coding."}),"")
    executor = LocalCodexExecutor({"model":"fixture-model"},invoke=invoke)
    assert executor.discover(tmp_path,"approved context",timeout=10) == {"status": "ready", "questions": [], "assessment": "Assigned requirements and saved decisions are sufficient to begin coding."}


@pytest.mark.parametrize("command,output,code", [("echo ready","ready",0),("","content",0),
    ("cat missing","missing",1)])
def test_discovery_rejects_bare_ready_regardless_of_tool_activity(command, output, code):
    # covers: ACD-1300g-1
    with pytest.raises(ExecutorError,match="assessment"):
        parse_outcome(events({"status":"ready","questions":[]},command,output,code),discovery=True)


@pytest.mark.parametrize("outcome", [{"status":"ready","questions":["confirm"]},
    {"status":"needs_input","questions":[]},{"status":"completed","questions":[]}])
def test_discovery_rejects_contradictory_outcomes(outcome):
    # covers: ACD-1300g-1
    with pytest.raises(ExecutorError):
        parse_outcome(events(outcome),discovery=True)


def test_discovery_rejects_model_supplied_approval():
    # covers: ACD-1300e-1
    with pytest.raises(ExecutorError, match="undeclared fields"):
        parse_outcome(events({"status":"needs_input","questions":["Choose policy"],
            "gate_approved":True,"resolved_user_decisions":["invented"]}),discovery=True)



@pytest.mark.skipif(os.environ.get("LEAFCUTTER_TEST_REAL_SANDBOX") != "1" or not sys.platform.startswith("linux"),
    reason="Opt-in real Linux sandbox; no inference")
def test_real_discovery_workspace_is_readonly_for_all_specific_paths(tmp_path):
    # covers: ACD-1300g-1
    workspace=tmp_path/"workspace"
    workspace.mkdir()
    names=["existing.txt","subdir/existing.txt",".leafcutter/scripts/guard.py",".codex/config.toml",".git"]
    for name in names:
        p=workspace/name
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text("sentinel")
    (workspace/"alias").symlink_to(workspace/"existing.txt")
    script="""from pathlib import Path
p=Path.cwd()
assert (p/'existing.txt').read_text()=='sentinel'
for name in ['existing.txt','subdir/existing.txt','.leafcutter/scripts/guard.py','.codex/config.toml','.git','alias','new.txt','subdir/new.txt']:
    try: (p/name).write_text('forbidden')
    except OSError: pass
    else: raise AssertionError('write permitted: '+name)
print('read succeeded; writes denied')
"""
    result=LocalCodexExecutor({"model":"not-invoked"}).check(workspace,[sys.executable,"-c",script],timeout=30,readonly=True)
    assert "read succeeded" in result.stdout
    for name in names:
        assert (workspace/name).read_text()=="sentinel"
    assert not (workspace/"new.txt").exists() and not (workspace/"subdir/new.txt").exists()


@pytest.mark.parametrize("command,output", [
    ("/usr/bin/cat README.md", "facts"),
    ("/bin/bash -lc '/usr/bin/head README.md'", "facts"),
    ("cat empty.txt", ""),
    ("/usr/bin/rg --files", "README.md"),
])
def test_discovery_accepts_inspection_activity_without_claiming_semantic_proof(command, output):
    # covers: ACD-1300g-1
    assert parse_outcome(events({"status": "ready", "questions": [], "assessment": "Assigned requirements and saved decisions are sufficient to begin coding."}, command, output),
                         discovery=True) == {"status": "ready", "questions": [], "assessment": "Assigned requirements and saved decisions are sufficient to begin coding."}
