"""
MODULE: discovery
GOAL: Assess readiness before granting a scoped implementation gate.
BUSINESS CONTEXT: Missing decisions must pause autonomous implementation.
ARCHITECTURE: LangGraph discovery delegates inference and records coordinator-owned proofs.
"""
import time

from .executors import ExecutorError
from .implementation_context import build_discovery_context
from .input_gate import binding, execution_context_payload, missing_inputs, operator_requests, request_inputs, workspace_proof
from .recovery import linux_runtime_id



def _admission_blocker(engine, run_id, ac_id):
    """Describe the persisted admission condition without changing budget accounting."""
    current = engine.store.get_run(run_id)
    if not engine.store.get_settings()["enabled"]:
        return "AC discovery cannot start because the worker is disabled"
    if current["state"] in {"blocked", "delivered", "completed"}:
        return "AC discovery cannot start from run state " + current["state"]
    budget = current["budgets"][ac_id]
    if budget["in_progress"]:
        return "AC has an uncertain attempt requiring reconciliation"
    if budget["attempts"] >= 3:
        return "AC implementation attempt limit reached"
    if budget["remaining_seconds"] <= 0:
        return "AC cumulative execution time budget exhausted"
    return "AC discovery admission changed; operator review is required"


def discover(engine, run):
    """Assess one AC and retain its result only with an unchanged input binding."""
    pending = run["payload"].get("pending", [])
    if not pending:
        return engine._save(run, "validate", input_gate=None, discovery_proof=None)
    ac_id = pending[0]
    missing = missing_inputs(engine, run, ac_id)
    if missing:
        return request_inputs(engine, run, ac_id, missing)
    if any(item["status"] != "resolved" for item in operator_requests(engine, run, ac_id)):
        engine.store.checkpoint(run["id"], "blocked", {"next": "discover", "input_gate": None})
        return {"run_id": run["id"], "next": "stop"}
    lease = engine._lease(run, "implementation")
    if not lease:
        return engine._pause_capacity(run, "discover")
    budget = engine.store.begin_attempt(run["id"], ac_id, implementation=False)
    if not budget:
        engine.store.release_lease(lease["lease_id"], engine.owner)
        return engine._block(run, _admission_blocker(engine, run["id"], ac_id))
    engine.store.checkpoint(run["id"], "running", {"next": "discover", "in_flight": "discover",
                           "input_gate": None, "discovery_proof": None, "process_runtime_id": linux_runtime_id()})
    started = time.monotonic()
    try:
        before = workspace_proof(engine, run)
        initial_proof = binding(engine, run, ac_id)
        context_payload = execution_context_payload(engine, run, ac_id)
        if initial_proof is None:
            raise ExecutorError("Operator input state changed before discovery; repeat the input gate")
        outcome = engine.local.discover(
            engine.git.assert_workspace(run),
            build_discovery_context(run["plan"], ac_id, context_payload, engine.settings["checks"]),
            timeout=budget["remaining_seconds"] - (time.monotonic() - started),
            heartbeat=lambda: engine.store.renew_lease(lease["lease_id"], engine.owner),
        )
        if workspace_proof(engine, run) != before:
            raise ExecutorError("Uncertain process termination or discovery workspace mutation; retain the execution lease")
        if initial_proof != binding(engine, run, ac_id):
            raise ExecutorError("Operator input proof changed during discovery; repeat the input gate")
        from .reply_contract import validate_reply

        outcome = validate_reply(outcome, discovery=True, adapter=True)
    except ExecutorError as error:
        if "Uncertain process termination" in str(error):
            raise
        engine.store.finish_attempt(run["id"], ac_id, time.monotonic() - started)
        engine.store.release_lease(lease["lease_id"], engine.owner)
        engine.store.checkpoint(run["id"], "running", {"in_flight": None})
        if getattr(error, "stop_run", False):
            from .reply_failure import stop_reply

            return stop_reply(engine, run, error, "discover")
        raise
    engine.store.finish_attempt(run["id"], ac_id, time.monotonic() - started)
    engine.store.release_lease(lease["lease_id"], engine.owner)
    engine.store.checkpoint(run["id"], "running", {"in_flight": None})
    if time.monotonic() - started >= budget["remaining_seconds"]:
        raise ExecutorError("AC cumulative discovery time budget exhausted")
    if outcome["status"] == "needs_input":
        engine.store.block_run(run["id"], "Discovery needs user input", {
            "gate_kind": "discovery", "ac_id": ac_id, "scope_digest": run["scope_digest"],
            "questions": outcome["questions"],
        })
        return {"run_id": run["id"], "next": "stop"}
    if not engine.store.get_settings()["enabled"]:
        return engine._pause_capacity(run, "discover")
    return engine._save(run, "input_gate", discovery_proof=initial_proof,
                        discovery_assessment={"assessment": outcome["assessment"], "binding": initial_proof})

# DECISION HISTORY
# ========================================
# - 2026-09-26 00:00 [python-coder]: Separate readiness assessment from coding evidence and preserve scoped advisory context. (#TICKETLESS reason=approved-ac-driven-discovery-contract)
# - 2026-09-30 00:00 [python-coder]: Report actual persisted admission blocker instead of mislabeling attempt exhaustion as discovery timeout. (#TICKETLESS reason=approved-ac-budget-diagnostics)
