"""
MODULE: unit_tests/workflows/test_tkt_600b_4_i.py
GOAL: RED test stubs for TKT-600b-4-i — a phase that ran records its own
      outcome (status + checklist row + comment entry, atomically); that is
      the ONLY write the drive makes to a ticket's phase record. The
      permitted write set must equal the dispatched set exactly — a
      dispatched phase whose outcome goes unrecorded (under-write, BUG-23)
      is as much a violation as writing an entry for a phase that was never
      dispatched (over-write, TKT-600b-4).
COVERS: TKT-600b-4-i

Extract-and-run pattern against the real templates/workflows-js/build-feature.js,
matching the existing BO-2700 seam tests.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

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


def _run_written_entries(dispatched_phases, phase_outcomes):
    """Execute the real writtenPhaseEntries(dispatchedPhases, phaseOutcomes)
    through node. Not yet implemented on the production side — this is the
    function TKT-600b-4-i's authorship equality (dispatched set == written
    set) is expected to be expressed through.
    """
    source = _WORKFLOW_PATH.read_text(encoding="utf-8")
    func_src = _extract_function(source, "writtenPhaseEntries")
    driver = (
        func_src
        + "\nconsole.log(JSON.stringify(writtenPhaseEntries("
        + "JSON.parse(process.argv[2]), JSON.parse(process.argv[3]))));\n"
    )
    with tempfile.NamedTemporaryFile(
        "w", suffix=".mjs", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(driver)
        path = fh.name
    try:
        proc = subprocess.run(
            [
                "node",
                path,
                json.dumps(dispatched_phases),
                json.dumps(phase_outcomes),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    finally:
        Path(path).unlink(missing_ok=True)
    return json.loads(proc.stdout.strip())


class TestOnlyTheDispatchedPhaseWritesItsOwnEntry:
    def test_passing_phase_writes_its_own_entry_row_and_comment(self) -> None:
        # covers: TKT-600b-4-i
        # angle: criterion
        """
        A dispatched phase that completes successfully must move its own
        entry to "signed_off". No entry belonging to any other phase changes.

        RED today: writtenPhaseEntries does not exist in build-feature.js.
        """
        outcomes = [{"agent": "python-coder", "result": "ok"}]
        written = _run_written_entries(["python-coder"], outcomes)

        assert written == {"python-coder": "signed_off"}

    def test_non_dispatched_phase_is_neither_signed_off_nor_excluded_by_the_drive(
        self,
    ) -> None:
        # covers: TKT-600b-4-i
        # angle: boundary
        """
        For a phase the drive declined to dispatch, the write set must
        contain NEITHER the passing value NOR the exclusion value for that
        agent. Asserting only the passing value is insufficient — marking it
        "not_needed" is the more plausible mistake, since it reads as a
        correction rather than a claim (TKT-600b-4's own violation, one
        function over).

        RED today: no such function exists to make this assertion meaningful
        at all.
        """
        outcomes = [{"agent": "python-coder", "result": "ok"}]
        written = _run_written_entries(["python-coder"], outcomes)

        assert "pull-request" not in written, (
            "a non-dispatched phase must not appear in the write set at "
            f"all (neither signed_off nor not_needed); got {written!r}"
        )

    def test_written_entry_set_equals_dispatched_set(self) -> None:
        # covers: TKT-600b-4-i
        # angle: seam
        """
        Execute the real write-set function and compare its output keys
        against the dispatched set, in BOTH directions — catches the
        over-write TKT-600b-4 forbids and the under-write (BUG-23 signature)
        that leaves a dispatched phase's outcome unrecorded.

        RED today: the function does not exist.
        """
        dispatched = ["python-coder", "test-runner"]
        outcomes = [
            {"agent": "python-coder", "result": "ok"},
            {"agent": "test-runner", "result": "ok"},
        ]
        written = _run_written_entries(dispatched, outcomes)

        assert set(written.keys()) == set(dispatched), (
            f"written entry set {set(written.keys())!r} must equal the "
            f"dispatched set {set(dispatched)!r} exactly"
        )
