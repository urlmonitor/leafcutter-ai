"""
MODULE: test_commit_guardian_imports
GOAL: Package-level import smoke test — every check_*.py and *_validators.py
      in scripts/commit_guardian/ must import cleanly, so a missing module
      fails this test rather than silently disabling a hook.
BUSINESS CONTEXT: GE-103 regression guard. diagram_type_validators was lost in
      the empty-tree corruption merge (2c2aa22), causing check_doc_frontmatter.py
      (via frontmatter_validators → diagram_type_validators) to raise
      "ModuleNotFoundError: No module named 'diagram_type_validators'" and
      silently disable ALL doc-frontmatter enforcement in consumer repos.
      This smoke test ensures that kind of regression is caught immediately
      rather than discovered in production via a silent hook bypass.
ARCHITECTURE: Each module is imported in-process via importlib.util with
      scripts/commit_guardian/ added to sys.path so inter-module dependencies
      within that directory resolve naturally. Failures are collected and
      reported per-module via subTest.

====================================================================
DECISION HISTORY
====================================================================
- 2026-07-08 [python-coder/GE-103]: Initial implementation.
  Scans scripts/commit_guardian/ for check_*.py and *_validators.py, then
  tries a live import of each. diagram_type_validators is tested both as a
  general import and with specific validate_diagram_type behaviour assertions
  to confirm GE-105 canonical enum values (data_flow, user_flow, agent_flow)
  are accepted and legacy alias 'dataflow' is retained.
====================================================================
"""

from __future__ import annotations

import importlib.util
import os
import sys
import subprocess
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
# GE-103 fix: target the canonical template dir (tracked in git, has all scripts).
# The runtime dir (scripts/commit_guardian/) is gitignored and only exists after
# build.py runs — using it here would cause CI failures on fresh checkouts.
_SCRIPTS_COMMIT_GUARDIAN = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"

# Modules with external (non-stdlib) or conditionally-deployed dependencies that
# are not always available in CI or fresh checkouts. These are excluded from the
# broad import scan — their own dedicated tests (if any) handle them separately.
# Excluding a module here does NOT exempt it from GE-103: the specific
# diagram_type_validators tests below still provide targeted coverage.
# AC-3 (TICKET-20260709-CommitGuardianHardeningFollowups): docstring_parser is
# now declared in requirements-dev.txt (>=0.15), so check_docstrings and
# docstring_validators are no longer excluded from the broad import scan.
_EXTERNAL_DEP_MODULES: frozenset[str] = frozenset({
    "check_secrets",         # needs scan_secrets (deployed by security-scanner skill)
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_module_from_dir(module_name: str, directory: Path):
    """Import a module by name from a specific directory.

    Temporarily inserts *directory* at the front of sys.path so that all
    relative imports within that package resolve correctly, then removes it
    after import.

    Args:
        module_name: Bare module name (no extension), e.g. ``"diagram_type_validators"``.
        directory: Directory to add to sys.path before importing.

    Returns:
        The imported module object.

    Raises:
        ImportError: If the module cannot be imported.
        ModuleNotFoundError: If the module file does not exist.
    """
    dir_str = str(directory)
    inserted = False
    try:
        if dir_str not in sys.path:
            sys.path.insert(0, dir_str)
            inserted = True
        if module_name in sys.modules:
            return sys.modules[module_name]
        spec = importlib.util.spec_from_file_location(
            module_name,
            directory / f"{module_name}.py",
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load spec for {module_name} from {directory}")  # noqa: TRY003
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    finally:
        if inserted and dir_str in sys.path:
            sys.path.remove(dir_str)


def _collect_modules(directory: Path) -> list[Path]:
    """Return sorted list of check_*.py and *_validators.py in *directory*.

    Excludes modules whose stems are listed in _EXTERNAL_DEP_MODULES — these
    have third-party or conditionally-deployed imports that are not guaranteed
    in all CI environments. Their absence from this list does NOT exempt them
    from GE-103; targeted tests handle key modules (e.g. diagram_type_validators)
    explicitly below.

    Args:
        directory: Directory to scan.

    Returns:
        Sorted list of matching .py file paths (external-dep modules excluded).
    """
    matches: list[Path] = []
    if not directory.is_dir():
        return matches
    for pyfile in sorted(directory.iterdir()):
        if not pyfile.is_file():
            continue
        name = pyfile.name
        if (name.startswith("check_") or name.endswith("_validators.py")) and name.endswith(".py"):
            if pyfile.stem not in _EXTERNAL_DEP_MODULES:
                matches.append(pyfile)
    return matches


# ---------------------------------------------------------------------------
# GE-103 smoke test: every module imports cleanly
# ---------------------------------------------------------------------------


class TestCommitGuardianModulesImportCleanly(unittest.TestCase):
    """GE-103: every check_*.py and *_validators.py in scripts/commit_guardian/ must import cleanly.

    A missing or broken module causes a ModuleNotFoundError that silently
    disables the hook. This test fails loudly when that happens so the
    regression is caught immediately rather than in production.
    """

    def test_scripts_commit_guardian_directory_exists(self) -> None:
        """The scripts/commit_guardian/ directory must exist.

        If it is absent, all subsequent import tests are meaningless.
        """
        self.assertTrue(
            _SCRIPTS_COMMIT_GUARDIAN.is_dir(),
            msg=(
                f"scripts/commit_guardian/ directory not found at {_SCRIPTS_COMMIT_GUARDIAN}. "
                "The runtime commit_guardian package must exist."
            ),
        )

    def test_all_modules_found(self) -> None:
        """At least one check_*.py or *_validators.py must be present.

        An empty directory is treated as a structural failure — something has
        gone wrong if there are no hook modules at all.
        """
        modules = _collect_modules(_SCRIPTS_COMMIT_GUARDIAN)
        self.assertGreater(
            len(modules),
            0,
            msg=(
                "No check_*.py or *_validators.py files found in "
                f"{_SCRIPTS_COMMIT_GUARDIAN}. Expected at least one hook module."
            ),
        )

    def test_each_module_imports_cleanly(self) -> None:
        """Each check_*.py and *_validators.py module must import without error.

        Uses subTest so all failures are surfaced in one pass rather than
        stopping at the first ModuleNotFoundError.
        """
        modules = _collect_modules(_SCRIPTS_COMMIT_GUARDIAN)
        # Run as subprocess with PYTHONPATH so the in-process sys.modules cache
        # does not interfere, and so each module is tested in isolation.
        env = {**os.environ, "PYTHONPATH": str(_SCRIPTS_COMMIT_GUARDIAN)}

        for pyfile in modules:
            module_name = pyfile.stem
            with self.subTest(module=module_name):
                try:
                    result = subprocess.run(
                        [sys.executable, "-c", f"import {module_name}"],
                        capture_output=True,
                        text=True,
                        timeout=15,
                        env=env,
                    )
                except subprocess.TimeoutExpired:
                    self.fail(
                        f"{module_name}: import timed out after 15 s — "
                        "check for blocking module-level code."
                    )
                self.assertEqual(
                    result.returncode,
                    0,
                    msg=(
                        f"{module_name} failed to import cleanly.\n"
                        f"stderr: {result.stderr.strip()}"
                    ),
                )


# ---------------------------------------------------------------------------
# GE-103 targeted test: diagram_type_validators specifically
# ---------------------------------------------------------------------------


class TestDiagramTypeValidatorsImportable(unittest.TestCase):
    """GE-103: diagram_type_validators must be importable from scripts/commit_guardian/.

    This class tests the specific module that was lost in the corruption merge
    and caused the silent hook-bypass defect. Tests are more targeted than the
    general smoke test above.
    """

    def _load_mod(self):
        """Load diagram_type_validators from scripts/commit_guardian/.

        Returns:
            The loaded module.
        """
        mod_name = "diagram_type_validators"
        # Clear any cached version to avoid cross-test interference.
        sys.modules.pop(mod_name, None)
        return _import_module_from_dir(mod_name, _SCRIPTS_COMMIT_GUARDIAN)

    def test_diagram_type_validators_file_exists(self) -> None:
        """diagram_type_validators.py must exist in scripts/commit_guardian/.

        This is the module that was lost — its absence causes
        "ModuleNotFoundError: No module named 'diagram_type_validators'" when
        check_doc_frontmatter.py runs.
        """
        target = _SCRIPTS_COMMIT_GUARDIAN / "diagram_type_validators.py"
        self.assertTrue(
            target.exists(),
            msg=(
                f"diagram_type_validators.py not found at {target}. "
                "GE-103: this module must exist so frontmatter_validators can "
                "import it without ModuleNotFoundError."
            ),
        )

    def test_diagram_type_validators_imports_without_error(self) -> None:
        """diagram_type_validators must import cleanly with no exception."""
        try:
            mod = self._load_mod()
        except ImportError as exc:
            self.fail(
                f"diagram_type_validators raised ImportError on import: {exc}\n"
                "GE-103: this module must be importable to keep hook enforcement live."
            )
        self.assertIsNotNone(mod)

    def test_validate_diagram_type_is_callable(self) -> None:
        """validate_diagram_type must be a callable exported by the module."""
        mod = self._load_mod()
        self.assertTrue(
            callable(getattr(mod, "validate_diagram_type", None)),
            msg="validate_diagram_type is not callable in diagram_type_validators.",
        )

    def test_validate_diagram_type_returns_empty_for_none(self) -> None:
        """validate_diagram_type returns [] when diagram_type is absent from frontmatter."""
        mod = self._load_mod()
        result = mod.validate_diagram_type({})
        self.assertEqual(result, [], msg="Expected empty list for frontmatter with no diagram_type.")

    def test_validate_diagram_type_accepts_known_values(self) -> None:
        """validate_diagram_type returns [] for every known diagram_type enum value."""
        mod = self._load_mod()
        known_values = [
            "context", "container", "component", "sequence",
            "erd", "state", "none",
        ]
        for value in known_values:
            with self.subTest(value=value):
                result = mod.validate_diagram_type({"diagram_type": value})
                self.assertEqual(
                    result,
                    [],
                    msg=f"Expected [] for known value '{value}', got {result!r}.",
                )

    def test_validate_diagram_type_returns_error_for_unknown_value(self) -> None:
        """validate_diagram_type returns a non-empty error list for an unknown value."""
        mod = self._load_mod()
        result = mod.validate_diagram_type({"diagram_type": "totally_invalid_xyz"})
        self.assertIsInstance(result, list)
        self.assertGreater(
            len(result),
            0,
            msg="Expected at least one error message for an unknown diagram_type value.",
        )
        combined = " ".join(result)
        self.assertIn(
            "totally_invalid_xyz",
            combined,
            msg="Error message must mention the invalid value.",
        )


# ---------------------------------------------------------------------------
# GE-105 targeted test: canonical enum values accepted
# ---------------------------------------------------------------------------


class TestGE105CanonicalEnumValuesAccepted(unittest.TestCase):
    """GE-105: data_flow, user_flow, agent_flow must be accepted by validate_diagram_type.

    These three values were missing from the stale hardcoded list, causing
    legitimate diagrams to be rejected with "unknown diagram_type: agent_flow".
    The fallback list in diagram_type_validators.py must include them all.
    Also verifies the legacy alias 'dataflow' is retained for backward
    compatibility.
    """

    def _load_mod(self):
        """Load diagram_type_validators for the GE-105 assertions."""
        mod_name = "diagram_type_validators"
        sys.modules.pop(mod_name, None)
        return _import_module_from_dir(mod_name, _SCRIPTS_COMMIT_GUARDIAN)

    def test_data_flow_accepted(self) -> None:
        """GE-105: 'data_flow' must be accepted as a valid diagram_type value."""
        mod = self._load_mod()
        result = mod.validate_diagram_type({"diagram_type": "data_flow"})
        self.assertEqual(
            result,
            [],
            msg=(
                f"Expected [] for 'data_flow', got {result!r}. "
                "GE-105: data_flow must be in the allowed enum."
            ),
        )

    def test_user_flow_accepted(self) -> None:
        """GE-105: 'user_flow' must be accepted as a valid diagram_type value."""
        mod = self._load_mod()
        result = mod.validate_diagram_type({"diagram_type": "user_flow"})
        self.assertEqual(
            result,
            [],
            msg=(
                f"Expected [] for 'user_flow', got {result!r}. "
                "GE-105: user_flow must be in the allowed enum."
            ),
        )

    def test_agent_flow_accepted(self) -> None:
        """GE-105: 'agent_flow' must be accepted as a valid diagram_type value."""
        mod = self._load_mod()
        result = mod.validate_diagram_type({"diagram_type": "agent_flow"})
        self.assertEqual(
            result,
            [],
            msg=(
                f"Expected [] for 'agent_flow', got {result!r}. "
                "GE-105: agent_flow must be in the allowed enum."
            ),
        )

    def test_dataflow_legacy_alias_still_accepted(self) -> None:
        """GE-105: legacy alias 'dataflow' must still be accepted (backward compat)."""
        mod = self._load_mod()
        result = mod.validate_diagram_type({"diagram_type": "dataflow"})
        self.assertEqual(
            result,
            [],
            msg=(
                f"Expected [] for legacy alias 'dataflow', got {result!r}. "
                "GE-105: backward compatibility requires retaining 'dataflow'."
            ),
        )


# ---------------------------------------------------------------------------
# AC-2: Ancestor-walk SSOT resolution and WARNING emission
# ---------------------------------------------------------------------------


class TestDiagramTypeValidatorsAncestorWalk(unittest.TestCase):
    """AC-2 (TICKET-20260709-CommitGuardianHardeningFollowups):
    Behavioral tests for the ported ancestor-walk SSOT resolution.

    The canonical diagram_type_validators.py previously used a fixed
    parents[2] path that never resolved to an existing file, making the
    except blocks unreachable and causing silent fallback on every execution.
    After the fix, _find_diagram_types_json() walks ancestor directories and
    WARNING logging is emitted on I/O or parse errors.
    """

    def _load_fresh_mod(self):
        """Load diagram_type_validators fresh from the canonical template path.

        Returns:
            The loaded module with a cleared cache.
        """
        mod_name = "diagram_type_validators"
        sys.modules.pop(mod_name, None)
        mod = _import_module_from_dir(mod_name, _SCRIPTS_COMMIT_GUARDIAN)
        mod._DIAGRAM_TYPES_CACHE = None
        return mod

    def test_find_diagram_types_json_returns_path_or_none(self) -> None:
        """AC-2: _find_diagram_types_json() returns a Path or None (does not raise).

        When running in the real project tree, it should find config/diagram_types.json
        at an ancestor of the canonical template directory.
        """
        mod = self._load_fresh_mod()
        result = mod._find_diagram_types_json()
        # Must be either None or a Path to an existing file named diagram_types.json
        if result is not None:
            self.assertIsInstance(result, Path)
            self.assertTrue(result.exists(), msg=f"Returned path does not exist: {result}")
            self.assertEqual(result.name, "diagram_types.json")

    def test_ancestor_walk_finds_config_via_start_dir_override(self) -> None:
        """AC-2: ancestor walk uses _start_dir override to find config/diagram_types.json.

        Creates a real temporary directory tree simulating a deployed project:
          tmproot/
            config/diagram_types.json   <- target file
            some/deep/path/             <- simulated script location

        Calls _find_diagram_types_json(_start_dir=some/deep/path/) and verifies
        the walk ascends to find the config file at tmproot/config/.
        """
        import tempfile

        mod = self._load_fresh_mod()
        with tempfile.TemporaryDirectory() as td:
            tmproot = Path(td)
            # Create the config directory and JSON file
            config_dir = tmproot / "config"
            config_dir.mkdir()
            dtj = config_dir / "diagram_types.json"
            dtj.write_text(
                '{"diagram_types": {"test_type": {"description": "test"}}}',
                encoding="utf-8",
            )
            # Create a simulated deep "deployed script" directory
            script_dir = tmproot / "some" / "deep" / "path"
            script_dir.mkdir(parents=True)

            result = mod._find_diagram_types_json(_start_dir=script_dir)

        self.assertIsNotNone(result, msg="Ancestor walk must find config/diagram_types.json.")
        self.assertEqual(result.name, "diagram_types.json")

    def test_ancestor_walk_finds_leafcutter_config_layout(self) -> None:
        """AC-2: ancestor walk finds leafcutter/config/diagram_types.json layout.

        Creates a real temporary directory tree simulating a consumer-project layout:
          tmproot/
            leafcutter/config/diagram_types.json   <- target file
            scripts/commit_guardian/               <- simulated script location
        """
        import tempfile

        mod = self._load_fresh_mod()
        with tempfile.TemporaryDirectory() as td:
            tmproot = Path(td)
            # Create the leafcutter/config directory and JSON file
            lc_config = tmproot / "leafcutter" / "config"
            lc_config.mkdir(parents=True)
            dtj = lc_config / "diagram_types.json"
            dtj.write_text(
                '{"diagram_types": {"consumer_type": {}}}',
                encoding="utf-8",
            )
            # Simulated deployed script directory
            script_dir = tmproot / "scripts" / "commit_guardian"
            script_dir.mkdir(parents=True)

            result = mod._find_diagram_types_json(_start_dir=script_dir)

        self.assertIsNotNone(
            result,
            msg="Ancestor walk must find leafcutter/config/diagram_types.json layout.",
        )
        self.assertIn("leafcutter", str(result))

    def test_warning_emitted_on_malformed_json(self) -> None:
        """AC-2: WARNING is logged when diagram_types.json is malformed.

        Uses a real tempdir with malformed JSON and patches _find_diagram_types_json
        to return that path, then verifies a WARNING log record is produced.
        """
        import logging
        import tempfile
        from unittest.mock import patch

        mod = self._load_fresh_mod()

        with tempfile.TemporaryDirectory() as td:
            malformed = Path(td) / "diagram_types.json"
            malformed.write_text("{ this is not valid json !!", encoding="utf-8")

            log_records: list[logging.LogRecord] = []

            class _Capture(logging.Handler):
                def emit(self, record: logging.LogRecord) -> None:
                    log_records.append(record)

            handler = _Capture()
            target_logger = logging.getLogger("diagram_type_validators")
            target_logger.addHandler(handler)
            target_logger.setLevel(logging.WARNING)
            mod._DIAGRAM_TYPES_CACHE = None

            try:
                with patch.object(mod, "_find_diagram_types_json", return_value=malformed):
                    result = mod._load_diagram_types()
            finally:
                target_logger.removeHandler(handler)

        # Must fall back to the config constant (non-empty dict)
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0, msg="Fallback must produce a non-empty dict.")
        # Must have emitted at least one WARNING
        warning_records = [r for r in log_records if r.levelno >= logging.WARNING]
        self.assertGreater(
            len(warning_records),
            0,
            msg="AC-2: malformed JSON must produce a WARNING log record.",
        )
        combined = " ".join(r.getMessage() for r in warning_records)
        self.assertIn(
            str(malformed),
            combined,
            msg="WARNING message must include the malformed file path.",
        )

    def test_warning_emitted_on_os_error(self) -> None:
        """AC-2: WARNING is logged when diagram_types.json raises OSError on open.

        Patches _find_diagram_types_json to return an existing path, then patches
        open() to raise OSError, and verifies a WARNING log record is produced.
        """
        import logging
        import tempfile
        from unittest.mock import MagicMock, patch

        mod = self._load_fresh_mod()

        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "diagram_types.json"
            target.write_text("{}", encoding="utf-8")

            log_records: list[logging.LogRecord] = []

            class _Capture(logging.Handler):
                def emit(self, record: logging.LogRecord) -> None:
                    log_records.append(record)

            handler = _Capture()
            target_logger = logging.getLogger("diagram_type_validators")
            target_logger.addHandler(handler)
            target_logger.setLevel(logging.WARNING)
            mod._DIAGRAM_TYPES_CACHE = None

            def _raise_oserror(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
                raise OSError("Permission denied (mocked)")  # noqa: TRY003

            try:
                with patch.object(mod, "_find_diagram_types_json", return_value=target):
                    with patch("builtins.open", side_effect=_raise_oserror):
                        result = mod._load_diagram_types()
            finally:
                target_logger.removeHandler(handler)

        self.assertIsInstance(result, dict)
        warning_records = [r for r in log_records if r.levelno >= logging.WARNING]
        self.assertGreater(
            len(warning_records),
            0,
            msg="AC-2: OSError on open must produce a WARNING log record.",
        )

    def test_validate_diagram_type_accepts_data_flow(self) -> None:
        """AC-2: validate_diagram_type still accepts 'data_flow' after the fix."""
        mod = self._load_fresh_mod()
        result = mod.validate_diagram_type({"diagram_type": "data_flow"})
        self.assertEqual(result, [])

    def test_validate_diagram_type_accepts_user_flow(self) -> None:
        """AC-2: validate_diagram_type still accepts 'user_flow' after the fix."""
        mod = self._load_fresh_mod()
        result = mod.validate_diagram_type({"diagram_type": "user_flow"})
        self.assertEqual(result, [])

    def test_validate_diagram_type_accepts_agent_flow(self) -> None:
        """AC-2: validate_diagram_type still accepts 'agent_flow' after the fix."""
        mod = self._load_fresh_mod()
        result = mod.validate_diagram_type({"diagram_type": "agent_flow"})
        self.assertEqual(result, [])

    def test_validate_diagram_type_accepts_dataflow_legacy(self) -> None:
        """AC-2: validate_diagram_type still accepts legacy alias 'dataflow'."""
        mod = self._load_fresh_mod()
        result = mod.validate_diagram_type({"diagram_type": "dataflow"})
        self.assertEqual(result, [])

    def test_validate_diagram_type_rejects_bogus_value(self) -> None:
        """AC-2: validate_diagram_type rejects unknown values after the fix."""
        mod = self._load_fresh_mod()
        result = mod.validate_diagram_type({"diagram_type": "totally_bogus_xyz"})
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertIn("totally_bogus_xyz", " ".join(result))


if __name__ == "__main__":
    unittest.main()
