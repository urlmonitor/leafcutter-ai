"""
MODULE: test_check_files_touched_reconciliation
GOAL: Unit tests for the generated-file and lockfile exemptions (BP-1100e-1-i)
    and the enabled/advisory/strict mode behaviour (BP-1100e-2) of
    check_files_touched_reconciliation.py.
BUSINESS CONTEXT: Verifies that out_of_scope entries, generated artifacts,
    and lock-files are never flagged as undeclared source changes; that
    genuinely undeclared source files are still caught; and that the hook is
    off (exit 0, no output) when disabled, advisory (exit 0) when
    enabled:true+strict:false, and blocking (exit 1) only when
    files_touched_reconciliation.enabled:true and strict:true in
    commit_guardian.json.
ARCHITECTURE: Tests import the hook module dynamically via importlib so the
    tests remain independent of the package install path. Pure-helper tests
    exercise functions directly with no subprocess calls. Integration tests
    use tempfile directories and unittest.mock.patch to inject controlled
    fixture data without touching the real git index.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

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


def _load_hook() -> types.ModuleType:
    """Dynamically load the hook module from its template path.

    Returns:
        Loaded module object.

    Raises:
        ImportError: When the hook script does not exist.
    """
    if not HOOK_PATH.exists():
        msg = f"Hook not found at {HOOK_PATH}. Implement it (python-coder phase)."
        raise ImportError(msg)
    spec = importlib.util.spec_from_file_location(
        "check_files_touched_reconciliation", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_hook = _load_hook()


# ---------------------------------------------------------------------------
# Tests: _is_generated_file
# ---------------------------------------------------------------------------


class TestIsGeneratedFile(unittest.TestCase):
    """Tests for the _is_generated_file pure helper."""

    def test_generated_directory_segment_flagged(self) -> None:
        """A file under a 'generated/' directory segment is a generated file."""
        self.assertTrue(_hook._is_generated_file("scripts/generated/paths_index.py"))

    def test_double_underscore_generated_flagged(self) -> None:
        """A file under '__generated__/' is a generated file."""
        self.assertTrue(_hook._is_generated_file("src/__generated__/types.ts"))

    def test_hidden_generated_flagged(self) -> None:
        """A file under '.generated/' is a generated file."""
        self.assertTrue(_hook._is_generated_file(".generated/schema.py"))

    def test_dist_directory_flagged(self) -> None:
        """A file under 'dist/' is a generated artifact."""
        self.assertTrue(_hook._is_generated_file("dist/bundle.js"))

    def test_generated_stem_suffix_dot_flagged(self) -> None:
        """A filename containing '.generated.' is a generated file."""
        self.assertTrue(_hook._is_generated_file("src/schema.generated.ts"))

    def test_generated_stem_suffix_underscore_flagged(self) -> None:
        """A filename containing '_generated.' is a generated file."""
        self.assertTrue(_hook._is_generated_file("scripts/client_generated.py"))

    def test_regular_source_file_not_flagged(self) -> None:
        """A regular source file is NOT flagged as generated."""
        self.assertFalse(_hook._is_generated_file("scripts/build_phases.py"))

    def test_not_generated_substring_not_flagged(self) -> None:
        """A path containing 'generated' as a word-interior substring is NOT flagged.

        'not_generated/foo.py' should not match the '/generated/' segment marker.
        """
        self.assertFalse(_hook._is_generated_file("not_generated/foo.py"))

    def test_nested_regular_file_not_flagged(self) -> None:
        """A deeply nested regular .py file is NOT flagged as generated."""
        self.assertFalse(_hook._is_generated_file("src/api/v2/client.py"))


# ---------------------------------------------------------------------------
# Tests: _is_lockfile
# ---------------------------------------------------------------------------


class TestIsLockfile(unittest.TestCase):
    """Tests for the _is_lockfile pure helper."""

    def test_poetry_lock_flagged(self) -> None:
        """poetry.lock is a lockfile."""
        self.assertTrue(_hook._is_lockfile("poetry.lock"))

    def test_poetry_lock_nested_flagged(self) -> None:
        """poetry.lock nested in a subdirectory is still a lockfile."""
        self.assertTrue(_hook._is_lockfile("subproject/poetry.lock"))

    def test_package_lock_json_flagged(self) -> None:
        """package-lock.json is a lockfile."""
        self.assertTrue(_hook._is_lockfile("package-lock.json"))

    def test_yarn_lock_flagged(self) -> None:
        """yarn.lock is a lockfile."""
        self.assertTrue(_hook._is_lockfile("yarn.lock"))

    def test_pnpm_lock_yaml_flagged(self) -> None:
        """pnpm-lock.yaml is a lockfile."""
        self.assertTrue(_hook._is_lockfile("pnpm-lock.yaml"))

    def test_uv_lock_flagged(self) -> None:
        """uv.lock is a lockfile."""
        self.assertTrue(_hook._is_lockfile("uv.lock"))

    def test_go_sum_flagged(self) -> None:
        """go.sum is a lockfile."""
        self.assertTrue(_hook._is_lockfile("go.sum"))

    def test_cargo_lock_flagged(self) -> None:
        """Cargo.lock is a lockfile."""
        self.assertTrue(_hook._is_lockfile("Cargo.lock"))

    def test_regular_py_file_not_flagged(self) -> None:
        """A regular .py file is NOT a lockfile."""
        self.assertFalse(_hook._is_lockfile("scripts/build.py"))

    def test_regular_json_file_not_flagged(self) -> None:
        """A regular .json config file is NOT a lockfile."""
        self.assertFalse(_hook._is_lockfile("config/settings.json"))


# ---------------------------------------------------------------------------
# Tests: _compute_undeclared (integration — AC BP-1100e-1-i scenarios)
# ---------------------------------------------------------------------------


class TestComputeUndeclared(unittest.TestCase):
    """Tests for _compute_undeclared exercising AC BP-1100e-1-i scenarios."""

    def _call(
        self,
        declared: set[str],
        branch: frozenset[str],
        staged: list[str],
    ) -> list[str]:
        """Thin wrapper so test bodies stay concise."""
        return _hook._compute_undeclared(declared, branch, staged)

    # --- AC scenario: out_of_scope entries are not flagged ---

    def test_out_of_scope_file_not_flagged(self) -> None:
        """A file declared in out_of_scope (in declared set) is NOT flagged.

        The declared set is files_touched UNION out_of_scope, so
        'scripts/legacy_shim.py' in out_of_scope must not appear as undeclared.
        """
        declared = {
            "scripts/build_phases.py",
            "scripts/legacy_shim.py",  # out_of_scope entry
        }
        branch = frozenset({"scripts/legacy_shim.py"})
        result = self._call(declared, branch, [])
        self.assertEqual(result, [])

    # --- AC scenario: lockfiles are not flagged ---

    def test_lockfile_not_flagged(self) -> None:
        """poetry.lock is not flagged even when it appears in the branch diff."""
        declared: set[str] = {"scripts/build_phases.py"}
        branch = frozenset({"poetry.lock"})
        result = self._call(declared, branch, [])
        self.assertEqual(result, [])

    def test_package_lock_not_flagged(self) -> None:
        """package-lock.json is not flagged even when changed."""
        declared: set[str] = {"src/index.ts"}
        branch = frozenset({"package-lock.json"})
        result = self._call(declared, branch, [])
        self.assertEqual(result, [])

    # --- AC scenario: generated files are not flagged ---

    def test_generated_directory_file_not_flagged(self) -> None:
        """A .py file under scripts/generated/ is not flagged as undeclared."""
        declared: set[str] = {"scripts/build_phases.py"}
        branch = frozenset({"scripts/generated/paths_index.py"})
        result = self._call(declared, branch, [])
        self.assertEqual(result, [])

    def test_generated_stem_file_not_flagged(self) -> None:
        """A .ts file with a .generated. stem is not flagged as undeclared."""
        declared: set[str] = {"src/api.ts"}
        branch = frozenset({"src/schema.generated.ts"})
        result = self._call(declared, branch, [])
        self.assertEqual(result, [])

    # --- AC scenario: genuine undeclared sources ARE still flagged ---

    def test_undeclared_source_is_flagged(self) -> None:
        """A real source file absent from the declared set IS flagged."""
        declared: set[str] = {"scripts/build_phases.py"}
        branch = frozenset({"scripts/new_module.py"})
        result = self._call(declared, branch, [])
        self.assertEqual(result, ["scripts/new_module.py"])

    def test_declared_source_not_flagged(self) -> None:
        """A source file present in the declared set is NOT flagged."""
        declared: set[str] = {"scripts/build_phases.py"}
        branch = frozenset({"scripts/build_phases.py"})
        result = self._call(declared, branch, [])
        self.assertEqual(result, [])

    # --- Full AC scenario: all three exemption types together ---

    def test_full_ac_scenario(self) -> None:
        """AC BP-1100e-1-i: combined exemptions + a genuine undeclared file.

        Changed files:
          - scripts/legacy_shim.py  (out_of_scope → not flagged)
          - poetry.lock             (lockfile → not flagged)
          - scripts/generated/paths_index.py  (generated → not flagged)
          - scripts/sneaky_new.py   (undeclared source → FLAGGED)
        """
        declared = {
            "scripts/build_phases.py",
            "scripts/legacy_shim.py",
        }
        branch = frozenset({
            "scripts/legacy_shim.py",
            "poetry.lock",
            "scripts/generated/paths_index.py",
            "scripts/sneaky_new.py",
        })
        result = self._call(declared, branch, [])
        self.assertEqual(result, ["scripts/sneaky_new.py"])

    def test_staged_files_included_in_computation(self) -> None:
        """Files in staged_files (not in branch diff) are still checked."""
        declared: set[str] = {"scripts/build_phases.py"}
        branch: frozenset[str] = frozenset()
        staged = ["scripts/another_undeclared.py"]
        result = self._call(declared, branch, staged)
        self.assertEqual(result, ["scripts/another_undeclared.py"])

    def test_no_changed_files_returns_empty(self) -> None:
        """Empty branch diff + no staged files → empty result."""
        declared: set[str] = {"scripts/build_phases.py"}
        result = self._call(declared, frozenset(), [])
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Tests: _load_config (AC BP-1100e-2 config reader)
# ---------------------------------------------------------------------------


class TestLoadConfig(unittest.TestCase):
    """Tests for the _load_config config reader (AC BP-1100e-2)."""

    def test_disabled_when_no_config_file(self) -> None:
        """Returns (False, False) when neither config path exists (fail-open)."""
        result = _hook._load_config("/nonexistent/path/that/does/not/exist")
        self.assertEqual(result, (False, False))

    def test_disabled_when_empty_repo_root(self) -> None:
        """Returns (False, False) when repo_root is an empty string (fail-open)."""
        result = _hook._load_config("")
        self.assertEqual(result, (False, False))

    def test_disabled_when_section_absent(self) -> None:
        """Returns (False, False) when files_touched_reconciliation key is absent."""
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "scripts" / "commit_guardian"
            config_dir.mkdir(parents=True)
            config_file = config_dir / "commit_guardian.json"
            config_file.write_text(
                json.dumps({"other_section": {}}), encoding="utf-8"
            )
            result = _hook._load_config(tmp)
            self.assertEqual(result, (False, False))

    def test_disabled_when_enabled_false_strict_false(self) -> None:
        """Returns (False, False) when both enabled and strict are explicitly false."""
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "scripts" / "commit_guardian"
            config_dir.mkdir(parents=True)
            config_file = config_dir / "commit_guardian.json"
            config_file.write_text(
                json.dumps({"files_touched_reconciliation": {"enabled": False, "strict": False}}),
                encoding="utf-8",
            )
            result = _hook._load_config(tmp)
            self.assertEqual(result, (False, False))

    def test_advisory_when_enabled_true_strict_false(self) -> None:
        """Returns (True, False) when enabled:true and strict:false (advisory mode)."""
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "scripts" / "commit_guardian"
            config_dir.mkdir(parents=True)
            config_file = config_dir / "commit_guardian.json"
            config_file.write_text(
                json.dumps({"files_touched_reconciliation": {"enabled": True, "strict": False}}),
                encoding="utf-8",
            )
            result = _hook._load_config(tmp)
            self.assertEqual(result, (True, False))

    def test_block_when_enabled_true_strict_true(self) -> None:
        """Returns (True, True) when enabled:true and strict:true (blocking mode)."""
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "scripts" / "commit_guardian"
            config_dir.mkdir(parents=True)
            config_file = config_dir / "commit_guardian.json"
            config_file.write_text(
                json.dumps({"files_touched_reconciliation": {"enabled": True, "strict": True}}),
                encoding="utf-8",
            )
            result = _hook._load_config(tmp)
            self.assertEqual(result, (True, True))

    def test_disabled_on_malformed_json(self) -> None:
        """Returns (False, False) (fail-open) when the config file contains invalid JSON."""
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "scripts" / "commit_guardian"
            config_dir.mkdir(parents=True)
            config_file = config_dir / "commit_guardian.json"
            config_file.write_text("{ this is not valid json }", encoding="utf-8")
            result = _hook._load_config(tmp)
            self.assertEqual(result, (False, False))

    def test_falls_back_to_templates_path(self) -> None:
        """Falls back to templates/ path when the primary scripts/ path is absent."""
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = (
                Path(tmp)
                / "templates"
                / "scripts"
                / "commit_guardian"
            )
            config_dir.mkdir(parents=True)
            config_file = config_dir / "commit_guardian.json"
            config_file.write_text(
                json.dumps({"files_touched_reconciliation": {"enabled": True, "strict": True}}),
                encoding="utf-8",
            )
            result = _hook._load_config(tmp)
            self.assertEqual(result, (True, True))


# ---------------------------------------------------------------------------
# Tests: main() three-state behaviour (AC BP-1100e-2)
# ---------------------------------------------------------------------------

_TICKET_REL = "tickets/bp_1100e2_test_ticket.md"
_SOURCE_FILE = "scripts/some_undeclared_source.py"


def _make_ticket_content(declared_source: bool) -> str:
    """Build minimal ticket content for three-state mode integration tests.

    Uses column-0 YAML block-sequence format (PyYAML default) so that the
    _parse_yaml_list_field regex with zero-or-more leading whitespace parses
    correctly.

    Args:
        declared_source: When True, the source file is in files_touched
            (clean — no undeclared files). When False, the source file is
            absent (undeclared — should trigger advisory or block).

    Returns:
        YAML-frontmatter ticket string suitable for _get_ticket_scope to parse.
    """
    if declared_source:
        files_yaml = (
            "- docs/some_doc.md\n"
            f"- {_SOURCE_FILE}\n"
        )
    else:
        files_yaml = "- docs/some_doc.md\n"
    return (
        "---\n"
        "status: done\n"
        "files_touched:\n"
        f"{files_yaml}"
        "---\n\n"
        "# Test Ticket\n"
    )


class TestMainThreeStateMode(unittest.TestCase):
    """Integration tests for main() three-state behaviour (AC BP-1100e-2).

    Tests cover: check-off (enabled:false), advisory (enabled:true+strict:false),
    and blocking (enabled:true+strict:true) states; plus fail-open paths.
    """

    def _run_main(
        self,
        *,
        enabled: bool,
        strict: bool,
        declared_source: bool,
    ) -> tuple[int, str]:
        """Run main() with a mocked repo and capture all output (stdout + stderr).

        Advisory and error text goes to stdout (print()); skip advisories go to
        stderr (print(..., file=sys.stderr)). Both are captured and concatenated
        so assertions can search for any output regardless of channel.

        Args:
            enabled: enabled flag for the mocked _load_config.
            strict: strict flag for the mocked _load_config.
            declared_source: When True, the source file is in files_touched.
                When False, the source file is absent (triggers violation).

        Returns:
            A (return_code, combined_output) tuple where combined_output is
            stdout + stderr concatenated.
        """
        with tempfile.TemporaryDirectory() as tmp:
            ticket_dir = Path(tmp) / "tickets"
            ticket_dir.mkdir()
            ticket_path = ticket_dir / "bp_1100e2_test_ticket.md"
            ticket_path.write_text(
                _make_ticket_content(declared_source), encoding="utf-8"
            )
            staged = [_TICKET_REL, _SOURCE_FILE]
            branch_diff: frozenset[str] = frozenset({_SOURCE_FILE})
            out_buf = io.StringIO()
            err_buf = io.StringIO()
            with patch.object(_hook, "_get_staged_files", return_value=staged):
                with patch.object(_hook, "_get_repo_root", return_value=tmp):
                    with patch.object(
                        _hook, "_get_branch_diff_files", return_value=branch_diff,
                    ):
                        with patch.object(
                            _hook, "_load_config", return_value=(enabled, strict),
                        ):
                            with contextlib.redirect_stdout(out_buf):
                                with contextlib.redirect_stderr(err_buf):
                                    code = _hook.main()
            return code, out_buf.getvalue() + err_buf.getvalue()

    def test_check_off_returns_zero_no_output(self) -> None:
        """enabled:false with undeclared source → exit 0, no advisory output."""
        code, stderr = self._run_main(enabled=False, strict=False, declared_source=False)
        self.assertEqual(code, 0)
        self.assertNotIn(_SOURCE_FILE, stderr, "Disabled check must produce no output")

    def test_check_off_enabled_key_absent_equivalent(self) -> None:
        """_load_config returns (False, False) when section absent → check is off."""
        with tempfile.TemporaryDirectory() as tmp:
            ticket_dir = Path(tmp) / "tickets"
            ticket_dir.mkdir()
            (ticket_dir / "t.md").write_text(
                "---\nstatus: done\nfiles_touched:\n- docs/some.md\n---\n",
                encoding="utf-8",
            )
            staged = ["tickets/t.md", "scripts/undeclared.py"]
            with patch.object(_hook, "_get_staged_files", return_value=staged):
                with patch.object(_hook, "_get_repo_root", return_value=tmp):
                    with patch.object(
                        _hook,
                        "_get_branch_diff_files",
                        return_value=frozenset({"scripts/undeclared.py"}),
                    ):
                        # No config file present → _load_config returns (False, False)
                        result = _hook.main()
            self.assertEqual(result, 0)

    def test_advisory_returns_zero_on_undeclared_files(self) -> None:
        """enabled:true, strict:false with undeclared source → exit 0, filename in output."""
        code, stderr = self._run_main(enabled=True, strict=False, declared_source=False)
        self.assertEqual(code, 0)
        self.assertIn(_SOURCE_FILE, stderr, "Advisory must name the undeclared file")

    def test_strict_returns_one_on_undeclared_files(self) -> None:
        """enabled:true, strict:true with undeclared source → exit 1, commit blocked."""
        code, _ = self._run_main(enabled=True, strict=True, declared_source=False)
        self.assertEqual(code, 1)

    def test_clean_advisory_returns_zero(self) -> None:
        """Advisory mode, all files declared → exit 0."""
        code, _ = self._run_main(enabled=True, strict=False, declared_source=True)
        self.assertEqual(code, 0)

    def test_clean_strict_returns_zero(self) -> None:
        """Strict mode, all files declared → exit 0 (nothing to block)."""
        code, _ = self._run_main(enabled=True, strict=True, declared_source=True)
        self.assertEqual(code, 0)

    def test_no_staged_files_returns_zero(self) -> None:
        """No staged files → exit 0 immediately (fail-open at the first gate)."""
        with patch.object(_hook, "_get_staged_files", return_value=[]):
            result = _hook.main()
            self.assertEqual(result, 0)

    def test_get_staged_files_returns_empty_on_subprocess_error(self) -> None:
        """_get_staged_files returns [] when subprocess raises — main() exits 0."""
        with patch(
            "subprocess.run", side_effect=subprocess.SubprocessError("git failed")
        ):
            result = _hook.main()
            self.assertEqual(result, 0)


class TestLoadConfigWrongShape(unittest.TestCase):
    """Tests that _load_config fails open on wrong-shape configs (AC BP-1100e-2)."""

    def _write_config(self, tmp: str, content: str) -> None:
        """Write content to the primary scripts/ config path."""
        config_dir = Path(tmp) / "scripts" / "commit_guardian"
        config_dir.mkdir(parents=True)
        (config_dir / "commit_guardian.json").write_text(content, encoding="utf-8")

    def test_null_section_returns_disabled(self) -> None:
        """files_touched_reconciliation: null → (False, False), no crash."""
        with tempfile.TemporaryDirectory() as tmp:
            self._write_config(tmp, '{"files_touched_reconciliation": null}')
            result = _hook._load_config(tmp)
            self.assertEqual(result, (False, False))

    def test_top_level_array_returns_disabled(self) -> None:
        """Top-level JSON array [] → (False, False), no crash."""
        with tempfile.TemporaryDirectory() as tmp:
            self._write_config(tmp, "[]")
            result = _hook._load_config(tmp)
            self.assertEqual(result, (False, False))

    def test_enabled_truthy_string_returns_disabled(self) -> None:
        """enabled: \"yes\" is not JSON true → enabled=False, not checked."""
        with tempfile.TemporaryDirectory() as tmp:
            self._write_config(
                tmp, '{"files_touched_reconciliation": {"enabled": "yes", "strict": true}}'
            )
            result = _hook._load_config(tmp)
            self.assertEqual(result, (False, True))

    def test_strict_truthy_string_not_enabled_as_strict(self) -> None:
        """enabled:true but strict:\"yes\" → (True, False); non-bool strict is not strict."""
        with tempfile.TemporaryDirectory() as tmp:
            self._write_config(
                tmp, '{"files_touched_reconciliation": {"enabled": true, "strict": "yes"}}'
            )
            result = _hook._load_config(tmp)
            self.assertEqual(result, (True, False))


if __name__ == "__main__":
    unittest.main()
