"""Validate live fixture plumbing without making any inference calls."""

import json
import sys

import pytest

from scripts.background_worker.git_ops import GitOps
from scripts.background_worker.planning import plan_features
from scripts.background_worker.sources import load_records, target_completed
from scripts.background_worker.store import Store
from ._background_worker_live_fixture import fixture, first_ac_commit, git


@pytest.mark.parametrize("needs_input", [False, True])
def test_live_fixture_has_one_ready_ordered_feature(tmp_path, needs_input):
    # covers: ACD-1300a-3
    repo, _, _ = fixture(tmp_path, needs_input=needs_input)
    plan = plan_features(load_records(repo), target_completed=target_completed(repo, "origin/main"))
    assert not plan.excluded
    assert len(plan.ready) == 1
    assert plan.ready[0].execution_order == ["LIVE-100a-1", "LIVE-100a-2"]
    with Store(repo / ".leafcutter/background-worker/state.sqlite") as store:
        store.update_settings(enabled=True)
        assert store.claim_feature(plan.ready[0].to_dict())["feature_id"] == "LIVE-100a"


def test_first_ac_history_uses_original_commit_after_later_repair(tmp_path):
    # covers: ACD-1300g-1, ACD-1300g-3-i
    repo, _, _ = fixture(tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    tree = git(repo, "rev-parse", "HEAD^{tree}")
    ac1_message = "feat: implement LIVE-100a-1 in background worker"
    first = git(repo, "commit-tree", tree, "-p", base, "-m", ac1_message)
    second = git(repo, "commit-tree", tree, "-p", first, "-m",
                 "feat: implement LIVE-100a-2 in background worker")
    repair = git(repo, "commit-tree", tree, "-p", second, "-m", ac1_message)
    git(repo, "update-ref", "refs/heads/main", repair)
    latest_evidence = {"LIVE-100a-1": {"head_sha": repair}}
    selected = first_ac_commit(repo, base, "LIVE-100a-1")
    assert selected == first and selected != latest_evidence["LIVE-100a-1"]["head_sha"]


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Real hook boundary requires Linux")
def test_live_fixture_real_hook_and_worktree_prepare_without_inference(tmp_path):
    # covers: ACD-1300b-1, ACD-1300g-4
    repo, _, _ = fixture(tmp_path)
    plan = plan_features(load_records(repo), target_completed=target_completed(repo, "origin/main"))
    with Store(repo / ".leafcutter/background-worker/state.sqlite") as store:
        store.update_settings(enabled=True)
        run = store.claim_feature(plan.ready[0].to_dict())
        ops = GitOps(repo, {"target_ref": "origin/main"})
        prepared = ops.prepare(run)
        run["workspace"] = prepared["workspace"]
        run["payload"].update(prepared)
        workspace = ops.assert_workspace(run)
        (workspace / "README.md").write_text("# Fixture hook smoke\n", encoding="utf-8")
        sha = ops.commit(run, "LIVE-100a-1")
        assert sha != prepared["base_sha"]
        assert (workspace / ".leafcutter/live-hook.log").read_text() == "checked\n"
        assert not ops.git(workspace, "status", "--porcelain")
        assert ops.package(run, {})["head_sha"] == sha


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Real hook boundary requires Linux")
def test_live_harness_reaches_implementation_with_canonical_settings(tmp_path, monkeypatch):
    # covers: ACD-1300g-1, ACD-1300c-1
    from scripts.background_worker.executors import LocalCodexExecutor, SDKReviewer
    from .test_background_worker_live_acceptance import run_live

    config = tmp_path / "settings.json"
    config.write_text(json.dumps({
        "implementation": {"executor": "codex-cli", "provider": "ollama", "model": "fixture"},
        "reviewer": {"executor": "codex-sdk", "model": "fixture"},
    }), encoding="utf-8")
    monkeypatch.setenv("LEAFCUTTER_LIVE_CONFIG", str(config))
    monkeypatch.setattr(LocalCodexExecutor, "preflight", lambda self: None)
    monkeypatch.setattr(SDKReviewer, "preflight", lambda self: None)
    calls = []

    def implementation(self, workspace, context, **kwargs):
        calls.append(json.loads(context)["assigned_ac"])
        return {"status": "needs_input", "questions": ["NON-INFERENCE preparation reached implementation"]}

    monkeypatch.setattr(LocalCodexExecutor, "discover", lambda self, *args, **kwargs: {"status": "ready", "questions": [], "assessment": "Assigned requirements and saved decisions are sufficient to begin coding."})
    monkeypatch.setattr(LocalCodexExecutor, "implement", implementation)
    with pytest.raises(AssertionError):
        run_live(tmp_path)
    assert calls == ["LIVE-100a-1"]
    result = json.loads((tmp_path / "run-result.json").read_text())
    assert result["state"] == "blocked"
    assert result["payload"]["execution_settings"]["hook_runtime"] == {}


def test_clarification_fixture_has_two_valid_policies_without_answer_leak(tmp_path):
    # covers: ACD-1300c-2, ACD-1300e-1
    repo, _, original_tests = fixture(tmp_path, needs_input=True)
    policy = json.loads((repo / "label-policy.json").read_text())
    assert policy["internal_whitespace"] is None
    assert set(policy["allowed_choices"]) == {"collapse", "preserve"}
    record = load_records(repo)["LIVE-100a-1"]
    assert record["required_inputs"][0]["choices"] == ["collapse", "preserve"]
    assert "value" not in record["required_inputs"][0]
    criteria = record["criteria"]
    assert "no default" in criteria and "return needs_input" in criteria
    # Both valid implementations satisfy every original test. The choice can
    # only come from a later user answer, not leaked expected test output.
    for normalize in (lambda value: " ".join(value.split()), lambda value: value.strip()):
        namespace = {"normalize_label": normalize}
        exec(compile(original_tests.replace("from labels import normalize_label", ""), "shared-tests", "exec"), namespace)
        cases = [value for name, value in namespace.items() if name.startswith("test_")]
        assert len(cases) == 2
        for case in cases:
            case()
    assert "NotImplementedError" in (repo / "labels.py").read_text()


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Real hook boundary requires Linux")
def test_declared_input_blocks_real_worktree_without_model_calls(tmp_path):
    # covers: ACD-1300c-2, ACD-1300e-1, ACD-1300g-1
    from pathlib import Path
    from scripts.background_worker.engine import WorkerEngine
    from ._background_worker_live_fixture import LocalPublication

    class NoModel:
        def discover(self, *args, **kwargs):
            raise AssertionError("Discovery called before operator input")

        def implement(self, *args, **kwargs):
            raise AssertionError("Writable call before operator input")

        def review(self, *args, **kwargs):
            raise AssertionError("Review called before operator input")

    repo, remote, _ = fixture(tmp_path, needs_input=True)
    plans = plan_features(load_records(repo), target_completed=target_completed(repo, "origin/main"))
    with Store(repo / ".leafcutter/background-worker/state.sqlite") as store:
        settings = store.update_settings(enabled=True)
        run = store.claim_feature(plans.ready[0].to_dict())
        engine = WorkerEngine(repo, store, settings, implementation=NoModel(), reviewer=NoModel(),
                              git=LocalPublication(repo, settings, remote, tmp_path / "receipt.json"))
        blocked = engine.run(run["id"])
        assert blocked["state"] == "blocked"
        assert len(store.list_inbox(pending_only=True)) == 1
        assert store.list_inbox(pending_only=True)[0]["details"]["gate_kind"] == "declared_input"
        assert all(b["attempts"] == 0 and b["elapsed_seconds"] == 0 for b in blocked["budgets"].values())
        workspace = Path(blocked["workspace"])
        assert not git(workspace, "status", "--porcelain")
        for name in ("labels.py", "README.md", "label-policy.json", "tests/test_labels.py"):
            assert (workspace / name).read_bytes() == (repo / name).read_bytes()
        assert not store.list_leases()
