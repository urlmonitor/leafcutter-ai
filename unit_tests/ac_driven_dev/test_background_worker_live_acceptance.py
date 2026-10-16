"""Opt-in REAL model acceptance; skipped unless LEAFCUTTER_RUN_LIVE=1.

LEAFCUTTER_LIVE_CONFIG points to caller-owned JSON containing implementation
and reviewer settings. Actual SDK review may incur cost. No GitHub PR is created:
only publication is adapted to a disposable local bare remote. The optional
hybrid-repair case deliberately synthesizes review one, then uses real local
repair and real SDK review two; it is not evidence of organic reviewer detection.
"""

import json
import os
from pathlib import Path
import sys

import pytest

from scripts.background_worker.engine import WorkerEngine
from scripts.background_worker.executors import LocalCodexExecutor, SDKReviewer
from scripts.background_worker.planning import plan_features
from scripts.background_worker.settings import validate
from scripts.background_worker.sources import load_records, target_completed
from scripts.background_worker.store import Store
from ._background_worker_live_fixture import LocalPublication, command, fixture, git, traced_invocation, first_ac_commit


pytestmark = pytest.mark.skipif(os.environ.get("LEAFCUTTER_RUN_LIVE") != "1",
                                reason="Explicit live model/reviewer opt-in required")


class HybridRepair:
    """Synthetic first finding, then the unmodified real SDK reviewer."""

    def __init__(self, reviewer):
        self.real = reviewer
        self.calls = 0

    def review(self, workspace, package, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return {"reviewed_sha": package["head_sha"], "disposition": "changes_required",
                    "findings": [{"ac_ids": ["LIVE-100a-1"], "severity": "medium",
                                  "description": "HYBRID ACCEPTANCE INJECTION: add tests/test_unicode_regression.py covering non-breaking Unicode whitespace normalization; preserve existing tests."}]}
        return self.real.review(workspace, package, **kwargs)


def run_live(tmp_path, *, hybrid=False, needs_input=False):
    config_path = os.environ.get("LEAFCUTTER_LIVE_CONFIG")
    assert config_path, "Set LEAFCUTTER_LIVE_CONFIG to explicit implementation/reviewer settings JSON"
    requested = json.loads(Path(config_path).read_text(encoding="utf-8"))
    settings = {"enabled": True, "max_agent_calls": 1, "target_ref": "origin/main",
                "poll_seconds": 5, "checks": [[sys.executable, "-m", "pytest", "-q"]],
                "implementation": requested["implementation"], "reviewer": requested["reviewer"]}
    validate(settings, executable=True)
    repo, remote, original_tests = fixture(tmp_path, needs_input=needs_input)
    settings["checks"] = json.loads((repo / "worker-checks.json").read_text())["checks"]
    checker_bytes = {name: (repo / name).read_bytes()
                     for name in ("tools/format_labels.py", "worker-checks.json")}
    receipt = tmp_path / "publication-receipt.json"
    db = repo / ".leafcutter/background-worker/state.sqlite"
    reviewer = SDKReviewer(settings["reviewer"])
    reviewer.preflight()
    adapter = HybridRepair(reviewer) if hybrid else None
    with Store(db) as store:
        settings = store.update_settings(**settings)
        plans = plan_features(load_records(repo), target_completed=target_completed(repo, "origin/main"))
        assert len(plans.ready) == 1, plans.excluded
        run = store.claim_feature(plans.ready[0].to_dict())
        engine = WorkerEngine(repo, store, settings, reviewer=adapter,
                              git=LocalPublication(repo, settings, remote, receipt))
        if os.environ.get("LEAFCUTTER_LIVE_TRACE") == "1":
            engine.local.invoke = traced_invocation(engine.local.invoke, tmp_path / "local-events.jsonl")
        result = engine.run(run["id"])
        if needs_input:
            assert result["state"] == "blocked", result
            item = store.list_inbox(pending_only=True)[0]
            assert item["details"]["questions"]
            assert all(b["attempts"] == 0 and b["elapsed_seconds"] == 0
                       for b in result["budgets"].values()), "Known inputs consumed model budget"
            trace = tmp_path / "local-events.jsonl"
            assert not trace.exists() or not trace.read_text(), "Model called before required input"
            blocked_workspace = Path(result["workspace"])
            assert not git(blocked_workspace, "status", "--porcelain"), "Files changed before policy answer"
            for relative in ("labels.py", "tests/test_labels.py", "README.md", "label-policy.json"):
                assert (blocked_workspace / relative).read_bytes() == (repo / relative).read_bytes()
            for name, expected in checker_bytes.items():
                assert (blocked_workspace / name).read_bytes() == expected
            assert not result["payload"].get("evidence"), "AC completed before policy answer"
            saved_workspace, saved_budgets = result["workspace"], result["budgets"]
            cli = Path(__file__).resolve().parents[2] / "scripts/background_worker_cli.py"
            prefix = [sys.executable, str(cli), "--repo", str(repo)]
            command([*prefix, "off"], tmp_path)
            command([*prefix, "answer", run["id"], "--request-id", item["id"],
                     "--answer", "collapse"], tmp_path)
            assert store.get_settings()["enabled"] is False
            assert store.get_run(run["id"])["budgets"] == saved_budgets
            engine.run(run["id"])
            assert store.get_run(run["id"])["budgets"] == saved_budgets
            command([*prefix, "on", "--no-start"], tmp_path)
            result = engine.run(run["id"])
            assert result["workspace"] == saved_workspace
        (tmp_path / "run-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        assert result["state"] == "delivered", store.list_inbox()
        assert set(result["payload"]["evidence"]) == {"LIVE-100a-1", "LIVE-100a-2"}
        assert all(0 < b["attempts"] <= 3 for b in result["budgets"].values())
        assert all(b["elapsed_seconds"] <= 3600 for b in result["budgets"].values())
        assert all(check["inspected"] > 0 and check["passed"]
                   for check in result["payload"]["package"]["feature_checks"])
        workspace = Path(result["workspace"])
        for name, expected in checker_bytes.items():
            assert (workspace / name).read_bytes() == expected, "Project checker was modified"
        first_sha = first_ac_commit(workspace, result["payload"]["base_sha"], "LIVE-100a-1")
        first_source = git(workspace, "show", first_sha + ":labels.py")
        assert not git(workspace, "ls-tree", "--name-only", first_sha, "--", "tests/test_blank_labels.py")
        # Check temporal scope at the AC1 evidence revision without checking out
        # history or exposing the coordinator to executing model-authored code.
        historical_check = (
            "namespace={}\nexec(compile(" + repr(first_source) + ", 'ac1-labels.py', 'exec'), namespace)\n"
            "normalize=namespace['normalize_label']\n"
            "assert normalize('  A\\t B  ') == 'A B'\n"
            "for value in ['', '   ', '\\t', '\\n', '\\t\\n']:\n"
            "    assert normalize(value) == '', 'AC1 implemented future AC2 rejection early'\n"
        )
        engine.local.check(workspace, [sys.executable, "-c", historical_check], timeout=60)
        assert (workspace / ".leafcutter/live-hook.log").read_text().splitlines().count("checked") >= 2
        assert (workspace / "tests/test_labels.py").read_text(encoding="utf-8") == original_tests
        assert (workspace / "tests/test_blank_labels.py").is_file()
        assert "NotImplementedError" not in (workspace / "labels.py").read_text(encoding="utf-8")
        if hybrid:
            assert result["review_count"] == 2
            assert adapter.calls == 2
            assert (workspace / "tests/test_unicode_regression.py").is_file()
        sha = git(workspace, "rev-parse", "HEAD")
        publication = json.loads(receipt.read_text(encoding="utf-8"))
        assert publication["sha"] == result["payload"]["validated_sha"] == result["payload"]["reviewed_sha"] == sha

    # Acceptance assertions live OUTSIDE every model-writable feature worktree.
    assertions = tmp_path / "independent_assertions.py"
    assertions.write_text(
        "import importlib.util, pathlib, sys\n"
        "spec=importlib.util.spec_from_file_location('accepted_labels', pathlib.Path(sys.argv[1])/'labels.py')\n"
        "module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)\n"
        "f=module.normalize_label\n"
        "assert f('  A\\t B\\n C  ') == 'A B C'\n"
        "assert f('Hello, WORLD!') == 'Hello, WORLD!'\n"
        "assert f('x\\u00a0y') == 'x y'\n"
        "for value in ['', '   ', '\\t', '\\n', '\\t\\n']:\n"
        "    try: f(value)\n"
        "    except ValueError as exc: assert str(exc) == 'label must not be blank'\n"
        "    else: raise AssertionError('blank input accepted')\n",
        encoding="utf-8")
    # Execute model-authored code inside the same enforced sandbox, passing the
    # externally held assertions as a command argument rather than granting the
    # model filesystem access to the acceptance source.
    LocalCodexExecutor(settings["implementation"]).check(
        workspace,
        [sys.executable, "-c", assertions.read_text(encoding="utf-8"), str(workspace)],
        timeout=60,
    )
    with Store(db) as reopened:
        before = reopened.get_run(run["id"])
        restarted = WorkerEngine(repo, reopened, settings,
                                 git=LocalPublication(repo, settings, remote, receipt)).run(run["id"])
        assert restarted["state"] == "delivered"
        assert restarted["budgets"] == before["budgets"]
        assert reopened.claim_feature(plans.ready[0].to_dict()) is None
        assert len(reopened.list_runs()) == 1
    mode = "real-needs-input-recovery" if needs_input else "hybrid-repair" if hybrid else "real-happy-path"
    print(json.dumps({"mode": mode,
                      "fixture": str(tmp_path), "run_id": run["id"], "reviewed_sha": sha,
                      "publication": "local bare push only; no GitHub PR"}))


# covers: ACD-1300g-1 ACD-1300g-2 ACD-1300g-3 ACD-1300g-4 ACD-1300a-3
def test_background_worker_live_happy_path(tmp_path):
    run_live(tmp_path)


# covers: ACD-1300g-3-i
@pytest.mark.skipif(os.environ.get("LEAFCUTTER_LIVE_HYBRID_REPAIR") != "1",
                    reason="Synthetic first-review injection needs separate opt-in")
def test_background_worker_live_hybrid_repair(tmp_path):
    run_live(tmp_path, hybrid=True)


# covers: ACD-1300c-2 ACD-1300e-1 ACD-1300b-3
@pytest.mark.skipif(os.environ.get("LEAFCUTTER_LIVE_NEEDS_INPUT") != "1",
                    reason="Real clarification and restart exercise needs separate opt-in")
def test_background_worker_live_needs_input_recovery(tmp_path):
    run_live(tmp_path, needs_input=True)
