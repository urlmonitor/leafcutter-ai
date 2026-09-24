"""Durable LangGraph delivery loop with a separate side-effect intent ledger.

Checkpoints record control flow; they never claim to roll back processes or Git.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import sqlite3
import time
import uuid

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from .executors import ExecutorError, LocalCodexExecutor, SDKReviewer, check_evidence
from .git_ops import GitOps
from .locks import exclusive

LOGGER = logging.getLogger(__name__)
PHASES = ("prepare", "implement", "validate", "review", "publish")


class DrainRequested(RuntimeError):
    """The active process drained; admission for the next process is closed."""


class WorkerEngine:
    def __init__(
        self,
        repo_root,
        store,
        settings,
        *,
        implementation=None,
        reviewer=None,
        git=None,
        scope_validator=None,
    ):
        self.repo = Path(repo_root).resolve()
        self.store = store
        self.settings = settings
        self.local = implementation or LocalCodexExecutor(settings["implementation"])
        self.reviewer = reviewer or SDKReviewer(settings["reviewer"])
        self.git = git or GitOps(self.repo, settings)
        self.scope_validator = scope_validator or self._scope_valid
        self.owner = str(uuid.uuid4())
        self.production_local = implementation is None
        self.production_reviewer = reviewer is None
        self.production_git = git is None

    @staticmethod
    def graph_builder(callbacks=None):
        graph = StateGraph(dict)
        callbacks = callbacks or {}
        for phase in PHASES:
            graph.add_node(phase, callbacks.get(phase, lambda state: state))
        routes = {phase: phase for phase in PHASES} | {"stop": END}
        graph.add_conditional_edges(START, lambda state: state["next"], routes)
        for phase in PHASES:
            graph.add_conditional_edges(phase, lambda state: state["next"], routes)
        return graph

    @staticmethod
    def implementation_context(plan, ac_id, payload):
        return json.dumps(
            {
                "assigned_ac": ac_id,
                "feature_plan": plan,
                "review_findings": payload.get("findings", []),
                "request_answers": payload.get("request_answers", {}),
                "answered_requests": payload.get("answered_requests", {}),
                "questions": payload.get("questions", []),
                "previous_evidence": payload.get("evidence", {}),
            },
            ensure_ascii=False,
        )

    def _scope_valid(self, run):
        from .sources import load_records, load_reference_contents, target_completed
        from .planning import plan_features

        records = load_records(self.repo)
        plans = plan_features(
            records,
            target_completed=target_completed(
                self.repo, self.settings.get("target_ref", "origin/main")
            ),
            adr_contents=load_reference_contents(self.repo, records),
        )
        return any(
            plan.feature_id == run["feature_id"] and plan.scope_digest == run["scope_digest"]
            for plan in plans.ready
        )

    def _save(self, run, phase, **payload):
        self.store.checkpoint(run["id"], "running", {"next": phase, **payload})
        return {"run_id": run["id"], "next": phase}

    def _block(self, run, reason):
        self.store.block_run(run["id"], reason, {"next": run["payload"].get("next", "prepare")})
        return {"run_id": run["id"], "next": "stop"}

    def _node(self, phase, state):
        run = self.store.get_run(state["run_id"])
        if not self.store.get_settings().get("enabled"):
            self.store.checkpoint(run["id"], "paused", {"next": phase})
            return {"run_id": run["id"], "next": "stop"}
        if not self.scope_validator(run):
            return self._block(run, "Approved feature scope or target dependency proof changed")
        execution_settings = {
            key: self.store.get_settings().get(key)
            for key in ("implementation", "reviewer", "checks", "target_ref")
        }
        saved_settings = run["payload"].get("execution_settings")
        if saved_settings is not None and saved_settings != execution_settings:
            return self._block(
                run,
                "Execution models, provider configuration, checks or target changed after claim",
            )
        try:
            if (
                phase in {"review", "publish"}
                and self.git.target_head() != run["payload"]["base_sha"]
            ):
                raise ExecutorError(
                    "Target advanced since worktree creation; validation and review require reconciliation"
                )
            return getattr(self, "_" + phase)(run)
        except DrainRequested:
            return self._pause_capacity(run, phase)
        except (ExecutorError, OSError, ValueError) as exc:
            LOGGER.warning("Worker phase %s blocked: %s", phase, type(exc).__name__)
            return self._block(run, str(exc))

    def run(self, run_id):
        with exclusive(self.store.path.parent / "locks" / (run_id + ".lock")) as acquired:
            if not acquired:
                return self.store.get_run(run_id)
            run = self.store.get_run(run_id)
            if run["state"] in {"delivered", "completed", "blocked"}:
                return run
            if run["payload"].get("in_flight"):
                # Publishing is idempotently discoverable. Unknown model/commit outcomes require a human.
                if run["payload"]["in_flight"] not in {"publish", "prepare"}:
                    self._block(
                        run,
                        "Interrupted side effect requires explicit reconciliation before another agent call",
                    )
                    return self.store.get_run(run_id)
            self.store.checkpoint(run_id, "running", {})
            if self.store.get_settings().get("enabled"):
                try:
                    if self.production_git:
                        self.git._assert_hooks_safe(self.repo)
                    if self.production_local:
                        self.local.preflight()
                    if self.production_reviewer:
                        self.reviewer.preflight()
                except (ExecutorError, OSError, ValueError) as exc:
                    self._block(run, str(exc))
                    return self.store.get_run(run_id)
            with sqlite3.connect(
                str(self.store.path.parent / "graph.sqlite"), check_same_thread=False
            ) as connection:
                saver = SqliteSaver(connection)
                graph = self.graph_builder(
                    {phase: lambda state, p=phase: self._node(p, state) for phase in PHASES}
                ).compile(checkpointer=saver)
                graph.invoke(
                    {"run_id": run_id, "next": run["payload"].get("next", "prepare")},
                    {"configurable": {"thread_id": run_id}, "recursion_limit": 10000},
                )
            return self.store.get_run(run_id)

    def _prepare(self, run):
        self.store.checkpoint(run["id"], "running", {"in_flight": "prepare", "next": "prepare"})
        workspace = self.git.prepare(run)
        execution_settings = {
            key: self.settings.get(key)
            for key in ("implementation", "reviewer", "checks", "target_ref")
        }
        return self._save(
            run,
            "implement",
            **workspace,
            in_flight=None,
            evidence={},
            pending=list(run["plan"]["execution_order"]),
            execution_settings=execution_settings,
        )

    def _lease(self, run, role):
        return self.store.acquire_lease(run["id"], role, self.owner)

    def _pause_capacity(self, run, phase):
        self.store.checkpoint(run["id"], "paused", {"next": phase})
        return {"run_id": run["id"], "next": "stop"}

    def _checks(self, workspace, *, timeout, heartbeat=None):
        if not self.settings.get("checks"):
            raise ExecutorError("Required project checks are not configured")
        started = time.monotonic()
        results = []
        for argv in self.settings["checks"]:
            if not self.store.get_settings().get("enabled"):
                raise DrainRequested()
            result = self.local.check(
                workspace, argv, timeout=timeout - (time.monotonic() - started), heartbeat=heartbeat
            )
            results.append(check_evidence(argv, result))
        return results

    def _implement(self, run):
        pending = run["payload"].get("pending", [])
        if not pending:
            return self._save(run, "validate")
        lease = self._lease(run, "implementation")
        if not lease:
            return self._pause_capacity(run, "implement")
        ac_id = pending[0]
        budget = self.store.begin_attempt(run["id"], ac_id)
        if not budget:
            self.store.release_lease(lease["lease_id"], self.owner)
            return self._block(
                run, f"AC {ac_id} exhausted its attempt/time budget or has an uncertain attempt"
            )
        self.store.checkpoint(run["id"], "running", {"in_flight": "implement", "next": "implement"})
        started = time.monotonic()

        def heartbeat():
            return self.store.renew_lease(lease["lease_id"], self.owner)

        try:
            workspace = self.git.assert_workspace(run)
            outcome = self.local.implement(
                workspace,
                self.implementation_context(run["plan"], ac_id, run["payload"]),
                timeout=budget["remaining_seconds"],
                heartbeat=heartbeat,
            )
            if outcome and outcome.get("status") == "needs_input":
                self.store.finish_attempt(
                    run["id"], ac_id, time.monotonic() - started, success=False
                )
                self.store.release_lease(lease["lease_id"], self.owner)
                self.store.checkpoint(
                    run["id"], "running", {"in_flight": None, "questions": outcome["questions"]}
                )
                self.store.block_run(
                    run["id"],
                    "Implementation needs user input",
                    {"ac_id": ac_id, "questions": outcome["questions"]},
                )
                return {"run_id": run["id"], "next": "stop"}
            checks = self._checks(
                workspace,
                timeout=budget["remaining_seconds"] - (time.monotonic() - started),
                heartbeat=heartbeat,
            )
            if not self.store.get_settings().get("enabled"):
                raise DrainRequested()
            sha = self.git.commit(run, ac_id)
            if time.monotonic() - started >= budget["remaining_seconds"]:
                raise ExecutorError(
                    "AC cumulative execution budget expired before evidence could be accepted"
                )
        except ExecutorError as exc:
            if "Uncertain process termination" in str(exc):
                raise
            self.store.finish_attempt(run["id"], ac_id, time.monotonic() - started, success=False)
            self.store.release_lease(lease["lease_id"], self.owner)
            return self._save(
                run,
                "implement",
                in_flight=None,
                last_failure=str(exc),
                failed_check=getattr(exc, "evidence", None),
            )
        except DrainRequested:
            self.store.finish_attempt(run["id"], ac_id, time.monotonic() - started, success=False)
            self.store.release_lease(lease["lease_id"], self.owner)
            self.store.checkpoint(run["id"], "running", {"in_flight": None})
            raise
        self.store.finish_attempt(run["id"], ac_id, time.monotonic() - started, success=True)
        self.store.release_lease(lease["lease_id"], self.owner)
        evidence = dict(run["payload"].get("evidence", {}))
        evidence[ac_id] = {"head_sha": sha, "checks": checks, "attempt": budget["attempts"]}
        return self._save(run, "implement", in_flight=None, pending=pending[1:], evidence=evidence)

    def _validate(self, run):
        workspace = self.git.assert_workspace(run)
        sha = self.git.head(workspace)
        self.store.checkpoint(run["id"], "running", {"in_flight": "validate", "next": "validate"})
        try:
            checks = self._checks(workspace, timeout=1800)
        except (ExecutorError, DrainRequested) as exc:
            if "Uncertain process termination" not in str(exc):
                self.store.checkpoint(
                    run["id"],
                    "running",
                    {"in_flight": None, "failed_check": getattr(exc, "evidence", None)},
                )
            raise
        if self.git.head(workspace) != sha:
            raise ExecutorError("Head changed during feature validation")
        package = self.git.package(run, run["payload"].get("evidence", {}))
        if package["head_sha"] != sha:
            raise ExecutorError("Head changed before review packaging")
        package["feature_checks"] = checks
        return self._save(run, "review", package=package, validated_sha=sha, in_flight=None)

    def _review(self, run):
        if self.git.head(run["workspace"]) != run["payload"]["package"]["head_sha"]:
            raise ExecutorError("Head changed after validation and before review")
        lease = self._lease(run, "reviewer")
        if not lease:
            return self._pause_capacity(run, "review")
        count = self.store.record_review(run["id"])
        if not count:
            self.store.release_lease(lease["lease_id"], self.owner)
            return self._block(run, "Feature review budget exhausted")
        self.store.checkpoint(run["id"], "running", {"in_flight": "review", "next": "review"})
        try:
            result = self.reviewer.review(
                run["workspace"],
                run["payload"]["package"],
                heartbeat=lambda: self.store.renew_lease(lease["lease_id"], self.owner),
            )
        except ExecutorError as exc:
            if "Uncertain process termination" not in str(exc):
                self.store.release_lease(lease["lease_id"], self.owner)
                self.store.checkpoint(run["id"], "running", {"in_flight": None})
            raise
        self.store.release_lease(lease["lease_id"], self.owner)
        if self.git.head(run["workspace"]) != result["reviewed_sha"]:
            raise ExecutorError("Head changed during read-only review")
        if result["disposition"] == "approved":
            return self._save(
                run, "publish", in_flight=None, reviewed_sha=result["reviewed_sha"], review=result
            )
        if count >= 2:
            self.store.checkpoint(
                run["id"], "running", {"in_flight": None, "findings": result["findings"]}
            )
            return self._block(run, "Second feature review has unresolved findings")
        requested = {ac for finding in result["findings"] for ac in finding["ac_ids"]}
        from .planning import _parent

        obligations = run["plan"]["source_context"].get("obligations", {})
        affected = set()
        for leaf in run["plan"]["ac_ids"]:
            current, seen = leaf, set()
            while current and current not in seen:
                seen.add(current)
                if current in requested:
                    affected.add(leaf)
                current = _parent(current, obligations.get(current, {}))
        if not affected:
            raise ExecutorError("Review findings cannot be mapped to executable AC obligations")
        pending = [ac for ac in run["plan"]["execution_order"] if ac in affected]
        return self._save(
            run, "implement", in_flight=None, pending=pending, findings=result["findings"]
        )

    def _publish(self, run):
        if run["payload"].get("validated_sha") != run["payload"].get("reviewed_sha"):
            raise ExecutorError("Publication does not have matching validation and review evidence")
        self.store.checkpoint(run["id"], "running", {"in_flight": "publish", "next": "publish"})
        url = self.git.publish(run, run["payload"]["reviewed_sha"])
        self.store.checkpoint(
            run["id"], "delivered", {"in_flight": None, "pr_url": url, "next": "stop"}
        )
        return {"run_id": run["id"], "next": "stop"}
