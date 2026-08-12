"""
MODULE: unit_tests/workflows/test_bo_2700_defer_epic_pr.py
GOAL: Coverage for the BO-2700 tree — /build-feature defers the pull-request phase
      for epic-member tickets so an epic opens exactly one PR (at finalize), not
      one per ticket.

Testability: templates/workflows-js/build-feature.js is a Workflow-engine script
that references injected globals (agent(), parallel()), so it is not importable /
executable at the unit layer. The load-bearing filtering decision, however, lives
in the PURE helper `selectDispatchPhases(orderedPhases, isEpicMember)`. These
tests EXECUTE that real function (extracted from the source and run under `node`)
against concrete inputs — genuinely behavioral, not grep-only (BO-2700a-1/-2/-3
and the a-1-i edge case). The call-site wiring AC (BO-2700a-4) — which call site
passes isEpicMember=true — cannot be run without the whole workflow, so it is
covered structurally, as documented in that AC.

=== Fixture-authenticity mandate (BO-2500c) ===
Reads the REAL on-disk build-feature.js. No hand-typed copy of the function.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unittest
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


class TestSelectDispatchPhasesBehavior(unittest.TestCase):
    """Behavioral tests: execute the real selectDispatchPhases via node."""

    source: str
    func_src: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = _WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.func_src = _extract_function(cls.source, "selectDispatchPhases")

    def _run_select(self, ordered_phases, is_epic_member):
        """Run the extracted selectDispatchPhases(orderedPhases, isEpicMember)."""
        driver = (
            self.func_src
            + "\nconsole.log(JSON.stringify(selectDispatchPhases("
            + "JSON.parse(process.argv[2]), JSON.parse(process.argv[3]))));\n"
        )
        with tempfile.NamedTemporaryFile(
            "w", suffix=".mjs", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(driver)
            path = fh.name
        try:
            proc = subprocess.run(
                ["node", path, json.dumps(ordered_phases), json.dumps(is_epic_member)],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
        finally:
            Path(path).unlink(missing_ok=True)
        return json.loads(proc.stdout.strip())

    _FULL = [
        {"agent": "test-writer", "status": "needed"},
        {"agent": "python-coder", "status": "needed"},
        {"agent": "commit", "status": "needed"},
        {"agent": "pull-request", "status": "needed"},
    ]

    def test_epic_member_drops_pull_request(self) -> None:
        # covers: BO-2700a-1
        result = self._run_select(self._FULL, True)
        agents = [p["agent"] for p in result]
        self.assertNotIn("pull-request", agents)
        self.assertEqual(len(result), len(self._FULL) - 1)

    def test_epic_member_retains_commit_and_non_pr_phases(self) -> None:
        # covers: BO-2700a-2
        result = self._run_select(self._FULL, True)
        agents = [p["agent"] for p in result]
        self.assertIn("commit", agents)
        for expected in ("test-writer", "python-coder", "commit"):
            self.assertIn(expected, agents)

    def test_single_ticket_preserves_all_phases(self) -> None:
        # covers: BO-2700a-3
        result = self._run_select(self._FULL, False)
        self.assertEqual(result, self._FULL)  # unchanged, pull-request retained

    def test_epic_member_noop_when_no_pull_request(self) -> None:
        # covers: BO-2700a-1-i
        no_pr = [
            {"agent": "test-writer", "status": "needed"},
            {"agent": "commit", "status": "needed"},
        ]
        result = self._run_select(no_pr, True)
        self.assertEqual(result, no_pr)  # safe no-op


class TestDispatchCallSites(unittest.TestCase):
    """Structural coverage of the call-site wiring (cannot run the full driver)."""

    source: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = _WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_epic_defers_single_ticket_does_not(self) -> None:
        # covers: BO-2700a-4
        deferred = re.findall(
            r"driveTicketPhases\(\s*worktreeTicketPath\s*,\s*true\s*\)", self.source
        )
        default = re.findall(
            r"driveTicketPhases\(\s*worktreeTicketPath\s*\)", self.source
        )
        self.assertEqual(len(deferred), 1, "exactly one (epic) call site defers the PR")
        self.assertGreaterEqual(
            len(default), 1, "single-ticket call site must not pass isEpicMember=true"
        )


if __name__ == "__main__":
    unittest.main()
