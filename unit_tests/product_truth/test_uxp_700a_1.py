"""
MODULE: test_uxp_700a_1
GOAL: AC UXP-700a-1 -- "Installing the tooling lays down a complete, runnable, empty
    record." A project that has never used the product-truth tooling must, after
    install, have: (1) a directory for each artifact type (flows/journeys,
    mock-data/example-data, mockups/screens), each present and EMPTY; (2) a store
    index declaring zero artifacts with every derived lookup (by_component,
    by_entity, by_flow, by_ac) present and empty; (3) every input the checker
    (validate_product_truth.py) opens before it begins per-artifact checking, so it
    reaches a stated verdict instead of crashing; (4) a written introduction naming
    each artifact type, where it lives, and the first thing to author.
BUSINESS CONTEXT: The AC's own evidence note (docs/acceptance-criteria/
    ux-prototyping/UXP-700-truthful-project-record/UXP-700a-1.yaml) names the exact
    gap: build_product_truth() (scripts/build_phases.py) currently deploys only
    scripts/*.py and schemas/*.json into a consumer project -- no directory
    scaffold, no index.json, no classifier/eval.jsonl, no README/introduction. The
    concretely-observed crash from the missing classifier/eval.jsonl input is
    recorded as UXP-700a-1-i. This file is the RED baseline for that gap: every
    test below is expected to fail against the current, unmodified
    build_product_truth() and only go green once it is extended to deploy the
    scaffold/index/eval-seed/introduction alongside the scripts/schemas it already
    deploys.
ARCHITECTURE: Two fixture styles, matching the two production entry points this AC
    touches.
      - TestFreshInstallProductTruthRecord calls build_phases.build_product_truth()
        directly (the real deploy-phase function; same style as the existing
        unit_tests/build_guards/test_build_product_truth.py) against a per-test
        tmpdir, then inspects the deployed tree/pipes the deployed record into the
        deployed checker's own loader functions. Covers the criterion / real_artifact
        / deployed / seam angles.
      - TestUxp700a1ReachableFromEntryPoint runs the REAL `scripts/build.py` CLI as
        a subprocess -- the actual "installing the tooling" entry point a human or
        CI runs -- against an isolated synthetic package + target tree (never this
        worktree's own root, whose `.leafcutter` is a shared symlink -- see the
        ISOLATION NOTE precedent in unit_tests/commit_guardian/test_bp_100k_3_i.py).
        Covers the reachability angle.

REACHABILITY ENTRY-POINT RESOLUTION (recorded per the test-writer skill's
    procedure): the AC's test_spec authored no entry point ("the entry point is not
    declared: resolve it before writing this test"). Checked in order: (1) CLI
    script -- YES. `scripts/build.py` has a `main()` guarded by
    `if __name__ == "__main__":` with argparse, and IS "the tooling" the AC's Given
    clause names ("a project ... holds no project record ... When the tooling is
    installed into that project"). Resolved to
    `python scripts/build.py --target-dir <target> (CLI via subprocess)`. See this
    ticket's sign-off comment for the completion_manifest.reachability_entry_point_answer
    record.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Force UTF-8 stdio on the child process regardless of the host console's
# codepage. Windows consoles commonly default to cp1252, which cannot encode
# the checkmark glyphs build.py's own success/warning helpers print -- an
# environment quirk unrelated to this AC that would otherwise mask the real
# red baseline behind an unrelated UnicodeEncodeError.
_UTF8_SUBPROCESS_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from build_phases import build_product_truth  # noqa: E402

_MINIMAL_CONFIG: dict = {"output_root": ".leafcutter"}

# The four derived lookups the index must carry, present and empty, on a zero-
# artifact install (mirrors unit_tests/product_truth/test_uxp_700a_2_i.py's naming).
_DERIVED_LOOKUP_KEYS = ("by_component", "by_entity", "by_flow", "by_ac")

# The three artifact-type directories the AC's Given/Then names by function
# (journeys, example data, screens) mapped onto the store's real directory names.
_ARTIFACT_TYPE_DIRS = ("flows", "mock-data", "mockups")


class TestFreshInstallProductTruthRecord(unittest.TestCase):
    """Deploying the product-truth phase into a project with no prior record."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.consumer = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _install(self) -> Path:
        """Run the REAL deploy-phase function against a fresh, empty consumer dir.

        Returns the consumer project root (self.consumer), for chaining.
        """
        build_product_truth(self.consumer, _MINIMAL_CONFIG, dry_run=False, force=True)
        return self.consumer

    def _import_deployed_validator(self, scripts_dir: Path):
        """Fresh-import the DEPLOYED validate_product_truth.py (never the source copy).

        Inserts *scripts_dir* at the front of sys.path so `import
        validate_product_truth` (which itself does `from generate_product_truth
        import ...`) resolves against the just-deployed files, and evicts any
        previously cached module of the same name first so this is a genuine
        fresh import bound to *this* tmpdir's STORE, not a stale module object
        left over from an earlier test's deployment. Registered cleanups undo
        both the sys.path and sys.modules mutation.
        """
        scripts_dir_str = str(scripts_dir)
        sys.path.insert(0, scripts_dir_str)
        self.addCleanup(lambda: scripts_dir_str in sys.path and sys.path.remove(scripts_dir_str))
        for name in ("validate_product_truth", "generate_product_truth"):
            sys.modules.pop(name, None)
        module = importlib.import_module("validate_product_truth")
        self.addCleanup(lambda: sys.modules.pop("validate_product_truth", None))
        self.addCleanup(lambda: sys.modules.pop("generate_product_truth", None))
        return module

    def test_fresh_install_creates_every_artifact_place_and_an_empty_index(self) -> None:
        # covers: UXP-700a-1
        # angle: real_artifact
        """A place for each artifact type, present and empty, plus a zero-artifact
        index with every derived lookup present and empty.

        Implementation requirement: build_product_truth() (scripts/build_phases.py)
        must additionally create docs/product-truth/{flows,mock-data,mockups}/ (empty)
        and write docs/product-truth/index.json declaring artifacts: [] with
        by_component/by_entity/by_flow/by_ac each present as {}.
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
                f"a fresh install's '{subdir}' place must be EMPTY, found: {leftover}",
            )

        index_path = pt / "index.json"
        self.assertTrue(
            index_path.is_file(),
            f"a fresh install must write a store index declaring zero artifacts: {index_path}",
        )
        index = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(
            index.get("artifacts"),
            [],
            f"a fresh install's index must declare zero artifacts, got: {index.get('artifacts')!r}",
        )
        for key in _DERIVED_LOOKUP_KEYS:
            self.assertIn(
                key,
                index,
                f"derived lookup '{key}' is ABSENT from a freshly installed index -- "
                "the AC requires an entry for every derived lookup, even when empty.",
            )
            self.assertEqual(
                index[key],
                {},
                f"derived lookup '{key}' must be empty on a fresh install, got {index[key]!r}",
            )

    def test_fresh_install_record_reaches_a_verdict_from_its_own_checker(self) -> None:
        # covers: UXP-700a-1
        # angle: deployed
        """Running the DEPLOYED checker against the freshly deployed record must
        terminate with a stated pass/fail verdict, never an unhandled crash.

        This is the exact regression named in the AC's evidence note: the
        concretely-missing classifier/eval.jsonl startup input crashed the checker
        (recorded as UXP-700a-1-i) instead of it reaching a verdict. Runs the
        DEPLOYED copy of validate_product_truth.py (never the package source), per
        the 'deployed' angle -- a source-tree read would be structurally blind to a
        deploy-manifest gap.
        """
        target = self._install()
        validator = target / "docs" / "product-truth" / "scripts" / "validate_product_truth.py"
        self.assertTrue(
            validator.is_file(),
            f"validate_product_truth.py must be deployed for the checker to run at all: {validator}",
        )

        result = subprocess.run(
            [sys.executable, str(validator), "--quiet"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=_UTF8_SUBPROCESS_ENV,
        )

        self.assertNotIn(
            "Traceback (most recent call last)",
            result.stderr,
            "the checker crashed with an unhandled exception instead of reaching a "
            f"stated verdict on the freshly deployed record.\nstderr:\n{result.stderr}",
        )
        self.assertIn(
            result.returncode,
            (0, 1),
            "the checker must exit with a stated pass(0)/fail(1) verdict, not any "
            f"other code; got {result.returncode}.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def test_every_startup_input_the_checker_reads_is_present_after_install(self) -> None:
        # covers: UXP-700a-1
        # angle: seam
        """Pipes the REAL deployed record (producer) into the REAL checker's own
        startup loaders (consumer) and asserts each resolves without error.

        Distinct from the 'deployed' test above: that test proves the checker's
        CLI entry point as a whole reaches a verdict; this test proves the SEAM
        itself -- that every specific input load_ac_records()/_load_json()/
        _read_text()/_load_schema() open before the per-artifact checking loop
        begins actually resolves against what install wrote, by calling the
        checker's own real loader functions (not a hand-written existence check
        that could drift from what the checker actually opens).
        """
        target = self._install()
        scripts_dir = target / "docs" / "product-truth" / "scripts"
        self.assertTrue(
            (scripts_dir / "validate_product_truth.py").is_file(),
            "validate_product_truth.py must be deployed before its startup inputs can be proved",
        )
        vpt = self._import_deployed_validator(scripts_dir)

        try:
            ac_records = vpt.load_ac_records()
            index = vpt._load_json(vpt.STORE / "index.json")
            eval_text = vpt._read_text(vpt.STORE / "classifier" / "eval.jsonl")
            for schema_name in (
                "flow.schema.json",
                "mock-data.schema.json",
                "mockup.schema.json",
                "classifier-eval.schema.json",
            ):
                vpt._load_schema(schema_name)
        except OSError as exc:
            self.fail(
                "a startup input the checker reads before checking begins is "
                f"missing/unreadable after a fresh install: {exc}"
            )

        self.assertIsInstance(ac_records, dict)
        self.assertIsInstance(index, dict)
        self.assertIsInstance(eval_text, str)

    def test_fresh_install_record_carries_a_written_introduction(self) -> None:
        # covers: UXP-700a-1
        # angle: real_artifact
        """The deployed record contains a written introduction naming each artifact
        type, its location, and the first artifact to author.

        Implementation requirement: build_product_truth() must write a
        docs/product-truth/README.md (or equivalent introduction) into a fresh
        consumer project stating the record is empty, naming where each of
        flows/mock-data/mockups lives, and naming the first thing to author.
        """
        target = self._install()
        pt = target / "docs" / "product-truth"
        intro_path = pt / "README.md"
        self.assertTrue(
            intro_path.is_file(),
            f"a fresh install must write an introduction into the record: {intro_path}",
        )
        text = intro_path.read_text(encoding="utf-8").lower()

        self.assertIn("empty", text, "introduction must state that the record is empty")

        for location in _ARTIFACT_TYPE_DIRS:
            self.assertIn(
                f"{location}/",
                text,
                f"introduction must name where the '{location}' artifact type lives",
            )

        self.assertTrue(
            any(kw in text for kw in ("first thing", "start by", "begin by", "first artifact")),
            "introduction must name the first thing a person should author "
            "(expected phrasing like 'first thing' / 'start by' / 'begin by')",
        )


def _load_build_synthetic_full_package():
    """Load ``_build_synthetic_full_package`` from unit_tests/build_guards/test_bp_100k_2.py.

    Loaded read-only via ``importlib.util.spec_from_file_location`` under a
    private module name rather than duplicating the copy-the-real-templates
    logic here, per the precedent in
    unit_tests/commit_guardian/test_bp_100k_3_i.py. That helper copies the
    REAL templates/, scripts/, config/, and (derived from build_phases.py's own
    `PACKAGE_ROOT / "docs" / "product-truth"` reference) docs/product-truth/
    trees into a synthetic package root, so `build_product_truth`'s deploy
    source is present in the isolated copy build.py runs against below.

    Returns:
        The ``_build_synthetic_full_package(workspace: Path) -> Path`` function.
    """
    helper_path = _REPO_ROOT / "unit_tests" / "build_guards" / "test_bp_100k_2.py"
    spec = importlib.util.spec_from_file_location(
        "_uxp700a1_synthetic_package_helper", helper_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module._build_synthetic_full_package


class TestUxp700a1ReachableFromEntryPoint(unittest.TestCase):
    """AC UXP-700a-1: the whole install-to-runnable pipeline, via the real CLI.

    Runs `python scripts/build.py --target-dir <target>` (the actual "installing
    the tooling" entry point named in the AC's Given/When) as a real subprocess
    against an isolated synthetic package + target tree, then asserts the
    deployed record is complete AND the deployed checker reaches a verdict --
    proving reachability through the real CLI-argument-parsing path a direct
    call to build_product_truth() (used by the sibling TestCase above) bypasses.

    ISOLATION NOTE: never runs against this worktree's own root -- its
    `.leafcutter` is a symlink shared by every other worktree in the workspace
    (see unit_tests/commit_guardian/test_bp_100k_3_i.py's module docstring for
    the incident this avoids, KI-BP-002). Builds into a fresh tempdir instead.
    """

    @classmethod
    def setUpClass(cls) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmpdir.cleanup)
        cls._isolated_tree = Path(tmpdir.name)

        build_synthetic_full_package = _load_build_synthetic_full_package()
        pkg_root = build_synthetic_full_package(cls._isolated_tree)
        build_script = pkg_root / "scripts" / "build.py"

        # The REAL build CLI -- the actual "installing the tooling" entry point --
        # run over every phase, exactly as a developer or CI invokes it, just
        # pointed at the isolated tree instead of this worktree's own root.
        cls._build_result = subprocess.run(
            [sys.executable, str(build_script), "--target-dir", str(cls._isolated_tree)],
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
                "setup bug: the real `scripts/build.py --target-dir` run failed "
                f"(returncode={self._build_result.returncode}).\n"
                f"stdout:\n{self._build_result.stdout}\nstderr:\n{self._build_result.stderr}"
            )

    def test_uxp_700a_1_reachable_from_entry_point(self) -> None:
        # covers: UXP-700a-1
        # angle: reachability
        """Invoking the real `scripts/build.py` CLI actually lays down the complete,
        runnable, empty record -- not merely that the internal deploy function does.

        Entry point resolution (Reachability Entry-Point Resolution, step 1 -- CLI
        script): scripts/build.py exposes a main() guarded by
        `if __name__ == "__main__":` with argparse, invoked in production as
        `python scripts/build.py --target-dir <project>`. This is "the tooling"
        the AC's own Given/When names ("a project that has never used the tooling
        ... When the tooling is installed into that project"). Importing
        build_product_truth and calling it directly (as
        TestFreshInstallProductTruthRecord above does) does NOT satisfy this angle
        on its own -- this test exists specifically to prove the behaviour survives
        the real CLI dispatch path (argument parsing, phase orchestration, halt
        guards) a direct function call bypasses.
        """
        for subdir in _ARTIFACT_TYPE_DIRS:
            place = self._pt / subdir
            self.assertTrue(
                place.is_dir(),
                f"real `build.py` CLI run did not create artifact-type place: {place}",
            )
            leftover = list(place.rglob("*"))
            self.assertEqual(
                leftover,
                [],
                f"'{subdir}' place must be EMPTY after a fresh install, found: {leftover}",
            )

        index_path = self._pt / "index.json"
        self.assertTrue(
            index_path.is_file(),
            f"real `build.py` CLI run did not write a store index: {index_path}",
        )
        index = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(index.get("artifacts"), [], "index must declare zero artifacts")
        for key in _DERIVED_LOOKUP_KEYS:
            self.assertIn(key, index, f"derived lookup '{key}' missing after real CLI install")
            self.assertEqual(index[key], {}, f"derived lookup '{key}' must be empty, got {index[key]!r}")

        eval_path = self._pt / "classifier" / "eval.jsonl"
        self.assertTrue(
            eval_path.is_file(),
            "the checker's classifier/eval.jsonl startup input must be present after "
            f"install (the concretely-missing input named in the AC's evidence note): {eval_path}",
        )

        validator = self._pt / "scripts" / "validate_product_truth.py"
        self.assertTrue(validator.is_file(), f"checker script not deployed: {validator}")

        result = subprocess.run(
            [sys.executable, str(validator), "--quiet"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=_UTF8_SUBPROCESS_ENV,
        )
        self.assertNotIn(
            "Traceback (most recent call last)",
            result.stderr,
            "the checker crashed instead of reaching a stated verdict against the "
            f"record produced by the real `build.py` CLI.\nstderr:\n{result.stderr}",
        )
        self.assertIn(
            result.returncode,
            (0, 1),
            f"checker did not exit with a stated verdict; got {result.returncode}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
