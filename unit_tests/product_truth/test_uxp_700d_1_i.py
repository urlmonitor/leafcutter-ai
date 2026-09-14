"""
MODULE: test_uxp_700d_1_i
GOAL: Pin the varying-population boundary UXP-700d-1-i exists to catch: a newly added
    example journey must be excluded from the project's own record by WHERE it lives
    (the product-root directory it was written under), not by any list of artifact
    names/ids that would need to be hand-edited every time a new example artifact
    ships. The AC's own test_rationale names the exact failure mode this guards
    against: "A hardcoded exclusion list satisfies every clause of UXP-700d-1 against
    today's ten mockups and three flows, and then silently stops working the first
    time someone adds an example."
BUSINESS CONTEXT: UXP-700d-1-i depends on UXP-700d-1 ("Expects From" in the ticket:
    AC UXP-700d-1, contract "The ownership predicate whose derivation this record
    proves"). UXP-700d-1 is still work_status: todo in this repo (see
    changelogs/2026-09-07-1710-the-example-plant-shop-stops-being-offered-as-work-you-
    could-pick-up.md, which explicitly held "the product-root ownership module for
    UXP-700d-1" for a follow-up commit). This mirrors UXP-700b-3-i's own situation
    exactly (see unit_tests/product_truth/test_uxp_700b_3_i.py's docstring: its
    prerequisites were "all still work_status: todo in this repo" too) — this file
    follows that same precedent and invents the not-yet-built module's contract below,
    for python-coder to satisfy.

    Precedent for the naming convention used below: scripts/ac_store/scan_ac_store.py
    already ships an analogous (but content-field-based, not path-based) separation for
    the AC/work store — `_is_example_content()` and a `set_aside_count` JSON field
    (UXP-700d-2, see scan_ac_store.py's own module docstring/changelog entries). This
    file reuses the `set_aside_count` name for the product-truth (flows) side to keep
    the vocabulary for "artifacts set aside as example content" consistent across both
    stores, per UXP-700d-1's `delivers_to` note that its predicate is meant to be
    reused by sibling tickets.

ARCHITECTURE: Targets a NEW module this ticket (together with its prerequisite
    UXP-700d-1) adds: docs/product-truth/scripts/product_ownership.py. It does not
    exist yet — every test below is expected to fail (ImportError / file-not-found
    subprocess exit) until python-coder creates it. Its expected contract:

        EXAMPLE_PRODUCT: str = "fern-and-fig"
            The single constant naming the example product's root. This is NOT a list
            of artifact ids/names — ownership is decided by comparing an artifact's
            `component` field (the directory segment it lives under, e.g.
            `flows/fern-and-fig/x.flow.json` -> component "fern-and-fig") against this
            one constant. Adding a new flow under that same directory must change
            nothing else in this module for the new flow to be recognised as an example
            artifact.

        def is_example_component(component: str | None) -> bool
            True iff `component == EXAMPLE_PRODUCT`.

        def own_record_flows(flows: dict) -> dict
            Given {flow_id -> flow_dict} (the shape generate_product_truth.load_flows()
            returns), return the subset belonging to the project's OWN record: every
            flow whose component is NOT the example product's root.

        def flows_by_product(flows: dict, product: str) -> dict
            Return the subset of `flows` whose component == `product` — how the
            example product's journeys are retrieved when "asked for by name".

        def set_aside_count(flows: dict) -> int
            len(flows_by_product(flows, EXAMPLE_PRODUCT)) — the stated count of flow
            artifacts set aside as example content.

        CLI: `python product_ownership.py --store <product-truth-root> [--product NAME]`
            Without --product: loads flows via generate_product_truth.load_flows()
            (after pointing its STORE at --store) and prints one line of JSON to
            stdout: {"own_record_count": N, "set_aside_count": M}. Exits 0.
            With --product NAME: prints {"product": NAME, "flow_ids": [...]} to
            stdout. Exits 0 when flow_ids is non-empty, 1 when it is empty — the
            lookup's result is consumed in the process's own exit code, not merely
            printed, per the reachability angle's requirement.

    Test-file layout:
      * TestOwnRecordExcludesNewExampleArtifact — angle: seam. Pipes the REAL
        generate_product_truth.load_flows() producer's on-disk output (a fixture
        store built from scratch in a tempdir, extended with ONE new fern-and-fig
        flow file after the "before" read) into the REAL own_record_flows() /
        flows_by_product() consumers — no fixture is a hand-typed in-memory dict
        that skips the on-disk round trip.
      * TestSetAsideCountRisesByOne — angle: seam. Same real round trip, proving
        set_aside_count() rises by exactly one when exactly one further example
        flow file is added on disk, with no code/config edit in between the two
        reads.
      * TestReachability — angle: reachability. Runs the REAL
        docs/product-truth/scripts/product_ownership.py CLI (this ticket's own,
        new entry point) as a subprocess against a fixture store built from
        scratch in a tempdir, and asserts the behaviour is visible in the real
        process's own stdout and exit code — not by importing the module's
        functions and calling them directly (that is what the two seam test
        classes above do).

        completion_manifest.reachability_entry_point_answer:
          result: resolved
          entry_point: "python docs/product-truth/scripts/product_ownership.py
            --store <dir> [--product NAME] (CLI via subprocess, main() guarded by
            if __name__ == '__main__':)."
          This ticket's own contract (see ARCHITECTURE above) requires python-coder
          to build this CLI as the module's production entry point — there is no
          pre-existing pre-commit hook, slash command, or workflow step to attach
          to, and UXP-700d-1 (this ticket's prerequisite) is itself still
          work_status: todo, so no other caller exists yet either. Category 1 of
          the resolution order (a CLI script with a main() guarded by
          `if __name__ == "__main__":`) is therefore the correct entry point to
          pin, not an inner helper reached by import.

        completion_manifest.cross_layer_seam_answer:
          result: covered
          producing_side: "generate_product_truth.load_flows() reading real
            *.flow.json files from disk (the producer side of the product-truth
            flows seam)."
          consuming_side: "product_ownership.own_record_flows() /
            flows_by_product() / set_aside_count() (the new predicate consumer
            this ticket adds)."
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# The scripts directory is not on the default path; add it so we can import,
# mirroring unit_tests/test_generate_product_truth_idempotency.py's and
# unit_tests/product_truth/test_uxp_700c_1.py's convention for this same
# docs/product-truth/scripts location.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "docs" / "product-truth" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_product_truth as gpt  # noqa: E402

_CLI_PATH = _SCRIPTS_DIR / "product_ownership.py"


# --------------------------------------------------------------------------- #
# Fixture builders (mirrors test_uxp_700c_1.py's _step/_base_flow/_write_flow
# convention for this same store shape).
# --------------------------------------------------------------------------- #
def _flow(flow_id: str) -> dict:
    component = flow_id.split("/", 1)[0]
    return {
        "id": flow_id,
        "component": component,
        "name": flow_id,
        "summary": "fixture flow for UXP-700d-1-i ownership tests",
        "kind": "user",
        "source": "mock",
        "status": "active",
        "readiness": "draft",
        "version": 1,
        "entities": [],
        "steps": [
            {
                "id": "browse",
                "label": "browse",
                "human": "the actor performs browse",
                "order": 1,
                "implements": [],
            }
        ],
        "branches": [],
    }


def _write_flow(flows_dir: Path, flow: dict) -> None:
    component_dir = flows_dir / flow["component"]
    component_dir.mkdir(parents=True, exist_ok=True)
    name = flow["id"].split("/", 1)[1]
    (component_dir / f"{name}.flow.json").write_text(
        json.dumps(flow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


class TestOwnRecordExcludesNewExampleArtifact(unittest.TestCase):
    """Seam: the REAL load_flows() producer piped into the REAL own_record_flows() /
    flows_by_product() consumers, proving a NEWLY added example journey is excluded
    from the project's own record without any list edit, while remaining reachable
    by product name."""

    def test_new_example_journey_is_absent_from_own_record_and_present_by_name(self):
        # covers: UXP-700d-1-i
        # angle: seam
        # AC-1: the new journey is absent from it, and no list of artifact names was
        #       edited to make that so
        # AC-2: the new journey is returned when the example product is asked for by
        #       name
        import product_ownership as po  # noqa: E402  (import expected to fail until implemented)

        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            flows_dir = tmp / "flows"
            _write_flow(flows_dir, _flow("leafcutter/own-flow"))
            _write_flow(flows_dir, _flow("fern-and-fig/existing-journey"))

            original_store = gpt.STORE
            gpt.STORE = tmp
            try:
                flows_before, _paths = gpt.load_flows()

                # Sanity baseline before the new artifact is added.
                own_before = po.own_record_flows(flows_before)
                self.assertIn("leafcutter/own-flow", own_before)
                self.assertNotIn("fern-and-fig/existing-journey", own_before)

                # A new example journey is added under the example product root.
                # NOTHING besides this new data file changes — no list, no config.
                _write_flow(flows_dir, _flow("fern-and-fig/new-journey"))

                flows_after, _paths2 = gpt.load_flows()
                own_after = po.own_record_flows(flows_after)
                example_after = po.flows_by_product(flows_after, po.EXAMPLE_PRODUCT)
            finally:
                gpt.STORE = original_store

        self.assertNotIn(
            "fern-and-fig/new-journey",
            own_after,
            "a newly added example journey must be absent from the project's own "
            "record without any exclusion-list edit",
        )
        self.assertIn(
            "fern-and-fig/new-journey",
            example_after,
            "the newly added example journey must still be returned when the "
            "example product is asked for by name",
        )
        self.assertIn(
            "leafcutter/own-flow",
            own_after,
            "the project's own, pre-existing flow must remain in its own record",
        )


class TestSetAsideCountRisesByOne(unittest.TestCase):
    """Seam: the REAL load_flows() producer piped into the REAL set_aside_count()
    consumer, proving the stated count rises by exactly one when exactly one further
    example artifact is added on disk."""

    def test_set_aside_count_rises_by_one_when_an_example_artifact_is_added(self):
        # covers: UXP-700d-1-i
        # angle: seam
        # AC-3: the stated count of artifacts set aside as example content is one
        #       greater than before the journey was added
        import product_ownership as po  # noqa: E402  (import expected to fail until implemented)

        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            flows_dir = tmp / "flows"
            _write_flow(flows_dir, _flow("leafcutter/own-flow"))
            _write_flow(flows_dir, _flow("fern-and-fig/existing-journey"))

            original_store = gpt.STORE
            gpt.STORE = tmp
            try:
                flows_before, _paths = gpt.load_flows()
                count_before = po.set_aside_count(flows_before)

                _write_flow(flows_dir, _flow("fern-and-fig/new-journey"))

                flows_after, _paths2 = gpt.load_flows()
                count_after = po.set_aside_count(flows_after)
            finally:
                gpt.STORE = original_store

        self.assertEqual(
            count_after,
            count_before + 1,
            "adding exactly one further example artifact must raise the stated "
            f"set-aside count by exactly one (before={count_before}, after={count_after})",
        )


def _build_fixture_store(tmp: Path) -> None:
    """Build a minimal, self-contained product-truth store (flows only) inside
    `tmp`, with one project-owned flow and one example-product flow."""
    flows_dir = tmp / "flows"
    _write_flow(flows_dir, _flow("leafcutter/own-flow"))
    _write_flow(flows_dir, _flow("fern-and-fig/existing-journey"))


class TestReachability(unittest.TestCase):
    """Reachability: the ownership predicate must be provable through its real CLI
    entry point, not merely through a direct import of own_record_flows() /
    flows_by_product() / set_aside_count()."""

    def test_uxp_700d_1_i_reachable_from_entry_point(self):
        # covers: UXP-700d-1-i
        # angle: reachability
        #
        # completion_manifest.reachability_entry_point_answer:
        #   result: resolved
        #   entry_point: "python docs/product-truth/scripts/product_ownership.py
        #     --store <dir> [--product NAME] (CLI via subprocess, main() guarded by
        #     if __name__ == '__main__':)."
        #   See the module docstring above for the full resolution rationale — this
        #   is a brand-new CLI this ticket's own contract requires python-coder to
        #   build (its prerequisite, UXP-700d-1, is itself still work_status: todo,
        #   so there is no pre-existing hook/command/workflow step to attach to).
        #
        # REQUIRED: invoke the production entry point as a subprocess and assert the
        # new behaviour is visible in the real process's own stdout and exit code —
        # not by importing own_record_flows()/set_aside_count() directly (that is
        # what the two seam TestCase classes above do; this test proves those
        # functions are actually wired into a real, runnable CLI).
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            _build_fixture_store(tmp)

            report_result = subprocess.run(
                [sys.executable, str(_CLI_PATH), "--store", str(tmp)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            named_result = subprocess.run(
                [sys.executable, str(_CLI_PATH), "--store", str(tmp), "--product", "fern-and-fig"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            absent_result = subprocess.run(
                [
                    sys.executable,
                    str(_CLI_PATH),
                    "--store",
                    str(tmp),
                    "--product",
                    "totally-nonexistent-product",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

        self.assertEqual(
            report_result.returncode,
            0,
            f"the default report must exit 0; stdout={report_result.stdout!r} "
            f"stderr={report_result.stderr!r}",
        )
        report_payload = json.loads(report_result.stdout)
        self.assertEqual(report_payload["own_record_count"], 1)
        self.assertEqual(report_payload["set_aside_count"], 1)

        self.assertEqual(
            named_result.returncode,
            0,
            f"a product with matching flows must exit 0; stdout={named_result.stdout!r} "
            f"stderr={named_result.stderr!r}",
        )
        named_payload = json.loads(named_result.stdout)
        self.assertIn("fern-and-fig/existing-journey", named_payload["flow_ids"])

        self.assertNotEqual(
            absent_result.returncode,
            0,
            "a product name that matches no flow must exit non-zero — the lookup's "
            "emptiness must be consumed in the process's own exit code, not merely "
            f"printed; stdout={absent_result.stdout!r} stderr={absent_result.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
