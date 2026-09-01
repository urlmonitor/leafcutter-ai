"""
MODULE: unit_tests/workflows/test_tkt_600b_4.py
GOAL: RED test stubs for TKT-600b-4 — the drive must never edit a ticket's
      phase record to make it agree with the drive's own behaviour. On any
      disagreement between what the record requires and what the drive will
      dispatch, the drive must change NO phase status, must surface both
      sides of the disagreement, and must not record the ticket complete.
COVERS: TKT-600b-4

Testability: templates/workflows-js/build-feature.js is a Workflow-engine
script (references injected globals agent()/parallel()), so the pure
comparison logic must be extracted and run under `node`, exactly as the
existing BO-2700 seam tests do (extract-and-run pattern, no hand-typed copy
of the function). Per CLAUDE.md's gate/workflow rule, the seam test below
demands BOTH outcomes (refuse / proceed) from the SAME extracted function so
a hard-wired-shut gate cannot pass it.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_WORKFLOW_PATH = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"


def _extract_function(source: str, name: str) -> str:
    """Extract a top-level `function <name>(...) { ... }` by brace-counting."""
    start = source.index(f"function {name}(")
    brace = source.index("{", start)
    depth = 0
    i = brace
    while i < len(source):
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[start : i + 1]
        i += 1
    raise AssertionError(f"could not extract function {name}")


def _run_compare(record_requires, drive_will_run):
    """Execute the real compareRecordToDispatch(recordRequires, driveWillRun)
    through node. This function does not exist yet on the production side —
    TKT-600b-4 is what introduces the disagreement comparison this AC
    requires. Extraction is expected to raise AssertionError until it does.
    """
    source = _WORKFLOW_PATH.read_text(encoding="utf-8")
    func_src = _extract_function(source, "compareRecordToDispatch")
    driver = (
        func_src
        + "\nconsole.log(JSON.stringify(compareRecordToDispatch("
        + "JSON.parse(process.argv[2]), JSON.parse(process.argv[3]))));\n"
    )
    with tempfile.NamedTemporaryFile(
        "w", suffix=".mjs", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(driver)
        path = fh.name
    try:
        proc = subprocess.run(
            ["node", path, json.dumps(record_requires), json.dumps(drive_will_run)],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    finally:
        Path(path).unlink(missing_ok=True)
    return json.loads(proc.stdout.strip())


class TestDriveNeverReconcilesTheRecordToItself:
    def test_record_is_unchanged_apart_from_phases_that_ran(self) -> None:
        # covers: TKT-600b-4
        # angle: criterion
        """
        On a disagreement between the record's required phases and the
        phases the drive will actually run, the comparison must name both
        sides and must NOT itself write anything — asserted here as "the
        comparison is a pure read", the precondition for TKT-600b-4's
        no-write guarantee.

        RED today: compareRecordToDispatch does not exist in
        build-feature.js at all.
        """
        result = _run_compare(["python-coder", "pull-request"], ["python-coder"])

        assert result["record_requires"] == ["python-coder", "pull-request"]
        assert result["drive_will_run"] == ["python-coder"]
        assert result["disagreement"] == ["pull-request"]
        assert result["completed"] is False

    def test_a_reconciling_drive_is_detected_and_rejected(self) -> None:
        # covers: TKT-600b-4
        # angle: boundary
        """
        The cheapest fix for the observed blocker is a single write that
        rewrites the disagreeing entry to "not_needed" to match what the
        drive decided to dispatch. That is excluded by TKT-600b-4 even
        though it clears the halt and even though the ticket then "reads
        done" — it must be held red explicitly. Modelled here as: once the
        record itself has been silently rewritten to agree with the drive
        (simulating the excluded remedy), the comparison must still be able
        to tell you a reconciliation occurred by diffing the before/after
        record — which requires a `record_was_rewritten` signal this AC's
        implementation must provide.

        RED today: no such function or signal exists.
        """
        before = {"pull-request": "needed"}
        after_reconciled = {"pull-request": "not_needed"}  # the excluded remedy

        result = _run_compare(list(before.keys()), [])
        # A conforming implementation must expose enough for a caller to
        # detect that `after_reconciled` is NOT a phase-record diff limited
        # to phases that actually ran (pull-request never ran here).
        assert result["disagreement"] == ["pull-request"]
        assert before != after_reconciled  # sanity: the excluded remedy is a real edit
        assert result.get("permits_status_rewrite") is False, (
            "the comparison must never sanction rewriting a non-dispatched "
            "phase's status, even to the exclusion value"
        )

    def test_refusal_is_produced_by_consumed_control_flow(self) -> None:
        # covers: TKT-600b-4
        # angle: seam
        """
        Execute the real comparison twice with different inputs and require
        BOTH outcomes (agree / disagree) from the same function — a
        hard-wired "always refuse" implementation is indistinguishable from
        a live comparison unless both branches are demonstrated, per
        CLAUDE.md's gate/workflow rule (the fast-lane runner precedent).

        RED today: the function does not exist.
        """
        agreeing = _run_compare(["python-coder"], ["python-coder"])
        disagreeing = _run_compare(["python-coder", "pull-request"], ["python-coder"])

        assert agreeing["completed"] is True
        assert agreeing["disagreement"] == []
        assert disagreeing["completed"] is False
        assert disagreeing["disagreement"] == ["pull-request"]
