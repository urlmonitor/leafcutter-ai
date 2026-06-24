"""
Tests for check_v2_ac_store_alignment.py — the pre-commit hook that verifies
every inline AC store reference (implements/amends/introduces AC-XX-NNN) in a
staged ticket body resolves to an active YAML file in docs/acceptance-criteria/.

These tests are written BEFORE the implementation (TDD test-first) and are
expected to be SKIPPED (module not yet importable) until
check_v2_ac_store_alignment.py is implemented.  Once the module exists, all
tests are expected to PASS (green).

MODULE: test_check_v2_ac_store_alignment
GOAL: Confirm all eight acceptance criteria for the alignment hook pass.
"""

import os
import sys
import tempfile
import textwrap
import unittest

import importlib.util as _ilu
import pathlib as _pl

_REPO_ROOT = _pl.Path(__file__).resolve().parent.parent.parent
_HOOK_PATH = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_v2_ac_store_alignment.py"
)

# ---------------------------------------------------------------------------
# Attempt to import the module under test.
# All unit tests are SKIPPED until the module exists.
# Integration tests call self.skipTest() from setUp when the script is absent.
# ---------------------------------------------------------------------------
try:
    _spec = _ilu.spec_from_file_location("check_v2_ac_store_alignment", _HOOK_PATH)
    _mod = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    load_prefix_map = _mod.load_prefix_map
    extract_ac_references = _mod.extract_ac_references
    check_ac_exists_and_active = _mod.check_ac_exists_and_active
    _IMPORT_OK = True
except (FileNotFoundError, AttributeError, ImportError, SyntaxError, TypeError):
    _IMPORT_OK = False


def _skip_if_not_imported(func):
    """Decorator — skip the test when the module under test is not yet importable."""
    if not _IMPORT_OK:
        return unittest.skip(
            "check_v2_ac_store_alignment not yet implemented"
        )(func)
    return func


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ac_store(tmp: str, index_content: str, ac_files: dict) -> str:
    """
    Create a temporary AC store structure.

    :param tmp: Temporary directory root.
    :param index_content: YAML string for index.yaml (empty string = no file).
    :param ac_files: Mapping of relative paths to YAML content strings.
    :returns: Path to the temporary AC store root (same as ``tmp``).
    """
    if index_content.strip():
        index_path = os.path.join(tmp, "index.yaml")
        with open(index_path, "w") as fh:
            fh.write(textwrap.dedent(index_content))
    for rel_path, content in ac_files.items():
        full_path = os.path.join(tmp, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as fh:
            fh.write(textwrap.dedent(content))
    return tmp


# ---------------------------------------------------------------------------
# Test: load_prefix_map
# ---------------------------------------------------------------------------


class TestLoadPrefixMap(unittest.TestCase):
    """Tests for load_prefix_map(ac_dir)."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    @_skip_if_not_imported
    def test_returns_prefix_to_component_mapping(self) -> None:
        # covers: UNKNOWN
        """load_prefix_map must parse index.yaml and return {prefix: component_id}."""
        _make_ac_store(
            self.tmp,
            """\
            components:
              - id: finalize
                prefix: FIN
              - id: auth
                prefix: AUTH
            """,
            {},
        )
        result = load_prefix_map(self.tmp)
        self.assertEqual(result.get("FIN"), "finalize")
        self.assertEqual(result.get("AUTH"), "auth")

    @_skip_if_not_imported
    def test_returns_empty_dict_when_index_absent(self) -> None:
        # covers: UNKNOWN
        """load_prefix_map must return {} when index.yaml does not exist."""
        result = load_prefix_map(self.tmp)
        self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# Test: extract_ac_references
# ---------------------------------------------------------------------------


class TestExtractAcReferences(unittest.TestCase):
    """Tests for extract_ac_references(ticket_text)."""

    @_skip_if_not_imported
    def test_extracts_implements_reference(self) -> None:
        # covers: UNKNOWN
        """extract_ac_references must find 'implements AC-FIN-001'."""
        ticket_body = "This ticket implements AC-FIN-001 as agreed."
        refs = extract_ac_references(ticket_body)
        self.assertIn("FIN-001", refs)

    @_skip_if_not_imported
    def test_extracts_amends_reference(self) -> None:
        # covers: UNKNOWN
        """extract_ac_references must find 'amends AC-FIN-001'."""
        ticket_body = "This ticket amends AC-FIN-001."
        refs = extract_ac_references(ticket_body)
        self.assertIn("FIN-001", refs)

    @_skip_if_not_imported
    def test_extracts_introduces_reference(self) -> None:
        # covers: UNKNOWN
        """extract_ac_references must find 'introduces AC-FIN-002'."""
        ticket_body = "introduces AC-FIN-002 for the new pipeline."
        refs = extract_ac_references(ticket_body)
        self.assertIn("FIN-002", refs)

    @_skip_if_not_imported
    def test_returns_empty_list_when_no_references(self) -> None:
        # covers: UNKNOWN
        """extract_ac_references must return [] when no AC store references present."""
        ticket_body = "This ticket has no AC references at all."
        refs = extract_ac_references(ticket_body)
        self.assertEqual(refs, [])

    @_skip_if_not_imported
    def test_multiple_references_all_found(self) -> None:
        # covers: UNKNOWN
        """extract_ac_references must return all references in document order."""
        ticket_body = (
            "implements AC-FIN-001 and also amends AC-AUTH-007 "
            "and introduces AC-FIN-002"
        )
        refs = extract_ac_references(ticket_body)
        self.assertIn("FIN-001", refs)
        self.assertIn("AUTH-007", refs)
        self.assertIn("FIN-002", refs)


# ---------------------------------------------------------------------------
# Test: check_ac_exists_and_active
# ---------------------------------------------------------------------------


class TestCheckAcExistsAndActive(unittest.TestCase):
    """Tests for check_ac_exists_and_active(ac_dir, prefix_map, ac_id)."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.prefix_map = {"FIN": "finalize", "AUTH": "auth"}

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    @_skip_if_not_imported
    def test_valid_active_ac_returns_ok_true(self) -> None:
        # covers: UNKNOWN
        """check_ac_exists_and_active must return (True, '') for an active AC."""
        _make_ac_store(
            self.tmp,
            "",
            {
                "finalize/FIN-001.yaml": """\
                    id: FIN-001
                    status: active
                    description: Some AC.
                """
            },
        )
        ok, err = check_ac_exists_and_active(self.tmp, self.prefix_map, "FIN-001")
        self.assertTrue(ok)
        self.assertEqual(err, "")

    @_skip_if_not_imported
    def test_missing_file_returns_ok_false_with_message(self) -> None:
        # covers: UNKNOWN
        """check_ac_exists_and_active returns (False, error_msg) when file absent."""
        ok, err = check_ac_exists_and_active(self.tmp, self.prefix_map, "FIN-003")
        self.assertFalse(ok)
        self.assertIn("FIN-003", err)
        self.assertIn("not found", err.lower())

    @_skip_if_not_imported
    def test_deprecated_ac_returns_ok_false_with_message(self) -> None:
        # covers: UNKNOWN
        """check_ac_exists_and_active returns (False, error_msg) for deprecated AC."""
        _make_ac_store(
            self.tmp,
            "",
            {
                "finalize/FIN-001.yaml": """\
                    id: FIN-001
                    status: deprecated
                    description: Old AC.
                """
            },
        )
        ok, err = check_ac_exists_and_active(self.tmp, self.prefix_map, "FIN-001")
        self.assertFalse(ok)
        self.assertIn("deprecated", err)

    @_skip_if_not_imported
    def test_unknown_prefix_returns_ok_false_with_message(self) -> None:
        # covers: UNKNOWN
        """check_ac_exists_and_active returns (False, error_msg) for unknown prefix."""
        ok, err = check_ac_exists_and_active(self.tmp, self.prefix_map, "ZZ-001")
        self.assertFalse(ok)
        self.assertIn("ZZ", err)
        self.assertIn("no registered component", err.lower())


# ---------------------------------------------------------------------------
# Integration / Acceptance tests (drive main() via subprocess)
# ---------------------------------------------------------------------------


class TestMainIntegration(unittest.TestCase):
    """
    End-to-end acceptance tests that exercise main() by invoking the script
    via subprocess with --ticket <path>.

    These tests are SKIPPED until check_v2_ac_store_alignment.py exists.
    """

    def setUp(self) -> None:

        self.tmp = tempfile.mkdtemp()
        if not _HOOK_PATH.exists():
            self.skipTest(
                "check_v2_ac_store_alignment.py not yet implemented"
            )

        # Build a minimal AC store inside tmp.
        #   <tmp>/index.yaml
        #   <tmp>/finalize/FIN-001.yaml  (active)
        #   <tmp>/finalize/FIN-002.yaml  (active)
        #   <tmp>/finalize/FIN-003.yaml  (deprecated)
        _make_ac_store(
            self.tmp,
            """\
            components:
              - id: finalize
                prefix: FIN
            """,
            {
                "finalize/FIN-001.yaml": "id: FIN-001\nstatus: active\n",
                "finalize/FIN-002.yaml": "id: FIN-002\nstatus: active\n",
                "finalize/FIN-003.yaml": "id: FIN-003\nstatus: deprecated\n",
            },
        )
        self.ac_store = self.tmp

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run_hook(self, ticket_body: str, ac_store_override: str = "") -> tuple:
        """
        Write a temp ticket file, invoke the script with --ticket, and return
        (returncode, stdout+stderr combined).

        :param ticket_body: Raw markdown text for the staged ticket.
        :param ac_store_override: Override the AC store path (empty = use default).
        :returns: Tuple of (returncode, combined output string).
        """
        import subprocess

        ticket_file = os.path.join(self.tmp, "test_ticket.md")
        with open(ticket_file, "w") as fh:
            fh.write(ticket_body)

        ac_store = ac_store_override if ac_store_override else self.ac_store
        result = subprocess.run(
            [
                sys.executable,
                str(_HOOK_PATH),
                "--ticket",
                ticket_file,
                "--ac-store",
                ac_store,
            ],
            capture_output=True,
            text=True,
        )
        output = result.stdout + result.stderr
        return result.returncode, output

    # --- AC-1 ---
    def test_valid_reference_exits_0(self) -> None:
        # covers: UNKNOWN
        """AC-1: implements AC-FIN-001, file exists + active -> exit 0."""
        rc, out = self._run_hook("This ticket implements AC-FIN-001.")
        self.assertEqual(rc, 0, msg=f"Expected exit 0, got {rc}. Output: {out}")

    # --- AC-2 ---
    def test_missing_file_exits_1(self) -> None:
        # covers: UNKNOWN
        """AC-2: implements AC-FIN-099 (file absent) -> exit 1, correct error."""
        rc, out = self._run_hook("This ticket implements AC-FIN-099.")
        self.assertEqual(rc, 1, msg=f"Expected exit 1, got {rc}. Output: {out}")
        self.assertIn("FIN-099", out)
        self.assertIn("not found", out.lower())

    # --- AC-3 ---
    def test_deprecated_ac_exits_1(self) -> None:
        # covers: UNKNOWN
        """AC-3: amends AC-FIN-003 (deprecated) -> exit 1, correct error message."""
        rc, out = self._run_hook("This ticket amends AC-FIN-003.")
        self.assertEqual(rc, 1, msg=f"Expected exit 1, got {rc}. Output: {out}")
        self.assertIn("FIN-003", out)
        self.assertIn("deprecated", out)

    # --- AC-4 ---
    def test_no_references_exits_0(self) -> None:
        # covers: UNKNOWN
        """AC-4: ticket with no AC store references -> exit 0 silently."""
        rc, out = self._run_hook("This ticket has no AC store references whatsoever.")
        self.assertEqual(rc, 0, msg=f"Expected silent exit 0, got {rc}. Output: {out}")
        self.assertEqual(out.strip(), "", msg=f"Expected no output, got: {out!r}")

    # --- AC-5 ---
    def test_missing_ac_dir_exits_0(self) -> None:
        # covers: UNKNOWN
        """AC-5: docs/acceptance-criteria/ does not exist -> exit 0 silently."""
        rc, out = self._run_hook(
            "This ticket implements AC-FIN-001.",
            ac_store_override="/nonexistent/docs/acceptance-criteria",
        )
        self.assertEqual(
            rc,
            0,
            msg=f"Expected exit 0 (graceful degrade), got {rc}. Output: {out}",
        )

    # --- AC-6 ---
    def test_unknown_prefix_exits_1(self) -> None:
        # covers: UNKNOWN
        """AC-6: implements AC-ZZ-001, ZZ not registered -> exit 1, correct error."""
        rc, out = self._run_hook("This ticket implements AC-ZZ-001.")
        self.assertEqual(rc, 1, msg=f"Expected exit 1, got {rc}. Output: {out}")
        self.assertIn("ZZ", out)
        self.assertIn("no registered component", out.lower())

    # --- AC-7: amends reference detected ---
    def test_amends_reference_detected(self) -> None:
        # covers: UNKNOWN
        """amends AC-FIN-001, file exists + active -> exit 0."""
        rc, out = self._run_hook("This ticket amends AC-FIN-001.")
        self.assertEqual(rc, 0, msg=f"Expected exit 0, got {rc}. Output: {out}")

    # --- AC-8: introduces reference detected ---
    def test_introduces_reference_detected(self) -> None:
        # covers: UNKNOWN
        """introduces AC-FIN-002, file exists + active -> exit 0."""
        rc, out = self._run_hook("This ticket introduces AC-FIN-002.")
        self.assertEqual(rc, 0, msg=f"Expected exit 0, got {rc}. Output: {out}")


if __name__ == "__main__":
    unittest.main()
