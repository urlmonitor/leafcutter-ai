"""
MODULE: test_uxp_700a_1_i
GOAL: Pin the behaviour of validate_product_truth.py's checker when the classifier
    evaluation set (docs/product-truth/classifier/eval.jsonl) has never been authored --
    the "freshly installed, empty record" case named by UXP-700a-1-i. Today the checker
    lets the missing-file OSError propagate out of main() uncaught: an unhandled
    traceback, not a reported condition.
BUSINESS CONTEXT: AC UXP-700a-1-i. expects_from UXP-700a-1 ("the deployed empty record
    whose checker this exercises"). The AC's three clauses: (1) the checker names the
    absent input and the artifact class it belongs to as a reported condition, (2) it
    reaches a stated verdict rather than terminating with an unhandled failure, (3) that
    verdict is not the verdict it reports for a record it checked and found sound.
    DIRECTLY OBSERVED bug (AC notes, 2026-09-07): with flows/, mock-data/, mockups/
    present but docs/product-truth/classifier/eval.jsonl absent, the checker exits with
    an uncaught Python traceback.
ARCHITECTURE: Uses a self-contained tempdir fixture that mirrors the minimal
    product-truth store layout the validator reads (flows/, mock-data/, mockups/,
    classifier/, index.json, schemas/, acceptance-criteria/), built either WITH an
    (empty, valid) classifier/eval.jsonl -- the "clean pass" control -- or WITHOUT one --
    the "absent start-up input" case this AC is about. All three tests invoke the REAL
    docs/product-truth/scripts/validate_product_truth.py (verbatim bytes copied into the
    fixture's own scripts/ dir, alongside its sibling generate_product_truth.py which it
    imports) as a subprocess with real argv -- the CLI-script branch of the Reachability
    Entry-Point Resolution procedure (validate_product_truth.py has a main() guarded by
    `if __name__ == "__main__":` with argparse; the same real script is also wired as a
    pre-commit hook via scripts/commit_guardian/run_hook.py, but the CLI-script check is
    first in the resolution order and genuinely applies, so a direct subprocess of the
    script itself -- not the run_hook.py wrapper -- is the entry point resolved here).
    Importing validate_product_truth and calling main()/_check_eval() directly would NOT
    satisfy this: the observed defect is that the CALLER (main(), and anything that
    invokes this script as a process) dies, so the process-level outcome is exactly what
    must be pinned.

completion_manifest (recorded in the ticket's sign-off comment, not here):
  cross_layer_seam_answer:
    result: not_applicable
    reason: >
      This AC exercises the checker's own file-I/O error path when a human-authored
      input (classifier/eval.jsonl) was never created -- there is no producer script
      whose real output is piped into this consumer for this scenario. UXP-700a-1 (the
      install/deploy phase) is a dependency but is not itself under test here; the
      "expects_from" contract is that a deployed-but-incomplete record exists, not that
      this AC pipes UXP-700a-1's real output through this checker.
  reachability_entry_point_answer:
    result: resolved
    entry_point: >
      python docs/product-truth/scripts/validate_product_truth.py --quiet (CLI via
      subprocess; main() guarded by `if __name__ == "__main__":` with argparse). The
      AC's own test_spec named no entry point (ticket Test Requirements entry 3: "the
      entry point is not declared: resolve it before writing this test") -- resolved per
      Reachability Entry-Point Resolution Step 1.1 (CLI script), same resolution the
      sibling ticket UXP-700a-2-i's test_uxp_700a_2_i.py used for
      generate_product_truth.py.

NOTE ON RED BASELINE: all three tests below are expected to be RED on arrival. The
current validate_product_truth.py lets the missing-file OSError from
generate_product_truth._read_text() propagate uncaught through _check_eval() and
main() -- an unhandled Python traceback on stderr, not a reported condition -- so the
"no Traceback" / "stated verdict" assertions in every test here fail against today's
code. See the ticket's sign-off comment for the captured verification-run output.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "docs" / "product-truth" / "scripts"
_SCHEMAS_DIR = _REPO_ROOT / "docs" / "product-truth" / "schemas"
_REAL_VALIDATOR_SCRIPT = _SCRIPTS_DIR / "validate_product_truth.py"
_REAL_GENERATOR_SCRIPT = _SCRIPTS_DIR / "generate_product_truth.py"

# The four schemas validate_product_truth.py loads unconditionally at startup
# (flow / mock-data / mockup / classifier-eval). Copied verbatim from the real store so
# schema validation runs for real, not against a hand-typed stub.
_SCHEMA_FILES = (
    "flow.schema.json",
    "mock-data.schema.json",
    "mockup.schema.json",
    "classifier-eval.schema.json",
)

# The artifact class this AC's absent input belongs to, and the concrete filename named
# in the AC's own notes -- both must appear in the reported condition.
_ABSENT_ARTIFACT_CLASS = "classifier"
_ABSENT_INPUT_FILENAME = "eval.jsonl"


def _make_minimal_store(tmp: Path, *, include_eval: bool) -> Path:
    """Build a minimal-but-complete product-truth store fixture.

    Layout: <tmp>/product-truth/{flows,mock-data,mockups}/ (all empty, zero artifacts),
    <tmp>/product-truth/schemas/ (the four real schema files, copied verbatim),
    <tmp>/product-truth/scripts/ (the real validator + generator scripts, copied
    verbatim), <tmp>/product-truth/index.json (declares zero artifacts, every derived
    lookup present and empty), and <tmp>/acceptance-criteria/ (empty).

    When ``include_eval`` is True, <tmp>/product-truth/classifier/eval.jsonl is created
    empty (a valid, zero-row eval set) -- the "record checked and found sound" clean-pass
    control. When False, the classifier/ directory is not created at all -- "the
    classifier evaluation set has never been authored", the exact absent-input case this
    AC is about.

    Returns the product-truth store root (the directory validate_product_truth.py's
    module-level STORE resolves to once the copied script runs from <store>/scripts/).
    """
    store = tmp / "product-truth"
    (store / "flows").mkdir(parents=True)
    (store / "mock-data").mkdir(parents=True)
    (store / "mockups").mkdir(parents=True)
    (tmp / "acceptance-criteria").mkdir(parents=True)

    schemas_dir = store / "schemas"
    schemas_dir.mkdir(parents=True)
    for name in _SCHEMA_FILES:
        (schemas_dir / name).write_bytes((_SCHEMAS_DIR / name).read_bytes())

    scripts_dir = store / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "validate_product_truth.py").write_bytes(_REAL_VALIDATOR_SCRIPT.read_bytes())
    (scripts_dir / "generate_product_truth.py").write_bytes(_REAL_GENERATOR_SCRIPT.read_bytes())
    # build.py deploys scripts/ as a whole "*.py" glob, and validate/generate
    # import sibling modules (product_truth_checks, product_truth_index_checks,
    # product_truth_derivations). Copy the whole set so this fixture matches
    # what a real install actually contains.
    for _sibling in sorted(_SCRIPTS_DIR.glob("*.py")):
        (scripts_dir / _sibling.name).write_bytes(_sibling.read_bytes())

    index = {
        "artifacts": [],
        "entity_registry": [],
        "by_component": {},
        "by_entity": {},
        "by_flow": {},
        "by_ac": {},
    }
    (store / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

    if include_eval:
        (store / "classifier").mkdir(parents=True)
        (store / "classifier" / "eval.jsonl").write_text("", encoding="utf-8")

    return store


def _run_validator(store: Path) -> subprocess.CompletedProcess:
    """Invoke the real, copied validate_product_truth.py as a subprocess.

    Reproduces the literal CLI invocation configured for this check in
    scripts/commit_guardian/commit_guardian.json's check-product-truth-validate entry
    (``... validate_product_truth.py --quiet``), minus the run_hook.py venv-resolution
    wrapper -- the CLI-script itself is the resolved entry point (see module docstring).
    """
    script = store / "scripts" / "validate_product_truth.py"
    return subprocess.run(
        [sys.executable, str(script), "--quiet"],
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestAbsentClassifierEvalReportedNotRaised(unittest.TestCase):
    """AC UXP-700a-1-i clauses 1 + 2: name the absent input; reach a stated verdict."""

    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp_dir.name)

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_absent_classifier_eval_is_reported_not_raised(self) -> None:
        # covers: UXP-700a-1-i
        # angle: failure
        """A store with no classifier evaluation set is reported, not crashed on.

        Implementation requirement: validate_product_truth.py's _check_eval() (or its
        caller) must catch the missing-file condition on
        docs/product-truth/classifier/eval.jsonl and append a message to `errors` that
        names the absent input (the filename) and the artifact class it belongs to (the
        classifier evaluation set) -- instead of letting generate_product_truth's
        _read_text() OSError propagate uncaught out of main(). Today it propagates: this
        test is RED because a Python traceback appears on stderr and the process exit
        code is the interpreter's own uncaught-exception code, not a value main() chose.
        """
        store = _make_minimal_store(self.tmp, include_eval=False)
        result = _run_validator(store)

        self.assertNotEqual(
            result.returncode,
            0,
            "checker must reach a non-zero (failing) verdict when a start-up input is "
            f"absent.\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )
        self.assertNotIn(
            "Traceback (most recent call last)",
            result.stderr,
            "checker must NOT terminate with an unhandled Python traceback -- it must "
            f"catch the absent-input condition and report it.\nstderr: {result.stderr}",
        )

        combined = (result.stdout + result.stderr).lower()
        self.assertIn(
            _ABSENT_INPUT_FILENAME,
            combined,
            f"reported condition must name the absent input ('{_ABSENT_INPUT_FILENAME}').\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )
        self.assertIn(
            _ABSENT_ARTIFACT_CLASS,
            combined,
            "reported condition must name the artifact class the absent input belongs to "
            f"('{_ABSENT_ARTIFACT_CLASS}').\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )


class TestAbsentStartupInputVerdictDiffersFromCleanPass(unittest.TestCase):
    """AC UXP-700a-1-i clause 3: the absent-input verdict != the clean-pass verdict."""

    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp_dir.name)

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_absent_startup_input_verdict_differs_from_clean_pass(self) -> None:
        # covers: UXP-700a-1-i
        # angle: boundary
        """The missing-input verdict must be distinguishable from a clean-pass verdict.

        Merely observing returncode 0 vs non-zero is not enough to prove this clause: an
        UNHANDLED crash also happens to exit non-zero, which would make this assertion
        trivially true even on today's broken code without proving anything about a
        "stated verdict". The discriminating assertion is that the checker must reach
        its OWN controlled summary (no interpreter traceback) for the missing-input run,
        exactly like it does for the clean-pass run, and that controlled summary must
        differ from -- never equal -- the clean-pass one.
        """
        # Both runs use --quiet (the literal flag the check-product-truth-validate
        # pre-commit hook is configured with; see _run_validator's docstring), which
        # sets the logging level to WARNING -- the clean pass's own "OK: ..." summary is
        # logged at INFO and is therefore deliberately suppressed in this mode on BOTH
        # sides. The verdict this test compares is therefore the process's own exit
        # code plus the presence/absence of an interpreter traceback, not log text that
        # --quiet intentionally silences.
        clean_store = _make_minimal_store(self.tmp / "clean", include_eval=True)
        clean_result = _run_validator(clean_store)
        self.assertEqual(
            clean_result.returncode,
            0,
            "control case: a clean, complete store must pass "
            f"(returncode 0).\nstdout: {clean_result.stdout}\nstderr: {clean_result.stderr}",
        )
        self.assertNotIn(
            "Traceback (most recent call last)",
            clean_result.stderr,
            "control case: a clean, complete store must not itself crash.\n"
            f"stderr: {clean_result.stderr}",
        )

        missing_store = _make_minimal_store(self.tmp / "missing", include_eval=False)
        missing_result = _run_validator(missing_store)

        self.assertNotIn(
            "Traceback (most recent call last)",
            missing_result.stderr,
            "the missing-input run must reach its OWN stated verdict (no interpreter "
            f"traceback) exactly like the clean-pass run does.\nstderr: {missing_result.stderr}",
        )
        self.assertNotEqual(
            missing_result.returncode,
            clean_result.returncode,
            "the verdict for the missing-input run must differ from the verdict for a "
            "record checked and found sound.\n"
            f"missing-input returncode: {missing_result.returncode}, "
            f"clean-pass returncode: {clean_result.returncode}",
        )


class TestUxp700a1iReachableFromEntryPoint(unittest.TestCase):
    """Reachability floor: the real CLI entry point, invoked as a subprocess."""

    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp_dir.name)

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_uxp_700a_1_i_reachable_from_entry_point(self) -> None:
        # covers: UXP-700a-1-i
        # angle: reachability
        """Invokes the real CLI entry point (subprocess) and consumes its verdict.

        Entry point resolution (Reachability Entry-Point Resolution, Step 1 -- CLI
        script): validate_product_truth.py exposes a main() guarded by
        `if __name__ == "__main__":` with argparse, invoked in production exactly as
        reproduced by _run_validator() above (the literal command configured for the
        check-product-truth-validate pre-commit hook, minus only the run_hook.py
        venv-resolution wrapper). Importing validate_product_truth and calling main() or
        _check_eval() directly does NOT satisfy this angle -- the observed defect is that
        the CALLING PROCESS dies, so only a real subprocess dispatch can prove the fix.

        "Consumed in control flow": the test does not merely inspect the returncode --
        it uses it to make the same pass/block decision a real caller (e.g. the
        pre-commit hook) would make, and asserts on that decision, not on the raw value.
        """
        store = _make_minimal_store(self.tmp, include_eval=False)
        result = _run_validator(store)

        # The same decision a real caller (pre-commit's hook gate) makes from this
        # process's exit code: zero means the commit proceeds, non-zero means it blocks.
        if result.returncode == 0:
            gate_decision = "pass"
        else:
            gate_decision = "block"

        self.assertEqual(
            gate_decision,
            "block",
            "a caller consuming this checker's exit code must see a BLOCK decision for "
            "a record whose start-up input is absent, not a silent pass.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )
        self.assertNotIn(
            "Traceback (most recent call last)",
            result.stderr,
            "the real CLI entry point must not hand its caller an unhandled traceback "
            f"in place of a stated verdict.\nstderr: {result.stderr}",
        )

        combined = (result.stdout + result.stderr).lower()
        self.assertIn(
            _ABSENT_INPUT_FILENAME,
            combined,
            f"reported condition (reached via the real entry point) must name the absent "
            f"input ('{_ABSENT_INPUT_FILENAME}').\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )
        self.assertIn(
            _ABSENT_ARTIFACT_CLASS,
            combined,
            "reported condition (reached via the real entry point) must name the "
            f"artifact class ('{_ABSENT_ARTIFACT_CLASS}').\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
