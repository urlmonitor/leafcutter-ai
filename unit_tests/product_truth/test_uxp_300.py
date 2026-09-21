"""
MODULE: unit_tests/product_truth/test_uxp_300.py
COVERS: UXP-300 — Product-truth artifacts live in docs/product-truth with one
        canonical dataset per entity per component.

GOAL: Failing (red) test stubs for the four checks the AC's Gherkin demands:
    1. every artifact the index registers resolves under a declared store
       directory (flows/, mock-data/, mockups/);
    2. no entity is carried by two mock-data artifacts within the same
       component (extend, never duplicate);
    3. the same duplicate-canonical-dataset defect survives a real
       generate_product_truth.py (producer) -> validate_product_truth.py
       (consumer) round trip, not only a hand-placed validate-only fixture;
    4. the DEPLOYED copy of validate_product_truth.py both (a) reports a
       real, non-hardcoded positive count against real data, and (b) fails
       *informatively* rather than with a raw traceback against an empty /
       freshly-deployed store with no data yet authored;
    5. the real CLI entry point (validate_product_truth.py, invoked as a
       subprocess — the same way the registered pre-commit hook invokes it,
       see .pre-commit-config.yaml's "Product-Truth Store Validation" entry)
       is reachable and its exit code is genuinely consumed as a pass/fail
       signal, not merely printed.

REAL-ARTIFACT DISCIPLINE (2h.2 / repo README §4-5): every fixture here is
    either (a) a verbatim copy of the real committed docs/product-truth +
    docs/acceptance-criteria trees (shutil.copytree of the actual files), or
    (b) a new *.mock.json file written through json.dump conforming to the
    real mock-data.schema.json's required-field contract, never a bare
    hand-typed string blob standing in for a serialized artifact. Every
    check is exercised by running the REAL scripts as a subprocess against
    those real trees — never by importing an internal function and calling
    it directly.

RED BASELINE (as of authoring, empirically confirmed against the current
    tree — see the docstring on each test for the exact captured failure):
    - test_1: no check exists for artifact['path'] resolving under a
      declared store directory; AssertionError (expected substring absent).
    - test_2: generate_product_truth.py's build_by_entity() silently keeps
      the LAST mock-data file that declares a given entity for a component
      (dict overwrite) and validate_product_truth.py has no check that
      flags the earlier one as an unreported duplicate; AssertionError.
    - test_3: same defect, exercised through the real generator's write of
      index.json rather than a hand-placed index; AssertionError.
    - test_4a: currently green already (glob-deploy already works) — kept
      as a locked-down regression, not the red leg of this file.
    - test_4b: empirically confirmed today to raise a raw, uncaught
      FileNotFoundError traceback from _load_json(STORE / "index.json")
      when the deployed store has no data — see generate_product_truth.py
      _load_json and validate_product_truth.py main(); this test currently
      fails because "Traceback (most recent call last):" IS present in the
      captured output.
    - test_5: same underlying defect as test_2, asserted via the CLI's
      returncode specifically (control-flow consumption, not string
      matching); AssertionError (returncode is 0 today; must become
      non-zero).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PT_SRC = _REPO_ROOT / "docs" / "product-truth"
_AC_STORE_SRC = _REPO_ROOT / "docs" / "acceptance-criteria"

_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_SUBPROCESS_TIMEOUT_SECONDS = 90

# --------------------------------------------------------------------------- #
# Expected-message contracts python-coder must implement.
# --------------------------------------------------------------------------- #
_EXPECTED_PATH_SUBSTR_PREFIX = "is outside the declared store directories (flows/, mock-data/, mockups/)"
_EXPECTED_DUP_ENTITY = "Plant"
_EXPECTED_DUP_COMPONENT = "ux-prototyping"
_EXPECTED_DUP_EXISTING_ID = "fern-and-fig/catalog"
_EXPECTED_DUP_NEW_ID = "fern-and-fig/catalog-dup"
_EXPECTED_DUP_SUBSTR = (
    f"entity '{_EXPECTED_DUP_ENTITY}' already has a canonical mock-data artifact "
    f"for component '{_EXPECTED_DUP_COMPONENT}': '{_EXPECTED_DUP_EXISTING_ID}'; "
    f"'{_EXPECTED_DUP_NEW_ID}' is a duplicate"
)


def _copy_store(dest_docs_dir: Path, *, include_ac_store: bool = True) -> Path:
    """Copy the REAL committed product-truth (and optionally AC) trees.

    Preserves the sibling relationship AC_STORE = STORE.parent / "acceptance-criteria"
    that validate_product_truth.py relies on (see its module-level AC_STORE assignment).
    Returns the path to the copied product-truth store root.
    """
    dest_docs_dir.mkdir(parents=True, exist_ok=True)
    pt_dest = dest_docs_dir / "product-truth"
    shutil.copytree(_PT_SRC, pt_dest)
    if include_ac_store:
        shutil.copytree(_AC_STORE_SRC, dest_docs_dir / "acceptance-criteria")
    return pt_dest


def _run_validator(store: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(store / "scripts" / "validate_product_truth.py")],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _run_generator(store: Path, *extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(store / "scripts" / "generate_product_truth.py"), *extra_args],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _write_duplicate_plant_mock(store: Path) -> None:
    """Write a second mock-data artifact for the ux-prototyping component that
    ALSO declares the 'Plant' entity already canonically owned by
    mock-data/fern-and-fig/catalog.mock.json — the exact "extend, never
    duplicate" violation UXP-300's AC forbids.

    Written via json.dump against the real mock-data.schema.json's required
    fields (id, component, status, readiness, entities) — not a hand-typed
    JSON string — per the Fixture Authenticity Rule.
    """
    dest = store / "mock-data" / "fern-and-fig" / "catalog-dup.mock.json"
    payload = {
        "id": _EXPECTED_DUP_NEW_ID,
        "component": _EXPECTED_DUP_COMPONENT,
        "status": "active",
        "readiness": "draft",
        "entities": {
            _EXPECTED_DUP_ENTITY: {
                "fields": {"id": "string", "name": "string"},
                "records": [{"id": "plant-dup-1", "name": "Duplicate Plant"}],
            }
        },
    }
    with dest.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


class TestArtifactPathsResolveUnderDeclaredStoreDirectories(unittest.TestCase):
    """AC-1 / test_spec #1 (angle: real_artifact)."""

    def test_every_registered_artifact_resolves_under_a_declared_store_directory(self) -> None:
        # covers: UXP-300
        # angle: real_artifact
        """A registered artifact whose index.json 'path' escapes flows/,
        mock-data/, mockups/ must be reported, not silently accepted.

        RED baseline: no such check exists yet in validate_product_truth.py
        (_check_index only compares status/readiness/version fields — the
        'path' field is never examined). Confirmed empirically: mutating an
        existing artifact's stored path produces no new error today.
        """
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp) / "docs"
            store = _copy_store(docs_dir, include_ac_store=False)

            index_path = store / "index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertTrue(index["artifacts"], "fixture store must have at least one artifact")

            target = index["artifacts"][0]
            artifact_id = target["id"]
            bogus_path = "not-a-declared-directory/bogus.json"
            target["path"] = bogus_path
            index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

            proc = _run_validator(store)
            output = proc.stdout + proc.stderr

            expected = (
                f"[index] artifact '{artifact_id}' path '{bogus_path}' "
                f"{_EXPECTED_PATH_SUBSTR_PREFIX}"
            )
            self.assertIn(
                expected,
                output,
                "validator must report an artifact whose registered path escapes "
                f"the declared store directories; got:\n{output}",
            )
            self.assertNotEqual(
                proc.returncode,
                0,
                "an out-of-tree artifact path must fail the validator, not merely warn",
            )


class TestOneCanonicalDatasetPerEntityPerComponent(unittest.TestCase):
    """AC-2 / test_spec #2 (angle: real_artifact)."""

    def test_one_canonical_dataset_per_entity_per_component(self) -> None:
        # covers: UXP-300
        # angle: real_artifact
        """A second mock-data artifact declaring an entity already owned by
        another artifact in the SAME component must be rejected, not merged.

        RED baseline: build_by_entity() in generate_product_truth.py assigns
        `bucket(entity)["canonical_mock_data"][component] = mock["id"]` —
        a plain dict write, so the second (alphabetically later) mock file
        silently becomes canonical with no error raised anywhere. Confirmed
        empirically: validate_product_truth.py exits 0 in this scenario today.
        """
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp) / "docs"
            store = _copy_store(docs_dir, include_ac_store=False)
            _write_duplicate_plant_mock(store)

            proc = _run_validator(store)
            output = proc.stdout + proc.stderr

            self.assertIn(
                _EXPECTED_DUP_SUBSTR,
                output,
                "validator must report the duplicate canonical mock-data artifact "
                f"for the same entity+component; got:\n{output}",
            )
            self.assertNotEqual(
                proc.returncode,
                0,
                "a duplicated canonical dataset must fail the validator",
            )


class TestDuplicateSurvivesTheRealGeneratorConsumerSeam(unittest.TestCase):
    """AC-2 / test_spec #3 (angle: seam) — Rule 3 cross-layer seam.

    Producer: generate_product_truth.py, which is the SINGLE WRITER of
    index.json's by_entity.canonical_mock_data map.
    Consumer: validate_product_truth.py, which must flag an ambiguous
    canonical dataset once it has actually been written to the real,
    on-disk index.json — not only when validate is run against a
    hand-placed fixture that never went through the generator.
    """

    def test_flow_to_ac_is_authored_and_the_reverse_edge_is_derived(self) -> None:
        # covers: UXP-300
        # angle: seam
        """Pipe the REAL generator's written index.json into the REAL
        validator and require the duplicate-canonical-dataset defect to be
        caught post-write, proving the fix cannot live only inside a
        validate-only code path that a differently-shaped generator write
        could still slip past.

        RED baseline: empirically confirmed today — generate_product_truth.py
        runs to completion (exit 0, 'OK: product-truth derived data written')
        and silently picks one mock as canonical; the subsequent validate run
        also exits 0 with no mention of the duplicate.
        """
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp) / "docs"
            store = _copy_store(docs_dir, include_ac_store=True)
            _write_duplicate_plant_mock(store)

            gen_proc = _run_generator(store)
            self.assertEqual(
                gen_proc.returncode,
                0,
                f"the real generator (producer) must complete its write step:\n"
                f"{gen_proc.stdout}{gen_proc.stderr}",
            )

            index = json.loads((store / "index.json").read_text(encoding="utf-8"))
            self.assertIn(_EXPECTED_DUP_ENTITY, index.get("by_entity", {}))

            val_proc = _run_validator(store)
            output = val_proc.stdout + val_proc.stderr

            self.assertIn(
                _EXPECTED_DUP_SUBSTR,
                output,
                "the real validator, reading the real generator's freshly-written "
                f"index.json, must surface the duplicate canonical dataset; got:\n{output}",
            )
            self.assertNotEqual(val_proc.returncode, 0)


class TestTheStorePassesItsOwnValidator(unittest.TestCase):
    """AC-4 / test_spec #4 (angle: deployed).

    Runs build_phases.build_product_truth() — the phase scripts/build.py's
    top-level phase list invokes for "Product-truth tooling" — into an
    isolated temp target, then exercises the DEPLOYED copy of
    validate_product_truth.py, not the source-tree one. A source-tree-only
    read is structurally blind to a deploy-manifest gap (BP-1100f-2).
    """

    def setUp(self) -> None:
        from build_phases import build_product_truth  # noqa: PLC0415

        self._build_product_truth = build_product_truth
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _deploy(self) -> Path:
        target = Path(self._tmp.name) / self.id().rsplit(".", 1)[-1]
        target.mkdir(parents=True, exist_ok=True)
        written = self._build_product_truth(target, {"output_root": ".leafcutter"}, dry_run=False, force=True)
        self.assertGreater(written, 0, "build_product_truth must actually deploy files")
        # Copy the real AC store alongside the deployed product-truth tree,
        # preserving the AC_STORE = STORE.parent / "acceptance-criteria"
        # sibling relationship validate_product_truth.py relies on. Without
        # this, every flow node's `implements` reference resolves to
        # "not found", cascading into unrelated impl_status-mismatch errors
        # that make the validator exit non-zero for reasons that have
        # nothing to do with what each test below actually proves.
        shutil.copytree(_AC_STORE_SRC, target / "docs" / "acceptance-criteria")
        return target / "docs" / "product-truth"

    def test_the_store_passes_its_own_validator(self) -> None:
        # covers: UXP-300
        # angle: deployed
        """(a) Against a DEPLOYED copy carrying the real committed data, the
        validator exits zero and states a REAL, non-hardcoded positive count
        (README §8: "a check that examined nothing must not look like a
        check that found nothing" — vary the population, require the
        number to move).
        """
        deployed_store = self._deploy()
        # build_product_truth() deliberately deploys only scripts/ + schemas/
        # (never the project-authored data) — copy the real DATA in too, so
        # the deployed copy has something real to examine.
        for name in ("flows", "mock-data", "mockups", "classifier", "evals", "index.json"):
            src = _PT_SRC / name
            dst = deployed_store / name
            if src.is_dir():
                # dirs_exist_ok=True: build_product_truth() now scaffolds
                # flows/, mock-data/, and mockups/ itself on a fresh install
                # (UXP-700a-1-ii), so these destinations already exist by
                # the time this loop runs; only their *contents* are new.
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy(src, dst)

        real_flow_count = len(list((_PT_SRC / "flows").rglob("*.flow.json")))
        real_mock_count = len(list((_PT_SRC / "mock-data").rglob("*.mock.json")))
        self.assertGreater(real_flow_count, 0, "fixture sanity: repo must have real flows")

        proc = _run_validator(deployed_store)
        output = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, f"deployed validator must pass against real data:\n{output}")
        self.assertIn(f"OK: {real_flow_count} flows, {real_mock_count} mock-data,", output)

    def test_deployed_validator_degrades_informatively_on_an_empty_store(self) -> None:
        # covers: UXP-300
        # angle: deployed
        """(b) Against a DEPLOYED copy with NO data yet authored (the state
        of a freshly-built consumer project before anyone has written a
        flow/mock/mockup), the validator must fail *informatively* — never
        with a raw uncaught traceback — so an empty store is distinguishable
        from a real pass rather than indistinguishable from a crash.

        RED baseline: empirically confirmed today. Deploying only
        scripts/+schemas/ (build_product_truth's real, current output) and
        running validate_product_truth.py against it raises an uncaught
        FileNotFoundError from _load_json(STORE / "index.json") — a raw
        Python traceback appears in stderr instead of a clean message.
        """
        deployed_store = self._deploy()

        proc = _run_validator(deployed_store)
        output = proc.stdout + proc.stderr

        self.assertNotIn(
            "Traceback (most recent call last):",
            output,
            "an empty/undeployed product-truth store must fail informatively, "
            f"not with a raw uncaught traceback; got:\n{output}",
        )
        self.assertNotEqual(proc.returncode, 0, "an empty store must not silently report success")


class TestUxp300ReachableFromEntryPoint(unittest.TestCase):
    """test_spec #5 (angle: reachability).

    Entry-point resolution (per the Reachability Entry-Point Resolution
    procedure): the AC authored no test_spec entry naming a surface for this
    test. Step 1 of the resolution procedure was walked against the real
    code: validate_product_truth.py is a CLI script under
    docs/product-truth/scripts/ with a main() guarded by
    `if __name__ == "__main__": sys.exit(main())` and its own argparse
    parser (--quiet) — Step 1.1 (CLI script) applies and takes priority over
    Step 1.2, even though the same script is ALSO wired as a pre-commit hook
    entry in .pre-commit-config.yaml ("Product-Truth Store Validation":
    `python .leafcutter/scripts/commit_guardian/run_hook.py
    docs/product-truth/scripts/validate_product_truth.py --quiet`).
    Resolved entry point: `python docs/product-truth/scripts/validate_product_truth.py`
    invoked as a real subprocess.
    """

    def test_uxp_300_reachable_from_entry_point(self) -> None:
        # covers: UXP-300
        # angle: reachability
        """Invoke the REAL CLI entry point via subprocess against a real
        store carrying the duplicate-canonical-dataset defect, and assert
        the exit code specifically is what a real caller (the registered
        pre-commit hook, via run_hook.py) actually branches on — not merely
        that some diagnostic string appears in stdout.

        RED baseline: empirically confirmed — returncode is 0 today for
        this scenario (no check exists), so the assertNotEqual below fails.

        include_ac_store=True is deliberate here (unlike the two
        real_artifact tests above): without the real AC store present,
        every flow node's `implements` reference resolves to "not found",
        which cascades into unrelated impl_status-mismatch errors and makes
        the validator exit non-zero for reasons that have nothing to do with
        the duplicate-dataset defect under test — an accidental-pass trap
        that would make this assertion true regardless of whether
        python-coder implements anything. Copying the real AC store isolates
        the single signal this test exists to prove.
        """
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp) / "docs"
            store = _copy_store(docs_dir, include_ac_store=True)
            _write_duplicate_plant_mock(store)

            proc = _run_validator(store)

            # This is the exact signal a real caller consumes in control flow:
            # run_hook.py / pre-commit treats a non-zero exit as "block the
            # commit". Asserting on returncode alone (not stdout content)
            # proves this is genuinely reachable production behavior, not an
            # import of an internal function.
            self.assertNotEqual(
                proc.returncode,
                0,
                "the real CLI entry point must exit non-zero when the store "
                f"carries a duplicated canonical mock-data artifact; got:\n"
                f"{proc.stdout}{proc.stderr}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
