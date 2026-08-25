"""
MODULE: unit_tests/ac_store/test_bo_2400c_6_tree_walk_seam.py
GOAL: RED test stubs for the traverse_ac_tree() seam that BO-2400c-6 and
      BO-2400c-6-ii both depend on: an optional, keyword-only ``id_index``
      parameter that the walk consumes instead of re-reading the store, and
      whose absence leaves the walk's existing self-building path untouched.
COVERS: BO-2400c-6, BO-2400c-6-ii

=== What must be true after python-coder's change ===

traverse_ac_tree(root_id, ac_store_root, *, id_index=None, exclude_done=True,
exclude_superseded=True) — when ``id_index`` is supplied, the walk uses it
directly and performs NO further rglob / YAML parse. When it is omitted
(``None``, the default), the walk builds its own index exactly as it does
today (BO-2400c-6-ii's "never an obligation" half).

=== Red baseline (verified live, 2026-08-25) ===

Today's signature is ``traverse_ac_tree(root_id, ac_store_root, *,
exclude_done=True, exclude_superseded=True)`` — no ``id_index`` parameter
exists yet. Calling it with ``id_index=...`` raises:

    TypeError: traverse_ac_tree() got an unexpected keyword argument 'id_index'

verified by direct execution against the live (pre-fix) module before this
file was written. That TypeError is the intended red state for both tests
below — it is a real signal that the seam does not exist yet, not an import
or fixture-collection failure.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AC_STORE_DIR = _REPO_ROOT / "scripts" / "ac_store"
if str(_AC_STORE_DIR) not in sys.path:
    sys.path.insert(0, str(_AC_STORE_DIR))

import scan_ac_store  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_ac(
    ac_root: Path,
    ac_id: str,
    *,
    level: str,
    work_status: str,
    readiness: str = "approved",
    depends_on: list | None = None,
    covered_by: list | None = None,
) -> Path:
    """Write a minimal AC YAML file using yaml.safe_dump (fixture-authenticity mandate)."""
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic test AC {ac_id}",
        "component": "build-orchestration",
        "level": level,
        "status": "active",
        "work_status": work_status,
        "readiness": readiness,
        "priority": "medium",
        "estimated_complexity": "S",
        "depends_on": depends_on if depends_on is not None else [],
        "covered_by": covered_by if covered_by is not None else [],
        "amended_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    path = subdir / f"{ac_id}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _build_id_index_from_disk(ac_root: Path) -> dict:
    """Build the same id-to-record mapping resolve_connected_build_set would build.

    Mirrors scan_ac_store._build_id_index(all loaded records) — a real,
    on-disk-derived index, never a hand-typed literal (fixture-authenticity,
    2h.2).
    """
    records = []
    for yaml_path in scan_ac_store._walk_ac_yamls(ac_root):
        record = scan_ac_store._load_ac(yaml_path)
        if record is not None:
            records.append(record)
    return scan_ac_store._build_id_index(records)


class TestTreeWalkUsesSuppliedIndexInsteadOfRereading(unittest.TestCase):
    """BO-2400c-6: given a prebuilt id_index, the walk must not re-read the store."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)
        _write_ac(self.ac_root, "BO-TST-SEAM-X01", level="L2", work_status="todo")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_tree_walk_uses_the_supplied_index_instead_of_rereading(self) -> None:
        # covers: BO-2400c-6
        """When the tree walk is given a prebuilt record index, no additional
        read of the store directory occurs during the walk — proving the
        argument is consumed rather than accepted and ignored.

        RED today: traverse_ac_tree() does not yet accept an ``id_index``
        keyword argument at all, so this call raises TypeError (verified
        live). Once implemented, no _load_ac call should occur because the
        supplied index already has everything the walk needs.
        """
        prebuilt_index = _build_id_index_from_disk(self.ac_root)

        real_load_ac = scan_ac_store._load_ac
        calls: list[Path] = []

        def counting_load_ac(path: Path):
            calls.append(path)
            return real_load_ac(path)

        with mock.patch.object(scan_ac_store, "_load_ac", side_effect=counting_load_ac):
            result = scan_ac_store.traverse_ac_tree(
                "BO-TST-SEAM-X01",
                self.ac_root,
                id_index=prebuilt_index,
            )

        self.assertEqual(
            calls,
            [],
            "traverse_ac_tree must not read/parse the store directory when given a "
            f"prebuilt id_index (BO-2400c-6) — the argument must be consumed, not "
            f"merely accepted. Got {len(calls)} unexpected parse(s): {calls!r}",
        )
        self.assertEqual(
            result,
            ["BO-TST-SEAM-X01"],
            f"traverse_ac_tree must still return the correct leaf set when given a "
            f"prebuilt id_index. Got: {result!r}",
        )


class TestTreeWalkWithoutSuppliedIndexReturnsSameAnswer(unittest.TestCase):
    """BO-2400c-6-ii: the no-index (self-building) path must remain available
    and must agree with the indexed path.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)
        _write_ac(
            self.ac_root,
            "BO-TST-SEAM-Y00",
            level="L0",
            work_status="todo",
            covered_by=["BO-TST-SEAM-Y01"],
        )
        _write_ac(self.ac_root, "BO-TST-SEAM-Y01", level="L2", work_status="todo")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_tree_walk_without_supplied_index_returns_the_same_answer(self) -> None:
        # covers: BO-2400c-6-ii
        """Called with no record index against a temporary on-disk store, the
        tree walk builds its own index and returns the identical answer to
        the same walk given a prebuilt index.

        The no-index call (``id_index`` omitted) already works today — this
        is the existing, unchanged self-building path (BO-2400c-6-ii: "never
        an obligation placed on callers that do not [hold a record set]").
        RED today only because the SECOND call (with ``id_index=`` explicitly
        supplied) raises TypeError — the seam this comparison depends on does
        not exist yet (verified live).
        """
        no_index_result = scan_ac_store.traverse_ac_tree("BO-TST-SEAM-Y00", self.ac_root)

        prebuilt_index = _build_id_index_from_disk(self.ac_root)
        with_index_result = scan_ac_store.traverse_ac_tree(
            "BO-TST-SEAM-Y00",
            self.ac_root,
            id_index=prebuilt_index,
        )

        self.assertEqual(
            no_index_result,
            with_index_result,
            "traverse_ac_tree must return the identical answer whether the caller "
            "supplies a prebuilt id_index or omits it entirely (BO-2400c-6-ii). "
            f"no_index={no_index_result!r} with_index={with_index_result!r}",
        )
        self.assertEqual(
            no_index_result,
            ["BO-TST-SEAM-Y01"],
            f"Sanity check on the no-index (self-building) path. Got: {no_index_result!r}",
        )


if __name__ == "__main__":
    unittest.main()
