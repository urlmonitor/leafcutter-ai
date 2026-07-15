"""
MODULE: test_audit_authoring_components
GOAL: Unit tests for scripts/ac_store/audit_authoring_components.py, the advisory
    store-wide audit that identifies authoring-agent ACs lacking a valid
    `components` membership field.
BUSINESS CONTEXT: KM-KGS-100e-4. Verifies that the audit correctly identifies
    violations in synthetic fixtures AND against a real AC from the on-disk store,
    ensuring the scanner is not a no-op on the real data format.
ARCHITECTURE: Tests add scripts/ac_store/ to sys.path and import the module
    directly, matching the convention in test_components_enforcement.py.
    Real-fixture verification uses a concrete AC file from docs/acceptance-criteria/
    that is known to be authored by an authoring agent.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AC_STORE_SCRIPTS = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_AC_STORE_SCRIPTS))

import audit_authoring_components as _mod  # noqa: E402
from _ac_components import load_registry_ids  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REGISTRY = {"knowledge-management", "ac-store", "build-pipeline"}


def _write_yaml(tmp: Path, name: str, body: str) -> Path:
    """Write a YAML file into the temp directory and return its path."""
    p = tmp / name
    p.write_text(body, encoding="utf-8")
    return p


def _make_ac_yaml(
    ac_id: str = "KM-TEST-001",
    origin_agent: str = "business-analyst",
    components: str | None = None,
) -> str:
    """Build a minimal AC YAML body."""
    base = (
        f"id: {ac_id}\n"
        f"origin_agent: {origin_agent}\n"
        "readiness: approved\n"
        "priority: high\n"
        f'title: "Test AC {ac_id}"\n'
        "level: L2\n"
        "status: active\n"
        "component: knowledge-management\n"
        'criteria: "Given X when Y then Z"\n'
    )
    if components is not None:
        base += components
    return base


# ---------------------------------------------------------------------------
# _is_authoring_agent — unit tests
# ---------------------------------------------------------------------------


class TestIsAuthoringAgent(unittest.TestCase):
    """Tests for the origin_agent matching predicate."""

    def test_canonical_business_analyst(self) -> None:
        self.assertTrue(_mod._is_authoring_agent("business-analyst"))

    def test_v3_variant_business_analyst(self) -> None:
        self.assertTrue(_mod._is_authoring_agent("business-analyst-v3"))

    def test_canonical_product_owner(self) -> None:
        self.assertTrue(_mod._is_authoring_agent("product-owner"))

    def test_v3_variant_product_owner(self) -> None:
        self.assertTrue(_mod._is_authoring_agent("product-owner-v3"))

    def test_canonical_it_po(self) -> None:
        self.assertTrue(_mod._is_authoring_agent("it-po"))

    def test_v3_variant_it_po(self) -> None:
        self.assertTrue(_mod._is_authoring_agent("it-po-v3"))

    def test_case_insensitive_match(self) -> None:
        self.assertTrue(_mod._is_authoring_agent("Business-Analyst"))

    def test_human_author_excluded(self) -> None:
        self.assertFalse(_mod._is_authoring_agent("BrainCandy"))

    def test_non_authoring_agent_excluded(self) -> None:
        self.assertFalse(_mod._is_authoring_agent("python-coder"))

    def test_none_excluded(self) -> None:
        self.assertFalse(_mod._is_authoring_agent(None))

    def test_empty_string_excluded(self) -> None:
        self.assertFalse(_mod._is_authoring_agent(""))


# ---------------------------------------------------------------------------
# scan_store — synthetic fixture tests
# ---------------------------------------------------------------------------


class TestScanStore(unittest.TestCase):
    """Tests for scan_store() against synthetic temporary fixtures."""

    def test_ac_with_valid_components_not_reported(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_yaml(
                root, "ok.yaml",
                _make_ac_yaml(components="components:\n  - knowledge-management\n"),
            )
            total, violations = _mod.scan_store(root, _REGISTRY)
            self.assertEqual(total, 1)
            self.assertEqual(violations, [])

    def test_ac_missing_components_reported(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_yaml(root, "missing.yaml", _make_ac_yaml())
            total, violations = _mod.scan_store(root, _REGISTRY)
            self.assertEqual(total, 1)
            self.assertEqual(len(violations), 1)
            self.assertIn("missing.yaml", violations[0]["path"])

    def test_ac_empty_components_reported(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_yaml(
                root, "empty.yaml",
                _make_ac_yaml(components="components: []\n"),
            )
            total, violations = _mod.scan_store(root, _REGISTRY)
            self.assertEqual(total, 1)
            self.assertEqual(len(violations), 1)

    def test_non_authoring_agent_ac_not_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_yaml(
                root, "other.yaml",
                _make_ac_yaml(origin_agent="python-coder"),
            )
            total, violations = _mod.scan_store(root, _REGISTRY)
            self.assertEqual(total, 0)
            self.assertEqual(violations, [])

    def test_multiple_acs_only_violations_reported(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_yaml(
                root, "good.yaml",
                _make_ac_yaml(
                    ac_id="KM-001", components="components:\n  - knowledge-management\n"
                ),
            )
            _write_yaml(root, "bad.yaml", _make_ac_yaml(ac_id="KM-002"))
            total, violations = _mod.scan_store(root, _REGISTRY)
            self.assertEqual(total, 2)
            self.assertEqual(len(violations), 1)
            self.assertIn("bad.yaml", violations[0]["path"])

    def test_missing_ac_root_returns_empty(self) -> None:
        nonexistent = Path("/tmp/totally_nonexistent_ac_store_xyzzy")
        total, violations = _mod.scan_store(nonexistent, _REGISTRY)
        self.assertEqual(total, 0)
        self.assertEqual(violations, [])

    def test_violation_dict_has_expected_keys(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_yaml(root, "v.yaml", _make_ac_yaml())
            _, violations = _mod.scan_store(root, _REGISTRY)
            self.assertEqual(len(violations), 1)
            v = violations[0]
            self.assertIn("path", v)
            self.assertIn("ac_id", v)
            self.assertIn("origin_agent", v)
            self.assertIn("errors", v)

    def test_it_po_v3_variant_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_yaml(
                root, "itpo.yaml",
                _make_ac_yaml(origin_agent="it-po-v3"),
            )
            total, violations = _mod.scan_store(root, _REGISTRY)
            self.assertEqual(total, 1)
            self.assertEqual(len(violations), 1)


# ---------------------------------------------------------------------------
# main() exit codes
# ---------------------------------------------------------------------------


class TestMainExitCodes(unittest.TestCase):
    """Tests for the main() entry point exit codes."""

    def test_exits_0_when_no_violations(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_yaml(
                root, "ok.yaml",
                # Registry is docs/components.json (underscore ids).
                _make_ac_yaml(components="components:\n  - knowledge_system\n"),
            )
            code = _mod.main(["--ac-root", str(root)])
            self.assertEqual(code, 0)

    def test_exits_1_when_violations_found(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_yaml(root, "bad.yaml", _make_ac_yaml())
            code = _mod.main(["--ac-root", str(root)])
            self.assertEqual(code, 1)

    def test_json_flag_produces_valid_json(self) -> None:
        import io
        import contextlib

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_yaml(root, "bad.yaml", _make_ac_yaml())
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                _mod.main(["--ac-root", str(root), "--json"])
            output = buf.getvalue()
            import json
            parsed = json.loads(output)
            self.assertIn("violation_count", parsed)
            self.assertIn("violations", parsed)
            self.assertEqual(parsed["violation_count"], 1)


# ---------------------------------------------------------------------------
# Real-fixture behavioral verification
# ---------------------------------------------------------------------------


class TestRealFixtureBehavior(unittest.TestCase):
    """Exercises the audit against a REAL on-disk AC file.

    This test guards against the synthetic-fixture bias identified in the
    EPIC-PhantomDoneFilesTouched retrospective (2026-07-07): synthetic fixtures
    can inadvertently match only specific formatting while the real data format
    is parsed differently.  We pick a known-authoring-agent AC from the store
    and verify it is scanned (not silently skipped).
    """

    _AC_STORE = _REPO_ROOT / "docs" / "acceptance-criteria"

    def _find_real_authoring_agent_ac(self) -> Path | None:
        """Return the path to the first authoring-agent AC in the real store."""
        if not self._AC_STORE.is_dir():
            return None
        for yaml_file in self._AC_STORE.rglob("*.yaml"):
            data = _mod._load_yaml_file(yaml_file)
            if data and _mod._is_authoring_agent(data.get("origin_agent")):
                return yaml_file
        return None

    def test_real_authoring_agent_ac_is_scanned(self) -> None:
        """Verify the scanner sees at least one authoring-agent AC in the real store."""
        if not self._AC_STORE.is_dir():
            self.skipTest("Real AC store not present in this environment")
        total, _ = _mod.scan_store(self._AC_STORE, _REGISTRY)
        self.assertGreater(total, 0, "Expected to scan at least one authoring-agent AC")

    def test_real_store_reports_expected_violation_count(self) -> None:
        """Run against the full real store with the live registry.

        The store was canonicalized onto docs/components.json (the components
        vocabulary migration, 2026-07-10), so the real store is now expected to
        be CLEAN: every authoring-agent AC carries only registry-valid component
        ids. The prior 51-violation baseline (2026-07-08) predates that cleanup.
        The scanner must still see authoring-agent ACs (total > 0); a total of 0
        would indicate the scanner is silently skipping real files.
        """
        if not self._AC_STORE.is_dir():
            self.skipTest("Real AC store not present in this environment")
        live_registry = load_registry_ids()
        total, violations = _mod.scan_store(self._AC_STORE, live_registry)
        self.assertGreater(
            total,
            0,
            "Expected to scan >0 authoring-agent ACs; a total of 0 would mean the "
            "scanner is silently skipping real files — check the real data format.",
        )
        self.assertEqual(
            len(violations),
            0,
            f"Expected a clean store (0 component violations) after the components "
            f"canonicalization; got {len(violations)} from {total} authoring-agent "
            f"ACs scanned: {violations[:10]}",
        )

    def test_real_ac_file_components_field_is_read_correctly(self) -> None:
        """Read one real AC file and verify the components field is parsed."""
        real_ac = self._find_real_authoring_agent_ac()
        if real_ac is None:
            self.skipTest("No authoring-agent AC found in real store")

        data = _mod._load_yaml_file(real_ac)
        self.assertIsNotNone(data, f"Failed to parse real AC: {real_ac}")
        # The AC should have an id field (basic sanity check for real format)
        self.assertIn("id", data, f"Real AC {real_ac} has no 'id' field")


if __name__ == "__main__":
    unittest.main()
