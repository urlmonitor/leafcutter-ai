"""
MODULE: test_uxp_700a_4
GOAL: AC UXP-700a-4 -- "The build proves a from-scratch record works before it
    ships one." The tooling's own build must (1) install a product-truth
    record into a throwaway empty project and RUN that record's checker
    against it (not merely verify file presence by name), (2) derive the set
    of files it requires from what the checker actually reads at startup
    rather than a hand-restated list, so that (3) adding one new start-up
    input to the checker extends the requirement with no second edit, and
    (4) the build states how many required files it checked, that figure
    rising by exactly one when the checker gains one such input.
BUSINESS CONTEXT: scripts/build_phases_product_truth.py today already carries
    a HAND-RESTATED tuple, ``_PRODUCT_TRUTH_REQUIRED_FILES`` (six entries),
    checked for bare on-disk presence by ``_verify_product_truth_required_files``
    -- a real, but static, list an author must remember to edit by hand every
    time ``validate_product_truth.py`` gains a new start-up input. It never
    actually EXECUTES the checker: the deployed record could crash on its
    first real run (as UXP-700a-1-i's classifier/eval.jsonl gap once did) and
    this existing check would still report every file "present" and let the
    build exit green. UXP-700a-4 closes that gap on two axes: the build must
    run the checker for real against a from-scratch record, AND the required
    set must be derived (traced from the checker's own reads), never
    restated by hand. AC-2 (the build fails, naming the file, when a required
    file was never installed) is the ALREADY-IMPLEMENTED half of this feature
    (``_verify_product_truth_required_files`` + ``record_deploy_failure``) and
    is exhaustively covered by the already-authored sibling ticket's own test
    file, unit_tests/build_guards/test_uxp_700a_4_i.py -- this file does not
    duplicate that coverage, per that file's own module docstring noting it
    remains RED until precisely the production work this ticket dispatches
    lands.
ARCHITECTURE: Three fixture styles, matching the three ``asserts`` entries
    this AC's test_spec authored (see the ticket's ## Test Requirements):
      - TestBuildRunsThrowawayRecordSmokeTest calls
        ``build_phases.build_product_truth()`` directly (the real deploy-phase
        function; same style as the pre-existing
        unit_tests/build_guards/test_build_product_truth.py and
        unit_tests/product_truth/test_uxp_700a_1.py) against a per-test
        tmpdir, capturing stdout+stderr around the call, and asserts the
        checker's own real outcome-contract JSON line (printed by
        ``product_truth_outcome._print_outcome_contract``) is present in that
        captured output -- proof the checker was actually RUN as part of the
        deploy phase's own call, not merely that files were copied. Covers
        the 'deployed' angle.
      - TestRequiredFileCountIsDerivedNotRestated builds a SYNTHETIC copy of
        the real ``docs/product-truth/{scripts,schemas}`` source tree (never
        the real one -- a mutation must never touch shared repo source),
        points ``build_phases.PACKAGE_ROOT`` at it via ``unittest.mock.patch``,
        and runs ``build_product_truth()`` twice: once against the
        unmodified synthetic copy (baseline), and once after physically
        adding ONE new file-read to the copied ``validate_product_truth.py``'s
        own startup path (a genuine extra input the checker itself reads,
        mirroring "the checker gains one start-up input" verbatim, robust
        regardless of whether the eventual implementation traces the checker
        in-process or via subprocess -- a Python-object monkeypatch would not
        survive a subprocess boundary, but a real source-text edit does).
        Asserts the build's OWN STATED required-file count (extracted from
        its stdout+stderr via a loose "<N> required file(s)" pattern) rises
        by EXACTLY one, with zero edits made anywhere in
        scripts/build_phases_product_truth.py itself during the test --
        proving the derivation tracks the checker's real reads rather than a
        hand-maintained manifest. Covers the 'seam' angle: pipes the REAL
        checker's own (mutated) startup reads into the REAL build's derived
        count and asserts the observable delta.
      - TestUxp700a4ReachableFromEntryPoint runs the REAL ``scripts/build.py``
        CLI as a subprocess -- the actual "the tooling's own build runs" the
        AC's own Given/When names -- against an isolated synthetic package +
        target tree (never this worktree's own root, whose ``.leafcutter`` is
        a shared symlink -- see the ISOLATION NOTE precedent in
        unit_tests/commit_guardian/test_bp_100k_3_i.py and
        unit_tests/product_truth/test_uxp_700a_1.py). Covers the
        'reachability' angle.

REACHABILITY ENTRY-POINT RESOLUTION (test-writer skill procedure): this AC's
    test_spec reachability descriptor explicitly carries the unresolved
    sentinel ("the entry point is not declared: resolve it before writing
    this test"). Resolved via Step 1: rule 1 (CLI script) applies --
    ``scripts/build.py`` has a ``main()`` guarded by
    ``if __name__ == "__main__":`` with argparse, and IS "the tooling" the
    AC's own Given/When clause names verbatim ("When the tooling's own build
    runs"). Resolved to ``python scripts/build.py --target-dir <target>``
    (CLI via subprocess) -- the identical resolution the sibling ticket
    UXP-700a-1 and UXP-700a-4-i already recorded for this exact script, for
    the same reason. See this ticket's sign-off comment for the recorded
    ``completion_manifest.reachability_entry_point_answer``.

IMPLEMENTATION STATUS (as of authoring): NOT implemented.
    ``build_product_truth()`` (scripts/build_phases_product_truth.py) today
    only copies files, write-if-absent-scaffolds an empty record, and
    verifies a HAND-RESTATED list of six file names is present by name -- it
    never invokes ``validate_product_truth.py`` at all, and reports no
    required-file COUNT anywhere. Every test in this file is expected to be
    RED until UXP-700a-4 adds: (a) an actual checker invocation against the
    freshly scaffolded (from-scratch, throwaway) record as part of the
    deploy phase's own call, and (b) a required-file count that is DERIVED
    from what the checker's startup path reads (rather than restated) and
    STATED in the build's own output.
"""
# @ac-tag: UXP-700a-4

from __future__ import annotations

import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup -- make scripts/ importable regardless of working directory.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_PT_SRC = _REPO_ROOT / "docs" / "product-truth"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build_phases  # noqa: E402
from build_phases import build_product_truth  # noqa: E402

_MINIMAL_CONFIG: dict = {"output_root": ".leafcutter"}

# Force UTF-8 stdio on any child process regardless of the host console's
# codepage -- Windows consoles commonly default to cp1252, which cannot
# encode the checkmark/box-drawing glyphs build.py's own helpers print, an
# environment quirk unrelated to this AC that would otherwise mask the real
# red baseline behind an unrelated UnicodeEncodeError (matches the precedent
# in unit_tests/product_truth/test_uxp_700a_1.py).
_UTF8_SUBPROCESS_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

# The checker's own real outcome-contract JSON fragment
# (product_truth_outcome._print_outcome_contract / _top_level_outcome) for a
# wholly from-scratch, zero-artifact record -- deterministic, real vocabulary
# already defined in this repo (UXP-700b-1), not invented by this test.
_NOTHING_EXAMINED_MARKER = '"outcome": "nothing-examined"'

# Loose pattern for AC-4's "the build states how many required files it
# checked" -- deliberately permissive about exact wording (this behaviour
# does not exist yet, so no exact string can be sourced from real code) while
# still requiring a real integer adjacent to "required file".
_REQUIRED_FILE_COUNT_RE = re.compile(r"(\d+)\s+required file", re.IGNORECASE)


def _extract_required_file_count(text: str) -> int | None:
    """Return the stated required-file count from build output, or None."""
    match = _REQUIRED_FILE_COUNT_RE.search(text)
    return int(match.group(1)) if match else None


def _run_build_product_truth_capturing_output(consumer: Path) -> tuple[int, str]:
    """Call the real ``build_product_truth()`` directly, capturing stdout+stderr.

    Returns (written_count, combined_output). Capturing around the direct
    function call (rather than a subprocess) is deliberate for the tests in
    this file that need to inspect what THIS SPECIFIC CALL produced, without
    the ambiguity of a whole ``build.py`` run's other phases also writing to
    the same stream.
    """
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        written = build_product_truth(consumer, _MINIMAL_CONFIG, dry_run=False, force=True)
    return written, out.getvalue() + err.getvalue()


def _copy_product_truth_source(dest_root: Path) -> Path:
    """Copy the REAL ``docs/product-truth/{scripts,schemas}`` tree into a
    synthetic package root under *dest_root*.

    Never touches the real repo source -- this is the isolated copy a test
    is free to mutate. Returns *dest_root*, usable directly as a
    ``build_phases.PACKAGE_ROOT`` stand-in since ``build_product_truth()``
    resolves its source as ``PACKAGE_ROOT / "docs" / "product-truth"``.
    """
    dest_pt = dest_root / "docs" / "product-truth"
    shutil.copytree(_PT_SRC / "scripts", dest_pt / "scripts",
                     ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(_PT_SRC / "schemas", dest_pt / "schemas",
                     ignore=shutil.ignore_patterns("__pycache__"))
    return dest_root


# The real, existing anchor line in validate_product_truth.py's own
# run_checks() -- used only to locate WHERE to splice in one extra startup
# read; verified present in the real source as of authoring (see
# docs/product-truth/scripts/validate_product_truth.py, run_checks()).
_STARTUP_ANCHOR = 'flow_schema = _load_schema("flow.schema.json")'


def _add_one_extra_checker_startup_read(synthetic_root: Path) -> None:
    """Give the SYNTHETIC checker copy one genuine extra start-up input.

    Writes a new schema file the copied ``validate_product_truth.py`` did not
    previously read, and splices in a real ``_load_schema(...)`` call for it
    immediately before the anchor line -- i.e. before any per-artifact
    checking begins, exactly where UXP-700a-4's own criteria text draws the
    line ("files a record needs in place before its checker can begin
    checking"). A genuine source-text edit (not a Python-object monkeypatch)
    so the extra read is observed identically whether the eventual
    implementation traces the checker in-process or via subprocess.
    """
    dest_pt = synthetic_root / "docs" / "product-truth"
    extra_schema = dest_pt / "schemas" / "uxp700a4-seam-test-extra.schema.json"
    extra_schema.write_text("{}\n", encoding="utf-8")

    validator_path = dest_pt / "scripts" / "validate_product_truth.py"
    text = validator_path.read_text(encoding="utf-8")
    assert _STARTUP_ANCHOR in text, (
        f"Precondition failed: anchor line {_STARTUP_ANCHOR!r} not found in "
        f"the synthetic copy of validate_product_truth.py at {validator_path}. "
        "The real checker's run_checks() may have been refactored -- update "
        "_STARTUP_ANCHOR to match."
    )
    mutated = text.replace(
        _STARTUP_ANCHOR,
        '_load_schema("uxp700a4-seam-test-extra.schema.json")  '
        '# UXP-700a-4 seam-test injected start-up input\n    ' + _STARTUP_ANCHOR,
        1,
    )
    validator_path.write_text(mutated, encoding="utf-8")


def _load_build_synthetic_full_package():
    """Load ``_build_synthetic_full_package`` from
    unit_tests/build_guards/test_bp_100k_2.py (read-only, by path), per the
    precedent in unit_tests/commit_guardian/test_bp_100k_3_i.py and
    unit_tests/product_truth/test_uxp_700a_1.py -- never a second,
    hand-authored copy of the same synthetic-package builder.
    """
    helper_path = _REPO_ROOT / "unit_tests" / "build_guards" / "test_bp_100k_2.py"
    spec = importlib.util.spec_from_file_location(
        "_uxp700a4_synthetic_package_helper", helper_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module._build_synthetic_full_package


class TestBuildRunsThrowawayRecordSmokeTest(unittest.TestCase):
    """UXP-700a-4 AC-1: the build installs a record into a throwaway empty
    project and RUNS that record's checker against it -- not merely verifies
    file presence by name."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.consumer = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_build_installs_a_throwaway_record_and_runs_its_checker(self) -> None:
        # covers: UXP-700a-4
        # angle: deployed
        """AC-1: the build's record smoke-test deploys into a temp project
        and executes the checker there.

        RED TODAY: build_product_truth() copies files, write-if-absent
        scaffolds an empty record, and checks six hand-named files exist by
        name (_verify_product_truth_required_files) -- it never actually
        invokes validate_product_truth.py. This assertion looks for the
        checker's own real outcome-contract JSON fragment
        (product_truth_outcome._print_outcome_contract) in the captured
        output of this single build_product_truth() call, which can only
        appear once the checker is genuinely run against the from-scratch
        record the same call just scaffolded.
        """
        written, combined = _run_build_product_truth_capturing_output(self.consumer)

        self.assertGreater(
            written, 0,
            "sanity: build_product_truth() reported writing nothing into a "
            f"fresh consumer dir ({self.consumer}) -- cannot evaluate the "
            "from-scratch smoke test against a deploy that did not happen.",
        )
        self.assertIn(
            _NOTHING_EXAMINED_MARKER,
            combined,
            "build_product_truth() must RUN the deployed checker against the "
            "throwaway, from-scratch (zero-artifact) record it just "
            "scaffolded, as part of this same call, and surface the "
            "checker's own outcome-contract JSON line "
            f"({_NOTHING_EXAMINED_MARKER!r}) reporting 'nothing-examined' -- "
            "the real, deterministic verdict for an empty record (UXP-700b-1). "
            "Today the deploy phase only verifies bare file presence by name; "
            "it never actually executes the checker (UXP-700a-4 AC-1).\n"
            f"Captured stdout+stderr:\n{combined}",
        )


class TestRequiredFileCountIsDerivedNotRestated(unittest.TestCase):
    """UXP-700a-4 AC-3/AC-4: the required-file set (and its stated count) is
    DERIVED from what the checker reads at startup, not restated by hand --
    so one new checker start-up input raises the stated count by exactly
    one, with no edit anywhere else."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_required_file_set_is_derived_not_restated(self) -> None:
        # covers: UXP-700a-4
        # angle: seam
        """AC-3/AC-4: adding a start-up input to the checker raises the
        build's stated required-file count by exactly one with no manifest
        edit.

        Pipes the REAL checker's own (deliberately mutated) startup reads
        into the REAL build's derivation/count-reporting -- baseline vs.
        mutated copy, same synthetic PACKAGE_ROOT, only the checker's own
        source text differs between the two runs. Zero lines of
        scripts/build_phases_product_truth.py are edited by this test, so a
        count delta of exactly one is only possible if the build's stated
        count genuinely tracks what the checker reads.

        RED TODAY: build_product_truth() states no required-file COUNT
        anywhere in its output (it only names individually MISSING files via
        record_deploy_failure, and only when one actually is missing) --
        there is nothing for _extract_required_file_count to find, on either
        run, so this assertion fails before the delta can even be evaluated.
        """
        baseline_root = _copy_product_truth_source(self.workspace / "baseline_pkg")
        mutated_root = _copy_product_truth_source(self.workspace / "mutated_pkg")
        _add_one_extra_checker_startup_read(mutated_root)

        with unittest.mock.patch.object(build_phases, "PACKAGE_ROOT", baseline_root):
            baseline_consumer = self.workspace / "baseline_consumer"
            baseline_consumer.mkdir()
            _, baseline_output = _run_build_product_truth_capturing_output(baseline_consumer)

        with unittest.mock.patch.object(build_phases, "PACKAGE_ROOT", mutated_root):
            mutated_consumer = self.workspace / "mutated_consumer"
            mutated_consumer.mkdir()
            _, mutated_output = _run_build_product_truth_capturing_output(mutated_consumer)

        baseline_count = _extract_required_file_count(baseline_output)
        mutated_count = _extract_required_file_count(mutated_output)

        self.assertIsNotNone(
            baseline_count,
            "the build's output must state how many required files it "
            f"checked (AC-4) -- found no '<N> required file(s)' pattern in "
            f"the baseline run's output:\n{baseline_output}",
        )
        self.assertIsNotNone(
            mutated_count,
            "the build's output must state how many required files it "
            f"checked (AC-4) -- found no '<N> required file(s)' pattern in "
            f"the mutated run's output:\n{mutated_output}",
        )
        self.assertEqual(
            mutated_count,
            baseline_count + 1,
            "adding exactly ONE new start-up input to the checker "
            f"(uxp700a4-seam-test-extra.schema.json) must raise the build's "
            f"stated required-file count by exactly one (baseline="
            f"{baseline_count}, mutated={mutated_count}) with no second edit "
            "to any hand-maintained list (AC-3/AC-4). This test edited only "
            "the SYNTHETIC checker copy's own source text -- "
            "scripts/build_phases_product_truth.py was never touched.",
        )


class TestUxp700a4ReachableFromEntryPoint(unittest.TestCase):
    """UXP-700a-4: the whole from-scratch smoke-test + derived-count
    behaviour, via the real CLI ``scripts/build.py`` a developer or CI
    actually runs -- not merely the internal deploy-phase function a direct
    call to ``build_product_truth()`` (used by the sibling TestCases above)
    bypasses.

    ISOLATION NOTE: never runs against this worktree's own root -- its
    ``.leafcutter`` is a symlink shared by every other worktree in the
    workspace (see unit_tests/commit_guardian/test_bp_100k_3_i.py's module
    docstring for the incident this avoids, KI-BP-002). Builds into a fresh
    tempdir instead, mirroring unit_tests/product_truth/test_uxp_700a_1.py's
    TestUxp700a1ReachableFromEntryPoint verbatim.
    """

    @classmethod
    def setUpClass(cls) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmpdir.cleanup)
        cls._isolated_tree = Path(tmpdir.name)

        build_synthetic_full_package = _load_build_synthetic_full_package()
        pkg_root = build_synthetic_full_package(cls._isolated_tree)
        build_script = pkg_root / "scripts" / "build.py"

        # The REAL build CLI -- the actual entry point UXP-700a-4's own
        # criteria text names ("When the tooling's own build runs...") -- run
        # over every phase, exactly as a developer or CI invokes it, just
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

    def test_uxp_700a_4_reachable_from_entry_point_MANUAL(self) -> None:
        # covers: UXP-700a-4
        # angle: reachability
        """AC-1/AC-4: invoking the real ``scripts/build.py`` CLI actually
        runs the from-scratch record smoke-test and states a required-file
        count -- not merely that the internal deploy function does.

        Entry-point resolution (BP-1100g-2, Step 1 rule 1 -- CLI script):
        ``scripts/build.py`` exposes a ``main()`` guarded by
        ``if __name__ == "__main__":`` with argparse, invoked in production
        as ``python scripts/build.py --target-dir <project>``. This is "the
        tooling's own build" the AC's Given/When clause names verbatim.
        Calling ``build_product_truth()`` directly (as the sibling
        TestCases above do) does NOT satisfy this angle on its own -- this
        test exists specifically to prove the behaviour survives the real
        CLI dispatch path (argument parsing, phase orchestration, halt
        guards) a direct function call bypasses.

        RED TODAY: the real CLI build exits 0 today having stated no
        required-file count anywhere and having never actually invoked the
        checker -- there is nothing for either assertion below to find.

        MANUAL: a full real ``build.py --target-dir`` run against a
        synthetic full package copy takes well over the 5-second per-test
        budget in testing_context (observed several seconds to tens of
        seconds locally, matching the documented cost of the same fixture in
        unit_tests/product_truth/test_uxp_700a_1.py and
        unit_tests/commit_guardian/test_bp_100k_3_i.py).
        """
        combined = self._build_result.stdout + self._build_result.stderr

        self.assertEqual(
            self._build_result.returncode,
            0,
            "the real `scripts/build.py --target-dir` run against an "
            "unmodified synthetic full package must exit 0 (positive "
            f"control) -- got {self._build_result.returncode}.\n"
            f"stdout:\n{self._build_result.stdout}\nstderr:\n{self._build_result.stderr}",
        )
        self.assertIn(
            _NOTHING_EXAMINED_MARKER,
            combined,
            "the real `scripts/build.py` CLI run must surface the checker's "
            f"own outcome-contract line ({_NOTHING_EXAMINED_MARKER!r}) for "
            "the throwaway from-scratch record it installs and checks as "
            "part of its own run (AC-1) -- not merely that the internal "
            "deploy-phase function does when called directly.\n"
            f"Combined output:\n{combined}",
        )
        self.assertIsNotNone(
            _extract_required_file_count(combined),
            "the real `scripts/build.py` CLI run must state how many "
            "required files it checked (AC-4) -- found no '<N> required "
            f"file(s)' pattern anywhere in its output.\nCombined output:\n{combined}",
        )


if __name__ == "__main__":
    unittest.main()
