"""
MODULE: unit_tests/workflows/test_bo2400f_4_changelog_family.py
GOAL: RED test stubs for the BO-2400f-4 changelog family (KI-BO-001): the fast
      lane commits and opens a PR but never writes a changelogs/ entry, so
      every PR it opens fails the required "Changelog entry present" CI check.
      PR #465 proved it live: 5/6 required checks green, changelog failing,
      mergeable_state blocked, fixed by hand in b3124ff25.

ACs covered (read from docs/acceptance-criteria/build-orchestration/
BO-2400-fast-lane-build/ — there is no ticket for this family; the AC YAML is
the spec):
    BO-2400f-4-i    — the "is an entry required" decision reuses the
                      changelog-presence gate's own rule (no duplicate list).
    BO-2400f-4-ii   — an exempt-only run writes no entry and still succeeds.
    BO-2400f-4-iii  — the run emits the entry itself, via the repo's emitter,
                      committed before the PR is opened.
    BO-2400f-4-iv   — the entry's breaking flag is always false, paired with
                      an unconditional "not determined, needs human review"
                      notice in the PR body; never inferred from AC metadata.
    BO-2400f-4-v    — a failed/absent entry HALTS the run (never a warning
                      alongside a reported success); no PR is opened.

=== Interface contract defined by these tests (no ticket exists to pin this,
so it is pinned here — python-coder must implement exactly this shape) ===

1) scripts/build_orchestration/fast_lane.py gains:

    compute_changelog_requirement(changed_paths: list[str]) -> dict
        Returns {"required": bool, "releasable_paths": list[str]}.
        MUST determine "required"/"releasable_paths" by calling into
        scripts/release/check_changelog_presence.py's own EXEMPT_PREFIXES /
        evaluate() — NEVER a second, hand-copied prefix tuple. Import the
        module (``import check_changelog_presence`` — do not
        ``from ... import EXEMPT_PREFIXES``, which freezes a private copy at
        import time and defeats the single-source property this AC exists to
        guarantee) and read ``check_changelog_presence.EXEMPT_PREFIXES`` at
        call time.

    build_changelog_payload(
        *, target_ac: str, built_ac_ids: list[str], files_modified: list[str],
        branch: str, ac_root: Path,
    ) -> dict
        Assembles the scripts/changelog/emit_entry.py payload from run state:
        title (from target_ac's own YAML "title" field), date, time,
        type="manual", components (union of built ACs' "components" lists),
        summary (business language), description (mentions every built AC id
        and every modified file), and breaking: ALWAYS False — a hardcoded
        default, never derived from any AC's risk_surface or other metadata
        (see BO-2400f-4-iv's rejected-design note: TKT-600a-1 is
        risk_surface=contract_boundary and genuinely non-breaking).

2) templates/workflows-js/fast-lane-ship.js gains a new phase dispatched
   between "Commit" and "Pull Request", ONLY when compute_changelog_requirement
   says required=True:

    agent(..., { agentType: ..., label: "fastlane-changelog", phase: "Changelog" })

   Response contract: {"status": "ok"|"error", "entry_added": bool,
   "entry_path": str|null, "message": str}. "entry_added" MUST be verified
   independently of the attempt's own report (a re-read of the delivered
   diff), per BO-2400f-4-v.

   - required=False (exempt-only change): the "fastlane-changelog" dispatch
     does not happen at all; the run proceeds straight to "fastlane-pr".
   - required=True and (status != "ok" OR entry_added is not true): the run
     HALTS — classification: halt, reason one of
     ["changelog_emit_failed", "changelog_entry_absent_from_change"] — and
     dispatches a "release-on-changelog-fail" call (mirroring the existing
     release-on-test-writer-fail / release-on-coder-fail / release-on-commit-fail
     pattern already in this file) BEFORE returning. "fastlane-pr" MUST NOT be
     dispatched on this path.
   - required=True and status=="ok" and entry_added is true: the run proceeds
     to "fastlane-pr" as today.

   The PR body (prBody, embedded in the "fastlane-pr" dispatch's prompt) MUST
   UNCONDITIONALLY (regardless of whether an entry was required/emitted) carry
   an explicit notice that the breaking flag was not determined by the run and
   must be confirmed by a human before merge.

=== Fixture-authenticity mandate ===

All AC YAML fixtures are written with yaml.safe_dump (not hand-typed YAML
literals), following the established pattern in test_fast_lane_connected.py /
test_fast_lane_cli.py.

=== Real-artifact behavioral mandate (BP-1100f-2) ===

BO-2400f-4-iii declares a durable, observable side effect: a changelog file
written to disk that becomes part of the PR's diff. This is a real
side-effect ticket even though it has no ticket file, so at least one test
here (test_ac_iii_run_emits_changelog_entry_via_real_emitter) invokes the
REAL scripts/changelog/emit_entry.emit_entry() against a tempfile-backed
directory and reads the written file back — no mocking of the write itself.

=== Harness limitation — what this file could NOT cover behaviorally ===

_workflow_engine_harness.run_workflow_under_e2() executes the workflow's
top-level body and captures every agent() dispatch (label, prompt, order) —
but it does NOT capture the workflow's final `return {...}` value (the JS
shim's `.then()` discards it and only serialises the captured calls/violations
to stdout). BO-2400f-4-v's structured halt payload
({classification: "halt", reason: <one of the fixed set>, built_ac_ids: [...],
branch: ...}) is therefore not independently assertable through this harness.
The tests below approximate it: they assert that a distinct
"release-on-changelog-fail" dispatch occurs on the halt path (mirroring the
existing release-call convention for every other halt in this file) and that
its prompt names the built AC id — but the exact `reason` enum value and the
`branch` field of the workflow's own return value are NOT verified here. This
is a genuine gap in what run_workflow_under_e2() can observe, not a grep
workaround — extending the harness to capture return values, or a live
subprocess-based run through the real `claude` engine, would be needed to
close it, and both are outside test-writer's mandate for this pass.

=== Red baseline ===

All tests are RED until python-coder implements the interface above. Python-
level tests fail with AttributeError (fast_lane has no
compute_changelog_requirement / build_changelog_payload yet) via the
_require_impl() guard. Harness-level tests fail with AssertionError because
fast-lane-ship.js today dispatches NO changelog-related agent call at all and
ALWAYS dispatches "fastlane-pr" unconditionally.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

# ---------------------------------------------------------------------------
# Repo path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_UNIT_TESTS_DIR = _REPO_ROOT / "unit_tests"
_BUILD_ORCH_DIR = _REPO_ROOT / "scripts" / "build_orchestration"
_RELEASE_DIR = _REPO_ROOT / "scripts" / "release"
_CHANGELOG_DIR = _REPO_ROOT / "scripts" / "changelog"

for _p in (_UNIT_TESTS_DIR, _BUILD_ORCH_DIR, _RELEASE_DIR, _CHANGELOG_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

import check_changelog_presence  # noqa: E402  (scripts/release — already exists)
import emit_entry  # noqa: E402  (scripts/changelog — already exists)

_FAST_LANE_SHIP_JS = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"

# ---------------------------------------------------------------------------
# Import the NOT-YET-IMPLEMENTED fast_lane.py symbols.
# ImportError/AttributeError IS the intended red state for the Python-level
# tests below (see _require_impl()).
# ---------------------------------------------------------------------------

_FUNC_IMPORT_OK = False
_FUNC_IMPORT_ERR = ""
compute_changelog_requirement: Any = None
build_changelog_payload: Any = None

try:
    from fast_lane import (  # noqa: E402  # type: ignore[no-redef]
        build_changelog_payload,
        compute_changelog_requirement,
    )
    _FUNC_IMPORT_OK = True
except (ImportError, AttributeError) as _exc:
    _FUNC_IMPORT_ERR = str(_exc)


def _require_impl() -> None:
    """Fail with a descriptive message when the new fast_lane symbols are absent.

    This is the intended RED state (BO-2400f-4-i/-iii/-iv) until python-coder
    implements compute_changelog_requirement() and build_changelog_payload()
    in scripts/build_orchestration/fast_lane.py.
    """
    if not _FUNC_IMPORT_OK:
        pytest.fail(
            "compute_changelog_requirement / build_changelog_payload not importable "
            f"from fast_lane — this IS the intended red state; python-coder must "
            f"implement both. Import error: {_FUNC_IMPORT_ERR}"
        )


# ---------------------------------------------------------------------------
# Fixture helpers (fixture-authenticity mandate: yaml.safe_dump, never a
# hand-typed YAML literal).
# ---------------------------------------------------------------------------


def _write_ac_fixture(
    ac_root: Path,
    ac_id: str,
    *,
    title: str,
    components: list[str],
    risk_surface: str = "internal",
) -> Path:
    """Write a minimal, realistic AC YAML fixture via yaml.safe_dump.

    Args:
        ac_root: Root of the synthetic AC store.
        ac_id: AC identifier (e.g. "BO-9001-1").
        title: The AC's human-readable title — build_changelog_payload must
            surface this in the emitted entry's "title" field.
        components: The AC's "components" list (union'd across built ACs by
            build_changelog_payload into the payload's "components" field).
        risk_surface: The AC's risk_surface field — used only to prove
            BO-2400f-4-iv's non-inference property; must have NO effect on
            the emitted "breaking" value.

    Returns:
        Path to the written YAML file.
    """
    subdir = ac_root / "build-orchestration"
    subdir.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "id": ac_id,
        "title": title,
        "components": components,
        "component": "build-orchestration",
        "level": "L3",
        "status": "active",
        "work_status": "done",
        "readiness": "approved",
        "priority": "medium",
        "estimated_complexity": "S",
        "risk_surface": risk_surface,
        "depends_on": [],
        "covered_by": [],
        "amended_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    path = subdir / f"{ac_id}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# BO-2400f-4-i — the decision reuses the gate's own rule (no duplicate list)
# ---------------------------------------------------------------------------


def test_ac_i_releasable_change_requires_changelog_entry():
    # covers: BO-2400f-4-i
    """A run whose delivered change touches a non-exempt path is told an entry
    is required, and the exempt paths are filtered out of releasable_paths."""
    _require_impl()

    changed = [
        "scripts/build_orchestration/fast_lane.py",
        "changelogs/2026-08-18-1200-stub.md",
        "docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400f-4-i.yaml",
    ]
    result = compute_changelog_requirement(changed)

    assert isinstance(result, dict), (
        f"compute_changelog_requirement must return a dict, got {type(result)}"
    )
    assert result.get("required") is True, (
        f"A non-exempt file (scripts/.../fast_lane.py) was changed — an entry must "
        f"be required. Got: {result}"
    )
    assert result.get("releasable_paths") == ["scripts/build_orchestration/fast_lane.py"], (
        f"releasable_paths must contain exactly the non-exempt file(s) changed. "
        f"Got: {result.get('releasable_paths')}"
    )


def test_ac_i_requirement_decision_follows_the_gate_rule(monkeypatch):
    # covers: BO-2400f-4-i
    """Changing the changelog-presence gate's exempt path families changes the
    lane's requirement decision — proving no duplicate exempt list exists in
    the lane (single-source property, the actual point of this AC).

    A lane that carries its own copy of EXEMPT_PREFIXES would keep answering
    "required" for this path even after the gate's own rule is widened to
    exempt it — this test fails silently-wrong in exactly that case, unless
    fast_lane.py re-reads check_changelog_presence.EXEMPT_PREFIXES at call time.
    """
    _require_impl()

    path = "scripts/build_orchestration/fast_lane.py"

    before = compute_changelog_requirement([path])
    assert before.get("required") is True, (
        "Sanity check failed: this path must be releasable (required=True) "
        f"BEFORE the gate's exempt set is widened. Got: {before}"
    )

    # Patch the GATE's own exempt list — not any copy inside fast_lane.py.
    monkeypatch.setattr(
        check_changelog_presence,
        "EXEMPT_PREFIXES",
        (*check_changelog_presence.EXEMPT_PREFIXES, "scripts/build_orchestration/"),
    )

    after = compute_changelog_requirement([path])
    assert after.get("required") is False, (
        "compute_changelog_requirement must re-derive its answer from "
        "check_changelog_presence.EXEMPT_PREFIXES at call time (import the module and "
        "read the attribute at call time — not `from check_changelog_presence import "
        "EXEMPT_PREFIXES`, which freezes a private copy at import time). Widening the "
        "gate's exempt set must flip the lane's decision in the same edit. "
        f"Before: {before}. After: {after}."
    )


# ---------------------------------------------------------------------------
# Harness-level fixtures for the fast-lane-ship.js dispatch topology
# ---------------------------------------------------------------------------

_TIMEOUT = 30  # seconds; all agent() calls are synchronous mocks

_EXEMPT_FILES_MODIFIED = [
    "docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-STUB-1.yaml",
]
_RELEASABLE_FILES_MODIFIED = [
    "scripts/build_orchestration/fast_lane.py",
]

# Full label_responses set that walks the CURRENT fast-lane-ship.js all the
# way through worktree -> resolve -> claim -> test-writer -> coder -> commit
# -> pull-request without any early return, matching each phase's schema.
_BASE_RESPONSES: dict = {
    "fastlane-worktree": {
        "worktree_path": "/tmp/fastlane-harness-wt",
        "branch": "fast-lane/bo-stub-1",
        "ac_store_path": "/tmp/fastlane-harness-wt/docs/acceptance-criteria",
        "created": True,
    },
    "resolve-connected": {"ac_ids": ["BO-STUB-1"], "message": "1 to build"},
    "claim-connected": {
        "claimed": ["BO-STUB-1"],
        "excluded_claimed": [],
        "target_refused": False,
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
    # These two phases were added to the workflow by the KI-BO-001 work and are
    # stubbed here with SCHEMA-CONFORMING positive replies (verdict_obtained /
    # entry_added), not the harness's generic default.
    #
    # Why this matters: an unstubbed label falls through to the harness default,
    # whose shape is {passed: true, ...}. If these entries were omitted, the only
    # way the workflow could reach the commit dispatch would be for its guards to
    # accept a bare `passed: true` as a review verdict — i.e. to treat a reply
    # carrying no verdict at all as a clean review. That is precisely the
    # fail-open BO-2400f-11 forbids ("no default-true, no || true"). The fixture
    # is the right place to say "review passed", not the guard.
    # Added when BO-2400c-1-iii wired the prompt-caching layer into the lane.
    # The context-bundle gate is mandatory and fails closed, so a fixture that
    # does not stub it halts the run before the Test Writer phase and every
    # assertion below about reaching commit/PR fails. Same reason the two
    # entries beneath this one exist: the harness default reply has no
    # `obtained` key, which is precisely the "absent" case the gate must reject.
    "fastlane-context-bundle": {
        "obtained": True,
        "bundle": (
            "ARCHITECTURE (stub)\n\nCONVENTIONS (stub)\n\nHIGH-LEVEL ACS (stub)"
            "\n\n<!-- CACHE_BREAKPOINT -->\n\nBATCH ACS (stub)\n\nPRIOR TESTS (stub)"
        ),
        "message": "bundle assembled",
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
        "branch": "fast-lane/bo-stub-1",
        "message": "committed",
    },
    "fastlane-pr": {
        "status": "ok",
        "pr_url": "https://github.com/example/example/pull/1",
        "message": "PR opened",
    },
}


def _run(label_responses: dict):
    return run_workflow_under_e2(
        _FAST_LANE_SHIP_JS, timeout=_TIMEOUT, label_responses=label_responses
    )


# ---------------------------------------------------------------------------
# BO-2400f-4-ii — exempt-only run writes no entry, still reaches PR
# ---------------------------------------------------------------------------


def test_ac_ii_changelog_dispatch_only_when_releasable():
    # covers: BO-2400f-4-ii
    """A releasable change dispatches the changelog step; an exempt-only
    change does not — and the exempt-only run still proceeds to open the PR.

    The FIRST assertion (releasable case dispatches 'fastlane-changelog') is
    the genuinely red one today: fast-lane-ship.js currently has NO
    changelog-related dispatch on ANY path, so a naive "no dispatch when
    exempt" assertion alone would pass vacuously right now. Asserting the
    positive case first pins real, currently-missing behavior.
    """
    releasable_responses = {
        **_BASE_RESPONSES,
        "coder-connected": {
            **_BASE_RESPONSES["coder-connected"],
            "files_modified": _RELEASABLE_FILES_MODIFIED,
        },
    }
    releasable_result = _run(releasable_responses)
    assert releasable_result.error == "", f"Harness error: {releasable_result.error}"
    releasable_labels = [c.label for c in releasable_result.agent_calls]
    assert "fastlane-changelog" in releasable_labels, (
        "A run whose coder reports a non-exempt (releasable) file change must dispatch "
        "a changelog decision/emission step (contract label 'fastlane-changelog') before "
        "opening the PR. No such dispatch exists today — this IS KI-BO-001: every "
        f"fast-lane PR ships without a changelog entry. Dispatched labels: {releasable_labels}"
    )

    exempt_responses = {
        **_BASE_RESPONSES,
        "coder-connected": {
            **_BASE_RESPONSES["coder-connected"],
            "files_modified": _EXEMPT_FILES_MODIFIED,
        },
    }
    exempt_result = _run(exempt_responses)
    assert exempt_result.error == "", f"Harness error: {exempt_result.error}"
    exempt_labels = [c.label for c in exempt_result.agent_calls]
    assert "fastlane-changelog" not in exempt_labels, (
        "A run whose coder's ENTIRE files_modified list is confined to the "
        "changelog-presence gate's exempt path families must NOT dispatch the "
        f"changelog step at all. Dispatched labels: {exempt_labels}"
    )
    assert "fastlane-pr" in exempt_labels, (
        "An exempt-only run must still reach the Pull Request phase — producing no "
        f"changelog entry is a success path here, not a blocker. Labels: {exempt_labels}"
    )


# ---------------------------------------------------------------------------
# BO-2400f-4-iii — the run emits the entry itself, committed before the PR
# ---------------------------------------------------------------------------


def test_ac_iii_run_emits_changelog_entry_via_real_emitter(tmp_path):
    # covers: BO-2400f-4-iii
    """Real-artifact behavioral test (BP-1100f-2): build the payload the run
    would assemble, then hand it to the REAL scripts/changelog/emit_entry.py
    emitter against a tempfile-backed directory (no mocking of the write
    itself), and read the written file back off disk."""
    _require_impl()

    ac_root = tmp_path / "acs"
    _write_ac_fixture(
        ac_root,
        "BO-9002-1",
        title="Real emitter round-trip AC",
        components=["build_orchestration"],
    )

    payload = build_changelog_payload(
        target_ac="BO-9002-1",
        built_ac_ids=["BO-9002-1"],
        files_modified=["scripts/build_orchestration/fast_lane.py"],
        branch="fast-lane/bo-9002-1",
        ac_root=ac_root,
    )

    changelog_dir = tmp_path / "changelogs"
    written_path = emit_entry.emit_entry(payload, changelog_dir=changelog_dir)

    assert written_path.exists(), (
        f"emit_entry must actually write a file to disk. Path: {written_path}"
    )
    assert written_path.parent == changelog_dir, (
        f"The entry must land in the requested changelog_dir, got parent {written_path.parent}"
    )
    content = written_path.read_text(encoding="utf-8")
    assert content.startswith("---"), "The written entry must carry YAML frontmatter."
    assert "breaking: false" in content, (
        f"The real, on-disk entry must record breaking: false. Content:\n{content}"
    )
    assert "BO-9002-1" in content, (
        f"The real, on-disk entry must name the built AC id. Content:\n{content}"
    )


def test_ac_iii_entry_content_derived_from_run_state(tmp_path):
    # covers: BO-2400f-4-iii
    """The emitted entry names the target AC (via its title), the built AC
    ids, and the files the coder modified — all drawn from facts the run
    already holds, with no operator input."""
    _require_impl()

    ac_root = tmp_path / "acs"
    _write_ac_fixture(
        ac_root,
        "BO-9001-1",
        title="Sample fast-lane target AC",
        components=["build_orchestration"],
    )

    payload = build_changelog_payload(
        target_ac="BO-9001-1",
        built_ac_ids=["BO-9001-1"],
        files_modified=[
            "scripts/build_orchestration/fast_lane.py",
            "templates/workflows-js/fast-lane-ship.js",
        ],
        branch="fast-lane/bo-9001-1",
        ac_root=ac_root,
    )

    assert "Sample fast-lane target AC" in str(payload.get("title", "")), (
        f"payload title must be derived from the target AC's own title. Got: {payload.get('title')}"
    )
    description = str(payload.get("description", ""))
    assert "BO-9001-1" in description, f"description must name the built AC id(s). Got: {description}"
    assert "scripts/build_orchestration/fast_lane.py" in description, (
        f"description must name the files the coder modified. Got: {description}"
    )
    assert "templates/workflows-js/fast-lane-ship.js" in description, (
        f"description must name every file the coder modified. Got: {description}"
    )
    assert payload.get("type") == "manual", f"payload type must be 'manual'. Got: {payload.get('type')}"
    assert "build_orchestration" in (payload.get("components") or []), (
        f"components must include the built AC's own components. Got: {payload.get('components')}"
    )


def test_ac_iii_changelog_entry_committed_before_pr_is_opened():
    # covers: BO-2400f-4-iii
    """The changelog-emit dispatch must occur, and must occur BEFORE the
    pull-request dispatch — so the entry is part of the PR's own diff rather
    than a follow-up commit (re-introducing KI-BO-001 for anyone reading the
    PR at the moment it opens)."""
    responses = {
        **_BASE_RESPONSES,
        "coder-connected": {
            **_BASE_RESPONSES["coder-connected"],
            "files_modified": _RELEASABLE_FILES_MODIFIED,
        },
        "fastlane-changelog": {
            "status": "ok",
            "entry_added": True,
            "entry_path": "changelogs/2026-08-18-1200-stub.md",
            "message": "emitted",
        },
    }
    result = _run(responses)
    assert result.error == "", f"Harness error: {result.error}"
    labels = [c.label for c in result.agent_calls]

    assert "fastlane-changelog" in labels, (
        "Expected a 'fastlane-changelog' dispatch for a releasable change. "
        f"Dispatched labels: {labels}"
    )
    assert "fastlane-pr" in labels, f"Expected the run to reach the PR phase. Labels: {labels}"
    assert labels.index("fastlane-changelog") < labels.index("fastlane-pr"), (
        "The changelog entry must be produced (and committed) BEFORE the pull-request "
        f"phase runs — emitting after the PR call re-introduces KI-BO-001. Labels: {labels}"
    )


# ---------------------------------------------------------------------------
# BO-2400f-4-iv — breaking is never guessed: emitted false, PR notice unconditional
# ---------------------------------------------------------------------------


def test_ac_iv_emitted_entry_is_not_breaking(tmp_path):
    # covers: BO-2400f-4-iv
    """The entry the run emits records the change as not breaking."""
    _require_impl()

    ac_root = tmp_path / "acs"
    _write_ac_fixture(
        ac_root,
        "BO-9003-1",
        title="Breaking-flag AC",
        components=["build_orchestration"],
        risk_surface="contract_boundary",
    )
    payload = build_changelog_payload(
        target_ac="BO-9003-1",
        built_ac_ids=["BO-9003-1"],
        files_modified=["scripts/build_orchestration/fast_lane.py"],
        branch="fast-lane/bo-9003-1",
        ac_root=ac_root,
    )
    assert payload.get("breaking") is False, (
        f"The emitted entry must record breaking: False. Got: {payload.get('breaking')!r}"
    )


def test_ac_iv_pr_body_declares_breaking_undetermined_and_entry_not_breaking(tmp_path):
    # covers: BO-2400f-4-iv
    """Asserts BOTH halves in one test, per this AC's own constraint:
    asserting only breaking==False cannot distinguish an honest, declared
    default from an unlabelled hardcoded constant — the PR must ALSO carry an
    explicit, UNCONDITIONAL notice that the flag was not determined by the
    run and needs human confirmation before merge.
    """
    # --- Half 1: the emitted payload's breaking field. ---
    _require_impl()

    ac_root = tmp_path / "acs"
    _write_ac_fixture(
        ac_root,
        "BO-9004-1",
        title="Both-halves AC",
        components=["build_orchestration"],
    )
    payload = build_changelog_payload(
        target_ac="BO-9004-1",
        built_ac_ids=["BO-9004-1"],
        files_modified=["scripts/build_orchestration/fast_lane.py"],
        branch="fast-lane/bo-9004-1",
        ac_root=ac_root,
    )
    assert payload.get("breaking") is False, (
        f"Half 1 failed: emitted entry must record breaking: False. Got: {payload.get('breaking')!r}"
    )

    # --- Half 2: the PR body (JS-computed, embedded verbatim in the
    # 'fastlane-pr' dispatch's prompt) must carry the notice UNCONDITIONALLY. ---
    responses = {
        **_BASE_RESPONSES,
        "coder-connected": {
            **_BASE_RESPONSES["coder-connected"],
            "files_modified": _RELEASABLE_FILES_MODIFIED,
        },
    }
    result = _run(responses)
    assert result.error == "", f"Harness error: {result.error}"
    pr_calls = [c for c in result.agent_calls if c.label == "fastlane-pr"]
    assert pr_calls, (
        f"Expected a 'fastlane-pr' dispatch. Labels: {[c.label for c in result.agent_calls]}"
    )
    pr_prompt = pr_calls[0].prompt
    assert isinstance(pr_prompt, str), f"fastlane-pr prompt must be a string. Got: {type(pr_prompt)}"
    lowered = pr_prompt.lower()
    assert (
        "not determined by the run" in lowered
        or "breaking flag was not determined" in lowered
    ), (
        "Half 2 failed: the PR body must carry an explicit, UNCONDITIONAL notice that "
        "the breaking flag was not determined by the run and needs human confirmation "
        f"before merge. fastlane-pr prompt (first 800 chars): {pr_prompt[:800]}"
    )
    assert "confirm" in lowered or "human" in lowered or "review" in lowered, (
        "The notice must ask for human confirmation/review, not merely mention "
        f"'breaking'. fastlane-pr prompt (first 800 chars): {pr_prompt[:800]}"
    )


def test_ac_iv_entry_identical_across_differing_risk_surface(tmp_path):
    # covers: BO-2400f-4-iv
    """Two runs whose built criteria differ ONLY in risk_surface must produce
    the SAME breaking value — proving the flag is not inferred from AC
    metadata (the rejected design this AC's notes explicitly reject: risk_surface
    marks WHERE a criterion sits, not whether the change made to it breaks
    callers; TKT-600a-1 is risk_surface=contract_boundary and genuinely
    non-breaking)."""
    _require_impl()

    ac_root_internal = tmp_path / "acs_internal"
    ac_root_contract_boundary = tmp_path / "acs_contract_boundary"
    _write_ac_fixture(
        ac_root_internal,
        "BO-9005-1",
        title="Risk-surface invariance AC",
        components=["build_orchestration"],
        risk_surface="internal",
    )
    _write_ac_fixture(
        ac_root_contract_boundary,
        "BO-9005-1",
        title="Risk-surface invariance AC",
        components=["build_orchestration"],
        risk_surface="contract_boundary",
    )

    payload_internal = build_changelog_payload(
        target_ac="BO-9005-1",
        built_ac_ids=["BO-9005-1"],
        files_modified=["scripts/build_orchestration/fast_lane.py"],
        branch="fast-lane/bo-9005-1",
        ac_root=ac_root_internal,
    )
    payload_contract_boundary = build_changelog_payload(
        target_ac="BO-9005-1",
        built_ac_ids=["BO-9005-1"],
        files_modified=["scripts/build_orchestration/fast_lane.py"],
        branch="fast-lane/bo-9005-1",
        ac_root=ac_root_contract_boundary,
    )

    assert payload_internal.get("breaking") is False
    assert payload_contract_boundary.get("breaking") is False
    assert payload_internal.get("breaking") == payload_contract_boundary.get("breaking"), (
        "The two runs above differ ONLY in the built AC's risk_surface and must "
        "produce the identical breaking value — any difference proves the flag is "
        "being (mis-)inferred from AC metadata. "
        f"internal={payload_internal.get('breaking')!r} "
        f"contract_boundary={payload_contract_boundary.get('breaking')!r}"
    )


# ---------------------------------------------------------------------------
# BO-2400f-4-v — a failed/absent entry HALTS; never a warning next to success
# ---------------------------------------------------------------------------


def test_ac_v_emit_failure_halts_before_pr_is_opened():
    # covers: BO-2400f-4-v
    """When the changelog-emit attempt returns an error, the run must halt
    (reason: changelog_emit_failed) and 'fastlane-pr' must NEVER be
    dispatched. This is genuinely red today because fast-lane-ship.js
    dispatches 'fastlane-pr' unconditionally — there is no gate to fail."""
    responses = {
        **_BASE_RESPONSES,
        "coder-connected": {
            **_BASE_RESPONSES["coder-connected"],
            "files_modified": _RELEASABLE_FILES_MODIFIED,
        },
        "fastlane-changelog": {
            "status": "error",
            "entry_added": False,
            "entry_path": None,
            "message": "emit_entry.py exited 1: missing required field",
        },
    }
    result = _run(responses)
    assert result.error == "", f"Harness error: {result.error}"
    labels = [c.label for c in result.agent_calls]
    assert "fastlane-pr" not in labels, (
        "When the changelog-emit attempt reports an error, the run MUST halt before "
        "opening the pull request (reason: changelog_emit_failed) — it must NEVER "
        f"proceed to the pull-request phase as a warning-next-to-success. Labels: {labels}"
    )


def test_ac_v_entry_absent_from_change_halts_even_on_reported_success():
    # covers: BO-2400f-4-v
    """A changelog-emit attempt that reports status ok but leaves no added
    entry present in the delivered change (silent failure — the exact
    KI-BO-001 failure mode) must ALSO halt, with reason
    changelog_entry_absent_from_change. The post-condition check must be
    independent of the attempt's own self-report."""
    responses = {
        **_BASE_RESPONSES,
        "coder-connected": {
            **_BASE_RESPONSES["coder-connected"],
            "files_modified": _RELEASABLE_FILES_MODIFIED,
        },
        "fastlane-changelog": {
            "status": "ok",
            "entry_added": False,
            "entry_path": None,
            "message": "reported success but nothing was staged",
        },
    }
    result = _run(responses)
    assert result.error == "", f"Harness error: {result.error}"
    labels = [c.label for c in result.agent_calls]
    assert "fastlane-pr" not in labels, (
        "A changelog-emit attempt that reports status ok but has no added entry in the "
        "delivered change must halt with reason changelog_entry_absent_from_change, "
        f"exactly as if the attempt had failed outright. Labels: {labels}"
    )


def test_ac_v_halt_releases_claimed_acs_naming_built_ac_ids():
    # covers: BO-2400f-4-v
    """A changelog halt must release the run's claimed ACs back to todo
    (BO-2400f-10 coordination) via a dedicated release dispatch — mirroring
    the existing release-on-test-writer-fail / release-on-coder-fail /
    release-on-commit-fail convention already used by every other halt path
    in this workflow — and that release dispatch must name the built AC ids
    so the operator can finish delivery by hand.

    NOTE (harness limitation, documented at module level): the workflow's own
    structured halt return value (classification/reason/branch) is not
    observable through this harness. This test approximates the "names the
    branch and built ACs" requirement via the release dispatch's prompt,
    which is the closest observable proxy — it does not independently confirm
    the return value's own `reason` or `branch` fields.
    """
    responses = {
        **_BASE_RESPONSES,
        "coder-connected": {
            **_BASE_RESPONSES["coder-connected"],
            "files_modified": _RELEASABLE_FILES_MODIFIED,
        },
        "fastlane-changelog": {
            "status": "error",
            "entry_added": False,
            "entry_path": None,
            "message": "boom",
        },
    }
    result = _run(responses)
    assert result.error == "", f"Harness error: {result.error}"
    labels = [c.label for c in result.agent_calls]

    release_calls = [c for c in result.agent_calls if c.label == "release-on-changelog-fail"]
    assert release_calls, (
        "A changelog halt must release the claimed ACs back to todo via a dedicated "
        "'release-on-changelog-fail' dispatch, mirroring the existing "
        "release-on-test-writer-fail / release-on-coder-fail / release-on-commit-fail "
        f"pattern already used by every other halt path in this file. Labels: {labels}"
    )
    release_prompt = release_calls[0].prompt
    assert isinstance(release_prompt, str), (
        f"release-on-changelog-fail prompt must be a string. Got: {type(release_prompt)}"
    )
    assert "BO-STUB-1" in release_prompt, (
        "The release dispatch must name the built AC id(s) it is releasing, so the "
        f"operator can finish delivery by hand. Prompt: {release_prompt[:400]}"
    )


def test_ac_i_js_exempt_mirror_matches_the_gate_module():
    # covers: BO-2400f-4-i
    """The workflow's JS exempt-prefix mirror must equal the gate's own list.

    fast-lane-ship.js decides whether to dispatch the changelog phase at all
    from a JS array, because the E2 engine has no filesystem access and cannot
    import the Python gate module to make that topology call (ADR-024). The
    requirement decision itself is single-source — compute_changelog_requirement
    re-reads check_changelog_presence.EXEMPT_PREFIXES at call time — but the
    dispatch gate is a hand-copied duplicate, and a duplicate that can drift is
    exactly what BO-2400f-4-i exists to prevent.

    The dangerous direction is specific: if the gate module gains a new exempt
    prefix and this mirror does not, the lane merely dispatches a changelog
    phase it did not need — harmless. If the gate module REMOVES a prefix (or
    narrows one) and this mirror keeps it, the lane skips the changelog phase
    for a change that in fact owes an entry, and opens an unmergeable PR. That
    is KI-BO-001 returning through a side door, and it would be silent.

    This test makes that drift impossible to land quietly.
    """
    workflow_src = _FAST_LANE_SHIP_JS.read_text(encoding="utf-8")

    marker = "const CHANGELOG_EXEMPT_PREFIXES = ["
    start = workflow_src.find(marker)
    assert start != -1, (
        "fast-lane-ship.js must declare CHANGELOG_EXEMPT_PREFIXES. If the "
        "dispatch decision was redesigned to avoid the mirror entirely (e.g. "
        "always dispatch and let the Python layer decide), delete this test "
        "along with the array — do not leave it asserting a stale shape."
    )
    end = workflow_src.find("]", start)
    body = workflow_src[start + len(marker) : end]

    js_prefixes = sorted(
        segment.strip().strip(",").strip('"').strip("'")
        for segment in body.split("\n")
        if segment.strip().strip(",").strip()
    )
    py_prefixes = sorted(check_changelog_presence.EXEMPT_PREFIXES)

    assert js_prefixes == py_prefixes, (
        "The JS exempt-prefix mirror in fast-lane-ship.js has drifted from "
        "check_changelog_presence.EXEMPT_PREFIXES, the rule the required CI "
        "check actually applies. Update the JS array in the same edit as the "
        "Python list.\n"
        f"  JS:     {js_prefixes}\n"
        f"  Python: {py_prefixes}"
    )
