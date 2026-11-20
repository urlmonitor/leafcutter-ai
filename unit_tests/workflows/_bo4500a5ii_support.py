"""
MODULE: unit_tests/workflows/_bo4500a5ii_support.py
GOAL: Shared drivers for the BO-4500a-5-ii tests (plan-feature's commits go through the shared commit step).
    Not collected: no tests here.
ARCHITECTURE:
    - ba_gate_run resumes the REAL plan-feature.js (run_workflow_under_e2) at gate-ba with a person's approve;
      the stage's four records come from the pause record's context, the rule check reports the five records
      to commit (four children and the edited parent), and `commit-stage-output` answers with a scripted reply.
    - drive runs ONE real plan-feature.js commit helper (commitStageOutput, commitStageOutputProductTruth,
      runFlowReconciliation, resolveOrphanedDrafts) in isolation through run_isolated_e2 and returns every
      dispatch it made, so each of the five commit paths is observed on its own.
"""

from __future__ import annotations

import json
import re
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from _acd_300a_support import fresh_table, run, triage  # noqa: E402
from _plan_feature_e2_runner import run_isolated_e2  # noqa: E402

RUN = "plan-bo-100k-20261012"
STORE = "docs/acceptance-criteria"
FOLDER = f"{STORE}/reliable-builds/BP-100-reliable-builds"
PARENT = "BP-100k-4"
CHILDREN = ["BP-100k-4-iv", "BP-100k-4-v", "BP-100k-4-vi", "BP-100k-4-vii"]
# A hand recipe: the commit agent staging or committing by a recipe of its own.
RAW_RECIPE = re.compile(r"git\s+(?:-C\s+\S+\s+)?(?:add|commit)\b|COMMIT_AGENT_MODE")
STEP_NAME = "commit_changes.py"


def rel(ac_id: str) -> str:
    return f"{FOLDER}/{ac_id}.yaml"


FIVE = [rel(c) for c in CHILDREN] + [rel(PARENT)]


def committed_answer(sha: str = "abc1234") -> dict:
    answer = {"status": "committed", "reason_code": None, "reason": None, "sha": sha}
    return {"status": "committed", "commit_answer": answer}


def non_committed_answer(status: str, reason_code: str, reason: str, hook_name=None, failing_files=None) -> dict:
    answer = {
        "status": status, "reason_code": reason_code, "reason": reason, "sha": None,
        "hook_name": hook_name, "failing_files": list(failing_files or []),
    }
    return {"status": status, "commit_answer": answer}


def ba_gate_run(commit_reply: dict):
    """Resume plan-feature.js at gate-ba, approve, and script the stage's commit reply."""
    record = {"exists": True, "stale": False, "record": {
        "run_id": RUN, "gate_id": "gate-ba", "status": "paused_awaiting_input",
        "question": {"type": "single_choice", "gate_id": "gate-ba", "options": ["approve", "edit", "cancel"]},
        "context": {"stage": "ba", "acs": list(CHILDREN)},
    }}
    report = json.dumps({"verdict": "passed", "location": STORE, "records_checked": 5, "findings": [],
                         "records_to_commit": list(FIVE)})
    table = fresh_table(triage("behavioral"), **{
        "peek-pause-record": record, "read-pause-record": record, "pause-persist-verify": record,
        "branch-check": {"output": "ac-authoring/bo-4500a-5-ii", "exit_code": 0},
        "rule-check-ba": {"output": report, "exit_code": 0, "stderr": ""},
        "commit-stage-output": commit_reply,
    })
    answer = {"gate_id": "gate-ba", "type": "single_choice", "action": "approve", "channel": "person"}
    return run(table, {"run_id": RUN, "resume_answer": answer})


def drive(function_names: list[str], call_js: str, replies: dict | None = None) -> dict:
    """Run `await <call_js>` with the real helper functions; returns {res, prompts: [{label, prompt}]}."""
    driver = textwrap.dedent(f"""
        const prompts = [];
        const replies = {json.dumps(replies or {})};
        const log = () => {{}};
        const agent = async (prompt, opts) => {{
            const label = (opts && opts.label) || '';
            prompts.push({{ label, prompt }});
            if (label === 'branch-check') return {{ output: 'ac-authoring/bo-4500a-5-ii', exit_code: 0 }};
            if (Object.prototype.hasOwnProperty.call(replies, label)) return replies[label];
            return {{ status: 'ok' }};
        }};
        (async () => {{
            const res = await {call_js};
            process.stdout.write(JSON.stringify({{ res, prompts }}));
        }})().catch(err => {{ process.stderr.write(String(err)); process.exit(1); }});
    """)
    return json.loads(run_isolated_e2(function_names, driver, timeout=30))


def commit_prompts(run_out: dict, label_prefix: str = "commit") -> list[str]:
    return [p["prompt"] for p in run_out["prompts"] if p["label"].startswith(label_prefix)]


def stage_commit(is_final: bool, paths: list[str], stage: str = "ba") -> dict:
    """commitStageOutput for the stage/final commit, naming `paths` as the rule check's records_to_commit."""
    call = (f"commitStageOutput({json.dumps(list(CHILDREN))}, {json.dumps(stage)}, 'build-orchestration', "
            f"{json.dumps(is_final)}, {json.dumps(RUN)}, {json.dumps(STORE)}, '/wt', {json.dumps(paths)})")
    return drive(["commitStageOutput", "stageDisplayName"], call, {"commit-stage-output": committed_answer()})


def orphan_commit(orphan_paths: list[str]) -> dict:
    orphans = [{"filePath": p, "acId": Path(p).stem} for p in orphan_paths]
    call = f"resolveOrphanedDrafts({json.dumps(orphans)}, {json.dumps(STORE)}, {json.dumps(RUN)}, '/wt', 'yes')"
    return drive(["resolveOrphanedDrafts", "commitStageOutput", "stageDisplayName"], call,
                 {"commit-stage-output": committed_answer()})


def product_truth_commit(paths: list[str]) -> dict:
    call = (f"commitStageOutputProductTruth({json.dumps(paths)}, 'flow', 'build-orchestration', "
            f"{json.dumps(RUN)}, 'docs/product-truth', '/wt')")
    return drive(["commitStageOutputProductTruth", "stageDisplayName"], call,
                 {"commit-stage-output-product-truth": committed_answer()})


def reconciliation_commit(flow_ref: str, script_output: str = "{}") -> dict:
    """runFlowReconciliation; `script_output` is the reconcile script's stdout (its rewritten_acs JSON report)."""
    call = (f"runFlowReconciliation({json.dumps(flow_ref)}, {{ 'step-1': ['BP-100k-4-iv'] }}, 'build-orchestration', "
            f"{json.dumps(RUN)}, 'docs/product-truth', '/wt')")
    replies = {
        "pt-reconcile-run": {"output": script_output, "exit_code": 0, "stderr": ""},
        "commit-flow-reconciliation": committed_answer(),
    }
    return drive(["runFlowReconciliation", "resolvePathOntoRoot", "classifyPathForm", "normalizePathForm"], call, replies)


def step_command(prompt: str) -> str | None:
    """The line of `prompt` that runs the shared step, or None when the prompt does not run it."""
    for line in prompt.splitlines():
        if STEP_NAME in line:
            return line
    return None


def command_paths(command: str) -> list[str]:
    """The record paths a step command names (everything after the script that is not an option or its value)."""
    tail = command.split(STEP_NAME, 1)[1]
    tail = re.sub(r"--message-file\s+(?:\"[^\"]*\"|'[^']*'|<[^>]*>|\S+)", " ", tail)
    tail = re.sub(r"--run\s+\S+", " ", tail)
    tail = tail.replace("--supervised", " ")
    paths = []
    for token in tail.split():
        token = token.strip("\"'`")
        if token.startswith("/wt/"):
            token = token[len("/wt/"):]
        if token.endswith(".yaml") or token.endswith(".json"):
            paths.append(token)
    return paths
