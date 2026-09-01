"""
MODULE: unit_tests/commit_guardian/test_ge_122d_1_single_rule_change.py
GOAL: Cover GE-122d-1's ``test_single_rule_change_propagates_to_all_three_stages``
    descriptor.
AC: docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-1.yaml
BUSINESS CONTEXT: "Given the rule is then extended so that a number shape
    previously accepted is now contested, with that extension made in ONE
    place... Then all three stages report the newly contested case." This
    test performs that single-place extension itself, against a scratch copy
    of the real deployed files, and confirms every real, invocable stage
    entry point observes it with no second edit made anywhere.

    THE CHOSEN "PREVIOUSLY ACCEPTED" SHAPE: two ADR filenames whose numeric
    segments are the same integer under two different string spellings --
    ``ADR-001-alpha.md`` and ``ADR-1-beta.md``. Confirmed empirically
    (2026-09-01) that today's ``scan_decisions`` treats these as two
    DIFFERENT numbers (raw string comparison of the regex capture group,
    ``"001" != "1"``), so this fixture reports ``passed=True`` (clean) at
    every stage before any edit. The single-place extension made by this
    test -- widening ``scan_decisions``'s ``number_of`` callable from
    ``lambda m: m.group(1)`` to ``lambda m: str(int(m.group(1)))`` -- is
    exactly the "ONE place" _uniqueness_scanners.py's own architecture
    already supports: both the commit-time module and the authoring-time
    module resolve their sibling scanner import from the SAME file on disk
    (see check_identifier_uniqueness_authoring.py's ARCHITECTURE note), so
    editing that one file's one line is a real single-place extension, not
    a simulated one.
ARCHITECTURE: Copies templates/scripts/commit_guardian/*.py and
    templates/hooks/check_identifier_uniqueness_authoring.py into a scratch
    "hooks/" + "scripts/commit_guardian/" deployed-shaped layout (mirroring
    test_ge_122d_6.py's precedent), asserts the BEFORE state is clean at
    both stages, edits the ONE shared file, then asserts the AFTER state is
    contested at both stages -- with the commit-time stage additionally
    invoked as a REAL subprocess CLI call (``python
    check_identifier_uniqueness.py``, matching this module's own documented
    CLI usage) rather than an in-process function call, per this
    repository's "Verify Behaviorally, Not by Grep" and reachability
    conventions.

DOC_LINKS:
  - templates/scripts/commit_guardian/_uniqueness_scanners.py
  - templates/hooks/check_identifier_uniqueness_authoring.py

DECISION HISTORY:
  - 2026-09-01 [test-writer/GE-122d-1]: Created. Confirmed empirically that
    the BEFORE fixture (ADR-001-alpha.md / ADR-1-beta.md) reports
    ``passed=True`` (not contested) at the commit-time stage today, and that
    editing _uniqueness_scanners.py's ``scan_decisions`` ``number_of``
    lambda to normalize via ``int()`` makes the same fixture report
    ``passed=False`` -- establishing this as a genuine, currently-true
    "previously accepted, now contested" shape, not a fabricated one.
"""
from __future__ import annotations

import importlib.util as _ilu
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_AUTHORING_SRC = _REPO_ROOT / "templates" / "hooks" / "check_identifier_uniqueness_authoring.py"
_COMMIT_STAGE_SRC = _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_identifier_uniqueness.py"
_SHARED_SRC_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"

_OLD_NUMBER_OF = "lambda m: m.group(1)"
_NEW_NUMBER_OF = "lambda m: str(int(m.group(1)))"


def _load_module(path: Path, name: str):
    """Load a module fresh from an explicit file path (never from sys.path)."""
    spec = _ilu.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not resolve a module spec/loader for {path}.")
    module = _ilu.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _build_leading_zero_fixture(root: Path) -> None:
    """A real, on-disk collection where two ADR filenames name the SAME
    integer under two different digit-string spellings."""
    (root / "docs" / "acceptance-criteria").mkdir(parents=True, exist_ok=True)
    adrs = root / "docs" / "architecture" / "adrs"
    adrs.mkdir(parents=True, exist_ok=True)
    (adrs / "ADR-001-alpha.md").write_text("# alpha\n", encoding="utf-8")
    (adrs / "ADR-1-beta.md").write_text("# beta\n", encoding="utf-8")
    (root / "docs" / "architecture" / "diagrams").mkdir(parents=True, exist_ok=True)
    tickets_dir = root / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    (tickets_dir / "ticket_lifecycle.json").write_text(json.dumps({"folders": []}), encoding="utf-8")


class TestSingleRuleChangePropagatesToAllStages(unittest.TestCase):
    def setUp(self) -> None:
        self._scratch_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._scratch_tmp.cleanup)
        self.scratch_root = Path(self._scratch_tmp.name)

        self.scripts_dir = self.scratch_root / "scripts" / "commit_guardian"
        self.scripts_dir.mkdir(parents=True)
        for src in _SHARED_SRC_DIR.glob("*.py"):
            shutil.copy2(src, self.scripts_dir / src.name)

        self.hooks_dir = self.scratch_root / "hooks"
        self.hooks_dir.mkdir(parents=True)
        self.deployed_authoring = self.hooks_dir / _AUTHORING_SRC.name
        shutil.copy2(_AUTHORING_SRC, self.deployed_authoring)

        self.deployed_commit = self.scripts_dir / _COMMIT_STAGE_SRC.name
        self.scanners_path = self.scripts_dir / "_uniqueness_scanners.py"

        self._fixture_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._fixture_tmp.cleanup)
        self.fixture_root = Path(self._fixture_tmp.name)
        _build_leading_zero_fixture(self.fixture_root)

    def _clear_shared_sys_modules(self) -> None:
        for name in (
            "_uniqueness_scanners",
            "_uniqueness_types",
            "_work_items_scanner",
            "_commit_disposition",
            "check_identifier_uniqueness",
        ):
            sys.modules.pop(name, None)

    def _run_commit_stage_cli(self) -> subprocess.CompletedProcess[str]:
        """Invoke the REAL CLI entry point as a fresh subprocess -- the
        actual command form a pre-commit hook or a developer runs."""
        return subprocess.run(
            [sys.executable, str(self.deployed_commit)],
            cwd=str(self.fixture_root),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def _apply_single_place_extension(self) -> None:
        content = self.scanners_path.read_text(encoding="utf-8")
        self.assertIn(
            _OLD_NUMBER_OF,
            content,
            "The expected single-place extension seam "
            "(_uniqueness_scanners.py's scan_decisions number_of lambda) is not "
            "present in the form this test expects -- the seam this AC requires "
            "may have moved or already been renamed. Update this test's constants.",
        )
        self.scanners_path.write_text(content.replace(_OLD_NUMBER_OF, _NEW_NUMBER_OF), encoding="utf-8")

    def test_single_rule_change_propagates_to_all_three_stages(self) -> None:
        # covers: GE-122d-1
        # angle: boundary
        # --- BEFORE: the leading-zero shape is accepted (not contested) ---
        self._clear_shared_sys_modules()
        before_result = self._run_commit_stage_cli()
        self.assertEqual(
            before_result.returncode,
            0,
            "BEFORE the single-place extension, the leading-zero ADR shape must "
            f"be accepted (exit 0). Got exit {before_result.returncode}, "
            f"stderr:\n{before_result.stderr}",
        )

        self._clear_shared_sys_modules()
        authoring_before = _load_module(self.deployed_authoring, "single_rule_authoring_before")
        payload_before = json.loads(authoring_before.evaluate_identifier_uniqueness(str(self.fixture_root)))
        self.assertTrue(
            payload_before["passed"],
            "BEFORE the single-place extension, the authoring stage must also "
            "report the leading-zero ADR shape as clean.",
        )

        # --- THE SINGLE-PLACE EXTENSION (made in ONE file) ---
        self._apply_single_place_extension()

        # --- AFTER: no second or third definition of the rule was touched ---
        self._clear_shared_sys_modules()
        after_result = self._run_commit_stage_cli()
        self.assertEqual(
            after_result.returncode,
            1,
            "AFTER the single-place extension, the commit-time stage (invoked "
            "as a real CLI subprocess) must report the leading-zero ADR shape "
            f"as contested (exit 1). Got exit {after_result.returncode}, "
            f"stdout:\n{after_result.stdout}\nstderr:\n{after_result.stderr}",
        )

        self._clear_shared_sys_modules()
        authoring_after = _load_module(self.deployed_authoring, "single_rule_authoring_after")
        payload_after = json.loads(authoring_after.evaluate_identifier_uniqueness(str(self.fixture_root)))
        self.assertFalse(
            payload_after["passed"],
            "AFTER the single-place extension -- made ONLY in "
            "_uniqueness_scanners.py, never in the authoring hook module -- the "
            "authoring stage must ALSO report the leading-zero ADR shape as "
            "contested. If this fails while the commit-time subprocess above "
            "reports contested, the two stages hold independent copies of the "
            "rule (GE-122d-1's coverage note names this exact failure).",
        )
        self.assertIn("1", payload_after.get("contested_numbers", []))


if __name__ == "__main__":
    unittest.main()
