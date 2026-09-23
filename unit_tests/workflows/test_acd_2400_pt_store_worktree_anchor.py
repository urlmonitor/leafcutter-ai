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


def test_pt_store_path_without_a_worktree_stays_the_plain_relative_default():
    # covers: ACD-2400
    """AC-3 (ACD-2400), negative form: when NO authoring worktree is reported
    (worktree-setup produces no usable payload), the PT store path falls back
    to the plain relative "docs/product-truth" default, unchanged from
    today's behaviour -- this fix must not invent a spurious anchor when
    there is nothing to anchor to.
    """
    label_responses = _label_responses()
    # Force the worktree-setup step to report no usable payload (unparseable
    # output), so wtPayload stays null and authoringWorktreePath stays null,
    # exactly like a worktree-setup dispatch failure today.
    label_responses["worktree-setup"] = {"output": "not json", "exit_code": 0}

    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=label_responses,
        args={"run_id": "test-acd-2400-no-worktree"},
    )
    assert result.error == "", f"Harness error: {result.error}"

    prompt = _pt_mockdata_author_prompt(result)

    assert _FAKE_AUTHORING_WORKTREE not in prompt, (
        "No authoring worktree was reported for this run, yet the dispatch "
        f"prompt names one anyway. Full prompt:\n{prompt}"
    )
    assert "docs/product-truth" in prompt, (
        "With no authoring worktree, the PT store path must still fall back "
        f"to the plain relative default. Full prompt:\n{prompt}"
    )
