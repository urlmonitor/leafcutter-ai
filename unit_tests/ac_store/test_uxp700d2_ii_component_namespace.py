"""
MODULE: test_uxp700d2_ii_component_namespace
GOAL: Failing test stubs for UXP-700d-2-ii — "A real criterion stored beside
    the example set is still dispatchable." Proves the example-content
    classification does NOT key on the `component` field: the 18 example
    criteria and every real AC in the UXP-700 tree share
    component: ux-prototyping, so an implementation that sets aside
    "anything under ux-prototyping" would pass UXP-700d-2 and UXP-700d-2-i
    while silently removing the whole component from the work queue. This is
    the paired acceptable input for that specific wrong fix.
TICKET: fast-lane build UXP-700d-1 UXP-700d-2 UXP-700d-2-i UXP-700d-2-ii
COVERS: UXP-700d-2-ii

RED-STATE CONTRACT: same as test_uxp700d2_ready_leaf_scan.py — the
example-content classification (marker: `product: fern-and-fig`) must be
independent of `component`/`components`.
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


def _write_ac(root: Path, subdir: str, ac_id: str, *, component: str, product: str | None = None, **overrides) -> Path:
    target = root / subdir
    target.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "id": ac_id,
        "title": overrides.pop("title", f"Test AC {ac_id}"),
        "component": component,
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


def _run_scan(ac_root: Path) -> dict:
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


class TestRealCriterionInSharedNamespaceStaysReady(unittest.TestCase):
    def test_a_real_criterion_in_the_shared_namespace_stays_in_the_ready_set(self) -> None:
        # covers: UXP-700d-2-ii
        # angle: boundary
        """UXP-700d-2-ii: a ready, real criterion under the SAME component
        (ux-prototyping) the example criteria also use is still returned by
        the ready-leaf scan. Mirrors UXP-514, a real ux-prototyping criterion
        cited in this AC's doc_links as "the kind of record that must stay
        dispatchable."
        """
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Real AC, same component as the example set, no product marker.
            _write_ac(root, "real", "ZZZ-514", component="ux-prototyping")
            # Example AC, same component as the real one above.
            _write_ac(
                root,
                "example",
                "ZZZ-210d-4",
                component="ux-prototyping",
                product="fern-and-fig",
            )

            output = _run_scan(root)
            ready_ids = {item["ac_id"] for item in output["ready"]}

            self.assertIn(
                "ZZZ-514",
                ready_ids,
                "a real AC sharing component: ux-prototyping with the example "
                "set must still be returned by the ready scan",
            )
            self.assertNotIn("ZZZ-210d-4", ready_ids)


class TestSetAsideRuleDoesNotKeyOnComponentNamespace(unittest.TestCase):
    def test_set_aside_rule_does_not_key_on_the_component_namespace(self) -> None:
        # covers: UXP-700d-2-ii
        # angle: seam
        """UXP-700d-2-ii: moving a real criterion into the same component as
        the example criteria does not set it aside, AND the exclusion of
        example criteria is invariant across different `component` values —
        proving the rule does not key on component at all, in either
        direction. Pipes real, on-disk AC YAML files (real producer output,
        written via yaml.safe_dump — not a hand-typed literal) through the
        REAL scan_ac_store.py CLI (real consumer).
        """
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Two example ACs under two DIFFERENT components.
            _write_ac(
                root,
                "example-a",
                "ZZZ-210d-5",
                component="ux-prototyping",
                product="fern-and-fig",
            )
            _write_ac(
                root,
                "example-b",
                "ZZZ-210d-6",
                component="ac-store",
                product="fern-and-fig",
            )
            # Two real ACs under two DIFFERENT components (one of which
            # matches an example AC's component above).
            _write_ac(root, "real-a", "ZZZ-514", component="ux-prototyping")
            _write_ac(root, "real-b", "ZZZ-515", component="ac-store")

            output = _run_scan(root)
            ready_ids = {item["ac_id"] for item in output["ready"]}

            # Both example ACs excluded, regardless of their component.
            self.assertNotIn("ZZZ-210d-5", ready_ids)
            self.assertNotIn("ZZZ-210d-6", ready_ids)
            # Both real ACs included, regardless of sharing a component with
            # an example AC.
            self.assertIn("ZZZ-514", ready_ids)
            self.assertIn("ZZZ-515", ready_ids)


if __name__ == "__main__":
    unittest.main()
