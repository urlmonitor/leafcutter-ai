"""
MODULE: test_uxp_700e_3_i
GOAL: Pin UXP-700e-3-i -- a field being reshaped is read in both shapes and
    written in only the new one: a step's `expands_to` is read as a list whether
    it is written as one id or a list, is written back only as a list, and a
    branch's newly introduced `outcome_kind` is, when absent, reported as a field
    to fill rather than as a violation.
BUSINESS CONTEXT: Read-both / write-new is easy to build half of. The read half
    alone leaves the old shape in the store forever; the write half alone breaks
    every artifact still in the old shape on its next read. So each half has its
    own assertion, and the write half is asserted by reading the FILE back --
    an in-memory list serialised in the old shape would pass every in-process
    check.
ARCHITECTURE: Unit tests call the real shape helpers and the generator's real
    rollup and hierarchy derivations with in-memory journeys. The real-artifact
    test takes the store's own deliver-a-feature journey, puts its expansion
    references back into the older single-value shape, runs the REAL generator
    CLI over it in a tempdir store and reads the file from disk. The
    reachability test runs the REAL generator then the REAL checker CLI, as
    subprocesses, over a store with an old-shaped reference and an unfilled
    branch.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PT_SRC = _REPO_ROOT / "docs" / "product-truth"
_SCRIPTS_DIR = _PT_SRC / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_product_truth as gpt  # noqa: E402
import validate_product_truth as vpt  # noqa: E402

_FLOW_SCHEMA = json.loads((_PT_SRC / "schemas" / "flow.schema.json").read_text(encoding="utf-8"))


def _journey(flow_id: str, steps: list[dict], branches: list[dict] | None = None) -> dict:
    return {
        "id": flow_id, "component": "ux-prototyping", "name": flow_id, "summary": "fixture journey",
        "kind": "user", "source": "mock", "status": "active", "readiness": "draft", "version": 1,
        "tags": [], "entities": [], "steps": steps, "branches": branches or [],
    }


def _step(step_id: str, order: int, **extra) -> dict:
    return {"id": step_id, "label": step_id, "human": f"the actor does {step_id}", "order": order, **extra}


def _branch(branch_id: str, **extra) -> dict:
    return {"id": branch_id, "from": "act", "condition": "something differs", "label": branch_id, **extra}


class TestSingleValueExpansionReferenceIsReadAsAListOfOne(unittest.TestCase):
    def test_single_value_expansion_reference_is_read_as_a_list_of_one(self) -> None:
        # covers: UXP-700e-3-i
        # angle: boundary
        parent = _journey("p/parent", [_step("act", 1, expands_to="p/child")])
        child = _journey("p/child", [_step("inner", 1, implements=["UXP-1"])])
        flows = {"p/parent": parent, "p/child": child}

        self.assertEqual(gpt.expansion_targets(parent["steps"][0]), ["p/child"])
        self.assertEqual(gpt.build_expands_map(flows)["p/parent"], ["p/child"],
                         "the hierarchy must read the single value as its one child, not as characters")
        self.assertEqual(gpt.build_parents_map(flows)["p/child"], [{"flow": "p/parent", "step": "act"}])
        self.assertEqual(gpt.compute_node_status(parent["steps"][0], {"UXP-1": {"work_status": "done"}}, flows),
                         "done", "a single-value reference rolls up from its one child exactly as before")

        gpt.normalise_flow_shapes(parent)
        self.assertEqual(parent["steps"][0]["expands_to"], ["p/child"])
        jsonschema.validate(_journey("p/old", [_step("act", 1, expands_to="p/child")]), _FLOW_SCHEMA)


class TestListExpansionReferenceIsReadUnchanged(unittest.TestCase):
    def test_list_expansion_reference_is_read_unchanged(self) -> None:
        # covers: UXP-700e-3-i
        # angle: criterion
        step = _step("act", 1, expands_to=["p/a", "p/b"])
        parent = _journey("p/parent", [step])
        flows = {
            "p/parent": parent,
            "p/a": _journey("p/a", [_step("x", 1, implements=["UXP-1"])]),
            "p/b": _journey("p/b", [_step("y", 1, implements=["UXP-2"])]),
        }
        ac_map = {"UXP-1": {"work_status": "done"}, "UXP-2": {"work_status": "todo"}}

        self.assertEqual(gpt.expansion_targets(step), ["p/a", "p/b"])
        gpt.normalise_flow_shapes(parent)
        self.assertEqual(step["expands_to"], ["p/a", "p/b"], "a list is kept as written")
        self.assertEqual(gpt.build_expands_map(flows)["p/parent"], ["p/a", "p/b"])
        self.assertEqual(gpt.compute_node_status(step, ac_map, flows), "in_progress",
                         "one child done and one not started rolls up to in progress")
        errors: list[str] = []
        vpt._check_expands({**flows, "p/parent": _journey("p/parent", [_step("act", 1, expands_to=["p/a", "p/gone"])])},
                           {}, errors)
        self.assertTrue(any("'p/gone'" in e and "resolves to no registered flow" in e for e in errors),
                        f"each id in a list is checked for a dangling reference; got {errors!r}")
        jsonschema.validate(parent, _FLOW_SCHEMA)


class TestAbsentBranchOutcomeKindIsReportedAsToBeFilledNotViolated(unittest.TestCase):
    def test_absent_branch_outcome_kind_is_reported_as_to_be_filled_not_violated(self) -> None:
        # covers: UXP-700e-3-i
        # angle: boundary
        flows = {"p/j": _journey("p/j", [_step("act", 1)],
                                 [_branch("unfilled"), _branch("filled", outcome_kind="failure")])}
        errors: list[str] = []
        warnings: list[str] = []

        unfilled = vpt._check_outcome_kinds(flows, warnings)

        self.assertEqual(unfilled, 1)
        self.assertEqual(errors, [], "an absent outcome kind is not a violation")
        self.assertEqual(len(warnings), 1, f"one to-be-filled report expected; got {warnings!r}")
        self.assertIn("to-be-filled", warnings[0])
        self.assertIn("p/j", warnings[0])
        self.assertIn("'unfilled'", warnings[0])
        self.assertNotIn("'filled'", warnings[0], "a branch that carries an outcome kind is not reported")
        jsonschema.validate(flows["p/j"], _FLOW_SCHEMA)


def _store(root: Path) -> Path:
    pt = root / "docs" / "product-truth"
    shutil.copytree(_SCRIPTS_DIR, pt / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(_PT_SRC / "schemas", pt / "schemas")
    for place in ("mock-data", "mockups", "classifier"):
        (pt / place).mkdir(parents=True)
    (pt / "classifier" / "eval.jsonl").write_text("", encoding="utf-8")
    (root / "docs" / "acceptance-criteria").mkdir(parents=True)
    return pt


def _put_journeys(pt: Path, journeys: list[dict]) -> None:
    for j in journeys:
        product, name = j["id"].split("/", 1)
        path = pt / "flows" / product / f"{name}.flow.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(j, indent=2) + "\n", encoding="utf-8")
    (pt / "index.json").write_text(json.dumps({
        "artifacts": [{"id": j["id"], "type": "flow", "component": j["component"],
                       "path": "flows/{}/{}.flow.json".format(*j["id"].split("/", 1)), "status": "active",
                       "readiness": j["readiness"], "version": j["version"]} for j in journeys],
        "entity_registry": [],
    }, indent=2) + "\n", encoding="utf-8")


def _generate(pt: Path) -> None:
    subprocess.run([sys.executable, str(pt / "scripts" / "generate_product_truth.py")],
                   capture_output=True, text=True, timeout=120, check=True)


class TestRewrittenArtifactIsSerialisedOnlyInTheNewShape(unittest.TestCase):
    def test_rewritten_artifact_is_serialised_only_in_the_new_shape(self) -> None:
        # covers: UXP-700e-3-i
        # angle: real_artifact
        real = json.loads((_PT_SRC / "flows" / "leafcutter" / "deliver-a-feature.flow.json").read_text(encoding="utf-8"))
        old_shaped = [s["id"] for s in real["steps"] if s.get("expands_to")]
        self.assertGreaterEqual(len(old_shaped), 3, "the real journey must carry the expansion references under test")
        for step in real["steps"]:
            if step.get("expands_to"):
                step["expands_to"] = gpt.expansion_targets(step)[0]

        with tempfile.TemporaryDirectory() as tmp:
            pt = _store(Path(tmp))
            _put_journeys(pt, [real])
            _generate(pt)
            on_disk = json.loads((pt / "flows" / "leafcutter" / "deliver-a-feature.flow.json").read_text(encoding="utf-8"))

        written = {s["id"]: s.get("expands_to") for s in on_disk["steps"] if s["id"] in old_shaped}
        for step_id, value in written.items():
            self.assertIsInstance(value, list, f"step {step_id!r} was written back in the older single-value shape")
            self.assertEqual(len(value), 1)


class TestUxp700e3IReachableFromEntryPoint(unittest.TestCase):
    def test_uxp_700e_3_i_reachable_from_entry_point(self) -> None:
        # covers: UXP-700e-3-i
        # angle: reachability
        # Entry point: the generator's CLI then the checker's CLI, as subprocesses.
        parent = _journey("p/parent", [_step("act", 1, expands_to="p/child")], [_branch("detour")])
        child = _journey("p/child", [_step("act", 1)])
        with tempfile.TemporaryDirectory() as tmp:
            pt = _store(Path(tmp))
            _put_journeys(pt, [parent, child])
            _generate(pt)
            written = json.loads((pt / "flows" / "p" / "parent.flow.json").read_text(encoding="utf-8"))
            result = subprocess.run([sys.executable, str(pt / "scripts" / "validate_product_truth.py")],
                                    capture_output=True, text=True, timeout=120)

        self.assertEqual(written["steps"][0]["expands_to"], ["p/child"])
        self.assertEqual(result.returncode, 0, f"neither shape nor an unfilled field blocks; stderr={result.stderr!r}")
        self.assertIn("[to-be-filled] p/parent", result.stderr)
        self.assertIn("'detour'", result.stderr)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(payload["outcome"], "checked-and-sound")
        self.assertEqual(payload["examined_by_check"].get("outcome-kinds"), 2)


if __name__ == "__main__":
    unittest.main()
