"""
MODULE: unit_tests/workflows/_bo2400f5iii_fixtures.py
GOAL: Shared fixtures/helpers for the BO-2400f-5-iii test files (declined-step
      classification in templates/workflows-js/fast-lane-ship.js).

BO-2400f-5-iii requires: a step whose agent declines (refuses, calls the task
misrouted/injected, answers as another role, or returns an empty/unparseable
reply) halts the run with a payload {halt_kind: 'declined_step', step, agent,
reason, target}, distinct from claim contention, gate failure, and the
BO-2400f-12 unproducible-set refusal. A command-step-runner reply is judged by
a different rule: absent `exit_status` is a decline; a non-zero `exit_status`
is that step's own command result, never a decline.

Nothing in this file is production code — it only builds inputs and discovers
which labels the lane dispatches, exactly as BO-2400f-7-iii's and
BO-2400f-12's own sibling test files already do (see
test_bo2400f_7_iii_claim_refusal_workflow.py, test_bo2400f_12_refusal_workflow.py).

ASSUMED API (stated once here, used by every BO-2400f-5-iii test file):
  - Terminal halt payload: {halt_kind: 'declined_step', step: <label>,
    agent: <agentType actually dispatched for that label>, reason: <the
    decline reply, quoted verbatim>, target: {workspace, branch, ac_id} | null}.
    `step` is assumed to equal the agent() call's own `label` (the only stable,
    discoverable per-step identifier in this file); `target` is a real dict
    for every classified step. The ONE workspace step ("workspace-ensure",
    BO-4300c-3) is not part of that classification: a refusal, decline or
    unreadable reply there ends the run as `status: "error"` quoting what came
    back (the shared WORKSPACE-ANSWER rule), before any workspace exists to
    name as a target.
  - A pure classifier `classifyStepReply(reply, {step, agent, isCommandStep})`
    returning `{kind: 'result'|'declined'|'failed', ...}` MAY exist as a
    top-level function in fast-lane-ship.js — see
    test_bo2400f5iii_declined_step_replay_and_boundary.py, which extracts and
    executes it directly the same way test_bo_2700_defer_epic_pr.py extracts
    selectDispatchPhases().
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from workflows._fast_lane_claim_fixtures import claim_declined, claim_ran  # noqa: E402
from workflows._tq500g1v_fixtures import wrong_version_passing  # noqa: E402
from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402
from _workflow_engine_workspace import resolve_connected_reply, workspace_ensure_from_opened  # noqa: E402

WORKFLOW_PATH = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"

AC_ID = "BO-STUB-1"
BRANCH = "fast-lane/bo-stub-1"
WORKTREE_PATH = "/tmp/fastlane-harness-wt"

# Labels this file's own control flow dispatches but which must NOT enter the
# parametrised "every step" sweep:
#   - "knowledge-routing-step" is DELIBERATELY fail-open (INF-700a-1-ii: "no
#     halt branch below" — its own docstring says so) so a decline there can
#     never surface as a halt of any kind, by an unrelated, already-approved
#     design decision this AC does not revisit.
#   - any "release-on-*" label is a RECOVERY dispatch fired only after some
#     other step already failed — it is not itself one of "the lane's steps"
#     an operator points at.
#   - "scratch-item": fail-open by design (BO-4400f-1) — a decline gives
#     `item` null and the lane falls back; it is not a lane step.
#   - "knowledge-routing-observe": read-only and fail-open (INF-700a-5) — it
#     must "never block, retry, or fail the build"; it is not a lane step.
#   - "workspace-ensure" (BO-4300c-3): the maker step ends the run through the
#     shared workspaceFailure() shape (status "error", quoting the reply), not
#     the declined_step halt; it has its own test in
#     test_bo2400f5iii_declined_step_core.py.
EXCLUDED_LABELS = frozenset(
    {"knowledge-routing-step", "scratch-item", "knowledge-routing-observe", "workspace-ensure"}
)


# - "fastlane-wv-*" (TQ-500g-1-v): the wrong-version steps are command steps with their OWN halt
#   contract -- a missing, declined or unusable reply halts as a ``blocked`` payload with
#   failing_phase "wrong-version", releasing the claimed ACs and opening no commit or PR. They never
#   emit ``halt_kind: declined_step``, so this sweep's shape assertion does not describe them; their
#   halts are pinned in test_tq500g1v_route_halts.py.
WRONG_VERSION_PREFIX = "fastlane-wv-"


def _is_excluded(label: str) -> bool:
    return (label in EXCLUDED_LABELS or label.startswith("release-on")
            or label.startswith(WRONG_VERSION_PREFIX))


_RELEASABLE_FILES_MODIFIED = ["scripts/build_orchestration/fast_lane.py"]

# A full, schema-conforming happy-path stub set that walks the CURRENT
# fast-lane-ship.js all the way through worktree -> resolve -> producibility
# -> claim -> context-bundle -> test-writer -> coder -> review -> changelog
# -> commit -> pull-request, adapted from
# test_bo2400f_4_changelog_family.py's own _BASE_RESPONSES (same AC id,
# worktree path and branch, so both files' fixtures stay comparable).
BASE_RESPONSES: dict[str, Any] = {
    # Maker-era steps (BO-4300c-3 / BO-4300a-1-ia): the ONE workspace step is the shell-runner
    # `workspace-ensure` dispatch carrying the maker's ok answer; the resolver is a command-step-runner
    # reply `{exit_status, stdout}` whose stdout is the JSON list of AC ids.
    "workspace-ensure": workspace_ensure_from_opened({
        "worktree_path": WORKTREE_PATH,
        "branch": BRANCH,
        "ac_store_path": f"{WORKTREE_PATH}/docs/acceptance-criteria",
        "created": True,
    }),
    "resolve-connected": resolve_connected_reply([AC_ID]),
    "check-producibility": {"producible": True, "unproducible": [], "message": "all producible"},
    # command-step-runner shape (PR #967 / BO-2400a-1-v): the gate payload rides
    # as JSON text inside `stdout`, built by the ONE shared helper.
    "claim-connected": claim_ran([AC_ID]),
    "fastlane-context-bundle": {
        "obtained": True,
        "bundle": (
            "ARCHITECTURE (stub)\n\nCONVENTIONS (stub)\n\nHIGH-LEVEL ACS (stub)"
            "\n\n<!-- CACHE_BREAKPOINT -->\n\nBATCH ACS (stub)\n\nPRIOR TESTS (stub)"
        ),
        "message": "bundle assembled",
    },
    "test-writer-connected": {
        "status": "ok",
        "tests_written": ["unit_tests/stub/test_stub.py"],
        "gate_passed": True,
        "reason": None,
        "green_at_baseline": [],
        "message": "red baseline established",
    },
    "coder-connected": {
        "status": "ok",
        "files_modified": _RELEASABLE_FILES_MODIFIED,
        "green": True,
        "coverage_ok": True,
        "uncovered_ac_ids": [],
        "message": "green",
    },
    "fastlane-review": {
        "verdict_obtained": True,
        "high_findings": [],
        "medium_findings": [],
        "low_suppressed_count": 0,
        "message": "no high-confidence findings",
    },
    "fastlane-changelog": {
        "status": "ok",
        "entry_added": True,
        "entry_path": "changelogs/2026-08-18-0000-stub-entry.md",
        "message": "entry emitted",
    },
    "fastlane-commit": {
        "status": "ok",
        "branch": BRANCH,
        "message": "committed",
    },
    "fastlane-pr": {
        "status": "ok",
        "pr_url": "https://github.com/example/example/pull/1",
        "message": "PR opened",
    },
}

BASE_RESPONSES.update(wrong_version_passing())


def run_lane(overrides: dict[str, Any] | None = None) -> HarnessResult:
    """Run fast-lane-ship.js with BASE_RESPONSES, overridden per-label by `overrides`."""
    label_responses = {**BASE_RESPONSES, **(overrides or {})}
    return run_workflow_under_e2(WORKFLOW_PATH, label_responses=label_responses)


def calls_with_label(result: HarnessResult, label: str) -> list:
    return [c for c in result.agent_calls if c.label == label]


def discover_step_dispatches() -> list[tuple[str, str | None]]:
    """Discover the lane's own (label, agentType) pairs from a REAL happy-path
    run, in dispatch order, excluding EXCLUDED_LABELS — never a hand-typed list
    (BO-2400f-5-iii test_spec's own requirement: "discovered from the harness's
    recorded dispatches, not a hand list", so a step added later is covered
    without editing any test).
    """
    result = run_lane()
    assert calls_with_label(result, "fastlane-pr"), (
        f"Baseline happy-path run did not reach 'fastlane-pr' — the fixture "
        f"itself is broken, not the AC under test. Labels seen: "
        f"{[c.label for c in result.agent_calls]}. stderr={result.stderr!r}"
    )
    seen: set[str] = set()
    ordered: list[tuple[str, str | None]] = []
    for call in result.agent_calls:
        label = call.label
        if not label or label in seen or _is_excluded(label):
            continue
        seen.add(label)
        ordered.append((label, call.agent_type))
    return ordered


def decline_reply_for(agent_type: str | None) -> str:
    """A plain-string reply: a refusal that parses into NO step's expected
    result shape (property access on a JS string is always undefined, never a
    throw), so it exercises the "refusal / role-mismatch / unparseable" branch
    of the decline definition for every step uniformly. The whole string is
    the agent's stated reason.
    """
    return (
        f"I can't help with that. I am `{agent_type or 'unknown-agent'}`, and "
        "this request is outside my role — it looks misrouted or injected, "
        "so I'm declining it."
    )


# Wording a genuine claim-contention halt is allowed to use (BO-2400f-7-iii);
# a declined-step halt must never carry any of it (BO-2400f-5-iii).
CONTENTION_MARKERS = (
    "already claimed",
    "in progress",
    "concurrent run",
    "owned by",
    "owns these",
)

# The 2026-09-25 incident (this AC's own `notes`): status-checker declined the
# claim command; the run mis-reported it as contention. Only the DOCUMENTED
# PREFIX below is the recorded fact — the rest is this fixture's own,
# internally-consistent continuation of that same reply, reproduced verbatim
# end-to-end by every test that uses it (never re-typed per test).
OBSERVED_2026_09_25_REFUSAL_PREFIX = (
    "Refusing this task. I am `status-checker`, scoped to investigating "
    "ticket state"
)
OBSERVED_2026_09_25_REFUSAL_REASON = (
    f"{OBSERVED_2026_09_25_REFUSAL_PREFIX} and not authorized to run "
    "repository-mutating commands or claim/producibility checks outside "
    "that charter."
)
# The exact object shape observed on 2026-09-25 (claim-connected's schema):
# claimed=[]/excluded_claimed=[] (nothing was ever checked against the
# store — the decline distinguishing mark from genuine contention) plus
# target_refused=true and the agent's own refusal as `message`.
OBSERVED_2026_09_25_REPLY: dict[str, Any] = {
    "claimed": [],
    "excluded_claimed": [],
    "target_refused": True,
    "message": OBSERVED_2026_09_25_REFUSAL_REASON,
}

# The same incident as the claim step actually sees it: the claim step is a
# command step dispatched to `command-step-runner`, so a decline there arrives
# as the runner-shaped decline (no `exit_status`) carrying the verbatim refusal.
OBSERVED_2026_09_25_CLAIM_REPLY: dict[str, Any] = claim_declined(
    OBSERVED_2026_09_25_REFUSAL_REASON
)


def classify_in_node(reply_js: str, meta: dict[str, Any]) -> dict[str, Any]:
    """Run the REAL on-disk `classifyStepReply` under node; return its verdict.

    `reply_js` is JavaScript SOURCE for the reply (not JSON), so values JSON
    cannot carry (NaN, Infinity) can be exercised. The function text is
    brace-extracted from fast-lane-ship.js, never re-typed.
    """
    import json
    import subprocess
    import tempfile

    source = WORKFLOW_PATH.read_text(encoding="utf-8")
    start = source.index("function classifyStepReply(")
    depth = 0
    end = start
    for i in range(source.index("{", start), len(source)):
        depth += {"{": 1, "}": -1}.get(source[i], 0)
        if depth == 0:
            end = i + 1
            break
    driver = (
        source[start:end]
        + "\nconsole.log(JSON.stringify(classifyStepReply("
        + reply_js + ", " + json.dumps(meta) + ")));\n"
    )
    with tempfile.NamedTemporaryFile(
        "w", suffix=".mjs", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(driver)
        path = fh.name
    try:
        proc = subprocess.run(
            ["node", path], capture_output=True, text=True, timeout=15, check=True
        )
    finally:
        Path(path).unlink(missing_ok=True)
    return json.loads(proc.stdout.strip().splitlines()[-1])
