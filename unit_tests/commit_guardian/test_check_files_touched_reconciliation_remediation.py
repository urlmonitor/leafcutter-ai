"""
MODULE: test_check_files_touched_reconciliation_remediation
GOAL: Regression tests for confirmed defects in check_files_touched_reconciliation.py
    (EPIC-PhantomDoneFilesTouched BP-1100e remediation rounds 1 and 2). Written
    TDD-first to establish the red baseline before production fixes are applied.
BUSINESS CONTEXT: Each defect was confirmed by code review and adversarial testing.
    Tests use the real PyYAML column-0 block-sequence format (dashes at column 0)
    rather than the indented format used by the pre-remediation test suite.
ARCHITECTURE: Tests import the hook module dynamically via importlib so they remain
    independent of the package install path. Pure-helper tests exercise functions
    directly. Integration tests use tempfile directories and unittest.mock.patch to
    inject controlled fixture data without touching the real git index.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
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
REAL_TICKET_02 = (
    REPO_ROOT
    / "tickets"
    / "00_inbox"
    / "epics"
    / "EPIC-PhantomDoneFilesTouched"
    / "02_TICKET-20260706-BP-1100e-1-i.md"
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
    def test_real_ticket_files_touched_has_core_entries(self) -> None:
        """Real ticket 01 declares the hook and config paths; list is non-empty — Defect 1.

        This test is robust: it asserts a non-empty list (>= 1 entry) and that
        the two core paths are present, rather than hardcoding the count (which
        would break if files_touched grows when new test files are added).
        """
        content = REAL_TICKET.read_text(encoding="utf-8")
        frontmatter = _hook._extract_frontmatter(content)
        self.assertIsNotNone(frontmatter, "Frontmatter should be parseable")
        result = _hook._parse_yaml_list_field(frontmatter, "files_touched")
        self.assertTrue(
            len(result) >= 1,
            f"Expected at least 1 declared file, got {len(result)}: {result}",
        )
        # Verify the two known core entries are present (column-0 parse regression)
        hook_path = "templates/scripts/commit_guardian/hooks/check_files_touched_reconciliation.py"
        config_path = "templates/scripts/commit_guardian/commit_guardian.json"
        result_set = set(result)
        self.assertIn(hook_path, result_set, f"Hook path missing from parsed files_touched: {result}")
        self.assertIn(config_path, result_set, f"Config path missing from parsed files_touched: {result}")


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
                            _hook, "_load_config", return_value=(True, True)
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
        """Run main() with a flow-list ticket and mocked git state.

        Args:
            files_touched_yaml: The raw flow-list YAML value for files_touched.
            changed: Files changed in the branch diff.
            strict: When True, use enabled:true+strict:true; when False,
                use enabled:true+strict:false (advisory).

        Returns:
            The integer return value of main().
        """
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
                            _hook, "_load_config", return_value=(True, strict)
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
        """is_docs_only_or_config_only_ticket must be invoked, not dead code.

        The check must be enabled (enabled:true) so main() doesn't short-circuit
        before reaching the ticket-processing phase. Without enabled:true, the
        function would never be called (check is off), which would be a false pass.
        """
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
                            _hook, "_load_config", return_value=(True, False)
                        ):
                            with patch.object(
                                _hook, "is_docs_only_or_config_only_ticket", sentinel
                            ):
                                _hook.main()
            self.assertTrue(
                sentinel.called,
                "is_docs_only_or_config_only_ticket was never called — dead code still present",
            )


# ---------------------------------------------------------------------------
# Remediation Round 2 — Fix 1: _load_strict_mode shape robustness
# ---------------------------------------------------------------------------


class TestLoadConfigShapeRobust(unittest.TestCase):
    """Tests that _load_config handles wrong-shape configs without crashing — Round 2 Fix 1."""

    def _write_primary_config(self, tmp: str, content: str) -> None:
        """Write content to the primary scripts/ config path in a temp dir."""
        config_dir = Path(tmp) / "scripts" / "commit_guardian"
        config_dir.mkdir(parents=True)
        (config_dir / "commit_guardian.json").write_text(content, encoding="utf-8")

    def test_section_null_returns_disabled(self) -> None:
        """files_touched_reconciliation: null — must return (False, False), no crash."""
        with tempfile.TemporaryDirectory() as tmp:
            self._write_primary_config(tmp, '{"files_touched_reconciliation": null}')
            result = _hook._load_config(tmp)
            self.assertEqual(result, (False, False))

    def test_top_level_list_returns_disabled(self) -> None:
        """Top-level JSON array [] — must return (False, False), no crash."""
        with tempfile.TemporaryDirectory() as tmp:
            self._write_primary_config(tmp, "[]")
            result = _hook._load_config(tmp)
            self.assertEqual(result, (False, False))

    def test_enabled_truthy_non_bool_string_not_enabled(self) -> None:
        """enabled: \"yes\" is truthy non-bool — must not enable the check."""
        with tempfile.TemporaryDirectory() as tmp:
            self._write_primary_config(
                tmp,
                '{"files_touched_reconciliation": {"enabled": "yes", "strict": true}}',
            )
            result = _hook._load_config(tmp)
            self.assertEqual(result, (False, True))

    def test_empty_object_returns_disabled(self) -> None:
        """Empty config {} — must return (False, False) (section absent)."""
        with tempfile.TemporaryDirectory() as tmp:
            self._write_primary_config(tmp, "{}")
            result = _hook._load_config(tmp)
            self.assertEqual(result, (False, False))

    def test_valid_enabled_strict_true_returns_block_mode(self) -> None:
        """enabled:true, strict:true must return (True, True) after the shape fix."""
        with tempfile.TemporaryDirectory() as tmp:
            self._write_primary_config(
                tmp,
                '{"files_touched_reconciliation": {"enabled": true, "strict": true}}',
            )
            result = _hook._load_config(tmp)
            self.assertEqual(result, (True, True))

    def test_strict_truthy_non_bool_advisory_exit_zero_with_undeclared(self) -> None:
        """enabled:true, strict:\"yes\" + undeclared file → main() exits 0 (advisory).

        strict:\"yes\" is not JSON boolean true, so strict=False → advisory mode,
        not blocking. This verifies that only exact JSON true enables strict mode.
        """
        with tempfile.TemporaryDirectory() as tmp:
            self._write_primary_config(
                tmp,
                '{"files_touched_reconciliation": {"enabled": true, "strict": "yes"}}',
            )
            ticket_dir = Path(tmp) / "tickets"
            ticket_dir.mkdir()
            (ticket_dir / "t.md").write_text(
                "---\nstatus: done\nfiles_touched:\n- scripts/declared.py\n---\n",
                encoding="utf-8",
            )
            staged = ["tickets/t.md", "scripts/declared.py", "scripts/undeclared.py"]
            branch_diff: frozenset[str] = frozenset({
                "scripts/declared.py",
                "scripts/undeclared.py",
            })
            with patch.object(_hook, "_get_staged_files", return_value=staged):
                with patch.object(_hook, "_get_repo_root", return_value=tmp):
                    with patch.object(
                        _hook, "_get_branch_diff_files", return_value=branch_diff
                    ):
                        result = _hook.main()
            self.assertEqual(
                result, 0, "strict: 'yes' must not enable strict mode — advisory exit 0"
            )


# ---------------------------------------------------------------------------
# Remediation Round 2 — Fix 2: _get_branch_diff_files logs WARNING on failure
# ---------------------------------------------------------------------------


class TestGetBranchDiffFilesWarning(unittest.TestCase):
    """Tests that _get_branch_diff_files logs a WARNING when git fails — Round 2 Fix 2."""

    def test_warning_logged_when_git_diff_raises_oserror(self) -> None:
        """When subprocess.run raises OSError, a WARNING is printed to stderr."""
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            with patch(
                "subprocess.run",
                side_effect=OSError("No such file or directory: 'git'"),
            ):
                result = _hook._get_branch_diff_files()
        self.assertEqual(result, frozenset(), "Fail-open: must return empty frozenset")
        self.assertIn(
            "WARNING",
            buf.getvalue(),
            f"Expected WARNING in stderr; got: {buf.getvalue()!r}",
        )


# ---------------------------------------------------------------------------
# Remediation Round 2 — Fix 3: _strip_yaml_value quoted paths with hash
# ---------------------------------------------------------------------------


class TestStripYamlValueQuotedHash(unittest.TestCase):
    """Tests that quoted paths containing ' #' are not truncated — Round 2 Fix 3."""

    def test_double_quoted_path_with_hash_returns_full_inner_content(self) -> None:
        """Double-quoted path containing ' #' returns the literal interior."""
        result = _hook._strip_yaml_value('"scripts/build #1.py"')
        self.assertEqual(result, "scripts/build #1.py")

    def test_single_quoted_path_with_hash_returns_full_inner_content(self) -> None:
        """Single-quoted path containing ' #' returns the literal interior."""
        result = _hook._strip_yaml_value("'scripts/build #1.py'")
        self.assertEqual(result, "scripts/build #1.py")

    def test_unquoted_path_trailing_comment_stripped(self) -> None:
        """Unquoted path with trailing ' # note' strips the comment correctly."""
        result = _hook._strip_yaml_value("scripts/foo.py  # note")
        self.assertEqual(result, "scripts/foo.py")

    def test_unquoted_path_inline_hash_no_space_preserved(self) -> None:
        """Unquoted path with a hash but no leading space is preserved (in-path hash)."""
        result = _hook._strip_yaml_value("scripts/build#1.py")
        self.assertEqual(result, "scripts/build#1.py")


class TestMainQuotedPathWithHash(unittest.TestCase):
    """Integration test: main() does not flag a declared quoted path with ' #' — Round 2 Fix 3."""

    _DECLARED_FILE = "scripts/build #1.py"

    def _run_main(
        self,
        *,
        strict: bool,
        also_stage_undeclared: bool,
    ) -> int:
        """Run main() with a ticket that declares a file whose name contains ' #'.

        Args:
            strict: When True, use enabled:true+strict:true. When False,
                use enabled:true+strict:false (advisory).
            also_stage_undeclared: When True, an additional undeclared source
                file is staged alongside the hash-name declared file.

        Returns:
            The integer return value of main().
        """
        with tempfile.TemporaryDirectory() as tmp:
            ticket_dir = Path(tmp) / "tickets"
            ticket_dir.mkdir()
            # Write ticket with the hash-in-name file declared in double quotes
            (ticket_dir / "t.md").write_text(
                '---\nstatus: done\nfiles_touched:\n- "scripts/build #1.py"\n---\n',
                encoding="utf-8",
            )
            staged = ["tickets/t.md", self._DECLARED_FILE]
            branch_diff: frozenset[str] = frozenset({self._DECLARED_FILE})
            if also_stage_undeclared:
                staged.append("scripts/extra.py")
                branch_diff = branch_diff | frozenset({"scripts/extra.py"})
            with patch.object(_hook, "_get_staged_files", return_value=staged):
                with patch.object(_hook, "_get_repo_root", return_value=tmp):
                    with patch.object(
                        _hook, "_get_branch_diff_files", return_value=branch_diff
                    ):
                        with patch.object(
                            _hook, "_load_config", return_value=(True, strict)
                        ):
                            return _hook.main()

    def test_declared_quoted_path_with_hash_not_flagged_strict(self) -> None:
        """Declared file with ' #' in name is NOT flagged in strict mode."""
        result = self._run_main(strict=True, also_stage_undeclared=False)
        self.assertEqual(result, 0, "Declared file with hash in name must not be flagged")

    def test_undeclared_source_flagged_when_declared_has_hash_strict(self) -> None:
        """An undeclared source file is still flagged even when the declared file has '#'."""
        result = self._run_main(strict=True, also_stage_undeclared=True)
        self.assertEqual(result, 1, "Undeclared extra source must be flagged in strict mode")


# ---------------------------------------------------------------------------
# Remediation Round 2 — Fix 4a: docs-only ticket with stray source file
# ---------------------------------------------------------------------------


class TestDocsOnlyWithStraySource(unittest.TestCase):
    """Docs-only ticket with a stray undeclared .py must be caught — Round 2 Fix 4a."""

    def _run_main_docs_only_stray(self, *, strict: bool) -> int:
        """Run main() with a docs-only ticket and an undeclared source file staged.

        Args:
            strict: When True, use enabled:true+strict:true (blocking mode).
                When False, use enabled:true+strict:false (advisory mode).

        Returns:
            The integer return value of main().
        """
        with tempfile.TemporaryDirectory() as tmp:
            ticket_dir = Path(tmp) / "tickets"
            ticket_dir.mkdir()
            # Column-0 format; all declared files are .md (docs-only ticket)
            (ticket_dir / "docs_ticket.md").write_text(
                "---\nstatus: done\nfiles_touched:\n- docs/some_doc.md\n---\n",
                encoding="utf-8",
            )
            staged = ["tickets/docs_ticket.md", "scripts/stray_source.py"]
            branch_diff: frozenset[str] = frozenset({"scripts/stray_source.py"})
            with patch.object(_hook, "_get_staged_files", return_value=staged):
                with patch.object(_hook, "_get_repo_root", return_value=tmp):
                    with patch.object(
                        _hook, "_get_branch_diff_files", return_value=branch_diff
                    ):
                        with patch.object(
                            _hook, "_load_config", return_value=(True, strict)
                        ):
                            return _hook.main()

    def test_docs_only_stray_source_advisory_exit_zero(self) -> None:
        """Docs-only ticket + stray source → advisory exit 0 (not blocked, but reported)."""
        result = self._run_main_docs_only_stray(strict=False)
        self.assertEqual(result, 0, "Advisory mode must exit 0 even with stray source")

    def test_docs_only_stray_source_strict_exit_one(self) -> None:
        """Docs-only ticket + stray source → strict exit 1 (stray source is caught)."""
        result = self._run_main_docs_only_stray(strict=True)
        self.assertEqual(result, 1, "Strict mode must exit 1 when stray source is undeclared")


# ---------------------------------------------------------------------------
# Remediation Round 2 — Fix 4b: real ticket 02 end-to-end
# ---------------------------------------------------------------------------


class TestRealTicket02EndToEnd(unittest.TestCase):
    """End-to-end main() tests using the real ticket 02 fixture — Round 2 Fix 4b."""

    _TICKET_REL = (
        "tickets/00_inbox/epics/EPIC-PhantomDoneFilesTouched"
        "/02_TICKET-20260706-BP-1100e-1-i.md"
    )
    # Files declared in the real ticket 02 frontmatter (column-0 format)
    _DECLARED = [
        "templates/scripts/commit_guardian/hooks/check_files_touched_reconciliation.py",
        "unit_tests/commit_guardian/test_check_files_touched_reconciliation.py",
    ]

    def _setup_temp_repo(self, tmp: str) -> None:
        """Copy the real ticket 02 into a temp directory structure."""
        ticket_dir = (
            Path(tmp)
            / "tickets"
            / "00_inbox"
            / "epics"
            / "EPIC-PhantomDoneFilesTouched"
        )
        ticket_dir.mkdir(parents=True)
        content = REAL_TICKET_02.read_text(encoding="utf-8")
        (ticket_dir / "02_TICKET-20260706-BP-1100e-1-i.md").write_text(
            content, encoding="utf-8"
        )

    @unittest.skipUnless(REAL_TICKET_02.exists(), "Ticket 02 not present in worktree")
    def test_real_ticket_02_declared_files_clean_strict(self) -> None:
        """Real ticket 02 with its declared files staged → clean exit 0 in strict mode."""
        with tempfile.TemporaryDirectory() as tmp:
            self._setup_temp_repo(tmp)
            staged = [self._TICKET_REL] + self._DECLARED
            branch_diff: frozenset[str] = frozenset(self._DECLARED)
            with patch.object(_hook, "_get_staged_files", return_value=staged):
                with patch.object(_hook, "_get_repo_root", return_value=tmp):
                    with patch.object(
                        _hook, "_get_branch_diff_files", return_value=branch_diff
                    ):
                        with patch.object(
                            _hook, "_load_config", return_value=(True, True)
                        ):
                            result = _hook.main()
            self.assertEqual(result, 0, "Real ticket 02 with declared files → clean")

    @unittest.skipUnless(REAL_TICKET_02.exists(), "Ticket 02 not present in worktree")
    def test_real_ticket_02_undeclared_extra_source_flagged_strict(self) -> None:
        """Real ticket 02 + extra undeclared .py staged → flagged exit 1 in strict mode."""
        with tempfile.TemporaryDirectory() as tmp:
            self._setup_temp_repo(tmp)
            extra = "scripts/sneaky_new_module.py"
            staged = [self._TICKET_REL] + self._DECLARED + [extra]
            branch_diff: frozenset[str] = frozenset(self._DECLARED + [extra])
            with patch.object(_hook, "_get_staged_files", return_value=staged):
                with patch.object(_hook, "_get_repo_root", return_value=tmp):
                    with patch.object(
                        _hook, "_get_branch_diff_files", return_value=branch_diff
                    ):
                        with patch.object(
                            _hook, "_load_config", return_value=(True, True)
                        ):
                            result = _hook.main()
            self.assertEqual(result, 1, "Undeclared extra source → flagged in strict mode")


# ---------------------------------------------------------------------------
# Remediation Round 2 — Fix 4c: D4 cross-flag test with column-0 fixtures
# ---------------------------------------------------------------------------


class TestMultiTicketCrossFlagColumnZero(unittest.TestCase):
    """D4 cross-flag test with column-0 (PyYAML default) fixtures — Round 2 Fix 4c."""

    def test_two_done_tickets_column0_no_cross_flag_strict(self) -> None:
        """Two tickets with column-0 dashes do not cross-flag each other in strict mode."""
        with tempfile.TemporaryDirectory() as tmp:
            ticket_dir = Path(tmp) / "tickets"
            ticket_dir.mkdir()
            # Column-0 format: no leading whitespace before dashes (PyYAML default)
            (ticket_dir / "ta.md").write_text(
                "---\nstatus: done\nfiles_touched:\n- scripts/ta.py\n---\n",
                encoding="utf-8",
            )
            (ticket_dir / "tb.md").write_text(
                "---\nstatus: done\nfiles_touched:\n- scripts/tb.py\n---\n",
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
                            _hook, "_load_config", return_value=(True, True)
                        ):
                            result = _hook.main()
            self.assertEqual(
                result,
                0,
                "Column-0 fixtures: union scope prevents cross-flagging → clean",
            )


# ---------------------------------------------------------------------------
# Remediation Round 2 — Fix 5: flow-list quote-aware comma splitting
# ---------------------------------------------------------------------------


class TestFlowListQuoteAwareSplit(unittest.TestCase):
    """Tests for quote-aware comma splitting in flow-sequence items — Round 2 Fix 5."""

    def test_quoted_item_with_comma_parses_as_single_item(self) -> None:
        """A quoted flow item containing a comma is one item, not split on the comma."""
        fm = 'files_touched: ["scripts/a,b.py"]\n'
        result = _hook._parse_yaml_list_field(fm, "files_touched")
        self.assertEqual(result, ["scripts/a,b.py"])

    def test_unquoted_multiple_items_still_split_on_comma(self) -> None:
        """Multiple unquoted items separated by commas still parse correctly."""
        fm = "files_touched: [scripts/a.py, scripts/b.py]\n"
        result = _hook._parse_yaml_list_field(fm, "files_touched")
        self.assertIn("scripts/a.py", result)
        self.assertIn("scripts/b.py", result)
        self.assertEqual(len(result), 2)

    def test_mixed_quoted_and_unquoted_flow_items(self) -> None:
        """Mixed quoted/unquoted flow items all parse correctly."""
        fm = 'files_touched: ["scripts/a,b.py", scripts/c.py]\n'
        result = _hook._parse_yaml_list_field(fm, "files_touched")
        self.assertIn("scripts/a,b.py", result)
        self.assertIn("scripts/c.py", result)
        self.assertEqual(len(result), 2)


# ---------------------------------------------------------------------------
# AC BP-1100e-1-iv — absent files_touched key: no-op even when check is active
# ---------------------------------------------------------------------------


class TestAbsentFilesTouchedNoOp(unittest.TestCase):
    """AC BP-1100e-1-iv: absent files_touched key → no-op + skip advisory printed.

    The check is enabled with strict:true so the test proves the no-op
    is a genuine scope guard (the absent frontmatter key), not merely
    the off switch (enabled:false).
    """

    def test_absent_files_touched_key_skips_and_prints_advisory(self) -> None:
        """Done ticket with NO files_touched key + stray .py staged → exit 0, skip printed.

        The ticket is done but has no files_touched key in its frontmatter.
        A stray .py is staged. The hook must:
        - NOT flag the stray .py (scope guard: no declared baseline)
        - Exit 0 (no block)
        - Print "skipped (no files_touched declared" to stderr (visible skip advisory)
        """
        with tempfile.TemporaryDirectory() as tmp:
            ticket_dir = Path(tmp) / "tickets"
            ticket_dir.mkdir()
            # Frontmatter has status:done but NO files_touched key at all
            (ticket_dir / "no_ft_ticket.md").write_text(
                "---\nstatus: done\ntitle: A ticket without files_touched\n---\n",
                encoding="utf-8",
            )
            staged = ["tickets/no_ft_ticket.md", "scripts/stray_source.py"]
            branch_diff: frozenset[str] = frozenset({"scripts/stray_source.py"})
            buf = io.StringIO()
            with patch.object(_hook, "_get_staged_files", return_value=staged):
                with patch.object(_hook, "_get_repo_root", return_value=tmp):
                    with patch.object(
                        _hook, "_get_branch_diff_files", return_value=branch_diff
                    ):
                        with patch.object(
                            _hook, "_load_config", return_value=(True, True)
                        ):
                            with contextlib.redirect_stderr(buf):
                                result = _hook.main()
            self.assertEqual(result, 0, "Absent files_touched must not block even in strict mode")
            self.assertIn(
                "skipped (no files_touched declared",
                buf.getvalue(),
                "Expected skip advisory in stderr; got: " + repr(buf.getvalue()[:200]),
            )
            self.assertNotIn(
                "scripts/stray_source.py",
                buf.getvalue(),
                "Stray source must NOT be named in output (scope guard bypasses it)",
            )


if __name__ == "__main__":
    unittest.main()
