"""
MODULE: test_uxp_700a_3
GOAL: Pin UXP-700a-3 -- "A newly installed record carries none of another
    project's content." A project that has never used the product-truth
    tooling must, after install: (AC-1) enumerate ZERO artifacts of every
    type (journeys, example data, screens); (AC-2) carry no artifact
    belonging to the tooling's own example product ("fern-and-fig") NOR to
    the tooling's own project record ("leafcutter") by default; and (AC-3)
    still let a person OBTAIN the example product by asking for it BY NAME,
    so the separation above is never achieved by deletion.
BUSINESS CONTEXT: Per this AC's own YAML notes (docs/acceptance-criteria/
    ux-prototyping/UXP-700-truthful-project-record/UXP-700a-3.yaml) and the
    architect-review sign-off on this ticket: AC-1/AC-2 ALREADY hold today --
    scripts/build_phases_product_truth.py's build_product_truth() only
    deploys scripts/*.py + schemas/*.json plus a write-if-absent EMPTY
    scaffold (UXP-700a-1). The real gap this AC closes is AC-3: there is
    currently NO way to obtain the example product's own worked example
    (flows/mock-data/mockups under fern-and-fig/ in the package's OWN
    docs/product-truth/ tree -- never deployed to a consumer by default) by
    asking for it by name.
IMPLEMENTATION CONTRACT (this file's red baseline; not yet implemented --
    python-coder must build to this contract, mirroring the --seed-docs /
    scripts/seed_project_docs.py precedent the architect-review comment on
    this ticket names explicitly):
      - A new script `scripts/seed_example_product.py`, exposing
        `seed_example_product(project_root: Path, product: str,
        dry_run: bool = False) -> dict[str, list[str]]` (keys "copied" /
        "skipped", missing-only semantics -- mirrors
        seed_project_docs.seed_architecture_scaffolds()'s return shape).
        Copies the package's OWN docs/product-truth/{flows,mock-data,
        mockups}/<product>/ tree (source, never the sibling "leafcutter"
        product-root content in those same directories) into
        `<project_root>/docs/product-truth/<type>/<product>/`, verbatim,
        recursively, for every file under each artifact-type directory that
        holds that product. Raises ValueError for a *product* that is not
        docs/product-truth/scripts/product_ownership.py's own
        `EXAMPLE_PRODUCT` constant (today: only "fern-and-fig" is known).
      - Wired as a new opt-in CLI flag on `scripts/build.py`,
        `--seed-example-product NAME` (default None; a bare flag with no
        value is not this AC's contract -- the person must ASK BY NAME),
        parsed in scripts/build_main_helpers.py's argument parser and
        consumed in `_run_optional_pre_deploy_steps` exactly the way
        `--seed-docs` already is (`if args.seed_example_product:
        _seed_example_product(target_root, args.seed_example_product,
        args.dry_run)`), so `python scripts/build.py --target-dir <dir>
        --seed-example-product fern-and-fig` is a real, reachable install-time
        request for the example product by name.
ARCHITECTURE: Three fixture styles, matching the three angles the AC's own
    test_spec names.
      - TestFreshInstallRecordHoldsZeroArtifacts calls
        build_phases.build_product_truth() directly (the real deploy-phase
        function; same style as unit_tests/product_truth/test_uxp_700a_1.py)
        against a per-test tmpdir, then reads back the REAL deployed
        index.json and product_ownership.py module. Covers 'real_artifact'.
      - TestExampleProductObtainableByName calls the new
        seed_example_product() function directly against a per-test tmpdir
        and asserts the real worked-example files land on disk with their
        real content. Covers 'criterion'.
      - TestUxp700a3ReachableFromEntryPoint runs the REAL `scripts/build.py`
        CLI as a subprocess -- the actual "asking for it by name" entry
        point a human or CI would invoke -- against an isolated synthetic
        package + target tree (never this worktree's own root; see the
        ISOLATION NOTE precedent in unit_tests/commit_guardian/
        test_bp_100k_3_i.py). Covers 'reachability'.

REACHABILITY ENTRY-POINT RESOLUTION (recorded per the test-writer skill's
    procedure): the AC's test_spec authored no entry point for its
    reachability-angle test ("the entry point is not declared: resolve it
    before writing this test"). Checked in order: (1) CLI script -- YES.
    `scripts/build.py` has a `main()` guarded by
    `if __name__ == "__main__":` with argparse, and IS "the tooling" the
    AC's own Given clause names ("the tooling is installed into a project").
    The architect-review sign-off on this ticket explicitly directs
    python-coder to wire the new by-name request as an opt-in flag on this
    same CLI, mirroring the shipped --seed-docs precedent, rather than
    inventing a new deploy convention. Resolved to `python scripts/build.py
    --target-dir <target> --seed-example-product fern-and-fig (CLI via
    subprocess)`. See this ticket's sign-off comment for the
    completion_manifest.reachability_entry_point_answer record.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import os
import subprocess

# Force UTF-8 stdio on the child process regardless of the host console's
# codepage, matching the precedent in test_uxp_700a_1.py.
_UTF8_SUBPROCESS_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_PT_SRC = _REPO_ROOT / "docs" / "product-truth"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from build_phases import build_product_truth  # noqa: E402

_MINIMAL_CONFIG: dict = {"output_root": ".leafcutter"}

# The three artifact-type directories the AC's Given/Then names by function
# (journeys, example data, screens) mapped onto the store's real directory
# names -- mirrors test_uxp_700a_1.py's own naming.
_ARTIFACT_TYPE_DIRS = ("flows", "mock-data", "mockups")

# The example product this AC's AC-3 must keep reachable by name. Sourced
# from the real, already-shipped constant rather than a hand-typed literal,
# so this test tracks the real module if the example product is ever renamed.
sys.path.insert(0, str(_PT_SRC / "scripts"))
from product_ownership import EXAMPLE_PRODUCT, PROJECT_PRODUCT  # noqa: E402

# A real, on-disk source file this AC's worked example is known to carry
# today, used to assert the seeded copy is byte-identical to the package's
# own source (never a hand-typed literal standing in for it).
_KNOWN_EXAMPLE_FLOW_REL = Path("flows") / EXAMPLE_PRODUCT / "customer-buys-a-plant.flow.json"


class TestFreshInstallRecordHoldsZeroArtifacts(unittest.TestCase):
    """AC-1 / AC-2: a fresh install enumerates zero artifacts of every type,
    and carries neither the example product's nor the tooling's own
    project-record content by default.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.consumer = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _install(self) -> Path:
        build_product_truth(self.consumer, _MINIMAL_CONFIG, dry_run=False, force=True)
        return self.consumer

    def _import_deployed_product_ownership(self, scripts_dir: Path):
        """Fresh-import the DEPLOYED product_ownership.py (never the source copy)."""
        scripts_dir_str = str(scripts_dir)
        sys.path.insert(0, scripts_dir_str)
        self.addCleanup(lambda: scripts_dir_str in sys.path and sys.path.remove(scripts_dir_str))
        sys.modules.pop("product_ownership", None)
        module = importlib.import_module("product_ownership")
        self.addCleanup(lambda: sys.modules.pop("product_ownership", None))
        return module

    def test_fresh_install_record_holds_zero_artifacts_of_every_type(self) -> None:
        # covers: UXP-700a-3
        # angle: real_artifact
        """Enumerating the installed project's record returns zero journeys,
        zero example datasets and zero screens, and neither the example
        product's nor the tooling's own project-record artifacts are present.

        Implementation requirement (already satisfied by the shipped
        build_product_truth(); this test pins the behaviour rather than
        changing it -- see this module's IMPLEMENTATION CONTRACT): a fresh
        install's flows/, mock-data/, mockups/ directories are each present
        and EMPTY, and the deployed index.json declares zero artifacts.
        """
        target = self._install()
        pt = target / "docs" / "product-truth"

        for subdir in _ARTIFACT_TYPE_DIRS:
            place = pt / subdir
            self.assertTrue(
                place.is_dir(),
                f"expected artifact-type place not created by a fresh install: {place}",
            )
            leftover = list(place.rglob("*"))
            self.assertEqual(
                leftover,
                [],
                f"a fresh install's '{subdir}' place must be EMPTY (count zero for every "
                f"artifact type), found: {leftover}",
            )

        # No path segment belonging to either forbidden product root is
        # present anywhere under the deployed record -- a stronger, more
        # literal check of AC-2 than "the three known directories are empty"
        # alone, since it would also catch content seeded to an unexpected
        # location.
        for forbidden_product in (EXAMPLE_PRODUCT, PROJECT_PRODUCT):
            hits = [p for p in pt.rglob("*") if forbidden_product in p.parts]
            self.assertEqual(
                hits,
                [],
                f"a fresh install must carry no artifact belonging to product "
                f"'{forbidden_product}', found: {hits}",
            )

        index_path = pt / "index.json"
        self.assertTrue(index_path.is_file(), f"fresh install must write an index: {index_path}")
        index = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(
            index.get("artifacts"),
            [],
            f"a fresh install's index must declare zero artifacts, got: {index.get('artifacts')!r}",
        )

        # Read the REAL deployed product_ownership.py (not the source copy)
        # against the REAL deployed index.json, and confirm its own
        # ownership predicate agrees: neither the example product nor the
        # project's own record has any artifact present.
        scripts_dir = pt / "scripts"
        self.assertTrue(
            (scripts_dir / "product_ownership.py").is_file(),
            f"product_ownership.py must be deployed for its predicate to be provable: {scripts_dir}",
        )
        deployed_ownership = self._import_deployed_product_ownership(scripts_dir)
        artifacts = index["artifacts"]
        self.assertEqual(
            deployed_ownership.own_record_artifacts(artifacts),
            [],
            "deployed product_ownership.own_record_artifacts() must report zero "
            "artifacts for the tooling's own project record on a fresh install",
        )
        self.assertEqual(
            deployed_ownership.artifacts_for_product(artifacts, EXAMPLE_PRODUCT),
            [],
            "deployed product_ownership.artifacts_for_product() must report zero "
            "artifacts for the example product on a fresh install",
        )


class TestExampleProductObtainableByName(unittest.TestCase):
    """AC-3: the example product remains obtainable by asking for it by
    name, so AC-1/AC-2's separation is never achieved by deletion.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.consumer = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_example_product_is_still_obtainable_on_explicit_request(self) -> None:
        # covers: UXP-700a-3
        # angle: criterion
        """Asking for the example product by name returns its artifacts, so
        the separation from AC-1/AC-2 is not achieved by deletion.

        Implementation requirement (see this module's IMPLEMENTATION
        CONTRACT): scripts/seed_example_product.py must expose
        `seed_example_product(project_root, product, dry_run=False)`,
        copying the package's own fern-and-fig worked example into the
        target project's docs/product-truth/ tree.
        """
        from seed_example_product import seed_example_product  # noqa: PLC0415

        result = seed_example_product(self.consumer, EXAMPLE_PRODUCT, dry_run=False)

        self.assertIn("copied", result, "result must report which files were copied")
        self.assertTrue(
            result["copied"],
            "asking for the example product by name must copy at least one real artifact",
        )

        # The real, on-disk worked-example file must now exist in the
        # target project, with content byte-identical to the package's own
        # source -- never a hand-typed stand-in.
        source_file = _PT_SRC / _KNOWN_EXAMPLE_FLOW_REL
        self.assertTrue(
            source_file.is_file(),
            f"fixture precondition failed: expected source worked-example file missing: {source_file}",
        )
        dest_file = self.consumer / "docs" / "product-truth" / _KNOWN_EXAMPLE_FLOW_REL
        self.assertTrue(
            dest_file.is_file(),
            f"asking for '{EXAMPLE_PRODUCT}' by name must materialize its real artifacts "
            f"on disk: {dest_file}",
        )
        self.assertEqual(
            dest_file.read_bytes(),
            source_file.read_bytes(),
            "the obtained example artifact must be byte-identical to the package's own "
            "source -- copied verbatim, not regenerated or paraphrased",
        )

        # Asking for an unknown product must fail clearly rather than
        # silently doing nothing (a request for it by name that is honoured
        # for one product but silently no-ops for a typo'd one would not be
        # a real ask-by-name contract).
        with self.assertRaises(
            ValueError,
            msg="asking for a product that is not the known example product must raise, "
            "not silently no-op",
        ):
            seed_example_product(self.consumer, "not-a-real-product", dry_run=False)


def _load_build_synthetic_full_package():
    """Load ``_build_synthetic_full_package`` from unit_tests/build_guards/test_bp_100k_2.py.

    Loaded read-only via ``importlib.util.spec_from_file_location`` under a
    private module name rather than duplicating the copy-the-real-templates
    logic here, per the precedent in unit_tests/product_truth/test_uxp_700a_1.py
    (which itself follows unit_tests/commit_guardian/test_bp_100k_3_i.py). That
    helper copies the REAL templates/, scripts/, config/, and (derived from
    build_phases.py's own `PACKAGE_ROOT / "docs" / "product-truth"` reference)
    docs/product-truth/ trees -- fern-and-fig's worked example included -- into
    a synthetic package root, so the seed-by-name flag's real source is
    present in the isolated copy build.py runs against below.

    Returns:
        The ``_build_synthetic_full_package(workspace: Path) -> Path`` function.
    """
    helper_path = _REPO_ROOT / "unit_tests" / "build_guards" / "test_bp_100k_2.py"
    spec = importlib.util.spec_from_file_location(
        "_uxp700a3_synthetic_package_helper", helper_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module._build_synthetic_full_package


class TestUxp700a3ReachableFromEntryPoint(unittest.TestCase):
    """AC UXP-700a-3, AC-3: the real `scripts/build.py` CLI, asked for the
    example product by name, actually obtains it -- not merely that the
    internal seed_example_product() function does.

    ISOLATION NOTE: never runs against this worktree's own root -- its
    `.leafcutter` is a symlink shared by every other worktree in the
    workspace (see unit_tests/commit_guardian/test_bp_100k_3_i.py's module
    docstring for the incident this avoids, KI-BP-002). Builds into a fresh
    tempdir instead, exactly as test_uxp_700a_1.py's own reachability
    TestCase does.
    """

    @classmethod
    def setUpClass(cls) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmpdir.cleanup)
        cls._isolated_tree = Path(tmpdir.name)

        build_synthetic_full_package = _load_build_synthetic_full_package()
        pkg_root = build_synthetic_full_package(cls._isolated_tree)
        build_script = pkg_root / "scripts" / "build.py"

        # The REAL build CLI, asked for the example product BY NAME via the
        # new opt-in flag -- the actual "obtaining the example product"
        # entry point a human or CI invokes -- run against the isolated
        # tree instead of this worktree's own root.
        cls._build_result = subprocess.run(
            [
                sys.executable,
                str(build_script),
                "--target-dir",
                str(cls._isolated_tree),
                "--seed-example-product",
                EXAMPLE_PRODUCT,
            ],
            cwd=str(cls._isolated_tree),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
            env=_UTF8_SUBPROCESS_ENV,
        )
        cls._pt = cls._isolated_tree / "docs" / "product-truth"

    def setUp(self) -> None:
        if self._build_result.returncode != 0:
            self.fail(
                "setup bug: the real `scripts/build.py --target-dir ... "
                "--seed-example-product ...` run failed "
                f"(returncode={self._build_result.returncode}).\n"
                f"stdout:\n{self._build_result.stdout}\nstderr:\n{self._build_result.stderr}"
            )

    def test_uxp_700a_3_reachable_from_entry_point(self) -> None:
        # covers: UXP-700a-3
        # angle: reachability
        """Invoking the real `scripts/build.py` CLI with `--seed-example-product
        <name>` actually obtains the example product's real artifacts on disk --
        not merely that the internal seed_example_product() function does.

        Entry point resolution (Reachability Entry-Point Resolution, step 1 --
        CLI script): scripts/build.py exposes a main() guarded by
        `if __name__ == "__main__":` with argparse; the new
        `--seed-example-product NAME` flag is this AC's real "ask for it by
        name" surface. Calling seed_example_product() directly (as
        TestExampleProductObtainableByName above does) does NOT satisfy this
        angle on its own -- this test exists specifically to prove the
        behaviour survives the real CLI dispatch path (argument parsing,
        phase orchestration) a direct function call bypasses.
        """
        dest_file = self._pt / _KNOWN_EXAMPLE_FLOW_REL
        self.assertTrue(
            dest_file.is_file(),
            "real `build.py --seed-example-product` CLI run did not materialize the "
            f"example product's real worked-example artifact on disk: {dest_file}\n"
            f"stdout:\n{self._build_result.stdout}\nstderr:\n{self._build_result.stderr}",
        )

        source_file = _PT_SRC / _KNOWN_EXAMPLE_FLOW_REL
        self.assertEqual(
            dest_file.read_bytes(),
            source_file.read_bytes(),
            "the obtained example artifact must be byte-identical to the package's own "
            "source after a real CLI run",
        )

        # A fresh install without the flag still carries none of the
        # example product by default (AC-1/AC-2) -- the flag is additive,
        # never a change to default behaviour. Checked here against the
        # SAME synthetic package/build run, not a separate install, so this
        # is a genuine assertion about what the flag alone added.
        for artifact_type in _ARTIFACT_TYPE_DIRS:
            place = self._pt / artifact_type
            other_products = {p.name for p in place.iterdir() if p.is_dir()} - {EXAMPLE_PRODUCT}
            self.assertEqual(
                other_products,
                set(),
                f"'{artifact_type}' must carry only the explicitly requested "
                f"'{EXAMPLE_PRODUCT}' product, found extra: {other_products}",
            )


if __name__ == "__main__":
    unittest.main()
