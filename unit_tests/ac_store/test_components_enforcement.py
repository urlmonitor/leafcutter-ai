"""
MODULE: test_components_enforcement
GOAL: Unit tests for the `components` membership enforcement + backfill that make
      the knowledge graph's component view actually populated.
COVERS: KM-KGS-100e-1, KM-KGS-100e-1-i, KM-KGS-100e-1-ii (enforcement),
        KM-KGS-100e-5, KM-KGS-100e-5-i (backfill).

Enforcement is exercised through the agent-side validator
(scripts/ac_store/validate_ac_schema.py) and the shared predicate
(scripts/ac_store/_ac_components.py). Backfill is exercised through
scripts/ac_store/backfill_components.py against a temp store.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AC_STORE_SCRIPTS = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_AC_STORE_SCRIPTS))

from _ac_components import components_field_errors, load_registry_ids  # noqa: E402
import backfill_components  # noqa: E402
import validate_ac_schema  # noqa: E402

_REGISTRY = {"knowledge-management", "ac-store", "build-pipeline"}

_COMMON = (
    'id: "XX-001"\n'
    "readiness: draft\n"
    "priority: high\n"
    'title: "t"\n'
    "component: knowledge-management\n"
    "level: L2\n"
    "status: active\n"
    'created_by: "x"\n'
    'criteria: "c"\n'
)


def _write(tmp: Path, name: str, body: str) -> Path:
    p = tmp / name
    p.write_text(body, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# KM-KGS-100e-1 / -1-i / -1-ii — the shared predicate
# ---------------------------------------------------------------------------


class TestComponentsFieldErrors(unittest.TestCase):
    def test_valid_registry_value_passes(self):
        errs = components_field_errors(
            {"components": ["knowledge-management"]}, _REGISTRY
        )
        self.assertEqual(errs, [])

    def test_missing_key_fails(self):  # KM-KGS-100e-1
        errs = components_field_errors({}, _REGISTRY)
        self.assertTrue(any("Missing required field 'components'" in e for e in errs))

    def test_empty_list_fails(self):  # KM-KGS-100e-1-i
        errs = components_field_errors({"components": []}, _REGISTRY)
        self.assertTrue(any("non-empty list" in e for e in errs))

    def test_blank_only_list_fails(self):  # KM-KGS-100e-1-i
        errs = components_field_errors({"components": ["", "  "]}, _REGISTRY)
        self.assertTrue(any("non-empty list" in e for e in errs))

    def test_non_list_fails(self):  # KM-KGS-100e-1-i (scalar instead of list)
        errs = components_field_errors({"components": "knowledge-management"}, _REGISTRY)
        self.assertTrue(any("Missing required field 'components'" in e for e in errs))

    def test_unknown_component_fails(self):  # KM-KGS-100e-1-ii
        errs = components_field_errors({"components": ["not-real"]}, _REGISTRY)
        self.assertTrue(any("unknown component" in e for e in errs))

    def test_empty_registry_skips_membership_check(self):
        # A broken/unreadable registry must not block everything: presence is
        # still enforced, but membership is skipped when the registry is empty.
        errs = components_field_errors({"components": ["anything"]}, set())
        self.assertEqual(errs, [])

    def test_real_registry_contains_knowledge_management(self):
        ids = load_registry_ids()
        self.assertIn("knowledge-management", ids)
        self.assertIn("ac-driven-dev", ids)  # added to the registry


# ---------------------------------------------------------------------------
# KM-KGS-100e-1 — end-to-end through the validator entry point
# ---------------------------------------------------------------------------


class TestValidatorEnforcesComponents(unittest.TestCase):
    def test_valid_file_passes(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write(Path(d), "v.yaml", _COMMON + "components:\n  - knowledge-management\n")
            self.assertEqual(validate_ac_schema._validate_file(p, _REGISTRY), [])

    def test_missing_components_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write(Path(d), "m.yaml", _COMMON)
            errs = validate_ac_schema._validate_file(p, _REGISTRY)
            self.assertTrue(any("components" in e for e in errs))

    def test_unknown_components_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write(Path(d), "u.yaml", _COMMON + "components:\n  - bogus\n")
            errs = validate_ac_schema._validate_file(p, _REGISTRY)
            self.assertTrue(any("unknown component" in e for e in errs))


# ---------------------------------------------------------------------------
# KM-KGS-100e-5 / -5-i — backfill
# ---------------------------------------------------------------------------


class TestBackfill(unittest.TestCase):
    def _make_store(self, tmp: Path) -> Path:
        store = tmp / "acceptance-criteria"
        (store / "knowledge-management").mkdir(parents=True)
        return store

    def test_scalar_copied_to_list(self):  # KM-KGS-100e-5
        with tempfile.TemporaryDirectory() as d:
            store = self._make_store(Path(d))
            p = _write(store / "knowledge-management", "a.yaml", _COMMON)
            res = backfill_components._backfill_file(p, _REGISTRY, dry_run=False)
            self.assertEqual(res, "backfilled")
            self.assertIn("components:\n  - knowledge-management", p.read_text())

    def test_idempotent_skip(self):  # KM-KGS-100e-5
        with tempfile.TemporaryDirectory() as d:
            store = self._make_store(Path(d))
            body = _COMMON + "components:\n  - knowledge-management\n"
            p = _write(store / "knowledge-management", "b.yaml", body)
            before = p.read_text()
            res = backfill_components._backfill_file(p, _REGISTRY, dry_run=False)
            self.assertEqual(res, "skipped")
            self.assertEqual(p.read_text(), before)

    def test_uninferable_reported_not_guessed(self):  # KM-KGS-100e-5-i
        with tempfile.TemporaryDirectory() as d:
            store = self._make_store(Path(d))
            # scalar component is a non-registry value -> must not be guessed
            body = _COMMON.replace(
                "component: knowledge-management", "component: build_pipeline"
            )
            p = _write(store / "knowledge-management", "c.yaml", body)
            before = p.read_text()
            res = backfill_components._backfill_file(p, _REGISTRY, dry_run=False)
            self.assertEqual(res, "review")
            self.assertEqual(p.read_text(), before)  # left unchanged

    def test_missing_scalar_reported(self):  # KM-KGS-100e-5-i
        with tempfile.TemporaryDirectory() as d:
            store = self._make_store(Path(d))
            body = _COMMON.replace("component: knowledge-management\n", "")
            p = _write(store / "knowledge-management", "e.yaml", body)
            res = backfill_components._backfill_file(p, _REGISTRY, dry_run=False)
            self.assertEqual(res, "review")


if __name__ == "__main__":
    unittest.main()
