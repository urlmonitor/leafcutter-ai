#!/usr/bin/env python3
"""
MODULE: test_tkt_500f_18_i
GOAL: RED test stubs for TKT-500f-18-i.
      Verifies that generate_ticket_from_ac._load_migration_map() degrades
      gracefully when the kebab-to-graph-id mapping source is malformed or
      unavailable, and that the module remains importable under that condition.

Behavior under test (AC TKT-500f-18-i, L3 edge of TKT-500f-18):

  A malformed or unavailable mapping source (e.g. docs/components.json missing
  or containing invalid JSON, or the sibling module raising SyntaxError or
  another error when loaded) must be caught so that:

    1. Importing scripts/ac_store/generate_ticket_from_ac.py does NOT raise.
    2. The generator degrades to a logged fallback mapping ({}) with a WARNING
       that names the failed source.
    3. A well-formed source is still loaded and used normally — the fallback is
       not triggered unnecessarily (no regression of TKT-500f-18).

Why all three tests are RED with the current implementation
-----------------------------------------------------------
The current _load_migration_map() except clause is:

    except (OSError, AttributeError, ImportError) as exc:

SyntaxError and RuntimeError are NOT in the tuple.  When the sibling module has
a syntax error, exec_module raises SyntaxError which propagates uncaught through
_load_migration_map() and out of the module-level assignment
``_COMPONENT_MIGRATION_MAP = _load_migration_map()``, making the generator
module un-importable.

Tests 1 and 2 inject SyntaxError and assert graceful fallback — both fail (RED)
because the exception propagates instead of returning {}.

Test 3 patches the sibling Python module to return an EMPTY MIGRATION_MAP, then
asserts that _load_migration_map returns a NON-EMPTY result (sourced from
docs/components.json, the future primary source per TKT-500f-18).  It fails
(RED) because the current implementation reads only from the Python sibling
and returns {} when that sibling's MIGRATION_MAP is empty.

TICKET: TICKET-20260721-TKT-500f-18-i.md
COVERS: TKT-500f-18-i
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Path setup: unit_tests/ac_store/ is 3 levels below the repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))
# Also expose scripts/ so generate_ticket_from_ac's own imports can resolve
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import generate_ticket_from_ac as _gen_module  # noqa: E402
from generate_ticket_from_ac import _load_migration_map  # noqa: E402


# ---------------------------------------------------------------------------
# Logging helper
# ---------------------------------------------------------------------------


class _WarningCapture(logging.Handler):
    """Minimal log handler that records WARNING-or-above messages emitted during a test."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        self.records.append(record)


# ---------------------------------------------------------------------------
# AC-1: Malformed / unavailable source → fallback {} + WARNING
# ---------------------------------------------------------------------------


class TestMalformedSourceDegradesToFallback(unittest.TestCase):
    """AC-1: A malformed or unavailable mapping source must NOT propagate an
    exception out of _load_migration_map().  The function must return {} and
    emit a WARNING that names the failed source.

    All tests in this class are RED before the fix because SyntaxError and
    RuntimeError are not in the current except clause.
    """

    def setUp(self) -> None:
        # Attach a capturing handler to the module's logger so we can assert
        # that the WARNING is actually emitted (not just swallowed silently).
        self._gen_logger = logging.getLogger(_gen_module.__name__)
        self._capture = _WarningCapture()
        self._gen_logger.addHandler(self._capture)

    def tearDown(self) -> None:
        self._gen_logger.removeHandler(self._capture)

    def test_malformed_components_json_import_still_succeeds(self):
        # covers: TKT-500f-18-i
        """AC-1: SyntaxError from exec_module degrades to {} + WARNING.

        When the sibling migrate_component_vocab.py has a syntax error,
        importlib's exec_module raises SyntaxError.  The current except clause
        only catches (OSError, AttributeError, ImportError) — SyntaxError is
        NOT caught and propagates out of _load_migration_map().

        Must be RED before the fix:
          _load_migration_map() raises SyntaxError instead of returning {}.
          assertEqual(result, {}) is never reached.

        After the fix:
          SyntaxError is caught; {} is returned; a WARNING names the failed
          source (the path to migrate_component_vocab.py).
        """
        mock_spec = MagicMock()
        mock_spec.loader.exec_module.side_effect = SyntaxError(
            "injected: invalid syntax in sibling module"
        )
        mock_mod = MagicMock()

        with patch("importlib.util.spec_from_file_location", return_value=mock_spec):
            with patch("importlib.util.module_from_spec", return_value=mock_mod):
                result = _load_migration_map()

        self.assertEqual(
            result,
            {},
            "Expected _load_migration_map to return {} when exec_module raises "
            f"SyntaxError, but got: {result!r}. "
            "Currently RED: SyntaxError is not in the except clause "
            "(only OSError, AttributeError, ImportError are caught).  The exception "
            "propagates out of _load_migration_map() so this line is never reached.",
        )

        warning_records = [
            r for r in self._capture.records if r.levelno >= logging.WARNING
        ]
        self.assertTrue(
            len(warning_records) > 0,
            "Expected at least one WARNING to be logged when the mapping source "
            f"raises SyntaxError, but no warnings were captured. "
            f"Records: {[r.getMessage() for r in self._capture.records]!r}",
        )
        # The warning message must name the failed source so the operator knows
        # which file caused the degradation.
        warning_text = " ".join(r.getMessage() for r in warning_records)
        self.assertTrue(
            "migrate_component_vocab" in warning_text or "MIGRATION_MAP" in warning_text,
            f"WARNING must name the failed source (e.g. 'migrate_component_vocab' or "
            f"'MIGRATION_MAP'), but warning text was: {warning_text!r}",
        )

    def test_malformed_components_json_runtime_error_also_degrades(self):
        # covers: TKT-500f-18-i
        """AC-1 supplementary: A RuntimeError from exec_module also degrades gracefully.

        The AC says 'a sibling data module raises a SyntaxError or other error when
        loaded'.  RuntimeError represents the 'other error' branch.  It is also NOT in
        the current except clause and therefore propagates — making this test RED.

        After the fix, any exception type that can arise from loading a Python module
        (SyntaxError, RuntimeError, ValueError, …) must be caught; {} must be returned
        with a WARNING naming the source.
        """
        mock_spec = MagicMock()
        mock_spec.loader.exec_module.side_effect = RuntimeError(
            "injected: module-level statement failed"
        )
        mock_mod = MagicMock()

        with patch("importlib.util.spec_from_file_location", return_value=mock_spec):
            with patch("importlib.util.module_from_spec", return_value=mock_mod):
                result = _load_migration_map()

        self.assertEqual(
            result,
            {},
            "Expected _load_migration_map to return {} when exec_module raises "
            f"RuntimeError, but got: {result!r}. "
            "Currently RED: RuntimeError is not in the except clause and propagates.",
        )

        warning_records = [
            r for r in self._capture.records if r.levelno >= logging.WARNING
        ]
        self.assertTrue(
            len(warning_records) > 0,
            "Expected a WARNING to be logged on exec_module RuntimeError, "
            f"but none were captured. Records: {[r.getMessage() for r in self._capture.records]!r}",
        )


# ---------------------------------------------------------------------------
# AC-2: Module remains importable after load failure; generation proceeds
# ---------------------------------------------------------------------------


class TestGenerationProceedsWithFallbackMapping(unittest.TestCase):
    """AC-2: When _load_migration_map() raises, the module-level assignment
    ``_COMPONENT_MIGRATION_MAP = _load_migration_map()`` must NOT propagate the
    exception — the module must remain importable with {} as the fallback.

    Test is RED before the fix: importlib.reload() raises SyntaxError because
    _load_migration_map() does not catch it, causing the module-level
    initialisation to fail.
    """

    def test_generation_proceeds_with_fallback_mapping(self):
        # covers: TKT-500f-18-i
        """AC-2: Module reload succeeds with fallback {} when exec_module raises.

        importlib.reload() re-executes all module-level code, including
        ``_COMPONENT_MIGRATION_MAP = _load_migration_map()``.  When the injected
        SyntaxError propagates out of _load_migration_map(), that assignment fails
        and reload() itself raises — making the generator un-importable under the
        failure condition.

        Must be RED before the fix:
          importlib.reload(_gen_module) raises SyntaxError.  self.fail() is called.

        After the fix:
          _load_migration_map() catches SyntaxError and returns {}.
          ``_COMPONENT_MIGRATION_MAP = {}`` is assigned cleanly.
          importlib.reload() succeeds.  self.fail() is NOT called.
          Generation with the passthrough empty map proceeds without crashing.
        """
        mock_spec = MagicMock()
        mock_spec.loader.exec_module.side_effect = SyntaxError(
            "injected: bad syntax in sibling module"
        )
        mock_mod = MagicMock()

        # Re-import to ensure the module is registered in sys.modules before calling
        # importlib.reload().  If test_tkt_500f_18 ran first, its tearDown pops the
        # module; importlib.reload() raises ModuleNotFoundError when the module is absent.
        # Using a local _m (rather than the module-level _gen_module captured at
        # collection time) makes this test order-independent: whether or not test_18
        # ran first, `import generate_ticket_from_ac as _m` repopulates sys.modules
        # and gives us a valid module object for reload.
        import generate_ticket_from_ac as _m  # noqa: PLC0415

        try:
            with patch("importlib.util.spec_from_file_location", return_value=mock_spec):
                with patch("importlib.util.module_from_spec", return_value=mock_mod):
                    # This reload re-executes: _COMPONENT_MIGRATION_MAP = _load_migration_map()
                    # Currently RED: _load_migration_map() propagates SyntaxError → reload fails.
                    # After fix: _load_migration_map() returns {} → reload succeeds.
                    importlib.reload(_m)
        except SyntaxError as exc:
            self.fail(
                f"importlib.reload raised SyntaxError: {exc}. "
                "After the fix, _load_migration_map must catch SyntaxError so that "
                "the module-level assignment "
                "'_COMPONENT_MIGRATION_MAP = _load_migration_map()' succeeds with {} "
                "rather than propagating the exception and making the module un-importable. "
                "Currently RED: SyntaxError is not in the except clause and propagates "
                "through the module-level initialisation."
            )
        finally:
            # Always restore the module to its real state to avoid polluting later tests.
            importlib.reload(_m)

        # After a successful reload with the fallback, _COMPONENT_MIGRATION_MAP must
        # exist as a dict (possibly empty).  Ticket generation with an unresolvable
        # component value must proceed via dict.get(key, key) passthrough — no crash.
        self.assertIsInstance(
            _m._COMPONENT_MIGRATION_MAP,
            dict,
            "Expected _COMPONENT_MIGRATION_MAP to be a dict (possibly empty {}) "
            "after a successful reload under fallback conditions, but got: "
            f"{type(_gen_module._COMPONENT_MIGRATION_MAP)!r}. "
            "The fallback must assign {} so that _build_components_list's "
            "dict.get(key, key) passthrough works without crashing.",
        )


# ---------------------------------------------------------------------------
# AC-3: Well-formed source loaded normally — no WARNING, non-empty result
# ---------------------------------------------------------------------------


class TestWellFormedSourceLoadedNormally(unittest.TestCase):
    """AC-3: When the mapping source is well-formed, _load_migration_map returns
    a non-empty mapping AND does NOT emit a WARNING.

    This is the no-regression check for TKT-500f-18 — after error-handling is
    added, a valid source must still be loaded and used (fallback not triggered).

    Test is RED before the fix for a different reason: the current implementation
    reads ONLY from the Python sibling module (importlib path).  When we patch the
    sibling to expose an EMPTY MIGRATION_MAP (simulating a sibling with no data),
    the current code returns {}.  The assertion ``result != {}`` fails.

    After TKT-500f-18-i (which depends on TKT-500f-18), _load_migration_map reads
    from docs/components.json as its primary/authoritative source.  The sibling
    patch has no effect on the JSON-reading path, so the result is non-empty and
    no WARNING is emitted.
    """

    def test_wellformed_source_still_loaded_no_fallback(self):
        # covers: TKT-500f-18-i
        """AC-3: Well-formed docs/components.json yields non-empty map, no WARNING.

        Strategy to produce a deterministic RED state:
          - Patch spec_from_file_location to return a mock spec whose exec_module
            assigns an EMPTY MIGRATION_MAP (simulating a sibling with no entries).
          - Current code: reads ONLY the sibling → returns {} → assertEqual fails.
          - Future code:  reads from docs/components.json (which exists and is
            valid in the repo) → returns non-empty → assertion passes.

        The assertNoLogs context verifies the fallback path is NOT triggered:
        a WARNING emitted during this call means the function wrongly degraded
        on a valid source.
        """
        # Mock the sibling module so exec_module assigns an empty MIGRATION_MAP.
        # Future implementation should read from docs/components.json, not this sibling,
        # so patching the sibling with an empty map does not affect the future result.
        mock_mod = MagicMock()
        mock_mod.MIGRATION_MAP = {}

        mock_spec = MagicMock()

        def _exec_with_empty_map(mod: object) -> None:
            # Set MIGRATION_MAP to empty on the mock module — simulates a sibling
            # module that loads successfully but carries no usable entries.
            try:
                mod.MIGRATION_MAP = {}  # type: ignore[attr-defined]
            except AttributeError:
                pass

        mock_spec.loader.exec_module.side_effect = _exec_with_empty_map

        # assertNoLogs (Python 3.10+): verifies no WARNING or above is emitted.
        # The fallback path MUST NOT be triggered for a well-formed source.
        with self.assertNoLogs(logger=_gen_module.__name__, level="WARNING"):
            with patch("importlib.util.spec_from_file_location", return_value=mock_spec):
                with patch("importlib.util.module_from_spec", return_value=mock_mod):
                    result = _load_migration_map()

        self.assertNotEqual(
            result,
            {},
            "Expected _load_migration_map to return a NON-EMPTY mapping from a "
            "well-formed source (docs/components.json), but got {}. "
            "Currently RED: the current implementation reads ONLY from the Python "
            "sibling module (migrate_component_vocab.py).  With the sibling patched "
            "to expose an empty MIGRATION_MAP, the function returns {}, failing this "
            "assertion.  After TKT-500f-18-i (on TKT-500f-18): _load_migration_map "
            "reads from docs/components.json directly.  docs/components.json exists "
            "and is well-formed in the repo → a non-empty mapping is returned and "
            "the fallback path is not triggered.",
        )


if __name__ == "__main__":
    unittest.main()
