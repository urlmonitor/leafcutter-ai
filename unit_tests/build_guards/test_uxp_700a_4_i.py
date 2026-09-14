"""
MODULE: test_uxp_700a_4_i
GOAL: Mutation-sensitivity proof for the build's from-scratch record check
    (UXP-700a-4): removing exactly one file that the checker reads before
    checking begins must turn the build red and name that file, while every
    other build check keeps its verdict, and restoring the file returns the
    build to green with no other change.
BUSINESS CONTEXT: UXP-700a-4-i is the negative control for UXP-700a-4. A guard
    that never refuses anything passes every test that only feeds it good
    input, so this record has to prove the check can actually fail — and that
    the isolation clause (only this check turns red) is real, not "the whole
    build fails loudly", which would be indistinguishable from a broken build.

IMPLEMENTATION STATUS (as of authoring, 2026-09-09): UXP-700a-4 — "the build
    installs a record into a throwaway empty project and runs that record's
    checker against it" — has NOT been implemented. As of this writing every
    ticket in EPIC-TruthfulProjectRecord that this ticket depends on
    (UXP-700a, UXP-700a-1, UXP-700a-4 — tickets 02-08) carries zero agent
    sign-offs. scripts/build_phases.py::build_product_truth() today only
    copies docs/product-truth/{scripts/*.py,schemas/*.json} into a consumer
    install; it performs no post-deploy smoke-test of the deployed record and
    has no per-file failure mode at all — a missing source file is silently
    not copied, and build.py still exits 0. These tests therefore describe
    the REQUIRED future behaviour and are expected to be RED until UXP-700a-4
    (and the isolation/naming behaviour this ticket adds on top of it) is
    implemented. Whoever implements UXP-700a-4 / UXP-700a-4-i must either
    satisfy these tests as written, or — if the eventual mechanism differs
    from the schema-file mutation modeled here — update the mutation target
    so it still isolates exactly one start-up input of the record's checker
    (docs/product-truth/scripts/validate_product_truth.py).

ARCHITECTURE: Reachability entry point resolved to ``scripts/build.py``,
    invoked via ``_build.main(["--target-dir", ...])`` (main() with real
    argv — the same pattern already established by
    unit_tests/test_bp_900g_4.py and unit_tests/test_build_guard_real_package.py
    for this exact script), justified directly by UXP-700a-4's own criteria
    text: "When the tooling's own build runs...". The mutation isolates ONE
    file from the two source groups build_product_truth() deploys today
    (docs/product-truth/schemas/*.json), because
    docs/product-truth/scripts/validate_product_truth.py declares JSON-Schema
    validation a MANDATORY, checked-before-any-artifact-row startup
    dependency (see that module's docstring, check #1 and the
    "SCHEMA VALIDATION IS MANDATORY" paragraph). flow.schema.json is one of
    the five schemas build_product_truth() currently deploys. The real repo
    file is moved aside for the duration of one build invocation and restored
    in a ``finally`` block so a test failure never leaves the source tree
    mutated.

    A full real ``build.py --target-dir`` run against this package takes
    several seconds (observed ~8.5s locally), over the 5-second per-test
    budget in testing_context — hence the ``_MANUAL`` suffix on every test
    function here (see performance-constraints rule in the test-writer
    skill). They are still meant to run (in CI or on demand), just not under
    the tight default budget.
"""
# @ac-tag: UXP-700a-4-i

from __future__ import annotations

import importlib.util
import io
import shutil
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Iterator

# ---------------------------------------------------------------------------
# Path setup — make scripts/ importable regardless of working directory.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _load_build_module() -> Any:
    """Load scripts/build.py by path (mirrors unit_tests/test_bp_900g_4.py).

    ``scripts/build.py`` shares its module name with the installed PyPI
    ``build`` package (the PEP 517 build frontend). Loading by path sidesteps
    that name collision rather than depending on sys.path insertion order.
    """
    build_py_path = _SCRIPTS_DIR / "build.py"
    spec = importlib.util.spec_from_file_location(
        "scripts_build_under_test_uxp700a4i", build_py_path
    )
    assert spec is not None and spec.loader is not None, f"could not load spec for {build_py_path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_build = _load_build_module()

# The real package_root used throughout these tests — behavior must be proven
# against the actual deployable source, not a synthetic stand-in.
_REAL_PACKAGE_ROOT = _REPO_ROOT

# The concrete file used as "one file the checker reads before checking
# begins". See ARCHITECTURE note above for why this file was chosen.
_REQUIRED_FILE = _REAL_PACKAGE_ROOT / "docs" / "product-truth" / "schemas" / "flow.schema.json"


@contextmanager
def _one_required_file_removed(path: Path) -> Iterator[Path]:
    """Temporarily remove exactly one required file, then restore it.

    Restoration happens in ``finally`` so an assertion failure inside the
    ``with`` block never leaves the real source tree mutated. This is the
    "Named mutation: delete one entry from what the deploy phase writes"
    described in UXP-700a-4-i's AC notes.
    """
    assert path.is_file(), (
        f"Precondition failed: {path} does not exist before the mutation — "
        "this test cannot prove anything about removing a file that was "
        "never there to begin with. If this schema was renamed/moved, "
        "update _REQUIRED_FILE above."
    )
    backup = path.with_suffix(path.suffix + ".uxp700a4i-bak")
    assert not backup.exists(), (
        f"stale backup {backup} already exists — a prior interrupted run "
        "may have crashed before restoring. Manually rename it back to "
        f"{path} before re-running these tests."
    )
    shutil.move(str(path), str(backup))
    try:
        yield path
    finally:
        shutil.move(str(backup), str(path))


def _run_build(target_dir: Path) -> tuple[int, str, str]:
    """Invoke the real ``build.py`` entry point with real argv.

    Captures stdout/stderr into in-memory buffers (never redirected to an OS
    file handle) specifically to avoid a Windows console-encoding crash
    (``UnicodeEncodeError`` on box-drawing/checkmark characters build.py
    prints) that is unrelated to the behaviour under test.

    Returns:
        (exit_code, stdout_text, stderr_text)
    """
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        exit_code = _build.main(["--target-dir", str(target_dir)])
    return exit_code, out.getvalue(), err.getvalue()


class TestUxp700a4iRemovingOneRequiredFileFailsTheBuild(unittest.TestCase):
    """Removing one required file turns the from-scratch record check red,
    and no other check, per UXP-700a-4-i."""

    def test_removing_one_required_file_fails_the_build_naming_it_MANUAL(self) -> None:
        # covers: UXP-700a-4-i
        # angle: failure
        """AC-1: the build fails and the failure names that file.

        RED TODAY: build.py has no from-scratch record check at all
        (UXP-700a-4 is not implemented), so build_product_truth() silently
        ships fewer files instead of failing the build. This assertion will
        only pass once UXP-700a-4's build-time smoke-test detects the
        missing start-up input and names it in the failure output.

        MANUAL: exercises the real full ``build.py --target-dir`` (~8.5s
        locally), over the 5s default budget.
        """
        with tempfile.TemporaryDirectory(prefix="uxp700a4i_target_") as tmp:
            target_dir = Path(tmp) / "consumer"
            target_dir.mkdir()

            with _one_required_file_removed(_REQUIRED_FILE) as missing_path:
                exit_code, out, err = _run_build(target_dir)

                rel = missing_path.relative_to(_REAL_PACKAGE_ROOT).as_posix()

                self.assertNotEqual(
                    exit_code,
                    0,
                    f"build.py exited 0 with {rel} removed from the install. "
                    "UXP-700a-4's from-scratch record check must fail the "
                    "build when a file its checker reads before checking "
                    "begins was not installed (UXP-700a-4-i AC-1).",
                )
                combined_output = out + err
                self.assertIn(
                    rel,
                    combined_output,
                    f"build.py failed (exit {exit_code}) but its output did "
                    f"not name the missing file {rel!r}. AC-1 requires the "
                    "failure to name the file, not merely fail. Output was:\n"
                    f"{combined_output}",
                )

    def test_removing_one_required_file_leaves_other_build_checks_green_MANUAL(self) -> None:
        # covers: UXP-700a-4-i
        # angle: boundary
        """AC-2: no other check in the build changes its verdict.

        Uses ``_check_script_reference_guard`` — a real, independent build
        guard already exercised by unit_tests/test_build_guard_real_package.py
        — as the "other check" whose verdict must be unaffected by removing
        one product-truth schema file. Called directly (not through
        ``main()``) because this test's job is isolation, not reachability;
        the reachability angle is covered by the third test in this file.

        RED TODAY: there is no isolated "from-scratch record check" verdict
        distinct from the rest of the build yet, so there is nothing here to
        actually isolate. This test can only start passing meaningfully once
        UXP-700a-4 gives the record check its own verdict, separate from
        unrelated guards — which is exactly the isolation clause it proves.

        MANUAL: shares the real-build fixture cost with its siblings in this
        file even though the guard call itself is cheap.
        """
        baseline_verdict = _build._check_script_reference_guard(_REAL_PACKAGE_ROOT)

        with _one_required_file_removed(_REQUIRED_FILE):
            mutated_verdict = _build._check_script_reference_guard(_REAL_PACKAGE_ROOT)

        self.assertEqual(
            baseline_verdict,
            mutated_verdict,
            "_check_script_reference_guard's verdict changed after removing "
            "one product-truth schema file "
            f"({baseline_verdict!r} -> {mutated_verdict!r}). Only the "
            "from-scratch record check UXP-700a-4 introduces may change "
            "verdict when this specific file is missing; every other build "
            "check must be unaffected (UXP-700a-4-i AC-2).",
        )

    def test_uxp_700a_4_i_reachable_from_entry_point_MANUAL(self) -> None:
        # covers: UXP-700a-4-i
        # angle: reachability
        """AC-1/AC-3: reachable through the real production entry point.

        REQUIRED — invokes ``scripts/build.py`` via ``_build.main()`` with
        real argv (not an inner helper function) twice: once with the
        required file present (must stay green, positive control matching
        AC-3's "restoring the file returns the build to passing") and once
        with it removed (must turn red). The two runs proving different
        outcomes is the evidence that the CLI a real user runs actually
        surfaces this behaviour, not merely that some internal function
        returns a particular value when called directly.

        Entry-point resolution (BP-1100g-2): ``scripts/build.py`` is named
        directly by UXP-700a-4's own criteria text ("When the tooling's own
        build runs..."), and it is a real, already-existing CLI script
        (``argparse``, ``if __name__ == "__main__":`` guard) — Step 1 rule 1
        (CLI script) of the Reachability Entry-Point Resolution procedure.
        See this ticket's completion_manifest.reachability_entry_point_answer
        for the recorded hand-off.

        RED TODAY: build.py performs no from-scratch record check, so both
        runs currently exit 0 — the two outcomes do not differ, which is
        exactly the missing behaviour this test exists to force into
        existence.

        MANUAL: two full build.py invocations (~17s combined locally).
        """
        with tempfile.TemporaryDirectory(prefix="uxp700a4i_baseline_") as tmp_base:
            baseline_target = Path(tmp_base) / "consumer"
            baseline_target.mkdir()
            baseline_exit_code, _, _ = _run_build(baseline_target)

        self.assertEqual(
            baseline_exit_code,
            0,
            "Positive control failed: build.py did not exit 0 with every "
            "required file present. The isolation clause (AC-3: restoring "
            "the file returns the build to passing) cannot be evaluated if "
            "the unmutated baseline is not itself green.",
        )

        with tempfile.TemporaryDirectory(prefix="uxp700a4i_mutated_") as tmp_mut:
            mutated_target = Path(tmp_mut) / "consumer"
            mutated_target.mkdir()
            with _one_required_file_removed(_REQUIRED_FILE):
                mutated_exit_code, _, _ = _run_build(mutated_target)

        self.assertNotEqual(
            mutated_exit_code,
            baseline_exit_code,
            "build.py --target-dir produced the SAME exit code "
            f"({baseline_exit_code!r}) whether or not "
            f"{_REQUIRED_FILE.relative_to(_REAL_PACKAGE_ROOT).as_posix()} was "
            "present. The real CLI entry point a consumer install actually "
            "runs must observably react to the missing start-up input — an "
            "internal function that would detect this but is never called "
            "from main() does not satisfy UXP-700a-4-i.",
        )


if __name__ == "__main__":
    unittest.main()
