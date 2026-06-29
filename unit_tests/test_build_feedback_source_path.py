"""
MODULE: unit_tests/test_build_feedback_source_path.py
GOAL: Regression tests for AC BP-1000a-5 — the build reads feedback deployable-script
    source from templates/scripts/feedback/ (the tracked templates mirror), NOT from
    scripts/feedback/ (the gitignored working-tree copy).
BUSINESS CONTEXT: On a fresh checkout scripts/feedback/ does not exist (it is gitignored).
    The only committed source lives under templates/scripts/feedback/ (mirroring the
    templates/scripts/commit_guardian/ pattern). Both _manifest_feedback_scripts() in
    build.py and build_feedback() in build_phases.py must read from the tracked mirror.

These tests are INTENTIONALLY RED before the fix. They assert the corrected behaviour
that python-coder must implement.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

sys.path.insert(0, str(_SCRIPTS_DIR))

import build_phases
import build


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_package_root(tmp_path):
    """Create a minimal fake package root with templates/scripts/feedback/ populated
    and NO scripts/feedback/ directory — simulating a fresh checkout."""
    pkg = tmp_path / "leafcutter_pkg"
    pkg.mkdir()

    # Create tracked mirror: templates/scripts/feedback/
    templates_feedback = pkg / "templates" / "scripts" / "feedback"
    templates_feedback.mkdir(parents=True)
    (templates_feedback / "submit_feedback.py").write_text("# submit_feedback stub\n", encoding="utf-8")
    (templates_feedback / "emit_hook_finding.py").write_text("# emit_hook_finding stub\n", encoding="utf-8")
    (templates_feedback / "list_tags.py").write_text("# list_tags stub\n", encoding="utf-8")
    (templates_feedback / "aggregate.py").write_text("# aggregate stub\n", encoding="utf-8")
    (templates_feedback / "resolve_feedback.py").write_text("# resolve_feedback stub\n", encoding="utf-8")

    # Deliberately do NOT create scripts/feedback/ — this is the gitignored location.
    # Asserting it is absent makes the test's precondition explicit.
    assert not (pkg / "scripts" / "feedback").exists(), (
        "Fixture error: scripts/feedback/ must NOT exist — it is gitignored on fresh checkout"
    )

    return pkg


@pytest.fixture()
def target_root(tmp_path):
    """Return a temporary target project root."""
    root = tmp_path / "target"
    root.mkdir()
    return root


# ---------------------------------------------------------------------------
# Tests for _manifest_feedback_scripts() in build.py
# ---------------------------------------------------------------------------


class TestManifestFeedbackScripts:
    """AC BP-1000a-5: _manifest_feedback_scripts() must read from templates/scripts/feedback/."""

    def test_ac_bp1000a5_manifest_reads_from_templates_mirror(self, fake_package_root):
        # covers: BP-1000a-5
        """The manifest helper must discover scripts from templates/scripts/feedback/,
        not from the gitignored scripts/feedback/ directory.

        Before the fix this test is RED because _manifest_feedback_scripts() reads from
        PACKAGE_ROOT/scripts/feedback/ which does not exist in the fixture, returning
        an empty set instead of the expected 5-entry set.
        """
        result = build._manifest_feedback_scripts(fake_package_root)

        assert result, (
            "_manifest_feedback_scripts() returned empty set — it is reading from "
            "scripts/feedback/ (absent) instead of templates/scripts/feedback/ (populated)."
        )
        assert "scripts/feedback/submit_feedback.py" in result
        assert "scripts/feedback/emit_hook_finding.py" in result
        assert "scripts/feedback/list_tags.py" in result
        assert "scripts/feedback/aggregate.py" in result
        assert "scripts/feedback/resolve_feedback.py" in result

    def test_ac_bp1000a5_manifest_does_not_require_gitignored_dir(self, fake_package_root):
        # covers: BP-1000a-5
        """The manifest must return a non-empty result even when scripts/feedback/ is absent.

        This asserts the 'does not require scripts/feedback/' part of the AC.
        """
        gitignored_dir = fake_package_root / "scripts" / "feedback"
        assert not gitignored_dir.exists(), "Precondition: scripts/feedback/ must be absent"

        result = build._manifest_feedback_scripts(fake_package_root)

        # Non-empty result proves the function did not silently depend on the absent dir.
        assert len(result) >= 5, (
            f"Expected at least 5 manifest entries, got {len(result)}. "
            "The function requires scripts/feedback/ to be present (it shouldn't)."
        )

    def test_ac_bp1000a5_manifest_ignores_gitignored_dir_if_present(self, fake_package_root):
        # covers: BP-1000a-5
        """When scripts/feedback/ happens to exist (working-tree copy), the manifest must
        STILL read from templates/scripts/feedback/ — not from the gitignored location.

        We populate scripts/feedback/ with a different file to detect which source wins.
        """
        gitignored_dir = fake_package_root / "scripts" / "feedback"
        gitignored_dir.mkdir(parents=True)
        # Add a decoy file that only exists in the gitignored dir
        (gitignored_dir / "only_in_gitignored.py").write_text("# decoy\n", encoding="utf-8")

        result = build._manifest_feedback_scripts(fake_package_root)

        # The tracked templates/scripts/feedback/ files must appear
        assert "scripts/feedback/submit_feedback.py" in result, (
            "submit_feedback.py from templates/scripts/feedback/ not found in manifest"
        )
        # The gitignored-only file must NOT appear (or if both dirs are read, this assertion
        # is the discriminator that proves templates/ wins)
        assert "scripts/feedback/only_in_gitignored.py" not in result, (
            "Decoy file from gitignored scripts/feedback/ appeared in manifest — "
            "the function is reading from the wrong source directory."
        )


# ---------------------------------------------------------------------------
# Tests for build_feedback() in build_phases.py
# ---------------------------------------------------------------------------


class TestBuildFeedbackSourcePath:
    """AC BP-1000a-5: build_feedback() must source from templates/scripts/feedback/."""

    def test_ac_bp1000a5_build_feedback_deploys_from_templates(
        self, fake_package_root, target_root, monkeypatch
    ):
        # covers: BP-1000a-5
        """build_feedback() must deploy scripts even when scripts/feedback/ is absent,
        by reading from templates/scripts/feedback/ instead.

        Before the fix this test is RED because build_feedback() checks
        PACKAGE_ROOT / "scripts" / "feedback" which does not exist, returns 0,
        and deploys nothing.
        """
        monkeypatch.setattr(build_phases, "PACKAGE_ROOT", fake_package_root)

        written = build_phases.build_feedback(target_root, {}, dry_run=False, force=True)

        assert written > 0, (
            "build_feedback() wrote 0 files. It requires scripts/feedback/ to be present "
            "(it doesn't exist in fixture) instead of reading from templates/scripts/feedback/."
        )

    def test_ac_bp1000a5_build_feedback_nonzero_without_gitignored_dir(
        self, fake_package_root, target_root, monkeypatch
    ):
        # covers: BP-1000a-5
        """build_feedback() must return non-zero even when scripts/feedback/ is absent.

        This directly asserts the AC clause: 'the build does not require any file under
        the gitignored scripts/feedback/ directory to be present'.
        """
        monkeypatch.setattr(build_phases, "PACKAGE_ROOT", fake_package_root)

        gitignored_dir = fake_package_root / "scripts" / "feedback"
        assert not gitignored_dir.exists(), "Precondition: scripts/feedback/ must be absent"

        result = build_phases.build_feedback(target_root, {}, dry_run=False, force=True)

        assert result > 0, (
            f"build_feedback() returned {result} with only templates/scripts/feedback/ present. "
            "It must succeed without scripts/feedback/ (gitignored)."
        )

    def test_ac_bp1000a5_deployed_scripts_match_templates_feedback(
        self, fake_package_root, target_root, monkeypatch
    ):
        # covers: BP-1000a-5
        """The scripts deployed by build_feedback() must match the files present under
        templates/scripts/feedback/ — not an arbitrary hardcoded list.
        """
        monkeypatch.setattr(build_phases, "PACKAGE_ROOT", fake_package_root)

        build_phases.build_feedback(target_root, {}, dry_run=False, force=True)

        templates_src = fake_package_root / "templates" / "scripts" / "feedback"
        expected_names = {f.name for f in templates_src.iterdir() if f.is_file()}

        deployed_dir = target_root / "scripts" / "feedback"
        assert deployed_dir.exists(), (
            "scripts/feedback/ was not created in target — build_feedback() deployed nothing."
        )
        deployed_names = {f.name for f in deployed_dir.iterdir() if f.is_file()}

        # Every file in templates/scripts/feedback/ must appear in the deployed output
        missing = expected_names - deployed_names
        assert not missing, (
            f"Files present in templates/scripts/feedback/ but not deployed: {missing}. "
            "build_feedback() is reading from the wrong source."
        )

    def test_ac_bp1000a5_build_feedback_uses_templates_dir_constant(
        self, fake_package_root, target_root, monkeypatch
    ):
        # covers: BP-1000a-5
        """Validate via source inspection: build_feedback() must reference
        TEMPLATES_DIR / 'scripts' / 'feedback' (or equivalent), NOT
        PACKAGE_ROOT / 'scripts' / 'feedback'.

        We patch TEMPLATES_DIR to the fake templates location and verify
        that build_feedback finds files from there.
        """
        templates_dir = fake_package_root / "templates"
        monkeypatch.setattr(build_phases, "PACKAGE_ROOT", fake_package_root)
        monkeypatch.setattr(build_phases, "TEMPLATES_DIR", templates_dir)

        written = build_phases.build_feedback(target_root, {}, dry_run=False, force=True)

        assert written > 0, (
            f"build_feedback() wrote {written} files after patching TEMPLATES_DIR to "
            f"{templates_dir}. The function is not using TEMPLATES_DIR as its source."
        )
