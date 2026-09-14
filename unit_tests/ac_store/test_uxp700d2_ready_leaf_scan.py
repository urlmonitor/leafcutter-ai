"""
MODULE: test_uxp700d2_ready_leaf_scan
GOAL: Failing test stubs for UXP-700d-2 — "No piece of the example product
    can be picked up as work." Proves against the REAL ready-leaf scan entry
    point (scripts/ac_store/scan_ac_store.py's CLI, invoked as a subprocess —
    not against a helper function in isolation, per the AC's own
    test_rationale) that AC records describing the example product are
    excluded from BOTH the ready and the blocked set, and that the scan
    states how many criteria it set aside as example content.
TICKET: fast-lane build UXP-700d-1 UXP-700d-2 UXP-700d-2-i UXP-700d-2-ii
COVERS: UXP-700d-2

FIXTURE DESIGN NOTE: the store built here is synthetic (tmp_path), not the
live docs/acceptance-criteria/ store — UXP-700d-2-i is the sibling record
that pins the assertion to the three specific example criteria observed in
the LIVE store (UXP-210d-4, UXP-210d-5, UXP-210d-6); see
test_uxp700d2_i_live_store.py. This split mirrors UXP-700d-2-i's own
test_rationale verbatim: "UXP-700d-2 is provable against a synthetic
fixture ... this record pins the assertion to the three specific criteria
observed in the live store."

RED-STATE CONTRACT (what must be implemented to turn this green):
    scan_ac_store.py must classify an AC record as "example content" when it
    carries a product-root marker distinguishing it from the project's own
    record (this test uses `product: fern-and-fig`, following the same
    product-root convention UXP-700d-1 establishes for product-truth
    artifacts) and:
      1. exclude such records from the `ready` JSON array,
      2. exclude such records from the `blocked` JSON array,
      3. report how many records were excluded via a new `set_aside_count`
         integer field in the --json output.
    If python-coder settles on a different marker (e.g. a directory-based
    product root instead of a `product:` field), update this fixture builder
    accordingly — see Source-of-Truth Discipline Rule 1 (test drift).
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCAN_SCRIPT = _REPO_ROOT / "scripts" / "ac_store" / "scan_ac_store.py"
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"

sys.path.insert(0, str(_SCRIPTS_DIR))
from scan_ac_store import _load_ac_by_id  # noqa: E402  (real, existing helper)


def _write_ac(root: Path, subdir: str, ac_id: str, *, product: str | None = None, **overrides) -> Path:
    """Write one AC YAML file into *root*/*subdir* and return its path."""
    target = root / subdir
    target.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "id": ac_id,
        "title": overrides.pop("title", f"Test AC {ac_id}"),
        "component": "ux-prototyping",
        "level": overrides.pop("level", "L2"),
        "status": overrides.pop("status", "active"),
        "req_status": "approved",
        "work_status": overrides.pop("work_status", "todo"),
        "readiness": overrides.pop("readiness", "approved"),
        "priority": "medium",
        "depends_on": overrides.pop("depends_on", []),
        "assigned_agent": "frontend-coder",
        "estimated_complexity": "S",
    }
    if product is not None:
        data["product"] = product
    data.update(overrides)
    path = target / f"{ac_id}.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _build_mixed_store(root: Path) -> dict:
    """Build a store with 2 real ACs and 3 example ("fern-and-fig") ACs.

    Returns a dict describing what each id is expected to do once the
    example-content classification exists.
    """
    # Real, project-owned ACs.
    _write_ac(root, "real-product", "ZZZ-100a-1")  # no deps -> ready
    _write_ac(
        root, "real-product", "ZZZ-100a-2", depends_on=["ZZZ-999-does-not-exist"]
    )  # unresolved dep -> blocked

    # Example ("fern-and-fig" plant-shop) ACs, mirroring the real UXP-210d
    # shape: one ready, one blocked behind another example AC.
    _write_ac(root, "example-product", "ZZZ-210d-4", product="fern-and-fig")  # would-be ready
    _write_ac(
        root,
        "example-product",
        "ZZZ-210d-5",
        product="fern-and-fig",
        depends_on=["ZZZ-210d-9"],
    )  # would-be blocked
    _write_ac(
        root, "example-product", "ZZZ-210d-9", product="fern-and-fig", work_status="todo"
    )  # the (not-done) blocker itself — also example content, also leaf/ready

    return {
        "real_ready": "ZZZ-100a-1",
        "real_blocked": "ZZZ-100a-2",
        "example_ids": ["ZZZ-210d-4", "ZZZ-210d-5", "ZZZ-210d-9"],
    }


def _run_scan(ac_root: Path) -> dict:
    """Invoke the REAL scan_ac_store.py CLI as a subprocess and return parsed JSON."""
    result = subprocess.run(
        [sys.executable, str(_SCAN_SCRIPT), "--ac-root", str(ac_root), "--json"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"scan_ac_store.py exited {result.returncode}. stderr={result.stderr}"
    )
    return json.loads(result.stdout)


class TestReadyLeafScanReturnsNoExampleCriteria(unittest.TestCase):
    def test_ready_leaf_scan_returns_no_example_criteria(self) -> None:
        # covers: UXP-700d-2
        # angle: criterion
        """UXP-700d-2: scanning a store containing example criteria returns
        none of them in the ready set (real CLI invocation, not a helper)."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = _build_mixed_store(root)
            output = _run_scan(root)

            ready_ids = {item["ac_id"] for item in output["ready"]}
            self.assertIn(fixture["real_ready"], ready_ids)
            for example_id in fixture["example_ids"]:
                self.assertNotIn(
                    example_id,
                    ready_ids,
                    f"example AC {example_id} must not appear in the ready set",
                )


class TestBlockedSetContainsNoExampleCriteria(unittest.TestCase):
    def test_blocked_set_contains_no_example_criteria(self) -> None:
        # covers: UXP-700d-2
        # angle: criterion
        """UXP-700d-2: none of the example criteria appears in the blocked
        set either, so none becomes ready when a blocker clears."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = _build_mixed_store(root)
            output = _run_scan(root)

            blocked_ids = {item["ac_id"] for item in output["blocked"]}
            self.assertIn(fixture["real_blocked"], blocked_ids)
            for example_id in fixture["example_ids"]:
                self.assertNotIn(
                    example_id,
                    blocked_ids,
                    f"example AC {example_id} must not appear in the blocked set",
                )


class TestScanStatesHowManyCriteriaItSetAside(unittest.TestCase):
    def test_scan_states_how_many_criteria_it_set_aside(self) -> None:
        # covers: UXP-700d-2
        # angle: criterion
        """UXP-700d-2: the scan reports a set-aside count, non-zero for a
        store containing example criteria.

        RED until --json output gains a `set_aside_count` field.
        """
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = _build_mixed_store(root)
            output = _run_scan(root)

            self.assertIn(
                "set_aside_count",
                output,
                "scan --json output must report how many criteria it set aside "
                f"as example content. Got keys: {sorted(output.keys())}",
            )
            self.assertEqual(output["set_aside_count"], len(fixture["example_ids"]))


class TestExampleCriteriaRemainReadableAfterTheChange(unittest.TestCase):
    def test_example_criteria_remain_readable_after_the_change(self) -> None:
        # covers: UXP-700d-2
        # angle: real_artifact
        """UXP-700d-2: each example criterion still loads and still carries
        its original content, and — the other half of the same AC clause —
        it must still be absent from the ready/blocked sets. A fix that only
        deletes the example criteria would pass the readability half and fail
        the exclusion half; a fix that does nothing at all would pass neither.
        """
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = _build_mixed_store(root)
            output = _run_scan(root)

            ready_ids = {item["ac_id"] for item in output["ready"]}
            blocked_ids = {item["ac_id"] for item in output["blocked"]}

            for example_id in fixture["example_ids"]:
                self.assertNotIn(example_id, ready_ids)
                self.assertNotIn(example_id, blocked_ids)

                loaded = _load_ac_by_id(root, example_id)
                self.assertIsNotNone(
                    loaded, f"example AC {example_id} must still be readable from disk"
                )
                self.assertEqual(loaded["id"], example_id)
                self.assertEqual(loaded.get("product"), "fern-and-fig")


if __name__ == "__main__":
    unittest.main()
