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
_SCRIPTS_COMMIT_GUARDIAN = _REPO_ROOT / "scripts" / "commit_guardian"


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
            raise ImportError(f"Cannot load spec for {module_name} from {directory}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    finally:
        if inserted and dir_str in sys.path:
            sys.path.remove(dir_str)


def _collect_modules(directory: Path) -> list[Path]:
    """Return sorted list of check_*.py and *_validators.py in *directory*.

    Args:
        directory: Directory to scan.

    Returns:
        Sorted list of matching .py file paths.
    """
    matches: list[Path] = []
    if not directory.is_dir():
        return matches
    for pyfile in sorted(directory.iterdir()):
        if not pyfile.is_file():
            continue
        name = pyfile.name
        if (name.startswith("check_") or name.endswith("_validators.py")) and name.endswith(".py"):
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


if __name__ == "__main__":
    unittest.main()
