"""
MODULE: test_acd_2400_pt_store_worktree_anchor
GOAL: Behavioral test for ACD-2400 -- "Product-truth artifacts are written
    inside the authoring worktree, not the caller's checkout."

INCIDENT BEING REGRESSION-TESTED (KI-ACD-007,
    docs/known-issues/ac-driven-dev/open-high-ki-acd-007.md): the
    product-truth (PT) authoring dispatch in
    templates/workflows-js/plan-feature.js tells mock-data-author /
    mockup-author / flow-author to write into "the product-truth store at
    ${ptStoreDir}", where `ptStoreDir` was a bare relative literal
    (`const ptStoreDir = "docs/product-truth";`, :2693) -- NEVER reassigned to
    the absolute, worktree-anchored location the way the AC store's own
    `acStoreDir` is (overridden from `wtPayload.ac_store_path` at :2513). A
    dispatched PT authoring agent resolves that relative path against its OWN
    working directory -- normally the user's main checkout, NOT the dedicated
    authoring worktree /plan-feature just created -- so the artifact lands on
    `main` instead of the isolated branch.

WHY THIS TEST DRIVES BEHAVIOUR, NOT A GREP: CLAUDE.md's "Gate / Workflow ACs"
    rule requires proof that the workflow's own control flow actually consumes
    the anchored value, not merely that the string "docs/product-truth" or
    "worktree" appears somewhere in the source. This test drives the REAL
    plan-feature.js top-level body through the E2 stub harness
    (`run_workflow_under_e2`, which executes the actual JS in a sandboxed
    Node vm -- never a hand-typed stand-in), configures a `worktree-setup`
    response that names a specific authoring worktree path, and inspects the
    ACTUAL PROMPT TEXT the workflow's own code assembled for the
    `pt-mockdata-author` agent() dispatch. The assertion is on which path
    the running script decided to hand the authoring agent, exercised
    through the code's own control flow -- not on the literal text of
    plan-feature.js.

TDD note: at HEAD (before ACD-2400's fix), `ptStoreDir` is never reassigned,
    so the captured dispatch prompt names the bare relative
    "docs/product-truth" rather than a path anchored inside the fake
    authoring worktree this test configures. This test is RED until
    plan-feature.js anchors `ptStoreDir` to `authoringWorktreePath` (mirroring
    `acStoreDir`) -- verified empirically (2026-09-23, this worktree, HEAD)
    by running this file against the unmodified source before authoring the
    fix.

TICKET: none (ad-hoc fix task; KI-ACD-007). AC: ACD-2400.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/), mirroring the sys.path
# convention every sibling file in this directory already uses.
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"

_TIMEOUT = 30  # seconds; all agent() calls are synchronous mocks.

# A fake authoring worktree path this test controls -- deliberately NOT a
# real directory on disk. run_workflow_under_e2() executes the workflow body
# under a pure-mock agent() (no real shell exec), so plumbing this string
# through the script's own path-anchoring logic is all that is exercised;
# nothing ever needs to `test -d` it for real.
_FAKE_AUTHORING_WORKTREE = "/tmp/ki-acd-007-fake-authoring-worktree"


def _label_responses() -> dict:
    """Build the label_responses needed to reach the pt-mockdata-author
    dispatch: force a non-covered triage route, report a real authoring
    worktree from worktree-setup, and select the mock-data-only PT outcome
    so the run-set is exactly [mock-data-author].
    """
    return {
        "stage-0-triage": {
            "route": "strategic",
            "existing_acs": [],
            "parent_l1_id": None,
            "rationale": "test fixture — route straight past the covered-route gate",
        },
        # KI-ACD-007's whole mechanism hinges on a real authoring worktree
        # having been created -- mirrors the real setup_ticket_worktree.py
        # create-ac-worktree JSON payload shape (worktree_path, ac_store_path).
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
        "pt-store-check": {"output": "present", "exit_code": 0},
    }


def _pt_mockdata_author_prompt(result) -> str:
    calls = [c for c in result.agent_calls if c.label == "pt-mockdata-author"]
    assert calls, (
        "No 'pt-mockdata-author' agent() dispatch was captured -- the PT phase "
        f"never reached the mock-data authoring step. All captured labels: "
        f"{[c.label for c in result.agent_calls]}"
    )
    prompt = calls[0].prompt
    assert isinstance(prompt, str), f"Expected a string prompt, got: {prompt!r}"
    return prompt


def test_pt_authoring_dispatch_is_anchored_to_the_authoring_worktree():
    # covers: ACD-2400
    """AC-1 (ACD-2400): when a dedicated authoring worktree exists for this
    run, the product-truth authoring dispatch names a store path anchored
    INSIDE that worktree -- never the bare relative "docs/product-truth"
    literal, which resolves against the dispatched agent's own checkout
    (the defect KI-ACD-007 describes).
    """
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_label_responses(),
        args={"run_id": "test-acd-2400-anchor"},
    )
    assert result.error == "", f"Harness error: {result.error}"

    prompt = _pt_mockdata_author_prompt(result)

    assert _FAKE_AUTHORING_WORKTREE in prompt, (
        "The product-truth authoring dispatch does not name the authoring "
        f"worktree path ({_FAKE_AUTHORING_WORKTREE!r}) anywhere in its prompt "
        "-- the PT store path handed to mock-data-author is not anchored to "
        f"the dedicated authoring worktree. Full prompt:\n{prompt}"
    )
    assert "in the product-truth store at docs/product-truth" not in prompt, (
        "The dispatch prompt still hands the authoring agent the bare "
        "relative literal 'docs/product-truth', which resolves against the "
        "dispatched agent's own checkout rather than the authoring worktree "
        f"created for this run. Full prompt:\n{prompt}"
    )


def test_pt_authoring_dispatch_carries_an_explicit_anchor_warning():
    # covers: ACD-2400
    """AC-2 (ACD-2400): the PT dispatch prompt explicitly tells the authoring
    agent not to write relative to its own checkout -- the same anchor
    warning the AC-authoring dispatch prompt already carries
    ("Do NOT write AC files ... relative to the current checkout"). Without
    an equivalent warning, an agent that ignores (or never receives) the
    absolute path can silently fall back to a relative resolution.
    """
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_label_responses(),
        args={"run_id": "test-acd-2400-warning"},
    )
    assert result.error == "", f"Harness error: {result.error}"

    prompt = _pt_mockdata_author_prompt(result)

    assert "relative to the current checkout" in prompt, (
        "The product-truth dispatch prompt carries no explicit warning against "
        "writing relative to the current checkout, unlike the AC-authoring "
        f"dispatch's equivalent warning. Full prompt:\n{prompt}"
    )



# BO-1500a-5-i (origin/main, merged into this branch after ACD-2400's fix) hardened
# the worktree-setup gate in templates/workflows-js/plan-feature.js
# (buildSetupFailureResult() and its two call sites, ~:2519-2572) to HALT before
# Stage 0 -- before ac-triage, before the covered-route gate, before the PT phase --
# on EVERY reply shape that would otherwise leave `authoringWorktreePath` null. The
# comment there states the invariant outright: "authoringWorktreePath must NEVER stay
# null past this point." That makes AC-3's old negative form (a no-worktree run still
# reaching the PT authoring dispatch with the bare relative default) describe a state
# that can no longer occur -- see ACD-2400.yaml's amended_by entry. The five shapes
# enumerated below are exactly the ones buildSetupFailureResult()'s two call sites
# cover: an uninterpretable reply, a refusal, a non-zero exit code, a success-shaped
# reply naming no directory, and a no-failure-reported reply naming neither directory
# nor branch.
_UNREACHABLE_WORKTREE_SETUP_SHAPES = {
    # wtParsed === null (raw reply is a plain string with no parseable JSON at all,
    # and carries none of isAgentRefusal()'s AGENT_REFUSAL_MARKERS) -> "uninterpretable".
    "uninterpretable": "The setup step could not determine what to do with this request.",
    # wtParsed === null AND the free text matches an AGENT_REFUSAL_MARKERS phrase
    # ("outside my scope") -> "refused".
    "refused": "I'm sorry, but creating a worktree is outside my scope of responsibility.",
    # wtParsed is a real object with an explicit non-zero exit_code -> fails hard
    # before the no-worktree-path check is even reached.
    "non_zero_exit": {"output": "", "exit_code": 1, "stderr": "fatal: unable to create worktree"},
    # wtParsed.output parses to a real JSON object with an explicit exit_code but no
    # worktree_path -> "no_workspace_named".
    "success_no_directory": {
        "output": json.dumps({"ac_store_path": "docs/acceptance-criteria"}),
        "exit_code": 0,
    },
    # wtParsed.output parses to `{}` -- no worktree_path AND no exit_code at all,
    # i.e. no failure reported either -> "silent_success".
    "no_failure_no_directory": {"output": json.dumps({}), "exit_code": None},
}


def test_pt_phase_is_unreachable_without_an_authoring_worktree():
    # covers: ACD-2400
    """AC-3 (ACD-2400), amended: the PT authoring dispatch (pt-mockdata-author) is
    NEVER reached on any of the five worktree-setup reply shapes BO-1500a-5-i's gate
    treats as a failed setup -- because that gate halts the entire run (status:
    "error", a `setup_failure_kind`) before Stage 0's ac-triage dispatch, and the PT
    phase runs strictly after Stage 0 in the script's own top-to-bottom control flow.
    run_workflow_under_e2() always executes the FULL top-level body (there is no
    separate resume entry point that starts partway through), so this is true on
    every invocation, not just a first run -- proving there is no reachable route
    that hands the PT authoring dispatch an unanchored (or any) store path when no
    authoring worktree exists for the run.
    """
    for shape_name, wt_response in _UNREACHABLE_WORKTREE_SETUP_SHAPES.items():
        label_responses = _label_responses()
        label_responses["worktree-setup"] = wt_response

        result = run_workflow_under_e2(
            _PLAN_FEATURE_JS,
            timeout=_TIMEOUT,
            label_responses=label_responses,
            args={"run_id": f"test-acd-2400-unreachable-{shape_name}"},
        )
        assert result.error == "", f"[{shape_name}] Harness error: {result.error}"

        captured_labels = [c.label for c in result.agent_calls]
        assert "pt-mockdata-author" not in captured_labels, (
            f"[{shape_name}] The PT phase's pt-mockdata-author dispatch was reached "
            "despite no usable authoring worktree being reported for this run -- "
            "BO-1500a-5-i's worktree-setup gate should have halted before Stage 0. "
            f"Captured labels: {captured_labels}"
        )
        assert isinstance(result.result, dict) and result.result.get("status") == "error", (
            f"[{shape_name}] Expected the worktree-setup gate to halt the run with "
            f"status: 'error'. Got: {result.result!r}"
        )
