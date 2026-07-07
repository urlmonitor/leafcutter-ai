"""
MODULE: test_check_files_touched_reconciliation_remediation
GOAL: Regression tests for 8 confirmed defects in check_files_touched_reconciliation.py
    (EPIC-PhantomDoneFilesTouched BP-1100e remediation 2026-07-07). Written TDD-first
    to establish the red baseline before production fixes are applied.
BUSINESS CONTEXT: Each defect was confirmed by code review and adversarial testing.
    Tests use the real PyYAML column-0 block-sequence format (dashes at column 0)
    rather than the indented format used by the pre-remediation test suite.
ARCHITECTURE: Tests import the hook module dynamically via importlib so they remain
    independent of the package install path. Pure-helper tests exercise functions
    directly. Integration tests use tempfile directories and unittest.mock.patch to
    inject controlled fixture data without touching the real git index.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = (
    REPO_ROOT
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "hooks"
    / "check_files_touched_reconciliation.py"
)
REAL_TICKET = (
    REPO_ROOT
    / "tickets"
    / "00_inbox"
    / "epics"
    / "EPIC-PhantomDoneFilesTouched"
    / "01_TICKET-20260706-BP-1100e-1.md"
)


def _load_hook() -> types.ModuleType:
    """Dynamically load the hook module from its template path."""
    if not HOOK_PATH.exists():
        msg = f"Hook not found at {HOOK_PATH}."
        raise ImportError(msg)
    spec = importlib.util.spec_from_file_location(
        "check_files_touched_reconciliation_remediation", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_hook = _load_hook()


# ---------------------------------------------------------------------------
# Defects 1, 3, 5 — _parse_yaml_list_field: column-0 dashes, quoted items,
# and flow-style lists.
# ---------------------------------------------------------------------------


class TestParseYamlListField(unittest.TestCase):
    """Tests for _parse_yaml_list_field covering defects 1, 3, and 5."""

    def _parse(self, frontmatter: str, field: str = "files_touched") -> list[str]:
        return _hook._parse_yaml_list_field(frontmatter, field)

    # D1 — column-0 block sequences
    def test_column0_files_touched_parses(self) -> None:
        """Column-0 dashes (PyYAML default) must parse correctly — Defect 1."""
        fm = "files_touched:\n- scripts/foo.py\n- scripts/bar.py\n"
        result = self._parse(fm)
        self.assertEqual(sorted(result), ["scripts/bar.py", "scripts/foo.py"])

    def test_column0_out_of_scope_parses(self) -> None:
        """Column-0 dashes for out_of_scope field — Defect 1."""
        fm = "out_of_scope:\n- scripts/legacy.py\n"
        result = self._parse(fm, "out_of_scope")
        self.assertEqual(result, ["scripts/legacy.py"])

    def test_indented_dashes_still_parse(self) -> None:
        """Indented dashes (two-space) must still parse after the column-0 fix."""
        fm = "files_touched:\n  - scripts/foo.py\n  - scripts/bar.py\n"
        result = self._parse(fm)
        self.assertEqual(sorted(result), ["scripts/bar.py", "scripts/foo.py"])

    # D3 — quoted paths
    def test_double_quoted_path_strips_quotes(self) -> None:
        """Double-quoted path keeps no surrounding quotes — Defect 3."""
        fm = 'files_touched:\n- "scripts/x.py"\n'
        result = self._parse(fm)
        self.assertIn("scripts/x.py", result)
        for item in result:
            self.assertFalse(item.startswith('"'), f"Quote not stripped: {item!r}")

    def test_single_quoted_path_strips_quotes(self) -> None:
        """Single-quoted path keeps no surrounding quotes — Defect 3."""
        fm = "files_touched:\n- 'scripts/x.py'\n"
        result = self._parse(fm)
        self.assertIn("scripts/x.py", result)
        for item in result:
            self.assertFalse(item.startswith("'"), f"Quote not stripped: {item!r}")

    # D5 — flow-style lists
    def test_flow_list_parses_items(self) -> None:
        """Inline flow-sequence [a, b] must parse to a list of items — Defect 5."""
        fm = "files_touched: [scripts/a.py, scripts/b.py]\n"
        result = self._parse(fm)
        self.assertIn("scripts/a.py", result)
        self.assertIn("scripts/b.py", result)

    def test_flow_list_with_quoted_items(self) -> None:
        """Flow-sequence with quoted items strips the quotes — Defects 3 + 5."""
        fm = 'files_touched: ["scripts/a.py", "scripts/b.py"]\n'
        result = self._parse(fm)
        self.assertIn("scripts/a.py", result)
        self.assertIn("scripts/b.py", result)


# ---------------------------------------------------------------------------
# Defect 1 — real ticket: column-0 produces correct count
# ---------------------------------------------------------------------------


class TestRealTicketParsing(unittest.TestCase):
    """Tests that the real ticket file parses correctly after the column-0 fix."""

    @unittest.skipUnless(REAL_TICKET.exists(), "Real ticket file not present in worktree")
    def test_real_ticket_files_touched_5_entries(self) -> None:
        """The real ticket 01_TICKET-20260706-BP-1100e-1.md declares 5 files — Defect 1."""
        content = REAL_TICKET.read_text(encoding="utf-8")
        frontmatter = _hook._extract_frontmatter(content)
        self.assertIsNotNone(frontmatter, "Frontmatter should be parseable")
        result = _hook._parse_yaml_list_field(frontmatter, "files_touched")
        self.assertEqual(
            len(result),
            5,
            f"Expected 5 declared files, got {len(result)}: {result}",
        )


# ---------------------------------------------------------------------------
# Defect 8 — _get_status: quoted status values
# ---------------------------------------------------------------------------


class TestGetStatus(unittest.TestCase):
    """Tests that _get_status handles quoted status values — Defect 8."""

    def test_status_double_quoted_done_recognized(self) -> None:
        """status: \"done\" (double quotes) must be recognized as done."""
        fm = 'status: "done"\nfiles_touched:\n- scripts/foo.py\n'
        result = _hook._get_status(fm)
        self.assertEqual(result, "done")

    def test_status_single_quoted_done_recognized(self) -> None:
        """status: 'done' (single quotes) must be recognized as done."""
        fm = "status: 'done'\nfiles_touched:\n- scripts/foo.py\n"
        result = _hook._get_status(fm)
        self.assertEqual(result, "done")

    def test_unquoted_status_still_works(self) -> None:
        """Unquoted status: done must continue to work after the quote fix."""
        fm = "status: done\n"
        result = _hook._get_status(fm)
        self.assertEqual(result, "done")


# ---------------------------------------------------------------------------
# Defect 6 — _normalise_path: lstrip strips too aggressively
# ---------------------------------------------------------------------------


class TestNormalisePathLeadingDot(unittest.TestCase):
    """Tests that _normalise_path uses removeprefix('./' ) logic — Defect 6."""

    def setUp(self) -> None:
        self._orig_fn = _hook._is_case_insensitive_fs
        _hook._FS_CASE_INSENSITIVE = None
        _hook._is_case_insensitive_fs = lambda: False  # case-sensitive

    def tearDown(self) -> None:
        _hook._is_case_insensitive_fs = self._orig_fn
        _hook._FS_CASE_INSENSITIVE = None

    def test_dotgithub_leading_dot_not_stripped(self) -> None:
        """.github/ci.py must not lose its leading dot — Defect 6."""
        result = _hook._normalise_path(".github/ci.py")
        self.assertEqual(result, ".github/ci.py")

    def test_hidden_file_leading_dot_not_stripped(self) -> None:
        """.hidden.py must not lose its leading dot — Defect 6."""
        result = _hook._normalise_path(".hidden.py")
        self.assertEqual(result, ".hidden.py")

    def test_dot_slash_prefix_still_stripped(self) -> None:
        """./scripts/foo.py must still strip the ./ prefix."""
        result = _hook._normalise_path("./scripts/foo.py")
        self.assertEqual(result, "scripts/foo.py")

    def test_double_dot_slash_not_over_stripped(self) -> None:
        """A path without ./ prefix (but starting with dot) keeps the dot."""
        result = _hook._normalise_path(".env")
        self.assertEqual(result, ".env")


# ---------------------------------------------------------------------------
# Defect 2 — git binary missing: FileNotFoundError must not escape
# ---------------------------------------------------------------------------


class TestGitBinaryMissing(unittest.TestCase):
    """Tests that a missing git binary causes fail-open exit 0 — Defect 2."""

    def test_main_exits_0_when_git_binary_missing(self) -> None:
        """Run hook with empty PATH — FileNotFoundError must not propagate to exit 1."""
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            capture_output=True,
            env={"PATH": "/nonexistent_path_for_testing"},
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Expected exit 0 (fail-open), got {result.returncode}."
            f" stderr: {result.stderr.decode()[:300]}",
        )


# ---------------------------------------------------------------------------
# Defect 4 — multi-ticket cross-flag: union of declared scopes
# ---------------------------------------------------------------------------


class TestMultiTicketCrossFlag(unittest.TestCase):
    """Tests that two staged done tickets do not cross-flag each other — Defect 4."""

    def test_two_done_tickets_no_undeclared_strict(self) -> None:
        """Ticket A declares scripts/ta.py; Ticket B declares scripts/tb.py.

        Both staged and both changed. After the union fix, no undeclared files
        exist, so main() must return 0 even in strict mode.
        """
        with tempfile.TemporaryDirectory() as tmp:
            ticket_dir = Path(tmp) / "tickets"
            ticket_dir.mkdir()
            # Use indented format so _parse_yaml_list_field works before column-0 fix.
            # The defect being tested is cross-flag (D4), not parsing (D1).
            (ticket_dir / "ta.md").write_text(
                "---\nstatus: done\nfiles_touched:\n  - scripts/ta.py\n---\n",
                encoding="utf-8",
            )
            (ticket_dir / "tb.md").write_text(
                "---\nstatus: done\nfiles_touched:\n  - scripts/tb.py\n---\n",
                encoding="utf-8",
            )
            staged = [
                "tickets/ta.md",
                "tickets/tb.md",
                "scripts/ta.py",
                "scripts/tb.py",
            ]
            branch_diff: frozenset[str] = frozenset({"scripts/ta.py", "scripts/tb.py"})
            with patch.object(_hook, "_get_staged_files", return_value=staged):
                with patch.object(_hook, "_get_repo_root", return_value=tmp):
                    with patch.object(
                        _hook, "_get_branch_diff_files", return_value=branch_diff
                    ):
                        with patch.object(
                            _hook, "_load_strict_mode", return_value=True
                        ):
                            result = _hook.main()
            self.assertEqual(result, 0, "Union fix: no undeclared files → exit 0 strict")


# ---------------------------------------------------------------------------
# Defect 5 — flow-style lists: main()-level integration
# ---------------------------------------------------------------------------


class TestFlowStyleListIntegration(unittest.TestCase):
    """Integration tests for flow-style lists exercised through main() — Defect 5."""

    _SOURCE = "scripts/flow_source.py"
    _OTHER = "scripts/other_source.py"

    def _run_main(
        self,
        files_touched_yaml: str,
        changed: frozenset[str],
        *,
        strict: bool,
    ) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            ticket_dir = Path(tmp) / "tickets"
            ticket_dir.mkdir()
            content = (
                "---\n"
                "status: done\n"
                f"files_touched: {files_touched_yaml}\n"
                "---\n"
            )
            (ticket_dir / "t.md").write_text(content, encoding="utf-8")
            staged = ["tickets/t.md"] + list(changed)
            with patch.object(_hook, "_get_staged_files", return_value=staged):
                with patch.object(_hook, "_get_repo_root", return_value=tmp):
                    with patch.object(
                        _hook, "_get_branch_diff_files", return_value=changed
                    ):
                        with patch.object(
                            _hook, "_load_strict_mode", return_value=strict
                        ):
                            return _hook.main()

    def test_flow_list_declaring_changed_file_not_flagged(self) -> None:
        """Flow-list that declares the changed source file → clean (exit 0 strict)."""
        result = self._run_main(
            f"[{self._SOURCE}]",
            frozenset({self._SOURCE}),
            strict=True,
        )
        self.assertEqual(result, 0)

    def test_flow_list_omitting_changed_source_flagged(self) -> None:
        """Flow-list that omits a changed source file → flagged (exit 1 strict)."""
        result = self._run_main(
            f"[{self._SOURCE}]",
            frozenset({self._SOURCE, self._OTHER}),
            strict=True,
        )
        self.assertEqual(result, 1)


# ---------------------------------------------------------------------------
# Defect 7 — is_docs_only_or_config_only_ticket wired into the code path
# ---------------------------------------------------------------------------


class TestDocsOnlyGuardWired(unittest.TestCase):
    """Tests that is_docs_only_or_config_only_ticket is called during processing — D7."""

    def test_docs_only_guard_is_called_during_ticket_processing(self) -> None:
        """is_docs_only_or_config_only_ticket must be invoked, not dead code."""
        with tempfile.TemporaryDirectory() as tmp:
            ticket_dir = Path(tmp) / "tickets"
            ticket_dir.mkdir()
            (ticket_dir / "docs_ticket.md").write_text(
                "---\nstatus: done\nfiles_touched:\n- docs/foo.md\n---\n",
                encoding="utf-8",
            )
            staged = ["tickets/docs_ticket.md"]
            sentinel = MagicMock(wraps=_hook.is_docs_only_or_config_only_ticket)
            with patch.object(_hook, "_get_staged_files", return_value=staged):
                with patch.object(_hook, "_get_repo_root", return_value=tmp):
                    with patch.object(
                        _hook, "_get_branch_diff_files", return_value=frozenset()
                    ):
                        with patch.object(
                            _hook, "is_docs_only_or_config_only_ticket", sentinel
                        ):
                            _hook.main()
            self.assertTrue(
                sentinel.called,
                "is_docs_only_or_config_only_ticket was never called — dead code still present",
            )


if __name__ == "__main__":
    unittest.main()
