"""Behavioral tests for docs/product-truth/scripts/apply_flow_backlinks.py.

Track 1.3 reconciliation script: writes a business-analyst's reported
``flow_backlinks`` map (step id -> [AC ids]) into a flow's ``step.implements[]``,
then re-runs ``generate_product_truth.py`` so all derived data is reconciled.

REAL-ARTIFACT SPOT-CHECK (repo policy): these tests copy the REAL on-disk
product-truth store into a temp dir and run the REAL flow fixture through the
script as a subprocess — no hand-typed flow literal — so the parser/serializer is
exercised against the exact format the store writes (``json.dumps(indent=2)``).

Cases:
  * writes step.implements (union, order-preserving) into a real flow;
  * re-runs the generator (derived data regenerated: flow impl_summary + index);
  * idempotent — a second identical run leaves every file byte-for-byte unchanged;
  * regenerates BOTH meta-flows' impl_status/impl_summary;
  * unknown step id is a non-fatal warning (skipped), not a crash;
  * --skip-generate writes back-links only without invoking the generator.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

# The REAL store this repo ships — the source of the temp copy each test drives.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_REAL_PT_STORE = _REPO_ROOT / "docs" / "product-truth"

# A real journey flow with steps that already carry implements[] edges.
_FIXTURE_FLOW_ID = "fern-and-fig/checkout-and-pay"
_FIXTURE_FLOW_REL = "flows/fern-and-fig/checkout-and-pay.flow.json"

# The two meta-flows the plan calls out explicitly.
_META_FLOWS = (
    "flows/leafcutter/author-product-truth.flow.json",
    "flows/leafcutter/define-a-feature.flow.json",
)


def _copy_store(dest_root: Path) -> Path:
    """Copy the real product-truth store into dest_root/docs/product-truth.

    Also creates an empty docs/acceptance-criteria sibling so the generator's
    AC_STORE (STORE.parent / 'acceptance-criteria') resolves to a real dir.
    """
    docs = dest_root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    pt_dest = docs / "product-truth"
    shutil.copytree(_REAL_PT_STORE, pt_dest)
    (docs / "acceptance-criteria").mkdir(exist_ok=True)
    return pt_dest


def _run_script(pt_store: Path, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    """Run the COPIED apply_flow_backlinks.py so STORE resolves to the temp store."""
    script = pt_store / "scripts" / "apply_flow_backlinks.py"
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestApplyFlowBacklinks(unittest.TestCase):
    """Reconciliation-script behavior against a real on-disk store copy."""

    def test_writes_step_implements(self) -> None:
        """A backlink for a step unions the AC id into that step's implements[]."""
        with TemporaryDirectory() as tmp:
            pt = _copy_store(Path(tmp))
            flow_path = pt / _FIXTURE_FLOW_REL

            new_ac = "UXP-NEW-1"
            backlinks = {"review": [new_ac]}
            proc = _run_script(
                pt,
                ["--flow", _FIXTURE_FLOW_ID, "--backlinks-json", json.dumps(backlinks), "--skip-generate"],
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)

            flow = _read_json(flow_path)
            review = next(s for s in flow["steps"] if s["id"] == "review")
            self.assertIn(new_ac, review["implements"])
            # Union preserves the pre-existing edge.
            self.assertIn("UXP-210d-4", review["implements"])

    def test_reruns_generator_regenerates_derived(self) -> None:
        """Running WITHOUT --skip-generate reconciles index.json by_ac + flow impl_summary."""
        with TemporaryDirectory() as tmp:
            pt = _copy_store(Path(tmp))
            index_before = _read_json(pt / "index.json")

            new_ac = "UXP-NEW-2"
            backlinks = {"payDetails": [new_ac]}
            proc = _run_script(
                pt,
                ["--flow", _FIXTURE_FLOW_ID, "--backlinks-json", json.dumps(backlinks)],
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)

            index_after = _read_json(pt / "index.json")
            # The generator inverts step.implements into index by_ac — the new edge appears.
            self.assertIn(new_ac, index_after.get("by_ac", {}))
            self.assertIn(
                _FIXTURE_FLOW_ID,
                {entry["flow"] for entry in index_after["by_ac"][new_ac]},
            )
            # index.json is regenerated (by_ac changed vs the pristine copy).
            self.assertNotEqual(index_before.get("by_ac"), index_after.get("by_ac"))

    def test_idempotent(self) -> None:
        """A second identical reconciliation leaves every file byte-for-byte unchanged."""
        with TemporaryDirectory() as tmp:
            pt = _copy_store(Path(tmp))
            args = [
                "--flow",
                _FIXTURE_FLOW_ID,
                "--backlinks-json",
                json.dumps({"authorize": ["UXP-NEW-3"]}),
            ]
            self.assertEqual(_run_script(pt, args).returncode, 0)

            flow_path = pt / _FIXTURE_FLOW_REL
            index_path = pt / "index.json"
            flow_after_first = flow_path.read_text(encoding="utf-8")
            index_after_first = index_path.read_text(encoding="utf-8")

            self.assertEqual(_run_script(pt, args).returncode, 0)
            self.assertEqual(flow_path.read_text(encoding="utf-8"), flow_after_first)
            self.assertEqual(index_path.read_text(encoding="utf-8"), index_after_first)

    def test_regenerates_meta_flow_impl_status(self) -> None:
        """BOTH meta-flows have valid regenerated impl_summary after a run."""
        with TemporaryDirectory() as tmp:
            pt = _copy_store(Path(tmp))
            proc = _run_script(
                pt,
                ["--flow", _FIXTURE_FLOW_ID, "--backlinks-json", json.dumps({"review": ["UXP-NEW-4"]})],
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)

            for rel in _META_FLOWS:
                flow = _read_json(pt / rel)
                summary = flow["impl_summary"]
                counted = sum(summary[k] for k in ("done", "in_progress", "not_started"))
                self.assertEqual(
                    summary["total"], counted, msg=f"{rel} impl_summary.total mismatch"
                )
                # Each node carries a regenerated impl_status from the derivation vocab.
                for node in flow.get("steps", []) + flow.get("branches", []):
                    self.assertIn(node["impl_status"], ("done", "in_progress", "not_started"))

    def test_unknown_step_is_nonfatal_warning(self) -> None:
        """A backlink for a step id that does not exist is skipped, not fatal."""
        with TemporaryDirectory() as tmp:
            pt = _copy_store(Path(tmp))
            proc = _run_script(
                pt,
                [
                    "--flow",
                    _FIXTURE_FLOW_ID,
                    "--backlinks-json",
                    json.dumps({"does-not-exist": ["UXP-NEW-5"]}),
                    "--skip-generate",
                ],
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            combined = proc.stdout + proc.stderr
            self.assertIn("does-not-exist", combined)

    def test_skip_generate_writes_backlinks_only(self) -> None:
        """--skip-generate writes step.implements but does NOT touch derived index.json."""
        with TemporaryDirectory() as tmp:
            pt = _copy_store(Path(tmp))
            index_before = (pt / "index.json").read_text(encoding="utf-8")
            proc = _run_script(
                pt,
                [
                    "--flow",
                    _FIXTURE_FLOW_ID,
                    "--backlinks-json",
                    json.dumps({"confirmed": ["UXP-NEW-6"]}),
                    "--skip-generate",
                ],
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            # Flow edge written…
            flow = _read_json(pt / _FIXTURE_FLOW_REL)
            confirmed = next(s for s in flow["steps"] if s["id"] == "confirmed")
            self.assertIn("UXP-NEW-6", confirmed["implements"])
            # …but the generator did not run, so index.json is untouched.
            self.assertEqual((pt / "index.json").read_text(encoding="utf-8"), index_before)

    def test_flow_resolves_by_path(self) -> None:
        """--flow accepts a concrete file path as well as a flow id."""
        with TemporaryDirectory() as tmp:
            pt = _copy_store(Path(tmp))
            flow_path = pt / _FIXTURE_FLOW_REL
            proc = _run_script(
                pt,
                [
                    "--flow",
                    str(flow_path),
                    "--backlinks-json",
                    json.dumps({"review": ["UXP-NEW-7"]}),
                    "--skip-generate",
                ],
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            flow = _read_json(flow_path)
            review = next(s for s in flow["steps"] if s["id"] == "review")
            self.assertIn("UXP-NEW-7", review["implements"])


if __name__ == "__main__":
    unittest.main()
