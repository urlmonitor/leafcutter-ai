"""Durable LangGraph delivery loop with a separate side-effect intent ledger.

Checkpoints record control flow; they never claim to roll back processes or Git.
"""

from __future__ import annotations

import logging
from pathlib import Path
import sqlite3
import time
import uuid

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from .executors import ExecutorError, LocalCodexExecutor, SDKReviewer
from .git_ops import GitOps
from .locks import exclusive
from .recovery import linux_runtime_id

LOGGER = logging.getLogger(__name__)
PHASES = ("prepare", "discover", "input_gate", "implement", "validate", "review", "publish")


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
    def implementation_context(plan, ac_id, payload, checks=None):
        from .implementation_context import build_context

        return build_context(plan, ac_id, payload, checks)

    def _scope_valid(self, run):
        from .scope_validation import scope_valid

        return scope_valid(self, run)

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
            for key in ("implementation", "reviewer", "checks", "target_ref", "hook_runtime")
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
            from .workspace_checkpoint import execute_phase

            return execute_phase(self, phase, run)
        except DrainRequested:
            return self._pause_capacity(run, phase)
        except (ExecutorError, OSError, ValueError) as exc:
            from .status_views import record_phase_failure

            record_phase_failure(self.store, run, phase, exc)
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
                        self.git.publication_destination(self.repo)
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
        self.store.checkpoint(
            run["id"], "running",
            {"in_flight": "prepare", "next": "prepare", "process_runtime_id": linux_runtime_id()},
        )
        workspace = self.git.prepare(run)
        execution_settings = {
            key: self.settings.get(key)
            for key in ("implementation", "reviewer", "checks", "target_ref", "hook_runtime")
        }
        return self._save(
            run,
            "discover",
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
        from .project_checks import run_checks

        return run_checks(self, workspace, timeout=timeout, heartbeat=heartbeat)

    def _discover(self, run):
        from .discovery import discover

        return discover(self, run)

    def _input_gate(self, run):
        from .input_gate import input_gate

        return input_gate(self, run)

    def _implement(self, run):
        pending = run["payload"].get("pending", [])
        if not pending:
            return self._save(run, "validate")
        from .input_gate import execution_context_payload, valid_gate

        if not valid_gate(self, run):
            return self._save(run, "discover", input_gate=None, discovery_proof=None)
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
        self.store.checkpoint(
            run["id"], "running",
            {"in_flight": "implement", "next": "discover", "input_gate": None, "discovery_proof": None, "process_runtime_id": linux_runtime_id()},
        )
        started = time.monotonic()

        def heartbeat():
            return self.store.renew_lease(lease["lease_id"], self.owner)

        try:
            workspace = self.git.assert_workspace(run)
            outcome = self.local.implement(
                workspace,
                self.implementation_context(run["plan"], ac_id, execution_context_payload(self, run, ac_id), self.settings["checks"]),
                timeout=budget["remaining_seconds"],
                heartbeat=heartbeat,
            )
            from .reply_contract import validate_reply

            outcome = validate_reply(outcome, adapter=True)
            if outcome["status"] == "needs_input":
                from .input_gate import request_implementation_input

                return request_implementation_input(self, run, ac_id, outcome["questions"], time.monotonic() - started, lease)
            checks = self._checks(
                workspace,
                timeout=budget["remaining_seconds"] - (time.monotonic() - started),
                heartbeat=heartbeat,
            )
            if isinstance(self.git, GitOps):
                from .completion import complete_ac

                changed = self.git.git(workspace, "diff", "--name-only", "-z", "HEAD", "--", ".").split("\0")
                changed += self.git.git(workspace, "ls-files", "-z", "--others", "--exclude-standard").split("\0")
                changed = [name for name in changed if name]
                if complete_ac(workspace, run["plan"], ac_id, changed, completed_ac_ids=run["payload"].get("evidence", {})):
                    checks = self._checks(workspace, timeout=budget["remaining_seconds"] - (time.monotonic() - started), heartbeat=heartbeat)
            if not self.store.get_settings().get("enabled"):
                raise DrainRequested()
            commit_options = {"timeout": budget["remaining_seconds"] - (time.monotonic() - started)} if isinstance(self.git, GitOps) else {}
            sha = self.git.commit(run, ac_id, **commit_options)
            if time.monotonic() - started >= budget["remaining_seconds"]:
                raise ExecutorError(
                    "AC cumulative execution budget expired before evidence could be accepted"
                )
        except ExecutorError as exc:
            if "Uncertain process termination" in str(exc):
                raise
            self.store.finish_attempt(run["id"], ac_id, time.monotonic() - started, success=False)
            self.store.release_lease(lease["lease_id"], self.owner)
            if getattr(exc, "stop_run", False):
                from .reply_failure import stop_reply

                return stop_reply(self, run, exc, "implement")
            if getattr(exc, "requires_reconciliation", False):
                return self._block(run, str(exc))
            return self._save(
                run,
                "discover",
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
        return self._save(run, "discover", in_flight=None, pending=pending[1:], evidence=evidence, questions=[], last_failure=None, failed_check=None, failed_reply=None)

    def _validate(self, run):
        workspace = self.git.assert_workspace(run)
        sha = self.git.head(workspace)
        self.store.checkpoint(
            run["id"], "running",
            {"in_flight": "validate", "next": "validate", "process_runtime_id": linux_runtime_id()},
        )
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
        self.store.checkpoint(
            run["id"], "running",
            {"in_flight": "review", "next": "review", "process_runtime_id": linux_runtime_id()},
        )
        try:
            result = self.reviewer.review(
                run["workspace"],
                run["payload"]["package"],
                heartbeat=lambda: self.store.renew_lease(lease["lease_id"], self.owner),
            )
        except ExecutorError as exc:
            from .status_views import _redact

            self.store.checkpoint(run["id"], "running", {"failed_review": _redact(getattr(exc, "evidence", None))})
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
            run, "discover", in_flight=None, input_gate=None, discovery_proof=None, pending=pending, findings=result["findings"]
        )

    def _publish(self, run):
        if run["payload"].get("validated_sha") != run["payload"].get("reviewed_sha"):
            raise ExecutorError("Publication does not have matching validation and review evidence")
        binding = {}
        resolver = getattr(self.git, "publication_destination", None)
        if resolver is not None:
            destination = resolver(run["workspace"])
            previous = run["payload"].get("publication_destination")
            if previous is not None and previous != destination:
                raise ExecutorError("Publication destination changed; explicit reconciliation required")
            binding["publication_destination"] = destination
        self.store.checkpoint(
            run["id"], "running",
            {"in_flight": "publish", "next": "publish", "process_runtime_id": linux_runtime_id(), **binding},
        )
        run = self.store.get_run(run["id"])
        url = self.git.publish(run, run["payload"]["reviewed_sha"])
        self.store.checkpoint(
            run["id"], "delivered", {"in_flight": None, "pr_url": url, "next": "stop"}
        )
        return {"run_id": run["id"], "next": "stop"}
