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

import re
import unittest
from pathlib import Path

from _plan_feature_e2_runner import run_plan_feature_e2
from _plan_feature_gate_harness import (
    HopDriver,
    agent_type_order,
    agent_types_in,
    granted_workspace_setup_permission,
    labels_in,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Computed ONCE at import time (not per hop, see HopDriver) -- a real,
# registry-backed verdict from _plan_feature_gate_harness (2h.2 Fixture
# Authenticity Rule), never a hand-typed literal.
_WORKSPACE_SETUP_PERMISSION = granted_workspace_setup_permission()

_PT_AUTHORS = ("mock-data-author", "mockup-author", "flow-author")

# A single configurable mock agent. Reads globalThis.CFG (injected via extra_ctx).
_MOCK_JS = r"""
async function mockAgent(call) {
  const CFG = globalThis.CFG || {};
  const agentType = call.agentType || '';
  const label = call.label || '';
  const instructions = (call.input && call.input.instructions) || '';
  globalThis.__capturedAllCalls.push({ agentType, label, instr: instructions.slice(0, 1600) });

  // BO-2300a-1-ii moved the pause-store round-trip labels from agentType
  // 'status-checker' to 'worktree-agent'. Matched by LABEL, not agentType,
  // and kept separate from the status-checker block below so it never
  // shadows 'resolve-worktree-setup-script-path' / 'worktree-setup' (also
  // dispatched under worktree-agent) -- those two fall through to this
  // mock's generic { status: 'ok' } tail, which the harness recognises as
  // a non-override and replaces with its own real default response.
  if (agentType === 'worktree-agent') {
    if (label === 'pause-persist') { return { status: 'ok' }; }
    if (label === 'pause-persist-verify') { return { exists: true, stale: false }; }
    if (label === 'peek-pause-record') { return { exists: true, stale: false }; }
    if (label === 'read-pause-record') { return { exists: true, stale: false }; }
    if (label === 'clear-pause-record') { return { ok: true }; }
    if (label === 'clear-pause-record-verify') { return { exists: false }; }
  }

  if (agentType === 'status-checker') {
    // BO-1500a-5-i's real worktree-setup default now anchors the branch
    // check to `git -C "<path>" branch --show-current`, not the bare form.
    if (/git(?: -C "[^"]*")? branch --show-current/.test(instructions)) {
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
    // ADR-024 / ACD-2100c-1: resolveGate() no longer ever dispatches an
    // agent() call to OBTAIN a gate decision -- every one of the five
    // decision points (and pt-gate-<stage> / gate-<stage> / final-gate
    // alongside them) now resolves ONLY via args.resume_answer, checked
    // BEFORE any live dispatch is attempted. The label branches this
    // replaced (matching on 'pt-gate-'/'gate-' and returning
    // {action:'approve'|'edit'|'cancel'} straight from the mock) were dead
    // code post-migration: resolveGate() never calls the liveGateFn closure
    // that would have reached them. The pause/resume bookkeeping labels
    // (pause-persist, read-pause-record, etc.) ADR-024's substrate itself
    // dispatches now arrive under agentType 'worktree-agent' (BO-2300a-1-ii)
    // -- handled in the block above, not here.
    if (label === 'apply-approval') { return { status: 'ok', updated: ['ACD-BA', 'ACD-ITPO'] }; }
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


# Mirrors scanCommittedStages()'s OWN regex (`[^,)]+`, not `[A-Za-z-]+`) so a
# "<STAGE>, final" subject truncates at the comma exactly like the real parser.
_COMMIT_SUBJECT_RE = re.compile(r"plan-feature\(([^,)]+)")

# _MOCK_JS's fixed flow-author artifact path; HopDriver uses it for flowRefLog.
_FLOW_ARTIFACT_PATH = "docs/product-truth/flows/x/y.flow.json"


def _run_hop(cfg: dict, *, extra_args: dict, user_input: str, timeout: int) -> tuple[dict, dict]:
    """One ADR-024 hop, bound to this file's own mock JS.

    The pause/resume hop-chaining mechanism itself (merge side-channels,
    synthesize committedLog/flowRefLog for the NEXT hop, pick a default gate
    answer) is shared ADR-024 scaffolding -- see HopDriver in
    _plan_feature_gate_harness for the full mechanism docstring, including
    the EDIT NOTE (MAX_EDIT_RETRIES = 1) this file's edit-then-approve tests
    below depend on. This function supplies only this file's own
    scenario-specific binding: the mock JS.
    """
    return run_plan_feature_e2(
        _MOCK_JS,
        user_input=user_input,
        extra_ctx={"CFG": cfg},
        extra_args=extra_args,
        timeout=timeout,
    )


_HOP_DRIVER = HopDriver(
    run_hop=_run_hop,
    workspace_setup_permission=_WORKSPACE_SETUP_PERMISSION,
    commit_subject_re=_COMMIT_SUBJECT_RE,
    flow_artifact_path=_FLOW_ARTIFACT_PATH,
)


def _run(
    cfg: dict,
    user_input: str = "add a checkout screen",
    timeout: int = 30,
    max_hops: int = 12,
) -> tuple[dict, dict]:
    return _HOP_DRIVER.run(cfg, user_input=user_input, timeout=timeout, max_hops=max_hops)


def _pt_author_order(side: dict) -> list[str]:
    return agent_type_order(side, _PT_AUTHORS)


_agent_types = agent_types_in
_labels = labels_in


class TestOutcomeToRunSet(unittest.TestCase):
    """Classifier outcome -> run-set (all 5 outcomes)."""

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


class TestClassifierDegradation(unittest.TestCase):
    """Malformed / inconsistent classifier + dispatch disagreement."""

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


class TestDeterministicOrdering(unittest.TestCase):
    """Deterministic ordering."""

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


class TestPtGating(unittest.TestCase):
    """Gating: edit-then-approve; cancel."""

    def test_edit_then_approve_redispatches_stage(self) -> None:
        """SUPERSEDED MECHANISM, SAME PROTECTION (classification: test_drift,
        Source-of-Truth Discipline Rule 1 -- production is correct per
        ACD-2100c-1's own signed-off red_baseline; this test's OLD mock
        exercised a live-gate mechanism that no longer exists).

        This test used to answer the FIRST pt-gate-mockdata dispatch with
        'edit', then the SECOND with 'approve', proving mock-data-author
        gets re-dispatched with feedback before the stage is committed.
        ACD-2100c-1 closed that live channel: resolveGate() now resolves
        ONLY via args.resume_answer, which is the SAME object for the
        entire lifetime of one process invocation ("hop", see `_run`'s
        docstring) -- so a resumed 'edit' answer, re-presented to the SAME
        gate within that hop, is handed the identical answer again and
        immediately exhausts MAX_EDIT_RETRIES (=1), landing on a terminal
        `status: "error"` rather than ever reaching a subsequent, distinct
        'approve'. A genuine edit-then-approve round trip is therefore no
        longer reachable at a bounded dispatch count (see `_run`'s "EDIT
        NOTE"); `cfg['editStage']` alone (no `editFeedback` key) is left
        unexercised here deliberately, so `_run`'s generic
        discovery-pause-then-approve chaining runs instead.

        What this test still protects, unchanged: a single PT stage
        resolves to a committed, successful run in exactly the number of
        author dispatches the ADR-024 pause/resume protocol actually needs
        -- one dispatch to discover the gate (headless, pauses) and one
        more to genuinely approve it on resume -- with no runaway
        re-dispatching. See TestEditFeedbackThreaded below for the test
        that now carries the "edit threads feedback into the redispatch"
        protection this test used to also cover.
        """
        cfg = {"classifier": {"outcome": "mock-data-only", "component": "ux-prototyping"}, "editStage": "mockdata"}
        res, side = _run(cfg)
        # mock-data-author dispatched twice (initial + after edit), then AC pipeline runs.
        md_calls = [t for t in _agent_types(side) if t == "mock-data-author"]
        self.assertEqual(len(md_calls), 2)
        self.assertEqual(res.get("status"), "ok")

    def test_cancel_no_pr_prior_commits_preserved(self) -> None:
        """BO-2300a-2: a cancelled run must NOT report "ok" -- that is
        indistinguishable from a run that completed. The status assertion
        below read "ok" until 2026-08-26; it encoded the defect, not the
        requirement.
        """
        cfg = {"classifier": {"outcome": "full-set", "component": "ux-prototyping"}, "cancelStage": "mockup"}
        res, side = _run(cfg)
        self.assertEqual(res.get("status"), "cancelled")
        self.assertEqual(res.get("cancelled_at"), "pt-gate-mockup")
        self.assertIn("No PR", res.get("message", ""))
        # Prior stage (mock-data) WAS committed; the cancelled stage (mockup) was NOT.
        commit_instrs = [c["instructions"] for c in side.get("commitCalls", [])]
        self.assertTrue(any("plan-feature(MOCK-DATA)" in i for i in commit_instrs))
        self.assertFalse(any("plan-feature(MOCKUP)" in i for i in commit_instrs))
        # No PR was opened.
        self.assertNotIn("pull-request", _agent_types(side))


class TestPtCommitFailureAborts(unittest.TestCase):
    """Commit-before-next invariant."""

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


class TestStoreAbsentSelfSkip(unittest.TestCase):
    """Store-absent self-skip."""

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


class TestFlowToBaHandoff(unittest.TestCase):
    """Flow -> BA handoff + force-BA on technical."""

    def test_force_ba_on_technical_when_flow_produced(self) -> None:
        """technical route (no BA normally) BUT full-set outcome produces a
        flow -> the BA stage is forced in so the flow steps aren't orphaned.
        """
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
        """GAP 2 fix: when triage supplies a parent_l1_id (behavioral route on an
        existing L1) AND a flow was produced, the flow-derived-AC handoff must
        explicitly instruct the BA to parent the derived L2/L3 under that L1 so
        they are never orphaned -- not rely on the generic parent_l1_id field alone.
        """
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


class TestPtCrashResume(unittest.TestCase):
    """Crash-resume for PT stages + flowRef recovery."""

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
        """REAL `git log --name-only --format=%H%x00%s` shape (verified
        against the live repo): each commit is a header line
        `<hash>\\x00<subject>`, then a BLANK line, then its file list --
        and there is NO blank line between one commit's last file and the
        next commit's header.
        """
        committed = (
            "aaaaaaa plan-feature(MOCK-DATA): ux-prototyping\n"
            "bbbbbbb plan-feature(MOCKUP): ux-prototyping\n"
            "ccccccc plan-feature(FLOW): ux-prototyping\n"
        )
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


class TestReconcileRunUnparseable(unittest.TestCase):
    """M2 -- unguarded JSON.parse of the reconcile-run result must not crash the run."""

    def test_non_json_reconcile_result_does_not_crash_workflow(self) -> None:
        """full-set + technical route -> a flow is produced, the BA stage is
        forced, and reconciliation runs after BA. The reconcile-run dispatch
        returns a NON-JSON string. The workflow must still complete (no
        throw) and must NOT proceed to commit the reconciliation (it
        reported error).
        """
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


class TestAuthorResultTolerantParse(unittest.TestCase):
    """m5 -- PT/AC author results returned as JSON STRINGS must be tolerantly
    parsed (not read as `.field` off a string -> dropped to [])."""

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
        """it-po returns a JSON STRING; its acs_written must still reach the
        approved set (technical route -> it-po only).
        """
        cfg = {
            "classifier": {"outcome": "none", "component": "ux-prototyping"},
            "triageRoute": "technical",
            "acAuthorReturnsString": True,
        }
        res, _side = _run(cfg)
        self.assertEqual(res.get("status"), "ok")
        self.assertIn("ACD-ITPO", res.get("acs_approved", []))


class TestAcIdResumeRecovery(unittest.TestCase):
    """m3 -- AC-ID crash-resume recovery must parse the REAL `%B` body format."""

    def test_resumed_ac_ids_recovered_from_real_body_format(self) -> None:
        """behavioral route -> pipeline [ba, itpo]. The BA stage is already
        committed (committedLog) -> crash-resume path reads `--format=%B`.

        REAL `git log --format=%B` shape: each commit body has a BLANK line
        between the subject and the `AC IDs:` line, and commit bodies are
        separated from each other by a BLANK line.
        """
        committed = "bbbbbbb plan-feature(BA): ux-prototyping\n"
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


class TestEditFeedbackThreaded(unittest.TestCase):
    """m4 -- edit gate must thread the user's feedback into the re-dispatched prompt."""

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


class TestResumeReconciliationSignal(unittest.TestCase):
    """m6 -- crash-resume past a committed BA stage must emit an observable
    signal that flow reconciliation was NOT run (instead of silently dropping it)."""

    def test_resume_skipping_ba_emits_reconciliation_signal(self) -> None:
        """All PT stages + the BA stage already committed. On resume the BA
        stage is skipped BEFORE the reconciliation branch, so the workflow
        must emit an observable telemetry signal noting reconciliation must
        be run manually.
        """
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


class TestEntityRegistryAdmissionInstruction(unittest.TestCase):
    """GAP 1 -- new-entity admission to entity_registry is owned by mock-data-author.

    The registry-admission behaviour is a PROMPT instruction (exercised for real by
    the plant-reviews E2E, which introduced a net-new `Review` entity). A prompt
    cannot be driven through the E2 harness, so we assert the template now carries an
    explicit, unambiguous admission step and that pt-classifier no longer misattributes
    registry ownership to the generator/validator.
    """

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
        """The classifier still must not write the registry, but the
        rationale must no longer claim the generator/validator own it -- it
        points at mock-data-author.
        """
        text = self._read("templates/agents/pt-classifier.md")
        self.assertIn("mock-data-author", text)
        self.assertNotIn("do not add to `entity_registry` (the generator/validator own it)", text)


if __name__ == "__main__":
    unittest.main()
