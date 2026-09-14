"""
MODULE: test_uxp_700e_3
GOAL: Pin UXP-700e-3 -- a journey's labels are checked: its component label must
    resolve to a component registered in the project, its tags must match a
    declared shape, a near miss (case or spacing only) is reported as the
    registered label having been meant, and the run states how many labels it
    resolved.
BUSINESS CONTEXT: A journey's component and tags are how it is found. Both were
    free text, so a typo filed a journey under a component that does not exist
    and nothing said so. Resolving against the WRONG registry would be worse --
    it turns every existing journey into a finding -- which the AC flagged as an
    open question. It is settled here by the repo's own two-axis convention and
    by measurement: a scalar `component` label takes the kebab id from
    docs/acceptance-criteria/index.yaml (all 14 real journeys resolve), not the
    underscore id from docs/components.json (none do).
ARCHITECTURE: Direct tests call the real label check with in-memory journeys and
    a registry set. The seam and reachability tests author a store in a tempdir
    with a real index.yaml registry, run the REAL generator CLI then the REAL
    checker CLI, and read `resolved_labels` from the structured stdout line.

    SEVERITY: reports are WARNINGS, not errors. Labels were free text, and the
    sibling UXP-700e-3-i's migration constraint is that a first tightening warns
    rather than blocks, so upgrading does not start failing commits in projects
    whose labels predate the rule.
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

_REGISTERED = {"ux-prototyping", "build-pipeline"}


def _journey(flow_id: str, component: str, tags: list[str]) -> dict:
    return {
        "id": flow_id, "component": component, "name": flow_id, "summary": "fixture journey",
        "kind": "user", "source": "mock", "status": "active", "readiness": "draft", "version": 1,
        "tags": tags, "entities": [],
        "steps": [{"id": "act", "label": "act", "human": "the actor acts", "order": 1}],
        "branches": [],
    }


class TestUnregisteredComponentLabelIsReportedWithArtifactAndLabel(unittest.TestCase):
    def test_unregistered_component_label_is_reported_with_artifact_and_label(self) -> None:
        # covers: UXP-700e-3
        # angle: criterion
        flows = {"p/typo": _journey("p/typo", "checkout-service", ["checkout"])}
        errors: list[str] = []
        warnings: list[str] = []

        resolved = vpt._check_labels(flows, _REGISTERED, errors, warnings)

        reports = [w for w in warnings if "checkout-service" in w]
        self.assertEqual(len(reports), 1, f"expected one report for the unregistered label; got {warnings!r}")
        self.assertIn("p/typo", reports[0], "the report must name the artifact")
        self.assertEqual(errors, [], "a first tightening of free text warns rather than blocks")
        self.assertEqual(resolved, 1, "only the well-shaped tag resolved; the unregistered component did not")


class TestTagNotMatchingTheDeclaredShapeIsReported(unittest.TestCase):
    def test_tag_not_matching_the_declared_shape_is_reported(self) -> None:
        # covers: UXP-700e-3
        # angle: criterion
        flows = {"p/tags": _journey("p/tags", "ux-prototyping", ["post-purchase", "Post Purchase", "c4_l0"])}
        errors: list[str] = []
        warnings: list[str] = []

        resolved = vpt._check_labels(flows, _REGISTERED, errors, warnings)

        for bad in ("Post Purchase", "c4_l0"):
            matching = [w for w in warnings if bad in w]
            self.assertEqual(len(matching), 1, f"tag {bad!r} must be reported once; got {warnings!r}")
            self.assertIn("p/tags", matching[0], "the report must name the artifact")
        self.assertFalse(any("'post-purchase'" in w for w in warnings), "a well-shaped tag must not be reported")
        self.assertEqual(resolved, 2, "the component and the one well-shaped tag resolved")


class TestNearMissLabelIsReportedAsTheRegisteredOneHavingBeenMeant(unittest.TestCase):
    def test_near_miss_label_is_reported_as_the_registered_one_having_been_meant(self) -> None:
        # covers: UXP-700e-3
        # angle: boundary
        for near_miss in ("UX-Prototyping", "ux prototyping", " ux-prototyping "):
            with self.subTest(label=near_miss):
                flows = {"p/near": _journey("p/near", near_miss, [])}
                warnings: list[str] = []
                vpt._check_labels(flows, _REGISTERED, [], warnings)
                self.assertEqual(len(warnings), 1, f"one report expected; got {warnings!r}")
                report = warnings[0]
                self.assertIn("'ux-prototyping'", report, "the report must name the registered label that was meant")
                self.assertIn("meant", report, "a near miss is reported as the registered one having been meant")
                self.assertNotIn("not registered", report, "a near miss must not be reported as a new label")


def _store(root: Path, journeys: list[dict]) -> Path:
    pt = root / "docs" / "product-truth"
    shutil.copytree(_SCRIPTS_DIR, pt / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(_PT_SRC / "schemas", pt / "schemas")
    for place in ("mock-data", "mockups", "classifier"):
        (pt / place).mkdir(parents=True)
    (pt / "classifier" / "eval.jsonl").write_text("", encoding="utf-8")
    ac_root = root / "docs" / "acceptance-criteria"
    ac_root.mkdir(parents=True)
    (ac_root / "index.yaml").write_text(yaml.safe_dump({"components": [
        {"id": "ux-prototyping", "prefix": "UXP", "description": "fixture"},
        {"id": "build-pipeline", "prefix": "BP", "description": "fixture"},
    ]}), encoding="utf-8")
    return pt


def _set_journeys(pt: Path, journeys: list[dict]) -> None:
    flows_dir = pt / "flows" / "p"
    if flows_dir.exists():
        shutil.rmtree(flows_dir)
    flows_dir.mkdir(parents=True)
    for j in journeys:
        (flows_dir / f"{j['id'].split('/', 1)[1]}.flow.json").write_text(json.dumps(j, indent=2) + "\n", encoding="utf-8")
    (pt / "index.json").write_text(json.dumps({
        "artifacts": [{"id": j["id"], "type": "flow", "component": j["component"],
                       "path": f"flows/p/{j['id'].split('/', 1)[1]}.flow.json", "status": "active",
                       "readiness": "draft", "version": 1} for j in journeys],
        "entity_registry": [],
    }, indent=2) + "\n", encoding="utf-8")


def _check(pt: Path) -> subprocess.CompletedProcess:
    subprocess.run([sys.executable, str(pt / "scripts" / "generate_product_truth.py")],
                   capture_output=True, text=True, timeout=60, check=True)
    return subprocess.run([sys.executable, str(pt / "scripts" / "validate_product_truth.py")],
                          capture_output=True, text=True, timeout=60)


def _payload(result: subprocess.CompletedProcess) -> dict:
    return json.loads(result.stdout.strip().splitlines()[-1])


class TestResolvedLabelCountRisesWithTheNumberOfLabels(unittest.TestCase):
    def test_resolved_label_count_rises_with_the_number_of_labels(self) -> None:
        # covers: UXP-700e-3
        # angle: seam
        one = _journey("p/one", "ux-prototyping", ["checkout"])
        two = _journey("p/two", "build-pipeline", ["pipeline"])
        with tempfile.TemporaryDirectory() as tmp:
            pt = _store(Path(tmp), [])
            _set_journeys(pt, [])
            empty = _payload(_check(pt))
            _set_journeys(pt, [one])
            before = _payload(_check(pt))
            _set_journeys(pt, [one, two])
            after = _payload(_check(pt))

        self.assertEqual(empty.get("resolved_labels"), 0,
                         "a record carrying no labels states zero, so it is told apart from one whose labels all resolved")
        self.assertEqual(before.get("resolved_labels"), 2, f"one component + one tag; payload={before!r}")
        self.assertEqual(after.get("resolved_labels"), before["resolved_labels"] + 2,
                         "adding a journey carrying two resolvable labels raises the count by two")


class TestUxp700e3ReachableFromEntryPoint(unittest.TestCase):
    def test_uxp_700e_3_reachable_from_entry_point(self) -> None:
        # covers: UXP-700e-3
        # angle: reachability
        # Entry point: the checker's own CLI after the generator's, as subprocesses.
        with tempfile.TemporaryDirectory() as tmp:
            pt = _store(Path(tmp), [])
            _set_journeys(pt, [_journey("p/near", "UX Prototyping", ["Checkout"])])
            result = _check(pt)

        self.assertEqual(result.returncode, 0, f"label reports warn, they do not block; stderr={result.stderr!r}")
        self.assertIn("'ux-prototyping'", result.stderr, "the near-miss report must reach the CLI's output")
        self.assertIn("Checkout", result.stderr, "the badly shaped tag must be reported through the CLI")
        self.assertEqual(_payload(result).get("resolved_labels"), 0)


if __name__ == "__main__":
    unittest.main()
