"""
MODULE: test_uxp_700c_1_i
GOAL: Pin UXP-700c-1-i and ADR-042 Amendment 1 -- a pointer whose target is not a
    kind the checker knows how to resolve is reported as UNRESOLVABLE: named with
    its holder, position, target and reason; counted neither as resolved nor as
    broken; and enough on its own to withhold checked-and-sound.
BUSINESS CONTEXT: UXP-700c-1 gave the checker a two-valued pointer verdict --
    resolved, or broken. That partition only works when every target is a kind
    the checker understands. Anything else was forced into one bucket or the
    other, and both are wrong: counted as resolved it is a false green (the run
    claims to have verified what it never understood); counted as broken it is
    a hard commit block for a pointer nobody knows to be dangling, which trains
    people to ignore the report. Screen and mockup pointers are an anticipated
    future kind, so this is not hypothetical.
ARCHITECTURE: Direct tests call product_truth_checks._check_pointers (re-exported
    by validate_product_truth) with an `unresolvable` out-list. The reachability
    test authors a journey and an AC, runs the REAL generator CLI and then the
    REAL checker CLI as subprocesses, and asserts on the structured stdout
    payload (ADR-042 §3) -- with a control run proving that the unclassifiable
    pointer, and nothing else, is what moves the outcome.

    NAMED MUTATION this file exists to kill: folding unresolvable into resolved.
    UXP-700c-1's own tests stay green under it, because every pointer they feed
    is classifiable; the boundary test below does not.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PT_SRC = _REPO_ROOT / "docs" / "product-truth"
_SCRIPTS_DIR = _PT_SRC / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import validate_product_truth as vpt  # noqa: E402

_FLOW_ID = "fixture-product/cli-journey"
_UNCLASSIFIABLE = "screen:checkout"


def _flow(implements: list[str]) -> dict:
    return {
        "id": _FLOW_ID, "component": "fixture-product", "name": "cli-journey", "summary": "fixture",
        "kind": "user", "source": "mock", "status": "active", "readiness": "draft", "version": 1,
        "entities": [],
        "steps": [{"id": "browse", "label": "browse", "human": "the actor browses", "order": 1,
                   "implements": implements}],
        "branches": [],
    }


class TestUnclassifiablePointerIsReportedAsUnresolvable(unittest.TestCase):
    def test_unclassifiable_pointer_is_reported_as_unresolvable(self) -> None:
        # covers: UXP-700c-1-i
        # angle: boundary
        flows = {_FLOW_ID: _flow([_UNCLASSIFIABLE])}
        errors: list[str] = []
        unresolvable: list[str] = []

        resolved = vpt._check_pointers(flows, ac_ids={"AC-REAL-1"}, mockups={}, errors=errors,
                                       unresolvable=unresolvable)

        self.assertEqual(len(unresolvable), 1, f"expected one unresolvable report, got {unresolvable!r}")
        message = unresolvable[0]
        self.assertTrue(message.startswith("[pointer-unresolvable]"),
                        f"must carry the prefix that separates it from a broken pointer: {message!r}")
        self.assertIn(_FLOW_ID, message, "must name the artifact holding the pointer")
        self.assertIn("browse", message, "must name the position within that artifact")
        self.assertIn(_UNCLASSIFIABLE, message, "must name the target that could not be classified")
        reason = message.split(_UNCLASSIFIABLE, 1)[1].lower()
        self.assertTrue(reason.strip(" :'\"—-"), "must state a reason, not end at the target")
        self.assertNotIn("unknown", reason, "the reason must say what the target failed, not just 'unknown'")
        self.assertEqual(errors, [], "an unresolvable pointer must never be reported as broken")
        self.assertEqual(resolved, 0, "an unresolvable pointer must never be counted as resolved")


class TestUnresolvablePointerIsInNeitherTheResolvedNorTheBrokenSet(unittest.TestCase):
    def test_unresolvable_pointer_is_in_neither_the_resolved_nor_the_broken_set(self) -> None:
        # covers: UXP-700c-1-i
        # angle: boundary
        # One pointer of each verdict on the same step: an AC id that resolves, an AC id
        # that is well-formed but absent (broken), and a target of no recognised kind.
        flows = {_FLOW_ID: _flow(["AC-REAL-1", "AC-GONE-9", _UNCLASSIFIABLE])}
        errors: list[str] = []
        unresolvable: list[str] = []

        resolved = vpt._check_pointers(flows, ac_ids={"AC-REAL-1"}, mockups={}, errors=errors,
                                       unresolvable=unresolvable)

        self.assertEqual(resolved, 1, "only the pointer that resolved may be counted as resolved")
        self.assertEqual(len(errors), 1, f"only the absent AC id is broken; got {errors!r}")
        self.assertIn("AC-GONE-9", errors[0])
        self.assertFalse(any(_UNCLASSIFIABLE in e for e in errors), "the unclassifiable target must not be broken")
        self.assertEqual(len(unresolvable), 1)
        self.assertIn(_UNCLASSIFIABLE, unresolvable[0])
        self.assertFalse(any("AC-GONE-9" in u for u in unresolvable),
                         "a well-formed AC id that fails lookup is BROKEN, never unresolvable (ADR-042 §A4)")


def _install_and_check(tmp: Path, implements: list[str]) -> subprocess.CompletedProcess:
    """Author one journey and one AC, derive the index with the real generator CLI,
    then run the real checker CLI -- the path an installed project takes."""
    pt = tmp / "docs" / "product-truth"
    shutil.copytree(_SCRIPTS_DIR, pt / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(_PT_SRC / "schemas", pt / "schemas")
    for place in ("mock-data", "mockups"):
        (pt / place).mkdir(parents=True)
    (pt / "classifier").mkdir(parents=True)
    (pt / "classifier" / "eval.jsonl").write_text("", encoding="utf-8")
    ac_dir = tmp / "docs" / "acceptance-criteria" / "fixture-product"
    ac_dir.mkdir(parents=True)
    (ac_dir / "AC-REAL-1.yaml").write_text(yaml.safe_dump({"id": "AC-REAL-1", "work_status": "todo"}),
                                           encoding="utf-8")
    flow_path = pt / "flows" / "fixture-product" / "cli-journey.flow.json"
    flow_path.parent.mkdir(parents=True)
    flow_path.write_text(json.dumps(_flow(implements), indent=2) + "\n", encoding="utf-8")
    (pt / "index.json").write_text(json.dumps({
        "artifacts": [{"id": _FLOW_ID, "type": "flow", "component": "fixture-product",
                       "path": "flows/fixture-product/cli-journey.flow.json", "status": "active",
                       "readiness": "draft", "version": 1}],
        "entity_registry": [],
    }, indent=2) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(pt / "scripts" / "generate_product_truth.py")],
                   capture_output=True, text=True, timeout=60, check=True)
    return subprocess.run([sys.executable, str(pt / "scripts" / "validate_product_truth.py")],
                          capture_output=True, text=True, timeout=60)


def _payload(result: subprocess.CompletedProcess) -> dict:
    return json.loads(result.stdout.strip().splitlines()[-1])


class TestUxp700c1iReachableFromEntryPoint(unittest.TestCase):
    def test_uxp_700c_1_i_reachable_from_entry_point(self) -> None:
        # covers: UXP-700c-1-i
        # angle: reachability
        # Entry point: validate_product_truth.py's own CLI, run as a subprocess after the
        # generator CLI, asserting on the stdout payload's fields per ADR-042 §3.
        with tempfile.TemporaryDirectory() as control_tmp:
            control = _install_and_check(Path(control_tmp), ["AC-REAL-1"])
        with tempfile.TemporaryDirectory() as tmp:
            result = _install_and_check(Path(tmp), ["AC-REAL-1", _UNCLASSIFIABLE])

        self.assertEqual(_payload(control)["outcome"], "checked-and-sound",
                         f"control: the same store without the unclassifiable pointer must be sound; "
                         f"stderr={control.stderr!r}")

        payload = _payload(result)
        self.assertEqual(result.returncode, 0,
                         f"an unresolvable pointer must not block the commit (ADR-042 §A3); stderr={result.stderr!r}")
        self.assertEqual(payload["outcome"], "degraded",
                         "a run holding an unresolvable pointer must not report checked-and-sound (ADR-042 §A2)")
        self.assertEqual(payload.get("resolved_pointers"), 1, f"payload={payload!r}")
        self.assertEqual(payload.get("unresolvable_pointers"), 1, f"payload={payload!r}")
        self.assertIn("[pointer-unresolvable]", result.stderr)
        self.assertNotIn("does not resolve in the AC store", result.stderr,
                         "the unclassifiable pointer must not be reported as a broken pointer")


if __name__ == "__main__":
    unittest.main()
