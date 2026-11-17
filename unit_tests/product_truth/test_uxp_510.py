"""
MODULE: test_uxp_510
GOAL: Pin UXP-510 -- generate_product_truth recomputes each flow step's
    impl_status from the work_status of the ACs in its implements list, and
    rolls the statuses up into the flow's impl_summary.
ARCHITECTURE: Drives the REAL generator generate() against a tempdir store whose
    AC YAMLs are written with yaml.safe_dump and whose flow is written with
    json.dump, then reads back what the generator actually wrote.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "docs" / "product-truth" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_product_truth as gpt  # noqa: E402


def _build_store(root: Path, ac_statuses: dict[str, str], steps: dict[str, list[str]]) -> tuple[Path, Path, Path]:
    store = root / "docs" / "product-truth"
    ac_root = root / "docs" / "acceptance-criteria"
    for place in ("flows/t", "mock-data", "mockups"):
        (store / place).mkdir(parents=True)
    ac_root.mkdir(parents=True)
    for ac_id, status in ac_statuses.items():
        (ac_root / f"{ac_id}.yaml").write_text(
            yaml.safe_dump({"id": ac_id, "work_status": status}), encoding="utf-8")
    flow = {
        "id": "t/demo", "kind": "data", "source": "real", "component": "c", "title": "Demo", "product": "t",
        "steps": [{"id": sid, "title": sid, "implements": acs, "impl_status": "done"} for sid, acs in steps.items()],
        "branches": [],
    }
    flow_path = store / "flows" / "t" / "demo.flow.json"
    flow_path.write_text(json.dumps(flow, indent=2), encoding="utf-8")
    (store / "index.json").write_text(json.dumps({"artifacts": []}), encoding="utf-8")
    return store, ac_root, flow_path


def _generate_and_read(root: Path, statuses: dict[str, str], steps: dict[str, list[str]]) -> dict:
    store, ac_root, flow_path = _build_store(root, statuses, steps)
    saved = gpt.STORE, gpt.AC_STORE
    gpt.STORE, gpt.AC_STORE = store, ac_root
    try:
        gpt.generate(check=False, run_date="2026-01-01")
    finally:
        gpt.STORE, gpt.AC_STORE = saved
    return json.loads(flow_path.read_text(encoding="utf-8"))


def _step_status(flow: dict) -> dict:
    return {s["id"]: s.get("impl_status") for s in flow["steps"]}


class TestUxp510(unittest.TestCase):
    def test_all_criteria_done_maps_the_step_to_done(self) -> None:
        # covers: UXP-510
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmp:
            flow = _generate_and_read(
                Path(tmp), {"X-1": "done", "X-2": "done"}, {"a": ["X-1", "X-2"]})
        self.assertEqual(_step_status(flow), {"a": "done"})

    def test_no_criteria_started_maps_the_step_to_not_started(self) -> None:
        # covers: UXP-510
        # angle: boundary
        with tempfile.TemporaryDirectory() as tmp:
            flow = _generate_and_read(
                Path(tmp), {"X-1": "todo", "X-2": "not_started", "X-3": "done"},
                {"a": ["X-1", "X-2"], "ctl": ["X-3"]})
        # the stale stored value was "done"; control step stays done, the other must flip.
        self.assertEqual(_step_status(flow), {"a": "not_started", "ctl": "done"})

    def test_mixed_criteria_map_the_step_to_in_progress(self) -> None:
        # covers: UXP-510
        # angle: boundary
        with tempfile.TemporaryDirectory() as tmp:
            flow = _generate_and_read(
                Path(tmp), {"X-1": "done", "X-2": "todo"}, {"a": ["X-1", "X-2"]})
        self.assertEqual(_step_status(flow), {"a": "in_progress"})

    def test_flow_rollup_counts_match_the_recomputed_step_statuses(self) -> None:
        # covers: UXP-510
        # angle: seam
        statuses = {"X-1": "done", "X-2": "todo", "X-3": "done", "X-4": "in_progress"}
        steps = {"s1": ["X-1"], "s2": ["X-2"], "s3": ["X-3", "X-4"], "s4": ["X-3"]}
        with tempfile.TemporaryDirectory() as tmp:
            flow = _generate_and_read(Path(tmp), statuses, steps)
            first = {k: flow["impl_summary"][k] for k in ("done", "in_progress", "not_started", "total")}
            tally = {"done": 0, "in_progress": 0, "not_started": 0}
            for s in flow["steps"]:
                tally[s["impl_status"]] += 1
            statuses2 = dict(statuses, **{"X-2": "done"})
            flow2 = _generate_and_read(Path(tmp) / "second", statuses2, steps)
            second = {k: flow2["impl_summary"][k] for k in ("done", "in_progress", "not_started", "total")}
        self.assertEqual(first, {"done": 2, "in_progress": 1, "not_started": 1, "total": 4})
        self.assertEqual({k: first[k] for k in tally}, tally)
        self.assertEqual(second, {"done": 3, "in_progress": 1, "not_started": 0, "total": 4})


if __name__ == "__main__":
    unittest.main()
