"""
Regression test for UXP-553 Bug 2: loader caches must be keyed by repoRoot() so
toggling mock mode in the same process serves fresh data from each root, not stale
data from a previous root's cache.

These tests verify the DATA INVARIANT that makes cache-by-root correct and necessary:
  - The fixture root (leafcutter-web/fixtures/) contains a DIFFERENT (smaller) set
    of data than the real repo root.
  - A single-value cache would serve stale data after a toggle: if mock was served
    first, a subsequent real request would return the fixture data.
  - With per-root keying, each root is cached independently.

The tests below are fast, server-free, and assert the invariant by reading the
fixture and real file trees directly. They do NOT import the TypeScript loaders —
that behavioral proof is in the drift-guard API route (leafcutter-web/app/api/drift-guard/).

Covers: UXP-553 (runtime override), UXP-550 (seam correctness).
"""
import json
import unittest
from pathlib import Path

# The fixture root (populated by UXP-551).
FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "leafcutter-web" / "fixtures"
# The real repo root (the worktree this test runs from).
REAL_ROOT = Path(__file__).resolve().parent.parent


class TestCacheByRootInvariant(unittest.TestCase):
    """
    Verify that the fixture root and the real repo root produce DIFFERENT data,
    so per-root cache keying is meaningful and necessary.

    If these data sets were identical, a stale-cache bug would be undetectable
    from the outputs. These tests assert the precondition for the fix to matter.
    """

    def test_fixture_has_fewer_flows_than_real(self):
        """
        Per-root cache invariant: mock root must have different (fewer) flows than
        the real repo root.

        If getFlows() is called with mock active, it reads from FIXTURE_ROOT.
        If then called with mock inactive (same process), it must read from REAL_ROOT
        and return a different result — not the cached fixture result.
        This test proves the two roots genuinely differ, so the bug (stale same-root
        result) would be observable if the fix were absent.
        """
        fixture_flows = list(
            (FIXTURE_ROOT / "docs" / "product-truth" / "flows").rglob("*.flow.json")
        )
        real_flows = list(
            (REAL_ROOT / "docs" / "product-truth" / "flows").rglob("*.flow.json")
        )
        self.assertGreater(
            len(real_flows),
            len(fixture_flows),
            (
                "Real repo must have more flows than the fixture tree — "
                "this is the invariant that makes per-root cache keying detectable. "
                f"Fixture has {len(fixture_flows)}, real has {len(real_flows)}."
            ),
        )

    def test_fixture_flow_ids_are_distinct_subset(self):
        """
        The fixture flow ids must not include all real flow ids (fixture is a small
        curated snapshot, not a copy). A full copy would hide the per-root cache bug.
        """
        fixture_ids = {
            json.loads(f.read_text(encoding="utf-8")).get("id")
            for f in (FIXTURE_ROOT / "docs" / "product-truth" / "flows").rglob("*.flow.json")
            if f.is_file()
        }
        real_ids = {
            json.loads(f.read_text(encoding="utf-8")).get("id")
            for f in (REAL_ROOT / "docs" / "product-truth" / "flows").rglob("*.flow.json")
            if f.is_file()
        }
        # All fixture ids must be valid flow ids (safety check)
        self.assertTrue(fixture_ids, "Fixture must contain at least one flow")
        # Real must have at least one id not in the fixture
        real_only = real_ids - fixture_ids
        self.assertGreater(
            len(real_only),
            0,
            (
                "Real repo must have flows not present in the fixture tree — "
                "if they were identical, toggling mock mode would be undetectable. "
                f"Fixture ids: {sorted(fixture_ids)}. Real-only ids (sample): "
                f"{sorted(real_only)[:5]}."
            ),
        )
        # Fixture must have at least one id not in the real store
        # (some fixture flows are mock-only, e.g. mock-mode-toggle)
        fixture_only = fixture_ids - real_ids
        self.assertGreater(
            len(fixture_only),
            0,
            (
                "Fixture must have at least one flow id not in the real store — "
                "this ensures a cache returning fixture data is distinguishable from real. "
                f"fixture_only: {sorted(fixture_only)}."
            ),
        )

    def test_fixture_has_fewer_acs_than_real(self):
        """
        The fixture AC store must have fewer ACs than the real store.
        loadAcs() is the most-used loader — stale mock ACs would corrupt every view.
        """
        fixture_acs = list(
            (FIXTURE_ROOT / "docs" / "acceptance-criteria").rglob("*.yaml")
        )
        fixture_acs = [f for f in fixture_acs if f.name != "index.yaml"]
        real_acs = list(
            (REAL_ROOT / "docs" / "acceptance-criteria").rglob("*.yaml")
        )
        real_acs = [f for f in real_acs if f.name != "index.yaml"]
        self.assertGreater(
            len(real_acs),
            len(fixture_acs),
            (
                "Real repo must have more ACs than the fixture tree. "
                f"Fixture has {len(fixture_acs)}, real has {len(real_acs)}."
            ),
        )

    def test_fixture_has_fewer_tickets_than_real(self):
        """
        The fixture ticket tree must have fewer tickets than the real store.
        loadTickets() drives the /now and /atlas views.
        """
        fixture_tickets = list((FIXTURE_ROOT / "tickets").rglob("*.md"))
        real_tickets = list((REAL_ROOT / "tickets").rglob("*.md"))
        fixture_tickets = [t for t in fixture_tickets if t.name.upper() != "README.MD"]
        real_tickets = [t for t in real_tickets if t.name.upper() != "README.MD"]
        self.assertGreater(
            len(real_tickets),
            len(fixture_tickets),
            (
                "Real repo must have more tickets than the fixture tree. "
                f"Fixture has {len(fixture_tickets)}, real has {len(real_tickets)}."
            ),
        )

    def test_reporoot_mock_and_real_are_different_paths(self):
        """
        FIXTURE_ROOT and REAL_ROOT must resolve to different absolute paths.
        This is the fundamental requirement for Map-keying by repoRoot() to work:
        if both paths were the same, all cached lookups would hit the same key
        regardless of mock mode.
        """
        self.assertNotEqual(
            FIXTURE_ROOT.resolve(),
            REAL_ROOT.resolve(),
            "FIXTURE_ROOT and REAL_ROOT must be different directories — "
            "per-root cache keying is only effective when the paths differ.",
        )


if __name__ == "__main__":
    unittest.main()
