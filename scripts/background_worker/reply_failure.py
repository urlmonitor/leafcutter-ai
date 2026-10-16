"""Persist terminal adapter reply failures without retrying writable work."""
from .execution_boundary import safe_output
from .status_views import _redact


def stop_reply(engine, run, error, phase):
    failure = {"phase": phase, "status": getattr(error, "reply_kind", "error"),
               "message": safe_output(str(error)), "evidence": _redact(getattr(error, "evidence", None))}
    engine.store.checkpoint(run["id"], "running", {
        "in_flight": None, "next": "discover", "input_gate": None, "discovery_proof": None,
        "last_failure": failure["message"], "failed_reply": failure,
    })
    return engine._block(engine.store.get_run(run["id"]), failure["message"])
