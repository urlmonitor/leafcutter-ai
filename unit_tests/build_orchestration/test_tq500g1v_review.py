"""
MODULE: unit_tests/build_orchestration/test_tq500g1v_review.py
GOAL: Regression test for the prefix-extended id bug in ``_wvr_records.load_records`` (TQ-500g-1-v review H-1).
BUSINESS CONTEXT: The one shared AC reader must answer exactly as the old per-id reader
    (``scan_ac_store._load_ac_by_id``) did, whatever the order of the ids and whatever ids
    extend one another (``X-1`` and ``X-1-i``).
ARCHITECTURE: Real YAML files written with yaml.safe_dump under tmp_path; no mocks.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "scripts" / "build_orchestration"))
import _wvr_records as records  # noqa: E402
from _fl_common import _load_ac_by_id  # noqa: E402


def _store(root: Path, ids: list[str]) -> None:
    """Write one AC file per id; the file names sort the longer (child) ids first."""
    for number, ac_id in enumerate(ids):
        (root / f"{number}.yaml").write_text(yaml.safe_dump({"id": ac_id, "test_spec": []}), encoding="utf-8")


def test_prefix_extended_ids_are_found_in_either_order(tmp_path: Path):
    # covers: TQ-500g-1-v
    # angle: boundary
    # must_catch: the reader takes the first alternative of an id alternation instead of every id present in the file
    _store(tmp_path, ["X-1-ii", "X-1-i", "X-1"])
    ids = ["X-1", "X-1-i", "X-1-ii"]
    for ordered in (ids, ids[::-1], [ids[1], ids[0], ids[2]]):
        got = records.load_records(ordered, tmp_path)
        for ac_id in ordered:
            old = _load_ac_by_id(tmp_path, ac_id)
            assert got[ac_id] is not None and got[ac_id]["id"] == ac_id, (ordered, ac_id, got[ac_id])
            assert old is not None and got[ac_id]["id"] == old["id"]
