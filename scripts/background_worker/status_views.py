"""Actionable CLI views derived from durable runs, leases and inbox requests."""
from .execution_boundary import safe_output


def capacity_status(store):
    settings = store.get_settings()
    leases = store.list_leases()
    count = len(leases)
    excess = max(count - settings["max_agent_calls"], 0)
    draining_count = count if not settings["enabled"] else excess
    draining = draining_count > 0
    return {"configured_limit": settings["max_agent_calls"], "active_call_count": count,
            "draining": draining, "draining_call_count": draining_count, "excess_call_count": excess,
            "active_leases": leases}


def _redact(value):
    if isinstance(value, str):
        return safe_output(value)
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def required_action(item, run):
    reason = item["reason"].lower()
    payload = run["payload"]
    pending = payload.get("pending", [])
    exhausted = any(run["budgets"].get(ac, {}).get("attempts", 0) >= 3
                    or run["budgets"].get(ac, {}).get("elapsed_seconds", 0) >= 3600
                    for ac in pending)
    if ("exhaust" in reason or "second feature review" in reason
            or (payload.get("next") in {"discover", "input_gate", "implement"} and exhausted)
            or (payload.get("next") == "review" and run["review_count"] >= 2)):
        return "Take over the preserved branch manually: automatic attempt/time or review budget is exhausted. An answer does not reset budgets."
    if "target advanced" in reason:
        return "Take over delivery manually against the new target, including checks and review. This run has no supported base-replacement command."
    if "preserved worktree" in reason or "head changed" in reason:
        return "Restore the exact saved worktree checkpoint before answering, or take over manually with fresh checks and review. An answer alone does not accept changed evidence."
    if payload.get("in_flight") in {"discover", "implement", "validate", "review"}:
        return "Disable the worker, prove the prior Linux runtime stopped, inspect preserved work, then run reconcile with an explicit note. Answer any remaining independent requests afterward."
    if payload.get("in_flight") == "publish":
        return "Inspect the remote branch and draft PR outcome, correct the publication failure, then answer this request. Continuation discovers existing remote proposals before retrying."
    if "scope" in reason or "execution models" in reason:
        return "Restore the approved scope and saved execution settings before answering, or take over manually. An answer does not approve changed requirements."
    return "Inspect the supporting evidence, correct the reported failure or supply the requested information, then answer this request to resume within remaining budgets."


def attention_items(store):
    result = []
    for item in store.list_inbox():
        run = store.get_run(item["run_id"])
        payload = run["payload"]
        details = item.get("details", {})
        pending = payload.get("pending", [])
        affected = [details["ac_id"]] if details.get("ac_id") else (
            pending[:1] if payload.get("next") in {"discover", "input_gate", "implement"} else run["plan"].get("ac_ids", []))
        result.append({**item, "feature_id": run["feature_id"], "affected_ac_ids": affected,
                       "required_action": required_action(item, run),
                       "supporting_evidence": {"checks": payload.get("evidence", {}),
                                               "failed_reply": payload.get("failed_reply"),
                          "failed_phase": payload.get("failed_phase"), "failed_check": payload.get("failed_check"), "failed_review": payload.get("failed_review"), "review_findings": payload.get("findings", []),
                          "budgets": run["budgets"], "next": payload.get("next"),
                          "last_failure": safe_output(payload.get("last_failure"))}})
    return _redact(result)


def record_phase_failure(store, run, phase, error):
    current = store.get_run(run["id"])
    store.checkpoint(run["id"], current["state"], {"failed_phase": _redact({
        "phase": phase, "error": str(error), "evidence": getattr(error, "evidence", None)
    })})
