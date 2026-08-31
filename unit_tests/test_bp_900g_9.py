"""
MODULE: unit_tests/test_bp_900g_9.py
GOAL: AC BP-900g-9 — a declared deploy phase entry whose source file cannot
    be found at the path the declaration names must fail the build instead
    of logging a warning and continuing. The build must exit non-zero, name
    the phase / entry / source_path, report EVERY unresolvable entry in one
    run (not only the first), and a zero-entry or fully-resolving
    declaration must still build clean.
BUSINESS CONTEXT: At HEAD 339b0981c the build_ac_store deploy loop in
    scripts/build_phases.py logged a warning and continued when a declared
    source was missing, so a consumer install could silently ship without a
    declared file while the build reported success. This is the same
    fail-open shape BP-900g-8 closed for undeclared dependencies, in the
    same loop. See docs/acceptance-criteria/build_pipeline/
    BP-900-deployment-completeness/BP-900g-9.yaml.
IMPLEMENTATION (committed at be12d44b2, ALREADY LANDED — see REBUILD NOTE
    below): build_phases.DeploySourceMissingError(FileNotFoundError) carries
    a ``.failures`` list of ``{phase, entry, source_path}`` dicts, one per
    unresolvable declared entry. Eight deploy sites accumulate every
    unresolvable entry and raise once at the end rather than warn-and-
    continue: build_ac_store, build_workflow_tools, build_knowledge_scripts,
    build_agent_support_scripts (two loops sharing one raise),
    _deploy_fast_lane_release_dependency, build_ac_store_docs,
    build_product_truth, build_build_orchestration_scripts. main() catches
    DeploySourceMissingError around _run_phases(), prints each failure to
    stderr, and returns 1.
THE CENTRAL CONSTRAINT (per the AC's it_requirements.constraints — the
    single most important one): THE OBSERVABLE IS THE EXIT CODE, NOT THE LOG
    TEXT. The pre-fix behaviour already logs the missing source accurately
    and completely; a test asserting only that the failure text is present
    is green against BOTH the fixed and the broken implementation. Every
    assertion below is on the exit code, the accumulated ``.failures``
    records, or the SET of names in a single failure report — never on log
    output alone.
REBUILD NOTE (2026-08-31): This file is a from-scratch rewrite. The
    original was lost when a parallel session deleted the worktree it was
    written in while a test run was in flight; nothing had been staged, so
    no blob survived (376 dangling blobs scanned, no hit). The production
    code this file specifies (be12d44b2) DID survive (recovered byte-for-
    byte from a pytest scratch copy) and is already committed and merged
    into this branch, so ordinary TDD is not available here — these tests
    are written against already-working code. To avoid the "a test written
    against working code is satisfied by construction" trap, every test
    below was verified to FAIL against a scratch copy of the package tree
    with scripts/build_phases.py and scripts/build.py reverted to their
    be12d44b2^ (pre-fix) state, and to PASS against the real, unmodified
    tree. See the ticket's original test-writer sign-off (## Comments,
    2026-08-26 16:05) for the recovered ``red_baseline`` this rebuild
    reproduces:
      - test_..._missing_declared_source_produces_a_failure_record_not_a_warning:
        pre-fix error was AttributeError: module 'build_phases' has no
        attribute 'DeploySourceMissingError'.
      - test_..._build_subprocess_exits_non_zero_on_a_declared_but_absent_source:
        pre-fix error was "AssertionError: 0 == 0" — the subprocess build
        exited 0 while mark_ac_done.py's declared source was absent.
      - test_..._three_unresolvable_entries_are_all_named_in_one_run:
        pre-fix error was "AssertionError: 0 == 0" with all three of
        mark_ac_done.py / scan_ac_orphans.py / ac_prioritizer.py named in
        the (non-blocking) pre-fix warning output — confirming this test
        discriminates on exit code, not log text.
      - test_..._empty_and_fully_resolving_declarations_both_build_clean:
        NOT part of the red baseline. This is a designed pre-existing-green
        control (see its own docstring) — it passes against both
        implementations by construction.
ARCHITECTURE / EXERCISE STRATEGY: Test 1 imports the real, source-tree
    ``build_phases`` module directly (via a scripts/-on-sys.path import, the
    same pattern unit_tests/test_bp_900g_6_paths.py already uses in this
    suite) and monkeypatches ``AC_STORE_DEPLOY_MAP`` to a single fake entry
    — the criterion angle, exercising the accumulation logic in isolation.
    Tests 2-4 build a SCRATCH COPY of the whole package tree
    (templates/scripts/config, plus docs/product-truth — see
    ``_build_synthetic_package`` below, adapted from the proven helper in
    unit_tests/build_guards/test_bp_100k_2.py) under ``tempfile.mkdtemp()``
    and invoke ``python scripts/build.py --target-dir <workspace>`` as a
    REAL SUBPROCESS against that copy — the reachability angle the AC
    demands explicitly ("a test that calls the phase's helper directly does
    not satisfy this criterion, because the fail-open branch is reached
    through the build's own iteration, not through the helper"). The REAL,
    committed ``scripts/build_phases.py`` and ``scripts/build.py`` in this
    worktree are NEVER mutated by any test in this file — every mutation
    (a deleted source file, or a text substitution) happens on a throwaway
    ``shutil.copytree`` copy under the system temp root, registered for
    cleanup in ``tearDown``. This is a deliberate departure from
    unit_tests/test_bp_900g_8.py's sibling reachability test, which mutates
    ``scripts/build_phases.py`` in the real worktree with a try/finally
    restore — that pattern nearly destroyed 1,177 lines of unpushed work
    when a test run and a worktree deletion raced, which is the same
    failure mode that made this very file's original copy unrecoverable.
"""
# @ac-tag: BP-900g-9

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES_DIR = _REPO_ROOT / "templates"
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_CONFIG_DIR = _REPO_ROOT / "config"

# Make the REAL, source-tree build_phases importable for test 1's in-process
# accumulation check (mirrors unit_tests/test_bp_900g_6_paths.py's pattern).
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build_phases as _bp  # noqa: E402 — after sys.path setup

_SUBPROCESS_TIMEOUT_SECONDS = 180

# ---------------------------------------------------------------------------
# Synthetic package helper. Adapted from (not imported from, to keep this
# file independent of the build_guards package)
# unit_tests/build_guards/test_bp_100k_2.py's _build_synthetic_full_package /
# _derive_additional_package_root_dirs, added there for the exact fixture-
# staleness finding this AC's own fail-closed guard surfaced: build_
# product_truth declares docs/product-truth as a source, and a fixture that
# only copies templates/scripts/config has no docs/ at all, which this
# guard (correctly) now treats as three missing declared entries rather
# than silently shipping nothing.
# ---------------------------------------------------------------------------

_WHOLESALE_COPIED_TOP_DIRS = {"templates", "scripts", "config"}
_PACKAGE_ROOT_CHAIN_RE = re.compile(r'PACKAGE_ROOT((?:\s*/\s*"[^"/]+")+)')
_CHAIN_SEGMENT_RE = re.compile(r'"([^"/]+)"')


def _derive_additional_package_root_dirs() -> list[Path]:
    """Find real-package source directories a deploy phase declares that the
    wholesale templates/scripts/config copy below does not cover (e.g.
    ``docs/product-truth``), by scanning the REAL build_phases.py source
    text for ``PACKAGE_ROOT / "seg1" / "seg2" / ...`` literal chains and
    keeping only those resolving to a real, on-disk directory outside the
    three wholesale dirs. Deriving this rather than hardcoding it is what
    keeps this fixture from going stale the same way test_bp_100k_2.py's
    "full package" fixture did.
    """
    try:
        text = (_SCRIPTS_DIR / "build_phases.py").read_text(encoding="utf-8")
    except OSError:
        return []

    seen: dict[Path, None] = {}
    for chain_match in _PACKAGE_ROOT_CHAIN_RE.finditer(text):
        segments = _CHAIN_SEGMENT_RE.findall(chain_match.group(1))
        if not segments or segments[0] in _WHOLESALE_COPIED_TOP_DIRS:
            continue
        candidate = Path(*segments)
        if candidate in seen:
            continue
        if (_REPO_ROOT / candidate).is_dir():
            seen[candidate] = None
    return list(seen)


def _build_synthetic_package(workspace: Path) -> Path:
    """Copy the real templates/, scripts/, config/ trees (plus any other
    directory a deploy phase declares as a source) into a synthetic package
    root under *workspace*, at the same relative depth self-hosting
    production uses (``package_root.parent == target_root`` passed to
    ``build.py``), so build.py's own ``PACKAGE_ROOT = Path(__file__)
    .resolve().parent.parent`` arithmetic behaves exactly as it does for a
    real ``python scripts/build.py --target-dir .`` run.

    Args:
        workspace: Temp directory to build the synthetic layout inside.
            This SAME directory is passed as ``--target-dir`` to build.py by
            callers, mirroring the self-hosting layout.

    Returns:
        Absolute path to the synthetic package root
        (``<workspace>/leafcutter-ai``).
    """
    pkg_root = workspace / "leafcutter-ai"
    shutil.copytree(
        _TEMPLATES_DIR, pkg_root / "templates", ignore=shutil.ignore_patterns("__pycache__")
    )
    shutil.copytree(
        _SCRIPTS_DIR, pkg_root / "scripts", ignore=shutil.ignore_patterns("__pycache__")
    )
    shutil.copytree(
        _CONFIG_DIR, pkg_root / "config", ignore=shutil.ignore_patterns("__pycache__")
    )
    for rel_path in _derive_additional_package_root_dirs():
        dest = pkg_root / rel_path
        if not dest.exists():
            shutil.copytree(
                _REPO_ROOT / rel_path, dest, ignore=shutil.ignore_patterns("__pycache__")
            )
    return pkg_root


def _run_build(pkg_root: Path, workspace: Path) -> subprocess.CompletedProcess:
    """Run the scratch copy's ``scripts/build.py --target-dir <workspace>``
    as a real subprocess — the production entry point, not the phase helper.
    """
    return subprocess.run(
        [sys.executable, str(pkg_root / "scripts" / "build.py"), "--target-dir", str(workspace)],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        cwd=str(workspace),
    )


class TestBp900g9(unittest.TestCase):
    """AC BP-900g-9 — a declared deploy entry whose source is missing fails
    the build instead of warning and continuing.
    """

    def setUp(self) -> None:
        self._tmp_dirs: list[str] = []

    def tearDown(self) -> None:
        for d in self._tmp_dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _mkdtemp(self) -> Path:
        d = tempfile.mkdtemp(prefix="bp900g9_")
        self._tmp_dirs.append(d)
        return Path(d)

    # -- Test 1: unit / criterion -------------------------------------------

    def test_bp_900g_9_missing_declared_source_produces_a_failure_record_not_a_warning(
        self,
    ) -> None:
        # covers: BP-900g-9
        # angle: criterion
        """The deploy iteration, given a declaration entry whose source path
        does not exist, accumulates a failure record carrying phase, entry
        and source_path, and raises DeploySourceMissingError instead of
        logging a warning and returning a success count. Asserts the
        record's fields and that the run's verdict is failure — never that a
        warning string was logged. Implemented by
        build_phases.build_ac_store (be12d44b2).
        """
        fake_entry = (
            "scripts/ac_store/does_not_exist_bp900g9.py",
            "does_not_exist_bp900g9.py",
        )
        target_root = self._mkdtemp()

        with mock.patch.object(_bp, "AC_STORE_DEPLOY_MAP", (fake_entry,)):
            with self.assertRaises(_bp.DeploySourceMissingError) as ctx:
                _bp.build_ac_store(target_root, {}, dry_run=True, force=False)

        # The verdict: a typed failure, not a bare exception and not a
        # logged warning with a returned success count.
        self.assertIsInstance(ctx.exception, FileNotFoundError)

        failures = ctx.exception.failures
        self.assertEqual(
            len(failures), 1, f"expected exactly one failure record, got: {failures}"
        )
        expected_source_path = str(_bp.PACKAGE_ROOT / fake_entry[0])
        self.assertEqual(
            failures[0],
            {
                "phase": "build_ac_store",
                "entry": fake_entry[1],
                "source_path": expected_source_path,
            },
        )

    # -- Test 2: integration / reachability (must_block) ---------------------

    def test_bp_900g_9_build_subprocess_exits_non_zero_on_a_declared_but_absent_source(
        self,
    ) -> None:
        # covers: BP-900g-9
        # angle: reachability
        """PRODUCTION ENTRY POINT, must_block. Deletes the source file behind
        one declared AC_STORE_DEPLOY_MAP entry (mark_ac_done.py) from a
        scratch copy of the package tree, leaving the declaration itself
        intact, and runs ``python scripts/build.py --target-dir <tmp>`` as a
        real subprocess. Asserts a non-zero exit and that the output names
        the phase, the entry, and the source path. Test 1 above — calling
        build_ac_store() directly — does NOT satisfy this angle on its own:
        the fail-open branch is reached through build.py's own iteration in
        main(), and a helper-level test alone would stay green even if the
        iteration that calls it still swallowed the result.
        """
        workspace = self._mkdtemp()
        pkg_root = _build_synthetic_package(workspace)
        missing_source = pkg_root / "scripts" / "ac_store" / "mark_ac_done.py"
        self.assertTrue(
            missing_source.is_file(),
            "fixture precondition: mark_ac_done.py must exist in the scratch "
            "copy before deletion, or this test proves nothing",
        )
        missing_source.unlink()

        result = _run_build(pkg_root, workspace)

        self.assertNotEqual(
            result.returncode,
            0,
            "build.py --target-dir exited 0 while a declared AC_STORE_DEPLOY_MAP "
            "entry's source file (mark_ac_done.py) was absent from the package "
            f"tree.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        combined_output = result.stdout + result.stderr
        self.assertIn("build_ac_store", combined_output)
        self.assertIn("mark_ac_done.py", combined_output)
        self.assertIn(str(missing_source), combined_output)

    # -- Test 3: integration / boundary (false-positive control) -------------

    def test_bp_900g_9_empty_and_fully_resolving_declarations_both_build_clean(
        self,
    ) -> None:
        # covers: BP-900g-9
        # angle: boundary
        """The zero/all controls through the same subprocess entry point.

        THIS TEST IS A DESIGNED PRE-EXISTING-GREEN CONTROL, NOT PART OF THE
        RED BASELINE. It passes against both the pre-fix (warn-and-continue)
        and post-fix (fail-closed) implementations by construction: in both
        halves every declared entry either does not exist at all (zero) or
        resolves (all), so there is nothing for either implementation to
        disagree about. Its purpose is the false-positive check the AC
        names explicitly: proving the fail-closed flip does not turn
        "nothing to ship" or "everything shipped" into a build failure.

        Half A (zero entries): a real, unmodified AC_STORE_DEPLOY_MAP cannot
        be emptied for this half — doing so (verified empirically) trips two
        unrelated, already-shipped preflight guards in build.py's main()
        that run BEFORE build_ac_store's own loop is ever reached
        (_check_script_reference_guard, BP-900c-2, and
        _check_intra_package_closure_guard, BP-900g-8), because every real
        AC-store deploy entry is referenced by a live template or
        transitively resolved by another already-deployed script. Instead
        this half edits the SCRATCH COPY's build_workflow_tools()
        deploy_scripts list to an empty list via an exact source-text
        substitution — build_workflow_tools's 7-script list has no such
        entanglement (nothing outside build.py itself imports those
        scripts). The REAL, committed build_phases.py is never touched.

        Half B (fully resolving): runs an unmodified scratch copy, whose
        real declared entries across every deploy phase all resolve.
        """
        # -- Half A: zero entries (build_workflow_tools, scratch-copy-local) --
        workspace_a = self._mkdtemp()
        pkg_root_a = _build_synthetic_package(workspace_a)
        build_phases_path = pkg_root_a / "scripts" / "build_phases.py"
        original_text = build_phases_path.read_text(encoding="utf-8")
        needle = (
            "    deploy_scripts = [\n"
            '        "add_component.py",\n'
            '        "knowledge_query.py",\n'
            '        "set_ticket_status.py",\n'
            '        "ticket_prioritizer.py",\n'
            '        "port_registry.py",\n'
            '        "live_surface_startup.py",\n'
            '        "generate_doc_index.py",\n'
            "    ]\n"
        )
        self.assertIn(
            needle,
            original_text,
            "fixture precondition: build_workflow_tools's deploy_scripts literal "
            "list must match exactly, or this substitution silently no-ops and "
            "Half A stops testing the zero-entries case at all",
        )
        build_phases_path.write_text(
            original_text.replace(needle, "    deploy_scripts = []\n"),
            encoding="utf-8",
        )

        result_a = _run_build(pkg_root_a, workspace_a)
        self.assertEqual(
            result_a.returncode,
            0,
            "a zero-entry deploy declaration must build clean ('nothing to ship' "
            f"is success, not failure).\nstdout:\n{result_a.stdout}\n"
            f"stderr:\n{result_a.stderr}",
        )

        # -- Half B: fully resolving (unmodified scratch copy) --
        workspace_b = self._mkdtemp()
        pkg_root_b = _build_synthetic_package(workspace_b)

        result_b = _run_build(pkg_root_b, workspace_b)
        self.assertEqual(
            result_b.returncode,
            0,
            "an unmodified declaration whose entries all resolve must build "
            f"clean ('everything shipped' is success).\nstdout:\n{result_b.stdout}\n"
            f"stderr:\n{result_b.stderr}",
        )

    # -- Test 4: integration / boundary (the many case) -----------------------

    def test_bp_900g_9_three_unresolvable_entries_are_all_named_in_one_run(
        self,
    ) -> None:
        # covers: BP-900g-9
        # angle: boundary
        """Deletes the source files behind THREE separate declared
        AC_STORE_DEPLOY_MAP entries and runs the build ONCE. Asserts all
        three are named in the single failure report — not one, and not
        one-per-run. A guard that halts at the first finding passes test 2
        above (one missing entry) and fails here, which is the only way to
        tell "collect, then fail" apart from "fail on first" — halting at
        the first turns a set of N stale entries into N build-fix-build
        cycles, and every intermediate build is green.
        """
        workspace = self._mkdtemp()
        pkg_root = _build_synthetic_package(workspace)
        missing_names = ["mark_ac_done.py", "scan_ac_orphans.py", "ac_prioritizer.py"]
        for name in missing_names:
            source = pkg_root / "scripts" / "ac_store" / name
            self.assertTrue(
                source.is_file(),
                f"fixture precondition: {name} must exist in the scratch copy "
                "before deletion, or this test proves nothing",
            )
            source.unlink()

        result = _run_build(pkg_root, workspace)

        self.assertNotEqual(
            result.returncode,
            0,
            "build.py --target-dir exited 0 while THREE declared "
            f"AC_STORE_DEPLOY_MAP entries' sources were absent ({missing_names})."
            f"\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        combined_output = result.stdout + result.stderr
        for name in missing_names:
            self.assertIn(
                name,
                combined_output,
                f"{name} must be named in the single failure report alongside "
                "the other two missing entries — a guard that halts at the "
                f"first finding would report only one of the three.\n"
                f"Output:\n{combined_output}",
            )


if __name__ == "__main__":
    unittest.main()
