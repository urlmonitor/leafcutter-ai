"""
MODULE: unit_tests/build_guards/test_acd_2100d_2.py
GOAL: ACD-2100d-2 -- a repair that lives ONLY in an installed output file
    (never in the source template it was generated from) must be reported by
    check_output_drift.py, must be named, must keep the change out of a
    "delivered" (i.e. commit-passing) state while the divergence stands, and
    must be shown to be a real content question -- not a raw byte comparison
    -- by re-running the installer over the same working copy and observing
    the repair actually get removed.
    See docs/acceptance-criteria/ac-driven-dev/ACD-2100-entry-point-unblocked/
    ACD-2100d-2.yaml.
BUSINESS CONTEXT: KI-ACD-004 documented a repair patched by hand into a
    DEPLOYED copy on 2026-08-18 that build.py silently overwrote on the next
    run -- the repair lived only in build output, never in its source
    template, and nothing reported that fact before the overwrite. This
    module locks in the behaviour that makes that class of loss visible
    instead of silent.
ARCHITECTURAL ANOMALY RECORDED BY architect-review (2026-08-26, see this
    ticket's sign-off comment): reading this worktree's HEAD at commit
    83737a447 shows check_output_drift.py's ``_derive_scan_dirs()`` already
    derives its scan set from the manifest's own ``output_mappings`` keys
    (not a hardcoded directory list), the not-in-mapping branch already
    reports GAP/EXEMPT (never a silent skip), and BOTH copies of
    commit_guardian.json (the self-hosted ``scripts/commit_guardian/`` copy
    and its ``templates/scripts/commit_guardian/`` source mirror) already
    register check-output-drift with ``always_run: true`` instead of the
    stale hardcoded ``files:`` prefix list that used to make the hook never
    fire at all. All four of those fixes are attributed, in
    check_output_drift.py's own DECISION HISTORY block, to
    EPIC-BuildPipelinePhantomRemediation review rounds dated 2026-08-25/26 --
    i.e. concurrent work sharing this branch already satisfies this AC's
    behavioural requirements, independently of this ticket.

    A behavioural spot-check performed here (2026-08-26, before authoring any
    test) against the REAL, unedited fixture-building helpers in
    ``test_bp_100k_2.py`` (never a hand-typed guess -- see that module's own
    "spot-check the real data format" discipline) confirmed the anomaly
    directly:
      - a fresh deploy of a template containing real ``{{...}}`` placeholders
        (``templates/agents/architect-review.md``) produces a deployed file
        whose raw bytes DIFFER from the raw template bytes, and the hook
        still reports the run clean (returncode 0, no GAP/DRIFT line for
        that key) -- confirming the check is not a raw byte comparison
        (test 4 below).
      - hand-editing a deployed, correctly-registered output produces
        returncode 1, a BLOCKED block, and the exact output key in the
        combined output (tests 1-2 below).
      - re-running the real ``build_agents()`` installer phase over the same
        working copy afterwards restores the file to the exact bytes it had
        before the hand-edit -- the repair is gone (test 3 below).

    RED BASELINE STATUS -- HONEST DEVIATION FROM THE USUAL CONTRACT: because
    the behaviour these tests assert is ALREADY correct on this branch (per
    the anomaly above), all four tests below pass on first run with NO
    production change. This is the documented TDD-order exception in this
    repo's own CLAUDE.md ("TDD Order -- test-writer Must Precede
    python-coder": "If test-writer runs and finds the target suite already
    green ... that is a TDD-order violation, not a pass -- document it in
    the ticket and do NOT mark the ticket TDD-compliant."). It is recorded
    here, and in the ticket's test-writer sign-off comment, rather than
    silently reported as a normal red-to-green cycle. These tests are not
    vacuous: each asserts against the SAME real, on-disk artifact and the
    SAME `main()`/`check_output_drift()` entry point a hand-edited working
    copy would actually exercise, and each was verified (by hand, before
    authoring) to have failed against the pre-2026-08-25 code shape
    described in check_output_drift.py's own DECISION HISTORY (hardcoded
    scan dirs skipping the deployed file entirely; a hardcoded
    ``files:`` trigger in commit_guardian.json that never matched a real
    ``.claude/*`` path; a duplicated, permissive ``main()`` implementation
    that never called ``check_output_drift()`` at all). Their purpose now is
    to LOCK IN that fix under this AC's own language so a future regression
    (e.g. someone re-introducing a hardcoded scan-dir list) is caught by a
    test that traces directly to ACD-2100d-2, not only to the differently-ID'd
    BP-100k-* tests that happened to catch it historically.
ARCHITECTURE / EXERCISE STRATEGY: imports ``test_bp_100k_2.py`` fresh, by
    file path, under a private module name (same discipline
    ``test_bp_100k_8.py`` already uses for the identical reason: never
    re-typed, never reused via a bare ``sys.modules`` cache entry) and calls
    its REAL ``_build_synthetic_full_package``, ``_load_pkg_modules``,
    ``_deploy_agents_and_write_manifest``, ``_deploy_hook``, and ``_run_hook``
    helpers directly. No hand-typed fixture stands in for a real deployed
    tree or a real invocation of the hook's own ``main()`` entry point.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEST_BP_100K_2_PATH = Path(__file__).resolve().parent / "test_bp_100k_2.py"

_UNIQUE_COUNTER = [0]


def _load_bp100k2_module() -> types.ModuleType:
    """Load ``test_bp_100k_2.py`` fresh, by file path, under a unique name.

    Mirrors ``test_bp_100k_8.py``'s own ``_load_bp100k2_module`` exactly:
    never reused across tests via a shared ``sys.modules`` bare-name entry,
    so each call gets its own fully independent module object (and its own
    independent internal ``_UNIQUE_COUNTER`` for ITS ``_load_fresh_module``
    calls).

    Returns:
        The freshly executed ``test_bp_100k_2`` module object.
    """
    _UNIQUE_COUNTER[0] += 1
    unique_name = f"_acd2100d2_test_bp_100k_2_{_UNIQUE_COUNTER[0]}"
    spec = importlib.util.spec_from_file_location(unique_name, _TEST_BP_100K_2_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# ---------------------------------------------------------------------------
# Descriptor 1 (criterion): the installed file's own repair is reported and
# named.
# ---------------------------------------------------------------------------


class TestInstalledRepairIsReportedAndNamed(unittest.TestCase):
    """ACD-2100d-2 criterion angle: a working copy where the installed file
    carries a change its source does not must be reported, by name."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.bp2 = _load_bp100k2_module()
        self.pkg_root = self.bp2._build_synthetic_full_package(self.workspace)

    def test_installed_file_carrying_a_repair_its_source_lacks_is_reported(self) -> None:
        # covers: ACD-2100d-2
        self.bp2._deploy_agents_and_write_manifest(self.workspace, self.pkg_root)

        deployed_file = self.workspace / ".claude" / "agents" / "README.md"
        self.assertTrue(
            deployed_file.exists(),
            f"setup bug: expected a real deployed file at {deployed_file}",
        )

        # Land a "repair" ONLY in the installed copy -- the source template
        # this file is generated from is never touched, exactly as
        # KI-ACD-004 describes.
        deployed_file.resolve().write_bytes(
            deployed_file.resolve().read_bytes()
            + b"\n<!-- ACD-2100d-2: repair present only in the installed copy -->\n"
        )

        hook_path = self.bp2._deploy_hook(self.workspace, self.bp2._CHECK_OUTPUT_DRIFT_SRC)
        result = self.bp2._run_hook(hook_path, self.workspace)
        combined = result.stdout + result.stderr

        output_key = ".claude/agents/README.md"
        self.assertIn(
            output_key,
            combined,
            msg=(
                "The check must name the file carrying the undelivered "
                f"repair. Combined output:\n{combined}"
            ),
        )
        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "A repair living only in the installed copy must not be "
                f"reported as a clean run. Combined output:\n{combined}"
            ),
        )


# ---------------------------------------------------------------------------
# Descriptor 2 (reachability): the verdict is consumed where "delivered" is
# decided -- a scan-nothing, exit-clean run must fail this test.
# ---------------------------------------------------------------------------


class TestDivergenceIsNotReportedAsDelivered(unittest.TestCase):
    """ACD-2100d-2 reachability angle: the check's own entry point
    (``main()``, invoked exactly as pre-commit would) must be the thing that
    decides the divergent working copy is not delivered -- not merely a
    function that COULD compute the right answer if some other caller asked
    it to."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.bp2 = _load_bp100k2_module()
        self.pkg_root = self.bp2._build_synthetic_full_package(self.workspace)

    def test_change_is_not_reported_as_delivered_while_the_divergence_stands(self) -> None:
        # covers: ACD-2100d-2
        self.bp2._deploy_agents_and_write_manifest(self.workspace, self.pkg_root)
        deployed_file = self.workspace / ".claude" / "agents" / "README.md"
        deployed_file.resolve().write_bytes(
            deployed_file.resolve().read_bytes()
            + b"\n<!-- ACD-2100d-2: repair present only in the installed copy -->\n"
        )

        hook_path = self.bp2._deploy_hook(self.workspace, self.bp2._CHECK_OUTPUT_DRIFT_SRC)
        # Invoke exactly the entry point pre-commit invokes -- ``main()`` via
        # ``python <hook>.py`` -- never the internal scan function directly,
        # so a duplicated/dead main() that never calls the real scan (the
        # exact BP-100k-3 regression check_output_drift.py's own DECISION
        # HISTORY records) cannot pass this test by accident.
        result = self.bp2._run_hook(hook_path, self.workspace)
        combined = result.stdout + result.stderr

        # The decisive assertion: a run that examined nothing and exited
        # clean is returncode == 0, which this rejects outright. A run that
        # examined files but reported an UNDECLARED gap (rather than the
        # actual drift) would exit 2, not 1 -- also rejected, since gap !=
        # "the divergent change is blocked from being delivered".
        self.assertEqual(
            1,
            result.returncode,
            msg=(
                "The verdict must be consumed at the point that decides "
                "whether the change is delivered: a divergent working copy "
                "must make the check's own exit code BLOCK (1), not pass "
                "(0) and not merely flag an unrelated coverage gap (2). "
                f"Combined output:\n{combined}"
            ),
        )
        # Prove the block was driven by an actual comparison, not a
        # zero-artifact floor tripping for an unrelated reason (which would
        # also be non-zero but would not be evidence the divergence itself
        # was seen).
        self.assertIn(
            "RESULT verified=",
            combined,
            msg=f"No RESULT line printed -- the run must state what it verified. Combined output:\n{combined}",
        )
        self.assertNotIn(
            "verified=0 ",
            combined,
            msg=(
                "verified=0 would mean nothing was actually compared -- the "
                f"exact 'examined none of them' failure mode this test "
                f"exists to catch. Combined output:\n{combined}"
            ),
        )


# ---------------------------------------------------------------------------
# Descriptor 3 (real_artifact): running the installer over the same working
# copy removes the repair, confirming the report.
# ---------------------------------------------------------------------------


class TestInstallerRunConfirmsReportByRemovingRepair(unittest.TestCase):
    """ACD-2100d-2 real_artifact angle: re-run the REAL installer phase over
    the same on-disk working copy and read the artifact back -- the repair
    must be gone, confirming the report rather than contradicting it."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.bp2 = _load_bp100k2_module()
        self.pkg_root = self.bp2._build_synthetic_full_package(self.workspace)

    def test_running_the_installer_confirms_the_report_by_removing_the_repair(self) -> None:
        # covers: ACD-2100d-2
        config, output_root = self.bp2._deploy_agents_and_write_manifest(
            self.workspace, self.pkg_root
        )
        deployed_file = self.workspace / ".claude" / "agents" / "README.md"
        original_bytes = deployed_file.resolve().read_bytes()
        repair_marker = b"<!-- ACD-2100d-2: repair present only in the installed copy -->"
        deployed_file.resolve().write_bytes(original_bytes + b"\n" + repair_marker + b"\n")

        hook_path = self.bp2._deploy_hook(self.workspace, self.bp2._CHECK_OUTPUT_DRIFT_SRC)
        result_before = self.bp2._run_hook(hook_path, self.workspace)
        self.assertNotEqual(
            0,
            result_before.returncode,
            "setup sanity: the hand-edited working copy must be reported as "
            "divergent before the installer is re-run.",
        )
        self.assertIn(
            repair_marker,
            deployed_file.resolve().read_bytes(),
            "setup sanity: the repair marker must actually be present on disk "
            "before the installer runs.",
        )

        # --- Act: run the REAL installer (build_agents) over the SAME
        # working copy -- no mock, a genuine re-execution of the phase that
        # produced the file in the first place, writing to the same real
        # on-disk path.
        build_helpers_mod, build_phases_mod, config_loader_mod = self.bp2._load_pkg_modules(
            self.pkg_root
        )
        build_phases_mod.build_agents(output_root, config, dry_run=False, force=True)

        # --- Assert: read the real artifact back off disk.
        after_bytes = deployed_file.resolve().read_bytes()
        self.assertNotIn(
            repair_marker,
            after_bytes,
            msg=(
                "Running the installer over the working copy must leave the "
                "installed file WITHOUT the repair -- confirming the report "
                "rather than contradicting it. The repair marker is still "
                f"present after re-install. Bytes tail: {after_bytes[-200:]!r}"
            ),
        )
        self.assertEqual(
            original_bytes,
            after_bytes,
            msg=(
                "The re-installed file must match what the installer "
                "actually generates from the source template, not merely "
                "lack the marker string."
            ),
        )


# ---------------------------------------------------------------------------
# Descriptor 4 (boundary): a generation-only difference is not reported.
# ---------------------------------------------------------------------------


class TestGenerationOnlyDifferenceIsNotReported(unittest.TestCase):
    """ACD-2100d-2 boundary angle: a freshly installed file that differs
    from its raw source template ONLY because generation (placeholder
    expansion) explains the difference must produce no report -- the check
    is not a raw byte comparison against the source template."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.bp2 = _load_bp100k2_module()
        self.pkg_root = self.bp2._build_synthetic_full_package(self.workspace)

    def test_a_generated_file_that_only_differs_by_generation_is_not_reported(self) -> None:
        # covers: ACD-2100d-2
        self.bp2._deploy_agents_and_write_manifest(self.workspace, self.pkg_root)

        # architect-review.md is a real template known to contain
        # {{...}} placeholders (registry-injection substitution — see
        # build_phases.build_agents), unlike README.md which happens to
        # contain none. Using it proves the boundary against a REAL
        # generation transform rather than an identity copy.
        deployed_file = self.workspace / ".claude" / "agents" / "architect-review.md"
        template_file = self.pkg_root / "templates" / "agents" / "architect-review.md"
        self.assertTrue(deployed_file.exists(), f"setup bug: expected {deployed_file}")
        self.assertTrue(template_file.exists(), f"setup bug: expected {template_file}")

        # Setup sanity: the deployed content must genuinely differ from the
        # raw template bytes -- otherwise this test would not distinguish a
        # raw-byte-comparison implementation from a hash-recorded-at-build-
        # time implementation at all.
        self.assertNotEqual(
            template_file.read_bytes(),
            deployed_file.resolve().read_bytes(),
            "setup sanity: generation must actually transform this "
            "template's content (placeholder expansion) for this boundary "
            "test to mean anything.",
        )

        hook_path = self.bp2._deploy_hook(self.workspace, self.bp2._CHECK_OUTPUT_DRIFT_SRC)
        result = self.bp2._run_hook(hook_path, self.workspace)
        combined = result.stdout + result.stderr

        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "A freshly installed file that differs from its raw source "
                "template only because generation explains the difference "
                f"must not be reported as drift. Combined output:\n{combined}"
            ),
        )
        output_key = ".claude/agents/architect-review.md"
        self.assertNotIn(
            f"GAP {output_key}",
            combined,
            msg=f"The generated file must not be reported as an uncomparable gap. Combined output:\n{combined}",
        )
        # Search the WHOLE output, not a 200-char window before output_key.
        # The window was built as
        #     combined.split(output_key)[0][-200:] if output_key in combined else ""
        # which collapses to the empty string whenever output_key is absent --
        # and assertNotIn("BLOCKED", "") can never fail. The absent case is
        # precisely the failure this assertion exists to catch, so the guard
        # went silent exactly when it was needed. Asserting against `combined`
        # is strictly stronger and cannot be satisfied vacuously.
        self.assertNotIn(
            "BLOCKED",
            combined,
            msg=f"The generated file must not be part of a BLOCKED block. Combined output:\n{combined}",
        )


if __name__ == "__main__":
    unittest.main()
