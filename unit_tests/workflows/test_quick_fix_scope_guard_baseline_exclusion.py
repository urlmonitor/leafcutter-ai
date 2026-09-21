"""
MODULE: test_quick_fix_scope_guard_baseline_exclusion
GOAL: /quick-fix (BP-600e-1-i) behavioral coverage for the scope-expansion
      guard's second blind spot: a file that was ALREADY dirty before the
      coder was ever dispatched — because pre-commit auto-formatted it, or
      doc-enforcer rewrote a docstring, or it was simply pre-existing drift
      in an isolated worktree — is not the coder's own intentional change,
      and must not count toward the scope-expansion threshold either.

      This is BP-600e-1-ii's sibling: that AC excludes the workflow's own
      THREE KNOWN artifacts (ac_path, parent_ac_path, testFile) by name.
      This AC excludes whatever else was ALREADY dirty by the time the Fix
      phase starts, via a `git status --porcelain` snapshot taken BEFORE the
      coder runs — so the exclusion set is dynamic, not a fixed list of
      three paths.

Drives the workflow end-to-end via run_workflow_under_e2 rather than
grepping quick-fix.js for a filter expression, for the same phantom-done
reason BP-600e-1-ii's sibling file documents: a presence-only source
assertion passes equally on a filter that matches nothing.

TICKET: BP-600e-1-i
AC: BP-600e-1-i
"""

from __future__ import annotations

import sys
from pathlib import Path

# unit_tests/workflows/ must be on sys.path so the flat sibling import below
# resolves — this package has __init__.py, so pytest's rootdir insertion
# does not add it automatically (mirrors the unit_tests/ insertion pattern
# _quick_fix_harness.py itself uses for _workflow_engine_harness).
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _quick_fix_harness import (  # noqa: E402
    _JS_PATH,
    _full_success_responses,
    _labels,
    run_workflow_under_e2,
)

_ALREADY_DIRTY_FILE = "scripts/__init__.py"
_UNRELATED_FILE = "src/some/unrelated_module.py"


class TestScopeGuardIgnoresPathsAlreadyDirtyBeforeTheFix:
    """BP-600e-1-i: the scope-expansion guard must ignore any path already
    dirty BEFORE the coder was dispatched, and must still catch a path the
    coder newly touched — with an unavailable baseline degrading to the
    guard's pre-existing (three-artifact-only) behaviour, never to a halt
    on everything."""

    def test_ac_bp600e1i_file_dirty_before_fix_phase_does_not_halt(self):
        # covers: BP-600e-1-i
        # angle: criterion
        """A path the baseline snapshot reports as already dirty before the
        Fix phase — reported back by the coder as an extra file — must NOT
        halt the run: the baseline is subtracted from extra_files exactly
        like the three known workflow artifacts are.

        Currently RED: quick-fix.js has no pre-fix baseline snapshot at
        all, so this path is judged as if the coder introduced it.
        """
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(**{
                "baseline-dirty-snapshot": {
                    "status": "ok",
                    "dirty_paths": [_ALREADY_DIRTY_FILE],
                },
                "python-coder/fix": {
                    "status": "ok",
                    "modified_files": ["stub/target.py"],
                    "scope_expanded": False,
                    "extra_files": [_ALREADY_DIRTY_FILE],
                },
            }),
        )

        assert result.result is not None, (
            f"Workflow produced no terminal result. stderr={result.stderr!r}"
        )
        assert result.result.get("halt_reason") != "scope_expansion", (
            f"The guard halted on {_ALREADY_DIRTY_FILE!r}, which the baseline "
            "snapshot reported as already dirty BEFORE the fix — it must be "
            f"excluded from the scope check. Got: {result.result!r}"
        )
        assert result.result.get("status") == "ok", (
            f"Run must proceed to a successful close. Got: {result.result!r}"
        )
        assert "green-verify/strict" in _labels(result), (
            "Run must reach the Green Phase once the pre-fix baseline is "
            f"excluded. Dispatched labels: {_labels(result)!r}"
        )

    def test_ac_bp600e1i_baseline_snapshot_is_dispatched_before_the_fix_agent(self):
        # covers: BP-600e-1-i
        # angle: seam
        """The baseline-dirty-snapshot label must be dispatched, and it must
        appear strictly before python-coder/fix in the label sequence — the
        snapshot is only meaningful if it is captured before the coder is
        given a chance to touch anything.
        """
        result = run_workflow_under_e2(
            _JS_PATH, label_responses=_full_success_responses(),
        )

        labels = _labels(result)
        assert "baseline-dirty-snapshot" in labels, (
            f"quick-fix.js must dispatch a baseline-dirty-snapshot step. Got: {labels!r}"
        )
        assert labels.index("baseline-dirty-snapshot") < labels.index("python-coder/fix"), (
            "The baseline snapshot must be captured BEFORE the coder runs, not "
            f"after. Dispatched labels: {labels!r}"
        )

    def test_ac_bp600e1i_file_the_coder_newly_touched_still_halts(self):
        # covers: BP-600e-1-i
        # angle: boundary
        """A path absent from the pre-fix baseline — one the coder touched
        for the first time — must still halt the run, naming that path.
        Negative control: proves the baseline exclusion is a precise
        subtraction against a real snapshot, not a guard disabled outright.
        """
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(**{
                "baseline-dirty-snapshot": {
                    "status": "ok",
                    "dirty_paths": [_ALREADY_DIRTY_FILE],
                },
                "python-coder/fix": {
                    "status": "ok",
                    "modified_files": ["stub/target.py"],
                    "scope_expanded": False,
                    "extra_files": [_ALREADY_DIRTY_FILE, _UNRELATED_FILE],
                },
            }),
        )

        assert result.result is not None, (
            f"Workflow produced no terminal result. stderr={result.stderr!r}"
        )
        assert result.result.get("status") == "blocked", (
            f"A genuinely new extra file must still halt the run. Got: {result.result!r}"
        )
        assert result.result.get("halt_reason") == "scope_expansion", (
            f"Halt must be reported as scope_expansion. Got: {result.result!r}"
        )
        remaining_extra = result.result.get("extra_files") or []
        assert _UNRELATED_FILE in remaining_extra, (
            f"Halt must name the newly-touched path. Got: {remaining_extra!r}"
        )
        assert _ALREADY_DIRTY_FILE not in remaining_extra, (
            f"The pre-fix-dirty path must be filtered out. Got: {remaining_extra!r}"
        )

    def test_ac_bp600e1i_unavailable_baseline_falls_back_to_the_three_artifact_exclusion(self):
        # covers: BP-600e-1-i
        # angle: failure
        """When the baseline-dirty-snapshot step itself is unavailable (here:
        it returns 'blocked', carrying no dirty_paths at all — the harness's
        generic unmocked-label stub has the same shape), the guard must
        degrade to today's behaviour: the three known workflow artifacts
        (ac_path, parent_ac_path, testFile) are still excluded by name, but
        nothing else is silently excused. This is NOT a halt-on-everything
        failure mode — a run whose extra_files names only the three known
        artifacts still completes normally.
        """
        ac_path = "docs/acceptance-criteria/build-pipeline/bp-900/BP-9001.yaml"
        parent_ac_path = "docs/acceptance-criteria/build-pipeline/bp-900/BP-900.yaml"
        test_file = "unit_tests/test_bp9001.py"

        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(**{
                "baseline-dirty-snapshot": {"status": "blocked", "message": "git unavailable"},
                "python-coder/fix": {
                    "status": "ok",
                    "modified_files": ["stub/target.py"],
                    "scope_expanded": False,
                    "extra_files": [ac_path, parent_ac_path, test_file],
                },
            }),
        )

        assert result.result is not None, (
            f"Workflow produced no terminal result. stderr={result.stderr!r}"
        )
        assert result.result.get("halt_reason") != "scope_expansion", (
            "An unavailable baseline must not turn the three known workflow "
            f"artifacts into a halt. Got: {result.result!r}"
        )
        assert result.result.get("status") == "ok", (
            f"Run must still complete normally. Got: {result.result!r}"
        )

    def test_ac_bp600e1i_unavailable_baseline_still_catches_a_genuine_extra_file(self):
        # covers: BP-600e-1-i
        # angle: failure
        """An unavailable baseline degrades to the pre-existing exclusion
        set, not to an empty one that lets everything through: a genuinely
        unrelated file must still halt the run exactly as it did before this
        AC — the failure mode of a missing baseline is 'no bonus exclusion',
        never 'no exclusion at all reported as a false halt' or 'guard
        disabled'.
        """
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(**{
                "baseline-dirty-snapshot": {"status": "blocked", "message": "git unavailable"},
                "python-coder/fix": {
                    "status": "ok",
                    "modified_files": ["stub/target.py"],
                    "scope_expanded": False,
                    "extra_files": [_UNRELATED_FILE],
                },
            }),
        )

        assert result.result is not None, (
            f"Workflow produced no terminal result. stderr={result.stderr!r}"
        )
        assert result.result.get("status") == "blocked", (
            f"A genuine extra file must still halt even with no baseline. Got: {result.result!r}"
        )
        assert result.result.get("halt_reason") == "scope_expansion", (
            f"Halt must be reported as scope_expansion. Got: {result.result!r}"
        )
