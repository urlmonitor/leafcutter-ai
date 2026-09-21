"""
MODULE: test_uxp_700b_1_ii
GOAL: Pin the mixed-emptiness case for the record's checker
    (docs/product-truth/scripts/validate_product_truth.py): a store holding three
    journeys (flows), zero example datasets (mock-data) and zero screens (mockups)
    must have its report name ONLY the empty artifact types (mock-data, mockups) —
    never journeys, which is populated — and its reported outcome must NOT be the
    outcome reserved for a record that was checked and found sound.
BUSINESS CONTEXT: UXP-700b-1 (this record's own prerequisite, still work_status:
    todo in this repo at authoring time) establishes that the checker must
    distinguish "checked and sound" from "nothing was there to check", and must
    name, per artifact type, which types it read zero records for. An
    implementation that only distinguishes "wholly empty" from "not wholly empty"
    passes UXP-700b-1 in full while still hiding the state this project's OWN
    store is actually in today: docs/product-truth notes on this AC record that
    10 of 10 registered mockups belong to the example product, so the project's
    REAL screen population is zero even though flows/journeys are populated.
    UXP-700b-1-ii is the case that catches an implementation that rounds a
    partially-empty store up to a clean pass.

    DIRECTLY OBSERVED (2026-09-09, this repo, this ticket's test-writer pass):
    `validate_product_truth.py`'s current main() reports only
    "OK: N flows, N mock-data, N mockups, ... (%d warnings)" and exit 0 for ANY
    combination of nonzero/zero counts — there is no per-type zero-record naming
    and no machine-readable outcome distinct from that prose. That is exactly the
    defect UXP-700b-1 / UXP-700b-1-ii exist to close.

ARCHITECTURE / THE CONTRACT THIS TEST FILE SPECIFIES:
    UXP-700b-1 (the per-type zero-record reporting mechanism this record's
    "Agent Contracts > Expects From" names as its prerequisite) is not yet
    implemented anywhere in this repo — there is no prior test-writer output to
    follow for it. As the test-writer for the mixed-store nuance (UXP-700b-1-ii),
    this file therefore specifies the minimal machine-readable wire contract
    python-coder must add to validate_product_truth.py's main():

      On a run that completes with zero schema/derived-data ERRORS (the shape
      this ticket's fixture always produces), main() must print, as the LAST
      non-empty line of STDOUT (stdout only — logger output goes to stderr via
      the existing logging.basicConfig call, so this line is not mixed with the
      existing prose), a single JSON object:

          {"outcome": "<value>", "empty_types": ["<type>", ...]}

      - "empty_types" lists a subset of {"flows", "mock-data", "mockups"} — the
        canonical type identifiers this module already uses (OUTCOME_BY_COMBO,
        the mock/mockup/flow directory names) — naming exactly the artifact
        types for which zero records were read. A type with at least one record
        MUST NOT appear, even when other types are empty (this is the boundary
        UXP-700b-1-ii adds on top of UXP-700b-1's wholly-empty case).
      - "outcome" DOES equal the literal "checked-and-sound" here: AC-3 was
        amended 2026-09-10 (KI-ACD-20260909-2130) so that partial emptiness is
        reported in "empty_types" without withholding the clean pass. This
        test file does not pin what
        "outcome" DOES equal in the mixed case — UXP-700b-1's own outcome
        vocabulary (checked-and-sound / nothing-examined / degraded / failed)
        is that record's contract, not this one's; UXP-700b-1-ii's own AC-3
        only requires inequality with the sound outcome.

    Fixture: a temporary, schema-valid product-truth store is built from
    scratch (three minimal flow.json fixtures, empty mock-data/ and mockups/
    directories, real schemas copied verbatim) and the REAL generator is run
    against it first (subprocess) to derive a self-consistent index.json via
    the ACTUAL production single-writer — mirroring
    unit_tests/test_generate_product_truth_idempotency.py's fixture-building
    convention for this same docs/product-truth/scripts location, but reached
    over subprocess (both scripts' real CLI entry points) rather than direct
    monkeypatched import, so this is a true generator -> validator seam test
    (Rule 3) as well as a reachability test for the validator's own CLI.

    completion_manifest.cross_layer_seam_answer:
      result: covered
      producing_side: "docs/product-truth/scripts/generate_product_truth.py main() (real CLI subprocess) — writes index.json"
      consuming_side: "docs/product-truth/scripts/validate_product_truth.py main() (real CLI subprocess) — reads index.json"
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PT_SRC = _REPO_ROOT / "docs" / "product-truth"
_SCRIPTS_SRC = _PT_SRC / "scripts"
_SCHEMAS_SRC = _PT_SRC / "schemas"


def _build_fixture(tmp: Path) -> Path:
    """Build a minimal, schema-valid product-truth store: three journeys
    (flows), zero example datasets (mock-data), zero screens (mockups) — the
    mixed-emptiness case UXP-700b-1-ii's AC names. Returns the fixture's own
    docs/product-truth root (tmp/docs/product-truth).

    Real production scripts and schemas are copied verbatim (Fixture
    Authenticity Rule — this fixture runs the ACTUAL generator/validator code,
    not a reimplementation of their logic).
    """
    store = tmp / "docs" / "product-truth"
    (store / "flows" / "test").mkdir(parents=True)
    (store / "mock-data").mkdir(parents=True)
    (store / "mockups").mkdir(parents=True)
    (store / "classifier").mkdir(parents=True)
    (store / "scripts").mkdir(parents=True)
    (tmp / "docs" / "acceptance-criteria").mkdir(parents=True)

    # build.py deploys scripts/ as a whole "*.py" glob, and both entry points
    # import sibling modules (product_truth_checks, product_truth_index_checks,
    # product_truth_derivations). Copy the whole set so this fixture is a real
    # install rather than two files that cannot import themselves.
    for _sibling in sorted(_SCRIPTS_SRC.glob("*.py")):
        shutil.copy2(_sibling, store / "scripts" / _sibling.name)
    shutil.copytree(_SCHEMAS_SRC, store / "schemas")

    # Empty classifier eval log — zero rows to check.
    (store / "classifier" / "eval.jsonl").write_text("", encoding="utf-8")

    # Three journeys (flows) — the POPULATED artifact type in this fixture.
    for n in range(1, 4):
        flow = {
            "id": f"test/journey-{n}",
            "component": "test",
            "name": f"Journey {n}",
            "summary": "Fixture journey for UXP-700b-1-ii's mixed-emptiness case.",
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
                    "human": "Do the thing.",
                    "order": 1,
                    "impl_status": "not_started",
                }
            ],
        }
        (store / "flows" / "test" / f"journey-{n}.flow.json").write_text(
            json.dumps(flow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    # mock-data/ and mockups/ are left empty — zero example datasets, zero screens.

    # Seed a minimal index.json. generate_product_truth.write_index() reads
    # this back and rebuilds by_component/by_entity/by_flow/by_ac from the
    # fixture's flows; it does not (re)populate "artifacts" from scratch, so
    # that key is deliberately left empty — this fixture makes no assertion
    # about it.
    index = {
        "artifacts": [],
        "entity_registry": [],
        "by_component": {},
        "by_entity": {},
        "by_flow": {},
        "by_ac": {},
    }
    (store / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    return store


def _run_pipeline(store: Path) -> subprocess.CompletedProcess:
    """Run the REAL generator, then the REAL validator, against the fixture —
    both via subprocess against their actual CLI entry points (each guarded by
    `if __name__ == "__main__":`). Returns the validator's CompletedProcess.
    """
    scripts_dir = store / "scripts"
    gen = subprocess.run(
        [sys.executable, str(scripts_dir / "generate_product_truth.py")],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if gen.returncode != 0:
        raise AssertionError(
            "fixture setup failed: the REAL generate_product_truth.py could not "
            f"derive index.json for the fixture store.\nstdout={gen.stdout}\n"
            f"stderr={gen.stderr}"
        )
    return subprocess.run(
        [sys.executable, str(scripts_dir / "validate_product_truth.py")],
        capture_output=True,
        text=True,
        timeout=30,
    )


def _parse_outcome_payload(stdout: str) -> dict:
    """Parse the final stdout line as the {'outcome', 'empty_types'} contract
    this test file specifies (see module docstring). Raises AssertionError
    (not a bare parse exception) with a message that names the missing
    contract, so a red run is diagnosable without reading this file.
    """
    lines = [line for line in stdout.strip().splitlines() if line.strip()]
    if not lines:
        raise AssertionError(
            "validate_product_truth.py produced no stdout output. Expected the "
            "final stdout line to be a JSON object "
            "{'outcome': <str>, 'empty_types': [<str>, ...]} reporting, per "
            "artifact type, which types had zero records read — see this test "
            "module's docstring for the exact contract. Not yet implemented "
            "(UXP-700b-1 / UXP-700b-1-ii)."
        )
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"final stdout line is not valid JSON: {lines[-1]!r} ({exc}). "
            "Expected {'outcome': <str>, 'empty_types': [<str>, ...]}."
        ) from None


class TestMixedStoreEmptyTypeNaming(unittest.TestCase):
    """UXP-700b-1-ii: three journeys, zero example data, zero screens — the
    report must name only the empty types."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp_dir = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp_dir.name)
        store = _build_fixture(tmp)
        cls.result = _run_pipeline(store)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp_dir.cleanup()

    def test_mixed_store_names_only_the_empty_artifact_types(self) -> None:
        # covers: UXP-700b-1-ii
        # angle: boundary
        # AC-1 / AC-2: with three journeys and zero example data / screens, the
        # report names example data (mock-data) and screens (mockups) as the
        # empty types, and does NOT name journeys (flows) — the populated type.
        payload = _parse_outcome_payload(self.result.stdout)
        empty_types = set(payload.get("empty_types", []))

        self.assertEqual(
            empty_types,
            {"mock-data", "mockups"},
            f"expected exactly {{'mock-data', 'mockups'}} named as empty types "
            f"(three journeys are populated and must not be named); got "
            f"{empty_types!r}. Full payload: {payload!r}. stderr={self.result.stderr}",
        )
        self.assertNotIn(
            "flows",
            empty_types,
            "journeys (flows) are populated in this fixture — the report must "
            "not name flows as an empty type",
        )

    def test_mixed_store_outcome_is_the_clean_pass_outcome(self) -> None:
        # covers: UXP-700b-1-ii
        # angle: criterion
        # AC-3 (AMENDED 2026-09-10, user decision, KI-ACD-20260909-2130): a
        # partially empty store DOES report the clean-pass outcome, because
        # everything it holds was checked and was sound. A record with
        # journeys but no screens or example data yet is young, not
        # defective. The clause this replaces asserted the opposite and
        # contradicted sibling UXP-700b-1-i, whose fixture is this same shape
        # and which asserts checked-and-sound; the contradiction was resolved
        # in -1-i's favour. What this AC uniquely pins is unaffected and is
        # asserted by the sibling test above: the report NAMES which types
        # read zero records. Emptiness is reported, not penalised.
        payload = _parse_outcome_payload(self.result.stdout)
        self.assertEqual(
            payload.get("outcome"),
            "checked-and-sound",
            "a store with three journeys but zero example data and zero "
            "screens holds nothing unchecked and nothing unsound, so it "
            f"reports the clean-pass outcome. Full payload: {payload!r}. "
            f"stderr={self.result.stderr}",
        )
        self.assertEqual(
            set(payload.get("empty_types", [])),
            {"mock-data", "mockups"},
            "the clean pass must not come at the cost of the emptiness "
            "report — which types read zero records is still named "
            f"alongside it. Full payload: {payload!r}",
        )


class TestReachability(unittest.TestCase):
    """Reachability: the mixed-store report must be provable through the
    validator's real CLI entry point (subprocess), not merely through a direct
    import/call of an internal helper function."""

    def test_uxp_700b_1_ii_reachable_from_entry_point(self) -> None:
        # covers: UXP-700b-1-ii
        # angle: reachability
        # REQUIRED: invoke the record's checker (validate_product_truth.py) as
        # a subprocess of its real CLI entry point (`if __name__ == "__main__":
        # sys.exit(main())`) against a fixture store built by the REAL
        # generator (also invoked as a subprocess), and assert the new
        # mixed-emptiness behaviour actually occurs in that process's own
        # stdout/exit code — not by importing and calling an inner function.
        #
        # completion_manifest.reachability_entry_point_answer:
        #   result: resolved
        #   entry_point: "python docs/product-truth/scripts/validate_product_truth.py
        #     (CLI via subprocess, main() guarded by
        #     if __name__ == '__main__': sys.exit(main()))"
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            store = _build_fixture(tmp)
            result = _run_pipeline(store)

        self.assertEqual(
            result.returncode,
            0,
            "the mixed-emptiness fixture has no schema/derived-data errors and "
            f"must still exit 0 (this is a reporting gap, not a failure "
            f"state). stdout={result.stdout} stderr={result.stderr}",
        )
        payload = _parse_outcome_payload(result.stdout)
        # The behaviour is "consumed": both halves of the AC must be present
        # together in the SAME real process run, not merely printed somewhere.
        self.assertEqual(set(payload.get("empty_types", [])), {"mock-data", "mockups"})
        # AC-3 amended 2026-09-10 (KI-ACD-20260909-2130): the clean pass is
        # reported and the emptiness is named alongside it, in the same line
        # of the same real process run. Previously asserted the negation,
        # which contradicted sibling UXP-700b-1-i over an identical store.
        self.assertEqual(payload.get("outcome"), "checked-and-sound")


if __name__ == "__main__":
    unittest.main(verbosity=2)
