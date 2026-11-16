"""
MODULE: unit_tests/portability/ge_120e_2/test_ge_120e_2_consumers_and_reachability.py
AC: GE-120e-2 — "Which checks work out their own change set is read from
    the manifest, not from the two that were caught"
GOAL: Tests 7-8 of the GE-120e-2 suite: adding change_set_source to every
    manifest entry leaves the manifest's existing consumers (the generated
    .pre-commit-config.yaml and check_hook_parity) unaffected (7), and the
    determination is reachable through the DEPLOYED change_set_source.py
    CLI, its exit code and its output (8).
CONTRACT: see the module docstring of ``_support.py`` in this package
    ("CONTRACT ASSUMED") for the CLI entry point test 8 drives.

DECISION HISTORY:
- 2026-11-16 [split-oversized-tests]: Moved here unchanged from
  unit_tests/portability/test_ge_120e_2.py when that file was split; the
  reachability class now declares its setUpClass attributes for the type
  checker.
"""
# @ac-tag: GE-120e-2

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar
from unittest import mock

from unit_tests.portability.ge_120e_2._support import (
    _ALLOWED_SOURCE_VALUES,
    _COMMIT_GUARDIAN_TEMPLATES,
    _REAL_MANIFEST_PATH,
    _write_fixture_manifest,
    _write_handed_its_files_script,
)

# ---------------------------------------------------------------------------
# build_phases (for the reachability test's deployed-copy check) and
# build_precommit / check_hook_parity (for the regression-guard test).
# ---------------------------------------------------------------------------
try:
    from build_phases import build_commit_guardian
    _BUILD_PHASES_OK = True
except (ImportError, ModuleNotFoundError):
    build_commit_guardian = None
    _BUILD_PHASES_OK = False

try:
    import build_phases as _build_phases_module
    import build_precommit as _build_precommit_module
    _BUILD_PRECOMMIT_OK = True
except (ImportError, ModuleNotFoundError):
    _build_phases_module = None
    _build_precommit_module = None
    _BUILD_PRECOMMIT_OK = False

if str(_COMMIT_GUARDIAN_TEMPLATES) not in sys.path:
    sys.path.insert(0, str(_COMMIT_GUARDIAN_TEMPLATES))

try:
    from check_hook_parity import check_manifest_parity
    _CHECK_HOOK_PARITY_OK = True
except (ImportError, ModuleNotFoundError):
    check_manifest_parity = None
    _CHECK_HOOK_PARITY_OK = False


# ---------------------------------------------------------------------------
# Test 7 — angle: seam
# ---------------------------------------------------------------------------
class TestAddedFieldLeavesPrecommitConfigGenerationAndHookParityIntact(unittest.TestCase):
    """Implementation Notes: "DO NOT BREAK THE MANIFEST'S EXISTING
    CONSUMERS." Real-artifact, cross-layer test: pipe the REAL manifest
    (with change_set_source added to every entry) through the REAL
    build_precommit_config() and the REAL check_hook_parity's
    check_manifest_parity(), and assert both are byte-for-byte /
    violation-for-violation unaffected by the new key's presence."""

    def test_ge120e2_added_field_leaves_precommit_config_generation_and_hook_parity_intact(self) -> None:
        # covers: GE-120e-2
        # angle: seam
        """Two-part test.

        Part 1 (RED TODAY, independent of the determination module): reads
        the REAL, installed templates/scripts/commit_guardian/commit_guardian.json
        and asserts every entry already carries a valid change_set_source
        value — false until python-coder lands the per-entry field, which is
        this test's own genuine red signal distinct from the ImportError
        gate every other test in this file relies on.

        Part 2 (regression guard, exercises the REAL production code):
        synthesises a "before" (field-stripped) and "after" (field-added to
        every entry) copy of the REAL manifest, runs the REAL
        build_precommit_config() against each via a temporary
        build_phases.TEMPLATES_DIR, and asserts the two generated
        .pre-commit-config.yaml files are byte-identical — proving the new
        key has zero effect on generation. Separately runs the REAL
        check_manifest_parity() between the two variants and asserts zero
        violations — proving the new key does not break id-based parity.
        """
        real_raw = json.loads(_REAL_MANIFEST_PATH.read_text(encoding="utf-8"))
        real_hooks = real_raw.get("hooks_manifest", {}).get("hooks", [])
        self.assertTrue(real_hooks, "The real manifest must have at least one hook entry.")

        missing_or_invalid = [
            h.get("id", "?") for h in real_hooks
            if h.get("change_set_source") not in _ALLOWED_SOURCE_VALUES
        ]
        self.assertEqual(
            [],
            missing_or_invalid,
            "Every entry in the REAL installed manifest must carry a valid "
            "change_set_source (handed_by_commit_path / self_derived) once "
            "GE-120e-2 lands. Entries still missing or invalid: "
            f"{missing_or_invalid!r}.",
        )

        if not _BUILD_PRECOMMIT_OK:
            self.fail(
                "scripts.build_precommit / scripts.build_phases could not be "
                "imported — cannot exercise the real build_precommit_config() "
                "regression guard."
            )
        if not _CHECK_HOOK_PARITY_OK:
            self.fail(
                "templates/scripts/commit_guardian/check_hook_parity.py "
                "could not be imported — cannot exercise the real "
                "check_manifest_parity() regression guard."
            )

        before_hooks = copy.deepcopy(real_hooks)
        for hook in before_hooks:
            hook.pop("change_set_source", None)
        after_hooks = copy.deepcopy(real_hooks)
        for hook in after_hooks:
            hook.setdefault("change_set_source", "handed_by_commit_path")

        config = {
            "output_root": ".leafcutter",
            "agents_dir": ".claude/agents",
            "skills_dir": ".claude/skills",
        }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            before_cg_root = tmp_path / "before"
            after_cg_root = tmp_path / "after"
            before_target = tmp_path / "before_target"
            after_target = tmp_path / "after_target"
            for d in (before_cg_root, after_cg_root, before_target, after_target):
                d.mkdir(parents=True, exist_ok=True)

            before_manifest_dir = before_cg_root / "scripts" / "commit_guardian"
            after_manifest_dir = after_cg_root / "scripts" / "commit_guardian"
            before_manifest_dir.mkdir(parents=True, exist_ok=True)
            after_manifest_dir.mkdir(parents=True, exist_ok=True)

            (before_manifest_dir / "commit_guardian.json").write_text(
                json.dumps({"hooks_manifest": {"hooks": before_hooks}}), encoding="utf-8",
            )
            (after_manifest_dir / "commit_guardian.json").write_text(
                json.dumps({"hooks_manifest": {"hooks": after_hooks}}), encoding="utf-8",
            )

            with mock.patch.object(_build_phases_module, "TEMPLATES_DIR", before_cg_root):
                _build_precommit_module.build_precommit_config(
                    before_target, config, dry_run=False, force=True,
                )
            with mock.patch.object(_build_phases_module, "TEMPLATES_DIR", after_cg_root):
                _build_precommit_module.build_precommit_config(
                    after_target, config, dry_run=False, force=True,
                )

            before_yaml = (before_target / "pre-commit-config.yaml").read_text(encoding="utf-8")
            after_yaml = (after_target / "pre-commit-config.yaml").read_text(encoding="utf-8")
            self.assertEqual(
                before_yaml, after_yaml,
                "Adding change_set_source to every manifest entry must leave "
                ".pre-commit-config.yaml byte-for-byte identical — "
                "_render_hook_yaml() must not read the new key.",
            )

            violations = check_manifest_parity(
                after_manifest_dir / "commit_guardian.json",
                before_manifest_dir / "commit_guardian.json",
            )
            self.assertEqual(
                [], violations,
                "check_manifest_parity() must report zero violations between "
                "the field-added and field-stripped variants of the same "
                f"manifest — id set must be unaffected. Got: {violations!r}.",
            )


# ---------------------------------------------------------------------------
# Test 8 — angle: reachability (REQUIRED by test_spec; entry point resolved
# in the CONTRACT ASSUMED section of _support.py's module docstring)
# ---------------------------------------------------------------------------
class TestReachableFromEntryPoint(unittest.TestCase):
    """REQUIRED reachability angle: invoke the DEPLOYED copy of
    change_set_source.py (scripts/commit_guardian/, not
    templates/scripts/commit_guardian/) as a real subprocess CLI, passing a
    fixture manifest path as argv, and assert the exit code and printed
    output are the mechanism by which a caller (e.g. a future commit-time
    hook registration) would actually consume this determination — not by
    importing determine_change_set_sources and calling it directly."""

    _tmp: ClassVar[tempfile.TemporaryDirectory[str]]
    fixture_root: ClassVar[Path]
    deployed_ok: ClassVar[bool]
    deployed_script: ClassVar[Path]

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.fixture_root = Path(cls._tmp.name)
        cls.deployed_ok = False
        if _BUILD_PHASES_OK:
            written = build_commit_guardian(
                cls.fixture_root,
                {
                    "output_root": ".leafcutter",
                    "agents_dir": ".claude/agents",
                    "skills_dir": ".claude/skills",
                },
                dry_run=False,
                force=True,
            )
            cls.deployed_script = (
                cls.fixture_root / "scripts" / "commit_guardian" / "change_set_source.py"
            )
            cls.deployed_ok = written > 0 and cls.deployed_script.exists()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_ge_120e_2_reachable_from_entry_point(self) -> None:
        # covers: GE-120e-2
        # angle: reachability
        """Runs the DEPLOYED (scripts/commit_guardian/, not
        templates/scripts/commit_guardian/) copy of change_set_source.py as
        a real subprocess, pointed at a fixture manifest containing one
        deliberately-broken entry, and asserts (a) the process exits
        non-zero and (b) the offending id appears in the combined
        stdout+stderr — proving the failure is actually surfaced through
        the production entry point's own observable output/exit-code
        control flow, not merely returned from a function nobody calls.
        """
        if not _BUILD_PHASES_OK:
            self.fail(
                "scripts.build_phases.build_commit_guardian could not be "
                "imported — cannot deploy the commit_guardian scripts into "
                "the fixture directory to test the deployed entry point."
            )
        if not self.deployed_ok:
            self.fail(
                "build_commit_guardian() did not produce a deployed "
                f"{self.fixture_root}/scripts/commit_guardian/change_set_source.py "
                "— GE-120e-2 has not landed a deployable module yet."
            )

        import subprocess

        handed_script = _write_handed_its_files_script(self.fixture_root)
        broken_manifest = _write_fixture_manifest(
            self.fixture_root,
            hooks=[{
                "id": "check-reachability-broken-entry",
                "entry": str(handed_script),
                # no change_set_source -> must be reported as a failure.
            }],
            name="reachability_broken.json",
        )

        result = subprocess.run(
            ["python3", str(self.deployed_script), str(broken_manifest)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertNotEqual(
            0, result.returncode,
            "The DEPLOYED change_set_source.py CLI must exit non-zero when "
            f"the given manifest names a failure. stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        combined = result.stdout + result.stderr
        self.assertIn(
            "check-reachability-broken-entry", combined,
            f"The CLI's output must name the offending check. Output: {combined!r}",
        )

        clean_manifest = _write_fixture_manifest(
            self.fixture_root,
            hooks=[{
                "id": "check-reachability-clean-entry",
                "entry": str(handed_script),
                "change_set_source": "handed_by_commit_path",
            }],
            name="reachability_clean.json",
        )
        clean_result = subprocess.run(
            ["python3", str(self.deployed_script), str(clean_manifest)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(
            0, clean_result.returncode,
            "The DEPLOYED change_set_source.py CLI must exit 0 for a "
            f"manifest with no failures. stdout={clean_result.stdout!r} "
            f"stderr={clean_result.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
