"""Execute the real LangGraph worker with controlled external boundaries."""

import pytest
import subprocess

from scripts.background_worker.engine import WorkerEngine
from scripts.background_worker.executors import ExecutorError
from scripts.background_worker.store import Store


class ControlledGit:
    def __init__(self, workspace):
        self.workspace, self.sha, self.published = workspace, "base", 0

    def prepare(self, run):
        return {"workspace": str(self.workspace), "branch": "codex/test", "base_sha": "base"}

    def assert_workspace(self, run):
        return self.workspace

    def head(self, workspace):
        return self.sha

    def target_head(self):
        return "base"

    def commit(self, run, ac_id):
        self.sha += "x"
        return self.sha

    def package(self, run, evidence):
        return {"head_sha": self.sha, "ac_ids": run["plan"]["ac_ids"], "evidence": evidence}

    def publish(self, run, expected_sha):
        assert self.sha == expected_sha
        self.published += 1
        return "https://example.test/pr/1"


class ControlledLocal:
    def __init__(self, after=None, fail=False):
        self.calls, self.after, self.fail = 0, after, fail

    def discover(self, workspace, context, **kwargs):
        return {"status": "ready", "questions": [], "assessment": "Assigned requirements and saved decisions are sufficient to begin coding."}

    def implement(self, workspace, context, **kwargs):
        self.calls += 1
        if self.after:
            self.after()
        if self.fail:
            raise ExecutorError("controlled failure")
        return {"status": "completed", "questions": []}

    def check(self, workspace, argv, **kwargs):
        assert kwargs["timeout"] > 0
        return subprocess.CompletedProcess(
            argv, 0, '{"leafcutter_check":{"inspected":3,"passed":true}}', ""
        )


class ControlledReview:
    def __init__(self, changes=0):
        self.calls, self.changes = 0, changes

    def review(self, workspace, package, **kwargs):
        self.calls += 1
        return {
            "reviewed_sha": package["head_sha"],
            "disposition": "changes_required" if self.calls <= self.changes else "approved",
            "findings": [{"ac_ids": ["AC-1-a"], "description": "Fix boundary", "severity": "high"}]
            if self.calls <= self.changes
            else [],
        }


@pytest.fixture
def scenario(tmp_path):
    with Store(tmp_path / "state.sqlite") as store:
        settings = store.update_settings(enabled=True, checks=[["check"]])
        run = store.claim_feature(
            {
                "feature_id": "AC-1",
                "ac_ids": ["AC-1-a"],
                "execution_order": ["AC-1-a"],
                "scope_digest": "scope",
                "source_context": {"obligations": {}},
            }
        )
        git = ControlledGit(tmp_path)

        def engine(local=None, reviewer=None, scope=None):
            return WorkerEngine(
                tmp_path,
                store,
                settings,
                implementation=local or ControlledLocal(),
                reviewer=reviewer or ControlledReview(),
                git=git,
                scope_validator=scope or (lambda run: True),
            )

        yield store, run, git, engine


def test_real_graph_delivers_exact_head_and_persists_checkpoint(scenario):
    # covers: ACD-1300e-2, ACD-1300g-4, ACD-1300g-2
    store, run, git, engine = scenario
    result = engine().run(run["id"])
    assert result["state"] == "delivered"
    assert result["payload"]["reviewed_sha"] == result["payload"]["validated_sha"] == git.sha
    assert result["budgets"]["AC-1-a"]["attempts"] == 1
    assert (store.path.parent / "graph.sqlite").stat().st_size > 0
    engine().run(run["id"])
    assert git.published == 1


def test_post_commit_hook_failure_blocks_instead_of_accepting_existing_commit(scenario):
    # covers: ACD-1300e-3, ACD-1300g-2
    from scripts.background_worker.git_hooks import GitHookError

    store, run, git, engine = scenario

    def failed_commit(run, ac_id):
        git.sha = "created-but-hook-failed"
        error = GitHookError("post-commit outcome needs reconciliation")
        error.requires_reconciliation = True
        raise error

    git.commit = failed_commit
    local, reviewer = ControlledLocal(), ControlledReview()
    result = engine(local=local, reviewer=reviewer).run(run["id"])
    assert result["state"] == "blocked"
    assert result["budgets"]["AC-1-a"]["attempts"] == 1
    assert local.calls == 1 and reviewer.calls == 0 and git.published == 0


def test_off_drains_active_attempt_then_resume_retains_work(scenario):
    # covers: ACD-1300b-2, ACD-1300e-3
    store, run, git, engine = scenario
    local = ControlledLocal(after=lambda: store.update_settings(enabled=False))
    paused = engine(local=local).run(run["id"])
    assert paused["state"] == "paused" and local.calls == 1 and git.published == 0
    store.update_settings(enabled=True)
    local.after = None
    result = engine(local=local).run(run["id"])
    assert result["state"] == "delivered" and local.calls == 2


def test_three_failed_attempts_block_without_review_or_publish(scenario):
    # covers: ACD-1300g-1-i, ACD-1300g-3-ii
    store, run, git, engine = scenario
    local, review = ControlledLocal(fail=True), ControlledReview()
    result = engine(local=local, reviewer=review).run(run["id"])
    assert result["state"] == "blocked" and local.calls == 3
    assert review.calls == git.published == 0
    assert not store.list_leases(run["id"])


@pytest.mark.parametrize("changes,expected", [(1, "delivered"), (2, "blocked")])
def test_review_repairs_share_ac_budget_and_never_exceed_two_reviews(scenario, changes, expected):
    # covers: ACD-1300g-3, ACD-1300g-3-ii
    store, run, git, engine = scenario
    local, review = ControlledLocal(), ControlledReview(changes)
    result = engine(local=local, reviewer=review).run(run["id"])
    assert result["state"] == expected and review.calls == 2 and local.calls == 2
    assert result["budgets"]["AC-1-a"]["attempts"] == 2


def test_unknown_inflight_restart_retains_capacity_and_blocks(scenario):
    # covers: ACD-1300e-3, ACD-1300e-1
    store, run, git, engine = scenario
    lease = store.acquire_lease(run["id"], "implementation", "previous-owner")
    store.checkpoint(run["id"], "paused", {"in_flight": "implement", "next": "implement"})
    local = ControlledLocal()
    result = engine(local=local).run(run["id"])
    assert result["state"] == "blocked" and local.calls == 0
    assert store.list_leases(run["id"])[0]["lease_id"] == lease["lease_id"]


def test_scope_change_blocks_before_any_side_effect(scenario):
    # covers: ACD-1300e-3
    store, run, git, engine = scenario
    local = ControlledLocal()
    result = engine(local=local, scope=lambda run: False).run(run["id"])
    assert result["state"] == "blocked" and local.calls == git.published == 0


def test_changed_model_configuration_invalidates_claim(scenario):
    # covers: ACD-1300e-3, ACD-1300b-1
    store, run, git, engine = scenario
    local = ControlledLocal(
        after=lambda: store.update_settings(implementation={"model": "different"})
    )
    result = engine(local=local).run(run["id"])
    assert result["state"] == "blocked" and git.published == 0
    assert "configuration" in store.list_inbox()[0]["reason"]


def test_target_change_blocks_before_review(scenario):
    # covers: ACD-1300g-2, ACD-1300g-3
    store, run, git, engine = scenario
    git.target_head = lambda: "new-base"
    reviewer = ControlledReview()
    result = engine(reviewer=reviewer).run(run["id"])
    assert result["state"] == "blocked" and reviewer.calls == git.published == 0


def test_off_between_check_commands_stops_new_subprocess(scenario):
    # covers: ACD-1300b-2
    store, run, git, engine = scenario
    instance = engine()
    instance.settings["checks"] = [["first"], ["second"]]
    commands = []

    def check(workspace, argv, **kwargs):
        commands.append(argv)
        store.update_settings(enabled=False)
        return subprocess.CompletedProcess(
            argv, 0, '{"leafcutter_check":{"inspected":3,"passed":true}}', ""
        )

    instance.local.check = check
    from scripts.background_worker.engine import DrainRequested

    with pytest.raises(DrainRequested):
        instance._checks(git.workspace, timeout=30)
    assert commands == [["first"]]


def test_coordinator_refuses_unisolated_git_hooks(tmp_path, monkeypatch):
    # covers: ACD-1300g-1, ACD-1300g-4
    from scripts.background_worker.git_ops import GitOps

    hooks = tmp_path / "hooks"
    hooks.mkdir()
    (hooks / "pre-commit").write_text("execute generated code")
    (hooks / "pre-commit").chmod(0o700)
    from scripts.background_worker.git_hooks import GitHookSandbox

    monkeypatch.setattr(GitHookSandbox, "original_hooks", lambda self, cwd: hooks)
    monkeypatch.setattr("scripts.background_worker.git_hooks.shutil.which", lambda name: None)
    coordinator = GitOps(tmp_path, {})
    coordinator.git = lambda workspace, *args: str(hooks)
    with pytest.raises(ExecutorError, match="bubblewrap"):
        coordinator._assert_hooks_safe(tmp_path)


def test_interrupted_prepare_reconciles_without_refunding_attempts(scenario):
    # covers: ACD-1300e-3
    store, run, git, engine = scenario
    store.checkpoint(run["id"], "paused", {"in_flight": "prepare", "next": "prepare"})
    result = engine().run(run["id"])
    assert result["state"] == "delivered"
    assert result["budgets"]["AC-1-a"]["attempts"] == 1


def test_question_stops_checks_and_resumes_same_workspace_with_budget(scenario):
    # covers: ACD-1300c-1, ACD-1300g-1, ACD-1300e-3
    store, run, git, engine = scenario
    local = ControlledLocal()
    local.implement = lambda *args, **kwargs: {
        "status": "needs_input",
        "questions": ["Which timezone?"],
    }
    blocked = engine(local=local).run(run["id"])
    assert blocked["state"] == "blocked" and git.sha == "base"
    assert store.list_inbox()[0]["details"]["questions"] == ["Which timezone?"]
    workspace = blocked["workspace"]
    store.answer_request(run["id"], store.list_inbox()[0]["id"], "UTC")
    result = engine().run(run["id"])
    assert result["state"] == "delivered" and result["workspace"] == workspace
    assert result["budgets"]["AC-1-a"]["attempts"] == 2


def test_uncertain_validation_restart_does_not_relaunch_checks(scenario):
    # covers: ACD-1300e-3, ACD-1300g-2
    store, run, git, engine = scenario
    store.checkpoint(run["id"], "paused", {"in_flight": "validate", "next": "validate"})
    instance = engine()
    instance.local.check = lambda *args, **kwargs: pytest.fail("must not launch a second check")
    assert instance.run(run["id"])["state"] == "blocked"


def test_worker_builds_a_real_state_graph():
    # covers: ACD-1300g-1, ACD-1300e-2
    assert WorkerEngine.graph_builder().nodes.keys() >= {
        "prepare",
        "implement",
        "validate",
        "review",
        "publish",
    }


def test_publication_destination_is_durable_before_side_effect_and_cannot_change(scenario):
    # covers: ACD-1300g-4, ACD-1300g-4-i
    store, run, git, engine = scenario
    destination = {
        "remote": "origin",
        "base": "main",
        "repository": "https://github.com/team/project",
    }
    git.publication_destination = lambda workspace: dict(destination)

    def uncertain(run, expected_sha):
        assert store.get_run(run["id"])["payload"]["publication_destination"] == destination
        raise ExecutorError("uncertain publication")

    git.publish = uncertain
    store.checkpoint(
        run["id"],
        "running",
        {"workspace": str(git.workspace), "validated_sha": "base", "reviewed_sha": "base"},
    )
    instance = engine()
    with pytest.raises(ExecutorError, match="uncertain publication"):
        instance._publish(store.get_run(run["id"]))
    destination["repository"] = "https://github.com/other/project"
    with pytest.raises(ExecutorError, match="destination changed"):
        instance._publish(store.get_run(run["id"]))


def test_obligation_package_includes_positive_parent_and_negative_child():
    # covers: ACD-1300g-2, ACD-1300f-1
    plan = {
        "feature_id": "AC-1",
        "ac_ids": ["AC-1-1-i"],
        "source_context": {
            "records": {
                "AC-1-1": {"criteria": "Positive behavior"},
                "AC-1-1-i": {"criteria": "Negative scenario"},
            }
        },
    }
    context = WorkerEngine.implementation_context(plan, "AC-1-1-i", {})
    assert "Positive behavior" in context
    assert "Negative scenario" in context


def test_success_clears_resolved_failure_feedback(scenario):
    # covers: ACD-1300g-1 ACD-1300g-2
    import json

    store, run, git, engine = scenario

    class RetryLocal(ControlledLocal):
        def implement(self, workspace, context, **kwargs):
            self.calls += 1
            if self.calls == 1:
                error = ExecutorError("temporary check problem")
                error.evidence = {"stderr": "repair this"}
                raise error
            value = json.loads(context)
            assert value["last_failure"] == "temporary check problem"
            assert value["failed_check"] == {"stderr": "repair this"}
            return {"status": "completed", "questions": []}

    result = engine(local=RetryLocal()).run(run["id"])
    assert result["state"] == "delivered"
    assert result["budgets"]["AC-1-a"]["attempts"] == 2
    assert result["payload"]["last_failure"] is None
    assert result["payload"]["failed_check"] is None
