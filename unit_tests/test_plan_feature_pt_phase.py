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
from pathlib import Path

from _plan_feature_e2_runner import run_plan_feature_e2

_REPO_ROOT = Path(__file__).resolve().parents[1]

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
    if (label === 'pt-reconcile-run') {
      // reconcileRunRaw lets a test return a NON-JSON string from the reconcile
      // script dispatch (exercises the unguarded-parse crash / M2 fix).
      if (CFG.reconcileRunRaw !== undefined && CFG.reconcileRunRaw !== null) { return CFG.reconcileRunRaw; }
      return { output: 'reconciled', exit_code: 0 };
    }
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
      if (CFG.editStage === stage && globalThis.__ptGateCounts[stage] === 1) {
        return { action: 'edit', feedback: (CFG.editFeedback || 'pt gate feedback text') };
      }
      return { action: (CFG.ptGateDefault || 'approve') };
    }
    // AC-pipeline gate (label 'gate-<stage>', distinct from 'pt-gate-<stage>').
    // Only overrides the default approve path when a test opts into acEditStage.
    if (CFG.acEditStage && label && label.indexOf('gate-') === 0 && label.indexOf('pt-gate-') !== 0) {
      const stage = label.slice('gate-'.length);
      globalThis.__acGateCounts = globalThis.__acGateCounts || {};
      globalThis.__acGateCounts[stage] = (globalThis.__acGateCounts[stage] || 0) + 1;
      if (CFG.acEditStage === stage && globalThis.__acGateCounts[stage] === 1) {
        return { action: 'edit', feedback: (CFG.acEditFeedback || 'ac gate feedback text') };
      }
      return { action: 'approve' };
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
  // maybeStr returns obj as a JSON STRING when the relevant CFG flag is set, so a
  // test can prove the workflow tolerantly parses string-typed agent responses
  // (m5) instead of silently dropping fields off a string.
  const maybeStr = (obj, flag) => (CFG[flag] ? JSON.stringify(obj) : obj);
  if (agentType === 'mock-data-author') {
    return maybeStr({ status: 'ok', artifact_paths: ['docs/product-truth/mock-data/x.mock.json'] }, 'ptAuthorReturnsString');
  }
  if (agentType === 'mockup-author') {
    return maybeStr({ status: 'ok', artifact_paths: ['docs/product-truth/mockups/x.mockup.json'] }, 'ptAuthorReturnsString');
  }
  if (agentType === 'flow-author') {
    return maybeStr({ status: 'ok', artifact_paths: ['docs/product-truth/flows/x/y.flow.json'], flow_ref: 'flows/x/y.flow.json' }, 'ptAuthorReturnsString');
  }
  if (agentType === 'business-analyst') {
    return maybeStr({ status: 'ok', acs_written: ['ACD-BA'], flow_backlinks: { review: ['ACD-BA'] } }, 'acAuthorReturnsString');
  }
  if (agentType === 'product-owner') { return maybeStr({ status: 'ok', acs_written: ['ACD-PO'] }, 'acAuthorReturnsString'); }
  if (agentType === 'it-po') { return maybeStr({ status: 'ok', acs_written: ['ACD-ITPO'] }, 'acAuthorReturnsString'); }
  if (agentType === 'ac-triage') {
    return { route: (CFG.triageRoute || 'technical'), existing_acs: [], parent_l1_id: (CFG.parentL1 || null), rationale: 't' };
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

    def test_ba_prompt_parents_under_parent_l1_when_present(self) -> None:
        # GAP 2 fix: when triage supplies a parent_l1_id (behavioral route on an
        # existing L1) AND a flow was produced, the flow-derived-AC handoff must
        # explicitly instruct the BA to parent the derived L2/L3 under that L1 so
        # they are never orphaned — not rely on the generic parent_l1_id field alone.
        cfg = {
            "classifier": {"outcome": "full-set", "component": "ux-prototyping"},
            "triageRoute": "behavioral",
            "parentL1": "UXP-491",
        }
        _res, side = _run(cfg)
        ba = next(c for c in side["allCalls"] if c.get("label") == "stage-ba-author")
        self.assertIn("flow was approved", ba["instr"])
        # The explicit parenting instruction names the run's L1.
        self.assertIn("Parent every flow-derived L2/L3 under the run's L1", ba["instr"])
        self.assertIn("UXP-491", ba["instr"])

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
        # REAL `git log --name-only --format=%H%x00%s` shape (verified against
        # the live repo): each commit is a header line `<hash>\x00<subject>`,
        # then a BLANK line, then its file list — and there is NO blank line
        # between one commit's last file and the next commit's header.
        flow_ref_log = (
            "aaaaaaa\x00plan-feature(MOCK-DATA): ux-prototyping\n"
            "\n"
            "docs/product-truth/mock-data/x.mock.json\n"
            "bbbbbbb\x00plan-feature(MOCKUP): ux-prototyping\n"
            "\n"
            "docs/product-truth/mockups/x.mockup.json\n"
            "ccccccc\x00plan-feature(FLOW): ux-prototyping\n"
            "\n"
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


# ---------------------------------------------------------------------------
# M2 — unguarded JSON.parse of the reconcile-run result must not crash the run.
# ---------------------------------------------------------------------------
class TestReconcileRunUnparseable(unittest.TestCase):
    def test_non_json_reconcile_result_does_not_crash_workflow(self) -> None:
        # full-set + technical route → a flow is produced, the BA stage is forced,
        # and reconciliation runs after BA. The reconcile-run dispatch returns a
        # NON-JSON string. The workflow must still complete (no throw) and must
        # NOT proceed to commit the reconciliation (it reported error).
        cfg = {
            "classifier": {"outcome": "full-set", "component": "ux-prototyping"},
            "triageRoute": "technical",
            "reconcileRunRaw": "this is not json at all",
        }
        res, side = _run(cfg)
        # Workflow ran to completion despite the unparseable reconcile result.
        self.assertEqual(res.get("status"), "ok")
        # Reconciliation WAS attempted…
        self.assertIn("pt-reconcile-run", _labels(side))
        # …but reported error → the dedicated reconciliation commit never ran.
        self.assertNotIn("commit-flow-reconciliation", _labels(side))


# ---------------------------------------------------------------------------
# m5 — PT/AC author results returned as JSON STRINGS must be tolerantly parsed
#      (not read as `.field` off a string → dropped to []).
# ---------------------------------------------------------------------------
class TestAuthorResultTolerantParse(unittest.TestCase):
    def test_pt_author_json_string_artifact_paths_are_staged(self) -> None:
        cfg = {
            "classifier": {"outcome": "mock-data-only", "component": "ux-prototyping"},
            "ptAuthorReturnsString": True,
        }
        res, side = _run(cfg)
        self.assertEqual(res.get("status"), "ok")
        # The mockdata commit must stage the reported artifact path — proving the
        # string response was parsed rather than dropped to [] (index.json only).
        md_commit = next(
            c for c in side.get("commitCalls", [])
            if "plan-feature(MOCK-DATA)" in c["instructions"]
        )
        self.assertIn("docs/product-truth/mock-data/x.mock.json", md_commit["instructions"])

    def test_ac_author_json_string_acs_are_approved(self) -> None:
        # it-po returns a JSON STRING; its acs_written must still reach the
        # approved set (technical route → it-po only).
        cfg = {
            "classifier": {"outcome": "none", "component": "ux-prototyping"},
            "triageRoute": "technical",
            "acAuthorReturnsString": True,
        }
        res, _side = _run(cfg)
        self.assertEqual(res.get("status"), "ok")
        self.assertIn("ACD-ITPO", res.get("acs_approved", []))


# ---------------------------------------------------------------------------
# m3 — AC-ID crash-resume recovery must parse the REAL `%B` body format.
# ---------------------------------------------------------------------------
class TestAcIdResumeRecovery(unittest.TestCase):
    def test_resumed_ac_ids_recovered_from_real_body_format(self) -> None:
        # behavioral route → pipeline [ba, itpo]. The BA stage is already
        # committed (committedLog) → crash-resume path reads `--format=%B`.
        committed = "bbbbbbb plan-feature(BA): ux-prototyping\n"
        # REAL `git log --format=%B` shape: each commit body has a BLANK line
        # between the subject and the `AC IDs:` line, and commit bodies are
        # separated from each other by a BLANK line.
        resume_body = (
            "plan-feature(BA): ux-prototyping\n"
            "\n"
            "AC IDs: ACD-BA-RESUMED, ACD-BA-2\n"
            "run-id: test-run\n"
            "mid-pipeline commit\n"
            "\n"
            "chore: an unrelated earlier commit\n"
            "\n"
            "some body text\n"
        )
        cfg = {
            "classifier": {"outcome": "none", "component": "ux-prototyping"},
            "triageRoute": "behavioral",
            "committedLog": committed,
            "resumeBodyLog": resume_body,
        }
        res, _side = _run(cfg)
        self.assertEqual(res.get("status"), "ok")
        approved = res.get("acs_approved", [])
        self.assertIn("ACD-BA-RESUMED", approved)
        self.assertIn("ACD-BA-2", approved)


# ---------------------------------------------------------------------------
# m4 — edit gate must thread the user's feedback into the re-dispatched prompt.
# ---------------------------------------------------------------------------
class TestEditFeedbackThreaded(unittest.TestCase):
    def test_pt_edit_feedback_reaches_redispatch_prompt(self) -> None:
        cfg = {
            "classifier": {"outcome": "mock-data-only", "component": "ux-prototyping"},
            "editStage": "mockdata",
            "editFeedback": "MAKE-THE-CART-EMPTY-STATE-EXPLICIT",
        }
        _res, side = _run(cfg)
        md_calls = [c for c in side["allCalls"] if c["agentType"] == "mock-data-author"]
        self.assertEqual(len(md_calls), 2)
        # The SECOND dispatch (post-edit) must carry the feedback text.
        self.assertIn("MAKE-THE-CART-EMPTY-STATE-EXPLICIT", md_calls[1]["instr"])

    def test_ac_edit_feedback_reaches_redispatch_prompt(self) -> None:
        cfg = {
            "classifier": {"outcome": "none", "component": "ux-prototyping"},
            "triageRoute": "behavioral",
            "acEditStage": "ba",
            "acEditFeedback": "SPLIT-THE-REFUND-BEHAVIOUR",
        }
        _res, side = _run(cfg)
        ba_calls = [c for c in side["allCalls"] if c.get("label") == "stage-ba-author"]
        self.assertEqual(len(ba_calls), 2)
        self.assertIn("SPLIT-THE-REFUND-BEHAVIOUR", ba_calls[1]["instr"])


# ---------------------------------------------------------------------------
# m6 — crash-resume past a committed BA stage must emit an observable signal
#      that flow reconciliation was NOT run (instead of silently dropping it).
# ---------------------------------------------------------------------------
class TestResumeReconciliationSignal(unittest.TestCase):
    def test_resume_skipping_ba_emits_reconciliation_signal(self) -> None:
        # All PT stages + the BA stage already committed. On resume the BA stage
        # is skipped BEFORE the reconciliation branch, so the workflow must emit
        # an observable telemetry signal noting reconciliation must be run manually.
        committed = (
            "aaaaaaa plan-feature(MOCK-DATA): ux-prototyping\n"
            "bbbbbbb plan-feature(MOCKUP): ux-prototyping\n"
            "ccccccc plan-feature(FLOW): ux-prototyping\n"
            "ddddddd plan-feature(BA): ux-prototyping\n"
        )
        flow_ref_log = (
            "ccccccc\x00plan-feature(FLOW): ux-prototyping\n"
            "\n"
            "docs/product-truth/flows/x/y.flow.json\n"
        )
        cfg = {
            "classifier": {"outcome": "full-set", "component": "ux-prototyping"},
            "triageRoute": "technical",
            "committedLog": committed,
            "flowRefLog": flow_ref_log,
        }
        res, side = _run(cfg)
        self.assertEqual(res.get("status"), "ok")
        # An observable, non-silent telemetry signal was emitted…
        self.assertIn("pt-telemetry", _labels(side))
        # …and it names the reconciliation-skipped event.
        telem = next(c for c in side["allCalls"] if c.get("label") == "pt-telemetry")
        self.assertIn("pt_reconciliation_skipped_on_resume", telem["instr"])


# ---------------------------------------------------------------------------
# GAP 1 — new-entity admission to entity_registry is owned by mock-data-author.
#
# The registry-admission behaviour is a PROMPT instruction (exercised for real by
# the plant-reviews E2E, which introduced a net-new `Review` entity). A prompt
# cannot be driven through the E2 harness, so we assert the template now carries an
# explicit, unambiguous admission step and that pt-classifier no longer misattributes
# registry ownership to the generator/validator.
# ---------------------------------------------------------------------------
class TestEntityRegistryAdmissionInstruction(unittest.TestCase):
    def _read(self, rel: str) -> str:
        return (_REPO_ROOT / rel).read_text(encoding="utf-8")

    def test_mock_data_author_admits_new_entities_to_registry(self) -> None:
        text = self._read("templates/agents/mock-data-author.md")
        # The template must now tell the agent to ADD a genuinely-new entity name to
        # the authoritative entity_registry array itself.
        self.assertIn("entity_registry", text)
        self.assertIn("Admit a genuinely-new entity yourself (MANDATORY)", text)
        # It must state the registry is authoritative / hand-maintained, NOT generator-derived.
        lowered = text.lower()
        self.assertIn("authoritative", lowered)
        self.assertTrue(
            "not a generator-derived field" in lowered or "never touches `entity_registry`" in text,
            msg="template must state entity_registry is not generator-derived",
        )
        # It must tie the admission to the same index.json edit as the artifacts[] registration.
        self.assertIn("artifacts[]", text)
        self.assertIn("SAME `index.json` edit", text)

    def test_pt_classifier_points_registry_write_to_mock_data_author(self) -> None:
        text = self._read("templates/agents/pt-classifier.md")
        # The classifier still must not write the registry, but the rationale must no
        # longer claim the generator/validator own it — it points at mock-data-author.
        self.assertIn("mock-data-author", text)
        self.assertNotIn("do not add to `entity_registry` (the generator/validator own it)", text)


if __name__ == "__main__":
    unittest.main()
