"""
MODULE: test_inf_500d_4_iv (workflow side)
GOAL: RED test for AC INF-500d-4-iv's plan-feature.js half -- the product-truth
    telemetry line the /plan-feature workflow dispatches is appended to the
    DECLARED operational telemetry stream, obtained through INF-500d-4-iii's
    location query in the dispatched instruction, never to a path the workflow
    composes from the (disposable) authoring worktree.
AC: INF-500d-4-iv (source_ac); depends on INF-500d-4-iii (--print-location).

WHY THIS DRIVES BEHAVIOUR, NOT A GREP: the real plan-feature.js top-level body
    runs in the E2 stub harness (``run_workflow_under_e2``: the actual JS in a
    sandboxed Node vm). The store-absent branch of the product-truth phase calls
    the REAL ``emitPtTelemetry`` with the REAL ``authoringWorktreePath`` the
    configured ``worktree-setup`` reply names, and the test inspects the prompt
    the workflow's own control flow assembled for the ``pt-telemetry`` dispatch.

CONTRACT THIS FILE FIXES: the dispatched instruction (a) still carries the
    event line, (b) obtains the append path by running the deployed
    ``sink_resolution.py --print-location telemetry``, and (c) contains no
    ``debugging/logs`` path composed by the workflow. The dispatch stays
    best-effort (one ``pt-telemetry`` call; the workflow does not halt).
"""
# @ac-tag: INF-500d-4-iv

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_TIMEOUT = 30
_FAKE_AUTHORING_WORKTREE = "/tmp/inf-500d-4-iv-fake-authoring-worktree"


def _label_responses() -> dict:
    """Reach the store-absent self-skip: a real authoring worktree, a PT outcome, and an ABSENT store."""
    return {
        "stage-0-triage": {
            "route": "strategic",
            "existing_acs": [],
            "parent_l1_id": None,
            "rationale": "test fixture -- route straight past the covered-route gate",
        },
        "worktree-setup": {
            "output": json.dumps(
                {
                    "worktree_path": _FAKE_AUTHORING_WORKTREE,
                    "ac_store_path": _FAKE_AUTHORING_WORKTREE + "/docs/acceptance-criteria",
                }
            ),
            "exit_code": 0,
        },
        "pt-classify": {
            "outcome": "mock-data-only",
            "component": "test-comp",
            "dispatch": ["mock-data-author"],
        },
        "pt-store-check": {"output": "absent", "exit_code": 0},
        "pt-telemetry": {"exit_code": 0},
    }


def test_plan_feature_pt_telemetry_targets_the_declared_stream():
    # covers: INF-500d-4-iv
    # angle: seam
    """The pt-telemetry dispatch asks the location query for the stream; it composes no worktree-prefixed log path."""
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_label_responses(),
        args={"run_id": "test-inf-500d-4-iv"},
    )
    assert result.error == "", f"Harness error: {result.error}"

    labels = [call.label for call in result.agent_calls]
    calls = [call for call in result.agent_calls if call.label == "pt-telemetry"]
    assert len(calls) == 1, f"the store-absent skip must dispatch exactly one pt-telemetry line; labels: {labels}"
    prompt = calls[0].prompt
    assert isinstance(prompt, str)

    # The logged line must still carry this event as its "event" field (key and value together, not the bare name).
    assert re.search(r'event\W+pt_phase_skipped_store_absent', prompt), f"the event line is no longer carried:\n{prompt}"
    assert "debugging/logs" not in prompt, (
        "the instruction still names a path the workflow composed itself (the worktree-prefixed "
        f"debugging/logs/agent_telemetry.jsonl append path):\n{prompt}"
    )
    assert _FAKE_AUTHORING_WORKTREE + "/debugging" not in prompt
    assert re.search(r"sink_resolution\.py\s+--print-location\s+telemetry", prompt), (
        f"the instruction must obtain the stream through the location query:\n{prompt}"
    )
