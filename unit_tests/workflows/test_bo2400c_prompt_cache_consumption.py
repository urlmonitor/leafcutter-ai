"""
MODULE: test_bo2400c_prompt_cache_consumption
GOAL: Consumption half of the fast-lane prompt-caching wiring tests
    (BO-2400c-1-iii and BO-2400c-1-iv), split out of
    test_bo2400c_prompt_cache_wiring.py to keep both files under the
    file-size ratchet. The reachability half (BO-2400c-1-ii, the
    ``assemble-bundle`` command) stays in that sibling file; see its module
    docstring for the full narrative, the assumed implementation contracts,
    and the verify-behaviorally-not-by-grep discipline that applies here too.

ACs covered:
  - BO-2400c-1-iii — the prompt a dispatched test-writer/coder agent receives
    IS the assembled bundle, verbatim (KI-BO-006).
  - BO-2400c-1-iv  — across one run's successive context-carrying dispatches,
    the cacheable prefix is byte-identical and the volatile suffix differs.

Every test EXECUTES the real, on-disk fast-lane-ship.js under
unit_tests/_workflow_engine_harness.py's run_workflow_under_e2() and asserts
on the RECORDED, EXECUTED agent_calls' prompts and the executed call order —
never on fast-lane-ship.js source text.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — make scripts/ and unit_tests/ importable regardless of cwd.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from injection_builders import assemble_context_bundle  # noqa: E402 — after sys.path setup
from _workflow_engine_harness import HarnessResult, resolve_connected_reply, run_workflow_under_e2, workspace_answer_of, workspace_ensure_from_opened  # noqa: E402

import workflows._fast_lane_claim_fixtures as _claim_fx  # noqa: E402

_FAST_LANE_SHIP_JS = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"

_DEFAULT_MARKER = "<!-- CACHE_BREAKPOINT -->"


# ===========================================================================
# BO-2400c-1-iii / BO-2400c-1-iv — consumption: the dispatched prompt IS the
# bundle, and the cacheable prefix is byte-identical across dispatches
# ===========================================================================

_TIMEOUT = 30  # seconds; Node subprocess spawn per harness run

# ASSUMED label for the not-yet-existing bundle-assembling dispatch in
# fast-lane-ship.js (see "Assumed implementation contracts" in the module
# docstring).
_BUNDLE_LABEL = "fastlane-context-bundle"

_STABLE_ARCH = "STABLE_ARCH_TEXT_FOR_BO2400C_III_IV"
_STABLE_HL = "STABLE_HL_TEXT_FOR_BO2400C_III_IV"
_VOLATILE_PRIOR_TESTS = "VOLATILE_PRIOR_TESTS_TEXT_FOR_BO2400C_III_IV"

# _STABLE_CONV and _VOLATILE_ACS are gone (BO-2400c-1-vi): the conventions
# and acs layers no longer exist as parameters or as bundle content.

# A real bundle produced the same way assemble_context_bundle() would produce
# it (fixture-authenticity: constructed via the actual pure function, not a
# hand-typed re-implementation of its ordering rule).
#
# BO-2400c-1-vi call-site audit: this is a MODULE-SCOPE call, so dropping
# conventions=/acs= here (to match the post-change three-layer signature)
# makes the entire file fail at pytest COLLECTION — not at assertion —
# against today's unmodified assemble_context_bundle(), which still requires
# both as keyword-only arguments with no default. That collection failure IS
# this file's red baseline for the call-site audit until BO-2400c-1-vi lands
# (see the module docstring's "call-site audit" section).
_KNOWN_BUNDLE = assemble_context_bundle(
    architecture=f"## Architecture\n{_STABLE_ARCH}",
    high_level=f"## L1 AC\n{_STABLE_HL}",
    prior_tests=f"## Prior Tests\n{_VOLATILE_PRIOR_TESTS}",
)

_BUNDLE_OK_RESPONSE = {
    "bundle": _KNOWN_BUNDLE,
    "obtained": True,
    "message": "bundle assembled",
}

# Green baseline label_responses — enough to drive fast-lane-ship.js's
# CURRENT (already-landed BO-2400f) phase order all the way to the Pull
# Request phase. Every key matches a label already present in
# fast-lane-ship.js's existing agent() dispatches.
_GREEN_LABELS: dict = {
    "workspace-ensure": workspace_ensure_from_opened({
        "worktree_path": "/tmp/fastlane-wt-bo2400c",
        "branch": "fast-lane/bo-stub-1",
        "ac_store_path": "/tmp/fastlane-wt-bo2400c/docs/acceptance-criteria",
        "created": True,
    }),
    "resolve-connected": resolve_connected_reply({
        "ac_ids": ["BO-STUB-1"],
        "message": "1 to build",
    }),
    "claim-connected": _claim_fx.claim_ran(["BO-STUB-1"]),
    "test-writer-connected": {
        "status": "ok",
        "tests_written": ["unit_tests/test_stub.py"],
        "gate_passed": True,
        "reason": None,
        "green_at_baseline": [],
        "message": "red baseline ok",
    },
    "coder-connected": {
        "status": "ok",
        "files_modified": ["scripts/stub_impl.py"],
        "green": True,
        "coverage_ok": True,
        "uncovered_ac_ids": [],
        "message": "implementation green",
    },
    "fastlane-review": {
        "verdict_obtained": True,
        "high_findings": [],
        "medium_findings": [],
        "low_suppressed_count": 0,
        "message": "clean review",
    },
    "fastlane-changelog": {
        "status": "ok",
        "entry_added": True,
        "entry_path": "changelogs/2026-08-18-0000-stub-entry.md",
        "message": "entry emitted",
    },
    "fastlane-commit": {
        "status": "ok",
        "branch": "fast-lane/bo-stub-1",
        "message": "committed",
    },
    "fastlane-pr": {
        "status": "ok",
        "pr_url": "https://github.com/example/repo/pull/1",
        "message": "PR opened",
    },
}


def _run_ship(bundle_response=_BUNDLE_OK_RESPONSE, extra_labels: dict | None = None,
              args: dict | None = None) -> HarnessResult:
    """Run the REAL fast-lane-ship.js under the E2 harness with the green
    baseline plus a stubbed bundle-assembling dispatch response.
    """
    labels = dict(_GREEN_LABELS)
    if extra_labels:
        labels.update(extra_labels)
    labels[_BUNDLE_LABEL] = bundle_response
    return run_workflow_under_e2(
        _FAST_LANE_SHIP_JS,
        timeout=_TIMEOUT,
        label_responses=labels,
        args=args or {"ac": "BO-STUB-1"},
    )


def _labels_ship(result: HarnessResult) -> list:
    return [c.label for c in result.agent_calls]


def _call(result: HarnessResult, label: str):
    return next((c for c in result.agent_calls if c.label == label), None)


# --- BO-2400c-1-iii ---------------------------------------------------------


def test_ac3iii_dispatched_agent_prompt_is_the_assembled_bundle():
    # covers: BO-2400c-1-iii
    """With the bundle-assembling dispatch stubbed to return a known bundle,
    the recorded test-writer and coder calls carry that bundle text in their
    prompts.

    RED today (KI-BO-006): fast-lane-ship.js never mentions the layer at
    all — the test-writer and coder prompts are custom prose that does not
    contain the bundle string.
    """
    result = _run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    tw_call = _call(result, "test-writer-connected")
    coder_call = _call(result, "coder-connected")
    assert tw_call is not None, (
        f"Expected the test-writer dispatch to execute. Labels: {_labels_ship(result)}"
    )
    assert coder_call is not None, (
        f"Expected the coder dispatch to execute. Labels: {_labels_ship(result)}"
    )

    for call, name in ((tw_call, "test-writer"), (coder_call, "coder")):
        prompt = call.prompt
        assert isinstance(prompt, str), f"{name} prompt must be a string. Got: {type(prompt)}"
        assert _KNOWN_BUNDLE in prompt, (
            f"The assembled bundle must reach the {name} dispatch verbatim as "
            f"prompt context. Bundle not found in prompt. "
            f"Prompt (first 400 chars): {prompt[:400]!r}"
        )


def test_ac3iii_bundle_reaches_the_agent_verbatim_no_rewrap():
    # covers: BO-2400c-1-iii
    """The stubbed bundle text appears in the recorded prompt unaltered —
    same bytes, same order, no re-wrapping, appearing exactly once (not
    duplicated or fragmented).

    RED today: the bundle string does not appear in the coder prompt at all.
    """
    result = _run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    coder_call = _call(result, "coder-connected")
    assert coder_call is not None, f"Expected coder dispatch. Labels: {_labels_ship(result)}"
    prompt = coder_call.prompt
    assert isinstance(prompt, str), f"coder prompt must be a string. Got: {type(prompt)}"

    assert prompt.count(_KNOWN_BUNDLE) == 1, (
        "The bundle must appear exactly once, as one contiguous, unaltered "
        f"substring — no re-wrapping, no interpolation inside it, no "
        f"duplication. Found {prompt.count(_KNOWN_BUNDLE)} occurrence(s). "
        f"Prompt (first 400 chars): {prompt[:400]!r}"
    )
    start = prompt.index(_KNOWN_BUNDLE)
    assert prompt[start:start + len(_KNOWN_BUNDLE)] == _KNOWN_BUNDLE, (
        "The bundle substring must be byte-for-byte identical to what the "
        "assembling command returned — no trimming, no re-wrapping."
    )


def test_ac3iii_bundle_assembly_dispatch_precedes_context_carrying_dispatches():
    # covers: BO-2400c-1-iii
    """In a fully green harness run, the bundle-assembling dispatch is
    EXECUTED before the test-writer and coder dispatches — asserted on
    executed call order, not source text.

    RED today: the bundle-assembling dispatch (label
    'fastlane-context-bundle') never executes at all, because
    fast-lane-ship.js never mentions the prompt-caching layer.
    """
    result = _run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    labels = _labels_ship(result)
    assert _BUNDLE_LABEL in labels, (
        f"Expected the bundle-assembling dispatch (label={_BUNDLE_LABEL!r}) "
        f"to actually execute. Got labels: {labels}"
    )
    assert "test-writer-connected" in labels and "coder-connected" in labels, (
        f"Expected both context-carrying dispatches to execute. Got: {labels}"
    )

    bundle_idx = labels.index(_BUNDLE_LABEL)
    tw_idx = labels.index("test-writer-connected")
    coder_idx = labels.index("coder-connected")
    assert bundle_idx < tw_idx, (
        f"Bundle dispatch must precede test-writer dispatch. Order: {labels}"
    )
    assert bundle_idx < coder_idx, (
        f"Bundle dispatch must precede coder dispatch. Order: {labels}"
    )


def test_ac3iii_unobtainable_bundle_halts_instead_of_dispatching_unbundled_prompts():
    # covers: BO-2400c-1-iii
    """With the assembling dispatch stubbed to return a failure, an empty
    payload, or nothing readable, the run records no test-writer or coder
    dispatch, and its terminal payload names the context bundle as the
    reason.

    RED today: fast-lane-ship.js never consults any bundle-assembling
    dispatch, so it sails straight through to test-writer/coder regardless
    of what this stub returns.
    """
    unusable_variants = [
        {"bundle": "", "obtained": False, "message": "assembling command failed"},
        {},
        None,
    ]
    for variant in unusable_variants:
        result = _run_ship(bundle_response=variant)
        assert result.error == "", f"Harness error for variant {variant!r}: {result.error}"

        labels = _labels_ship(result)
        assert "test-writer-connected" not in labels, (
            f"An unobtainable bundle ({variant!r}) must not permit an "
            f"unbundled test-writer dispatch. Labels: {labels}"
        )
        assert "coder-connected" not in labels, (
            f"An unobtainable bundle ({variant!r}) must not permit an "
            f"unbundled coder dispatch. Labels: {labels}"
        )

        payload = result.result
        assert payload is not None, (
            f"Missing terminal payload for variant {variant!r}. Labels: {labels}"
        )
        message_blob = json.dumps(payload).lower()
        assert "bundle" in message_blob, (
            f"The terminal payload must name the context bundle as the "
            f"reason the run halted before dispatching context-carrying "
            f"agents. Got: {payload}"
        )
        assert payload.get("status") not in ("ok",), (
            f"An unobtainable bundle must never be reported as a successful "
            f"run. Got: {payload}"
        )


def test_ac3iii_breakpoint_marker_present_exactly_once_in_dispatched_prompt():
    # covers: BO-2400c-1-iii
    """Each recorded context-carrying prompt contains exactly one cache
    breakpoint marker, with the stable layers before it and this run's
    volatile content after it.

    RED today: the marker never appears in either prompt at all.
    """
    result = _run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    for label in ("test-writer-connected", "coder-connected"):
        call = _call(result, label)
        assert call is not None, f"Expected {label} dispatch. Labels: {_labels_ship(result)}"
        prompt = call.prompt
        assert isinstance(prompt, str), f"{label} prompt must be a string."

        count = prompt.count(_DEFAULT_MARKER)
        assert count == 1, (
            f"{label} prompt must contain the cache breakpoint marker "
            f"exactly once. Found {count}. Prompt (first 400 chars): {prompt[:400]!r}"
        )
        marker_idx = prompt.index(_DEFAULT_MARKER)
        assert _STABLE_ARCH in prompt[:marker_idx], (
            f"{label}: stable layer content must appear before the "
            f"breakpoint marker."
        )
        assert _VOLATILE_PRIOR_TESTS in prompt[marker_idx:], (
            f"{label}: volatile layer content must appear after the "
            f"breakpoint marker."
        )


# --- BO-2400c-1-iv -----------------------------------------------------------


def _stable_prefix(prompt: str, marker: str) -> str:
    """Return the portion of *prompt* up to and including *marker*.

    If the marker is absent, the entire prompt counts as "prefix" — there is
    no partition into stable/volatile yet, so any run-varying content in the
    prompt correctly counts as a violation of "nothing run-varying appears
    before the breakpoint."
    """
    idx = prompt.find(marker)
    if idx == -1:
        return prompt
    return prompt[: idx + len(marker)]


def _volatile_suffix(prompt: str, marker: str) -> str:
    """Return the portion of *prompt* strictly after *marker* (empty if absent)."""
    idx = prompt.find(marker)
    if idx == -1:
        return ""
    return prompt[idx + len(marker):]


def test_ac4iv_stable_prefix_identical_across_successive_dispatches():
    # covers: BO-2400c-1-iv
    """In an executed harness run, the region up to and including the
    breakpoint marker is byte-equal across every recorded context-carrying
    prompt.

    RED today: fast-lane-ship.js never inserts the assembled bundle into
    either prompt, so the two phase-specific prompt bodies differ entirely
    and their "prefixes" (the whole prompt, absent any marker) are unequal.
    """
    result = _run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    tw_call = _call(result, "test-writer-connected")
    coder_call = _call(result, "coder-connected")
    assert tw_call is not None and coder_call is not None, (
        f"Expected both dispatches to execute. Labels: {_labels_ship(result)}"
    )

    prefix_tw = _stable_prefix(tw_call.prompt, _DEFAULT_MARKER)
    prefix_coder = _stable_prefix(coder_call.prompt, _DEFAULT_MARKER)
    assert prefix_tw == prefix_coder, (
        "The portion of each dispatched prompt up to and including the cache "
        "breakpoint must be byte-identical across the test-writer and coder "
        "dispatches.\n"
        f"test-writer prefix (first 200 chars): {prefix_tw[:200]!r}\n"
        f"coder prefix (first 200 chars): {prefix_coder[:200]!r}"
    )


def test_ac4iv_volatile_suffix_differs_across_successive_dispatches():
    # covers: BO-2400c-1-iv
    """The regions after the breakpoint marker are not all equal, so the
    prefix equality cannot be satisfied by sending every agent the same
    prompt.

    RED today: since the breakpoint marker is absent from both prompts, the
    helper treats both suffixes as empty strings — which are (wrongly) equal,
    so this assertion correctly fails.
    """
    result = _run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    tw_call = _call(result, "test-writer-connected")
    coder_call = _call(result, "coder-connected")
    assert tw_call is not None and coder_call is not None, (
        f"Expected both dispatches to execute. Labels: {_labels_ship(result)}"
    )

    suffix_tw = _volatile_suffix(tw_call.prompt, _DEFAULT_MARKER)
    suffix_coder = _volatile_suffix(coder_call.prompt, _DEFAULT_MARKER)
    assert suffix_tw != suffix_coder, (
        "The per-phase content after the breakpoint must genuinely differ "
        "between dispatches — otherwise the prefix-equality guarantee could "
        "be satisfied trivially by sending every agent an identical prompt, "
        "which would destroy the per-phase context the lane depends on.\n"
        f"test-writer suffix: {suffix_tw!r}\ncoder suffix: {suffix_coder!r}"
    )


def test_ac4iv_run_varying_values_do_not_appear_before_the_breakpoint():
    # covers: BO-2400c-1-iv
    """The worktree path, branch name, and target AC id supplied to the
    executed run appear only after the breakpoint marker in the recorded
    prompts, never in the prefix.

    RED today: there is no breakpoint marker in the dispatched prompt at
    all, so the entire prompt — which DOES contain the worktree path and
    branch — counts as the prefix.
    """
    result = _run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    answer = workspace_answer_of(_GREEN_LABELS["workspace-ensure"])
    worktree_path, branch = answer["workspace_path"], answer["branch"]
    target_ac = "BO-STUB-1"

    for label in ("test-writer-connected", "coder-connected"):
        call = _call(result, label)
        assert call is not None, f"Expected {label} dispatch. Labels: {_labels_ship(result)}"
        prefix = _stable_prefix(call.prompt, _DEFAULT_MARKER)

        for run_varying, name in (
            (worktree_path, "worktree_path"),
            (branch, "branch"),
            (target_ac, "target_ac"),
        ):
            assert run_varying not in prefix, (
                f"{label}: run-varying value {name}={run_varying!r} must "
                f"never appear in the stable prefix (everything up to and "
                f"including the breakpoint) — a prefix carrying it would "
                f"yield a cold cache on every single run.\n"
                f"prefix (first 400 chars): {prefix[:400]!r}"
            )


def test_ac4iv_prefix_drift_between_dispatches_is_surfaced():
    # covers: BO-2400c-1-iv
    """Drift is reported rather than tolerated: the bundle-assembling
    dispatch must be obtained exactly ONCE per run and its stable region
    reused verbatim by every later context-carrying dispatch. Re-obtaining
    or re-assembling it per phase is precisely how prefix drift enters (a
    stable source re-read and re-rendered mid-run, BO-2400c-1-iv's own named
    cause) — enforcing single-dispatch is what prevents it from ever being
    observable in the first place.

    RED today: the bundle-assembling dispatch does not exist at all, so it
    is dispatched zero times, not exactly once.
    """
    result = _run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    labels = _labels_ship(result)
    bundle_dispatch_count = labels.count(_BUNDLE_LABEL)
    assert bundle_dispatch_count == 1, (
        "The bundle-assembling dispatch must be obtained exactly ONCE per "
        f"run. Got {bundle_dispatch_count} dispatch(es) with label "
        f"{_BUNDLE_LABEL!r}. Full label order: {labels}"
    )
