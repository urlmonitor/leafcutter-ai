"""Run required project checks within the current action's remaining time."""
import time

from .executors import ExecutorError, check_evidence


def run_checks(engine, workspace, *, timeout, heartbeat=None):
    from .engine import DrainRequested

    if not engine.settings.get("checks"):
        raise ExecutorError("Required project checks are not configured")
    started = time.monotonic()
    results = []
    for argv in engine.settings["checks"]:
        if not engine.store.get_settings().get("enabled"):
            raise DrainRequested()
        result = engine.local.check(
            workspace, argv, timeout=timeout - (time.monotonic() - started), heartbeat=heartbeat
        )
        results.append(check_evidence(argv, result))
    return results
