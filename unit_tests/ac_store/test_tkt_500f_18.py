"""
MODULE: test_tkt_500f_18
GOAL: RED test stubs for TKT-500f-18. Verifies that importing
      scripts/ac_store/generate_ticket_from_ac.py does NOT reconfigure
      global logging (no logging.basicConfig side effect) and that the
      kebab-to-graph-id mapping is obtained from a side-effect-free source.

      Current bug:
        _load_migration_map() exec's scripts/migrate_component_vocab.py at
        module import time via importlib.util.spec_from_file_location +
        exec_module. migrate_component_vocab.py has:
            logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
        at line 51. This fires during exec, reconfiguring the root logger as
        a side effect of importing the generator.

      All three tests must be RED on current code. They become GREEN once
      _load_migration_map is replaced with a side-effect-free source
      (e.g. parse docs/components.json or inline the MIGRATION_MAP dict).

TICKET: TICKET-20260721-TKT-500f-18.md
COVERS: TKT-500f-18
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Path setup: unit_tests/ac_store/ is 3 levels below the repo root.
#
# IMPORTANT: generate_ticket_from_ac is NOT imported at module level here.
# Importing it at module level would exec migrate_component_vocab.py (via
# _load_migration_map) which calls logging.basicConfig — the very side
# effect under test — before any test can intercept it.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_AC_STORE_DIR = str(_REPO_ROOT / "scripts" / "ac_store")

if _SCRIPTS_AC_STORE_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_AC_STORE_DIR)

_MODULE_NAME = "generate_ticket_from_ac"


# ---------------------------------------------------------------------------
# Helper: force a fresh module import (re-runs module-level code)
# ---------------------------------------------------------------------------

def _fresh_import():
    """Remove the module from sys.modules and re-import it.

    This forces generate_ticket_from_ac's module-level code (including
    _COMPONENT_MIGRATION_MAP = _load_migration_map()) to re-execute,
    making import-time side effects observable in each test.
    """
    sys.modules.pop(_MODULE_NAME, None)
    return importlib.import_module(_MODULE_NAME)


# ===========================================================================
# Test class 1: logging side-effect tests (AC-2, AC-3)
# ===========================================================================


class TestImportLoggingSideEffects(unittest.TestCase):
    """TKT-500f-18 AC-2/AC-3: Importing generate_ticket_from_ac must not
    reconfigure global logging (no logging.basicConfig call, no root-logger
    handler mutation).
    """

    def setUp(self):
        """Save root-logger state; clear handlers so basicConfig would add one if called."""
        root = logging.getLogger()
        self._saved_handlers = list(root.handlers)
        self._saved_level = root.level
        # Remove all handlers so the "no handlers → basicConfig adds one" path is live.
        for h in list(root.handlers):
            root.removeHandler(h)
        # Save the current module reference (if any) so tearDown can restore it.
        # This keeps sys.modules clean for later tests (e.g. test_tkt_500f_18_i's
        # importlib.reload) that require the module to be registered there.
        self._saved_module = sys.modules.get(_MODULE_NAME)
        # Remove cached module so each test starts from a fresh import.
        sys.modules.pop(_MODULE_NAME, None)

    def tearDown(self):
        """Restore root-logger state and sys.modules to their pre-setUp state."""
        root = logging.getLogger()
        for h in list(root.handlers):
            root.removeHandler(h)
        for h in self._saved_handlers:
            root.addHandler(h)
        root.setLevel(self._saved_level)
        # Remove the freshly-imported module (from _fresh_import or the test body).
        sys.modules.pop(_MODULE_NAME, None)
        # Restore the module that existed before setUp so later tests can find it
        # in sys.modules (importlib.reload requires the module to be registered).
        if self._saved_module is not None:
            sys.modules[_MODULE_NAME] = self._saved_module

    # ------------------------------------------------------------------
    # Test 1 of 3
    # ------------------------------------------------------------------

    def test_import_does_not_call_logging_basicconfig(self):
        # covers: TKT-500f-18
        """Importing generate_ticket_from_ac must NOT call logging.basicConfig.

        AC-2: no logging.basicConfig call (or equivalent root-logger
        reconfiguration) runs as a side effect of importing the generator
        or the mapping source.

        Strategy:
          Patch logging.basicConfig before the fresh import.  The patched
          mock records every call.  After the import completes, assert the
          mock was never called.

        RED on current code:
          _load_migration_map() exec's migrate_component_vocab.py.  That
          script has ``logging.basicConfig(level=logging.INFO, ...)`` at
          module level (line 51).  exec_module runs the whole script, so
          basicConfig IS called → mock_basic_config.assert_not_called()
          raises AssertionError.

        GREEN after fix:
          Replace the exec-based _load_migration_map with a side-effect-free
          source (e.g. inline the dict or parse docs/components.json) that
          never calls logging.basicConfig.  Then the mock is never invoked.
        """
        with patch("logging.basicConfig") as mock_basic_config:
            importlib.import_module(_MODULE_NAME)
            mock_basic_config.assert_not_called()

    # ------------------------------------------------------------------
    # Test 2 of 3
    # ------------------------------------------------------------------

    def test_import_preserves_preexisting_root_logging_config(self):
        # covers: TKT-500f-18
        """Root-logger handlers and level must be unchanged after the import.

        AC-3: a program that imports the generator keeps whatever root
        logging configuration it had before the import (handlers and level
        are unchanged by the import).

        setUp has already cleared all root-logger handlers, simulating a
        fresh program that has not configured logging yet.  After the fresh
        import:
          - handlers must still be [] (basicConfig must not have added one).
          - level must be unchanged (basicConfig(level=INFO) must not have
            set the root logger's level to INFO).

        RED on current code:
          migrate_component_vocab.py's logging.basicConfig(level=logging.INFO,
          ...) fires during exec_module. Python's basicConfig adds a
          StreamHandler when the root logger has no handlers → the list
          changes from [] to [<StreamHandler>] → the assertEqual fails.
          Additionally, if root.level was 30 (WARNING, the default), basicConfig
          resets it to 20 (INFO) → the level check also fails.

        GREEN after fix:
          The side-effect-free mapping source never calls basicConfig, so the
          root logger's handler list and level remain exactly as they were
          before the import.
        """
        root = logging.getLogger()
        # setUp cleared handlers; record the clean baseline.
        handlers_before = list(root.handlers)
        level_before = root.level

        importlib.import_module(_MODULE_NAME)

        handlers_after = list(root.handlers)
        level_after = root.level

        self.assertEqual(
            handlers_before,
            handlers_after,
            (
                f"Root-logger handler list changed after importing the generator. "
                f"Before: {handlers_before!r}  After: {handlers_after!r}. "
                f"This indicates logging.basicConfig was called as an import side "
                f"effect (it adds a StreamHandler when no handlers are present). "
                f"Current cause: _load_migration_map exec's migrate_component_vocab.py "
                f"which calls logging.basicConfig() at module level (line 51). "
                f"Fix: replace the exec-based path with a side-effect-free source "
                f"(e.g. parse docs/components.json or inline a plain dict)."
            ),
        )
        self.assertEqual(
            level_before,
            level_after,
            (
                f"Root-logger level changed after importing the generator. "
                f"Before: {level_before}  After: {level_after}. "
                f"logging.basicConfig(level=logging.INFO) resets the level to "
                f"INFO (20) when called. "
                f"Fix: stop exec-ing migrate_component_vocab.py at import time."
            ),
        )


# ===========================================================================
# Test class 2: side-effect-free mapping source (AC-1)
# ===========================================================================


class TestMappingFromSideEffectFreeSource(unittest.TestCase):
    """TKT-500f-18 AC-1: The kebab-to-graph-id mapping is obtainable from a
    side-effect-free source even when migrate_component_vocab.py is absent.
    """

    def setUp(self):
        root = logging.getLogger()
        self._saved_handlers = list(root.handlers)
        self._saved_level = root.level
        for h in list(root.handlers):
            root.removeHandler(h)
        # Save the current module reference (if any) so tearDown can restore it.
        self._saved_module = sys.modules.get(_MODULE_NAME)
        sys.modules.pop(_MODULE_NAME, None)

    def tearDown(self):
        root = logging.getLogger()
        for h in list(root.handlers):
            root.removeHandler(h)
        for h in self._saved_handlers:
            root.addHandler(h)
        root.setLevel(self._saved_level)
        # Remove the freshly-imported module.
        sys.modules.pop(_MODULE_NAME, None)
        # Restore the module that existed before setUp so later tests can find it
        # in sys.modules (importlib.reload requires the module to be registered).
        if self._saved_module is not None:
            sys.modules[_MODULE_NAME] = self._saved_module

    # ------------------------------------------------------------------
    # Test 3 of 3
    # ------------------------------------------------------------------

    def test_mapping_read_from_side_effect_free_source(self):
        # covers: TKT-500f-18
        """The kebab-to-graph-id mapping must be obtainable even when
        migrate_component_vocab.py is inaccessible — proving the mapping
        comes from a side-effect-free source (docs/components.json or a
        plain data module), not from exec-ing the sibling script.

        AC-1: the mapping is read from a side-effect-free source — parsing
        docs/components.json or importing a plain data module — rather than
        from a module whose import runs configuration side effects.

        Test strategy:
          Patch importlib.util.spec_from_file_location so that any call
          referencing 'migrate_component_vocab' raises OSError (simulating
          the sibling script being absent). Non-migrate calls pass through
          to the real implementation so the import machinery is unaffected.

          After the import, assert:
            (a) _COMPONENT_MIGRATION_MAP is non-empty, AND
            (b) the canonical mapping 'ticket-creation' → 'ticket_creation_pipeline'
                is present and correct.

        RED on current code:
          _load_migration_map calls spec_from_file_location("migrate_component_vocab",
          ...) → OSError is raised → the try/except catches it and returns {} →
          _COMPONENT_MIGRATION_MAP = {} → assertIn("ticket-creation", {}) fails.

        GREEN after fix:
          The fixed code reads from docs/components.json (or a plain dict) WITHOUT
          calling spec_from_file_location for migrate_component_vocab.  The OSError
          is never raised, and the mapping contains the canonical entries.

        Known canonical entry (from MIGRATION_MAP in migrate_component_vocab.py):
          'ticket-creation' -> 'ticket_creation_pipeline'
        """
        # Capture the real function BEFORE patching so non-migrate calls work.
        _original_spec = importlib.util.spec_from_file_location
        # TRY003: extract message to variable so ruff does not flag the raise site.
        _blocked_msg = "test-tkt-500f-18: migrate_component_vocab exec blocked"

        def _raise_for_migrate_vocab(name, location=None, *args, **kwargs):
            """Block exec of migrate_component_vocab; pass all other calls through."""
            if "migrate_component_vocab" in str(name) or (
                location is not None
                and "migrate_component_vocab" in str(location)
            ):
                raise OSError(_blocked_msg)
            return _original_spec(name, location, *args, **kwargs)

        with patch(
            "importlib.util.spec_from_file_location",
            side_effect=_raise_for_migrate_vocab,
        ):
            mod = importlib.import_module(_MODULE_NAME)

        migration_map = getattr(mod, "_COMPONENT_MIGRATION_MAP", None)

        self.assertIsNotNone(
            migration_map,
            (
                "_COMPONENT_MIGRATION_MAP attribute is absent from the module after "
                "a fresh import where migrate_component_vocab.py was blocked. "
                "The module must expose the kebab-to-graph-id mapping regardless of "
                "whether the sibling script is accessible."
            ),
        )
        self.assertIn(
            "ticket-creation",
            migration_map,
            (
                f"Known kebab key 'ticket-creation' is missing from "
                f"_COMPONENT_MIGRATION_MAP when migrate_component_vocab.py is "
                f"inaccessible (OSError injected by test). "
                f"Current map contents: {migration_map!r}. "
                f"This proves _load_migration_map relies exclusively on exec-ing "
                f"migrate_component_vocab.py (exec path returns {{}} on OSError). "
                f"Fix: read the mapping from docs/components.json or inline the "
                f"MIGRATION_MAP dict so the mapping is available without exec."
            ),
        )
        self.assertEqual(
            migration_map.get("ticket-creation"),
            "ticket_creation_pipeline",
            (
                f"'ticket-creation' did not resolve to 'ticket_creation_pipeline'. "
                f"Got: {migration_map.get('ticket-creation')!r}. "
                f"The side-effect-free mapping source must preserve the canonical "
                f"kebab-to-graph-id entries, including "
                f"'ticket-creation' → 'ticket_creation_pipeline'."
            ),
        )


if __name__ == "__main__":
    unittest.main()
