"""Deterministic queue driver; models run only in the LangGraph engine."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import time
import subprocess
import logging

LOGGER = logging.getLogger(__name__)
from .locks import exclusive
from .planning import plan_features
from .sources import load_records, load_reference_contents, target_completed, refresh_target
from .store import Store
from .settings import validate


def _advance(repo, db, run_id):
    with exclusive(db.parent / (run_id + ".lock")) as owned:
        if not owned:
            return {"state": "owned_elsewhere"}
        from .engine import WorkerEngine

        with Store(db) as store:
            return WorkerEngine(repo, store, store.get_settings()).run(run_id)


def run_service(repo, db, *, once=False):
    with Store(db) as store, exclusive(db.parent / "service.lock") as owned:
        if not owned:
            return {"state": "already_running"}
        with ThreadPoolExecutor(max_workers=64) as pool:
            active = {}
            while True:
                settings = store.get_settings()
                for run_id, future in list(active.items()):
                    if not future.done():
                        continue
                    try:
                        future.result()
                    except Exception as exc:
                        LOGGER.warning("Worker execution failed: %s", type(exc).__name__)
                        store.block_run(run_id, "Worker execution failed", {"error": str(exc)})
                    del active[run_id]
                if not settings.get("enabled"):
                    for rid, future in active.items():
                        try:
                            future.result()
                        except Exception as exc:
                            LOGGER.warning("Worker execution failed: %s", type(exc).__name__)
                            store.block_run(rid, "Worker execution failed", {"error": str(exc)})
                    from .notifications import notify_outcomes

                    notify_outcomes(db, store)
                    return {"state": "disabled", "draining": []}
                try:
                    validate(settings, executable=True)
                    records = load_records(repo)
                    references = load_reference_contents(repo, records)
                    if records:
                        refresh_target(repo, settings.get("target_ref", "origin/main"))
                    completed = (
                        target_completed(repo, settings.get("target_ref", "origin/main"))
                        if records
                        else set()
                    )
                    selection = plan_features(
                        records,
                        target_completed=completed,
                        reserved_features=store.reserved_features(),
                        adr_contents=references,
                    )
                except (ValueError, OSError, subprocess.SubprocessError) as exc:
                    store.set_queue_status({"error": str(exc), "ready": [], "excluded": {}})
                    store.update_settings(enabled=False)
                    raise
                store.set_queue_status(
                    {
                        "observed_at": time.time(),
                        "excluded": selection.excluded,
                        "ready": [
                            {"feature_id": p.feature_id, "effective_priority": p.effective_priority}
                            for p in selection.ready
                        ],
                    }
                )
                limit = settings["max_agent_calls"]
                # Recover preserved runnable runs before selecting additional features.
                for run in store.list_runs():
                    rid = run.get("run_id", run["id"])
                    if len(active) >= limit:
                        break
                    if rid not in active and run["state"] in {
                        "claimed",
                        "ready",
                        "running",
                        "paused",
                        "waiting",
                    }:
                        active[rid] = pool.submit(_advance, repo, db, rid)
                for plan in selection.ready:
                    if len(active) >= limit:
                        break
                    claimed = store.claim_feature(asdict(plan))
                    if claimed:
                        rid = claimed.get("run_id", claimed["id"])
                        active[rid] = pool.submit(_advance, repo, db, rid)
                from .notifications import notify_outcomes

                notify_outcomes(db, store)
                if once:
                    outcomes = []
                    for rid, future in active.items():
                        try:
                            outcomes.append(future.result())
                        except Exception as exc:
                            LOGGER.warning("Worker execution failed: %s", type(exc).__name__)
                            store.block_run(rid, "Worker execution failed", {"error": str(exc)})
                            outcomes.append({"run_id": rid, "state": "blocked"})
                    notify_outcomes(db, store)
                    return {
                        "state": "processed" if active else "waiting",
                        "outcomes": outcomes,
                        "excluded": selection.excluded,
                    }
                time.sleep(settings.get("poll_seconds", 5))
