"""
Tests for the test-requirements guard.

Verifies:
- AC-1 (BO-2000e-1): authoring guard rejects a code ticket with empty/absent
  Test Requirements, emitting an actionable reason.
- AC-2 (BO-2000e-1-i): a non-code ticket (docs-only/config-only) is NOT
  blocked — the documented skip behaviour is preserved.
- AC-3 (BO-2000e-2): the deterministic dispatch (build-ticket.js) refuses to
  dispatch the coder phase for a code ticket whose Test Requirements is
  empty/absent, surfacing a structured blocker rather than proceeding.

These are test-FIRST stubs. The authoring-guard module
(scripts/commit_guardian/check_ticket_test_requirements.py) does not yet exist.
Tests must be RED on first run.

Covers: BO-2000e-1, BO-2000e-1-i, BO-2000e-2
"""
from __future__ import annotations

import os
import re
import sys
import unittest

# ---------------------------------------------------------------------------
# Path bootstrap — make scripts/ importable from the worktree root
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_BUILD_TICKET_JS = os.path.join(
    _REPO_ROOT, "templates", "workflows-js", "build-ticket.js"
)

# ---------------------------------------------------------------------------
# Ticket fixture builders
# These represent realistic ticket content as it would appear on disk.
# ---------------------------------------------------------------------------

_CODE_TICKET_NO_TEST_REQUIREMENTS = """\
---
title: "Example code ticket"
status: todo
agents:
  python-coder: needed
  test-writer: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
---

# Example code ticket

## Acceptance Criteria

- [ ] AC-1: does something.

## Comments

_(no comments yet)_
"""

_CODE_TICKET_EMPTY_TESTS_ARRAY = """\
---
title: "Example code ticket with empty tests"
status: todo
agents:
  python-coder: needed
  test-writer: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
---

# Example code ticket with empty tests

## Test Requirements

```yaml
tests: []
```

## Comments

_(no comments yet)_
"""

_CODE_TICKET_WITH_TEST_REQUIREMENTS = """\
---
title: "Example code ticket with populated tests"
status: todo
agents:
  python-coder: needed
  test-writer: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
---

# Example code ticket with populated tests

## Test Requirements

```yaml
tests:
  - name: test_something
    file: unit_tests/foo/test_something.py
    covers: [AC-1]
    asserts: "the guard rejects an invalid input"
```

## Comments

_(no comments yet)_
"""

_NON_CODE_TICKET_DOCS_ONLY = """\
---
title: "Docs-only ticket"
status: todo
agents:
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
---

# Docs-only ticket

## Acceptance Criteria

- [ ] AC-1: document something.

## Comments

_(no comments yet)_
"""

_NON_CODE_TICKET_CONFIG_ONLY = """\
---
title: "Config-only ticket"
status: todo
agents:
  pr-reviewer: needed
  commit: needed
---

# Config-only ticket

## Acceptance Criteria

- [ ] AC-1: update some configuration.

## Comments

_(no comments yet)_
"""


# ---------------------------------------------------------------------------
# AC-1 / BO-2000e-1 — authoring guard rejects code ticket without test reqs
# ---------------------------------------------------------------------------


class TestAuthoringBlocksCodeTicketWithoutTestRequirements(unittest.TestCase):
    """AC-1 (BO-2000e-1): authoring guard rejects a code ticket with empty/absent
    Test Requirements and emits an actionable reason."""

    def test_authoring_blocks_code_ticket_without_test_requirements(self):
        # covers: BO-2000e-1
        """Guard must return (False, <non-empty reason>) for a code ticket
        that has NO ## Test Requirements section at all."""
        from scripts.commit_guardian.check_ticket_test_requirements import (  # noqa: PLC0415
            check_ticket_has_test_requirements,
        )

        ok, reason = check_ticket_has_test_requirements(
            _CODE_TICKET_NO_TEST_REQUIREMENTS
        )

        self.assertFalse(
            ok,
            "The authoring guard must return False for a code ticket with no "
            "## Test Requirements section.",
        )
        self.assertIsInstance(reason, str, "reason must be a string")
        self.assertTrue(
            len(reason) > 0,
            "reason must be non-empty so the author has actionable guidance.",
        )
        self.assertRegex(
            reason,
            re.compile(r"test.requirements|test requirements", re.IGNORECASE),
            "reason must mention 'Test Requirements' so the author knows what to add.",
        )

    def test_authoring_blocks_code_ticket_with_empty_tests_array(self):
        # covers: BO-2000e-1
        """Guard must return (False, <reason>) for a code ticket with
        ## Test Requirements present but tests: [] (empty array)."""
        from scripts.commit_guardian.check_ticket_test_requirements import (  # noqa: PLC0415
            check_ticket_has_test_requirements,
        )

        ok, reason = check_ticket_has_test_requirements(
            _CODE_TICKET_EMPTY_TESTS_ARRAY
        )

        self.assertFalse(
            ok,
            "The authoring guard must return False for a code ticket with "
            "## Test Requirements present but tests: [] (empty array).",
        )
        self.assertTrue(
            len(reason) > 0,
            "reason must be non-empty when tests array is empty.",
        )


# ---------------------------------------------------------------------------
# AC-2 / BO-2000e-1-i — non-code ticket is NOT blocked
# ---------------------------------------------------------------------------


class TestAuthoringAllowsNonCodeTicket(unittest.TestCase):
    """AC-2 (BO-2000e-1-i): a docs-only / config-only ticket with no coder
    needed is NOT blocked — the documented skip behaviour is preserved."""

    def test_authoring_allows_docs_only_ticket(self):
        # covers: BO-2000e-1-i
        """Guard must return (True, '') for a docs-only ticket (no coder needed)."""
        from scripts.commit_guardian.check_ticket_test_requirements import (  # noqa: PLC0415
            check_ticket_has_test_requirements,
        )

        ok, reason = check_ticket_has_test_requirements(
            _NON_CODE_TICKET_DOCS_ONLY
        )

        self.assertTrue(
            ok,
            "The authoring guard must return True for a docs-only ticket "
            "(no coder agent is needed). "
            f"Reason returned: {reason!r}",
        )

    def test_authoring_allows_config_only_ticket(self):
        # covers: BO-2000e-1-i
        """Guard must return (True, '') for a config-only ticket (no coder needed)."""
        from scripts.commit_guardian.check_ticket_test_requirements import (  # noqa: PLC0415
            check_ticket_has_test_requirements,
        )

        ok, reason = check_ticket_has_test_requirements(
            _NON_CODE_TICKET_CONFIG_ONLY
        )

        self.assertTrue(
            ok,
            "The authoring guard must return True for a config-only ticket "
            "(no coder agent is needed). "
            f"Reason returned: {reason!r}",
        )

    def test_authoring_allows_code_ticket_with_populated_tests(self):
        # covers: BO-2000e-1
        # covers: BO-2000e-1-i
        """Guard must return (True, '') when a code ticket has a populated
        ## Test Requirements section — this is the happy path."""
        from scripts.commit_guardian.check_ticket_test_requirements import (  # noqa: PLC0415
            check_ticket_has_test_requirements,
        )

        ok, reason = check_ticket_has_test_requirements(
            _CODE_TICKET_WITH_TEST_REQUIREMENTS
        )

        self.assertTrue(
            ok,
            "The authoring guard must return True for a code ticket that has "
            "a populated ## Test Requirements section. "
            f"Reason returned: {reason!r}",
        )


# ---------------------------------------------------------------------------
# AC-3 / BO-2000e-2 — build-ticket.js dispatch refusal
# ---------------------------------------------------------------------------


class TestDispatchRefusesCoderWithoutTestRequirements(unittest.TestCase):
    """AC-3 (BO-2000e-2): build-ticket.js must refuse to dispatch the coder
    phase for a code ticket whose ## Test Requirements is empty/absent,
    surfacing a structured blocker rather than proceeding."""

    def _read_build_ticket_js(self) -> str:
        try:
            with open(_BUILD_TICKET_JS, encoding="utf-8") as fh:
                return fh.read()
        except OSError as exc:
            self.skipTest(f"build-ticket.js not readable: {exc}")
            return ""

    def test_dispatch_has_test_requirements_check(self):
        # covers: BO-2000e-2
        """build-ticket.js must contain a reference to Test Requirements as
        part of the coder dispatch guard."""
        js_source = self._read_build_ticket_js()

        self.assertRegex(
            js_source,
            re.compile(
                r"test.?requirements|testRequirements|Test Requirements",
                re.IGNORECASE,
            ),
            "build-ticket.js must contain a reference to 'Test Requirements' "
            "as part of the coder dispatch guard (BO-2000e-2). "
            "The guard was not found in the source.",
        )

    def test_dispatch_emits_structured_blocker_not_proceeds(self):
        # covers: BO-2000e-2
        """build-ticket.js must connect the test-requirements check to a
        structured blocker / refusal (not silently dispatch the coder)."""
        js_source = self._read_build_ticket_js()

        # Guard must appear near a blocker/refusal outcome.
        # Accept either ordering: testReqs → blocker OR blocker → testReqs.
        forward_pattern = re.compile(
            r"(test.?requirements|testRequirements|Test Requirements)"
            r".{0,400}"
            r"(blocker|structured_blocker|structured blocker|refuse|reject|block)",
            re.IGNORECASE | re.DOTALL,
        )
        reverse_pattern = re.compile(
            r"(blocker|structured_blocker|refuse|reject)"
            r".{0,400}"
            r"(test.?requirements|testRequirements|Test Requirements)",
            re.IGNORECASE | re.DOTALL,
        )
        has_guard = bool(forward_pattern.search(js_source)) or bool(
            reverse_pattern.search(js_source)
        )
        self.assertTrue(
            has_guard,
            "build-ticket.js must connect the Test Requirements check to a "
            "structured blocker / refusal when dispatching a coder phase "
            "(BO-2000e-2). "
            "Neither 'testRequirements…blocker' nor 'blocker…testRequirements' "
            "pattern was found within 400 characters of each other.",
        )


# ---------------------------------------------------------------------------
# AC-3 (behavioral) / BO-2000e-2 — EXECUTE the dispatch guard
#
# The two tests above grep build-ticket.js for a string. That cannot distinguish
# a working guard from a broken one: both the deadlocking version (which read a
# stale pre-drive snapshot and blocked the coder even after test-writer wrote a
# verified-red suite) and the fixed version contain "Test Requirements" next to
# "blocker". Per CLAUDE.md "Gate / Workflow ACs — Verify Behaviorally, Not by
# Grep", these tests run the real script under stubbed workflow globals and
# assert on which phase agents it actually dispatched.
# ---------------------------------------------------------------------------

_HARNESS = os.path.join(
    os.path.dirname(__file__), "harness_build_ticket_guard.mjs"
)


class TestDispatchGuardBehavior(unittest.TestCase):
    """AC-3 (BO-2000e-2), behavioral: the coder guard must open when tests
    demonstrably exist and stay closed when they do not."""

    def _run_scenario(self, **scenario) -> dict:
        """Execute build-ticket.js against stubbed globals; return
        {"dispatched": [...], "result": {...}}."""
        import json  # noqa: PLC0415
        import shutil  # noqa: PLC0415
        import subprocess  # noqa: PLC0415

        if shutil.which("node") is None:
            self.skipTest("node is not available on PATH")

        try:
            proc = subprocess.run(
                ["node", _HARNESS, _BUILD_TICKET_JS, json.dumps(scenario)],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self.fail(f"harness invocation failed: {exc}")

        if proc.returncode != 0:
            self.fail(
                f"harness exited {proc.returncode}.\n"
                f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
            )
        return json.loads(proc.stdout)

    def test_coder_dispatched_when_test_writer_reports_tests_written(self):
        # covers: BO-2000e-2
        # covers: BO-2000e-2-i
        """The deadlock regression: ## Test Requirements is absent, but
        test-writer derived tests from the AC store and wrote them. The coder
        MUST run — blocking here strands every AC-generated ticket."""
        out = self._run_scenario(
            has_test_requirements=False,
            phases=["test-writer", "python-coder"],
            test_writer_result={
                "status": "ok",
                "tests_written": ["unit_tests/test_bp_900a_1.py"],
                "red_baseline_verified": True,
            },
        )

        self.assertIn(
            "python-coder",
            out["dispatched"],
            "python-coder must be dispatched after test-writer reports it wrote "
            "test files, even though ## Test Requirements is absent. Blocking "
            "here is the deadlock that made every AC-generated ticket unbuildable.",
        )
        self.assertEqual(out["result"]["status"], "ok")

    def test_coder_blocked_when_test_writer_wrote_nothing(self):
        # covers: BO-2000e-2
        # covers: BO-2000e-2-iii
        """Fail-closed: test-writer self-skipped (empty tests_written), so the
        original phantom-test protection must still fire."""
        out = self._run_scenario(
            has_test_requirements=False,
            phases=["test-writer", "python-coder"],
            test_writer_result={"status": "ok", "tests_written": []},
        )

        self.assertNotIn(
            "python-coder",
            out["dispatched"],
            "python-coder must NOT be dispatched when test-writer wrote no tests.",
        )
        self.assertEqual(out["result"]["status"], "blocked")

    def test_coder_blocked_when_test_writer_omits_evidence_field(self):
        # covers: BO-2000e-2
        # covers: BO-2000e-2-iii
        """Absent evidence must never read as satisfied evidence. A phase agent
        on an older template that omits tests_written entirely must leave the
        guard closed, not open it by default."""
        out = self._run_scenario(
            has_test_requirements=False,
            phases=["test-writer", "python-coder"],
            test_writer_result={"status": "ok"},
        )

        self.assertNotIn(
            "python-coder",
            out["dispatched"],
            "A missing tests_written field must leave the guard CLOSED.",
        )
        self.assertEqual(out["result"]["status"], "blocked")

    def test_coder_blocked_when_no_test_writer_phase_scheduled(self):
        # covers: BO-2000e-2
        # covers: BO-2000e-2-iii
        """No ## Test Requirements and no test-writer phase at all — the
        original BO-2000e-2 refusal, unchanged."""
        out = self._run_scenario(
            has_test_requirements=False,
            phases=["python-coder"],
            test_writer_result={"status": "ok"},
        )

        self.assertNotIn("python-coder", out["dispatched"])
        self.assertEqual(out["result"]["status"], "blocked")

    def test_coder_dispatched_on_resume_when_prior_tests_exist_on_disk(self):
        # covers: BO-2000e-2
        # covers: BO-2000e-2-ii
        """Resume case: a previous drive's test-writer is already signed_off, so
        it is no longer in the needed set and cannot re-supply route 2 evidence.
        The tests it wrote still exist on disk, so the coder MUST run — otherwise
        the ticket deadlocks permanently on every re-run."""
        out = self._run_scenario(
            has_test_requirements=False,
            existing_test_files=["unit_tests/test_bp_900a_1.py"],
            phases=["python-coder"],
            test_writer_result={"status": "ok"},
        )

        self.assertIn(
            "python-coder",
            out["dispatched"],
            "python-coder must be dispatched on resume when a prior drive's test "
            "files still exist on disk.",
        )
        self.assertEqual(out["result"]["status"], "ok")

    def test_coder_blocked_on_resume_when_prior_tests_are_gone(self):
        # covers: BO-2000e-2
        # covers: BO-2000e-2-iii
        """Route 3 is evidence-based, not status-based: if the previously written
        test files no longer exist, the planner reports none and the guard closes."""
        out = self._run_scenario(
            has_test_requirements=False,
            existing_test_files=[],
            phases=["python-coder"],
            test_writer_result={"status": "ok"},
        )

        self.assertNotIn("python-coder", out["dispatched"])
        self.assertEqual(out["result"]["status"], "blocked")

    def test_coder_dispatched_when_ticket_declares_test_requirements(self):
        # covers: BO-2000e-2
        """Route 1 is untouched: a populated ## Test Requirements section still
        satisfies the guard on its own."""
        out = self._run_scenario(
            has_test_requirements=True,
            phases=["python-coder"],
            test_writer_result={"status": "ok"},
        )

        self.assertIn("python-coder", out["dispatched"])
        self.assertEqual(out["result"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
