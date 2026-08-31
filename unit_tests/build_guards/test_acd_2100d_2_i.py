"""
MODULE: unit_tests/build_guards/test_acd_2100d_2_i.py
GOAL: ACD-2100d-2-i -- an install that overwrites a generated file whose
    on-disk content has diverged from what the installer would produce (a
    "local edit" made after the last install, per KI-ACD-004) must SAY SO in
    its own output for that run, name the file, still perform the overwrite
    (the install always wins -- this is an announcement, never a refusal or a
    merge), and must NOT say so for any file that was not locally changed.
    See docs/acceptance-criteria/ac-driven-dev/ACD-2100-entry-point-unblocked/
    ACD-2100d-2-i.yaml.
BUSINESS CONTEXT: On 2026-08-18 a hand-applied repair was patched directly
    into a DEPLOYED copy. The next `build.py` run silently discarded it --
    the workaround did not fail loudly, it disappeared, and the operator who
    applied it had every reason to believe it was still in effect. This
    module locks in the fix: the SAME loss must now be visible in the
    installer's own output at the moment it happens.
ARCHITECTURE / EXERCISE STRATEGY: The installer has four independent
    compare-before-write branches (write_file in scripts/build.py; _write and
    _files_content_identical in scripts/build_phases.py; and the
    workflow-script phase's own inline SHA-256 compare, which does NOT route
    through _files_content_identical and is the load-bearing branch per this
    AC's own it_requirements -- it is the path the route's own deployed copy
    takes). To make it impossible for an implementation that instruments only
    the shared text helper to pass by accident, the tests below deliberately
    spread their mutated file across TWO of the four branches:
      - `.claude/workflows/*.js`  -> the workflow-script phase's own inline
        SHA-256 branch (build_workflow_scripts in scripts/build_phases.py).
      - `.claude/agents/*.md`     -> the `_write` text-equality branch
        (build_agents -> _write, in scripts/build_phases.py).

    Every test drives the REAL installer -- `python <pkg_root>/scripts/
    build.py --target-dir <workspace>` -- as a REAL subprocess (never a
    helper function called directly), against a synthetic, self-hosting-
    layout copy of this repo's OWN real templates/scripts/config trees
    (`pkg_root.parent == workspace`, mirroring production self-hosting -- see
    ADR-001). This layout is REQUIRED for `_compute_output_mappings()` to
    resolve correctly (verified empirically while authoring this file: an
    ordinary `--target-dir` pointed away from the package root, the shape
    most other tests in this repo use, makes output_mappings computation
    raise a path-arithmetic ValueError and produces an EMPTY output_mappings
    section -- exactly the shape that would make ACD-2100d-2's divergence
    determination unable to see anything). The synthetic-package helper is
    never re-implemented here -- it is imported, by file path under a private
    module name, from test_bp_100k_2.py's own `_build_synthetic_full_package`
    (the same real, on-disk templates/scripts/config trees, never a
    hand-typed fixture), exactly as unit_tests/build_guards/
    test_acd_2100d_2.py already does for the identical reason.

RED BASELINE (captured 2026-08-31, before any production-code change, by
    hand-running the exact two-install-plus-mutation sequence each test
    below automates): a fresh synthetic install into a temp workspace,
    editing `.claude/workflows/build-epic.js` (and, separately,
    `.claude/agents/README.md`) with a one-line marker, then re-running the
    same real `build.py --target-dir` against the same workspace -- the
    marker is silently removed (the file is overwritten back to the
    installer's own content, confirming the compare-before-write branch
    already fires and already replaces the file) and NEITHER run's combined
    stdout+stderr contains the phrase "local change is being replaced" or
    the changed file's key anywhere near it. The overwrite already happens;
    the announcement does not exist yet. All four tests below are therefore
    expected to fail RED at authoring time on the phrase/announcement
    assertions.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

_TEST_BP_100K_2_PATH = Path(__file__).resolve().parent / "test_bp_100k_2.py"

_SUBPROCESS_TIMEOUT_SECONDS = 120
_UNIQUE_COUNTER = [0]

# The literal phrase the AC's own Gherkin Then-clause requires: "it states in
# its output for that run that a local change is being replaced and names
# the file". Matched case-insensitively so a coder's exact capitalisation
# choice does not fail this test for a reason unrelated to the behaviour.
_ANNOUNCEMENT_PHRASE = "local change is being replaced"


def _load_bp100k2_module() -> types.ModuleType:
    """Load ``test_bp_100k_2.py`` fresh, by file path, under a unique name.

    Mirrors ``test_acd_2100d_2.py``'s own ``_load_bp100k2_module`` exactly
    (itself mirroring ``test_bp_100k_8.py``'s use of the same pattern): never
    reused across tests via a shared ``sys.modules`` bare-name entry, so each
    call gets its own fully independent module object.

    Returns:
        The freshly executed ``test_bp_100k_2`` module object.
    """
    _UNIQUE_COUNTER[0] += 1
    unique_name = f"_acd2100d2i_test_bp_100k_2_{_UNIQUE_COUNTER[0]}"
    spec = importlib.util.spec_from_file_location(unique_name, _TEST_BP_100K_2_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _run_build(pkg_root: Path, workspace: Path) -> subprocess.CompletedProcess:
    """Invoke the REAL ``scripts/build.py`` CLI as a fresh subprocess.

    This is the actual production entry point an operator running the
    installer would use -- ``python scripts/build.py --target-dir <dir>`` --
    never a helper function (``write_file``, ``_write``,
    ``_files_content_identical``, or a phase function) called directly. Every
    test in this module goes through this one call so that no test can pass
    by accident by exercising a lower-level function that a real install
    never reaches on its own.

    Args:
        pkg_root: The synthetic package root containing ``scripts/build.py``.
        workspace: The target directory to install into (``pkg_root.parent``
            by construction, per the self-hosting layout requirement).

    Returns:
        The completed subprocess result (returncode, stdout, stderr captured
        as text).
    """
    build_script = pkg_root / "scripts" / "build.py"
    return subprocess.run(
        [sys.executable, str(build_script), "--target-dir", str(workspace)],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


def _lines_with_phrase(combined: str, phrase: str) -> list[str]:
    """Return every line of ``combined`` containing ``phrase`` (case-insensitive).

    Args:
        combined: The full stdout+stderr text to scan.
        phrase: Substring to search for, matched case-insensitively.

    Returns:
        List of matching lines, in order of appearance.
    """
    phrase_lower = phrase.lower()
    return [line for line in combined.splitlines() if phrase_lower in line.lower()]


class _BaseInstallerAnnouncementTest(unittest.TestCase):
    """Shared setup: a fresh, self-hosting-layout synthetic install.

    Each test gets its OWN temporary workspace and its OWN first ("Install
    1") real ``build.py`` run -- never shared or reused across tests -- so
    that no test's mutation or assertion can be order-dependent on another
    test's run.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.bp2 = _load_bp100k2_module()
        self.pkg_root = self.bp2._build_synthetic_full_package(self.workspace)

        result_install_1 = _run_build(self.pkg_root, self.workspace)
        self.assertEqual(
            0,
            result_install_1.returncode,
            msg=(
                "setup sanity: the first (clean) real installer run must "
                f"succeed before any mutation.\nstdout:\n{result_install_1.stdout}"
                f"\nstderr:\n{result_install_1.stderr}"
            ),
        )
        self.install_1_combined = result_install_1.stdout + result_install_1.stderr


# ---------------------------------------------------------------------------
# Descriptor 1 (criterion): the announcement fires, and names the file, from
# the workflow-script phase's own inline SHA-256 branch -- the load-bearing
# branch per this AC's own it_requirements.
# ---------------------------------------------------------------------------


class TestInstallAnnouncesLocallyChangedGeneratedFileByName(_BaseInstallerAnnouncementTest):
    """ACD-2100d-2-i criterion angle."""

    def test_install_announces_a_locally_changed_generated_file_by_name(self) -> None:
        # covers: ACD-2100d-2-i
        # angle: criterion
        changed_key = ".claude/workflows/build-epic.js"
        changed_file = self.workspace / changed_key
        self.assertTrue(
            changed_file.exists(),
            f"setup bug: expected a real deployed file at {changed_file}",
        )

        # Land a change ONLY in the installed copy -- the source template
        # (templates/workflows-js/build-epic.js) is never touched, exactly
        # as KI-ACD-004 describes.
        changed_file.write_bytes(
            b"// ACD-2100d-2-i: local edit present only in the installed copy\n"
            + changed_file.read_bytes()
        )

        result_install_2 = _run_build(self.pkg_root, self.workspace)
        combined = result_install_2.stdout + result_install_2.stderr

        self.assertEqual(
            0,
            result_install_2.returncode,
            msg=(
                "The install must still win -- a locally changed generated "
                "file must not make build.py fail or refuse. "
                f"Combined output:\n{combined}"
            ),
        )
        self.assertIn(
            _ANNOUNCEMENT_PHRASE,
            combined.lower(),
            msg=(
                "The second install run's own output must state that a "
                f"local change is being replaced. Combined output:\n{combined}"
            ),
        )
        matching_lines = _lines_with_phrase(combined, _ANNOUNCEMENT_PHRASE)
        self.assertTrue(
            any(changed_key in line for line in matching_lines),
            msg=(
                f"The announcement must name the changed file ({changed_key!r}). "
                f"Lines containing the announcement phrase: {matching_lines!r}"
            ),
        )


# ---------------------------------------------------------------------------
# Descriptor 2 (boundary): the statement appears exactly once and names only
# the changed file -- an unchanged generated file produces no such statement.
# ---------------------------------------------------------------------------


class TestUnchangedGeneratedFilesProduceNoAnnouncement(_BaseInstallerAnnouncementTest):
    """ACD-2100d-2-i boundary angle."""

    def test_unchanged_generated_files_produce_no_announcement(self) -> None:
        # covers: ACD-2100d-2-i
        # angle: boundary
        changed_key = ".claude/workflows/build-epic.js"
        unchanged_key = ".claude/workflows/build-feature.js"
        changed_file = self.workspace / changed_key
        unchanged_file = self.workspace / unchanged_key
        self.assertTrue(changed_file.exists(), f"setup bug: expected {changed_file}")
        self.assertTrue(unchanged_file.exists(), f"setup bug: expected {unchanged_file}")

        changed_file.write_bytes(
            b"// ACD-2100d-2-i: local edit present only in the installed copy\n"
            + changed_file.read_bytes()
        )
        # unchanged_file is deliberately left untouched.

        result_install_2 = _run_build(self.pkg_root, self.workspace)
        combined = result_install_2.stdout + result_install_2.stderr

        matching_lines = _lines_with_phrase(combined, _ANNOUNCEMENT_PHRASE)
        self.assertEqual(
            1,
            len(matching_lines),
            msg=(
                "Exactly one file diverged this run, so the announcement "
                "must appear exactly once -- a message per generated file "
                "(including ones that did not diverge) is noise that gets "
                "filtered and then ignored, which is the same as no message "
                f"at all. Matching lines: {matching_lines!r}\n"
                f"Full combined output:\n{combined}"
            ),
        )
        self.assertIn(
            changed_key,
            matching_lines[0],
            msg=(
                f"The single announcement line must name {changed_key!r}. "
                f"Actual line: {matching_lines[0]!r}"
            ),
        )
        self.assertNotIn(
            unchanged_key,
            matching_lines[0],
            msg=(
                f"The announcement must not also name {unchanged_key!r}, "
                "which was never locally changed. "
                f"Actual line: {matching_lines[0]!r}"
            ),
        )
        # Also guard the risk this AC's own notes flag explicitly: the
        # announcement must not fire for the build manifest the installer
        # writes about itself (every run rewrites .build_manifest.json, so a
        # naive "differs from what I'm about to write" signal with no
        # divergence determination behind it would falsely fire here too,
        # which the exactly-once assertion above would already have caught
        # -- this assertion just names the exact failure mode).
        self.assertFalse(
            any(".build_manifest.json" in line for line in matching_lines),
            msg=(
                "The build manifest itself must never be reported as a "
                "locally-changed generated file being replaced. "
                f"Matching lines: {matching_lines!r}"
            ),
        )


# ---------------------------------------------------------------------------
# Descriptor 3 (real_artifact): after the announced replacement, the file's
# bytes are exactly what the installer produces -- no preservation, no merge.
# ---------------------------------------------------------------------------


class TestInstalledContentsAfterAnnouncedReplacementAreTheInstallersOwn(
    _BaseInstallerAnnouncementTest
):
    """ACD-2100d-2-i real_artifact angle."""

    def test_installed_contents_after_the_announced_replacement_are_the_installers_own(
        self,
    ) -> None:
        # covers: ACD-2100d-2-i
        # angle: real_artifact
        changed_key = ".claude/workflows/build-epic.js"
        changed_file = self.workspace / changed_key
        self.assertTrue(changed_file.exists(), f"setup bug: expected {changed_file}")

        original_bytes = changed_file.read_bytes()
        marker = b"// ACD-2100d-2-i: local edit present only in the installed copy\n"
        changed_file.write_bytes(marker + original_bytes)
        self.assertIn(
            marker,
            changed_file.read_bytes(),
            "setup sanity: the local-edit marker must actually be on disk "
            "before the second install run.",
        )

        result_install_2 = _run_build(self.pkg_root, self.workspace)
        combined = result_install_2.stdout + result_install_2.stderr
        self.assertEqual(
            0,
            result_install_2.returncode,
            msg=f"setup sanity: the second install run must succeed.\n{combined}",
        )
        self.assertIn(
            _ANNOUNCEMENT_PHRASE,
            combined.lower(),
            msg=(
                "setup sanity: the second run must have announced the "
                f"replacement (this is asserted properly by the criterion "
                f"descriptor; here it only gates this test's own meaning). "
                f"Combined output:\n{combined}"
            ),
        )

        after_bytes = changed_file.read_bytes()
        self.assertNotIn(
            marker,
            after_bytes,
            msg=(
                "The announced replacement must actually replace the file "
                f"-- the local-edit marker is still present. Tail of file: "
                f"{after_bytes[-200:]!r}"
            ),
        )
        self.assertEqual(
            original_bytes,
            after_bytes,
            msg=(
                "The file's contents after the announced replacement must "
                "be EXACTLY what the installer produces -- not a "
                "preservation of the local edit and not a merge of the two. "
                "This is the installer's own clean-install output, read "
                "back from disk after the real subprocess run."
            ),
        )


# ---------------------------------------------------------------------------
# Descriptor 4 (reachability): the announcement is observed in the real
# installer's captured output in a fresh process -- never from a helper
# called directly -- exercised here against a DIFFERENT compare-before-write
# branch (_write, via build_agents) than descriptors 1-3 use, so that an
# implementation instrumenting only one branch cannot pass every test in
# this module by accident.
# ---------------------------------------------------------------------------


class TestAnnouncementIsProducedByRunningTheRealInstaller(_BaseInstallerAnnouncementTest):
    """ACD-2100d-2-i reachability angle.

    Never imports ``build`` or ``build_phases`` as Python modules and never
    calls ``write_file`` / ``_write`` / ``_files_content_identical`` (or any
    phase function) directly -- the ENTIRE exercise, for both installs, is
    two ``subprocess.run`` invocations of the real ``scripts/build.py`` CLI
    (see ``_run_build`` / setUp above), each a genuinely fresh Python
    process. A duplicated or dead entry point that never reaches the real
    write path (the exact class of regression BP-100k-3's DECISION HISTORY
    records for a different gate) cannot pass this test by accident.
    """

    def test_announcement_is_produced_by_running_the_real_installer(self) -> None:
        # covers: ACD-2100d-2-i
        # angle: reachability
        # Deliberately a different branch to descriptors 1-3: `_write`
        # (build_agents), not the workflow-script phase's inline SHA-256
        # branch.
        changed_key = ".claude/agents/README.md"
        changed_file = self.workspace / changed_key
        self.assertTrue(changed_file.exists(), f"setup bug: expected {changed_file}")

        original_text = changed_file.read_text(encoding="utf-8")
        changed_file.write_text(
            "<!-- ACD-2100d-2-i: local edit present only in the installed copy -->\n"
            + original_text,
            encoding="utf-8",
        )

        result_install_2 = _run_build(self.pkg_root, self.workspace)
        combined = result_install_2.stdout + result_install_2.stderr

        self.assertEqual(
            0,
            result_install_2.returncode,
            msg=(
                "The real installer subprocess must exit 0 even while "
                f"announcing a replaced local change.\nCombined output:\n{combined}"
            ),
        )
        self.assertNotIn(
            "Traceback (most recent call last):",
            combined,
            msg=(
                "The real installer process must not have crashed while "
                f"producing the announcement.\nCombined output:\n{combined}"
            ),
        )
        self.assertIn(
            _ANNOUNCEMENT_PHRASE,
            combined.lower(),
            msg=(
                "The real installer's own captured subprocess output (never "
                "a helper's return value) must contain the announcement. "
                f"Combined output:\n{combined}"
            ),
        )
        matching_lines = _lines_with_phrase(combined, _ANNOUNCEMENT_PHRASE)
        self.assertTrue(
            any(changed_key in line for line in matching_lines),
            msg=(
                f"The announcement observed in the real installer's output "
                f"must name {changed_key!r}. Matching lines: {matching_lines!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
