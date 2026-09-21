"""
MODULE: test_quick_fix_scope_guard_artifact_exclusion
GOAL: /quick-fix (BP-600e-1-ii) behavioral coverage for the scope-expansion
      guard's blind spot: the guard currently trusts fixResult.extra_files
      verbatim, so it halts on the workflow's OWN earlier outputs — the AC
      YAML (ac_path), its back-linked parent AC (parent_ac_path), and the
      red-phase test file (testFile) — even though those three paths are
      *expected* to already be dirty by the time the Fix phase runs.

      This is the exact symptom from the 2026-09-17 run: a quick-fix halted
      naming the AC it had just written, that AC's parent, and the test
      test-writer had just written — although python-coder touched nothing
      but the target file.

Drives the workflow end-to-end via run_workflow_under_e2 rather than
grepping quick-fix.js for a filter expression: a presence-only source
assertion ("extra_files is filtered somewhere") passes equally on a filter
that matches nothing, which is precisely the phantom-done shape BP-600e-2's
notes warn about for this family. Only a run that supplies the three
artifact paths and observes no halt proves the exclusion works, and only a
run that adds one more, genuinely unrelated, path and observes a halt proves
the guard was narrowed rather than disabled outright.

TICKET: BP-600e-1-ii
AC: BP-600e-1-ii
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

# The exact artifact paths _full_success_responses() wires through the run:
# ac-creation supplies ac_path/parent_ac_path, test-writer supplies testFile.
_AC_PATH = "docs/acceptance-criteria/build-pipeline/bp-900/BP-9001.yaml"
_PARENT_AC_PATH = "docs/acceptance-criteria/build-pipeline/bp-900/BP-900.yaml"
_TEST_FILE = "unit_tests/test_bp9001.py"


class TestScopeGuardIgnoresTheWorkflowsOwnOutputs:
    """BP-600e-1-ii: the scope-expansion guard must ignore the workflow's
    own three artifact paths and must not halt because of them."""

    def test_ac_bp600e1ii_workflow_artifacts_do_not_halt_the_run(self):
        # covers: BP-600e-1-ii
        # angle: criterion
        """A Fix response whose extra_files lists exactly the run's own
        ac_path, parent_ac_path and testFile must NOT halt the run: the run
        must reach status 'ok' and must not report halt_reason
        'scope_expansion'.

        Currently RED: quick-fix.js's scope-expansion guard
        (`if (fixResult.scope_expanded || fixResult.extra_files.length > 0)`)
        trusts extra_files verbatim with no notion of which paths the
        workflow itself authored, so this run halts today exactly like the
        2026-09-17 incident did.
        """
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(**{
                "python-coder/fix": {
                    "status": "ok",
                    "modified_files": ["stub/target.py"],
                    "scope_expanded": False,
                    "extra_files": [_AC_PATH, _PARENT_AC_PATH, _TEST_FILE],
                },
            }),
        )

        assert result.result is not None, (
            f"Workflow produced no terminal result. stderr={result.stderr!r}"
        )
        assert result.result.get("halt_reason") != "scope_expansion", (
            "The guard halted on the workflow's own artifacts "
            f"(ac_path={_AC_PATH!r}, parent_ac_path={_PARENT_AC_PATH!r}, "
            f"testFile={_TEST_FILE!r}) reported as extra_files — these three "
            "paths are expected additions per SKILL.md Phase 3.5 and must be "
            f"excluded before the guard judges scope expansion. Got: "
            f"{result.result!r}"
        )
        assert result.result.get("status") == "ok", (
            "Run must proceed past the Fix phase to a successful close once "
            f"the three workflow-authored paths are excluded. Got: {result.result!r}"
        )
        # The run must actually have continued to the green phase and beyond
        # — not merely avoided the specific halt_reason string by luck.
        assert "green-verify/strict" in _labels(result), (
            "Run must reach the Green Phase once the workflow's own "
            f"artifacts are excluded from the scope check. Dispatched labels: "
            f"{_labels(result)!r}"
        )

    def test_ac_bp600e1ii_genuine_third_party_file_still_halts(self):
        # covers: BP-600e-1-ii
        # angle: boundary
        """The same run must still halt with halt_reason 'scope_expansion',
        naming the offending path, when extra_files contains one genuinely
        unrelated file alongside the three workflow-authored paths — the
        filter narrows the halt, it does not remove it.

        Negative control for the test above: proves the exclusion is a
        precise filter against known paths, not a guard that has been
        disabled outright (e.g. by deleting the scope-expansion check
        entirely, which would make the first test pass for the wrong
        reason).
        """
        unrelated_file = "src/some/unrelated_module.py"

        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(**{
                "python-coder/fix": {
                    "status": "ok",
                    "modified_files": ["stub/target.py"],
                    "scope_expanded": False,
                    "extra_files": [
                        _AC_PATH,
                        _PARENT_AC_PATH,
                        _TEST_FILE,
                        unrelated_file,
                    ],
                },
            }),
        )

        assert result.result is not None, (
            f"Workflow produced no terminal result. stderr={result.stderr!r}"
        )
        assert result.result.get("status") == "blocked", (
            f"A genuine third-party extra file must still halt the run. Got: {result.result!r}"
        )
        assert result.result.get("halt_reason") == "scope_expansion", (
            f"Halt must be reported as scope_expansion. Got: {result.result!r}"
        )
        assert unrelated_file in str(result.result.get("message", "")) or unrelated_file in (
            result.result.get("extra_files") or []
        ), (
            "Halt must name the genuinely unrelated file, not just the "
            f"workflow's own artifacts. Got: {result.result!r}"
        )
        # And it must NOT include the two workflow-authored AC paths / test
        # file as if they were still under suspicion — only the genuine
        # extra should remain once the exclusion is applied.
        remaining_extra = result.result.get("extra_files") or []
        assert _AC_PATH not in remaining_extra, (
            f"ac_path must be filtered out of the reported extra_files. Got: {remaining_extra!r}"
        )
        assert _PARENT_AC_PATH not in remaining_extra, (
            f"parent_ac_path must be filtered out of the reported extra_files. Got: {remaining_extra!r}"
        )
        assert _TEST_FILE not in remaining_extra, (
            f"testFile must be filtered out of the reported extra_files. Got: {remaining_extra!r}"
        )

    def test_ac_bp600e1ii_unnamed_expansion_in_modified_files_still_halts(self):
        # covers: BP-600e-1-ii
        # angle: failure
        """scope_expanded=true with an EMPTY extra_files must still halt when
        modified_files names a genuinely unrelated file: the fix agent may
        set scope_expanded without ever naming the offending path in
        extra_files, and the guard must catch that via modified_files rather
        than trust extra_files alone.

        Currently RED: the guard only filters fixResult.extra_files and never
        looks at modified_files, so an expansion reported solely through
        modified_files sails through unnoticed and the run closes with
        unexpected edits left uncommitted.
        """
        unrelated_file = "src/some/unrelated_module.py"

        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(**{
                "python-coder/fix": {
                    "status": "ok",
                    "modified_files": ["stub/target.py", unrelated_file],
                    "scope_expanded": True,
                    "extra_files": [],
                },
            }),
        )

        assert result.result is not None, (
            f"Workflow produced no terminal result. stderr={result.stderr!r}"
        )
        assert result.result.get("status") == "blocked", (
            "An unnamed expansion surfaced only through modified_files must "
            f"still halt the run. Got: {result.result!r}"
        )
        assert result.result.get("halt_reason") == "scope_expansion", (
            f"Halt must be reported as scope_expansion. Got: {result.result!r}"
        )
        assert unrelated_file in str(result.result.get("message", "")) or unrelated_file in (
            result.result.get("extra_files") or []
        ), (
            "Halt must name the genuinely unrelated modified_files path, not "
            f"just be silent about it. Got: {result.result!r}"
        )

    def test_ac_bp600e1ii_target_file_and_artifacts_in_modified_files_do_not_halt(self):
        # covers: BP-600e-1-ii
        # angle: criterion
        """scope_expanded=true with empty extra_files and modified_files
        holding only target_file plus the three workflow artifacts must NOT
        halt: target_file is the expected edit and the three artifacts are
        the workflow's own earlier outputs, so modified_files naming exactly
        those four paths is not an expansion at all.
        """
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(**{
                "python-coder/fix": {
                    "status": "ok",
                    "modified_files": [
                        "stub/target.py",
                        _AC_PATH,
                        _PARENT_AC_PATH,
                        _TEST_FILE,
                    ],
                    "scope_expanded": True,
                    "extra_files": [],
                },
            }),
        )

        assert result.result is not None, (
            f"Workflow produced no terminal result. stderr={result.stderr!r}"
        )
        assert result.result.get("halt_reason") != "scope_expansion", (
            "modified_files naming only target_file and the three workflow "
            f"artifacts must not be treated as an expansion. Got: {result.result!r}"
        )
        assert result.result.get("status") == "ok", (
            "Run must proceed past the Fix phase to a successful close when "
            f"modified_files names nothing genuinely unexpected. Got: {result.result!r}"
        )
        assert "green-verify/strict" in _labels(result), (
            "Run must reach the Green Phase once modified_files is filtered "
            f"correctly. Dispatched labels: {_labels(result)!r}"
        )
