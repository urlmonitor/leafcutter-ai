"""
MODULE: test_check_ac_count_limits
GOAL: Unit tests for the ticket-body AC count hook at
    templates/scripts/commit_guardian/hooks/check_ac_limits.py.
    Covers _analyse_ticket for v1-flat (no ## Agent Contracts) ticket format,
    the OSError-guard semantics of result.skipped, the ac_limit_override path,
    the JSON payload shape, and a regression guard for the v2 Agent Contracts
    path.
BUSINESS CONTEXT: The hook enforces a 20-total AC cap per ticket. For v1-flat
    tickets (no ## Agent Contracts section), the current code silently skips the
    check by setting result.skipped=True and returning early. These tests guard
    the fix that enforces the total cap on v1-flat tickets and restricts
    skipped=True to OSError only.
ARCHITECTURE: Uses importlib to load the hooks/ module directly from its
    canonical source path, bypassing the build pipeline. Tests are unit-level
    (no subprocess), run against real temp files, and complete in < 5 seconds.

NOTE: This file tests a DIFFERENT hook from test_check_ac_limits.py.
  - test_check_ac_limits.py → templates/scripts/commit_guardian/check_ac_limits.py
                              (the AC tree-depth hook)
  - THIS file         → templates/scripts/commit_guardian/hooks/check_ac_limits.py
                              (the ticket-body AC count hook)
"""

from __future__ import annotations

import importlib.util
import io
import os
import pathlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOK_SCRIPT = (
    _REPO_ROOT
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "hooks"
    / "check_ac_limits.py"
)

# Load the ticket-body AC count hook module directly via importlib to avoid
# package import issues (the hook is a standalone file, not a proper package).
# The module must be added to sys.modules before exec_module so that the
# @dataclass decorator can resolve the module namespace correctly (Python 3.12).
try:
    _MODULE_NAME = "check_ac_count_limits_test_shim"
    _spec = importlib.util.spec_from_file_location(_MODULE_NAME, _HOOK_SCRIPT)
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules[_MODULE_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    _analyse_ticket = _mod._analyse_ticket
    _has_override = _mod._has_override
    _extract_agent_contracts_block = _mod._extract_agent_contracts_block
    _count_acs_per_agent = _mod._count_acs_per_agent
    _count_total_acs = _mod._count_total_acs
    _build_json_payload = _mod._build_json_payload
    TicketResult = _mod.TicketResult
    _MAX_ACS_TOTAL = _mod._MAX_ACS_TOTAL
    _IMPORT_OK = True
except (
    FileNotFoundError,
    AttributeError,
    ImportError,
    SyntaxError,
    TypeError,
    ValueError,
) as _exc:
    _IMPORT_OK = False
    _IMPORT_ERROR = str(_exc)


def _requires_import(func):
    """Skip test if the hook module failed to import.

    Args:
        func: Test function to conditionally skip.

    Returns:
        The original function, or a skipped version if the module failed to load.
    """
    if not _IMPORT_OK:
        return unittest.skip(
            f"check_ac_limits (hooks/) not importable: {_IMPORT_ERROR}"
        )(func)
    return func


# ---------------------------------------------------------------------------
# Ticket body builders
# ---------------------------------------------------------------------------


def _make_v1_flat_ticket(num_acs: int, override: bool = False) -> str:
    """Build a minimal v1-flat ticket body with num_acs unchecked AC lines.

    The resulting ticket has NO ## Agent Contracts section (v1 flat format).

    Args:
        num_acs: Number of `- [ ] AC-N:` lines to include.
        override: If True, insert `ac_limit_override: true` into the frontmatter.

    Returns:
        Full ticket file content as a string, suitable for writing to disk.
    """
    ac_lines = "\n".join(
        f"- [ ] AC-{i}: Acceptance criterion {i}" for i in range(1, num_acs + 1)
    )
    override_line = "ac_limit_override: true\n" if override else ""
    return (
        f"---\ntitle: Test ticket\n{override_line}---\n\n"
        f"## Acceptance Criteria\n\n{ac_lines}\n"
    )


def _make_v2_ticket(agent_name: str, num_acs: int) -> str:
    """Build a minimal v2 ticket with a ## Agent Contracts section.

    Args:
        agent_name: Agent-subsection heading (e.g. 'python-coder').
        num_acs: Number of AC lines to place in the agent subsection.

    Returns:
        Full ticket file content as a string, suitable for writing to disk.
    """
    ac_lines = "\n".join(
        f"- [ ] AC-{i}: Acceptance criterion {i}" for i in range(1, num_acs + 1)
    )
    return (
        f"---\ntitle: Test ticket\n---\n\n"
        f"## Acceptance Criteria\n\n(See Agent Contracts section.)\n\n"
        f"## Agent Contracts\n\n"
        f"### {agent_name}\n\n{ac_lines}\n\n"
        f"## Sign-offs\n"
    )


# ---------------------------------------------------------------------------
# Tests: v1-flat AC count enforcement
# ---------------------------------------------------------------------------


class TestV1FlatAcCountEnforcement(unittest.TestCase):
    """Tests for _analyse_ticket on v1-flat (no ## Agent Contracts) tickets.

    All tests in this class (except test_v2_agent_contracts_path_regression)
    are designed to be RED against the current hook code, because the current
    code sets result.skipped=True whenever ## Agent Contracts is absent.
    """

    @_requires_import
    def test_v1_flat_over_20_acs_not_skipped(self) -> None:
        # covers: UNKNOWN
        """AC-1: v1-flat ticket with 21 AC lines must not be skipped and must violate the total cap.

        Must implement: _analyse_ticket must count _AC_LINE_RE matches across
        the full body when ## Agent Contracts is absent, set skipped=False,
        set total_ac_count=21, and set total_violation=True when count > 20.
        Do NOT set skipped=True on the absent-contracts path.

        RED with current code: current _analyse_ticket sets skipped=True and
        returns without counting ACs whenever contracts_block is None.
        """
        content = _make_v1_flat_ticket(num_acs=21)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ticket_path = root / "tickets" / "test_flat_over.md"
            ticket_path.parent.mkdir(parents=True, exist_ok=True)
            ticket_path.write_text(content, encoding="utf-8")

            result = _analyse_ticket("tickets/test_flat_over.md", root)

        self.assertFalse(
            result.skipped,
            "v1-flat ticket with 21 ACs must NOT be skipped (skipped=True reserved for OSError only)",
        )
        self.assertEqual(
            result.total_ac_count,
            21,
            f"total_ac_count must be 21 for a v1-flat ticket with 21 AC lines, got {result.total_ac_count}",
        )
        self.assertTrue(
            result.total_violation,
            "total_violation must be True when 21 ACs exceed the 20-total cap",
        )

    @_requires_import
    def test_v1_flat_within_20_acs_passes(self) -> None:
        # covers: UNKNOWN
        """AC-2: v1-flat ticket with exactly 20 AC lines must produce no violation and not be skipped.

        Must implement: when ## Agent Contracts is absent and AC count <= 20,
        result.skipped must be False, result.total_violation must be False,
        and result.violations must be empty.

        RED with current code: current code sets skipped=True instead of
        counting ACs, so the skipped=False assertion fails.
        """
        content = _make_v1_flat_ticket(num_acs=20)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ticket_path = root / "tickets" / "test_flat_within.md"
            ticket_path.parent.mkdir(parents=True, exist_ok=True)
            ticket_path.write_text(content, encoding="utf-8")

            result = _analyse_ticket("tickets/test_flat_within.md", root)

        self.assertFalse(
            result.skipped,
            "v1-flat ticket with exactly 20 ACs must NOT be skipped",
        )
        self.assertFalse(
            result.total_violation,
            "total_violation must be False when 20 ACs are exactly at the cap (not over)",
        )
        self.assertEqual(
            result.violations,
            [],
            "violations list must be empty for a within-cap v1-flat ticket",
        )

    @_requires_import
    def test_oserror_sets_skipped_not_missing_contracts(self) -> None:
        # covers: UNKNOWN
        """AC-6: skipped=True occurs ONLY on OSError; absent ## Agent Contracts must not set skipped=True.

        Part 1 (guards current behaviour): When Path.read_text raises OSError,
        result.skipped must be True. Expected to pass with both old and new code.

        Part 2 (the fix target): When the ticket file is readable but has no
        ## Agent Contracts section, result.skipped must be False after the fix.
        This assertion FAILS against the current code, which sets skipped=True
        whenever contracts_block is None.
        """
        # Part 1: OSError → skipped=True (already correct in current code)
        with patch.object(
            pathlib.Path, "read_text", side_effect=OSError("simulated IO failure")
        ):
            result_oserror = _analyse_ticket("tickets/dummy.md", Path("/fake/root"))

        self.assertTrue(
            result_oserror.skipped,
            "OSError while reading a ticket file must set result.skipped=True",
        )

        # Part 2: Readable file with no ## Agent Contracts → skipped must be False
        # (FAILS against current code — this is the correct RED state)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ticket_path = root / "tickets" / "no_contracts.md"
            ticket_path.parent.mkdir(parents=True, exist_ok=True)
            ticket_path.write_text(
                (
                    "---\ntitle: Minimal v1 ticket\n---\n\n"
                    "## Acceptance Criteria\n\nNo AC lines here — just prose.\n"
                ),
                encoding="utf-8",
            )
            result_no_contracts = _analyse_ticket("tickets/no_contracts.md", root)

        self.assertFalse(
            result_no_contracts.skipped,
            (
                "A readable ticket with no ## Agent Contracts section must NOT set "
                "skipped=True. skipped=True must be reserved exclusively for OSError."
            ),
        )

    @_requires_import
    def test_v1_flat_override_warns_not_blocks(self) -> None:
        # covers: UNKNOWN
        """AC-3: v1-flat ticket with >20 ACs and ac_limit_override: true must set override_active=True.

        The hook must not block (override_active=True suppresses the violation
        gate in the caller). After the fix, total_ac_count must also be populated
        with the flat AC count so that the override warning can identify the excess.

        Partial RED with current code: override_active=True assertion PASSES
        (the override branch fires) but total_ac_count=0 because the current code
        short-circuits after finding no Agent Contracts block and does not count
        the flat ACs. The total_ac_count assertion FAILS.
        """
        content = _make_v1_flat_ticket(num_acs=21, override=True)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ticket_path = root / "tickets" / "override_ticket.md"
            ticket_path.parent.mkdir(parents=True, exist_ok=True)
            ticket_path.write_text(content, encoding="utf-8")

            result = _analyse_ticket("tickets/override_ticket.md", root)

        self.assertTrue(
            result.override_active,
            "override_active must be True when frontmatter contains ac_limit_override: true",
        )
        self.assertEqual(
            result.total_ac_count,
            21,
            (
                "total_ac_count must be 21 (the flat AC count) even when override is active "
                f"so the warning emission can identify the excess; got {result.total_ac_count}"
            ),
        )

    @_requires_import
    def test_json_payload_shape_v1_flat_violation(self) -> None:
        # covers: UNKNOWN
        """AC-4: JSON payload for a v1-flat total violation has a 'total' violation with no per_agent entries.

        Flow: _analyse_ticket on a v1-flat 21-AC ticket → _build_json_payload.
        Assertions:
          - payload['violations'] has exactly 1 ticket entry (one ticket blocked).
          - That entry's inner violations list contains a 'total' type entry.
          - That entry's inner violations list contains no 'per_agent' type entries.

        RED with current code: _analyse_ticket sets skipped=True so has_violations
        is False; _build_json_payload skips the entry → payload['violations'] is
        empty → assertEqual(1) fails.
        """
        content = _make_v1_flat_ticket(num_acs=21)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ticket_path = root / "tickets" / "payload_test.md"
            ticket_path.parent.mkdir(parents=True, exist_ok=True)
            ticket_path.write_text(content, encoding="utf-8")

            result = _analyse_ticket("tickets/payload_test.md", root)

        payload = _build_json_payload([result])

        self.assertEqual(
            payload["hook"],
            "check_ac_limits",
            f"payload 'hook' must be 'check_ac_limits', got {payload['hook']!r}",
        )
        self.assertEqual(
            payload["fix_agent"],
            "it-po",
            f"payload 'fix_agent' must be 'it-po', got {payload['fix_agent']!r}",
        )
        self.assertEqual(
            len(payload["violations"]),
            1,
            (
                f"Expected 1 ticket entry in payload violations for the v1-flat total "
                f"violation; got {len(payload['violations'])}. "
                "Currently FAILS because _analyse_ticket skips v1-flat tickets, "
                "leaving payload violations empty."
            ),
        )
        ticket_entry = payload["violations"][0]
        inner = ticket_entry["violations"]
        inner_types = [v["type"] for v in inner]
        self.assertIn(
            "total",
            inner_types,
            f"Expected a 'total' violation type in the inner violations list, got: {inner_types}",
        )
        self.assertNotIn(
            "per_agent",
            inner_types,
            (
                "v1-flat ticket violations must contain no 'per_agent' entries "
                f"(per-agent cap not applied on flat path); got types: {inner_types}"
            ),
        )


# ---------------------------------------------------------------------------
# Regression guard: v2 Agent Contracts path
# ---------------------------------------------------------------------------


class TestV2AgentContractsRegression(unittest.TestCase):
    """Regression guard: the v2 Agent Contracts path must be unaffected by the v1-flat fix."""

    @_requires_import
    def test_v2_agent_contracts_path_regression(self) -> None:
        # covers: UNKNOWN
        """AC-5: Ticket with ## Agent Contracts section uses per-agent counting — no regression.

        A ticket with a ### python-coder subsection of 3 ACs must produce:
          - per_agent == {'python-coder': 3}
          - total_ac_count == 3
          - skipped == False
          - total_violation == False

        This test is expected to PASS with the current code (before the fix) and
        must remain GREEN after the fix. It guards against over-broad changes
        that accidentally break the existing v2 Agent Contracts path.
        """
        content = _make_v2_ticket(agent_name="python-coder", num_acs=3)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ticket_path = root / "tickets" / "v2_ticket.md"
            ticket_path.parent.mkdir(parents=True, exist_ok=True)
            ticket_path.write_text(content, encoding="utf-8")

            result = _analyse_ticket("tickets/v2_ticket.md", root)

        self.assertFalse(
            result.skipped,
            "v2 ticket with ## Agent Contracts must not be skipped",
        )
        self.assertEqual(
            result.per_agent,
            {"python-coder": 3},
            f"per_agent must be {{'python-coder': 3}}, got {result.per_agent}",
        )
        self.assertEqual(
            result.total_ac_count,
            3,
            f"total_ac_count must be 3, got {result.total_ac_count}",
        )
        self.assertFalse(
            result.total_violation,
            "total_violation must be False when 3 ACs are well within the 20-total cap",
        )


# ---------------------------------------------------------------------------
# Helper: ticket body with fenced code block AC lines (H-1 fixture)
# ---------------------------------------------------------------------------


def _make_v1_flat_ticket_with_fenced_acs(
    num_real_acs: int, num_fenced_acs: int, override: bool = False
) -> str:
    """Build a v1-flat ticket with real ACs and ACs inside a fenced code block.

    The fenced block uses triple-backtick delimiters. After the H-1 fix, lines
    inside fenced blocks must NOT be counted by _count_acs_in_block.

    Args:
        num_real_acs: Number of real ``- [ ] AC-N:`` lines outside any fenced block.
        num_fenced_acs: Number of ``- [ ] AC-N:`` lines inside a ``` fenced block.
        override: If True, insert ``ac_limit_override: true`` into the frontmatter.

    Returns:
        Full ticket file content as a string, suitable for writing to disk.
    """
    real_ac_lines = "\n".join(
        f"- [ ] AC-{i}: Real acceptance criterion {i}"
        for i in range(1, num_real_acs + 1)
    )
    fenced_ac_lines = "\n".join(
        f"- [ ] AC-{i}: Fenced example criterion {i}"
        for i in range(1, num_fenced_acs + 1)
    )
    override_line = "ac_limit_override: true\n" if override else ""
    return (
        f"---\ntitle: Test ticket with fenced ACs\n{override_line}---\n\n"
        f"## Acceptance Criteria\n\n{real_ac_lines}\n\n"
        f"## Example Usage\n\n"
        f"```\n{fenced_ac_lines}\n```\n"
    )


# ---------------------------------------------------------------------------
# H-1 tests: fenced code block AC lines must not be counted
# ---------------------------------------------------------------------------


class TestH1FenceStripping(unittest.TestCase):
    """H-1 regression tests: AC lines inside fenced code blocks must not be counted.

    Tests test_fenced_acs_not_counted and test_fenced_acs_do_not_cause_false_block
    are RED with the current hook code (no fence stripping in _count_acs_in_block).
    They become GREEN only after the H-1 fix strips fenced blocks from content
    before counting AC lines.
    """

    @_requires_import
    def test_fenced_acs_not_counted(self) -> None:
        # covers: UNKNOWN
        """H-1: v1-flat ticket with 3 real + 3 fenced ACs produces total_ac_count == 3 (not 6).

        Must implement: strip ``` fenced code blocks from content before counting
        _AC_LINE_RE matches in _count_acs_in_block (or equivalently in the v1-flat
        branch of _analyse_ticket).

        RED with current code: no fence stripping → total_ac_count == 6.
        """
        content = _make_v1_flat_ticket_with_fenced_acs(num_real_acs=3, num_fenced_acs=3)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ticket_path = root / "tickets" / "fenced_3_3_test.md"
            ticket_path.parent.mkdir(parents=True, exist_ok=True)
            ticket_path.write_text(content, encoding="utf-8")

            result = _analyse_ticket("tickets/fenced_3_3_test.md", root)

        self.assertEqual(
            result.total_ac_count,
            3,
            (
                f"total_ac_count must be 3 (only real ACs outside fenced blocks); "
                f"got {result.total_ac_count}. "
                "Current code counts all AC lines including those inside ``` fenced blocks."
            ),
        )
        self.assertFalse(
            result.total_violation,
            "total_violation must be False when only 3 real ACs exist (fenced lines excluded)",
        )

    @_requires_import
    def test_fenced_acs_do_not_cause_false_block(self) -> None:
        # covers: UNKNOWN
        """H-1: 18 real ACs + 3 fenced ACs → total_ac_count == 18, no false block via main().

        Before the H-1 fix: 18 + 3 = 21 counted → total_violation=True → main() exits 1
        (false block on a legitimate ticket that only has 18 real ACs).
        After the H-1 fix: fenced lines excluded → 18 counted → no violation → exit 0.

        RED with current code: total_ac_count == 21, total_violation == True, exit 1.
        """
        content = _make_v1_flat_ticket_with_fenced_acs(num_real_acs=18, num_fenced_acs=3)

        # Part 1: unit-level check via _analyse_ticket
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ticket_path = root / "tickets" / "fenced_18_3_unit.md"
            ticket_path.parent.mkdir(parents=True, exist_ok=True)
            ticket_path.write_text(content, encoding="utf-8")

            result = _analyse_ticket("tickets/fenced_18_3_unit.md", root)

        self.assertEqual(
            result.total_ac_count,
            18,
            (
                f"total_ac_count must be 18 (real ACs only, fenced excluded); "
                f"got {result.total_ac_count}. "
                "Before fix: 21 counted (18 real + 3 fenced lines inside ``` block)."
            ),
        )
        self.assertFalse(
            result.total_violation,
            "total_violation must be False when 18 real ACs are within the 20-total cap",
        )

        # Part 2: end-to-end via main() — confirms the false block does not occur
        with tempfile.TemporaryDirectory() as tmp2:
            root2 = Path(tmp2)
            ticket_path2 = root2 / "tickets" / "fenced_18_3_e2e.md"
            ticket_path2.parent.mkdir(parents=True, exist_ok=True)
            ticket_path2.write_text(content, encoding="utf-8")

            diff_file = root2 / "test_diff.txt"
            diff_file.write_text("tickets/fenced_18_3_e2e.md\n", encoding="utf-8")

            with patch.object(_mod, "_find_project_root", return_value=root2):
                with patch.dict(os.environ, {"HOOK_TEST_DIFF": str(diff_file)}):
                    with patch("sys.stderr", io.StringIO()):
                        exit_code = _mod.main()

        self.assertEqual(
            exit_code,
            0,
            (
                f"main() must exit 0 for a ticket with 18 real ACs + 3 fenced ACs; "
                f"got exit code {exit_code}. "
                "Before fix: exits 1 because it counts 21 and triggers total_violation."
            ),
        )


# ---------------------------------------------------------------------------
# Tests: main() end-to-end exit-code paths (M-2 and M-3 gap closers)
# ---------------------------------------------------------------------------


class TestMainEndToEnd(unittest.TestCase):
    """End-to-end tests for main() covering AC-1 (exit 1), AC-2 (exit 0), AC-3 (override + warning).

    These tests invoke the hook's main() function directly with HOOK_TEST_DIFF
    wired to a synthetic fixture file and _find_project_root mocked to a temp
    directory. They close the gap identified in the H-1 code review: AC-1, AC-2,
    and AC-3 were tested only at _analyse_ticket unit level; main() exit-code
    paths and the override warning output were never exercised.

    Tests test_main_exits_1_on_flat_over_limit, test_main_exits_0_on_flat_within_limit,
    and test_override_warning_message_emitted are expected GREEN with the current
    hook code (GE-114 fix already shipped). If any of them fail, it is a real
    regression — not a test authoring issue.
    """

    def _run_main_with_ticket(
        self, content: str, ticket_rel_path: str = "tickets/main_e2e_test.md"
    ) -> tuple[int, str]:
        """Write content to a temp ticket, invoke main(), return (exit_code, stderr).

        Args:
            content: Full ticket file content to write to disk.
            ticket_rel_path: Relative path under the temp root. Must match
                the _TICKET_PATH_RE pattern (tickets/*.md).

        Returns:
            Tuple of (exit_code, captured_stderr_text).
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ticket_path = root / ticket_rel_path
            ticket_path.parent.mkdir(parents=True, exist_ok=True)
            ticket_path.write_text(content, encoding="utf-8")

            diff_file = root / "test_diff.txt"
            diff_file.write_text(f"{ticket_rel_path}\n", encoding="utf-8")

            fake_stderr = io.StringIO()
            with patch.object(_mod, "_find_project_root", return_value=root):
                with patch.dict(os.environ, {"HOOK_TEST_DIFF": str(diff_file)}):
                    with patch("sys.stderr", fake_stderr):
                        exit_code = _mod.main()

            stderr_text = fake_stderr.getvalue()

        return exit_code, stderr_text

    @_requires_import
    def test_main_exits_1_on_flat_over_limit(self) -> None:
        # covers: UNKNOWN
        """AC-1 end-to-end: main() returns 1 for a v1-flat ticket with 21 real ACs.

        Closes the M-2 gap: AC-1 was tested only at _analyse_ticket unit level.
        This test confirms the hook's exit-code path through main().

        Expected GREEN with current code (GE-114 fix already shipped).
        A failure here is a real regression in the v1-flat violation path.
        """
        content = _make_v1_flat_ticket(num_acs=21)
        exit_code, _ = self._run_main_with_ticket(
            content, "tickets/over_limit_main_test.md"
        )
        self.assertEqual(
            exit_code,
            1,
            (
                f"main() must return 1 for a v1-flat ticket with 21 ACs; "
                f"got exit code {exit_code}"
            ),
        )

    @_requires_import
    def test_main_exits_0_on_flat_within_limit(self) -> None:
        # covers: UNKNOWN
        """AC-2 end-to-end: main() returns 0 for a v1-flat ticket with exactly 20 ACs.

        Closes the M-2 happy-path gap: confirms main() returns 0 for within-limit
        v1-flat tickets.

        Expected GREEN with current code (GE-114 fix already shipped).
        A failure here is a real regression in the v1-flat non-violation path.
        """
        content = _make_v1_flat_ticket(num_acs=20)
        exit_code, _ = self._run_main_with_ticket(
            content, "tickets/within_limit_main_test.md"
        )
        self.assertEqual(
            exit_code,
            0,
            (
                f"main() must return 0 for a v1-flat ticket with exactly 20 ACs; "
                f"got exit code {exit_code}"
            ),
        )

    @_requires_import
    def test_override_warning_message_emitted(self) -> None:
        # covers: UNKNOWN
        """AC-3 end-to-end: override path exits 0 and emits a warning to stderr naming the ticket.

        Closes the M-3 gap: _print_override_warning was never exercised via main().
        Asserts: (a) exit code 0 when ac_limit_override: true is active, and
        (b) the warning message names the ticket path and mentions the total AC count.

        Expected GREEN with current code (GE-114 fix already shipped).
        A failure here is a real regression in the override warning path.
        """
        content = _make_v1_flat_ticket(num_acs=21, override=True)
        exit_code, stderr_text = self._run_main_with_ticket(
            content, "tickets/override_warning_main_test.md"
        )
        self.assertEqual(
            exit_code,
            0,
            (
                f"main() must return 0 when ac_limit_override: true is active; "
                f"got exit code {exit_code}"
            ),
        )
        self.assertIn(
            "override_warning_main_test.md",
            stderr_text,
            (
                "Override warning must name the ticket file in stderr output; "
                f"stderr was: {stderr_text!r}"
            ),
        )
        self.assertIn(
            "21",
            stderr_text,
            (
                "Override warning must mention the total AC count (21) in stderr; "
                f"stderr was: {stderr_text!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
