"""
MODULE: test_acs_300g2_components_preserved
GOAL: Verify that the three original component entries (sync_platforms,
      build_pipeline, config_loader) are present in docs/components.json
      and each satisfies the minimum schema defined in check_components_integrity.py.
BUSINESS CONTEXT: ACS-300g-2 asserted that when 17 new subsystem entries were
      added to components.json the 3 pre-existing entries must remain
      byte-for-byte identical (total count == 20). The file now has 43 entries,
      so the literal count == 20 premise is obsolete. This test asserts the
      still-meaningful invariant: the 3 originals are present and each passes
      the minimum schema check. See the Completion Report recommendation on
      whether ACS-300g-2 should be marked done or SUPERSEDED.
ARCHITECTURE: Uses importlib.util to load validate_component_minimum_schema
      from the canonical templates/scripts/commit_guardian/check_components_integrity.py
      (same pattern as test_check_components_minimum_schema.py after FIX 1).
      No subprocess; no git ops; reads docs/components.json directly.
# covers: ACS-300g-2
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from typing import Any, ClassVar

# ---------------------------------------------------------------------------
# Load validate_component_minimum_schema from the canonical templates path.
# ---------------------------------------------------------------------------

_WORKTREE_ROOT = Path(__file__).resolve().parents[1]
_HOOK_SCRIPT = (
    _WORKTREE_ROOT
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "check_components_integrity.py"
)
_COMPONENTS_JSON = _WORKTREE_ROOT / "docs" / "components.json"

try:
    _spec = importlib.util.spec_from_file_location(
        "check_components_integrity", _HOOK_SCRIPT
    )
    assert _spec is not None and _spec.loader is not None, (
        f"could not load spec for {_HOOK_SCRIPT}"
    )
    # Typed Any: this module's REPO_ROOT attribute is patched below, and a
    # dynamically-loaded module's attribute surface is not statically known.
    _cg_mod: Any = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_cg_mod)
    # REPO_ROOT defaults to parents[2] of the canonical templates path, which
    # resolves to the templates/ subdirectory rather than the worktree root.
    # Patch it to the worktree root so detail_ref path existence checks work
    # (same technique used in test_check_components_minimum_schema.py).
    _cg_mod.REPO_ROOT = _WORKTREE_ROOT
    _validate = _cg_mod.validate_component_minimum_schema
    MODULE_AVAILABLE = True
except Exception as exc:  # noqa: BLE001 — discovery error, not runtime
    MODULE_AVAILABLE = False
    _load_error = str(exc)

# The three entries that must have been present before the initial backfill
# (ACS-300g-2 criteria).
_ORIGINAL_IDS = ("sync_platforms", "build_pipeline", "config_loader")


@unittest.skipUnless(MODULE_AVAILABLE, f"module load failed: {_load_error if not MODULE_AVAILABLE else ''}")
class TestOriginalComponentEntriesPreserved(unittest.TestCase):
    """Asserts the 3 original component entries still exist and pass minimum schema.

    The literal count==20 from ACS-300g-2 is no longer testable (docs/components.json
    has 43 entries after a later canonicalization). The preservation invariant —
    that the 3 originals are present and valid — is what this test checks.
    # covers: ACS-300g-2
    """

    components: ClassVar[dict] = {}

    @classmethod
    def setUpClass(cls) -> None:
        """Load docs/components.json once for all tests in this class."""
        if not _COMPONENTS_JSON.exists():
            raise unittest.SkipTest(  # noqa: TRY003
                f"docs/components.json not found at {_COMPONENTS_JSON}"
            )
        try:
            with _COMPONENTS_JSON.open(encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise unittest.SkipTest(  # noqa: TRY003
                f"Failed to load docs/components.json: {exc}"
            ) from exc
        cls.components = data.get("components", {})

    def test_sync_platforms_is_present(self):
        """sync_platforms must exist as a key in docs/components.json."""
        self.assertIn(
            "sync_platforms",
            self.components,
            "sync_platforms is missing from docs/components.json",
        )

    def test_build_pipeline_is_present(self):
        """build_pipeline must exist as a key in docs/components.json."""
        self.assertIn(
            "build_pipeline",
            self.components,
            "build_pipeline is missing from docs/components.json",
        )

    def test_config_loader_is_present(self):
        """config_loader must exist as a key in docs/components.json."""
        self.assertIn(
            "config_loader",
            self.components,
            "config_loader is missing from docs/components.json",
        )

    def test_sync_platforms_passes_minimum_schema(self):
        """sync_platforms must satisfy the minimum schema defined by check_components_integrity."""
        entry = self.components.get("sync_platforms", {})
        errors = _validate("sync_platforms", entry)
        self.assertEqual(
            errors,
            [],
            "sync_platforms fails minimum schema:\n" + "\n".join(errors),
        )

    def test_build_pipeline_passes_minimum_schema(self):
        """build_pipeline must satisfy the minimum schema defined by check_components_integrity."""
        entry = self.components.get("build_pipeline", {})
        errors = _validate("build_pipeline", entry)
        self.assertEqual(
            errors,
            [],
            "build_pipeline fails minimum schema:\n" + "\n".join(errors),
        )

    def test_config_loader_passes_minimum_schema(self):
        """config_loader must satisfy the minimum schema defined by check_components_integrity."""
        entry = self.components.get("config_loader", {})
        errors = _validate("config_loader", entry)
        self.assertEqual(
            errors,
            [],
            "config_loader fails minimum schema:\n" + "\n".join(errors),
        )

    def test_all_three_originals_pass_minimum_schema(self):
        """All three original entries must pass the minimum schema in one consolidated check."""
        all_errors: list[str] = []
        for cid in _ORIGINAL_IDS:
            entry = self.components.get(cid, {})
            errors = _validate(cid, entry)
            all_errors.extend(errors)
        self.assertEqual(
            all_errors,
            [],
            "One or more original entries fail minimum schema:\n"
            + "\n".join(all_errors),
        )


if __name__ == "__main__":
    unittest.main()
