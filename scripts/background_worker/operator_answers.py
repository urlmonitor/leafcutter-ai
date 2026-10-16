"""Atomic operator answer binding and resumable input-gate checkpoints."""
import json
import time


def answer_request(store, run_id, item_id, answer):
    """Atomically bind an answer and the resumable checkpoint to its own run.

    A crash cannot leave an answered request blocking a run forever, and
    simultaneous answers cannot overwrite another request's saved context.
    """
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("An explicit non-empty answer is required")
    with store._transaction():
        row = store.connection.execute(
            "SELECT * FROM inbox WHERE id=? AND run_id=? AND status='pending'",
            (item_id, run_id),
        ).fetchone()
        if not row:
            return None
        run = store.get_run(run_id)
        if run["state"] in {"delivered", "completed"}:
            return None
        from .input_gate import validate_answer

        validate_answer(run, store._json(row["details"]), answer)
        store.connection.execute(
            "UPDATE inbox SET status='resolved',answer=?,resolved_at=? WHERE id=?",
            (answer, time.time(), item_id),
        )
        answers = {
            item["id"]: item["answer"]
            for item in store.connection.execute(
                "SELECT id,answer FROM inbox WHERE run_id=? AND status='resolved'", (run_id,)
            )
        }
        pending = store.connection.execute(
            "SELECT COUNT(*) FROM inbox WHERE run_id=? AND status='pending'", (run_id,)
        ).fetchone()[0]
        state = "blocked" if pending else "paused"
        answered_requests = {
            item["id"]: {
                "question": item["reason"],
                "details": store._json(item["details"]),
                "answer": item["answer"],
            }
            for item in store.connection.execute(
                "SELECT id,reason,details,answer FROM inbox WHERE run_id=? AND status='resolved'",
                (run_id,),
            )
        }
        payload = {
            **run["payload"],
            "request_answers": answers,
            "answered_requests": answered_requests,
        }
        if payload.get("next") in {"discover", "input_gate", "implement"}:
            payload.update(next="discover", input_gate=None, discovery_proof=None)
        store.connection.execute(
            "UPDATE runs SET state=?,payload=?,updated_at=? WHERE id=?",
            (state, json.dumps(payload), time.time(), run_id),
        )
    return {"run_id": run_id, "request_id": item_id, "state": state}
