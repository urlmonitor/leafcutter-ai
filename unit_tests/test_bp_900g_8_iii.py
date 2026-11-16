"""
MODULE: test_bp_900g_8_iii
GOAL: Pin BP-900g-8-iii: the CLAUDE.md rule "New Hook / Gate Dependencies Must Be
    in the Build Deploy-Manifest" defines a deploy dependency as ANY file a
    guardrail reads (modules, schemas, vocabularies, registries, data tables),
    describes the data-file symptom, names the deployed-layout verification and
    why the package workspace cannot do it, gives a non-code worked example, and
    points at the mechanism that enforces it.
BUSINESS CONTEXT: The rule used to define the class by the error a missing module
    raises, so a configuration JSON (which raises FileNotFoundError, or is silently
    skipped) looked out of scope. Five gaps on 2026-08-18 were in the rule's intent
    and outside its wording.

NOTE ON SCOPE: CLAUDE.md is not deployed to consumer installs (ADR-001), so the
    artifact under test is the source CLAUDE.md itself; there is no deployed copy
    to read and this test does not use the shared reference layout. The wording
    claims are tied to reality by importing the named mechanism and checking the
    named example files exist.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_HEADING = "### New Hook / Gate Dependencies Must Be in the Build Deploy-Manifest"


def _rule_section() -> str:
    text = (_REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    start = text.index(_HEADING)
    nxt = re.search(r"^### ", text[start + len(_HEADING):], flags=re.MULTILINE)
    end = start + len(_HEADING) + nxt.start() if nxt else len(text)
    return text[start:end]


class TestDeployDependencyRuleWording(unittest.TestCase):
    """Each test fails on the pre-change wording (module-only definition)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.section = _rule_section()
        cls.lower = cls.section.lower()

    # covers: BP-900g-8-iii
    def test_dependency_class_is_any_file_read_not_only_imported_modules(self) -> None:
        self.assertRegex(self.lower, r"any file[^.]*\b(reads|read)\b")
        for kind in ("schema", "vocabular", "registr", "data table"):
            self.assertIn(kind, self.lower, f"rule must name {kind!r} files")

    # covers: BP-900g-8-iii
    def test_data_file_symptom_is_described_as_concretely_as_the_module_case(self) -> None:
        self.assertIn("ModuleNotFoundError", self.section)
        self.assertIn("FileNotFoundError", self.section)
        self.assertRegex(self.lower, r"silent")

    # covers: BP-900g-8-iii
    def test_names_deployed_install_verification_and_why_the_workspace_cannot(self) -> None:
        self.assertRegex(self.lower, r"install that does not contain the package")
        self.assertRegex(self.lower, r"(source tree|workspace)[^.]*(contains|has) every")

    # covers: BP-900g-8-iii
    def test_worked_example_is_a_real_non_code_declaring_file(self) -> None:
        examples = re.findall(r"config/[A-Za-z0-9_]+\.json", self.section)
        self.assertTrue(examples, "rule must cite a config/*.json worked example")
        for rel in examples:
            self.assertTrue((_REPO_ROOT / rel).is_file(), f"{rel} cited but absent")

    # covers: BP-900g-8-iii
    def test_points_at_the_enforcing_mechanism_and_it_exists(self) -> None:
        import build  # noqa: PLC0415 -- after sys.path setup
        import build_referential_integrity as bri  # noqa: PLC0415

        self.assertIn("_check_intra_package_closure_guard", self.section)
        self.assertIn("compute_intra_package_closure", self.section)
        self.assertTrue(callable(getattr(build, "_check_intra_package_closure_guard", None)))
        self.assertTrue(callable(getattr(bri, "compute_intra_package_closure", None)))
        self.assertIn("BP-900g-8-ii", self.section)


if __name__ == "__main__":
    unittest.main()
