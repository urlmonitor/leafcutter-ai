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


if __name__ == "__main__":
    unittest.main()
