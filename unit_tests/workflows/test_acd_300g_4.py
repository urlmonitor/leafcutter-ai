"""
MODULE: unit_tests/workflows/test_acd_300g_4.py
COVERS: ACD-300g-4
GOAL: Red-first specification of cancel at a confirmation gate: no commit for the cancelled stage, the drafts
    stay on disk untouched, the exit message lists the uncommitted draft paths and gives an anchored git
    checkout, a gate-2 cancel keeps the stage-1 commit and counts only stage-2 ids as drafts, and the message
    keeps the committed and the uncommitted ids apart.
ARCHITECTURE: The cancel runs resume the REAL plan-feature.js through run_workflow_under_e2 at gate-po / gate-ba
    (_acd_300g_support.py; it stands in for run_plan_feature_e2, which needs a hand-written JS mock per test).
    buildCancelMessage is the REAL function run through run_isolated_e2 (_plan_feature_e2_runner.py).
RED STATE: two tests are red until buildCancelMessage lists the rule check's records_to_commit paths
    (cancel_message_lists_draft_paths, gate_cancel_message_lists_rule_check_paths); the other five are
    green-today guards of the existing cancel behaviour.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_300g_support import (  # noqa: E402
    BA_IDS, PO_IDS, UNDO, after_gate, build_cancel_message, calls, committed_stages, gate_run, names, terminal,
)

STORE = "docs/acceptance-criteria"
WORKTREE = "/tmp/authoring-wt"
# The product-owner ids the mocked git log recovers (committed_stages gives the first stage ACD-9301).
PO_IDS_IN_LOG = ["ACD-9301"]


def _po_cancel():
    return gate_run("strategic", "gate-po", "cancel", PO_IDS)


def _ba_cancel():
    """Gate 2 cancelled with the product-owner commit already in the mocked git log."""
    return gate_run("strategic", "gate-ba", "cancel", BA_IDS, **committed_stages("PO"))


def test_acd_300g_4_cancel_at_gate_makes_no_commit():
    # covers: ACD-300g-4
    # angle: reachability
    """Strategic route with a gate-po cancel resume answer: no commit-stage-output dispatch is recorded and
    the run returns status cancelled.

    Wrong version caught: the stage output is committed before the gate action is read.
    """
    result = _po_cancel()

    assert calls(result, "commit-stage-output") == [], names(result)
    assert terminal(result).get("status") == "cancelled", terminal(result)


def test_acd_300g_4_cancel_leaves_drafts_untouched():
    # covers: ACD-300g-4
    # angle: criterion
    """The same cancel run: no dispatch after the gate carries git restore, git checkout, git reset or rm,
    and acs_as_drafts lists the product-owner ids."""
    result = _po_cancel()

    undoing = [str(c.label) for c in after_gate(result) if UNDO.search(str(c.prompt))]
    assert undoing == [], names(result)
    assert sorted(terminal(result).get("acs_as_drafts") or []) == PO_IDS, terminal(result)


def test_acd_300g_4_cancel_message_lists_draft_paths():
    # covers: ACD-300g-4
    # angle: discrimination
    """buildCancelMessage with draft ids [ACD-T-1, ACD-T-2, ACD-T-3] and the rule check's records_to_commit list:
    each draft is listed under its real repo-relative path from that list (subfolder included); the flat
    <store>/ACD-T-1.yaml does not appear; ACD-T-10.yaml is not listed (exact filename-stem match); ACD-T-3, which
    has no matching path, is named without any invented <store>/ACD-T-3.yaml path.

    Wrong versions caught: a flat <store>/<id>.yaml path for a record in a subfolder; a prefix match that lists
    ACD-T-10.yaml for ACD-T-1; an id missing from records_to_commit falling back to an invented flat path.
    """
    sub = f"{STORE}/ac-driven-dev/ACD-T-feature/ACD-T-1.yaml"
    prefix_decoy = f"{STORE}/ac-driven-dev/ACD-T-10.yaml"
    flat_two = f"{STORE}/ac-driven-dev/ACD-T-2.yaml"
    text = build_cancel_message([], ["ACD-T-1", "ACD-T-2", "ACD-T-3"], store=STORE, paths=[sub, prefix_decoy, flat_two])

    assert sub in text and flat_two in text, text
    assert f"{STORE}/ACD-T-1.yaml" not in text, text
    assert "ACD-T-10.yaml" not in text, text
    assert "ACD-T-3" in text, text
    assert f"{STORE}/ACD-T-3.yaml" not in text and "ACD-T-3.yaml" not in text, text


def test_acd_300g_4_gate_cancel_message_lists_rule_check_paths():
    # covers: ACD-300g-4
    # angle: reachability
    """The real workflow resumed at gate-po with cancel and the PO ids, with a rule-check-po reply whose report
    (verdict failed, exit_code 1, so the paths must be read from the report and not from the passed-only
    toCommit) carries records_to_commit: the cancelled outcome's message names both paths exactly and no
    <store>/ACD-9301.yaml flat path.

    Wrong version caught: the cancel message builds flat <store>/<id>.yaml paths instead of using the report's.
    """
    sub = f"{STORE}/ac-driven-dev/ACD-9300-x/ACD-9301.yaml"
    top = f"{STORE}/ac-driven-dev/ACD-9302.yaml"
    report = {"verdict": "failed", "location": STORE, "records_checked": 2, "findings": [],
              "records_to_commit": [sub, top]}
    reply = {"output": json.dumps(report), "exit_code": 1, "stderr": ""}

    outcome = terminal(gate_run("strategic", "gate-po", "cancel", PO_IDS, **{"rule-check-po": reply}))

    assert outcome.get("status") == "cancelled", outcome
    message = outcome.get("message") or ""
    assert sub in message and top in message, message
    assert f"{STORE}/ACD-9301.yaml" not in message and f"{STORE}/ACD-9302.yaml" not in message, message


def test_acd_300g_4_cancel_message_gives_anchored_checkout():
    # covers: ACD-300g-4
    # angle: criterion
    """buildCancelMessage with an authoring worktree path: the message carries git -C "<worktree>" checkout --
    <store>/ and the commit hint, and warns that untracked files need an explicit delete."""
    text = build_cancel_message([], ["ACD-T-1"], store=STORE, worktree=WORKTREE)

    assert f'git -C "{WORKTREE}" checkout -- {STORE}/' in text, text
    assert f'git -C "{WORKTREE}" add' in text and f'git -C "{WORKTREE}" commit' in text, text
    assert re.search(r"untracked", text, re.IGNORECASE) and "rm " in text, text


def test_acd_300g_4_gate2_cancel_keeps_stage1_commit():
    # covers: ACD-300g-4
    # angle: discrimination
    """Resumed at gate-ba with cancel and the PO commit present in the mocked git log: committed_acs holds the
    PO ids and no git reset or git revert dispatch is recorded.

    Wrong version caught: cancel at gate 2 reverts or resets the stage 1 commit.
    """
    result = _ba_cancel()

    outcome = terminal(result)
    assert outcome.get("status") == "cancelled", outcome
    assert outcome.get("committed_acs") == PO_IDS_IN_LOG, outcome
    assert [str(c.label) for c in result.agent_calls if re.search(r"git [^\n]*\b(reset|revert)\b", str(c.prompt))] == [], names(result)


def test_acd_300g_4_gate2_cancel_drafts_are_stage2_only():
    # covers: ACD-300g-4
    # angle: criterion
    """The same gate-ba cancel run: acs_as_drafts holds exactly the business-analyst ids and none of the
    committed PO ids."""
    outcome = terminal(_ba_cancel())

    assert sorted(outcome.get("acs_as_drafts") or []) == BA_IDS, outcome
    assert [i for i in outcome.get("committed_acs") or [] if i in outcome["acs_as_drafts"]] == [], outcome


def test_acd_300g_4_cancel_message_separates_committed_and_drafts():
    # covers: ACD-300g-4
    # angle: discrimination
    """buildCancelMessage with committed [ACD-T-1] and drafts [ACD-T-1a]: the 'Committed ACs from prior stages'
    line names only ACD-T-1 and the uncommitted-drafts section names only ACD-T-1a.

    Wrong versions caught: committed and draft ids are merged into one list; the committed ids are listed
    under the uncommitted-drafts heading.
    """
    text = build_cancel_message(["ACD-T-1"], ["ACD-T-1a"], where="gate after business-analyst", store=STORE)

    committed_line = next(line for line in text.splitlines() if "Committed ACs from prior stages" in line)
    assert set(re.findall(r"ACD-T-\w+", committed_line)) == {"ACD-T-1"}, committed_line
    drafts = text[text.index("Uncommitted draft AC files"):]
    assert set(re.findall(r"ACD-T-\w+", drafts)) == {"ACD-T-1a"}, drafts
