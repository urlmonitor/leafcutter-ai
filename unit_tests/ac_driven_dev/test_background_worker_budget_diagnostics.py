"""Budget blockers name the observed cause without changing admission limits."""
import pytest

from .test_background_worker_input_gate import setup_run


@pytest.mark.parametrize("cause", ["attempts", "time", "uncertain"])
def test_discovery_budget_blocker_identifies_actual_cause(tmp_path, cause):
    # covers: ACD-1300d-1
    # angle: failure
    store, run, engine, local = setup_run(tmp_path)
    ac_id = "TEST-100a-1"
    with store:
        engine._prepare(run)
        if cause == "attempts":
            for _ in range(3):
                assert store.begin_attempt(run["id"], ac_id)
                store.finish_attempt(run["id"], ac_id, 393)
        else:
            assert store.begin_attempt(run["id"], ac_id)
            if cause == "time":
                store.finish_attempt(run["id"], ac_id, 3600)
        before = store.get_run(run["id"])["budgets"][ac_id]
        result = engine.run(run["id"])
        assert result["state"] == "blocked"
        assert local.calls == local.discoveries == engine.reviewer.calls == engine.git.published == 0
        assert result["budgets"][ac_id] == before
        inbox = store.list_inbox()
        assert len(inbox) == 1
        reason = inbox[0]["reason"].lower()
        if cause == "attempts":
            assert "implementation" in reason and "attempt" in reason and "limit" in reason
            assert "time" not in reason and "uncertain" not in reason
        elif cause == "time":
            assert "time" in reason and "uncertain" not in reason and "attempt limit" not in reason
        else:
            assert "uncertain" in reason and "exhaust" not in reason
        assert not store.list_leases()
