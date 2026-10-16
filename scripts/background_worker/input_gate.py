"""Coordinator-owned operator input proofs before writable model execution."""
import re
from .git_ops import GitOps
from .planning import _digest, _parent


def declarations(run, ac_id):
    records = run["plan"].get("source_context", {}).get("obligations", {})
    result, seen = [], set()
    current = ac_id
    while current and current not in seen:
        seen.add(current)
        record = records.get(current, {})
        entries = record.get("required_inputs", [])
        if not isinstance(entries, list):
            raise ValueError("required_inputs must be a list")
        identifiers = set()
        for item in entries:
            if (not isinstance(item, dict) or set(item) - {"id", "question", "choices"} or not isinstance(item.get("id"), str)
                    or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", item["id"]) or not isinstance(item.get("question"), str)
                    or not item["question"].strip() or item["id"] in identifiers):
                raise ValueError("Required inputs need unique identifiers and explicit questions")
            choices = item.get("choices")
            if "choices" in item and (not isinstance(choices, list) or not choices
                                       or any(not isinstance(choice, str) or not choice.strip() for choice in choices)
                                       or len(set(choices)) != len(choices)):
                raise ValueError("Required input choices must be nonempty strings")
            identifiers.add(item["id"])
            result.append({**item, "declared_by": current})
        current = _parent(current, record)
    return result


def operator_requests(engine, run, ac_id):
    inherited = {(item["declared_by"], item["id"]) for item in declarations(run, ac_id)}
    result = []
    for item in engine.store.list_inbox():
        details = item["details"]
        if item["run_id"] != run["id"] or details.get("scope_digest") != run["scope_digest"]:
            continue
        declared = details.get("gate_kind") == "declared_input" and (
            details.get("declared_by"), details.get("input_id")) in inherited
        discovered = details.get("gate_kind") == "discovery" and details.get("ac_id") == ac_id
        if declared or discovered:
            result.append(item)
    return result


def missing_inputs(engine, run, ac_id):
    resolved = {(item["details"].get("declared_by"), item["details"].get("input_id"))
                for item in operator_requests(engine, run, ac_id)
                if item["status"] == "resolved" and isinstance(item.get("answer"), str) and item["answer"].strip()}
    return [item for item in declarations(run, ac_id)
            if (item["declared_by"], item["id"]) not in resolved]


def workspace_proof(engine, run):
    if isinstance(engine.git, GitOps):
        from .workspace_checkpoint import fingerprint

        return fingerprint(engine.git, run)
    # Controlled adapters must still expose a stable checkpoint; production Git
    # always uses the full tracked/untracked content fingerprint above.
    return {"head_sha": engine.git.head(engine.git.assert_workspace(run))}


def binding(engine, run, ac_id):
    requests = operator_requests(engine, run, ac_id)
    if any(item["status"] != "resolved" for item in requests) or missing_inputs(engine, run, ac_id):
        return None
    answers = [{"request_id": item["id"], "details": item["details"], "answer": item["answer"]}
               for item in requests]
    return {"ac_id": ac_id, "scope_digest": run["scope_digest"],
            "workspace": workspace_proof(engine, run), "operator_answers": _digest(answers)}


def valid_gate(engine, run):
    pending = run["payload"].get("pending", [])
    return bool(pending and run["payload"].get("input_gate")
                and run["payload"]["input_gate"] == binding(engine, run, pending[0]))


def input_gate(engine, run):
    pending = run["payload"].get("pending", [])
    if not pending:
        return engine._save(run, "validate", input_gate=None)
    proof = binding(engine, run, pending[0])
    if proof is None or proof != run["payload"].get("discovery_proof"):
        return engine._save(run, "discover", input_gate=None, discovery_proof=None)
    return engine._save(run, "implement", input_gate=proof)


def request_inputs(engine, run, ac_id, missing):
    engine.store.checkpoint(run["id"], "running", {"next": "discover", "input_gate": None, "discovery_proof": None})
    for item in missing:
        engine.store.block_run(run["id"], "Required operator input", {
            "gate_kind": "declared_input", "ac_id": ac_id, "scope_digest": run["scope_digest"],
            "input_id": item["id"], "declared_by": item["declared_by"],
            "questions": [item["question"]], "choices": item.get("choices"),
        })
    return {"run_id": run["id"], "next": "stop"}


def validate_answer(run, details, answer):
    if details.get("gate_kind") not in {"declared_input", "discovery"}:
        return
    if details.get("scope_digest") != run["scope_digest"]:
        raise ValueError("Operator input request no longer matches the approved scope")
    if details.get("gate_kind") == "declared_input":
        matches = [item for item in declarations(run, details.get("ac_id"))
                   if item["id"] == details.get("input_id") and item["declared_by"] == details.get("declared_by")]
        if len(matches) != 1 or details.get("choices") != matches[0].get("choices"):
            raise ValueError("Operator input request does not match its approved declaration")
        if matches[0].get("choices") and answer not in matches[0]["choices"]:
            raise ValueError("Answer must exactly match a declared input choice")


def execution_context_payload(engine, run, ac_id):
    """Read operator decisions from their durable inbox rows, never model mirrors."""
    payload = dict(run["payload"])
    requests = operator_requests(engine, run, ac_id)
    payload["answered_requests"] = {item["id"]: {
        "question": item["reason"], "details": item["details"], "answer": item["answer"]
    } for item in requests if item["status"] == "resolved"}
    payload["request_answers"] = {key: item["answer"] for key, item in payload["answered_requests"].items()}
    return payload


def request_implementation_input(engine, run, ac_id, questions, elapsed, lease):
    """Pause unexpected writable-phase questions without accepting partial work."""
    engine.store.finish_attempt(run["id"], ac_id, elapsed, success=False)
    engine.store.release_lease(lease["lease_id"], engine.owner)
    engine.store.checkpoint(run["id"], "running", {
        "in_flight": None, "next": "discover", "questions": questions,
    })
    engine.store.block_run(run["id"], "Implementation needs user input", {
        "gate_kind": "discovery", "ac_id": ac_id, "scope_digest": run["scope_digest"], "questions": questions,
    })
    return {"run_id": run["id"], "next": "stop"}
