"""
MODULE: test_uxp_700c_1
GOAL: Pin the contract for the new pointer-resolution check UXP-700c-1 adds to
    docs/product-truth/scripts/validate_product_truth.py: every AC `implements`
    pointer a flow step/branch holds must be resolved against the AC store, a
    broken pointer must be reported naming the holder artifact, the position
    within it, and the target that did not resolve, and the run must state how
    many pointers it resolved so a run that resolved none is distinguishable
    from a run in which none were broken.
BUSINESS CONTEXT: UXP-700c-1 is the TIER-1 FLOOR of the "citations" sub-surface
    of the Truthful Project Record epic: it asks only "does the target exist" —
    no content comparison (that is UXP-700c-2), and it must not depend on any
    external tooling so it stays always-on. architect-review (2026-09-09)
    directed this be built as an extension of validate_product_truth.py's
    existing `_check_*` helper pattern (see `_check_flow`, `_check_expands`)
    rather than a parallel checker, keeping the "artifact / position / target"
    naming in the broken-pointer report literal so UXP-700c-3's automatic gate
    can surface it verbatim.
ARCHITECTURE: Targets a NEW module-level function this ticket adds to the
    EXISTING, already-shipped docs/product-truth/scripts/validate_product_truth.py
    (imported here as `vpt`), following the same style as `_check_flow` /
    `_check_expands` (mutates a shared `errors` list) but ALSO returns the
    resolved-pointer count directly, since main() must state that figure in its
    own right (UXP-700b-2's per-check examined-figure convention) rather than
    only inferring it from an error/warning count.

    Required new symbol (does not exist yet — every test below is expected to
    fail until python-coder adds it):

        def _check_pointers(
            flows: dict, ac_ids: set[str], mockups: dict, errors: list[str]
        ) -> int:
            \"\"\"Resolve every AC `implements` pointer across all flow steps
            and branches.

            Returns the number of pointers that resolved (their target AC id
            is a member of ac_ids). Every pointer whose target is NOT in
            ac_ids is appended to `errors` as one message that names, in the
            message text:
              1. the artifact holding the pointer  -> flow['id']
              2. the position within that artifact  -> the step/branch id
              3. the target that did not resolve    -> the AC id
            An intact pointer produces NO entry in `errors` — only a broken
            one is reported.
            \"\"\"

    main() must:
      * call `_check_pointers(flows, ac_ids, mockups, errors)` alongside the
        other `_check_*` calls (its broken-pointer messages feed the SAME
        `errors` list every other check already uses, so a broken pointer
        makes the run exit non-zero exactly like every other error class);
      * state the returned resolved count in the run's own output, in a form
        containing the literal substring "resolved N" (N = the count) EVERY
        run — including N == 0 — so a run that resolved none of the pointers
        it holds is distinguishable, in the text, from a run that resolved
        some and found none of them broken.

    Test-file layout:
      * TestCheckPointersDirect — angle: failure / criterion. Calls
        `_check_pointers` directly against hand-built in-memory flow dicts
        (fast, no process boundary — these two assert the function's own
        return/errors contract in isolation).
      * TestCheckPointersSeam — angle: seam. Pipes the REAL
        `generate_product_truth.load_flows()` producer's on-disk output into
        the REAL `_check_pointers` consumer, proving the resolved count rises
        by exactly one when one further on-disk pointer is added — a round
        trip through real JSON flow files, not a hand-typed in-memory dict
        (Fixture Authenticity Rule, CLAUDE.md / test-writer skill §2h.2).
      * TestReachability — angle: reachability. Runs the REAL
        validate_product_truth.py CLI as a subprocess (its own, pre-existing
        entry point — this ticket EXTENDS that script rather than adding a
        new one, per architect-review) against a complete, schema-valid,
        self-consistent fixture store built from scratch in a tempdir, and
        asserts the new pointer-resolution behaviour is visible in the real
        process's own stdout/stderr and exit code.
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
_SCRIPTS_DIR = _REPO_ROOT / "docs" / "product-truth" / "scripts"
_PT_SRC = _REPO_ROOT / "docs" / "product-truth"

# The scripts directory is not on the default path; add it so we can import,
# mirroring unit_tests/test_generate_product_truth_idempotency.py's convention
# for this same docs/product-truth/scripts location.
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_product_truth as gpt  # noqa: E402
import validate_product_truth as vpt  # noqa: E402  (import of _check_pointers is expected to fail until implemented)

_CLI_PATH = _SCRIPTS_DIR / "validate_product_truth.py"


# --------------------------------------------------------------------------- #
# Fixture builders (mirrors unit_tests/test_generate_product_truth_idempotency.py's
# _make_store convention for this same store shape).
# --------------------------------------------------------------------------- #
def _step(step_id: str, implements: list, order: int, impl_status: str | None = None) -> dict:
    step = {
        "id": step_id,
        "label": step_id,
        "human": f"the actor performs {step_id}",
        "order": order,
        "implements": implements,
    }
    if impl_status is not None:
        step["impl_status"] = impl_status
    return step


def _base_flow(flow_id: str, steps: list) -> dict:
    component = flow_id.split("/", 1)[0]
    return {
        "id": flow_id,
        "component": component,
        "name": flow_id,
        "summary": "fixture flow for UXP-700c-1 pointer-resolution tests",
        "kind": "user",
        "source": "mock",
        "status": "active",
        "readiness": "draft",
        "version": 1,
        "entities": [],
        "steps": steps,
        "branches": [],
    }


def _write_flow(flows_dir: Path, flow: dict) -> None:
    component_dir = flows_dir / flow["component"]
    component_dir.mkdir(parents=True, exist_ok=True)
    name = flow["id"].split("/", 1)[1]
    (component_dir / f"{name}.flow.json").write_text(
        json.dumps(flow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


class TestCheckPointersDirect(unittest.TestCase):
    """Direct-call tests against validate_product_truth._check_pointers()."""

    def test_broken_pointer_is_reported_with_holder_position_and_target(self):
        # covers: UXP-700c-1
        # angle: failure
        # A journey step pointing at an acceptance criterion that does not exist
        # is reported naming the journey (holder), the step (position) and the
        # missing criterion (target). AttributeError until _check_pointers exists.
        flow = _base_flow(
            "fixture-product/broken-journey",
            steps=[_step("browse", implements=["AC-GHOST-1"], order=1)],
        )
        flows = {flow["id"]: flow}
        errors: list[str] = []

        resolved = vpt._check_pointers(flows, ac_ids=set(), mockups={}, errors=errors)

        self.assertEqual(resolved, 0, "a pointer to a nonexistent AC must not count as resolved")
        self.assertEqual(
            len(errors), 1, f"expected exactly one broken-pointer report, got {errors!r}"
        )
        message = errors[0]
        self.assertIn(
            "fixture-product/broken-journey", message, "report must name the holder artifact (the flow)"
        )
        self.assertIn("browse", message, "report must name the position (step id) within the artifact")
        self.assertIn("AC-GHOST-1", message, "report must name the target that did not resolve")

    def test_intact_pointers_are_not_reported(self):
        # covers: UXP-700c-1
        # angle: criterion
        # A store in which every pointer resolves produces no pointer report.
        flow = _base_flow(
            "fixture-product/sound-journey",
            steps=[_step("browse", implements=["AC-REAL-1"], order=1)],
        )
        flows = {flow["id"]: flow}
        errors: list[str] = []

        resolved = vpt._check_pointers(flows, ac_ids={"AC-REAL-1"}, mockups={}, errors=errors)

        self.assertEqual(resolved, 1)
        self.assertEqual(errors, [], "an intact pointer must never be reported as broken")


class TestCheckPointersSeam(unittest.TestCase):
    """Seam: the REAL load_flows() producer piped into the REAL _check_pointers() consumer."""

    def test_resolved_pointer_count_rises_with_the_number_of_pointers(self):
        # covers: UXP-700c-1
        # angle: seam
        # Adding one pointer raises the stated resolved count by exactly one.
        # Proven by round-tripping through real on-disk JSON flow files (via the
        # real generate_product_truth.load_flows() producer) rather than a
        # hand-built in-memory dict — the Fixture Authenticity Rule round trip.
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            flows_dir = tmp / "flows"
            flow = _base_flow(
                "fixture-product/growing-journey",
                steps=[_step("browse", implements=["AC-REAL-1"], order=1)],
            )
            _write_flow(flows_dir, flow)

            original_store = gpt.STORE
            gpt.STORE = tmp
            try:
                loaded_before, _paths = gpt.load_flows()
                resolved_before = vpt._check_pointers(
                    loaded_before, ac_ids={"AC-REAL-1", "AC-REAL-2"}, mockups={}, errors=[]
                )

                flow["steps"].append(_step("checkout", implements=["AC-REAL-2"], order=2))
                _write_flow(flows_dir, flow)

                loaded_after, _paths2 = gpt.load_flows()
                resolved_after = vpt._check_pointers(
                    loaded_after, ac_ids={"AC-REAL-1", "AC-REAL-2"}, mockups={}, errors=[]
                )
            finally:
                gpt.STORE = original_store

        self.assertEqual(
            resolved_after,
            resolved_before + 1,
            "adding exactly one further intact pointer to the on-disk store must raise "
            "the stated resolved count by exactly one on the next run",
        )


def _build_minimal_cli_store(tmp: Path) -> Path:
    """Build a complete, schema-valid, self-consistent product-truth store inside
    tmp — real scripts + real schemas copied verbatim, one small flow authored
    with one intact and one broken AC pointer, and a derived index.json that
    already agrees with a fresh rebuild (so ONLY the new pointer-resolution
    check is exercised by the CLI run, not the pre-existing D1-D5 drift gates).
    Returns the path to the copied validate_product_truth.py CLI entry point.
    """
    pt_root = tmp / "docs" / "product-truth"
    shutil.copytree(_PT_SRC / "scripts", pt_root / "scripts")
    shutil.copytree(_PT_SRC / "schemas", pt_root / "schemas")
    (pt_root / "flows").mkdir(parents=True)
    (pt_root / "mock-data").mkdir(parents=True)
    (pt_root / "mockups").mkdir(parents=True)
    classifier_dir = pt_root / "classifier"
    classifier_dir.mkdir(parents=True)
    (classifier_dir / "eval.jsonl").write_text("", encoding="utf-8")

    ac_dir = tmp / "docs" / "acceptance-criteria" / "fixture-product"
    ac_dir.mkdir(parents=True)
    ac_record = {
        "id": "AC-REAL-1",
        "work_status": "todo",
        "product_truth": [
            {
                "flow": "fixture-product/cli-journey",
                "node": "browse",
                "node_kind": "step",
                "flow_kind": "user",
                "screen": None,
                "mock_data": None,
                "entities": [],
                "source": "mock",
                "asof": "2026-01-01",
            }
        ],
    }
    (ac_dir / "AC-REAL-1.yaml").write_text(
        yaml.safe_dump(ac_record, sort_keys=False), encoding="utf-8"
    )

    flow = _base_flow(
        "fixture-product/cli-journey",
        steps=[
            _step("browse", ["AC-REAL-1"], 1, impl_status="not_started"),
            _step("checkout", ["AC-GHOST-1"], 2, impl_status="not_started"),
        ],
    )
    flow["impl_summary"] = {
        "done": 0,
        "in_progress": 0,
        "not_started": 2,
        "total": 2,
        "asof": "2026-01-01",
    }
    _write_flow(pt_root / "flows", flow)

    common_entry_fields = {
        "flow_kind": "user",
        "screen": None,
        "mock_data": None,
        "entities": [],
        "source": "mock",
        "asof": "2026-01-01",
    }
    index = {
        "artifacts": [],
        "entity_registry": [],
        "by_component": {},
        "by_entity": {},
        "by_flow": {
            "fixture-product/cli-journey": {
                "component": "fixture-product",
                "level": None,
                "entities": [],
                "path": "flows/fixture-product/cli-journey.flow.json",
                "impl_status": "not_started",
                "impl_summary": {
                    "done": 0,
                    "in_progress": 0,
                    "not_started": 2,
                    "total": 2,
                    "asof": "2026-01-01",
                },
                "expands": [],
                "parents": [],
            }
        },
        "by_ac": {
            "AC-REAL-1": [
                {"flow": "fixture-product/cli-journey", "node": "browse", "node_kind": "step", **common_entry_fields}
            ],
            "AC-GHOST-1": [
                {"flow": "fixture-product/cli-journey", "node": "checkout", "node_kind": "step", **common_entry_fields}
            ],
        },
    }
    (pt_root / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return pt_root / "scripts" / "validate_product_truth.py"


class TestReachability(unittest.TestCase):
    """Reachability: the pointer check must be provable through validate_product_truth.py's
    real CLI entry point, not merely through a direct call to _check_pointers()."""

    def test_uxp_700c_1_reachable_from_entry_point(self):
        # covers: UXP-700c-1
        # angle: reachability
        #
        # completion_manifest.reachability_entry_point_answer:
        #   result: resolved
        #   entry_point: "python docs/product-truth/scripts/validate_product_truth.py
        #     (CLI via subprocess, main() guarded by if __name__ == '__main__':)."
        #   This is the SAME, already-shipped entry point validate_product_truth.py has
        #   always had (see its own `if __name__ == "__main__": sys.exit(main())`
        #   footer). UXP-700c-1 extends that existing script with a new _check_*
        #   helper per architect-review's explicit instruction ("extension ... rather
        #   than a parallel checker"); it does not introduce a second CLI. Category 1
        #   of the resolution order (a CLI script with a main() guarded by
        #   `if __name__ == "__main__":`) is therefore the correct, and only, entry
        #   point to pin — not an inner helper reached by import.
        #
        # REQUIRED: invoke the production entry point as a subprocess and assert the
        # new pointer-resolution behaviour actually occurs in the real process's own
        # output and exit code — not by importing _check_pointers and calling it
        # directly (that is what TestCheckPointersDirect / TestCheckPointersSeam do;
        # this test proves those functions are actually wired into main()).
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            cli_path = _build_minimal_cli_store(tmp)

            result = subprocess.run(
                [sys.executable, str(cli_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )

        combined = (result.stdout + result.stderr).lower()

        self.assertNotEqual(
            result.returncode,
            0,
            "a store containing one broken AC pointer must exit non-zero via the real "
            f"CLI; stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertIn(
            "fixture-product/cli-journey",
            combined,
            "the CLI's broken-pointer report must name the holder artifact (the flow)",
        )
        self.assertIn(
            "checkout", combined, "the CLI's broken-pointer report must name the position (step id)"
        )
        self.assertIn(
            "ac-ghost-1",
            combined,
            "the CLI's broken-pointer report must name the target that did not resolve",
        )
        self.assertIn(
            "resolved 1",
            combined,
            "the run must state how many pointers it resolved (1: only AC-REAL-1 "
            "resolves) — this is what distinguishes a run that resolved one pointer "
            "from a run that resolved none",
        )


if __name__ == "__main__":
    unittest.main()
