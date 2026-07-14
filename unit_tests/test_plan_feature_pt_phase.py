"""Full-body behavioral tests for the product-truth (PT) phase in plan-feature.js.

Track 1.2 wires an ALWAYS-ON product-truth phase into the E2 runtime workflow,
between ac-triage and the AC pipeline. These tests drive the REAL top-level body
via the _plan_feature_e2_runner harness under a configurable mock agent and assert
on observable dispatch behavior (agent-call sequence + commit prompts + the run
result) — not on source strings.

Coverage (mirrors the plan's Test plan):
  * classifier outcome → run-set for all 5 outcomes incl `none`;
  * malformed / inconsistent classifier JSON → PT skipped, AC pipeline runs;
  * outcome/dispatch disagreement → trust outcome;
  * deterministic PT ordering regardless of dispatch order;
  * each PT stage gated; edit-then-approve; cancel → no PR + prior commits preserved;
  * commit-failure at a PT stage aborts BEFORE the next agent;
  * store-absent self-skip emits an observable telemetry signal + AC pipeline proceeds;
  * force-BA-on-technical when a flow was produced + flow committed before BA;
  * crash-resume skips committed PT stages + recovers flowRef from the FLOW commit.
"""
from __future__ import annotations

import unittest

from _plan_feature_e2_runner import run_plan_feature_e2

_PT_AUTHORS = ("mock-data-author", "mockup-author", "flow-author")

# A single configurable mock agent. Reads globalThis.CFG (injected via extra_ctx).
_MOCK_JS = r"""
async function mockAgent(call) {
  const CFG = globalThis.CFG || {};
  const agentType = call.agentType || '';
  const label = call.label || '';
  const instructions = (call.input && call.input.instructions) || '';
  globalThis.__capturedAllCalls.push({ agentType, label, instr: instructions.slice(0, 1600) });

  if (agentType === 'status-checker') {
    if (instructions.includes('git branch --show-current')) {
      return { output: 'ac-authoring/test', exit_code: 0 };
    }
    if (instructions.includes('setup_ticket_worktree')) {
      return { output: '', exit_code: 0 };
    }
    if (label === 'pt-store-check') {
      return { output: (CFG.storePresent === false ? 'absent' : 'present'), exit_code: 0 };
    }
    if (label === 'pt-telemetry') { return { exit_code: 0 }; }
    if (label === 'resume-flow-ref') { return { output: (CFG.flowRefLog || ''), exit_code: 0 }; }
    if (label === 'pt-reconcile-run') { return { output: 'reconciled', exit_code: 0 }; }
    if (instructions.includes('log --oneline origin/main..HEAD')) {
      return { output: (CFG.committedLog || ''), exit_code: 0 };
    }
    if (instructions.includes('--format=%B')) {
      return { output: (CFG.resumeBodyLog || ''), exit_code: 0 };
    }
    if (instructions.includes('git status --porcelain')) {
      return { output: '', exit_code: 0 };
    }
    if (label.indexOf('pt-gate-') === 0) {
      const stage = label.slice('pt-gate-'.length);
      globalThis.__ptGateCounts = globalThis.__ptGateCounts || {};
      globalThis.__ptGateCounts[stage] = (globalThis.__ptGateCounts[stage] || 0) + 1;
      if (CFG.cancelStage === stage) { return { action: 'cancel' }; }
      if (CFG.editStage === stage && globalThis.__ptGateCounts[stage] === 1) { return { action: 'edit' }; }
      return { action: (CFG.ptGateDefault || 'approve') };
    }
    if (instructions.includes('update their YAML files')) {
      return { status: 'ok', updated: ['ACD-BA', 'ACD-ITPO'] };
    }
    if (instructions.includes('IT PO v3 has enriched')) {
      return { action: 'approve', priority: 'high' };
    }
    if (instructions.includes('has written the following ACs')) {
      return { action: 'approve' };
    }
    return { status: 'ok' };
  }

  if (agentType === 'pt-classifier') {
    if (CFG.classifierRaw !== undefined && CFG.classifierRaw !== null) { return CFG.classifierRaw; }
    return CFG.classifier;
  }
  if (agentType === 'mock-data-author') {
    return { status: 'ok', artifact_paths: ['docs/product-truth/mock-data/x.mock.json'] };
  }
  if (agentType === 'mockup-author') {
    return { status: 'ok', artifact_paths: ['docs/product-truth/mockups/x.mockup.json'] };
  }
  if (agentType === 'flow-author') {
    return { status: 'ok', artifact_paths: ['docs/product-truth/flows/x/y.flow.json'], flow_ref: 'flows/x/y.flow.json' };
  }
  if (agentType === 'business-analyst') {
    return { status: 'ok', acs_written: ['ACD-BA'], flow_backlinks: { review: ['ACD-BA'] } };
  }
  if (agentType === 'product-owner') { return { status: 'ok', acs_written: ['ACD-PO'] }; }
  if (agentType === 'it-po') { return { status: 'ok', acs_written: ['ACD-ITPO'] }; }
  if (agentType === 'ac-triage') {
    return { route: (CFG.triageRoute || 'technical'), existing_acs: [], parent_l1_id: null, rationale: 't' };
  }
  if (agentType === 'commit') {
    globalThis.__capturedCommitCalls.push({ instructions });
    if (CFG.failCommitSubject && instructions.includes(CFG.failCommitSubject)) {
      return { status: 'error', message: 'mock commit failure', hook_name: null, failing_files: [], is_conflict: false };
    }
    return { status: 'ok', message: 'committed successfully' };
  }
  if (agentType === 'pull-request') {
    return { status: 'ok', message: 'PR opened', pr_url: 'https://github.com/o/r/pull/1' };
  }
  return { status: 'ok' };
}
"""


def _run(cfg: dict, user_input: str = "add a checkout screen", timeout: int = 30):
    return run_plan_feature_e2(_MOCK_JS, user_input=user_input, extra_ctx={"CFG": cfg}, timeout=timeout)


def _pt_author_order(side: dict) -> list[str]:
    return [c["agentType"] for c in side.get("allCalls", []) if c["agentType"] in _PT_AUTHORS]


def _agent_types(side: dict) -> list[str]:
    return [c["agentType"] for c in side.get("allCalls", [])]


def _labels(side: dict) -> list[str]:
    return [c.get("label") for c in side.get("allCalls", [])]


# ---------------------------------------------------------------------------
# Classifier outcome → run-set (all 5 outcomes)
# ---------------------------------------------------------------------------
class TestOutcomeToRunSet(unittest.TestCase):
    def test_full_set_dispatches_all_three_in_order(self) -> None:
        cfg = {"classifier": {"outcome": "full-set", "component": "ux-prototyping"}}
        _res, side = _run(cfg)
        self.assertEqual(_pt_author_order(side), ["mock-data-author", "mockup-author", "flow-author"])

    def test_mockup_plus_data_skips_flow(self) -> None:
        cfg = {"classifier": {"outcome": "mockup+data", "component": "ux-prototyping"}}
        _res, side = _run(cfg)
        self.assertEqual(_pt_author_order(side), ["mock-data-author", "mockup-author"])

    def test_mockup_only(self) -> None:
        cfg = {"classifier": {"outcome": "mockup-only", "component": "ux-prototyping"}}
        _res, side = _run(cfg)
        self.assertEqual(_pt_author_order(side), ["mockup-author"])

    def test_mock_data_only(self) -> None:
        cfg = {"classifier": {"outcome": "mock-data-only", "component": "ux-prototyping"}}
        _res, side = _run(cfg)
        self.assertEqual(_pt_author_order(side), ["mock-data-author"])

    def test_none_dispatches_no_pt_agents_but_runs_ac_pipeline(self) -> None:
        cfg = {"classifier": {"outcome": "none", "component": "ux-prototyping"}}
        res, side = _run(cfg)
        self.assertEqual(_pt_author_order(side), [])
        # store presence is not even checked when outcome=none.
        self.assertNotIn("pt-store-check", _labels(side))
        # AC pipeline still ran to completion (technical route → it-po).
        self.assertIn("it-po", _agent_types(side))
        self.assertEqual(res.get("status"), "ok")


# ---------------------------------------------------------------------------
# Malformed / inconsistent classifier + dispatch disagreement
# ---------------------------------------------------------------------------
class TestClassifierDegradation(unittest.TestCase):
    def test_missing_outcome_skips_pt_and_runs_ac(self) -> None:
        cfg = {"classifier": {"component": "ux-prototyping"}}  # no outcome
        res, side = _run(cfg)
        self.assertEqual(_pt_author_order(side), [])
        self.assertNotIn("pt-store-check", _labels(side))
        self.assertIn("it-po", _agent_types(side))
        self.assertEqual(res.get("status"), "ok")

    def test_unparseable_classifier_string_skips_pt_and_runs_ac(self) -> None:
        cfg = {"classifierRaw": "this is not json at all", "classifier": None}
        res, side = _run(cfg)
        self.assertEqual(_pt_author_order(side), [])
        self.assertIn("it-po", _agent_types(side))
        self.assertEqual(res.get("status"), "ok")

    def test_unknown_outcome_enum_skips_pt(self) -> None:
        cfg = {"classifier": {"outcome": "everything", "component": "ux-prototyping"}}
        _res, side = _run(cfg)
        self.assertEqual(_pt_author_order(side), [])

    def test_dispatch_disagreement_trusts_outcome(self) -> None:
        # outcome says mockup-only, but dispatch claims the flow agent — trust outcome.
        cfg = {
            "classifier": {
                "outcome": "mockup-only",
                "component": "ux-prototyping",
                "dispatch": ["mock-data-author", "flow-author"],
            }
        }
        _res, side = _run(cfg)
        self.assertEqual(_pt_author_order(side), ["mockup-author"])


# ---------------------------------------------------------------------------
# Deterministic ordering
# ---------------------------------------------------------------------------
class TestDeterministicOrdering(unittest.TestCase):
    def test_order_is_fixed_regardless_of_dispatch_array_order(self) -> None:
        cfg = {
            "classifier": {
                "outcome": "full-set",
                "component": "ux-prototyping",
                "dispatch": ["flow-author", "mockup-author", "mock-data-author"],
            }
        }
        _res, side = _run(cfg)
        self.assertEqual(_pt_author_order(side), ["mock-data-author", "mockup-author", "flow-author"])


# ---------------------------------------------------------------------------
# Gating: edit-then-approve; cancel
# ---------------------------------------------------------------------------
class TestPtGating(unittest.TestCase):
    def test_edit_then_approve_redispatches_stage(self) -> None:
        cfg = {"classifier": {"outcome": "mock-data-only", "component": "ux-prototyping"}, "editStage": "mockdata"}
        res, side = _run(cfg)
        # mock-data-author dispatched twice (initial + after edit), then AC pipeline runs.
        md_calls = [t for t in _agent_types(side) if t == "mock-data-author"]
        self.assertEqual(len(md_calls), 2)
        self.assertEqual(res.get("status"), "ok")

    def test_cancel_no_pr_prior_commits_preserved(self) -> None:
        cfg = {"classifier": {"outcome": "full-set", "component": "ux-prototyping"}, "cancelStage": "mockup"}
        res, side = _run(cfg)
        self.assertEqual(res.get("status"), "ok")
        self.assertEqual(res.get("cancelled_at"), "pt-gate-mockup")
        self.assertIn("No PR", res.get("message", ""))
        # Prior stage (mock-data) WAS committed; the cancelled stage (mockup) was NOT.
        commit_instrs = [c["instructions"] for c in side.get("commitCalls", [])]
        self.assertTrue(any("plan-feature(MOCK-DATA)" in i for i in commit_instrs))
        self.assertFalse(any("plan-feature(MOCKUP)" in i for i in commit_instrs))
        # No PR was opened.
        self.assertNotIn("pull-request", _agent_types(side))


# ---------------------------------------------------------------------------
# Commit-before-next invariant
# ---------------------------------------------------------------------------
class TestPtCommitFailureAborts(unittest.TestCase):
    def test_commit_failure_aborts_before_next_agent(self) -> None:
        cfg = {
            "classifier": {"outcome": "full-set", "component": "ux-prototyping"},
            "failCommitSubject": "plan-feature(MOCK-DATA)",
        }
        res, side = _run(cfg)
        self.assertEqual(res.get("status"), "error")
        self.assertEqual(res.get("failed_stage"), "mockdata")
        # The next PT agents were NEVER dispatched (aborted before mockup/flow).
        self.assertNotIn("mockup-author", _agent_types(side))
        self.assertNotIn("flow-author", _agent_types(side))


# ---------------------------------------------------------------------------
# Store-absent self-skip
# ---------------------------------------------------------------------------
class TestStoreAbsentSelfSkip(unittest.TestCase):
    def test_store_absent_emits_signal_and_ac_proceeds(self) -> None:
        cfg = {"classifier": {"outcome": "full-set", "component": "ux-prototyping"}, "storePresent": False}
        res, side = _run(cfg)
        # store presence was checked…
        self.assertIn("pt-store-check", _labels(side))
        # …absent → observable, non-silent telemetry signal emitted…
        self.assertIn("pt-telemetry", _labels(side))
        # …no PT authors dispatched…
        self.assertEqual(_pt_author_order(side), [])
        # …and the AC pipeline proceeded.
        self.assertIn("it-po", _agent_types(side))
        self.assertEqual(res.get("status"), "ok")


# ---------------------------------------------------------------------------
# Flow → BA handoff + force-BA on technical
# ---------------------------------------------------------------------------
class TestFlowToBaHandoff(unittest.TestCase):
    def test_force_ba_on_technical_when_flow_produced(self) -> None:
        # technical route (no BA normally) BUT full-set outcome produces a flow →
        # the BA stage is forced in so the flow steps aren't orphaned.
        cfg = {"classifier": {"outcome": "full-set", "component": "ux-prototyping"}, "triageRoute": "technical"}
        _res, side = _run(cfg)
        self.assertIn("business-analyst", _agent_types(side))

    def test_ba_prompt_carries_flow_anchor_when_no_parent_l1(self) -> None:
        cfg = {"classifier": {"outcome": "full-set", "component": "ux-prototyping"}, "triageRoute": "technical"}
        _res, side = _run(cfg)
        ba = next(c for c in side["allCalls"] if c.get("label") == "stage-ba-author")
        self.assertIn("flow was approved", ba["instr"])
        # No parent_l1_id on the technical route → anchor instruction present.
        self.assertIn("Anchor the derived L2s", ba["instr"])

    def test_flow_committed_before_ba_author(self) -> None:
        cfg = {"classifier": {"outcome": "full-set", "component": "ux-prototyping"}, "triageRoute": "technical"}
        _res, side = _run(cfg)
        calls = side["allCalls"]
        flow_commit_idx = next(
            i for i, c in enumerate(calls)
            if c["agentType"] == "commit" and "plan-feature(FLOW)" in c["instr"]
        )
        ba_author_idx = next(i for i, c in enumerate(calls) if c.get("label") == "stage-ba-author")
        self.assertLess(flow_commit_idx, ba_author_idx, msg="flow must be committed BEFORE the BA stage")

    def test_reconciliation_runs_after_ba(self) -> None:
        cfg = {"classifier": {"outcome": "full-set", "component": "ux-prototyping"}, "triageRoute": "technical"}
        _res, side = _run(cfg)
        labels = _labels(side)
        self.assertIn("pt-reconcile-run", labels)
        ba_idx = labels.index("stage-ba-author")
        self.assertGreater(labels.index("pt-reconcile-run"), ba_idx)


# ---------------------------------------------------------------------------
# Crash-resume for PT stages + flowRef recovery
# ---------------------------------------------------------------------------
class TestPtCrashResume(unittest.TestCase):
    def test_committed_pt_stages_are_skipped(self) -> None:
        committed = (
            "aaaaaaa plan-feature(MOCK-DATA): ux-prototyping\n"
            "bbbbbbb plan-feature(MOCKUP): ux-prototyping\n"
        )
        cfg = {
            "classifier": {"outcome": "mockup+data", "component": "ux-prototyping"},
            "committedLog": committed,
        }
        _res, side = _run(cfg)
        # Both PT stages already committed → neither author re-dispatched.
        self.assertEqual(_pt_author_order(side), [])

    def test_flow_ref_recovered_from_committed_flow_commit(self) -> None:
        committed = (
            "aaaaaaa plan-feature(MOCK-DATA): ux-prototyping\n"
            "bbbbbbb plan-feature(MOCKUP): ux-prototyping\n"
            "ccccccc plan-feature(FLOW): ux-prototyping\n"
        )
        # recoverFlowRefFromCommit reads: <hash>\x00<subject>\n<file>\n\n
        flow_ref_log = (
            "ccccccc\x00plan-feature(FLOW): ux-prototyping\n"
            "docs/product-truth/flows/x/y.flow.json\n"
        )
        cfg = {
            "classifier": {"outcome": "full-set", "component": "ux-prototyping"},
            "triageRoute": "technical",
            "committedLog": committed,
            "flowRefLog": flow_ref_log,
        }
        _res, side = _run(cfg)
        # All PT stages committed → no PT authors, but flowRef recovery ran…
        self.assertEqual(_pt_author_order(side), [])
        self.assertIn("resume-flow-ref", _labels(side))
        # …and the recovered flowRef flows into the forced BA prompt.
        ba = next(c for c in side["allCalls"] if c.get("label") == "stage-ba-author")
        self.assertIn("docs/product-truth/flows/x/y.flow.json", ba["instr"])


if __name__ == "__main__":
    unittest.main()
