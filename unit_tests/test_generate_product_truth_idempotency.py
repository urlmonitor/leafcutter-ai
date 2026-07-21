"""
MODULE: test_generate_product_truth_idempotency
GOAL: Verify that generate_product_truth.py preserves existing 'asof' timestamps
    when derived content is unchanged, even when the run date differs from the
    stored date. This is the core idempotency guarantee that prevents ~97 false
    validate_product_truth.py errors on every calendar-date rollover.
BUSINESS CONTEXT: The product-truth store stamps an 'asof' date on every derived
    field (by_ac entries, impl_summary blocks, impl_asof node stamps). Prior to
    this fix the generator unconditionally set asof = today on every run, causing
    the validator to report ~97 "does not match a fresh rebuild" errors whenever
    the run date differed from the stored date — even when NO logical content
    had changed. This test suite pins the idempotency contract so the regression
    cannot silently reintroduce itself.
ARCHITECTURE: Uses a self-contained tempdir fixture that mirrors the minimal
    product-truth store layout (flows/, mock-data/, index.json, schemas/,
    acceptance-criteria/). Calls generate() directly with injected run_date
    strings to simulate calendar-date boundaries without touching the real store.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# The scripts directory is not on the default path; add it so we can import.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "product-truth" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# Likewise for schemas (needed at runtime by validate_product_truth).
_PT_SRC = Path(__file__).resolve().parent.parent / "docs" / "product-truth"

import generate_product_truth as gpt  # noqa: E402


# --------------------------------------------------------------------------- #
# Minimal schema stubs needed by the validator (not exercised by these tests).
# --------------------------------------------------------------------------- #
_FLOW_SCHEMA_STUB = {
    "type": "object",
    "properties": {},
    "additionalProperties": True,
}


# --------------------------------------------------------------------------- #
# Fixture builders
# --------------------------------------------------------------------------- #

def _make_store(tmp: Path, ac_work_status: str = "not_started") -> None:
    """Populate a minimal product-truth store inside tmp."""
    # acceptance-criteria/
    ac_dir = tmp / "acceptance-criteria" / "leafcutter"
    ac_dir.mkdir(parents=True)
    ac_yaml = {
        "id": "ACD-001",
        "work_status": ac_work_status,
        "title": "A test acceptance criterion",
    }
    (ac_dir / "ACD-001.yaml").write_text(yaml.safe_dump(ac_yaml), encoding="utf-8")

    # flows/
    flow_dir = tmp / "docs" / "product-truth" / "flows" / "leafcutter"
    flow_dir.mkdir(parents=True)
    flow = {
        "id": "leafcutter/test-flow",
        "component": "leafcutter",
        "kind": "user",
        "source": "real",
        "status": "active",
        "readiness": "draft",
        "version": 1,
        "entities": [],
        "steps": [
            {
                "id": "step-a",
                "label": "Step A",
                "order": 1,
                "implements": ["ACD-001"],
                "impl_status": "not_started",
                "impl_asof": "2026-01-01",
            }
        ],
        "branches": [],
        "impl_summary": {
            "done": 0,
            "in_progress": 0,
            "not_started": 1,
            "total": 1,
            "asof": "2026-01-01",
        },
    }
    (flow_dir / "test-flow.flow.json").write_text(
        json.dumps(flow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # mock-data/ (empty dir — no mocks in this fixture)
    (tmp / "docs" / "product-truth" / "mock-data").mkdir(parents=True)

    # schemas/ — copy real schemas so generate/validate can load them
    schemas_src = _PT_SRC / "schemas"
    schemas_dst = tmp / "docs" / "product-truth" / "schemas"
    if schemas_src.exists():
        shutil.copytree(schemas_src, schemas_dst)
    else:
        schemas_dst.mkdir(parents=True)

    # index.json
    store_path = tmp / "docs" / "product-truth"
    index = {
        "artifacts": [
            {
                "id": "leafcutter/test-flow",
                "type": "flow",
                "component": "leafcutter",
                "status": "active",
                "readiness": "draft",
                "version": 1,
                "impl_summary": {
                    "done": 0,
                    "in_progress": 0,
                    "not_started": 1,
                    "total": 1,
                    "asof": "2026-01-01",
                },
            }
        ],
        "entity_registry": [],
        "by_component": {},
        "by_entity": {},
        "by_flow": {
            "leafcutter/test-flow": {
                "component": "leafcutter",
                "level": None,
                "entities": [],
                "path": "flows/leafcutter/test-flow.flow.json",
                "impl_status": "not_started",
                "impl_summary": {
                    "done": 0,
                    "in_progress": 0,
                    "not_started": 1,
                    "total": 1,
                    "asof": "2026-01-01",
                },
                "expands": [],
                "parents": [],
            }
        },
        "by_ac": {
            "ACD-001": [
                {
                    "flow": "leafcutter/test-flow",
                    "node": "step-a",
                    "node_kind": "step",
                    "flow_kind": "user",
                    "screen": None,
                    "mock_data": None,
                    "entities": [],
                    "source": "real",
                    "asof": "2026-01-01",
                }
            ]
        },
    }
    (store_path / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # Write the AC's product_truth block (what the generator would write)
    ac_path = ac_dir / "ACD-001.yaml"
    ac_with_pt = dict(ac_yaml)
    ac_with_pt["product_truth"] = [
        {
            "flow": "leafcutter/test-flow",
            "node": "step-a",
            "node_kind": "step",
            "flow_kind": "user",
            "screen": None,
            "mock_data": None,
            "entities": [],
            "source": "real",
            "asof": "2026-01-01",
        }
    ]
    # Write as the generator's own hand-rolled YAML (not yaml.dump) to match the format
    # the generator produces, so the no-change comparison in write_ac_product_truth works.
    pt_text = (
        f"id: {ac_with_pt['id']}\n"
        f"work_status: {ac_with_pt['work_status']}\n"
        f"title: {ac_with_pt['title']}\n"
        "product_truth:\n"
        "  - flow: leafcutter/test-flow\n"
        "    node: step-a\n"
        "    node_kind: step\n"
        "    flow_kind: user\n"
        "    screen: null\n"
        "    mock_data: null\n"
        "    entities: []\n"
        "    source: real\n"
        "    asof: '2026-01-01'\n"
    )
    ac_path.write_text(pt_text, encoding="utf-8")


def _run_generate(tmp: Path, run_date: str) -> bool:
    """Run generate() against a fixture store inside tmp; return changed flag."""
    # Temporarily redirect module-level STORE and AC_STORE to the fixture.
    store = tmp / "docs" / "product-truth"
    ac_store = tmp / "acceptance-criteria"
    original_store = gpt.STORE
    original_ac_store = gpt.AC_STORE
    gpt.STORE = store
    gpt.AC_STORE = ac_store
    try:
        return gpt.generate(check=False, run_date=run_date)
    finally:
        gpt.STORE = original_store
        gpt.AC_STORE = original_ac_store


def _read_asof_from_ac(tmp: Path, ac_id: str) -> str | None:
    """Extract the asof from the first product_truth entry in an AC file."""
    ac_path = tmp / "acceptance-criteria" / "leafcutter" / f"{ac_id}.yaml"
    data = yaml.safe_load(ac_path.read_text(encoding="utf-8")) or {}
    truth = data.get("product_truth") or []
    if truth:
        return truth[0].get("asof")
    return None


def _read_flow_impl_asof(tmp: Path) -> str | None:
    """Extract the impl_asof from the first step of the test flow."""
    flow_path = tmp / "docs" / "product-truth" / "flows" / "leafcutter" / "test-flow.flow.json"
    data = json.loads(flow_path.read_text(encoding="utf-8"))
    steps = data.get("steps") or []
    return steps[0].get("impl_asof") if steps else None


def _read_flow_summary_asof(tmp: Path) -> str | None:
    """Extract impl_summary.asof from the test flow JSON."""
    flow_path = tmp / "docs" / "product-truth" / "flows" / "leafcutter" / "test-flow.flow.json"
    data = json.loads(flow_path.read_text(encoding="utf-8"))
    return (data.get("impl_summary") or {}).get("asof")


def _read_index_by_ac_asof(tmp: Path) -> str | None:
    """Extract asof from the first by_ac entry for ACD-001 in index.json."""
    idx = json.loads((tmp / "docs" / "product-truth" / "index.json").read_text(encoding="utf-8"))
    entries = idx.get("by_ac", {}).get("ACD-001") or []
    return entries[0].get("asof") if entries else None


def _read_index_by_flow_summary_asof(tmp: Path) -> str | None:
    """Extract impl_summary.asof from by_flow for the test flow in index.json."""
    idx = json.loads((tmp / "docs" / "product-truth" / "index.json").read_text(encoding="utf-8"))
    entry = idx.get("by_flow", {}).get("leafcutter/test-flow") or {}
    return (entry.get("impl_summary") or {}).get("asof")


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
class TestAsofPreservationOnUnchangedContent(unittest.TestCase):
    """Core idempotency guarantee: asof is NOT bumped when content is unchanged."""

    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp_dir.name)
        _make_store(self.tmp)

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_same_date_regen_preserves_asof_in_ac_yaml(self) -> None:
        """Regenerating on the SAME date as stored should preserve asof (no churn)."""
        _run_generate(self.tmp, run_date="2026-01-01")
        self.assertEqual(_read_asof_from_ac(self.tmp, "ACD-001"), "2026-01-01")

    def test_different_date_regen_preserves_asof_in_ac_yaml(self) -> None:
        """Regenerating on a DIFFERENT date must NOT bump asof when content is unchanged.

        This is the core regression test for the non-idempotent-date bug:
        content identical, but the calendar date advanced past the stored asof.
        Before the fix, every field would be re-stamped with today's date,
        producing ~97 false stale errors on every calendar-date rollover.
        """
        _run_generate(self.tmp, run_date="2099-12-31")
        self.assertEqual(
            _read_asof_from_ac(self.tmp, "ACD-001"),
            "2026-01-01",
            "asof must be preserved when logical content is unchanged, "
            "regardless of the run date.",
        )

    def test_different_date_preserves_flow_impl_asof(self) -> None:
        """Node impl_asof in the flow JSON must be preserved when status unchanged."""
        _run_generate(self.tmp, run_date="2099-12-31")
        self.assertEqual(_read_flow_impl_asof(self.tmp), "2026-01-01")

    def test_different_date_preserves_flow_summary_asof(self) -> None:
        """Flow impl_summary.asof must be preserved when counts are unchanged."""
        _run_generate(self.tmp, run_date="2099-12-31")
        self.assertEqual(_read_flow_summary_asof(self.tmp), "2026-01-01")

    def test_different_date_preserves_index_by_ac_asof(self) -> None:
        """index.json by_ac entry asof must be preserved when content is unchanged."""
        _run_generate(self.tmp, run_date="2099-12-31")
        self.assertEqual(_read_index_by_ac_asof(self.tmp), "2026-01-01")

    def test_different_date_preserves_index_by_flow_summary_asof(self) -> None:
        """index.json by_flow impl_summary.asof must be preserved when counts unchanged."""
        _run_generate(self.tmp, run_date="2099-12-31")
        self.assertEqual(_read_index_by_flow_summary_asof(self.tmp), "2026-01-01")

    def test_second_regen_produces_no_file_change(self) -> None:
        """Two consecutive generator runs must produce identical output (no diff).

        This verifies the full-round-trip idempotency: after a first run the
        second run must detect no change and return False (nothing written).
        """
        # Run once with a "later" date — content unchanged, asof preserved.
        _run_generate(self.tmp, run_date="2026-06-01")
        # Capture state after first run.
        ac_text_after_1 = (
            self.tmp / "acceptance-criteria" / "leafcutter" / "ACD-001.yaml"
        ).read_text(encoding="utf-8")
        flow_text_after_1 = (
            self.tmp / "docs" / "product-truth" / "flows" / "leafcutter" / "test-flow.flow.json"
        ).read_text(encoding="utf-8")
        index_text_after_1 = (
            self.tmp / "docs" / "product-truth" / "index.json"
        ).read_text(encoding="utf-8")

        # Run again with a yet-different date — should produce ZERO changes.
        changed = _run_generate(self.tmp, run_date="2026-12-31")
        ac_text_after_2 = (
            self.tmp / "acceptance-criteria" / "leafcutter" / "ACD-001.yaml"
        ).read_text(encoding="utf-8")
        flow_text_after_2 = (
            self.tmp / "docs" / "product-truth" / "flows" / "leafcutter" / "test-flow.flow.json"
        ).read_text(encoding="utf-8")
        index_text_after_2 = (
            self.tmp / "docs" / "product-truth" / "index.json"
        ).read_text(encoding="utf-8")

        self.assertFalse(changed, "Second run must return False (nothing changed)")
        self.assertEqual(ac_text_after_1, ac_text_after_2, "AC YAML must not change on second run")
        self.assertEqual(flow_text_after_1, flow_text_after_2, "Flow JSON must not change on second run")
        self.assertEqual(index_text_after_1, index_text_after_2, "index.json must not change on second run")


class TestAsofUpdatesWhenContentChanges(unittest.TestCase):
    """asof MUST be bumped when the underlying AC work_status changes."""

    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp_dir.name)
        # Initialise store with not_started AC.
        _make_store(self.tmp, ac_work_status="not_started")

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_asof_updates_when_impl_status_changes(self) -> None:
        """When an AC's work_status changes its derived impl_status, asof must update.

        This confirms the generator is not OVER-preserving: a genuine content
        change must still bump the asof to the run date.
        """
        # Verify starting asof is the stored date.
        self.assertEqual(_read_flow_impl_asof(self.tmp), "2026-01-01")

        # Change the AC's work_status from not_started → done.
        ac_path = self.tmp / "acceptance-criteria" / "leafcutter" / "ACD-001.yaml"
        text = ac_path.read_text(encoding="utf-8")
        updated_text = text.replace("work_status: not_started", "work_status: done")
        ac_path.write_text(updated_text, encoding="utf-8")

        # Regenerate with a specific run_date.
        _run_generate(self.tmp, run_date="2026-06-15")

        # The flow's step now derives impl_status=done — asof must be updated.
        self.assertEqual(
            _read_flow_impl_asof(self.tmp),
            "2026-06-15",
            "impl_asof must be updated when the node's impl_status changes.",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
