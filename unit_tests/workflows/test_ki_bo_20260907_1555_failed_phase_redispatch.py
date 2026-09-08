"""
MODULE: unit_tests/workflows/test_ki_bo_20260907_1555_failed_phase_redispatch.py
GOAL: Regression coverage for KI-BO-20260907-1555 — a phase recorded `failed`
      was filtered out of the dispatch set, so no later drive could ever re-run
      it. `failed` was a write-only terminal state.

Testability: templates/workflows-js/build-{ticket,feature}.js are Workflow-engine
scripts that reference injected globals (agent(), parallel()), so they are not
importable / executable at the unit layer. The load-bearing decision, however,
now lives in the PURE helper `selectDispatchableByStatus(orderedPhases)` — which
is exactly why it was extracted from an inline filter. These tests EXECUTE that
real function (extracted from the source and run under `node`) against concrete
inputs, following the pattern established by test_bo_2700_defer_epic_pr.py.

Two of the cases are deliberately NOT behavioral, and say so: the call-site
wiring (which call site passes the result to sortByCanonicalPriority) cannot be
run without the whole workflow, so it is asserted structurally — the same
carve-out BO-2700a-4 documents.

=== Fixture-authenticity mandate (BO-2500c) ===
Reads the REAL on-disk workflow files. No hand-typed copy of the function.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_WORKFLOWS = _REPO_ROOT / "templates" / "workflows-js"
_BUILD_TICKET = _WORKFLOWS / "build-ticket.js"
_BUILD_FEATURE = _WORKFLOWS / "build-feature.js"

_FUNC = "selectDispatchableByStatus"


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


def _run_select(func_src: str, ordered_phases):
    """Execute the extracted selectDispatchableByStatus under node."""
    driver = (
        func_src
        + f"\nconsole.log(JSON.stringify({_FUNC}(JSON.parse(process.argv[2]))));\n"
    )
    with tempfile.NamedTemporaryFile(
        "w", suffix=".mjs", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(driver)
        path = fh.name
    try:
        proc = subprocess.run(
            ["node", path, json.dumps(ordered_phases)],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    finally:
        Path(path).unlink(missing_ok=True)
    return json.loads(proc.stdout.strip())


def _statuses(phases):
    return sorted(p["status"] for p in phases)


def _agents(phases):
    return sorted(p["agent"] for p in phases)


class _SelectDispatchableByStatusContract:
    """Behavioral contract, run against BOTH twins via the subclasses below."""

    workflow_path: Path
    source: str
    func_src: str

    @classmethod
    def setUpClass(cls) -> None:
        source = cls.workflow_path.read_text(encoding="utf-8")
        cls.func_src = _extract_function(source, _FUNC)
        cls.source = source

    # -- the defect itself --------------------------------------------------

    def test_a_failed_phase_is_dispatched(self):
        """THE REGRESSION. Before the fix this returned [] and the drive was a no-op."""
        # covers: KI-BO-20260907-1555
        # angle: behavioral
        got = _run_select(
            self.func_src, [{"agent": "python-coder", "status": "failed"}]
        )
        self.assertEqual(
            _agents(got),
            ["python-coder"],
            "a phase recorded `failed` must be re-dispatchable; filtering it out "
            "makes `failed` a write-only terminal state that no drive can clear",
        )

    def test_ticket_36_shape_dispatches_rather_than_doing_nothing(self):
        """GE-120 ticket 36's real frontmatter: four failed, zero needed."""
        # covers: KI-BO-20260907-1555
        # angle: behavioral
        got = _run_select(
            self.func_src,
            [
                {"agent": "ac-fulfillment-gate", "status": "failed"},
                {"agent": "ac-validator", "status": "failed"},
                {"agent": "commit", "status": "failed"},
                {"agent": "pull-request", "status": "not_needed"},
                {"agent": "python-coder", "status": "failed"},
                {"agent": "test-runner", "status": "failed"},
                {"agent": "test-writer", "status": "signed_off"},
            ],
        )
        self.assertEqual(
            _agents(got),
            [
                "ac-fulfillment-gate",
                "ac-validator",
                "commit",
                "python-coder",
                "test-runner",
            ],
            "the exact ticket that surfaced this must now dispatch its five "
            "failed phases instead of dispatching nothing",
        )

    # -- the boundaries the fix must NOT cross ------------------------------

    def test_signed_off_is_not_redispatched(self):
        """Widening to signed_off would re-run passed work on every drive."""
        # covers: KI-BO-20260907-1555
        # angle: negative-control
        got = _run_select(
            self.func_src, [{"agent": "test-writer", "status": "signed_off"}]
        )
        self.assertEqual(got, [], "signed_off is terminal and must not be re-run")

    def test_not_needed_is_not_redispatched(self):
        """The ticket declared the phase inapplicable; that must be honoured."""
        # covers: KI-BO-20260907-1555
        # angle: negative-control
        got = _run_select(
            self.func_src, [{"agent": "pull-request", "status": "not_needed"}]
        )
        self.assertEqual(got, [], "not_needed must not be re-run")

    def test_needed_still_dispatched(self):
        """The pre-existing behaviour must survive the change."""
        # covers: KI-BO-20260907-1555
        # angle: regression
        got = _run_select(
            self.func_src, [{"agent": "python-coder", "status": "needed"}]
        )
        self.assertEqual(_agents(got), ["python-coder"])

    def test_mixed_set_selects_exactly_needed_and_failed(self):
        """All four states at once — the full truth table in one call."""
        # covers: KI-BO-20260907-1555
        # angle: behavioral
        got = _run_select(
            self.func_src,
            [
                {"agent": "a", "status": "needed"},
                {"agent": "b", "status": "failed"},
                {"agent": "c", "status": "signed_off"},
                {"agent": "d", "status": "not_needed"},
            ],
        )
        self.assertEqual(_agents(got), ["a", "b"])
        self.assertEqual(_statuses(got), ["failed", "needed"])

    # -- robustness ---------------------------------------------------------

    def test_absent_and_malformed_input_does_not_throw(self):
        """A null list or a null entry must not crash the dispatcher."""
        # covers: KI-BO-20260907-1555
        # angle: error-path
        self.assertEqual(_run_select(self.func_src, None), [])
        self.assertEqual(_run_select(self.func_src, []), [])
        got = _run_select(
            self.func_src, [None, {"agent": "a", "status": "failed"}]
        )
        self.assertEqual(_agents(got), ["a"])

    def test_unknown_status_is_not_dispatched(self):
        """Fail closed on a status outside the enum rather than guessing."""
        # covers: KI-BO-20260907-1555
        # angle: error-path
        got = _run_select(
            self.func_src, [{"agent": "a", "status": "in_progress"}]
        )
        self.assertEqual(got, [], "an unrecognised status must not be dispatched")

    # -- call-site wiring (structural — documented carve-out) ---------------

    def test_the_dispatch_set_actually_consumes_this_function(self):
        """Structural: a pure helper nothing calls would pass every test above."""
        # covers: KI-BO-20260907-1555
        # angle: structural
        self.assertIn(
            f"{_FUNC}(orderedPhases)",
            self.source,
            f"{self.workflow_path.name} defines {_FUNC} but never applies it to "
            "orderedPhases — the helper would be dead code and the inline filter "
            "would still be live",
        )

    def test_the_old_inline_filter_is_gone(self):
        """Structural: the defect must not survive alongside the fix."""
        # covers: KI-BO-20260907-1555
        # angle: structural
        self.assertNotIn(
            'orderedPhases.filter((p) => p.status === "needed")',
            self.source,
            f"{self.workflow_path.name} still contains the needed-only dispatch "
            "filter this fix replaces",
        )


class TestBuildTicketDispatchableByStatus(
    _SelectDispatchableByStatusContract, unittest.TestCase
):
    workflow_path = _BUILD_TICKET


class TestBuildFeatureDispatchableByStatus(
    _SelectDispatchableByStatusContract, unittest.TestCase
):
    workflow_path = _BUILD_FEATURE


class TestTwinsStayInSync(unittest.TestCase):
    """The two drivers must not drift — this defect existed in both."""

    def test_both_twins_define_an_identical_predicate(self):
        # covers: KI-BO-20260907-1555
        # angle: structural
        ticket = _extract_function(
            _BUILD_TICKET.read_text(encoding="utf-8"), _FUNC
        )
        feature = _extract_function(
            _BUILD_FEATURE.read_text(encoding="utf-8"), _FUNC
        )
        self.assertEqual(
            ticket,
            feature,
            "build-ticket.js and build-feature.js carry divergent copies of "
            f"{_FUNC}; the original defect was present in both, and a fix to "
            "one is not a fix to the other",
        )


if __name__ == "__main__":
    unittest.main()
