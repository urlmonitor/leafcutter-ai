"""UXP-511: the generator rebuilds the derived index lookups from the sources.

Every test copies the REAL product-truth store (flows, mock data, index.json and
the real generator scripts) into a temp dir, mutates one source file with the
store's own serializer format (json.dumps indent=2 / yaml.safe_dump), runs the
REAL generator as a subprocess, and reads index.json back. No hand-typed index.
"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_PT_STORE = _REPO_ROOT / "docs" / "product-truth"
_NOW = "2026-01-01"
_NEW_COMPONENT = "zz-new-component"
_NEW_ENTITY = "ZzNewEntity"
_NEW_FLOW_ID = "zz-new-component/zz-new-flow"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _copy_store(root: Path) -> Path:
    docs = root / "docs"
    docs.mkdir(parents=True)
    pt = docs / "product-truth"
    shutil.copytree(_REAL_PT_STORE, pt)
    (docs / "acceptance-criteria").mkdir()
    return pt


def _generate(pt: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(pt / "scripts" / "generate_product_truth.py"), "--now", _NOW],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr


def _first_flow_path(pt: Path) -> Path:
    return sorted((pt / "flows").rglob("*.flow.json"))[0]


def _add_new_flow(pt: Path, entity: str | None = None) -> Path:
    """Add a flow (derived from a real one) in a brand-new component, plus its index artifact."""
    flow = copy.deepcopy(_read(_first_flow_path(pt)))
    flow["id"] = _NEW_FLOW_ID
    flow["component"] = _NEW_COMPONENT
    flow["entities"] = [entity] if entity else []
    flow.pop("mock_data_ref", None)
    dest_dir = pt / "flows" / _NEW_COMPONENT
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "zz-new-flow.flow.json"
    _write(dest, flow)
    index = _read(pt / "index.json")
    index["artifacts"].append({
        "id": _NEW_FLOW_ID, "type": "flow", "component": _NEW_COMPONENT,
        "path": dest.relative_to(pt).as_posix(), "summary": "x",
    })
    _write(pt / "index.json", index)
    return dest


class TestUxp511IndexRebuild(unittest.TestCase):
    def test_by_component_is_rebuilt_from_artifacts_on_disk(self) -> None:
        # covers: UXP-511
        # angle: criterion
        with TemporaryDirectory() as tmp:
            pt = _copy_store(Path(tmp))
            _generate(pt)
            self.assertNotIn(_NEW_COMPONENT, _read(pt / "index.json")["by_component"])
            _add_new_flow(pt)
            _generate(pt)
            by_component = _read(pt / "index.json")["by_component"]
            self.assertEqual(by_component[_NEW_COMPONENT]["flows"], [_NEW_FLOW_ID])
            # control: pre-existing components untouched
            self.assertGreaterEqual(len(by_component), 2)

    def test_by_entity_is_rebuilt_from_artifacts_on_disk(self) -> None:
        # covers: UXP-511
        # angle: criterion
        with TemporaryDirectory() as tmp:
            pt = _copy_store(Path(tmp))
            _generate(pt)
            self.assertNotIn(_NEW_ENTITY, _read(pt / "index.json")["by_entity"])
            _add_new_flow(pt, entity=_NEW_ENTITY)
            _generate(pt)
            by_entity = _read(pt / "index.json")["by_entity"]
            self.assertEqual(by_entity[_NEW_ENTITY]["flows"], {_NEW_COMPONENT: [_NEW_FLOW_ID]})

    def test_by_flow_is_rebuilt_from_the_flows_and_mocks_on_disk(self) -> None:
        # covers: UXP-511
        # angle: criterion
        with TemporaryDirectory() as tmp:
            pt = _copy_store(Path(tmp))
            _generate(pt)
            before = set(_read(pt / "index.json")["by_flow"])
            self.assertNotIn(_NEW_FLOW_ID, before)
            flow_file = _add_new_flow(pt)
            _generate(pt)
            after_add = _read(pt / "index.json")["by_flow"]
            self.assertIn(_NEW_FLOW_ID, after_add)
            self.assertEqual(set(after_add), before | {_NEW_FLOW_ID})
            flow_file.unlink()
            _generate(pt)
            self.assertEqual(set(_read(pt / "index.json")["by_flow"]), before)

    def test_derived_lookups_are_deterministically_ordered(self) -> None:
        # covers: UXP-511
        # angle: seam
        with TemporaryDirectory() as tmp:
            pt = _copy_store(Path(tmp))
            _generate(pt)
            first = (pt / "index.json").read_text(encoding="utf-8")
            # Producer output (artifacts[] in reversed order) piped into the generator.
            index = _read(pt / "index.json")
            index["artifacts"].reverse()
            _write(pt / "index.json", index)
            _generate(pt)
            second = _read(pt / "index.json")
            for key in ("by_component", "by_entity", "by_flow", "by_ac"):
                self.assertTrue(second[key], key)
                self.assertEqual(list(second[key]), sorted(second[key]), key)
            for comp in second["by_component"].values():
                for ids in comp.values():
                    self.assertEqual(ids, sorted(ids))
            for key in ("by_component", "by_entity", "by_flow", "by_ac"):
                self.assertEqual(second[key], json.loads(first)[key], key)

    def test_flow_artifact_rollup_in_the_index_matches_the_recomputed_rollup(self) -> None:
        # covers: UXP-511
        # angle: seam
        with TemporaryDirectory() as tmp:
            pt = _copy_store(Path(tmp))
            index = _read(pt / "index.json")
            flow_ids = {a["id"] for a in index["artifacts"] if a.get("type") == "flow"}
            target = None
            for path in sorted((pt / "flows").rglob("*.flow.json")):
                flow = _read(path)
                if flow["id"] not in flow_ids:
                    continue
                for step in flow.get("steps", []):
                    if step.get("implements") and not step.get("expands_to"):
                        target = (flow["id"], step["id"], step["implements"][0])
                        break
                if target:
                    break
            self.assertIsNotNone(target)
            flow_id, _step, ac_id = target
            ac_path = pt.parent / "acceptance-criteria" / "zz.yaml"

            def summary_for(status: str) -> tuple[dict, dict]:
                ac_path.write_text(yaml.safe_dump({"id": ac_id, "work_status": status}), encoding="utf-8")
                _generate(pt)
                idx = _read(pt / "index.json")
                art = next(a for a in idx["artifacts"] if a["id"] == flow_id)
                self.assertEqual(art["impl_summary"], idx["by_flow"][flow_id]["impl_summary"])
                return art["impl_summary"], idx["by_flow"][flow_id]

            todo, _ = summary_for("todo")
            done, by_flow_entry = summary_for("done")
            self.assertEqual(done["done"], todo["done"] + 1)
            self.assertEqual(done["not_started"], todo["not_started"] - 1)
            self.assertEqual(done["total"], todo["total"])
            self.assertEqual(by_flow_entry["impl_summary"], done)

    def test_by_ac_inverts_step_implements_into_sorted_full_back_references(self) -> None:
        # covers: UXP-511
        # angle: criterion
        with TemporaryDirectory() as tmp:
            pt = _copy_store(Path(tmp))
            ac_id = "ZZ-INVERT-1"
            new_path = _add_new_flow(pt)  # copied from the first flow, so add it before editing that one
            base_path = _first_flow_path(pt)
            base = _read(base_path)
            linked = [s for s in base["steps"] if not s.get("expands_to")][:2]
            self.assertEqual(len(linked), 2)
            for step in linked:
                step["implements"] = list(step.get("implements", [])) + [ac_id]
            _write(base_path, base)
            new_flow = _read(new_path)
            new_flow["steps"][0]["implements"] = [ac_id]
            _write(new_path, new_flow)
            _generate(pt)
            entries = _read(pt / "index.json")["by_ac"][ac_id]
            expected = sorted(
                [(base["id"], s["id"]) for s in linked] + [(_NEW_FLOW_ID, new_flow["steps"][0]["id"])]
            )
            self.assertEqual([(e["flow"], e["node"]) for e in entries], expected)
            fields = {"flow", "node", "node_kind", "flow_kind", "screen", "mock_data", "entities", "source", "asof"}
            by_flow = {base["id"]: base, _NEW_FLOW_ID: new_flow}
            for entry in entries:
                self.assertEqual(set(entry), fields)
                flow = by_flow[entry["flow"]]
                self.assertEqual(entry["node_kind"], "step")
                self.assertEqual(entry["flow_kind"], flow["kind"])
                self.assertEqual(entry["source"], flow["source"])
                self.assertEqual(entry["asof"], _NOW)
